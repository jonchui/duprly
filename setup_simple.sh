#!/bin/bash
# Simple setup script - works without Homebrew
# Just install Python 3.11 from python.org first!

echo "🚀 DUPRLY MCP Simple Setup"
echo "=========================="
echo ""

# Try to find Python 3.11
PYTHON_CMD=""
for py in python3.11 python3.12 python3.10; do
    if command -v $py &> /dev/null; then
        VERSION=$($py --version 2>&1 | awk '{print $2}')
        MAJOR=$(echo $VERSION | cut -d. -f1)
        MINOR=$(echo $VERSION | cut -d. -f2)
        if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; then
            PYTHON_CMD=$py
            echo "✅ Found $py ($VERSION)"
            break
        fi
    fi
done

# Try common installation paths (Homebrew on Mac Mini / Apple Silicon, etc.)
if [ -z "$PYTHON_CMD" ]; then
    for path in /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11; do
        if [ -f "$path" ]; then
            VERSION=$($path --version 2>&1 | awk '{print $2}')
            PYTHON_CMD="$path"
            echo "✅ Found Python at $path ($VERSION)"
            break
        fi
    done
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Python 3.10+ not found!"
    echo ""
    echo "Please install Python 3.11 from:"
    echo "  https://www.python.org/downloads/"
    echo ""
    echo "Make sure to check 'Add Python to PATH' during installation."
    echo ""
    echo "After installing, run this script again."
    exit 1
fi

echo ""
echo "📦 Upgrading pip..."
$PYTHON_CMD -m pip install --upgrade pip --user

echo ""
echo "📦 Installing DUPRLY dependencies (MCP, keyring, etc.)..."
$PYTHON_CMD -m pip install --user -r requirements.txt

echo ""
echo "📝 Checking .env file..."
if [ ! -f .env ]; then
    echo "Creating .env from .env.template..."
    cp .env.template .env
    echo "⚠️  Set your credentials: edit .env or run set_secrets to use keychain:"
    echo "   $PYTHON_CMD scripts/set_secrets.py"
else
    echo "✅ .env file exists"
fi

echo ""
echo "🧪 Testing setup..."
$PYTHON_CMD test_mcp.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "Your Python command is: $PYTHON_CMD"
echo ""
echo "To start the MCP server (stdio for Cursor):"
echo "  ./run.sh"
echo "  # or: $PYTHON_CMD duprly_mcp.py"
echo ""
echo "For Poke / HTTP SSE:"
echo "  ./run.sh --sse --port 8000"
echo ""
echo "Store secrets in keychain (optional):"
echo "  $PYTHON_CMD scripts/set_secrets.py"
echo ""
echo "Cursor MCP: command = $PYTHON_CMD, args = $PWD/duprly_mcp.py"


