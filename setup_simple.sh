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

# Try common installation paths
if [ -z "$PYTHON_CMD" ]; then
    for path in /usr/local/bin/python3.11 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11; do
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
echo "📦 Installing MCP SDK..."
$PYTHON_CMD -m pip install --user git+https://github.com/modelcontextprotocol/python-sdk.git

echo ""
echo "📦 Installing DUPRLY dependencies..."
$PYTHON_CMD -m pip install --user -r requirements.txt

echo ""
echo "📝 Checking .env file..."
if [ ! -f .env ]; then
    echo "Creating .env from env.example..."
    cp env.example .env
    echo "⚠️  Please edit .env with your DUPR credentials!"
    echo "   nano .env"
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
echo "To start the MCP server:"
echo "  $PYTHON_CMD duprly_mcp.py"
echo ""
echo "For Cursor MCP integration, use this command:"
echo "  $PYTHON_CMD"
echo ""
echo "And this path for args:"
echo "  $PWD/duprly_mcp.py"


