# Intragent MCP server (ChatGPT plugin)

The ChatGPT **plugin** surface for Intragent, built as a **custom MCP server**.

OpenAI is retiring Custom GPTs (Dec 11, 2026) and moving to plugins. A GPT's
instructions carry over as a *skill* and connected apps as *apps*, but **custom
actions do not transfer — they must be rebuilt as a supported connector or a
custom MCP server** ([migration FAQ][faq]). Intragent's tools were a custom GPT
action; this repo is that rebuild.

It is a **thin proxy**. It does *not* re-implement any tool logic, credentials,
or database access. It:

1. speaks the MCP **streamable HTTP** transport at `/mcp`,
2. is an OAuth 2.1 **resource server** (verifies the caller's token; never
   issues tokens), and
3. forwards each tool call to the existing Intragent backend's
   `POST /tools/{integration}/{tool}` endpoints, passing the caller's token
   through unchanged.

The backend (`../integragent/backend`) stays the single source of truth for
tools (`TOOL_REGISTRY`), per-company credentials (Supabase Vault), and the audit
trail. **The legacy Custom GPT / GPT Actions setup is untouched and keeps
working** until it is retired.

## Architecture

```
ChatGPT (MCP client)
    │  MCP streamable HTTP + OAuth 2.1 (auth-code + PKCE/S256)
    ▼
This MCP server  (:8100/mcp)
    │  verifies the token locally (shared OAUTH_TOKEN_SECRET, HS256)
    │  forwards with the caller's Bearer token
    ▼
Intragent backend  (:8000)  POST /tools/{integration}/{tool}
    ▼
Regla · Tímavera · Unimaze
```

The 19 tools mirror exactly the set the Custom GPT exposed (Regla accounting +
verkbókhald, Tímavera, Unimaze). WooCommerce is a legacy demo and is not
exposed, matching the GPT surface.

## OAuth discovery chain

The plugin needs no new authorization server — it reuses the backend's. ChatGPT
walks:

1. `GET /mcp` → `401` with a `WWW-Authenticate` pointing at
   `…/.well-known/oauth-protected-resource/mcp` (served by this server via
   `AuthSettings`).
2. That metadata lists the backend as the `authorization_servers` entry.
3. ChatGPT reads the backend's `/.well-known/oauth-authorization-server`
   (RFC 8414 — added to the backend in this change) and runs the
   authorization-code + PKCE flow against `/oauth/authorize` + `/oauth/token`.
4. The backend issues its usual HS256 access token; this server verifies it and
   forwards it to `/tools/*`.

The backend changes for this are **additive** (PKCE + the metadata endpoint) and
do not affect the confidential Custom GPT client, which sends no PKCE and reads
no metadata. See `../integragent/supabase/migrations/0010_oauth_pkce.sql`.

## Running locally

Start the backend first (`../integragent/backend`, on `:8000`). Then:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # set OAUTH_TOKEN_SECRET to the backend's value
python server.py        # serves http://localhost:8100/mcp
```

Check discovery is up:

```bash
curl http://localhost:8100/.well-known/oauth-protected-resource/mcp
curl http://localhost:8000/.well-known/oauth-authorization-server
```

## Environment variables

| Name | Required | Purpose |
|------|----------|---------|
| `INTRAGENT_BACKEND_URL` | yes | Backend base URL; tool calls go to `…/tools/*` |
| `OAUTH_ISSUER_URL` | yes | OAuth issuer = backend public URL (usually same as above) |
| `MCP_PUBLIC_URL` | yes | This server's public URL **including `/mcp`** (the resource) |
| `OAUTH_TOKEN_SECRET` | yes | Must equal the backend's — verifies its HS256 tokens |
| `MCP_HOST` / `MCP_PORT` | no | Bind address/port (default `127.0.0.1:8100`) |
| `INTRAGENT_BACKEND_TIMEOUT` | no | Per-call HTTP timeout, seconds (default 30) |

## Registering with ChatGPT

Register `MCP_PUBLIC_URL` as a custom MCP server / connector in ChatGPT. Add an
`oauth_clients` row for it in Supabase (see the commented seed in
`0010_oauth_pkce.sql`) with ChatGPT's redirect URI. ChatGPT does PKCE, so the
client can be public (no secret) or confidential — both are accepted.

[faq]: https://help.openai.com/en/articles/20001519-custom-gpt-retirement-and-migration-faq
