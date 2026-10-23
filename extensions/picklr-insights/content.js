/*
 * content.js — ISOLATED world bootstrap.
 *
 * - Receives captured payloads from interceptor.js (via window.postMessage).
 * - Keeps an in-memory + chrome.storage.local cache (survives navigation).
 * - Recomputes analytics (analytics.js) and refreshes the panel (panel.js).
 * - Adds a launcher button and listens for popup / clear commands.
 */
(function () {
  "use strict";

  const TAG = "PBP_INSIGHTS_CAPTURE";
  const STORE_KEY = "pbp_captures_v1";
  const MAX_CAPTURES = 400; // bound memory; reports paginate

  window.__pbpCaptures = window.__pbpCaptures || [];
  let analysis = null;
  let saveTimer = null;

  // ---- load any previous session ----
  chrome.storage.local.get(STORE_KEY, (res) => {
    if (res && res[STORE_KEY] && Array.isArray(res[STORE_KEY])) {
      window.__pbpCaptures = res[STORE_KEY];
      recompute();
    }
  });

  function persist() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      try {
        chrome.storage.local.set({ [STORE_KEY]: window.__pbpCaptures });
      } catch (e) {}
    }, 800);
  }

  function recompute() {
    try {
      analysis = window.PBP.analyze(window.__pbpCaptures);
    } catch (e) {
      analysis = null;
    }
    if (window.PBPPanel) window.PBPPanel.update();
  }

  // ---- ingest captures ----
  window.addEventListener("message", (ev) => {
    const d = ev.data;
    if (!d || d.__pbp !== TAG) return;
    window.__pbpCaptures.push({ url: d.url, method: d.method, body: d.body, t: Date.now() });
    if (window.__pbpCaptures.length > MAX_CAPTURES) {
      window.__pbpCaptures.splice(0, window.__pbpCaptures.length - MAX_CAPTURES);
    }
    persist();
    debounceRecompute();
  });

  let rcTimer = null;
  function debounceRecompute() {
    clearTimeout(rcTimer);
    rcTimer = setTimeout(recompute, 400);
  }

  // ---- clear ----
  window.addEventListener("pbp-clear", () => {
    window.__pbpCaptures = [];
    chrome.storage.local.remove(STORE_KEY);
    recompute();
  });

  // ---- popup / background messages ----
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg && msg.type === "pbp-open-panel") {
      ensurePanel();
      window.PBPPanel.show();
      sendResponse({ ok: true, counts: analysis ? analysis.counts : null });
    } else if (msg && msg.type === "pbp-get-counts") {
      sendResponse({ counts: analysis ? analysis.counts : null });
    } else if (msg && msg.type === "pbp-clear") {
      window.dispatchEvent(new CustomEvent("pbp-clear"));
      sendResponse({ ok: true });
    }
    return true;
  });

  function ensurePanel() {
    if (window.PBPPanel) window.PBPPanel.mount(() => analysis);
  }

  // ---- floating launcher button ----
  function addLauncher() {
    if (document.getElementById("pbp-insights-launch")) return;
    const btn = document.createElement("button");
    btn.id = "pbp-insights-launch";
    btn.textContent = "\u2191 Insights";
    btn.style.cssText =
      "position:fixed;bottom:18px;right:18px;z-index:2147483646;background:#1f6feb;color:#fff;" +
      "border:none;border-radius:99px;padding:10px 16px;font:600 13px -apple-system,sans-serif;" +
      "box-shadow:0 2px 10px rgba(0,0,0,.35);cursor:pointer;";
    btn.addEventListener("click", () => {
      ensurePanel();
      const host = document.getElementById("pbp-insights-host");
      if (host && host.style.display === "none") host.style.display = "";
      else window.PBPPanel.show();
    });
    document.body.appendChild(btn);
  }

  if (document.body) addLauncher();
  else document.addEventListener("DOMContentLoaded", addLauncher);

  ensurePanel();
})();
