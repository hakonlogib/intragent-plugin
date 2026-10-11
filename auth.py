"""OAuth 2.1 token verification for the MCP resource server.

ChatGPT (the MCP client) obtains an access token from the Intragent backend's
OAuth server via the authorization-code + PKCE flow, then presents it to
``/mcp``. We verify it locally: it is the same self-contained HS256 token the
backend's ``require_oauth_token`` checks, signed with the shared
``OAUTH_TOKEN_SECRET``, so a tool call needs no extra round-trip. The raw token
is kept on the returned ``AccessToken`` so ``backend_client`` can forward it to
``/tools/*`` unchanged.
"""
from __future__ import annotations

import os

import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier

# Must match the backend's issue_access_token (openai_plugin/oauth_token.py):
# HS256, this audience, the same secret.
_AUDIENCE = "integragent-tools"


def _secret() -> str:
    secret = os.getenv("OAUTH_TOKEN_SECRET")
    if not secret:
        raise RuntimeError("OAUTH_TOKEN_SECRET is not configured.")
    return secret


class IntragentTokenVerifier(TokenVerifier):
    """Verify a backend-issued GPT access token; return its AccessToken or None."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            claims = jwt.decode(
                token,
                _secret(),
                algorithms=["HS256"],
                audience=_AUDIENCE,
            )
        except jwt.PyJWTError:
            return None

        company_id = claims.get("company_id")
        subject = claims.get("sub")
        if not company_id or not subject:
            return None

        return AccessToken(
            token=token,
            # The company is the tenant the token acts for; surfaced for logging.
            client_id=str(company_id),
            scopes=[],
            expires_at=claims.get("exp"),
        )
