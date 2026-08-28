---
title: "Harness HTTP route reference"
description: "This document is the canonical catalog of HTTP paths the Sentinel harness exposes on api.port (default 8080)."
---

# Harness HTTP route reference

This document is the **canonical catalog** of HTTP paths the Sentinel harness exposes on `api.port` (default `8080`). It complements [HTTP API Reference](/api-reference), which focuses on usage examples and payloads; this page focuses on **route prefixes** and how they interact with **default kit** and **keyhole** settings.

---

## Conventions

- Responses use the harness shape: HTTP **200** with errors in the JSON body (`ok`, `err`, `msg`) unless noted.
- Short prefixes follow the brevity regime for **core automation** (`/fl`, `/ex`, `/hl`, `/tr`, …).
- **Content planes** use clear multi-character names: `/fcms`, `/ccms` (see [Content planes](/content-planes)).
- Auth: in production mode, Bearer token or dashboard signing (`X-Sn-Sig`) applies except for explicitly public routes (see `system-specs/api.yaml`).

---

## Health and kit inventory

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/hl` | Health and component summary |
| GET | `/hl/runtime` | Runtime metadata (`sre_path`, `cwd`, project name, `public_url` from `sentinel.yaml`) |
| GET | `/hl/kt` | List discovered kits (`ok`, `kits[]` with `on` per kit) |
| GET | `/mcp` | MCP sidecar status + catalog (never tokens or license keys) |
| POST | `/hl/reload` | Full SRE reload (`kits_loaded`, `flows_registered`, `flows_removed`) |
| POST | `/hl/kt/{ns}/{name}/rl` | Reload one kit from disk |
| POST | `/hl/kt/{ns}/{name}/off` | Disable kit at runtime (optional body `{reason}`) |
| POST | `/hl/kt/{ns}/{name}/on` | Enable kit and reload from disk |

The dashboard and probes use **`GET /hl/kt`** for kit inventory (not `/hl/k`). Per-kit lifecycle routes are proxied by the dashboard BFF under `/api/dashboard/harness/kt/{ns}/{name}/rl|off|on` (see `specs/kitlife.md`).

---

## Default kit and keyhole (`keyhole` in `.sentinel/config.json`)

These interact **only when** `sentinel.yaml` sets **`default_kit`** (namespace + kit name). They control whether normal **kit HTTP routes** (`/kt/{ns}/{name}/...`) are registered on the main listener and how the **catch-all** page handler behaves.

| `keyhole` | Normal `/kt/...` routes | Notes |
|-----------|-------------------------|--------|
| **`blocked`** (default when empty) | **Not** mounted on the root router | The default kit owns **`GET /*`** for public pages. **`GET /hl/kt`** is still registered so APIs and the dashboard can list kits. |
| **`header`** | Mounted, but **`X-Sentinel-Keyhole`** + Bearer required | Lets operators hit `/kt/...` URLs while keeping public traffic on the default kit. |
| **Prefix** (e.g. `"_"`) | Mounted under **`/{prefix}/kt/...`** | Normal kit URLs move under the prefix; root stays with the default kit. |

Without `default_kit`, the harness registers full kit routes at **`/kt/...`** as usual; `keyhole` still resolves internally but the default-kit catch-all is not used.

---

## Flows, executions, logs

| Prefix | Purpose |
|--------|---------|
| `/fl` | Flow definitions and runs |
| `/ex` | Execution history and per-exec log streams (`/ex/{id}/lg`) |
| `/lg` | Log streams (including `/lg/live`) |

---

## Triggers, secrets, data services

| Prefix | Purpose |
|--------|---------|
| `/tr` | Trigger CRUD |
| `/sc` | Vault-backed secrets |
| `/pg` | PostgreSQL connection registry |
| `/st` | Storage points (S3-compatible) |
| `/fm` | Global forms index (non-kit-scoped) |

---

## Kit HTTP surface (`/kt/...`)

When kit routes are registered (see keyhole table):

| Pattern | Purpose |
|---------|---------|
| `/kt/{ns}/{name}` | Kit page |
| `/kt/{ns}/{name}/{page}` | Named page |
| `/kt/{ns}/{name}/fm/{form}` | Kit form GET/POST |
| `/kt/{ns}/{name}/pb/*` | Public bundle assets |
| `/kt/{ns}/{name}/pv/*` | Private assets (local-only middleware) |
| `/kt/{ns}/{name}/wh/*` | Kit webhooks |

---

## fcms — file CMS (`/fcms`, legacy `/cm` `/ct`)

Git-native Markdown content in kit `ct/` directories (**fcms** plane). Slash kit paths in URLs.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/fcms` (alias `/cm`) | List all content slugs |
| GET | `/fcms/{ns}/{name}/*` (alias `/cm/...`) | Parsed content (JSON); `?raw=1` for editor round-trip |
| GET | `/fcms/{ns}/{name}/_tree` | Hierarchical slug tree |
| GET | `/fcms/{ns}/{name}/_meta` | Folder → form name (`cms_metadata`) |
| POST | `/fcms/{ns}/{name}` | Create `ct/{slug}.md` |
| PUT | `/fcms/{ns}/{name}/*` | Update content |
| DELETE | `/fcms/{ns}/{name}/*` | Delete content |
| GET | `/fcms/render/{ns}/{name}/{template}/*` (alias `/ct/...`) | Render HTML via `tp/{template}.gohtml` (no Lua VM) |

Full operator guide: [17-SENTINEL-CMS.md](/sentinel-cms). Content planes: [24-CONTENT-PLANES.md](/content-planes).

## ccms — collection CMS (`/ccms`)

Postgres collections via Graphile (default host port **1880**). Independent of fcms content cache.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ccms/status` | Data plane + migrations + pub form count |
| GET | `/ccms/forms` | Live shippable form catalog |
| GET | `/ccms/{ns}/{name}/forms/{form}` | Editor form (HTML) or JSON (`?fmt=json`) |
| POST | `/ccms/{ns}/{name}/forms/{form}` | Submit via Graphile (fail closed if Graphile down) |
| GET | `/ccms/{ns}/{name}/forms/{form}/list` | Minimal list/browse surface |

CLI: `sentinel ccms migrate|validate|status|install-refkit`.

---

## MCP operator status (`GET /mcp`)

Read-only snapshot of the optional MCP sidecar (`sentinel harness start --mcp`). Always HTTP 200 with `{ok: true, ...}`. Returns the full tool/resource/prompt catalog even when `enabled` is false so operators can inspect the ceiling. Never includes bearer tokens, vault values, or occupy license keys.

The dashboard page `GET /mcp` and BFF `GET /api/dashboard/mcp` proxy this payload. Details: [MCP Agent Integration](/mcp-agent-integration).

---

## Other major prefixes

| Prefix | Purpose |
|--------|---------|
| `/ws` | WebSocket bus (harness) |
| `/wh/*` | Global webhooks |
| `/docker/*` | Compose stacks |
| `/lib/*` | API library vendors |
| `/ai/*`, `/rag/*` | AI/RAG endpoints |
| `/bk/*` | Backups |
| `/src/*` | Source file API |
| `/schema/*` | Schema helpers |
| `/cfg/*` | Config API |
| `/fs/pl`, `/fs/test` | Filesystem access policies (FS Control) |
| `/mk/*` | Marketplace (SKM) |
| `/cert/*` | TLS CA / server cert distribution |
| `/panic/recent` | Recovered panic events |
| `/ws/cfg`, `/ws/cn`, `/ws/dbg` | WS observability (HTTP) |

---

## Dashboard proxy mapping

The standalone dashboard rewrites friendly paths to harness brevity paths (see `internal/dashboard/proxy.go`). Examples:

- `/api/flows` → `/fl`
- `/api/executions` → `/ex`
- `/api/health` → `/hl`
- `/api/kt` or `/api/k` → `/hl/kt`
- `/api/dashboard/mcp` → `/mcp`
- `/api/fs/*` → `/fs/*`

---

## Spec sources

- Machine-readable overview: `system-specs/api.yaml`
- Kits and kit URLs: `system-specs/kits.yaml`
- Short URL cheat sheet: `sre-url-map.md`

When changing routes in code, update those specs and this document per project conventions.
