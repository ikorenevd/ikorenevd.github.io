"use strict";

(() => {
  const minute = 60_000;
  const day = 24 * 60 * minute;
  const progressKey = `organizer:french:progress:v1:${new URL("./", location.href).pathname}`;
  const kindNames = {word: "Слово или выражение", conjugation: "Спряжение", number: "Число"};
  const dueDate = new Intl.DateTimeFormat("ru-RU", {dateStyle: "medium", timeStyle: "short"});
  const form = $("french-form");
  const editor = $("french-editor");
  const ratingButtons = [...document.querySelectorAll("[data-french-rating]")];
  let cards = [];
  let progress = {};
  let loaded = false;
  let loading = false;
  let panel = "study";
  let kind = "all";
  let current = null;
  let session = null;
  let completed = null;
  let editing = null;
  let saving = false;
  let timer;

  function readProgress() {
    const saved = JSON.parse(localStorage.getItem(progressKey) || "{}");
    if (!saved || Array.isArray(saved) || typeof saved !== "object") {
      throw Error("Некорректные данные повторений");
    }
    return saved;
  }

  function record(card) {
    const value = progress[card.id];
    if (Number.isFinite(value?.due) && Number.isFinite(value?.interval)) return value;
    return (card.previous_ids || []).map(id => progress[id])
      .filter(item => Number.isFinite(item?.due) && Number.isFinite(item?.interval))
      .sort((a, b) => a.due - b.due)[0] || null;
  }

  function filteredCards() {
    return cards.filter(card => kind === "all" || card.kind === kind);
  }

  function dueCards(deck, now) {
    return deck.filter(card => record(card)?.due <= now)
      .sort((a, b) => record(a).due - record(b).due);
  }

  function nextInterval(previous, rating) {
    const interval = previous?.interval || 0;
    if (rating === "again") return minute;
    if (rating === "hard") return Math.min(365 * day, Math.max(10 * minute, interval * 1.2));
    if (rating === "good") return Math.min(365 * day, Math.max(day, interval * 2));
    return Math.min(365 * day, Math.max(4 * day, interval * 3));
  }

  function formatInterval(interval) {
    if (interval < 60 * minute) return `${Math.round(interval / minute)} мин`;
    if (interval < day) return `${Math.round(interval / (60 * minute))} ч`;
    return `${Math.round(interval / day)} дн.`;
  }

  function renderStudy() {
    clearTimeout(timer);
    const deck = filteredCards();
    const now = Date.now();
    const due = dueCards(deck, now).length;
    const fresh = deck.filter(card => !record(card)).length;
    const next = Math.min(...deck.map(card => record(card)?.due ?? Infinity).filter(date => date > now));

    $("french-new").textContent = fresh;
    $("french-due").textContent = due;
    $("french-total").textContent = deck.length;
    $("french-question").hidden = !current;
    $("french-start-screen").hidden = !!current;
    $("french-start").hidden = !due && !fresh;

    if (!current) {
      const message = [];
      if (completed !== null) message.push(`Ответов за занятие: ${completed}.`);
      if (!deck.length) message.push("В этой категории пока нет карточек.");
      else if (due || fresh) message.push("За занятие можно изучить до 10 новых карточек.");
      else if (next < Infinity) message.push(`Следующее повторение — ${dueDate.format(next)}.`);
      $("french-session-status").textContent = message.join(" ");
    }

    if (next < Infinity) {
      timer = setTimeout(renderStudy, Math.min(next - now, 2_147_483_647));
    }
  }

  function renderDeck() {
    const query = $("french-search").value.trim().toLocaleLowerCase();
    const deck = filteredCards().filter(card =>
      [card.front, card.back, card.translation, card.example].join(" ").toLocaleLowerCase().includes(query)
    );
    $("french-deck-count").textContent = deck.length ? `Карточек: ${deck.length}` : "Карточки не найдены.";
    $("french-list").innerHTML = deck.map(card => `
      <li>
        <div>
          <strong lang="fr">${esc(card.front)}</strong>
          <p${card.kind !== "word" ? ' lang="fr"' : ""}${card.kind === "conjugation" ? ' class="french-forms"' : ""}>${esc(card.back)}</p>
          ${card.translation ? `<small>${esc(card.translation)}</small>` : ""}
          <small>${kindNames[card.kind]}</small>
          ${card.example ? `<small lang="fr">${esc(card.example)}</small>` : ""}
        </div>
        ${canEdit ? `<button type="button" class="text-button" data-french-edit="${esc(card.id)}">Изменить</button>` : ""}
      </li>`).join("");
  }

  function render() {
    const guide = panel === "guide";
    $("french-guide").hidden = !guide;
    $("french-filters").hidden = guide;
    $("french-loading").hidden = guide || loaded;
    $("french-study").hidden = !loaded || panel !== "study";
    $("french-deck").hidden = !loaded || panel !== "deck";
    clearTimeout(timer);
    if (!loaded || guide) return;
    if (panel === "study") renderStudy();
    else renderDeck();
  }

  async function loadCards() {
    if (loading || loaded) return;
    loading = true;
    $("french-load-status").textContent = "Загрузка карточек…";
    $("french-retry").hidden = true;
    try {
      const data = await api("french");
      if (!Array.isArray(data)) throw Error("Некорректный каталог");
      cards = data;
      loaded = true;
      $("french-load-status").textContent = "";
    } catch {
      $("french-load-status").textContent = "Не удалось загрузить карточки.";
      $("french-retry").hidden = false;
    } finally {
      loading = false;
      render();
    }
  }

  function endSession() {
    if (session) completed = session.answers;
    session = null;
    current = null;
    renderStudy();
  }

  function nextCard() {
    const deck = filteredCards();
    current = dueCards(deck, Date.now())[0] ||
      (session.newCards < 10 ? deck.find(card => !record(card)) : null);
    if (!current) {
      endSession();
      if (!$("french-start").hidden) $("french-start").focus();
      return;
    }
    $("french-card-kind").textContent = kindNames[current.kind];
    $("french-front").textContent = current.front;
    $("french-back").textContent = current.back;
    $("french-back").lang = current.kind === "word" ? "ru" : "fr";
    $("french-back").classList.toggle("french-forms", current.kind === "conjugation");
    $("french-translation").textContent = current.translation || "";
    $("french-translation").hidden = !current.translation;
    $("french-example").textContent = current.example || "";
    $("french-example").hidden = !current.example;
    $("french-solution").hidden = true;
    $("french-ratings").hidden = true;
    $("french-reveal").hidden = false;
    $("french-progress-error").hidden = true;
    renderStudy();
    $("french-front").focus();
  }

  function reveal() {
    if (!current) return;
    for (const button of ratingButtons) {
      const interval = nextInterval(record(current), button.dataset.frenchRating);
      button.querySelector("small").textContent = formatInterval(interval);
    }
    $("french-solution").hidden = false;
    $("french-ratings").hidden = false;
    $("french-reveal").hidden = true;
    if (current.kind === "conjugation") $("french-back").focus();
    else ratingButtons[2].focus();
  }

  function rate(rating) {
    if (!current || $("french-ratings").hidden) return;
    try {
      const latest = readProgress();
      const previous = record(current);
      const interval = nextInterval(previous, rating);
      latest[current.id] = {due: Date.now() + interval, interval};
      localStorage.setItem(progressKey, JSON.stringify(latest));
      progress = latest;
      session.answers += 1;
      if (!previous) session.newCards += 1;
      nextCard();
    } catch {
      $("french-progress-error").textContent = "Не удалось сохранить прогресс. Проверьте настройки хранилища браузера.";
      $("french-progress-error").hidden = false;
    }
  }

  function openEditor(card = null) {
    if (!canEdit) return;
    editing = card;
    form.reset();
    form.elements.kind.value = card?.kind || (kind === "all" ? "word" : kind);
    form.elements.front.value = card?.front || "";
    form.elements.back.value = card?.back || "";
    form.elements.translation.value = card?.translation || "";
    form.elements.example.value = card?.example || "";
    form.elements.verb_model.value = card?.verb_model || "";
    form.elements.kind.onchange();
    $("french-editor-title").textContent = card ? "Изменить карточку" : "Новая карточка";
    $("french-delete").hidden = !card;
    $("french-form-error").hidden = true;
    editor.showModal();
  }

  async function changeCard(method) {
    if (!canEdit || saving) return;
    const error = $("french-form-error");
    const data = Object.fromEntries([...new FormData(form)].map(([key, value]) => [key, value.trim()]));
    error.hidden = true;
    if (method !== "DELETE" && (!data.front || (data.kind !== "conjugation" && !data.back))) {
      error.textContent = "Заполните вопрос и ответ.";
      error.hidden = false;
      return;
    }
    if (method === "DELETE" && !window.confirm(`Удалить карточку «${editing.front}»?`)) return;
    saving = true;
    for (const button of form.querySelectorAll("button")) button.disabled = true;
    try {
      cards = await api(editing ? `french/${encodeURIComponent(editing.id)}` : "french", {
        method,
        headers: {"Content-Type": "application/json"},
        body: method === "DELETE" ? undefined : JSON.stringify(data)
      });
      editor.close();
      renderDeck();
      toast(method === "DELETE" ? "Карточка удалена" : "Карточка сохранена");
    } catch (failure) {
      error.textContent = failure.message || "Не удалось сохранить изменение карточки.";
      error.hidden = false;
    } finally {
      saving = false;
      for (const button of form.querySelectorAll("button")) button.disabled = false;
    }
  }

  try {
    progress = readProgress();
  } catch {
    // The study screen can still open if storage is unavailable.
  }
  window.addEventListener("storage", event => {
    if (event.key !== progressKey && event.key !== null) return;
    try {
      progress = readProgress();
      render();
    } catch {
      // Keep the last readable state until storage becomes available again.
    }
  });

  document.querySelector('[data-view="french"]').addEventListener("click", () => {
    if (loaded || panel === "guide") render();
    else loadCards();
  });
  $("french-view").addEventListener("click", event => {
    const button = event.target.closest("button");
    if (!button) return;
    const {frenchPanel, frenchKind, frenchRating, frenchEdit} = button.dataset;
    if (frenchPanel && frenchPanel !== panel) {
      if (frenchPanel === "deck") endSession();
      panel = frenchPanel;
      for (const tab of document.querySelectorAll("[data-french-panel]")) {
        const active = tab === button;
        tab.classList.toggle("active", active);
        tab.setAttribute("aria-pressed", active);
      }
      render();
      if (panel !== "guide" && !loaded) loadCards();
    }
    if (frenchKind && frenchKind !== kind) {
      kind = frenchKind;
      endSession();
      completed = null;
      for (const filter of document.querySelectorAll("[data-french-kind]")) {
        const active = filter === button;
        filter.classList.toggle("active", active);
        filter.setAttribute("aria-pressed", active);
      }
      render();
    }
    if (frenchRating) rate(frenchRating);
    if (frenchEdit) {
      const card = cards.find(item => item.id === frenchEdit);
      if (card) openEditor(card);
    }
  });
  $("french-retry").onclick = loadCards;
  $("french-start").onclick = () => {
    session = {answers: 0, newCards: 0};
    completed = null;
    nextCard();
  };
  $("french-finish").onclick = endSession;
  $("french-reveal").onclick = reveal;
  $("french-search").oninput = renderDeck;
  $("french-add").onclick = () => openEditor();
  form.elements.kind.onchange = () => {
    const conjugation = form.elements.kind.value === "conjugation";
    $("french-verb-model").hidden = form.elements.kind.value === "number";
    $("french-conjugation-hint").hidden = !conjugation;
    $("french-translation-field").hidden = !conjugation;
    form.elements.translation.disabled = !conjugation;
    form.elements.back.required = !conjugation;
  };
  $("french-close").onclick = $("french-cancel").onclick = () => editor.close();
  editor.addEventListener("cancel", event => {
    if (saving) event.preventDefault();
  });
  form.onsubmit = event => {
    event.preventDefault();
    changeCard(editing ? "PUT" : "POST");
  };
  $("french-delete").onclick = () => changeCard("DELETE");
})();
