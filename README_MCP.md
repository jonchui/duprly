# DUPRLY MCP Server

An MCP (Model Context Protocol) server that exposes DUPR (Dynamic Universal Pickleball Rating) functionality, allowing you to interact with DUPR data through MCP-compatible clients like Claude Desktop or Cursor.

## Features

- **🔍 Player Search**: Search for DUPR players by name
- **👤 Player Information**: Get detailed player data including ratings
- **📊 Match History**: Retrieve match history for any player
- **🎯 Expected Scores**: Predict match outcomes using DUPR's expected score API
- **🏆 Club Management**: Get all members from your DUPR club
- **💾 Database Queries**: Query your local DUPR database
- **📈 Statistics**: Get database statistics

## Prerequisites

- **Python 3.10+** (required for the `mcp` package). On macOS, `python3` is often 3.9 — **you must use `python3.11`** (see below).
- DUPR account credentials
- `.env` file with your DUPR credentials (see setup below)

## Installation

### Option 1: Install from Source

```bash
# Clone the repository
git clone <your-repo-url>
cd duprly

# Install dependencies
pip install -r requirements.txt

# Or install as a package
pip install -e .
```

### Option 2: Install via uv (Recommended)

```bash
# Install uv if you haven't already
brew install uv  # macOS
# or follow instructions at https://github.com/astral-sh/uv

# Install the package
uv pip install -e .
```

## How to install MCP (Python 3.10+ required)

If you see **"No matching distribution found for mcp"** or **"Requires-Python >=3.10"**, your default `python3` is too old. Use **Python 3.11** explicitly:

```bash
# Install MCP and other deps (use python3.11, not python3)
python3.11 -m pip install mcp requests python-dotenv SQLAlchemy loguru
```

For SSE mode (Poke.com), also install:

```bash
python3.11 -m pip install starlette sse-starlette uvicorn
```

Then **run the server** with the same Python:

```bash
python3.11 duprly_mcp.py
# or for Poke.com:
python3.11 duprly_mcp.py --sse --port 8000
```

Don't have Python 3.11? Install it: `brew install python@3.11` then use `python3.11` as above.

---

## Setup

1. **Create `.env`** from the template (`.env` is gitignored; never commit it):
   ```bash
   cp .env.template .env
   ```

2. **Set your credentials** — either edit `.env` or store them in the system keychain (recommended for passwords and API key):
   - **Option A – .env only**: Edit `.env` and set `DUPR_USERNAME`, `DUPR_PASSWORD`, `DUPR_CLUB_ID`, and optionally `MCP_API_KEY`.
   - **Option B – Keychain (macOS)**: Install keyring and run the set-secrets script so passwords and API key are stored in Keychain instead of plain text:
     ```bash
     pip install keyring   # or: pip install -e ".[keychain]"
     python3 scripts/set_secrets.py
     ```
     You can then remove or leave blank the sensitive values in `.env`; the app will read them from the keychain.

3. **Install dependencies** (required before running the server). Use **Python 3.10+** (e.g. `python3.11` on macOS if `python3` is 3.9):
   ```bash
   python3.11 -m pip install -r requirements.txt
   ```
   Or install the package with SSE support: `python3.11 -m pip install -e ".[sse]"`

4. **Test the MCP server** (use the same Python you used for install, e.g. `python3.11`):
   ```bash
   python3.11 duprly_mcp.py
   ```

## Run on this Mac or Mac Mini

Same steps on **any Mac** (MacBook, Mac Mini, etc.):

**One-time setup (per machine):**
```bash
cd duprly
./setup_simple.sh                    # installs deps, creates .env from .env.template
python3.11 scripts/set_secrets.py    # store DUPR + optional MCP_API_KEY in keychain (recommended)
```

**Run the server:**
```bash
cd duprly
./run.sh                 # stdio mode (for Cursor on this machine)
./run.sh --sse --port 8000   # HTTP/SSE (for Poke; use http://127.0.0.1:8000/sse)
```

With **just** (if installed): `just mcp` or `just mcp-sse` or `just set-secrets`.

