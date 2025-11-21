# Quick MCP Setup Guide

## Installation

1. **Install MCP SDK**:
   ```bash
   pip install mcp
   ```
   
   If that doesn't work, try:
   ```bash
   pip install mcp-python
   ```
   
   Or check the official MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk

2. **Install DUPRLY dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure `.env` file**:
   ```env
   DUPR_USERNAME=your_email@example.com
   DUPR_PASSWORD=your_password
   DUPR_CLUB_ID=your_club_id
   ```

## Quick Test

Test the MCP server directly:
```bash
python duprly_mcp.py
```

If you see no errors, the server is ready to use.

## Cursor Integration (Simplest)

1. Open Cursor Settings > MCP
2. Add new server:
   - **Command**: `python /absolute/path/to/duprly/duprly_mcp.py`
   - Or if using uv: `uvx duprly-mcp`

## Claude Desktop Integration

Edit `claude_desktop_config.json`:
```json
{
    "mcpServers": {
        "duprly": {
            "command": "python",
            "args": ["/absolute/path/to/duprly/duprly_mcp.py"]
        }
    }
}
```

## Troubleshooting

### "mcp package not installed"
- Run: `pip install mcp`
- If that fails, check: https://github.com/modelcontextprotocol/python-sdk

### "DUPR_USERNAME not set"
- Create `.env` file in the project root
- Add your DUPR credentials

### Import errors
- Make sure you're in the project directory
- Verify all dependencies: `pip install -r requirements.txt`

