#!/usr/bin/env bash
# Run DUPRLY MCP server. Same script works on MacBook or Mac Mini.
# Usage: ./run.sh           # stdio (for Cursor)
#        ./run.sh --sse --port 8000   # HTTP/SSE (for Poke, etc.)

set -e
cd "$(dirname "$0")"

# Find Python 3.10+
PYTHON_CMD=""
for py in python3.11 python3.12 python3.10 python3; do
    if command -v "$py" &>/dev/null; then
        ver=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        if [ -n "$ver" ]; then
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; then
                PYTHON_CMD="$py"
                break
            fi
        fi
    fi
done
[ -z "$PYTHON_CMD" ] && for path in /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11; do
    if [ -x "$path" ]; then
        PYTHON_CMD="$path"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo "❌ Python 3.10+ not found. Install from https://www.python.org/downloads/ or run: brew install python@3.11"
    exit 1
fi

# Ensure .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env from .env.template..."
    cp .env.template .env
    echo "   Edit .env or run: $PYTHON_CMD scripts/set_secrets.py"
fi

exec "$PYTHON_CMD" duprly_mcp.py "$@"