The `run.sh` script finds Python 3.10+ for you (including `/opt/homebrew/bin/python3.11` on Apple Silicon Mac Mini). No need to remember the Python path.

## Integration

### Claude Desktop Integration

1. Go to **Claude** > **Settings** > **Developer** > **Edit Config** > **claude_desktop_config.json**

2. Add the following configuration:

```json
{
    "mcpServers": {
        "duprly": {
            "command": "python",
            "args": [
                "/absolute/path/to/duprly/duprly_mcp.py"
            ],
            "env": {
                "DUPR_USERNAME": "your_email@example.com",
                "DUPR_PASSWORD": "your_password_here",
                "DUPR_CLUB_ID": "YOUR_CLUB_ID_HERE"
            }
        }
    }
}
```

**Or using uvx** (if installed via uv):

```json
{
    "mcpServers": {
        "duprly": {
            "command": "uvx",
            "args": [
                "duprly-mcp"
            ]
        }
    }
}
```

### Cursor Integration

**Option A – Project config (recommended)**  
This repo includes `.cursor/mcp.json`. With the **duprly** folder open as your Cursor workspace, Cursor will start the DUPRLY MCP server automatically when you use it.

1. Open the **duprly** project in Cursor (File → Open Folder → select the `duprly` folder).
2. Reload or restart Cursor so it picks up `.cursor/mcp.json`.
3. In any chat, try: *"What's my DUPR rating?"* or *"Search for player Alaina Naccarato"* — Cursor will call the DUPRLY tools.

**Option B – Manual config**  
1. Go to **Cursor Settings** → **MCP**  
2. Add a server: **Name** `duprly`, **Command** `python3.11`, **Args** `["/absolute/path/to/duprly/duprly_mcp.py"]`  
3. If you don’t use keychain, add env: `DUPR_USERNAME`, `DUPR_PASSWORD` (and optionally `DUPR_CLUB_ID`).

**Or using uvx**: `uvx duprly-mcp`

⚠️ **Note**: Only run one instance of the MCP server (either on Cursor or Claude Desktop), not both.

### Poke.com Integration

