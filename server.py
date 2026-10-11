"""Intragent MCP server — the ChatGPT plugin surface.

A thin OAuth 2.1 resource server over MCP streamable HTTP. It verifies the
caller's access token (``auth.py``) and forwards each tool call to the existing
Intragent backend (``backend_client.py``); the backend stays the single source
of truth for tool logic, per-company credentials, and audit. This runs
*alongside* the legacy Custom GPT (GPT Actions) setup — nothing here replaces or
removes it. See the FAQ: custom actions must be rebuilt as a custom MCP server,
which is what this is.

Auth discovery chain ChatGPT walks:
    /mcp (401) → this server's /.well-known/oauth-protected-resource/mcp
    → authorization_servers: [ backend ]
    → backend /.well-known/oauth-authorization-server (RFC 8414)
    → authorization-code + PKCE against the backend's /oauth/authorize + /token
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from mcp.server.auth.settings import AuthSettings  # noqa: E402  (after load_dotenv)
from mcp.server.mcpserver import MCPServer  # noqa: E402
from pydantic import AnyHttpUrl  # noqa: E402

from auth import IntragentTokenVerifier  # noqa: E402
from tools import register_tools  # noqa: E402

# The backend's public URL, which is also our OAuth authorization server (issuer).
_ISSUER_URL = os.environ["OAUTH_ISSUER_URL"].rstrip("/")
# This server's own public URL including the /mcp path (the protected resource).
_MCP_PUBLIC_URL = os.environ["MCP_PUBLIC_URL"].rstrip("/")
_HOST = os.getenv("MCP_HOST", "127.0.0.1")
_PORT = int(os.getenv("MCP_PORT", "8100"))

_INSTRUCTIONS = (
    "Query an Icelandic company's connected business tools — Regla (accounting "
    "and verkbókhald), Tímavera (time tracking) and Unimaze (e-invoicing). All "
    "tools are read-only except unimaze_mark_as_imported. The company is resolved "
    "from the signed-in user's token; never ask the user for a company id. "
    "Tímavera durations are in seconds; Regla project 'Quantity' is in hours — "
    "do not mix them."
)

mcp = MCPServer(
    name="Intragent",
    instructions=_INSTRUCTIONS,
    token_verifier=IntragentTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(_ISSUER_URL),
        resource_server_url=AnyHttpUrl(_MCP_PUBLIC_URL),
        required_scopes=None,
        # Our tokens carry aud "integragent-tools", not the MCP resource URL, and
        # the verifier checks that audience itself — so don't also enforce the
        # RFC 8707 resource match here.
        validate_token_resource=False,
    ),
)

register_tools(mcp)


if __name__ == "__main__":
    # Serves MCP streamable HTTP at {host}:{port}/mcp and the protected-resource
    # metadata at /.well-known/oauth-protected-resource/mcp.
    mcp.run(transport="streamable-http", host=_HOST, port=_PORT)
