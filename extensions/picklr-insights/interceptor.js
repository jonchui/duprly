/*
 * interceptor.js  —  runs in the page's MAIN world at document_start.
 *
 * PlayByPoint's admin reports render from its own JSON API (XHR/fetch).
 * Rather than scrape the 1,000+ page HTML table, we transparently patch
 * window.fetch and XMLHttpRequest, clone any JSON response that looks like
 * report/player/membership data, and hand it to the isolated content script
 * via window.postMessage. We never block, modify, or delay the page's own
 * requests — this is read-only observation.
 */
(function () {
  "use strict";
  if (window.__pbpInsightsInstalled) return;
  window.__pbpInsightsInstalled = true;

  const TAG = "PBP_INSIGHTS_CAPTURE";

  // URL fragments worth capturing. Broad on purpose; the analytics layer
  // decides what's actually a player/membership payload.
  const INTERESTING = [
    "report",
    "player",
    "member",
    "user",
    "booking",
    "subscription",
    "checkin",
    "attendance",
  ];

  function isInteresting(url) {
    if (!url) return false;
    const u = String(url).toLowerCase();
    if (!u.includes("playbypoint.com")) {
      // relative URLs resolve to the same origin, still fine
    }
    return INTERESTING.some((k) => u.includes(k));
  }

  function post(url, method, body) {
    try {
      window.postMessage(
        { __pbp: TAG, url: String(url), method: method || "GET", body },
        "*"
      );
    } catch (e) {
      /* body not cloneable / too large — ignore */
    }
  }

  function tryParse(text) {
    if (!text || typeof text !== "string") return null;
    const t = text.trim();
    if (!t || (t[0] !== "{" && t[0] !== "[")) return null;
    try {
      return JSON.parse(t);
    } catch (e) {
      return null;
    }
  }

  /* ---- patch fetch ---- */
  const origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function (input, init) {
      const url = typeof input === "string" ? input : input && input.url;
      const method =
        (init && init.method) ||
        (input && input.method) ||
        "GET";
      const p = origFetch.apply(this, arguments);
      if (isInteresting(url)) {
        p.then((res) => {
          try {
            res
              .clone()
              .text()
              .then((text) => {
                const json = tryParse(text);
                if (json) post(url, method, json);
              })
              .catch(() => {});
          } catch (e) {}
        }).catch(() => {});
      }
      return p;
    };
  }

  /* ---- patch XMLHttpRequest ---- */
  const XHR = window.XMLHttpRequest;
  if (XHR) {
    const origOpen = XHR.prototype.open;
    const origSend = XHR.prototype.send;
    XHR.prototype.open = function (method, url) {
      this.__pbpUrl = url;
      this.__pbpMethod = method;
      return origOpen.apply(this, arguments);
    };
    XHR.prototype.send = function () {
      if (isInteresting(this.__pbpUrl)) {
        this.addEventListener("load", () => {
          try {
            const ct = this.getResponseHeader("content-type") || "";
            if (this.responseType && this.responseType !== "text" && this.responseType !== "json") {
              return;
            }
            let json = null;
            if (this.responseType === "json") {
              json = this.response;
            } else if (ct.includes("json") || true) {
              json = tryParse(this.responseText);
            }
            if (json) post(this.__pbpUrl, this.__pbpMethod, json);
          } catch (e) {}
        });
      }
      return origSend.apply(this, arguments);
    };
  }
})();
