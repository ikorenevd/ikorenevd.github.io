# Полка

Личная коллекция фильмов, сериалов и книг. Статический сайт на HTML/CSS/JavaScript и Python CLI без внешних зависимостей. Добавление и изменение статусов происходит через CLI; сайт читает JSON-каталоги.

## Добавление

```sh
# Фильм. Статус по умолчанию — в ожидании.
python3 shelf.py add movie --title-ru "Начало" --title-original "Inception" --year 2010

# Сериал. Год — год премьеры сериала.
python3 shelf.py add series --title-ru "Твин Пикс" --title-original "Twin Peaks" --year 1990 --status watched

# Книга. Год — год первой публикации.
python3 shelf.py add book --title-ru "Дюна" --title-original "Dune" --year 1965 --status read
```

Русское и оригинальное названия обязательны. Для русскоязычного произведения они могут совпадать. Дата добавления назначается автоматически. Записи не содержат отдельного ID: для выбора произведения используются тип, оригинальное название и год. Повторное добавление этого сочетания отклоняется.

## Статусы и просмотр списка

| Значение в CLI/JSON | На сайте | Типы |
| --- | --- | --- |
| `waiting` | В ожидании | Все |
| `watched` | Просмотрено | Фильмы и сериалы |
| `read` | Прочитано | Книги |

```sh
python3 shelf.py list
python3 shelf.py list --type book --status waiting
python3 shelf.py list --json

# Укажите тип, оригинальное название и год нужного произведения.
python3 shelf.py set-status movie watched --title-original "Inception" --year 2010
python3 shelf.py set-status book read --title-original "Dune" --year 1965
python3 shelf.py set-status series waiting --title-original "Twin Peaks" --year 1990

python3 shelf.py --help
python3 shelf.py add --help
```
