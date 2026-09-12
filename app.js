"use strict";

const typeLabels = { movie: "Фильм", series: "Сериал", book: "Книга" };
const headings = { all: "Моя коллекция", movie: "Фильмы", series: "Сериалы", book: "Книги" };
const statusLabels = { waiting: "В ожидании", watched: "Просмотрено", read: "Прочитано" };
const state = { records: [], type: "all", status: "all", query: "" };
const byId = (id) => document.getElementById(id);
const dateFormat = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
const displayTitle = (record) => record.title_ru.trim() || record.title_original.trim();
const bookAuthors = (record) => [...new Set([record.author_ru, record.author_original].map((name) => name.trim()).filter(Boolean))];

function validateCatalog(records, types) {
  if (!Array.isArray(records)) throw new Error("Каталог должен быть массивом");
  for (const record of records) {
    if (!record || !types.includes(record.type)
      || ![record.title_ru, record.title_original].every((value) => typeof value === "string")
      || !(record.title_ru.trim() || record.title_original.trim())
      || (record.type === "book" && [record.author_ru, record.author_original, record.author]
        .some((value) => value !== undefined && typeof value !== "string"))
      || !Number.isInteger(record.year) || record.year < 1 || record.year > 9999
      || !["waiting", record.type === "book" ? "read" : "watched"].includes(record.status)
      || typeof record.added_at !== "string" || !Number.isFinite(Date.parse(record.added_at))
      || (record.completed_at !== undefined && record.completed_at !== null
        && (typeof record.completed_at !== "string" || !Number.isFinite(Date.parse(record.completed_at))))
      || (record.status !== "waiting" && record.completed_at === null)) {
      throw new Error("Некорректная запись каталога");
    }
  }
  return records.map((record) => ({
    ...record,
    ...(record.type === "book" ? {
      author_ru: record.author_ru ?? record.author ?? "",
      author_original: record.author_original ?? "",
    } : {}),
    completed_at: record.status === "waiting" ? null : record.completed_at ?? record.added_at,
  }));
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
}

function dateCell(value, label) {
  const cell = element("td", "entry-date", "");
  const caption = element("span", "date-label", `${label}:`);
  caption.setAttribute("aria-hidden", "true");
  cell.append(caption);
  if (value) {
    const time = element("time", "", dateFormat.format(new Date(value)));
    time.dateTime = value;
    cell.append(time);
  } else {
    cell.append(element("span", "", "—"));
  }
  return cell;
}

