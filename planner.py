#!/usr/bin/env python3
"""CLI для локального расписания и списка задач."""

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

DATA_DIR = Path(__file__).resolve().parent / "src" / "data"


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def read(name):
    path = DATA_DIR / name
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Не удалось прочитать {path}: {error}") from error
    if not isinstance(data, list):
        raise ValueError(f"{path} должен содержать JSON-массив")
    if name == "events.json" and any(item.get("recurrence") for item in data):
        data = [occurrence for item in data for occurrence in expand_event(item)]
        write(name, data)
    return data


def write(name, data):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / name
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=DATA_DIR, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def ask(prompt, value=None, required=False):
    while True:
        answer = value if value is not None else input(f"{prompt}: ").strip()
        if answer or not required:
            return answer
        print("Поле не может быть пустым.")


def parse_moment(value, field):
    try:
        moment = datetime.strptime(value, "%d/%m/%Y %H:%M") if "/" in value else datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field}: используйте формат ГГГГ-ММ-ДДTЧЧ:ММ") from error
    return moment.astimezone().isoformat(timespec="seconds") if moment.tzinfo else moment.astimezone().isoformat(timespec="seconds")


def validate_event(event):
    if not isinstance(event, dict) or not isinstance(event.get("title"), str) or not event["title"].strip():
        raise ValueError("Введите название события")
    all_day = event.get("all_day", False)
    if type(all_day) is not bool:
        raise ValueError("all_day должно быть логическим значением")
    start = datetime.strptime(event["start"], "%Y-%m-%d") if all_day else datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
    end = datetime.strptime(event["end"], "%Y-%m-%d") if all_day else datetime.fromisoformat(event["end"].replace("Z", "+00:00"))
    if (not all_day and (start.tzinfo is None or end.tzinfo is None)) or end < start:
        raise ValueError("Некорректное начало или окончание события")
    rule = event.get("recurrence")
    if rule is None:
        return
    if not isinstance(rule, dict) or rule.get("frequency") != "weekly":
        raise ValueError("Поддерживается еженедельное повторение")
    interval = rule.get("interval", 1)
    if type(interval) is not int or not 1 <= interval <= 520:
        raise ValueError("Интервал: от 1 до 520 недель")
    if ("until" in rule) == ("count" in rule):
        raise ValueError("Укажите либо конечную дату, либо количество событий")
    if "count" in rule:
        if type(rule["count"]) is not int or not 1 <= rule["count"] <= 10000:
            raise ValueError("Количество: от 1 до 10000 событий")
    else:
        until = datetime.strptime(rule["until"], "%Y-%m-%d").date()
        if until < (start.date() if all_day else start.astimezone().date()):
            raise ValueError("Последняя дата раньше начала серии")


def expand_event(event):
    """Каждый повтор становится самостоятельной записью без правила повторения."""
    validate_event(event)
    rule = event.get("recurrence")
    if not rule:
        return [{**event, "recurrence": None}]
    all_day = event.get("all_day", False)
    start = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(event["end"].replace("Z", "+00:00"))
    if not all_day:
        start, end = start.astimezone(), end.astimezone()
    result = []
    for index in range(rule.get("count", 10001)):
        offset = timedelta(weeks=rule.get("interval", 1)*index)
        current, finish = start+offset, end+offset
        if rule.get("until") and current.date().isoformat() > rule["until"]:
            break
        if index >= 10000:
            raise ValueError("В одной серии допускается не более 10000 событий")
        result.append({**event, "id": event.get("id", str(uuid.uuid4())) if index == 0 else str(uuid.uuid4()),
                       "start": current.date().isoformat() if all_day else current.isoformat(),
                       "end": finish.date().isoformat() if all_day else finish.isoformat(), "recurrence": None})
    return result


def add_event(args):
    interactive = args.title is None or args.start is None
    title = ask("Название", args.title, True)
    if interactive and not args.all_day:
        args.all_day = input("На весь день? (да/нет): ").strip().lower() == "да"
    def read_date(value):
        return (datetime.strptime(value, "%d/%m/%Y") if "/" in value else datetime.strptime(value, "%Y-%m-%d")).date().isoformat()
    start_text = ask("Начало (дд/мм/гггг" + (")" if args.all_day else " чч:мм)"), args.start, True)
    start = read_date(start_text) if args.all_day else parse_moment(start_text, "Начало")
    end_text = ask("Окончание (Enter — как начало)", args.end)
    end = (read_date(end_text) if args.all_day else parse_moment(end_text, "Окончание")) if end_text else start
    if datetime.fromisoformat(end) < datetime.fromisoformat(start):
        raise ValueError("Окончание не может быть раньше начала")
    events = read("events.json")
    event = {"id": str(uuid.uuid4()), "title": title, "start": start, "end": end,
             "notes": ask("Заметка (необязательно)", args.notes), "created_at": now(), "all_day": args.all_day}
    if interactive and not args.repeat:
        args.repeat = "weekly" if input("Повторять еженедельно? (да/нет): ").strip().lower() == "да" else None
        if args.repeat:
            args.interval = int(input("Каждые … недель (Enter — 1): ").strip() or "1")
            if input("Окончание: 1 — по дате, 2 — по количеству: ").strip() == "2":
                args.count = int(input("Всего событий, включая первое: ").strip())
            else:
                args.until = input("Последняя дата (дд/мм/гггг): ").strip()
    event["recurrence"] = None
    if args.repeat:
        rule = {"frequency": "weekly", "interval": args.interval}
        if args.count is not None:
            rule["count"] = args.count
        elif args.until:
            rule["until"] = datetime.strptime(args.until, "%d/%m/%Y").strftime("%Y-%m-%d") if "/" in args.until else args.until
        event["recurrence"] = rule
    elif args.until or args.count is not None:
        raise ValueError("Для правила окончания укажите --repeat weekly")
    validate_event(event)
    events.extend(expand_event(event))
    write("events.json", events)
    print(f"Добавлено событие: {title} · {start}")


