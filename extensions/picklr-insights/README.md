# Picklr Insights — PlayByPoint Chrome Extension

Turns PlayByPoint's admin reports into **real, member-only data**. The native
"All Users" report counts the entire 34k+ contact database (86% of which are
non-members and ghost/0-visit records). This extension watches the report's own
API responses, filters to actual members, and renders a **funnel** and
**cohort/retention** breakdown — with one-click CSV export.

## How it works (no scraping, no extra API load)

1. `interceptor.js` runs in the page's **MAIN world** and transparently wraps
   `fetch` / `XMLHttpRequest`. When PlayByPoint loads report/member/booking
   JSON, it clones the response (read-only) and forwards it.
2. `content.js` (isolated world) caches captures in `chrome.storage.local` so
   they survive navigation, then runs the analytics and updates the panel.
3. `analytics.js` normalizes rows (defensive field-name aliasing), de-dupes by
   id/email, and computes the funnel, cohorts, and signup-vs-cancel flow.
4. `panel.js` renders a Shadow-DOM panel (PlayByPoint CSS can't interfere).

Because it reads the responses the page *already* fetches, it adds **zero**
extra API calls — you just scroll/paginate the report and the panel fills in.

## Install (unpacked)

1. Chrome → `chrome://extensions`
2. Toggle **Developer mode** (top right)
3. **Load unpacked** → select this folder (`extensions/picklr-insights`)
4. Go to PlayByPoint:
   `https://app.playbypoint.com/admin/facilities/thepicklrthornton/manage_bookings#/reports/players2`
5. Open **Reports → All Users** (and the **Memberships** report for status/
   plan/expiration data). Scroll / page through; bump the page-size selector to
   load more rows at once.
6. Click the floating **↑ Insights** button (bottom-right) or the toolbar icon.

## What you get

- **Funnel** — All players → Members → Paid → Active paid → Active+recent →
  Frequent (12+ visits). Strips out non-members and 0-visit ghosts.
- **Cohorts** — join-month → joined / still-active / survival %.
- **Signups vs Cancels** — monthly inflow/outflow + net (the seasonality view).
- **Members** — filtered member list, CSV export (members or all rows).
- **Capture** — debug tab showing which endpoints/fields were seen. Use this to
  confirm the field mapping (see below).

## Tuning field names

PlayByPoint's report API field names aren't publicly documented, so
`analytics.js` matches a list of common aliases per field (see `ALIASES`). After
your first capture, open the **Capture** tab — it prints the real `sampleKeys`
for each endpoint. If a field you care about isn't mapping, add its real key to
the relevant alias list in `analytics.js` and reload the extension. This is the
only step that may need a one-time adjustment against the live API.

## Privacy

All data stays local (in-memory + `chrome.storage.local`). Nothing is sent
anywhere. "Clear captured data" wipes it. Exports are plain CSV/JSON downloads
you trigger manually.

## Feeding it back into the analysis DB

The **Export members CSV** matches the column shape expected by
`scripts/import_picklr_checkins.py` work in the parent repo, so a fresh export
can refresh the churn/LTV canvases without a manual XLSX download.
