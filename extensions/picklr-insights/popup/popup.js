function relay(payload, cb) {
  chrome.runtime.sendMessage({ type: "pbp-relay", payload }, (resp) => {
    if (chrome.runtime.lastError) { cb({ ok: false }); return; }
    cb(resp || { ok: false });
  });
}

function renderCounts(counts) {
  const box = document.getElementById("stats");
  if (!counts) {
    box.innerHTML = '<p style="margin:0">No data captured yet. Open the PlayByPoint Reports → All Users page and scroll.</p>';
    return;
  }
  const rows = [
    ["Active paid members", counts.activePaid],
    ["Members (any)", counts.members],
    ["Unique rows", counts.unique],
    ["Captured rows", counts.captured],
  ];
  box.innerHTML = rows.map(([l, v]) => `<div class="stat"><span>${l}</span><b>${(v ?? 0).toLocaleString()}</b></div>`).join("");
}

document.getElementById("open").addEventListener("click", () => {
  relay({ type: "pbp-open-panel" }, (r) => {
    if (!r.ok) { document.getElementById("err").textContent = "Open a PlayByPoint tab first."; return; }
    if (r.resp && r.resp.counts) renderCounts(r.resp.counts);
    window.close();
  });
});

document.getElementById("clear").addEventListener("click", () => {
  relay({ type: "pbp-clear" }, () => renderCounts(null));
});

relay({ type: "pbp-get-counts" }, (r) => {
  if (r.ok && r.resp) renderCounts(r.resp.counts);
  else renderCounts(null);
});
