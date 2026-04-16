"""
Vercel Python ASGI entrypoint. Routes: /health, /sse, /messages/*
See DEPLOY.md for env vars and gateway-mcp wiring.
"""

from duprly_mcp import build_duprly_mcp_starlette_app

app = build_duprly_mcp_starlette_app()
