#!/usr/bin/env python3
"""Остановка локального сервера органайзера без завершения других процессов."""

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener


def main(argv=None):
    parser = argparse.ArgumentParser(description="Остановить локальный сервер органайзера")
    parser.add_argument("--port", type=int, default=8000, help="порт сервера (по умолчанию 8000)")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("порт должен быть от 1 до 65535")
    request = Request(
        f"http://127.0.0.1:{args.port}/api/shutdown",
        data=b"", method="POST", headers={"X-Organizer-Control": "stop"},
    )
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
            result = json.load(response)
        if result.get("application") != "local-organizer":
            raise ValueError("Неожиданный ответ сервера")
    except HTTPError:
        print("Сервер не поддерживает остановку. Если он был запущен до обновления, "
              "остановите его через Ctrl+C и запустите server.py заново.", file=sys.stderr)
        return 1
    except (URLError, OSError):
        print(f"Сервер на порту {args.port} недоступен или уже остановлен.", file=sys.stderr)
        return 1
    except (ValueError, AttributeError):
        print("На этом порту ответило другое приложение.", file=sys.stderr)
        return 1
    print(f"Команда остановки отправлена серверу на порту {args.port}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