def add_task(args):
    title = ask("Задача", args.title, True)
    due_text = ask("Срок (ГГГГ-ММ-ДДTЧЧ:ММ, Enter — без срока)", args.due)
    tasks = read("tasks.json")
    task = {"id": str(uuid.uuid4()), "title": title,
            "due_at": parse_moment(due_text, "Срок") if due_text else None,
            "status": "todo", "notes": ask("Заметка (необязательно)", args.notes),
            "created_at": now(), "completed_at": None}
    tasks.append(task)
    write("tasks.json", tasks)
    print(f"Добавлена задача: {title}")


def list_items(args):
    items = read("events.json" if args.kind == "events" else "tasks.json")
    if not items:
        print("Список пуст.")
    for item in items:
        if args.kind == "events":
            stamp = datetime.fromisoformat(item['start']).strftime("%d/%m/%Y") + " · Весь день" if item.get("all_day") else datetime.fromisoformat(item['start'].replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M")
            print(f"{item['id']}  {stamp}  {item['title']}")
            if item.get("recurrence"):
                rule = item["recurrence"]
                limit = f"всего {rule['count']} событий" if "count" in rule else "до " + datetime.strptime(rule["until"], "%Y-%m-%d").strftime("%d/%m/%Y")
                print(f"  Каждые {rule.get('interval', 1)} недель, {limit}")
        else:
            due = datetime.fromisoformat(item["due_at"].replace("Z", "+00:00")).astimezone().strftime("%d/%m/%Y %H:%M") if item.get("due_at") else "без срока"
            mark = "✓" if item.get("status") == "done" else "·"
            print(f"{item['id']}  {mark} {item['title']}  ({due})")


def task_status(args):
    tasks = read("tasks.json")
    task = next((item for item in tasks if item.get("id") == args.id), None)
    if task is None:
        raise ValueError("Задача с таким ID не найдена")
    task["status"] = args.status
    task["completed_at"] = now() if args.status == "done" else None
    write("tasks.json", tasks)
    print(f"Задача «{task['title']}»: {'выполнена' if args.status == 'done' else 'возвращена в работу'}")


def delete_item(args):
    name = "events.json" if args.kind == "event" else "tasks.json"
    items = read(name)
    updated = [item for item in items if item.get("id") != args.id]
    if len(updated) == len(items):
        raise ValueError("Запись с таким ID не найдена")
    write(name, updated)
    print("Удалено.")


def parser():
    root = argparse.ArgumentParser(description="Локальное расписание и задачи")
    commands = root.add_subparsers(dest="command")
    event = commands.add_parser("add-event", help="добавить событие")
    event.add_argument("--title"); event.add_argument("--start"); event.add_argument("--end"); event.add_argument("--notes")
    event.add_argument("--repeat", choices=("weekly",))
    event.add_argument("--all-day", action="store_true", help="событие на весь день; даты без времени")
    event.add_argument("--interval", type=int, default=1, help="интервал в неделях")
    ending = event.add_mutually_exclusive_group()
    ending.add_argument("--until", help="последняя дата включительно, дд/мм/гггг")
    ending.add_argument("--count", type=int, help="всего событий, включая первое")
    event.set_defaults(handler=add_event)
    task = commands.add_parser("add-task", help="добавить задачу")
    task.add_argument("--title"); task.add_argument("--due"); task.add_argument("--notes")
    task.set_defaults(handler=add_task)
    listing = commands.add_parser("list", help="показать записи")
    listing.add_argument("kind", choices=("events", "tasks")); listing.set_defaults(handler=list_items)
    status = commands.add_parser("task-status", help="изменить статус задачи")
    status.add_argument("id"); status.add_argument("status", choices=("todo", "done")); status.set_defaults(handler=task_status)
    delete = commands.add_parser("delete", help="удалить событие или задачу")
    delete.add_argument("kind", choices=("event", "task")); delete.add_argument("id"); delete.set_defaults(handler=delete_item)
    return root


def main(argv=None):
    root = parser(); args = root.parse_args(argv)
    if not args.command:
        choice = input("Что добавить? 1 — событие, 2 — задачу: ").strip()
        args = root.parse_args(["add-event" if choice == "1" else "add-task"])
    try:
        args.handler(args)
    except (ValueError, OSError, EOFError) as error:
        print(f"Ошибка: {error}", file=sys.stderr); return 1
    except KeyboardInterrupt:
        print("\nОперация отменена.", file=sys.stderr); return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
