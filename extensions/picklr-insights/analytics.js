/*
 * analytics.js — runs in the ISOLATED content-script world.
 *
 * Pure(ish) data layer: normalize captured PlayByPoint payloads into a
 * canonical row shape, then compute the member funnel and join-cohort
 * retention. Defensive about field names because PBP's report API field
 * names aren't documented — we look for many common aliases and expose a
 * `debugFields()` helper so mappings can be tuned after the first capture.
 *
 * Exposes a global `PBP` object consumed by panel.js / content.js.
 */
(function () {
  "use strict";

  // ---- field alias resolution -------------------------------------------
  const ALIASES = {
    id: ["member_id", "memberId", "id", "user_id", "userId", "uuid"],
    email: ["email", "email_address", "user_email"],
    name: ["name", "full_name", "fullName", "display_name"],
    first: ["first_name", "firstName", "first"],
    last: ["last_name", "lastName", "last"],
    association: ["association", "player_association", "type", "membership_status_label"],
    membershipStatus: ["status", "subscription_status", "membership_status", "state"],
    subscription: ["subscription", "subscription_details"],
    plan: ["membership_plan", "plan", "plan_name", "membership"],
    planPeriod: ["plan_period", "period", "billing_period"],
    billingAmount: ["billing_amount", "billingAmount", "amount", "price"],
    isTrial: ["trial", "is_trial", "isTrial"],
    totalVisits: ["total_visits", "totalVisits", "visits", "visit_count"],
    firstVisit: ["first_visit", "firstVisit", "first_visit_at"],
    lastVisit: ["last_visit", "lastVisit", "last_visit_at"],
    lastLogin: ["last_login", "lastLogin", "last_login_at"],
    dateJoined: ["date_joined", "dateJoined", "created_at", "createdAt", "acquisition_date", "joined_at", "signup_date"],
    acquisitionDate: ["acquisition_date", "acquisitionDate"],
    expirationDate: ["expiration_date", "expirationDate", "expires_at", "end_date"],
    nextBilling: ["next_billing_date", "nextBillingDate", "renewal_date"],
    duprSingles: ["dupr_singles", "duprSingles", "singles"],
    duprDoubles: ["dupr_doubles", "duprDoubles", "doubles"],
  };

  function pick(obj, key) {
    for (const a of ALIASES[key] || [key]) {
      if (obj[a] !== undefined && obj[a] !== null && obj[a] !== "") return obj[a];
    }
    return undefined;
  }

  // ---- find arrays of "row-like" objects inside any JSON payload ---------
  function extractRows(json) {
    const out = [];
    const seen = new Set();
    function looksLikeRow(o) {
      if (!o || typeof o !== "object" || Array.isArray(o)) return false;
      // a row should have at least an identity + one membership/visit signal
      const hasId = ["email", "member_id", "id", "uuid", "user_id"].some((k) => o[k] !== undefined);
      const hasSignal = [
        "association", "status", "subscription", "total_visits", "membership_plan",
        "date_joined", "created_at", "acquisition_date", "last_visit", "plan",
      ].some((k) => o[k] !== undefined);
      return hasId && hasSignal;
    }
    function walk(node, depth) {
      if (depth > 6 || node == null) return;
      if (Array.isArray(node)) {
        let rowsHere = 0;
        for (const el of node) {
          if (looksLikeRow(el)) {
            out.push(el);
            rowsHere++;
          } else {
            walk(el, depth + 1);
          }
        }
        return;
      }
      if (typeof node === "object") {
        for (const k of Object.keys(node)) walk(node[k], depth + 1);
      }
    }
    walk(json, 0);
    return out;
  }

  // ---- normalize one raw row into the canonical shape --------------------
  function normalize(raw) {
    const subText = String(pick(raw, "subscription") || "").toLowerCase();
    const statusRaw = String(pick(raw, "membershipStatus") || "").toLowerCase();
    const assoc = String(pick(raw, "association") || "").toLowerCase();

    let state = "unknown";
    const blob = subText + " " + statusRaw;
    if (/active|valid/.test(blob)) state = "active";
    if (/paus/.test(blob)) state = "paused";
    if (/fail|overdue|declin/.test(blob)) state = "failed";
    if (/cancel|expired|invalid/.test(blob)) state = "cancelled";

    const isMember =
      /member/.test(assoc) && !/non-?member/.test(assoc)
        ? true
        : pick(raw, "plan") !== undefined || state !== "unknown";

    const name =
      pick(raw, "name") ||
      [pick(raw, "first"), pick(raw, "last")].filter(Boolean).join(" ").trim() ||
      pick(raw, "email") ||
      "(unknown)";

    return {
      id: pick(raw, "id"),
      email: pick(raw, "email"),
      name,
      association: assoc || (isMember ? "member" : "non-member"),
      isMember,
      isTrial: /yes|true/i.test(String(pick(raw, "isTrial"))),
      state,
      plan: pick(raw, "plan"),
      planPeriod: pick(raw, "planPeriod"),
      billingAmount: num(pick(raw, "billingAmount")),
      totalVisits: num(pick(raw, "totalVisits")),
      dateJoined: parseDate(pick(raw, "acquisitionDate") || pick(raw, "dateJoined")),
      expirationDate: parseDate(pick(raw, "expirationDate")),
      lastVisit: parseDate(pick(raw, "lastVisit")),
      lastLogin: parseDate(pick(raw, "lastLogin")),
      _raw: raw,
    };
  }

  function num(v) {
    if (v === undefined || v === null || v === "") return null;
    const n = parseFloat(String(v).replace(/[^0-9.\-]/g, ""));
    return isNaN(n) ? null : n;
  }

  function parseDate(v) {
    if (!v) return null;
    if (v instanceof Date) return v;
    // numeric epoch?
    if (typeof v === "number") return new Date(v > 1e12 ? v : v * 1000);
    const d = new Date(v);
    return isNaN(d.getTime()) ? null : d;
  }

  function monthKey(d) {
    if (!d) return null;
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
  }

  // ---- dedup by id|email -------------------------------------------------
  function mergeRows(rows) {
    const map = new Map();
    for (const r of rows) {
      const key = (r.id != null ? "id:" + r.id : "") || (r.email ? "em:" + r.email : "") || JSON.stringify(r._raw).slice(0, 60);
      const prev = map.get(key);
      if (!prev) {
        map.set(key, r);
      } else {
        // prefer the record with more membership signal
        const score = (x) => (x.state !== "unknown" ? 2 : 0) + (x.plan ? 1 : 0) + (x.dateJoined ? 1 : 0);
        map.set(key, score(r) >= score(prev) ? { ...prev, ...stripEmpty(r) } : { ...r, ...stripEmpty(prev) });
      }
    }
    return [...map.values()];
  }
  function stripEmpty(o) {
    const c = {};
    for (const k of Object.keys(o)) if (o[k] !== undefined && o[k] !== null && o[k] !== "") c[k] = o[k];
    return c;
  }

  // ---- the funnel --------------------------------------------------------
  function funnel(rows) {
    const total = rows.length;
    const members = rows.filter((r) => r.isMember);
    const paid = members.filter((r) => !r.isTrial);
    const active = paid.filter((r) => r.state === "active");
    const RECENT_DAYS = 30;
    const now = Date.now();
    const activeRecent = active.filter(
      (r) => r.lastVisit && now - r.lastVisit.getTime() < RECENT_DAYS * 864e5
    );
    const frequent = active.filter((r) => (r.totalVisits || 0) >= 12);
    return [
      { stage: "All players (DB)", n: total },
      { stage: "Members (any)", n: members.length },
      { stage: "Paid members", n: paid.length },
      { stage: "Active paid", n: active.length },
      { stage: "Active + visited <30d", n: activeRecent.length },
      { stage: "Frequent (12+ visits)", n: frequent.length },
    ];
  }

  // ---- cohort retention --------------------------------------------------
  function cohorts(rows) {
    const paid = rows.filter((r) => r.isMember && !r.isTrial && r.dateJoined);
    const byMonth = new Map();
    for (const r of paid) {
      const k = monthKey(r.dateJoined);
      if (!byMonth.has(k)) byMonth.set(k, { joined: 0, active: 0 });
      const c = byMonth.get(k);
      c.joined++;
      if (r.state === "active") c.active++;
    }
    return [...byMonth.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([month, c]) => ({
        month,
        joined: c.joined,
        active: c.active,
        survival: c.joined ? c.active / c.joined : 0,
      }));
  }

  // ---- monthly signups vs cancellations ----------------------------------
  function flow(rows) {
    const signups = new Map();
    const cancels = new Map();
    const now = Date.now();
    for (const r of rows) {
      if (!r.isMember || r.isTrial) continue;
      if (r.dateJoined) bump(signups, monthKey(r.dateJoined));
      if ((r.state === "cancelled" || r.state === "failed") && r.expirationDate && r.expirationDate.getTime() <= now) {
        bump(cancels, monthKey(r.expirationDate));
      }
    }
    const months = [...new Set([...signups.keys(), ...cancels.keys()])].filter(Boolean).sort();
    return months.map((m) => ({
      month: m,
      signups: signups.get(m) || 0,
      cancels: cancels.get(m) || 0,
      net: (signups.get(m) || 0) - (cancels.get(m) || 0),
    }));
  }
  function bump(map, k) {
    if (!k) return;
    map.set(k, (map.get(k) || 0) + 1);
  }

  function debugFields(captures) {
    const seen = {};
    for (const cap of captures) {
      const rows = extractRows(cap.body);
      if (rows.length) {
        seen[cap.url] = { rows: rows.length, sampleKeys: Object.keys(rows[0]) };
      }
    }
    return seen;
  }

  // ---- top-level: captures -> everything ---------------------------------
  function analyze(captures) {
    let raw = [];
    for (const cap of captures) raw = raw.concat(extractRows(cap.body));
    const rows = mergeRows(raw.map(normalize));
    return {
      rows,
      funnel: funnel(rows),
      cohorts: cohorts(rows),
      flow: flow(rows),
      counts: {
        captured: raw.length,
        unique: rows.length,
        members: rows.filter((r) => r.isMember).length,
        activePaid: rows.filter((r) => r.isMember && !r.isTrial && r.state === "active").length,
      },
    };
  }

  function toCSV(rows) {
    const cols = [
      "id", "email", "name", "association", "isMember", "isTrial", "state",
      "plan", "planPeriod", "billingAmount", "totalVisits",
      "dateJoined", "expirationDate", "lastVisit", "lastLogin",
    ];
    const esc = (v) => {
      if (v == null) return "";
      if (v instanceof Date) return v.toISOString().slice(0, 10);
      const s = String(v).replace(/"/g, '""');
      return /[",\n]/.test(s) ? `"${s}"` : s;
    };
    const head = cols.join(",");
    const body = rows.map((r) => cols.map((c) => esc(r[c])).join(",")).join("\n");
    return head + "\n" + body;
  }

  window.PBP = { analyze, toCSV, debugFields, extractRows, normalize };
})();
