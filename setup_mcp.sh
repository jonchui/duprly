#!/bin/bash
# Quick setup script for DUPRLY MCP

set -e

echo "🚀 DUPRLY MCP Setup"
echo "==================="
echo ""

# Check Python version
PYTHON_CMD="python3"
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    echo "✅ Found Python 3.11"
elif command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
    echo "✅ Found Python 3.12"
elif command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
    echo "✅ Found Python 3.10"
else
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
    echo "⚠️  Current Python: $PYTHON_VERSION (need 3.10+)"
    echo ""
    echo "Installing Python 3.11 via Homebrew..."
    if command -v brew &> /dev/null; then
        brew install python@3.11
        PYTHON_CMD="python3.11"
        echo "✅ Python 3.11 installed"
    else
        echo "❌ Homebrew not found. Please install Python 3.10+ manually:"
        echo "   Visit: https://www.python.org/downloads/"
        exit 1
    fi
fi

echo ""
echo "📦 Installing MCP SDK..."
$PYTHON_CMD -m pip install --upgrade pip
$PYTHON_CMD -m pip install git+https://github.com/modelcontextprotocol/python-sdk.git

echo ""
echo "📦 Installing DUPRLY dependencies..."
$PYTHON_CMD -m pip install -r requirements.txt

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
echo "🧪 Running setup test..."
$PYTHON_CMD test_mcp.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the MCP server, run:"
echo "  $PYTHON_CMD duprly_mcp.py"
echo ""
echo "Or integrate with Cursor (see QUICK_START.md)"

