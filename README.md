# DUPR Data Tools

A comprehensive suite of tools for managing DUPR (Dynamic Universal Pickleball Rating) data, including both Python-based data analysis and Google Apps Script automation for club management.

## 🎯 What's Included

### 1. **DUPR Club Manager** (Google Apps Script)
Automatically search DUPR players, verify identity, track historical ratings, and add members to your club.

**📁 Files:**
- `dupr_club_manager_fixed.gs` - Main Google Apps Script
- `README_DUPR_CLUB_MANAGER.md` - Complete setup guide

**🚀 Quick Start:**
1. Copy `dupr_club_manager_fixed.gs` to Google Apps Script
2. Update CONFIG with your DUPR credentials
3. Run `setup()` to initialize
4. Use `processAllPlayers()` to manage your club

### 2. **DUPR Data Downloader** (Python)
Pulls player and match history data for all players belonging to a club. This program pulls data from all the players that our players have played against even if they are not in the club, so the dataset can get pretty big.

The data is stored in a local sqlite3 database via SQLAlchemy (I am working on a Mac).
This is my yet another attempt to master SQLAlchemy ORM.

After normalizing the data, I am using datasette to analyze the data. It is a great tool.
Check it out!

### 3. **duprly web** (FastAPI + HTMX)
A small local web app that wraps the downloader/simulator in a browser UI with
a live DUPR player autocomplete. Run it with:

```bash
python3.11 -m venv .venv-web
.venv-web/bin/pip install -r api/requirements.txt 'uvicorn[standard]'
.venv-web/bin/uvicorn web.main:app --reload --port 8000
```

