"""Proxy to the Intragent backend's ``/tools/*`` endpoints.

The MCP server is a thin transport shell: it authenticates the ChatGPT caller
(OAuth 2.1 + PKCE, verified in ``auth.py``) and forwards each tool call to the
existing Intragent backend, which owns the tool logic, per-company credentials
(Supabase Vault), and the audit trail. The caller's own access token is
forwarded verbatim — the backend's ``require_oauth_token`` accepts it — so there
is a single identity end to end and the tools behave identically to the Custom
GPT channel.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.auth.middleware.auth_context import get_access_token


def _backend_url() -> str:
    return os.environ["INTRAGENT_BACKEND_URL"].rstrip("/")


_TIMEOUT = float(os.getenv("INTRAGENT_BACKEND_TIMEOUT", "30"))


async def call_tool(integration: str, tool: str, args: dict[str, Any]) -> Any:
    """Forward one tool call to ``POST /tools/{integration}/{tool}``.

    Returns the tool's ``result`` payload on success. Platform/backend errors
    (invalid token, tool not enabled for the company, upstream failure) are
    returned as ``{"error": ...}`` so the model receives a clear, readable
    message instead of an exception bubbling out of the transport.
    """
    access = get_access_token()
    if access is None:
        # /mcp is auth-gated, so this is defensive only.
        return {"error": "Not authenticated."}

    url = f"{_backend_url()}/tools/{integration}/{tool}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {access.token}"},
            json=args,
        )

    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        return {"error": f"Backend error {resp.status_code}: {detail}"}

    body = resp.json()
    # The backend wraps every tool result as {"result": ...}; unwrap it so the
    # model sees the data directly.
    return body.get("result", body) if isinstance(body, dict) else body
