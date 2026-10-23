/*
 * background.js — MV3 service worker.
 * Minimal: relays the popup's "open panel" / "clear" commands to the active
 * PlayByPoint tab. All heavy lifting happens in the content scripts.
 */
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg && msg.type === "pbp-relay") {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const tab = tabs[0];
      if (!tab || !/playbypoint\.com/.test(tab.url || "")) {
        sendResponse({ ok: false, error: "not_on_playbypoint" });
        return;
      }
      chrome.tabs.sendMessage(tab.id, msg.payload, (resp) => {
        sendResponse({ ok: true, resp });
      });
    });
    return true; // async
  }
});
