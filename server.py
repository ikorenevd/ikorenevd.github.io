#!/usr/bin/env python3
"""Локальный сервер сайта и JSON API. Python 3.9+, без зависимостей."""

from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import uuid
from urllib.parse import urlparse
import argparse
import threading
from planner import validate_event, expand_event
from french_verbs import (conjugation_label, conjugation_rows, conjugation_target,
                          format_conjugations, group_conjugations, normalized)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "data"
COLLECTIONS = {"movies": "movies.json", "series": "series.json", "books": "books.json",
               "events": "events.json", "tasks": "tasks.json", "french": "french.json"}
FRENCH_LOCK = threading.Lock()


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load(name):
    path = DATA / COLLECTIONS[name]
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if not isinstance(data, list):
        raise ValueError("Файл должен содержать массив")
    if name == "events" and any(item.get("recurrence") for item in data):
        data = [occurrence for item in data for occurrence in expand_event(item)]
        save(name, data)
    return group_conjugations(data) if name == "french" else data


def save(name, data):
    path = DATA / COLLECTIONS[name]
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=DATA, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, ensure_ascii=False, indent=2); stream.write("\n")
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists(): temporary.unlink()


def validate_french_card(item, card_id):
    if not isinstance(item, dict) or item.get("kind") not in ("word", "conjugation", "number"):
        raise ValueError("Укажите тип карточки")
    card = {"id": card_id, "kind": item["kind"]}
    for key, limit, label in (("front", 200, "Вопрос"), ("back", 4000, "Ответ"),
                              ("translation", 400, "Перевод"),
                              ("example", 400, "Пример")):
        value = item.get(key, "")
        if not isinstance(value, str) or len(value.strip()) > limit:
            raise ValueError(f"{label}: допустимо до {limit} символов")
        value = value.strip()
        if not value and (key == "front" or key == "back" and card["kind"] != "conjugation"):
            raise ValueError(f"{label}: заполните поле")
        if value:
            card[key] = value
    if card["kind"] in ("word", "conjugation"):
        model = item.get("verb_model", "")
        if model not in ("", "er", "ir", "none"):
            raise ValueError("Выберите модель спряжения.")
        if model and card["kind"] == "word":
            card["verb_model"] = model
        target = conjugation_target({**card, "verb_model": model})
        if card["kind"] == "conjugation" and not card.get("back"):
            if not target:
                raise ValueError("Введите спряжение вручную или выберите модель глагола.")
            card["back"] = format_conjugations(conjugation_rows(target))
        elif card["kind"] == "word" and target and normalized(card["front"]) == conjugation_label(target):
            card["kind"] = "conjugation"
            card["translation"] = card["back"]
            card["back"] = format_conjugations(conjugation_rows(target))
            card.pop("verb_model", None)
    return card