Then open [http://localhost:8000](http://localhost:8000). Pages:

- **`/forecast`** — pick 4 players via DUPR search and preview the rating
  delta of any 11-point score. Falls back to a reverse-engineered model if
  DUPR's `/match/forecast` endpoint is unreachable, otherwise shows the
  official per-player DUPR deltas.
- **`/goal`** — reverse-forecast: "what score would push my rating up by
  `+0.03`?" against a fixed lineup.
- **`/reset`** — **shadow-reset simulator**. Pick your DUPR player (by name,
  short id, numeric id, or `dashboard.dupr.com/.../player/<id>` URL) and
  a cutoff date (default `2024-04-16`, the start of the last public ratings
  overhaul). The app replays every one of your DUPR matches since the cutoff
  with your reliability forced to 0%, which gives the *maximum* per-match
  impact the model can assign — a directional lower bound for "what would
  my rating be if DUPR rebuilt it from scratch tomorrow?". Same reverse-
  engineered model caveat as the CLI script — treat it as a what-if, not a
  production DUPR number.
- **`/jupr`** — a local "what-if match log" you can edit independently of
  your official DUPR history.
- **`/api/docs`** — OpenAPI/Swagger for the underlying JSON API.

The player-picker autocomplete hits a hybrid cache-first / live-fallback
search (`/dupr/search`) backed by a `DuprCachedPlayer` SQLite table. It
preserves DUPR's own relevance ranking when live results are present, and
supports single-letter last-name queries like `Cody F`. Set `DUPR_USERNAME`
and `DUPR_PASSWORD` in `.env` to enable live fallback; without credentials
you get cache-only results.

## Setup Instructions

### For Google Apps Script (DUPR Club Manager)

1. **Copy Environment Template:**
   ```bash
   cp env.example .env
   ```

2. **Update `.env` with your DUPR credentials:**
   ```bash
   DUPR_USERNAME=your_email@example.com
   DUPR_PASSWORD=your_password_here
   DUPR_CLUB_ID=YOUR_CLUB_ID_HERE
   ```

3. **Follow the complete setup guide:** See `README_DUPR_CLUB_MANAGER.md` for detailed instructions

### For Python Tools (DUPR Data Downloader)

1. **Install Dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Configure Environment Variables:**
   Create a `.env` file in the project root with your DUPR credentials:

   ```bash
   DUPR_USERNAME=your_email@example.com
   DUPR_PASSWORD=your_password
   DUPR_CLUB_ID=your_club_id
   ```

   **Note:** You'll need to find your DUPR club ID. This can usually be found in the URL when viewing your club page on the DUPR website.

### 3. Run the Application

```bash
python3 duprly.py --help
```

### Available Commands

- `python3 duprly.py get-data` - Update all data from DUPR
- `python3 duprly.py get-player <player_id>` - Get a specific player
- `python3 duprly.py get-all-players` - Get all players from your club
- `python3 duprly.py get-matches <dupr_id>` - Get match history for a specific player
- `python3 duprly.py write-excel` - Generate Excel report
- `python3 duprly.py stats` - Show database statistics
- `python3 duprly.py update-ratings` - Update player ratings
- `python3 duprly.py build-match-detail` - Flatten match data for faster queries

### Shadow Reset Simulator (Last N Matches, CLI)

There are two flavors of this simulator in the repo:

- **CLI (rolling N-match windows)** — this section, `scripts/shadow_reset.py`.
  Replays your last 8/16/24 matches on demand, useful for tracking form.
- **Web UI (cutoff-date replay)** — [`/reset`](#3-duprly-web-fastapi--htmx)
  in the web app. Replays every match since a cutoff date (default
  `2024-04-16`) with reliability pinned to 0%. Good for the "if DUPR
  rebuilt my rating from scratch tomorrow" lower-bound.

Both share the same reverse-engineered delta model. Neither is DUPR
production code.

Use the Python simulator to replay your recent form over rolling match windows.

```bash
python3 scripts/shadow_reset.py --dupr-id YOUR_DUPR_ID --windows 8 16 24
```

Optional reliability modes:

```bash
# Include all matches (default)
python3 scripts/shadow_reset.py --dupr-id YOUR_DUPR_ID --mode include_all

# Skip matches below reliability threshold for the target player
python3 scripts/shadow_reset.py --dupr-id YOUR_DUPR_ID --mode min_rel_threshold --min-rel 95

# Apply current reliability as a weighting proxy to each impact
python3 scripts/shadow_reset.py --dupr-id YOUR_DUPR_ID --mode weighted_current
```

The output includes:
- baseline rating
- shadow rating for each window
- higher-of rating (`max(baseline, shadow)`)
- used/skipped matches and diversity diagnostics

Important caveat: this is a reverse-engineered approximation, not DUPR's internal production implementation.
It is designed for directional "what-if" analysis, especially for last `8/16/24` reset-style windows.

Run history is saved to SQLite by default:

- DB file: `shadow_reset_history.db`
- Tables:
  - `shadow_reset_runs` (one row per CLI invocation)
  - `shadow_reset_window_results` (one row per window per run)

Disable logging for one-off runs:

```bash
python3 scripts/shadow_reset.py --dupr-id YOUR_DUPR_ID --no-log
```

Use a custom DB path:

```bash
python3 scripts/shadow_reset.py --dupr-id YOUR_DUPR_ID --history-db data/shadow_runs.db
```

### Getting Started

1. First, run `get-all-players` to download all players from your club
2. Then run `get-data` to download all match history and update ratings
3. Use `write-excel` to generate a spreadsheet report
4. Use `stats` to see how much data you have

## API Issues

Keeping a list of things I found. Note that this is NOT a public and supported API.
I am just documenting it as I try different calls.

- Player call returns no DuprId field.
- double (and singles?) rating is always returned in the ratings field, not the verified field even
  if the rating is verified according to the isDoublesVerified field
- Match history calls returns teams with players but only minimal fields, and the players have a different type of DuprId

## Design Issues

- because different player data gets returned between the match calls and the
  player calls, saving a player, which is a composite object, is messy
- don't yell at me for storing the user id and password in a plain text env file!
  Actually this is really bad practice - do not do it.

## ToDo

- fix the write_excel code -- which is still using the old tinyDB database interface
- write tests!

## SQLAlchemy notes

## Selecting directly into list of objects

- use session.scalar(select(Class).where().all()) instead of session.execute(...).scalars()
- returning objects cannot be use outside of the session scope afterwards!!?

## Joins and selecting columns

result = session.execute(
...     select(User.name, Address.email_address)
...     .join(User.addresses)
...     .order_by(User.id, Address.id)

## M-1 Foreign Key

- in the child, store a FK field, but also
- declare a relationship field that is for object level reference

'''
class Rating(Base):
    ...
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"))
    player: Mapped["Player"] = relationship(back_populates="rating")
'''
