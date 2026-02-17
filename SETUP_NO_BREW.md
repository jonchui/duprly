# 🚀 DUPRLY MCP Setup (No Homebrew Required)

Since you don't have Homebrew, here are your options:

## Option 1: Install Python 3.10+ from python.org (Recommended)

### Step 1: Download Python
1. Go to https://www.python.org/downloads/
2. Download **Python 3.11** or **3.12** for macOS
3. Run the installer (it's a `.pkg` file)
4. **Important**: Check "Add Python to PATH" during installation

### Step 2: Verify Installation
Open a **new terminal** and check:
```bash
python3.11 --version
# Should show: Python 3.11.x
```

If that doesn't work, try:
```bash
/usr/local/bin/python3.11 --version
# or
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 --version
```

### Step 3: Install MCP SDK
```bash
# Use whichever python3.11 path worked above
python3.11 -m pip install --upgrade pip
python3.11 -m pip install git+https://github.com/modelcontextprotocol/python-sdk.git
python3.11 -m pip install -r requirements.txt
```

### Step 4: Create .env file
```bash
cp env.example .env
# Edit .env with your DUPR credentials
nano .env
```

### Step 5: Test it
```bash
python3.11 test_mcp.py
python3.11 duprly_mcp.py
```

## Option 2: Use Cursor's Built-in Python

Cursor might have its own Python that's newer. Let's check:

1. **Open Cursor's integrated terminal** (not system terminal)
2. Run:
   ```bash
   which python
   python --version
   ```

If it shows Python 3.10+, you're good! Then:
```bash
pip install git+https://github.com/modelcontextprotocol/python-sdk.git
pip install -r requirements.txt
```

Then configure Cursor MCP to use that Python.

## Option 3: Install Homebrew (Optional, but useful)

If you want Homebrew for future use:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then you can use the automated setup script.

## Quick Setup Script (After Python 3.11 is installed)

Once you have Python 3.11 installed, run:

```bash
# Find your Python 3.11
PYTHON=$(which python3.11 || echo "/usr/local/bin/python3.11")

# Install everything
$PYTHON -m pip install --upgrade pip
$PYTHON -m pip install git+https://github.com/modelcontextprotocol/python-sdk.git
$PYTHON -m pip install -r requirements.txt

# Create .env
cp env.example .env
echo "⚠️  Edit .env with your DUPR credentials!"

# Test
$PYTHON test_mcp.py
```

## Configuring Cursor MCP

Once Python 3.11 is working:

1. **Find your Python 3.11 path:**
   ```bash
   which python3.11
   # or
   /usr/local/bin/python3.11 --version
   ```

2. **In Cursor Settings → MCP**, add:
   - **Name**: `duprly`
   - **Command**: `/usr/local/bin/python3.11` (or your actual path)
   - **Args**: `["/Users/jonchui/Documents/GitHub/duprly/duprly_mcp.py"]`
   - **Working Directory**: `/Users/jonchui/Documents/GitHub/duprly`

3. **Environment Variables** (if not using .env):
   - `DUPR_USERNAME`: your email
   - `DUPR_PASSWORD`: your password  
   - `DUPR_CLUB_ID`: your club ID

4. **Restart Cursor**

## Troubleshooting

### "python3.11: command not found"
- Make sure you installed Python from python.org
- Check if it's in a different location:
  ```bash
  ls -la /usr/local/bin/python3*
  ls -la /Library/Frameworks/Python.framework/Versions/*/bin/python3*
  ```

### "Permission denied"
- Use `--user` flag:
  ```bash
  python3.11 -m pip install --user git+https://github.com/modelcontextprotocol/python-sdk.git
  ```

### Still having issues?
- Check Python version: `python3.11 --version` (must be 3.10+)
- Check pip works: `python3.11 -m pip --version`
- Try installing with user flag: `python3.11 -m pip install --user <package>`


