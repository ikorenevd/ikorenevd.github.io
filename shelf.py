#!/usr/bin/env python3
"""Управление JSON-каталогами Полки. Python 3.9+, без зависимостей."""

import argparse
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile


DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "src" / "data"
FILES = {"movies.json": ("movie",), "series.json": ("series",), "books.json": ("book",)}
TYPE_FILES = {kind: filename for filename, kinds in FILES.items() for kind in kinds}
STATUSES = {"movie": ("waiting", "watched"), "series": ("waiting", "watched"), "book": ("waiting", "read")}
STATUS_LABELS = {"waiting": "В ожидании", "watched": "Просмотрено", "read": "Прочитано"}
TYPE_LABELS = {"movie": "Фильм", "series": "Сериал", "book": "Книга"}


class CatalogError(ValueError):
    """Понятная пользователю ошибка каталога."""


def current_timestamp():
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def validate_timestamp(value, field):
    try:
        if not isinstance(value, str):
            raise ValueError("not a string")
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("missing timezone")
    except ValueError as error:
        raise CatalogError(f"{field} должна быть датой ISO 8601 с часовым поясом.") from error


def normalize_record(record):
    """Дополняет старый формат, сохраняя уже заданные значения и даты."""
    if not isinstance(record, dict):
        return record
    record = record.copy()
    record.setdefault("completed_at", record.get("added_at") if record.get("status") in ("watched", "read") else None)
    if record.get("type") == "book":
        previous_author = record.pop("author", "")
        record.setdefault("author_ru", previous_author)
        record.setdefault("author_original", "")
    return record


