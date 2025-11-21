#!/usr/bin/env python3
"""
Quick test script to verify MCP server setup
"""

import sys

print("Testing DUPRLY MCP Server Setup...")
print("=" * 50)

# Test 1: Python version
print(f"\n1. Python version: {sys.version}")
if sys.version_info < (3, 10):
    print("   ⚠️  WARNING: Python 3.10+ recommended (you have {sys.version_info.major}.{sys.version_info.minor})")
else:
    print("   ✅ Python version OK")

# Test 2: Check MCP package
print("\n2. Checking MCP package...")
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    print("   ✅ MCP package installed")
except ImportError as e:
    print(f"   ❌ MCP package not found: {e}")
    print("\n   To install MCP SDK, try:")
    print("   pip3 install mcp")
    print("   OR")
    print("   pip3 install git+https://github.com/modelcontextprotocol/python-sdk.git")
    sys.exit(1)

# Test 3: Check DUPRLY dependencies
print("\n3. Checking DUPRLY dependencies...")
try:
    from dupr_client import DuprClient
    from dupr_db import open_db
    from dotenv import load_dotenv
    print("   ✅ DUPRLY dependencies OK")
except ImportError as e:
    print(f"   ❌ Missing dependency: {e}")
    print("   Run: pip3 install -r requirements.txt")
    sys.exit(1)

# Test 4: Check .env file
print("\n4. Checking .env file...")
import os
from pathlib import Path
env_path = Path(".env")
if env_path.exists():
    print("   ✅ .env file found")
    load_dotenv()
    username = os.getenv("DUPR_USERNAME")
    password = os.getenv("DUPR_PASSWORD")
    club_id = os.getenv("DUPR_CLUB_ID")
    
    if username and password:
        print(f"   ✅ DUPR_USERNAME: {username[:3]}***")
        print(f"   ✅ DUPR_PASSWORD: {'*' * len(password) if password else 'NOT SET'}")
    else:
        print("   ⚠️  DUPR_USERNAME or DUPR_PASSWORD not set in .env")
    
    if club_id:
        print(f"   ✅ DUPR_CLUB_ID: {club_id}")
    else:
        print("   ⚠️  DUPR_CLUB_ID not set (optional)")
else:
    print("   ❌ .env file not found")
    print("   Create it by copying env.example: cp env.example .env")

# Test 5: Test database connection
print("\n5. Testing database connection...")
try:
    eng = open_db()
    print("   ✅ Database connection OK")
except Exception as e:
    print(f"   ⚠️  Database issue: {e}")
    print("   (This is OK if you haven't run duprly.py yet)")

print("\n" + "=" * 50)
print("Setup check complete!")
print("\nTo start the MCP server, run:")
print("  python3 duprly_mcp.py")