Poke.com connects to MCP servers over **HTTP/SSE**. To use DUPRLY from [Poke](https://poke.com):

1. **Install SSE dependencies**:
   ```bash
   pip install 'duprly-mcp[sse]'
   ```

2. **Run the MCP server in SSE mode** (expose it at a URL):
   ```bash
   python duprly_mcp.py --sse --port 8000
   ```
   For remote access (e.g. from Poke), expose this server via a public URL:
   - **Local testing**: Use [ngrok](https://ngrok.com) or similar: `ngrok http 8000`, then use the `https://.../sse` URL.
   - **Production**: Deploy the app (e.g. on Railway, Fly.io, or a VPS) and use your public URL.

3. **Add the integration in Poke**:
   - Go to **Settings → Connections** in the Poke app
   - Click **Add Integration** → **Create**
   - Enter a **Name** (e.g. `duprly`)
   - **MCP Server URL**: use **`http://127.0.0.1:8000/sse`** (not `http://0.0.0.0:8000/sse`) when Poke is on the same machine. For remote access use your public URL + `/sse`.
   - **API Key**: leave empty unless you want auth. To generate and set a unique key: **`python3.11 scripts/generate_mcp_api_key.py`** (or **`just mcp-key`**), then paste the printed key into Poke's API Key field.
   - Click **Create Integration**

You can then ask Poke to use DUPR (e.g. "What's my DUPR rating?" or "Search for player Alaina").

## Available Tools

### `search_players`
Search for DUPR players by name.

**Parameters:**
- `query` (required): Player name to search for
- `limit` (optional): Maximum number of results (default: 25)

**Example:**
```
Search for players named "John Smith"
```

### `get_player`
Get detailed information about a specific player.

**Parameters:**
- `player_id` (required): DUPR player ID

**Example:**
```
Get player information for ID "1234567890"
```

### `get_player_matches`
Get match history for a specific player.

**Parameters:**
- `dupr_id` (required): DUPR player ID

**Example:**
```
Get match history for player "1234567890"
```

### `get_expected_score`
Get expected scores for a doubles match between two teams.

**Parameters:**
- `player1_id` (required): Numeric DUPR ID for player 1 on team 1
- `player2_id` (required): Numeric DUPR ID for player 2 on team 1
- `player3_id` (required): Numeric DUPR ID for player 1 on team 2
- `player4_id` (required): Numeric DUPR ID for player 2 on team 2

**Example:**
```
Get expected score for match between players 1234567890 & 9876543210 vs 5555555555 & 6666666666
```

### `get_my_profile`
Get the logged-in user's DUPR profile and ratings (doubles and singles).

**Parameters:** None (uses DUPR_USERNAME/DUPR_PASSWORD from .env)

**Example:**
```
What's my DUPR score?
```

### `get_club_members`
Get all members from your DUPR club.

**Parameters:**
- `club_id` (optional): DUPR club ID (uses DUPR_CLUB_ID from .env if not provided)

**Example:**
```
Get all members from my club
```

### `get_database_stats`
Get statistics about the local DUPR database.

**Example:**
```
Get database statistics
```

### `query_players`
Query players from the local database by name or DUPR ID.

**Parameters:**
- `query` (required): Search query (name or DUPR ID)

**Example:**
```
Find players named "John" in the database
```

### `get_player_rating_history`
Get a player's rating history from the local database.

**Parameters:**
- `dupr_id` (required): DUPR player ID

**Example:**
```
Get rating history for player "1234567890"
```

## Usage Examples

Once integrated, you can use natural language to interact with DUPR:

- "Search for players named John Smith"
- "Get the expected score for a match between players 1234567890 and 9876543210 vs 5555555555 and 6666666666"
- "Show me all members in my club"
- "What are the database statistics?"
- "Find players with 'Smith' in their name"

## Development

### Running the Server Directly

```bash
python duprly_mcp.py
```

The server will run in stdio mode, ready to accept MCP requests.

### Testing

Test individual functions:

```bash
# Test player search
python -c "from duprly_mcp import *; ensure_auth(); rc, r = dupr.search_players('John'); print(r)"

# Test database query
python -c "from duprly_mcp import *; from sqlalchemy.orm import Session; from dupr_db import eng, Player, select; sess = Session(eng); players = sess.scalars(select(Player).limit(5)).all(); print([p.full_name for p in players])"
```

## Troubleshooting

### Authentication Errors

- Ensure your `.env` file has correct `DUPR_USERNAME` and `DUPR_PASSWORD`
- Check that your credentials are valid by testing with `duprly.py` directly

### Import Errors / "No matching distribution found for mcp"

- The `mcp` package requires **Python 3.10+**. If you see this error, your default `python3` is likely 3.9 (e.g. Xcode's).
- Use a newer Python for install and run:
  ```bash
  python3.11 -m pip install -r requirements.txt
  python3.11 duprly_mcp.py --sse --port 8000
  ```
- On macOS with Homebrew: `brew install python@3.11` then use `python3.11` as above.

### 401 "Unauthorized: Invalid or missing API key" (e.g. when using Poke)

- **Use the right URL**: In Poke, use **`http://127.0.0.1:8000/sse`** (or `http://localhost:8000/sse`), not `http://0.0.0.0:8000/sse`. `0.0.0.0` is the server bind address, not a URL clients should use.
- **Optional API key**: Generate one with **`python3.11 scripts/generate_mcp_api_key.py`** (or **`just mcp-key`**); it’s stored in keychain or `.env` and printed so you can paste it into Poke’s "API Key" field. If you don’t want auth, leave `MCP_API_KEY` unset and leave Poke’s API key empty.

### MCP Connection Issues

- Check that the path to `duprly_mcp.py` is absolute in your MCP configuration
- Ensure the Python interpreter path is correct
- Check MCP client logs for detailed error messages

## Security Notes

- Never commit your `.env` file to version control
- The `.env` file contains sensitive credentials - keep it secure
- Consider using environment variables instead of `.env` file in production

## License

MIT

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

