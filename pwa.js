"use strict";

// Local editing always talks to the Python server, without an offline worker.
const localPwaHost = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
if (!localPwaHost && location.protocol === "https:" && "serviceWorker" in navigator) {
  window.addEventListener("load", async () => {
    try {
      await navigator.serviceWorker.register("./sw.js", {scope: "./", updateViaCache: "none"});
    } catch (error) {
      console.warn("Офлайн-копия пока недоступна:", error);
    }
  });
  const notice = document.createElement("p");
  notice.textContent = "Нет интернета. Показана сохранённая копия данных.";
  notice.setAttribute("role", "status");
  notice.style.cssText = "padding:12px 18px;margin:0;background:#fff0da;color:#875219;text-align:center;font-size:14px";
  document.body.prepend(notice);
  const updateConnection = () => { notice.hidden = navigator.onLine; };
  updateConnection();
  window.addEventListener("offline", updateConnection);
  window.addEventListener("online", () => {
    updateConnection();
    if (typeof load === "function") load();
  });
}
