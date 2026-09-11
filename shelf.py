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


def validate_record(record, allowed_types):
    if not isinstance(record, dict):
        raise CatalogError("Запись должна быть JSON-объектом.")
    for key in ("type", "title_ru", "title_original", "status", "added_at"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise CatalogError(f"Поле {key} должно быть непустой строкой.")
    if record["type"] not in allowed_types:
        raise CatalogError("Неверный тип произведения для этого каталога.")
    if type(record.get("year")) is not int or not 1 <= record["year"] <= 9999:
        raise CatalogError("Год должен быть целым числом от 1 до 9999.")
    if record["status"] not in STATUSES[record["type"]]:
        raise CatalogError(f"Недопустимый статус для {record['type']}: {record['status']}.")
    try:
        added_at = datetime.fromisoformat(record["added_at"].replace("Z", "+00:00"))
        if added_at.tzinfo is None:
            raise ValueError("missing timezone")
    except ValueError as error:
        raise CatalogError("added_at должна быть датой ISO 8601 с часовым поясом.") from error


def record_key(record):
    return record["type"], record["title_original"].strip().casefold(), record["year"]


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
        for record in records:
            try:
                validate_record(record, allowed_types)
            except CatalogError as error:
                raise CatalogError(f"{path}: {error}") from error
            key = record_key(record)
            if key in seen:
                raise CatalogError(f"Повторяющееся произведение: {record['title_original']} ({record['year']}, {record['type']}).")
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


def add_record(args):
    record = {
        "type": args.type,
        "title_ru": args.title_ru.strip(),
        "title_original": args.title_original.strip(),
        "year": args.year,
        "status": args.status,
        "added_at": datetime.now().astimezone().isoformat(timespec="microseconds"),
    }
    validate_record(record, tuple(STATUSES))
    filename = TYPE_FILES[args.type]
    with catalog_lock(args.data_dir):
        catalogs = load_catalogs(args.data_dir)
        for existing in catalogs[filename]:
            if record_key(existing) == record_key(record):
                raise CatalogError(f"Произведение уже в коллекции: {existing['title_original']} ({existing['year']}).")
        catalogs[filename].append(record)
        write_catalog(args.data_dir / filename, catalogs[filename])
        # Новый пользовательский каталог сразу пригоден для сайта.
        for other in FILES:
            if not (args.data_dir / other).exists():
                write_catalog(args.data_dir / other, catalogs[other])
    print(f"Добавлено: {record['title_ru']} ({record['year']})")


def set_status(args):
    filename = TYPE_FILES[args.type]
    target = args.type, args.title_original.strip().casefold(), args.year
    with catalog_lock(args.data_dir):
        catalogs = load_catalogs(args.data_dir)
        records = catalogs[filename]
        for record in records:
            if record_key(record) == target:
                updated = {**record, "status": args.status}
                validate_record(updated, FILES[filename])
                record.update(updated)
                write_catalog(args.data_dir / filename, records)
                print(f"{record['title_ru']}: {STATUS_LABELS[record['status']]}")
                return
        raise CatalogError(f"{args.title_original} ({args.year}, {args.type}) не найдено. Проверьте название и год командой list.")


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
            print(f"  {record['title_ru']} / {record['title_original']} ({record['year']}) · {record['added_at']}")


def build_parser():
    parser = argparse.ArgumentParser(description="Полка — управление фильмами, сериалами и книгами.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="папка JSON-каталогов (по умолчанию src/data рядом со скриптом)")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="добавить произведение")
    add.add_argument("type", choices=STATUSES, help="movie — фильм, series — сериал, book — книга")
    add.add_argument("--title-ru", required=True, help="название на русском")
    add.add_argument("--title-original", required=True, help="название на языке оригинала")
    add.add_argument("--year", required=True, type=int, help="год выпуска; для сериала — год премьеры, для книги — первой публикации")
    add.add_argument("--status", choices=STATUS_LABELS, default="waiting", help="waiting — в ожидании (по умолчанию), watched — просмотрено, read — прочитано")
    add.set_defaults(handler=add_record)
    status = commands.add_parser("set-status", help="изменить статус по типу, оригинальному названию и году")
    status.add_argument("type", choices=STATUSES, help="movie — фильм, series — сериал, book — книга")
    status.add_argument("status", choices=STATUS_LABELS)
    status.add_argument("--title-original", required=True, help="название на языке оригинала")
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
    try:
        args.handler(args)
    except (CatalogError, OSError) as error:
        print(f"Ошибка: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
