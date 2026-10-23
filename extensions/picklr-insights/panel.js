/*
 * panel.js — ISOLATED world. Builds the floating "Picklr Insights" panel
 * inside a Shadow DOM so PlayByPoint's CSS can't touch it and vice-versa.
 * Reads window.PBP (analytics.js) and a getter for the current captures.
 * Exposes window.PBPPanel = { mount, update }.
 */
(function () {
  "use strict";

  const STYLE = `
    :host { all: initial; }
    * { box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .wrap { position: fixed; top: 0; right: 0; width: 460px; max-width: 96vw; height: 100vh;
            background: #14161a; color: #e6e8eb; z-index: 2147483647; box-shadow: -2px 0 18px rgba(0,0,0,.5);
            display: flex; flex-direction: column; border-left: 1px solid #2a2e35; }
    .hdr { display:flex; align-items:center; gap:8px; padding:12px 14px; border-bottom:1px solid #2a2e35; }
    .hdr h1 { font-size: 14px; font-weight: 700; margin:0; flex:1; }
    .badge { font-size:11px; background:#1f6feb22; color:#6cb0ff; border:1px solid #1f6feb55; padding:2px 7px; border-radius:99px; }
    .x { cursor:pointer; color:#8b949e; font-size:18px; line-height:1; padding:2px 6px; }
    .x:hover { color:#fff; }
    .tabs { display:flex; gap:4px; padding:8px 10px; border-bottom:1px solid #2a2e35; flex-wrap:wrap; }
    .tab { font-size:12px; padding:5px 10px; border-radius:6px; cursor:pointer; color:#9aa3ad; border:1px solid transparent; }
    .tab.active { background:#21262d; color:#fff; border-color:#30363d; }
    .body { padding:14px; overflow:auto; flex:1; }
    .stat-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:8px; margin-bottom:14px; }
    .stat { background:#1b1f24; border:1px solid #2a2e35; border-radius:8px; padding:10px; }
    .stat .v { font-size:20px; font-weight:700; }
    .stat .l { font-size:11px; color:#8b949e; margin-top:2px; }
    table { width:100%; border-collapse:collapse; font-size:12px; }
    th,td { text-align:left; padding:6px 8px; border-bottom:1px solid #23272e; }
    th { color:#8b949e; font-weight:600; }
    td.num, th.num { text-align:right; font-variant-numeric: tabular-nums; }
    .bar { height:8px; background:#1f6feb; border-radius:4px; }
    .barbg { background:#23272e; border-radius:4px; overflow:hidden; }
    .funnel-row { display:flex; align-items:center; gap:10px; margin:6px 0; }
    .funnel-row .name { width:160px; font-size:12px; color:#cdd3da; }
    .funnel-row .cnt { width:54px; text-align:right; font-weight:700; font-size:13px; }
    .funnel-row .track { flex:1; }
    .btn { font-size:12px; background:#21262d; border:1px solid #30363d; color:#e6e8eb; padding:6px 10px;
           border-radius:6px; cursor:pointer; }
    .btn:hover { background:#2a313a; }
    .btn.primary { background:#1f6feb; border-color:#1f6feb; }
    .row { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
    .muted { color:#8b949e; font-size:11px; }
    .empty { color:#8b949e; font-size:13px; text-align:center; padding:30px 10px; line-height:1.5; }
    code { background:#1b1f24; padding:1px 5px; border-radius:4px; font-size:11px; color:#9ecbff; }
    .neg { color:#f85149; } .pos { color:#3fb950; }
  `;

  let host, root, currentTab = "funnel", getData;

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    if (attrs) for (const k in attrs) {
      if (k === "class") e.className = attrs[k];
      else if (k === "text") e.textContent = attrs[k];
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), attrs[k]);
      else e.setAttribute(k, attrs[k]);
    }
    (children || []).forEach((c) => e.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
    return e;
  }

  function mount(getDataFn) {
    getData = getDataFn;
    if (host) return;
    host = el("div", { id: "pbp-insights-host" });
    document.documentElement.appendChild(host);
    root = host.attachShadow({ mode: "open" });
    root.appendChild(el("style", { text: STYLE }));
    render();
  }

  function setTab(t) { currentTab = t; render(); }

  function render() {
    if (!root) return;
    // clear (keep style node)
    [...root.querySelectorAll(".wrap")].forEach((n) => n.remove());

    const data = getData ? getData() : null;
    const wrap = el("div", { class: "wrap" });

    // header
    wrap.appendChild(el("div", { class: "hdr" }, [
      el("h1", { text: "Picklr Insights" }),
      el("span", { class: "badge", text: data ? `${data.counts.unique} rows` : "no data" }),
      el("span", { class: "x", text: "\u2715", onclick: () => host.style.display = "none" }),
    ]));

    // tabs
    const tabs = el("div", { class: "tabs" });
    [["funnel", "Funnel"], ["cohorts", "Cohorts"], ["flow", "Signups vs Cancels"], ["members", "Members"], ["debug", "Capture"]]
      .forEach(([id, label]) => {
        tabs.appendChild(el("div", {
          class: "tab" + (currentTab === id ? " active" : ""), text: label, onclick: () => setTab(id),
        }));
      });
    wrap.appendChild(tabs);

    const body = el("div", { class: "body" });
    if (!data || data.counts.unique === 0) {
      body.appendChild(el("div", { class: "empty" }, [
        "No member data captured yet.",
        el("br"), el("br"),
        "Open the PlayByPoint ",
        el("b", { text: "Reports \u2192 All Users" }),
        " (or the Memberships report) and scroll / paginate through it. ",
        "This panel fills in as the data loads.",
        el("br"), el("br"),
        el("span", { class: "muted", text: "Tip: use the report's own page-size selector to load more rows at once." }),
      ]));
    } else {
      ({ funnel: renderFunnel, cohorts: renderCohorts, flow: renderFlow, members: renderMembers, debug: renderDebug }[currentTab] || renderFunnel)(body, data);
    }
    wrap.appendChild(body);
    root.appendChild(wrap);
  }

  function renderFunnel(body, data) {
    const c = data.counts;
    const grid = el("div", { class: "stat-grid" });
    [["Active paid members", c.activePaid], ["Members (any)", c.members],
     ["Unique rows", c.unique], ["Captured rows", c.captured]]
      .forEach(([l, v]) => grid.appendChild(el("div", { class: "stat" }, [
        el("div", { class: "v", text: String(v) }), el("div", { class: "l", text: l }),
      ])));
    body.appendChild(grid);

    const max = Math.max(...data.funnel.map((f) => f.n), 1);
    data.funnel.forEach((f) => {
      const track = el("div", { class: "barbg track" }, [
        el("div", { class: "bar", style: `width:${(f.n / max) * 100}%` }),
      ]);
      body.appendChild(el("div", { class: "funnel-row" }, [
        el("span", { class: "name", text: f.stage }),
        el("span", { class: "cnt", text: f.n.toLocaleString() }),
        track,
      ]));
    });
    body.appendChild(el("div", { class: "muted", style: "margin-top:10px",
      text: "Non-members and 0-visit ghost records are excluded from every stage below the first." }));
  }

  function renderCohorts(body, data) {
    if (!data.cohorts.length) return body.appendChild(el("div", { class: "empty", text: "No join-date data captured yet." }));
    const tbl = el("table");
    tbl.appendChild(el("tr", {}, [
      el("th", { text: "Join month" }), el("th", { class: "num", text: "Joined" }),
      el("th", { class: "num", text: "Active" }), el("th", { class: "num", text: "Survival" }),
    ]));
    data.cohorts.forEach((c) => {
      tbl.appendChild(el("tr", {}, [
        el("td", { text: c.month }),
        el("td", { class: "num", text: String(c.joined) }),
        el("td", { class: "num", text: String(c.active) }),
        el("td", { class: "num", text: (c.survival * 100).toFixed(0) + "%" }),
      ]));
    });
    body.appendChild(tbl);
  }

  function renderFlow(body, data) {
    if (!data.flow.length) return body.appendChild(el("div", { class: "empty", text: "No signup/cancel dates captured yet." }));
    const tbl = el("table");
    tbl.appendChild(el("tr", {}, [
      el("th", { text: "Month" }), el("th", { class: "num", text: "Signups" }),
      el("th", { class: "num", text: "Cancels" }), el("th", { class: "num", text: "Net" }),
    ]));
    data.flow.forEach((f) => {
      tbl.appendChild(el("tr", {}, [
        el("td", { text: f.month }),
        el("td", { class: "num", text: String(f.signups) }),
        el("td", { class: "num", text: String(f.cancels) }),
        el("td", { class: "num " + (f.net < 0 ? "neg" : "pos"), text: (f.net > 0 ? "+" : "") + f.net }),
      ]));
    });
    body.appendChild(tbl);
  }

  function renderMembers(body, data) {
    const members = data.rows.filter((r) => r.isMember);
    body.appendChild(el("div", { class: "row" }, [
      el("button", { class: "btn primary", text: "Export members CSV", onclick: () => exportCSV(members, "picklr_members") }),
      el("button", { class: "btn", text: "Export all rows CSV", onclick: () => exportCSV(data.rows, "picklr_all_rows") }),
    ]));
    const tbl = el("table");
    tbl.appendChild(el("tr", {}, [
      el("th", { text: "Member" }), el("th", { text: "State" }),
      el("th", { text: "Plan" }), el("th", { class: "num", text: "Visits" }),
    ]));
    members.slice(0, 200).forEach((m) => {
      tbl.appendChild(el("tr", {}, [
        el("td", { text: m.name || m.email || m.id || "?" }),
        el("td", { text: m.state }),
        el("td", { text: m.plan || "" }),
        el("td", { class: "num", text: m.totalVisits != null ? String(m.totalVisits) : "" }),
      ]));
    });
    body.appendChild(tbl);
    if (members.length > 200) body.appendChild(el("div", { class: "muted", style: "margin-top:8px", text: `Showing first 200 of ${members.length}. Export CSV for all.` }));
  }

  function renderDebug(body, data) {
    body.appendChild(el("div", { class: "row" }, [
      el("button", { class: "btn", text: "Clear captured data", onclick: () => window.dispatchEvent(new CustomEvent("pbp-clear")) }),
      el("button", { class: "btn", text: "Export raw JSON", onclick: () => exportRaw() }),
    ]));
    const dbg = window.PBP.debugFields(window.__pbpCaptures || []);
    const keys = Object.keys(dbg);
    if (!keys.length) return body.appendChild(el("div", { class: "empty", text: "No row-shaped payloads captured yet." }));
    keys.forEach((url) => {
      body.appendChild(el("div", { style: "margin-bottom:10px" }, [
        el("div", { class: "muted", text: url.length > 70 ? "…" + url.slice(-70) : url }),
        el("div", { text: `${dbg[url].rows} rows` }),
        el("div", { class: "muted", text: "keys: " + dbg[url].sampleKeys.join(", ") }),
      ]));
    });
  }

  function exportCSV(rows, name) {
    const csv = window.PBP.toCSV(rows);
    download(csv, `${name}_${stamp()}.csv`, "text/csv");
  }
  function exportRaw() {
    download(JSON.stringify(window.__pbpCaptures || [], null, 2), `picklr_raw_${stamp()}.json`, "application/json");
  }
  function download(text, filename, type) {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const a = el("a", { href: url, download: filename });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }
  function stamp() { return new Date().toISOString().slice(0, 10); }

  function update() { render(); }
  function show() { if (host) host.style.display = ""; }

  window.PBPPanel = { mount, update, show };
})();
