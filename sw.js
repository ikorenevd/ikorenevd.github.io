"use strict";

const ROOT = new URL("./", self.location.href);
const PREFIX = `organizer:${ROOT.pathname}:`;
const CACHE = `${PREFIX}v3`;
const FILES = [
  "./", "index.html", "styles.css?v=calendar-2", "calendar.css?v=readonly-1",
  "app.js?v=readonly-1", "calendar.js?v=readonly-1", "pwa.js?v=1",
  "manifest.webmanifest", "icons/apple-touch-icon.png?v=3", "icons/icon-192.png?v=3", "icons/icon-512.png?v=3",
  "src/data/movies.json", "src/data/series.json", "src/data/books.json",
  "src/data/events.json", "src/data/tasks.json"
];
const allowedPaths = new Set(FILES.map(file => new URL(file, ROOT).pathname));

async function usable(response, url) {
  if (!response.ok || response.type === "opaque") throw Error("Ресурс недоступен");
  if (url.pathname.endsWith(".json") && !Array.isArray(await response.clone().json())) {
    throw Error("Некорректный каталог");
  }
  return response;
}

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const entries = await Promise.all(FILES.map(async file => {
      const url = new URL(file, ROOT);
      const response = await usable(await fetch(url, {cache: "reload"}), url);
      return [url.href, response];
    }));
    const cache = await caches.open(CACHE);
    await Promise.all(entries.map(([url, response]) => cache.put(url, response)));
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    await Promise.all((await caches.keys()).filter(key => key.startsWith(PREFIX) && key !== CACHE).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== ROOT.origin || !allowedPaths.has(url.pathname)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    try {
      const response = await usable(await fetch(request, {cache: "no-store", signal: controller.signal}), url);
      await cache.put(request, response.clone());
      return response;
    } catch (error) {
      const saved = await cache.match(request, {ignoreSearch: true});
      if (saved) return saved;
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  })());
});