def validate_record(record, allowed_types):
    if not isinstance(record, dict):
        raise CatalogError("Запись должна быть JSON-объектом.")
    for key in ("type", "status", "added_at"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise CatalogError(f"Поле {key} должно быть непустой строкой.")
    for key in ("title_ru", "title_original"):
        if not isinstance(record.get(key), str):
            raise CatalogError(f"Поле {key} должно быть строкой.")
    if not (record["title_ru"].strip() or record["title_original"].strip()):
        raise CatalogError("Укажите хотя бы одно название: русское или оригинальное.")
    if record["type"] not in allowed_types:
        raise CatalogError("Неверный тип произведения для этого каталога.")
    if record["type"] == "book":
        for key in ("author_ru", "author_original"):
            if not isinstance(record.get(key), str):
                raise CatalogError(f"Поле {key} должно быть строкой.")
    if type(record.get("year")) is not int or not 1 <= record["year"] <= 9999:
        raise CatalogError("Год должен быть целым числом от 1 до 9999.")
    if record["status"] not in STATUSES[record["type"]]:
        raise CatalogError(f"Недопустимый статус для {record['type']}: {record['status']}.")
    validate_timestamp(record["added_at"], "added_at")
    if "completed_at" not in record:
        raise CatalogError("В записи должно быть поле completed_at.")
    if record["status"] == "waiting":
        if record["completed_at"] is not None:
            raise CatalogError("Для статуса waiting поле completed_at должно быть null.")
    else:
        validate_timestamp(record["completed_at"], "completed_at")


def display_title(record):
    return record["title_ru"].strip() or record["title_original"].strip()


def record_key(record):
    title = record["title_original"].strip() or record["title_ru"].strip()
    return record["type"], title.casefold(), record["year"]


def load_catalogs(data_dir):
    catalogs = {}
    seen = set()
    for filename, allowed_types in FILES.items():
        path = data_dir / filename
        try:
            records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        except (json.JSONDecodeError, UnicodeError) as error:
            raise CatalogError(f"Не удалось прочитать {path}: некорректный JSON или UTF-8.") from error
        if not isinstance(records, list):
            raise CatalogError(f"{path}: каталог должен быть массивом.")
        records = [normalize_record(record) for record in records]
        for record in records:
            try:
                validate_record(record, allowed_types)
            except CatalogError as error:
                raise CatalogError(f"{path}: {error}") from error
            key = record_key(record)
            if key in seen:
                raise CatalogError(f"Повторяющееся произведение: {display_title(record)} ({record['year']}, {record['type']}).")
            seen.add(key)
        catalogs[filename] = records
    return catalogs


@contextmanager
def catalog_lock(data_dir):
    data_dir.mkdir(parents=True, exist_ok=True)
    lock = data_dir / ".catalog.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise CatalogError(f"Каталог занят другим процессом. Если CLI был аварийно завершён, убедитесь, что он не запущен, и удалите {lock}.") from error
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink()


def write_catalog(path, records):
    """Атомарная замена: читатель видит либо старый, либо новый JSON."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".catalog-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(records, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(path.stat().st_mode & 0o777 if path.exists() else 0o644)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def ask_choice(question, choices, labels, default=None):
    print(question)
    for number, choice in enumerate(choices, 1):
        suffix = " (по умолчанию)" if choice == default else ""
        print(f"  {number}. {labels[choice]}{suffix}")
    while True:
        answer = input("Ваш выбор: ").strip().casefold()
        if not answer and default is not None:
            return default
        for number, choice in enumerate(choices, 1):
            if answer in (str(number), choice, labels[choice].casefold()):
                return choice
        print(f"Введите номер от 1 до {len(choices)}.")


def collect_add_fields(args):
    interactive = (args.type is None or args.year is None
                   or (args.title_ru is None and args.title_original is None))
    if args.type is None:
        args.type = ask_choice("Что хотите добавить?", tuple(TYPE_LABELS), TYPE_LABELS)
    if interactive:
        if args.title_ru is None:
            args.title_ru = input("Название на русском (Enter — пропустить): ").strip()
        if args.title_original is None:
            args.title_original = input("Оригинальное название (Enter — пропустить): ").strip()
        while not (args.title_ru.strip() or args.title_original.strip()):
            print("Нужно заполнить хотя бы одно название.")
            args.title_ru = input("Название на русском (Enter — пропустить): ").strip()
            args.title_original = input("Оригинальное название (Enter — пропустить): ").strip()
    args.title_ru = args.title_ru or ""
    args.title_original = args.title_original or ""
    if args.type == "book":
        if interactive and args.author_ru is None:
            args.author_ru = input("Автор на русском (Enter — пропустить): ").strip()
        if interactive and args.author_original is None:
            args.author_original = input("Автор в оригинале (Enter — пропустить): ").strip()
        args.author_ru = (args.author_ru or "").strip()
        args.author_original = (args.author_original or "").strip()
    elif args.author_ru is not None or args.author_original is not None:
        raise CatalogError("Параметры автора доступны только для книг.")
    while args.year is None:
        label = {"movie": "Год выпуска", "series": "Год премьеры", "book": "Год первой публикации"}[args.type]
        answer = input(f"{label}: ").strip()
        try:
            year = int(answer)
        except ValueError:
            year = 0
        if 1 <= year <= 9999:
            args.year = year
        else:
            print("Введите год — целое число от 1 до 9999.")
    if args.status is None:
        args.status = ask_choice("Статус:", STATUSES[args.type], STATUS_LABELS, default="waiting") if interactive else "waiting"


def add_record(args):
    collect_add_fields(args)
    added_at = current_timestamp()
    record = {
        "type": args.type,
        "title_ru": args.title_ru.strip(),
        "title_original": args.title_original.strip(),
        "year": args.year,
        "status": args.status,
        "added_at": added_at,
        "completed_at": None if args.status == "waiting" else added_at,
    }
    if args.type == "book":
        record["author_ru"] = args.author_ru
        record["author_original"] = args.author_original
    validate_record(record, tuple(STATUSES))
    filename = TYPE_FILES[args.type]
    with catalog_lock(args.data_dir):
        catalogs = load_catalogs(args.data_dir)
        for existing in catalogs[filename]:
            if record_key(existing) == record_key(record):
                raise CatalogError(f"Произведение уже в коллекции: {display_title(existing)} ({existing['year']}).")
        catalogs[filename].append(record)
        write_catalog(args.data_dir / filename, catalogs[filename])
        # Новый пользовательский каталог сразу пригоден для сайта.
        for other in FILES:
            if not (args.data_dir / other).exists():
                write_catalog(args.data_dir / other, catalogs[other])
    print(f"Добавлено: {display_title(record)} ({record['year']})")


def set_status(args):
    filename = TYPE_FILES[args.type]
    if args.title is not None:
        title, fields = args.title, ("title_ru", "title_original")
    elif args.title_ru is not None:
        title, fields = args.title_ru, ("title_ru",)
    else:
        title, fields = args.title_original, ("title_original",)
    target = title.strip().casefold()
    if not target:
        raise CatalogError("Название для поиска не должно быть пустым.")
    with catalog_lock(args.data_dir):
        catalogs = load_catalogs(args.data_dir)
        records = catalogs[filename]
        matches = [record for record in records if record["year"] == args.year
                   and any(record[field].strip().casefold() == target for field in fields)]
        if not matches:
            raise CatalogError(f"{title} ({args.year}, {args.type}) не найдено. Проверьте название и год командой list.")
        if len(matches) > 1:
            raise CatalogError("Найдено несколько произведений. Уточните название через --title-original или --title-ru по данным команды list.")
        record = matches[0]
        updated = {**record, "status": args.status,
                   "completed_at": None if args.status == "waiting" else current_timestamp()}
        validate_record(updated, FILES[filename])
        record.update(updated)
        write_catalog(args.data_dir / filename, records)
        print(f"{display_title(record)}: {STATUS_LABELS[record['status']]}")


def list_records(args):
    catalogs = load_catalogs(args.data_dir)
    records = [record for catalog in catalogs.values() for record in catalog
               if (args.type is None or record["type"] == args.type)
               and (args.status is None or record["status"] == args.status)]
    records.sort(key=lambda record: datetime.fromisoformat(record["added_at"].replace("Z", "+00:00")), reverse=True)
    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
    elif not records:
        print("Коллекция пуста по выбранным условиям.")
    else:
        for record in records:
            print(f"{TYPE_LABELS[record['type']]} · {STATUS_LABELS[record['status']]}")
            titles = " / ".join(dict.fromkeys(title.strip() for title in (record["title_ru"], record["title_original"]) if title.strip()))
            print(f"  {titles} ({record['year']})")
            if record["type"] == "book":
                authors = " / ".join(dict.fromkeys(author.strip() for author in (record["author_ru"], record["author_original"]) if author.strip()))
                if authors:
                    print(f"  Автор: {authors}")
            print(f"  Добавлено: {record['added_at']}")
            completion_label = "Прочитано" if record["type"] == "book" else "Просмотрено"
            print(f"  {completion_label}: {record['completed_at'] or '—'}")


def build_parser():
    parser = argparse.ArgumentParser(description="Управление фильмами, сериалами и книгами. Без команды — добавление с вопросами.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="папка JSON-каталогов (по умолчанию src/data рядом со скриптом)")
    commands = parser.add_subparsers(dest="command")
    add = commands.add_parser("add", help="добавить произведение")
    add.add_argument("type", nargs="?", choices=STATUSES, help="movie — фильм, series — сериал, book — книга")
    add.add_argument("--title-ru", help="название на русском; можно пропустить, если указано оригинальное")
    add.add_argument("--title-original", help="название на языке оригинала; можно пропустить, если указано русское")
    add.add_argument("--author-ru", "--author", dest="author_ru", help="имя автора книги на русском; необязательное поле")
    add.add_argument("--author-original", help="имя автора книги в оригинале; необязательное поле")
    add.add_argument("--year", type=int, help="год выпуска; для сериала — год премьеры, для книги — первой публикации")
    add.add_argument("--status", choices=STATUS_LABELS, help="waiting — в ожидании (по умолчанию), watched — просмотрено, read — прочитано")
    add.set_defaults(handler=add_record)
    status = commands.add_parser("set-status", help="изменить статус по типу, названию и году")
    status.add_argument("type", choices=STATUSES, help="movie — фильм, series — сериал, book — книга")
    status.add_argument("status", choices=STATUS_LABELS)
    titles = status.add_mutually_exclusive_group(required=True)
    titles.add_argument("--title", help="поиск по любому из названий")
    titles.add_argument("--title-original", help="поиск по оригинальному названию")
    titles.add_argument("--title-ru", help="поиск по русскому названию")
    status.add_argument("--year", required=True, type=int, help="год произведения из каталога")
    status.set_defaults(handler=set_status)
    listing = commands.add_parser("list", help="показать коллекцию")
    listing.add_argument("--type", choices=STATUSES)
    listing.add_argument("--status", choices=STATUS_LABELS)
    listing.add_argument("--json", action="store_true", help="вывести JSON вместо текста")
    listing.set_defaults(handler=list_records)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        args = argparse.Namespace(data_dir=args.data_dir, type=None, title_ru=None,
                                  title_original=None, author_ru=None, author_original=None,
                                  year=None, status=None, handler=add_record)
    try:
        args.handler(args)
    except EOFError:
        print("Ввод завершён до заполнения всех полей. Запись не добавлена.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nОперация отменена.", file=sys.stderr)
        return 130
    except (CatalogError, OSError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