class Handler(SimpleHTTPRequestHandler):
    def send_json(self, value, status=200):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def body(self):
        size = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(size))

    def api(self):
        parts = [part for part in urlparse(self.path).path.split("/") if part]
        return parts[1:] if parts and parts[0] == "api" else None

    def do_GET(self):
        parts = self.api()
        if parts is None: return super().do_GET()
        try:
            if len(parts) == 1 and parts[0] in COLLECTIONS: return self.send_json(load(parts[0]))
            self.send_json({"error": "Не найдено"}, 404)
        except Exception as error: self.send_json({"error": str(error)}, 400)

    def do_POST(self):
        if self.api() == ["shutdown"]:
            # Команда доступна локальной программе, но не сторонним веб-страницам.
            if self.headers.get("Origin") or self.headers.get("X-Organizer-Control") != "stop":
                return self.send_json({"error": "Команда остановки недоступна"}, 403)
            self.send_json({"message": "Сервер останавливается", "application": "local-organizer"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self.change("post")
    def do_PUT(self): self.change("put")
    def do_DELETE(self): self.change("delete")

    def change_french(self, method, parts):
        if len(parts) != (1 if method == "post" else 2):
            return self.send_json({"error": "Не найдено"}, 404)

        item = self.body() if method != "delete" else None
        with FRENCH_LOCK:
            cards = load("french")
            previous = None
            if method != "post":
                previous = next((card for card in cards if card["id"] == parts[1]), None)
                if previous is None:
                    return self.send_json({"error": "Карточка не найдена"}, 404)
            if method == "delete":
                result = previous
                cards = [card for card in cards if card["id"] != previous["id"]]
            else:
                result = validate_french_card(item, previous["id"] if previous else str(uuid.uuid4()))
                if previous and previous.get("previous_ids"):
                    result["previous_ids"] = previous["previous_ids"]
                added = []
                if result["kind"] == "conjugation":
                    existing = next((card for card in cards if card["kind"] == "conjugation"
                                     and normalized(card["front"]) == normalized(result["front"])), None)
                    if existing and existing is not previous:
                        if method == "put" or item["kind"] == "conjugation":
                            raise ValueError("Карточка для этого глагола уже есть.")
                        result = {**existing, **{key: result[key] for key in ("translation", "example")
                                                 if key in result}}
                elif result["kind"] == "word":
                    target = conjugation_target(result)
                    if target and (not previous or target != conjugation_target(previous)):
                        label = conjugation_label(target)
                        if not any(card["kind"] == "conjugation" and normalized(card["front"]) == label
                                   for card in cards):
                            added.append({"id": str(uuid.uuid4()), "kind": "conjugation", "front": label,
                                          "back": format_conjugations(conjugation_rows(target))})
                cards = [result if card["id"] == result["id"] else card for card in cards]
                if not any(card["id"] == result["id"] for card in cards):
                    cards.append(result)
                cards.extend(added)
            save("french", cards)
        return self.send_json(cards, 201 if method == "post" else 200)

    def change(self, method):
        parts = self.api()
        try:
            if not parts or parts[0] not in COLLECTIONS: return self.send_json({"error": "Не найдено"}, 404)
            if parts[0] == "french": return self.change_french(method, parts)
            name, items = parts[0], load(parts[0])
            if method == "post":
                item = self.body()
                if name == "events": validate_event(item)
                if name in ("events", "tasks"):
                    item.setdefault("id", str(uuid.uuid4())); item.setdefault("created_at", now())
                items.extend(expand_event(item) if name == "events" else [item])
                save(name, items); return self.send_json(item, 201)
            key = parts[1] if len(parts) > 1 else ""
            if name in ("events", "tasks"):
                index = next((i for i, item in enumerate(items) if item.get("id") == key), -1)
            else:
                index = int(key) if key.isdigit() else -1
            if not 0 <= index < len(items): return self.send_json({"error": "Запись не найдена"}, 404)
            if method == "delete":
                removed = items.pop(index); save(name, items); return self.send_json(removed)
            item = self.body()
            if name == "events" and item.get("recurrence"):
                raise ValueError("Редактируется одно событие. Повторение задаётся при создании.")
            if name == "events": validate_event(item)
            if name == "tasks":
                previous = items[index]
                if item.get("status") == "done" and previous.get("status") != "done": item["completed_at"] = now()
                if item.get("status") != "done": item["completed_at"] = None
            if name in ("movies", "series", "books"):
                previous = items[index]
                if item.get("status") in ("watched", "read") and previous.get("status") == "waiting": item["completed_at"] = now()
                if item.get("status") == "waiting": item["completed_at"] = None
                item["added_at"] = previous["added_at"]
            items[index] = item; save(name, items); return self.send_json(item)
        except (ValueError, json.JSONDecodeError, KeyError) as error: self.send_json({"error": str(error)}, 400)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Локальный сервер личного органайзера")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Хранилище: http://127.0.0.1:{args.port}")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nСервер остановлен.")
    finally:
        server.server_close()