function render() {
  const records = state.records;
  for (const type of Object.keys(headings)) {
    byId(`count-${type}`).textContent = type === "all" ? records.length : records.filter((r) => r.type === type).length;
  }
  const selectedRecords = records.filter((record) => state.type === "all" || record.type === state.type);
  byId("stat-total").textContent = selectedRecords.length;
  byId("stat-finished").textContent = selectedRecords.filter((r) => r.status !== "waiting").length;
  byId("stat-waiting").textContent = selectedRecords.filter((r) => r.status === "waiting").length;
  byId("stat-finished-label").textContent = state.type === "all"
    ? "просмотрено и прочитано"
    : state.type === "book" ? "прочитано" : "просмотрено";
  byId("page-title").textContent = headings[state.type];
  byId("completed-heading").textContent = state.type === "all" ? "Дата завершения"
    : state.type === "book" ? "Дата прочтения" : "Дата просмотра";
  const searchAuthors = state.type === "all" || state.type === "book";
  byId("search").placeholder = searchAuthors ? "Название или автор" : "Поиск по названию";
  byId("search").setAttribute("aria-label", searchAuthors
    ? "Поиск по русскому или оригинальному названию и имени автора книги"
    : "Поиск по русскому или оригинальному названию");
  document.querySelectorAll("[data-type]").forEach((button) => {
    const active = button.dataset.type === state.type;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  document.querySelectorAll("[data-status]").forEach((button) => {
    const active = button.dataset.status === state.status;
    button.classList.toggle("selected", active);
    button.setAttribute("aria-pressed", String(active));
    button.hidden = (state.type === "book" && button.dataset.status === "watched")
      || (["movie", "series"].includes(state.type) && button.dataset.status === "read");
  });
  const query = state.query.trim().toLocaleLowerCase("ru");
  const visible = selectedRecords.filter((record) => (state.status === "all" || record.status === state.status)
    && `${record.title_ru} ${record.title_original} ${record.type === "book" ? bookAuthors(record).join(" ") : ""}`.toLocaleLowerCase("ru").includes(query))
    .sort((a, b) => Date.parse(b.added_at) - Date.parse(a.added_at) || displayTitle(a).localeCompare(displayTitle(b), "ru"));
  byId("result-count").textContent = `Записей: ${visible.length}`;
  byId("entries").replaceChildren(...visible.map((record) => {
    const row = document.createElement("tr");
    const title = document.createElement("td");
    title.append(element("span", "entry-title", displayTitle(record)));
    if (record.title_ru.trim() && record.title_original.trim() && record.title_ru.trim() !== record.title_original.trim()) {
      title.append(element("span", "entry-original", record.title_original));
    }
    if (record.type === "book") {
      const authors = bookAuthors(record);
      if (authors.length) title.append(element("span", "entry-author", `Автор: ${authors.join(" / ")}`));
    }
    title.append(element("span", "entry-kind", typeLabels[record.type]));
    const status = document.createElement("td");
    status.append(element("span", `badge ${record.status}`, statusLabels[record.status]));
    row.append(title, element("td", "", record.year), status,
      dateCell(record.added_at, "Дата добавления"),
      dateCell(record.status === "waiting" ? null : record.completed_at, record.type === "book" ? "Дата прочтения" : "Дата просмотра"));
    return row;
  }));
  byId("table-wrap").hidden = visible.length === 0;
  byId("empty-state").hidden = visible.length !== 0;
  const empty = records.length === 0;
  byId("empty-title").textContent = empty ? "Коллекция пока пуста" : "Ничего не найдено";
  byId("empty-description").textContent = empty
    ? "Добавьте фильм, сериал или книгу через CLI."
    : `По выбранным условиям ничего не нашлось. Попробуйте ${searchAuthors ? "другое название или автора" : "другое название"} или сбросьте фильтры.`;
  byId("empty-command").hidden = !empty;
  byId("reset-filters").hidden = empty;
}

async function load() {
  byId("error-state").hidden = true;
  byId("empty-state").hidden = true;
  byId("table-wrap").hidden = true;
  byId("result-count").textContent = "Загружаем коллекцию…";
  try {
    const catalogTypes = { movies: "movie", series: "series", books: "book" };
    const catalogs = await Promise.all(Object.entries(catalogTypes).map(async ([name, type]) => {
      const response = await fetch(`src/data/${name}.json`, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return validateCatalog(await response.json(), [type]);
    }));
    state.records = catalogs.flat();
    render();
  } catch (error) {
    byId("result-count").textContent = "Коллекция недоступна";
    byId("error-state").hidden = false;
    console.error("Не удалось загрузить каталоги:", error);
  }
}

byId("type-filters").addEventListener("click", (event) => {
  const button = event.target.closest("[data-type]");
  if (!button) return;
  state.type = button.dataset.type;
  if ((state.type === "book" && state.status === "watched") || (["movie", "series"].includes(state.type) && state.status === "read")) state.status = "all";
  if (byId("error-state").hidden) render();
});
byId("status-filters").addEventListener("click", (event) => {
  const button = event.target.closest("[data-status]");
  if (!button) return;
  state.status = button.dataset.status;
  if (byId("error-state").hidden) render();
});
byId("search").addEventListener("input", (event) => {
  state.query = event.target.value;
  if (byId("error-state").hidden) render();
});
byId("reset-filters").addEventListener("click", () => {
  Object.assign(state, { type: "all", status: "all", query: "" });
  byId("search").value = "";
  render();
});
byId("retry").addEventListener("click", load);
load();
