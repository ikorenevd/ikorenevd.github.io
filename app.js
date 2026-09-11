"use strict";

const typeLabels = { movie: "Фильм", series: "Сериал", book: "Книга" };
const headings = { all: "Моя коллекция", movie: "Фильмы", series: "Сериалы", book: "Книги" };
const statusLabels = { waiting: "В ожидании", watched: "Просмотрено", read: "Прочитано" };
const state = { records: [], type: "all", status: "all", query: "" };
const byId = (id) => document.getElementById(id);
const dateFormat = new Intl.DateTimeFormat("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });

function validateCatalog(records, types) {
  if (!Array.isArray(records)) throw new Error("Каталог должен быть массивом");
  for (const record of records) {
    if (!record || !types.includes(record.type)
      || ![record.title_ru, record.title_original].every((value) => typeof value === "string" && value.trim())
      || !Number.isInteger(record.year) || record.year < 1 || record.year > 9999
      || !["waiting", record.type === "book" ? "read" : "watched"].includes(record.status)
      || typeof record.added_at !== "string" || !Number.isFinite(Date.parse(record.added_at))) {
      throw new Error("Некорректная запись каталога");
    }
  }
  return records;
}

function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  node.textContent = text;
  return node;
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
    && `${record.title_ru} ${record.title_original}`.toLocaleLowerCase("ru").includes(query))
    .sort((a, b) => Date.parse(b.added_at) - Date.parse(a.added_at) || a.title_ru.localeCompare(b.title_ru, "ru"));
  byId("result-count").textContent = `Записей: ${visible.length}`;
  byId("entries").replaceChildren(...visible.map((record) => {
    const row = document.createElement("tr");
    const title = document.createElement("td");
    title.append(element("span", "entry-title", record.title_ru), element("span", "entry-original", record.title_original), element("span", "entry-kind", typeLabels[record.type]));
    const status = document.createElement("td");
    status.append(element("span", `badge ${record.status}`, statusLabels[record.status]));
    const date = document.createElement("td");
    const time = element("time", "", dateFormat.format(new Date(record.added_at)));
    time.dateTime = record.added_at;
    date.append(time);
    row.append(title, element("td", "", record.year), status, date);
    return row;
  }));
  byId("table-wrap").hidden = visible.length === 0;
  byId("empty-state").hidden = visible.length !== 0;
  const empty = records.length === 0;
  byId("empty-title").textContent = empty ? "Коллекция пока пуста" : "Ничего не найдено";
  byId("empty-description").textContent = empty
    ? "Добавьте фильм, сериал или книгу через CLI."
    : "По выбранным условиям ничего не нашлось. Попробуйте другое название или сбросьте фильтры.";
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
