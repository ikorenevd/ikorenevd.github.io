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

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "src" / "data"
COLLECTIONS = {"movies": "movies.json", "series": "series.json", "books": "books.json",
               "events": "events.json", "tasks": "tasks.json"}


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
    return data


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

    def change(self, method):
        parts = self.api()
        try:
            if not parts or parts[0] not in COLLECTIONS: return self.send_json({"error": "Не найдено"}, 404)
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
