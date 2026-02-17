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

- Python 3.10+
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

## Setup

1. **Create `.env` file** (copy from `env.example`):
   ```bash
   cp env.example .env
   ```

2. **Configure your DUPR credentials** in `.env`:
   ```env
   DUPR_USERNAME=your_email@example.com
   DUPR_PASSWORD=your_password_here
   DUPR_CLUB_ID=YOUR_CLUB_ID_HERE
   ```

3. **Install dependencies** (required before running the server):
   ```bash
   pip install -r requirements.txt
   ```
   Or install the package with SSE support: `pip install -e ".[sse]"`

4. **Test the MCP server**:
   ```bash
   python duprly_mcp.py
   ```

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

1. Go to **Cursor Settings** > **MCP**

2. Add a new MCP server with:
   - **Name**: `duprly`
   - **Command**: `python /absolute/path/to/duprly/duprly_mcp.py`
   - **Environment Variables**: Add your DUPR credentials

**Or using uvx**:

```
uvx duprly-mcp
```

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
   - Enter the **MCP Server URL**: your base URL + `/sse` (e.g. `https://your-host.example.com/sse` or `https://xxxx.ngrok.io/sse`)
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

### Import Errors

- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Verify Python version is 3.10+: `python --version`

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

