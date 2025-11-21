# 🚀 Quick Start Guide - Testing DUPRLY MCP

## ⚠️ Python Version Requirement

**You need Python 3.10 or higher!** Your system has Python 3.9.6.

### Option 1: Install Python 3.10+ (Recommended)

**Using Homebrew:**
```bash
brew install python@3.11
```

Then use it:
```bash
python3.11 -m pip install git+https://github.com/modelcontextprotocol/python-sdk.git
python3.11 duprly_mcp.py
```

**Or install Python 3.12:**
```bash
brew install python@3.12
python3.12 -m pip install git+https://github.com/modelcontextprotocol/python-sdk.git
python3.12 duprly_mcp.py
```

### Option 2: Use Cursor's Built-in Python

Cursor might have its own Python. Try this in Cursor's terminal:
```bash
# Check what Python Cursor uses
which python
python --version

# If it's 3.10+, install MCP
pip install git+https://github.com/modelcontextprotocol/python-sdk.git
```

## Step-by-Step Setup

### 1. Install Python 3.10+
```bash
brew install python@3.11
```

### 2. Install MCP SDK
```bash
python3.11 -m pip install git+https://github.com/modelcontextprotocol/python-sdk.git
python3.11 -m pip install -r requirements.txt
```

### 3. Create .env file
```bash
cp env.example .env
# Then edit .env with your DUPR credentials
nano .env
```

### 4. Test the Setup
```bash
python3.11 test_mcp.py
```

### 5. Start the MCP Server
```bash
python3.11 duprly_mcp.py
```

If it starts without errors, you're ready!

## Testing in Cursor

### Method 1: Direct Integration (Easiest)

1. **Open Cursor Settings** → **MCP**

2. **Add New Server:**
   - **Name**: `duprly`
   - **Command**: `/usr/local/bin/python3.11` (or wherever your Python 3.11 is)
   - **Args**: `["/absolute/path/to/duprly/duprly_mcp.py"]`
   - **Working Directory**: `/Users/jonchui/Documents/GitHub/duprly`

3. **Environment Variables** (optional, if not using .env):
   - `DUPR_USERNAME`: your email
   - `DUPR_PASSWORD`: your password
   - `DUPR_CLUB_ID`: your club ID

4. **Restart Cursor**

5. **Test it!** In Cursor chat, try:
   - "Search for players named John"
   - "Get database statistics"
   - "Show me club members"

### Method 2: Test with MCP Inspector

1. **Install MCP Inspector:**
   ```bash
   npm install -g @modelcontextprotocol/inspector
   ```

2. **Start the MCP server** (in one terminal):
   ```bash
   python3.11 duprly_mcp.py
   ```

3. **Start MCP Inspector** (in another terminal):
   ```bash
   mcp-inspector
   ```

4. **Connect** to your server and test the tools!

## Quick Test Commands

```bash
# Check setup
python3.11 test_mcp.py

# Test DUPR connection (if you have .env set up)
python3.11 -c "from dupr_client import DuprClient; from dotenv import load_dotenv; import os; load_dotenv(); d = DuprClient(); d.auth_user(os.getenv('DUPR_USERNAME'), os.getenv('DUPR_PASSWORD')); print('✅ DUPR connection OK')"

# Start MCP server
python3.11 duprly_mcp.py
```

## Troubleshooting

### "Python 3.10+ not found"
- Install via Homebrew: `brew install python@3.11`
- Or download from python.org

### "MCP package not found"
- Install from GitHub: `python3.11 -m pip install git+https://github.com/modelcontextprotocol/python-sdk.git`

### "DUPR_USERNAME not set"
- Create `.env` file: `cp env.example .env`
- Edit it with your credentials

### Server won't start
- Check Python version: `python3.11 --version` (should be 3.10+)
- Check MCP is installed: `python3.11 -c "import mcp; print('OK')"`
- Check .env file exists and has credentials

## Next Steps

Once it's working:
1. Try asking Cursor: "Search for players named [name]"
2. Try: "Get expected score for match between players X, Y vs Z, W"
3. Explore all 8 available tools!

