---
title: "fcms (file CMS) — Operator Guide"
description: "Git-native file content in Sentinel: Markdown files in a kit’s ct/ directory are the source of truth."
---

# fcms (file CMS) — Operator Guide

> **Plane name:** **fcms** (file CMS). This is **not** collection CMS (**ccms**) or WordPress (**wpcms**).  
> See [Content planes](/content-planes) for the full model.  
> **Canonical routes:** `/fcms`, `/fcms/render`. **Legacy aliases:** `/cm`, `/ct` (deprecation window).

Git-native file content in Sentinel: Markdown files in a kit’s `ct/` directory are the source of truth. The harness parses them into a local cache, exposes structured JSON over **`/fcms`** (alias `/cm`), renders public HTML over **`/fcms/render`** (alias `/ct`), and makes the same data available to kit pages and Lua flows.

**Audience:** operators, SRE maintainers, and integrators who run or proxy **fcms**-backed sites — not harness contributors.

**Related docs:**

| Document | Focus |
|----------|--------|
| [Kit Development — CMS Kits](/kit-development#cms-kits) | Authoring kits, frontmatter, templates, `sn.cms.*` in Lua |
| [Lua API — CMS](/lua-api) | Flow-level `sn.cms.get` / `sn.cms.list` |
| [HTTP API Reference](/api-reference) | Full API payloads and error codes |
| [Harness HTTP routes](/harness-http-routes) | Prefix catalog and keyhole behavior |
| [The `.sentinel/` directory](/sentinel-directory) | `cms.db` location, backup, rebuild |
| `system-specs/api.yaml` | Machine-readable route definitions |

**Reference kit:** `sn.cms` in the integration test SRE (`../SRE/test/sn.cms` or `$SENTINEL_TEST_SRE/sn.cms`).

---

## Mental model

```text
  Git (authoritative)                Harness (runtime)
  ─────────────────                  ─────────────────

  {ns}.{name}/ct/**/*.md  ──watch──►  cms.db  (bbolt)
         │                              ├─ bucket "cms"   → parsed CacheEntry per slug
         │                              └─ bucket "render" → pre-rendered HTML (/ct only)
         │
         ├──► GET /cm/{ns}/{name}/…     JSON for editors & agents
         ├──► GET /ct/{ns}/{name}/{template}/…   HTML (Go templates, no Lua VM)
         └──► GET /kt/{ns}/{name}/…     Kit UI pages (Lua variables + tp/*.gohtml)
```

Three ways to publish HTML from the same content:

| Path | When to use | Lua at render? |
|------|-------------|----------------|
| **`/ct/...`** | Production site pages, reverse-proxied URLs, CDN-friendly static-ish HTML | **No** — fastest |
| **`/kt/...`** | Kit UI with dynamic variables, auth, sidebars, forms | **Yes** — page `variables:` and optional `pg/*.lua` merge |
| **Flow + template** | Custom logic, APIs, non-page responses | **Yes** — full flow sandbox |

**Important:** `md/` in a kit is reserved for **Lua modules** (`sn.md.*`). CMS Markdown lives only in **`ct/`**.

---

## On-disk layout

```text
sn.cms/                          # kit directory on disk: {namespace}.{kit_name}
  kit.yaml                       # cms_full_html, cms_render_cache_ttl_sec, cms_metadata, …
  ct/                            # CMS Markdown (source of truth)
    hello-world.md
    guides/getting-started.md
  pg/                            # Kit page definitions (optional UI routes)
    home.yaml                    # YAML only, or YAML + home.lua merge
    render.yaml
  tp/                            # Go html/template for pages and /ct
    home.html
    render.html
  fl/                            # Optional flows (e.g. legacy render helpers)
  fm/                            # Optional metadata forms (editor integration)
  pb/                            # Static assets (/kt/sn/cms/pb/…)
```

### Slugs

- Slug = path under `ct/` without `.md`, using `/` separators.
- `ct/hello-world.md` → slug `hello-world`
- `ct/guides/getting-started.md` → slug `guides/getting-started`

Internal cache keys use the on-disk kit directory name (`sn.cms`). HTTP APIs expose the **slash form** `sn/cms/...` for operators.

### `kit.yaml` CMS fields

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `cms_full_html` | bool | `false` | Populate `full_html` on parsed entries (needed for `{{ safeHTML .post.full_html }}` in templates). Rebuilt on cold start; see [Hot reload](#hot-reload). |
| `cms_render_cache_ttl_sec` | int | `0` (= harness default **300s**) | TTL for `/ct` HTML render cache entries. |
| `cms_metadata` | map | — | Maps content folder → form name for metadata editors (`GET /cm/{ns}/{name}/_meta`). |

Example:

```yaml
namespace: sn
kit-name: cms
cms_full_html: true
cms_render_cache_ttl_sec: 600
cms_metadata:
  _default: cms-post
  guides: cms-guide
```

There is **no** layout wrapper field in `kit.yaml` for CMS; layout is entirely in your `tp/*.gohtml` templates.

---

## URL conventions

CMS HTTP routes use **slash-separated kit paths**, aligned with kit UI URLs:

| Concept | On disk | HTTP (CMS) | Kit UI |
|---------|---------|------------|--------|
| Kit | `sn.cms/` | `sn/cms` | `/kt/sn/cms/...` |

The top-level prefix **`/ct`** is both the on-disk folder name (`ct/`) and the public HTML API — intentional symmetry for operators and reverse proxies.

Examples (harness on `http://127.0.0.1:8080`):

```http
GET /cm/sn/cms/guides/getting-started
GET /ct/sn/cms/render/guides/getting-started
GET /kt/sn/cms/render?slug=guides/getting-started
```

---

## Parse cache (`cms.db`)

Location: `{data_dir}/cms.db` (default `.sentinel/cms.db`). See [16-SENTINEL-DIRECTORY.md](/sentinel-directory).

| Bucket | Key | Value | Purpose |
|--------|-----|-------|---------|
| `cms` | `{kitDir}` → `{slug}` | JSON `CacheEntry` | Parsed frontmatter, preamble HTML, section tree, source path, content hash |
| `render` | `{kitDir}\|{template}\|{slug}` | JSON `{ html, made_ts }` | Cached output of `GET /ct/...` only |

**Source of truth remains git-tracked files in `ct/`.** Deleting `cms.db` is safe: the harness rebuilds the parse cache on next start from `ct/`. The render bucket is also rebuilt on demand after expiry or invalidation.

### Startup and rebuild

On harness start, the CMS builder walks all kits’ `ct/` trees and populates the `cms` bucket. If a kit is added or `ct/` changes while running, the project watcher updates parse entries and **invalidates** matching `render` keys for that slug (or the whole kit on ambiguous deletes).

---

## Content authoring

### Frontmatter

Each `ct/**/*.md` file may start with YAML frontmatter (`---` delimiters). Known fields map to structured types; any other keys are preserved under `meta`.

| Field | Required | Exposed via `/cm` | In Lua `sn.cms.get` |
|-------|----------|-------------------|---------------------|
| `title` | Recommended | Yes | Yes |
| `slug` | No (filename is canonical) | Yes | Yes |
| `date` | No | Yes | Yes |
| `description` | No | Yes | Yes |
| `tags` | No | Yes | Yes |
| `agent_context` | No | **Stripped** | Yes |
| Other keys | No | Under `meta` | Under `meta` |

**Lua in frontmatter is not supported** (performance and security). Use `ct/` Markdown + templates, or kit page `variables:` / `pg/*.lua` for dynamic behavior.

### Minimal example

```markdown
---
title: Hello World
date: 2026-03-01
description: First post
tags: [intro]
---

# Hello World

Body content before the first `##` heading becomes **preamble** HTML.

## Overview

This section is addressable in templates via `querySelector` or the `sections` map.
```

### Write API (create / update / delete)

Editors and automation can mutate files on disk through the harness (still subject to your git workflow):

| Method | Path | Body / notes |
|--------|------|----------------|
| `POST` | `/cm/{ns}/{name}` | `{ "slug", "frontmatter", "markdown" }` — creates `ct/{slug}.md` |
| `PUT` | `/cm/{ns}/{name}/{slug…}` | `{ "frontmatter", "markdown", "hash?" }` — optimistic concurrency via `hash` |
| `DELETE` | `/cm/{ns}/{name}/{slug…}` | Removes `ct/{slug}.md` (path-confined) |

All CMS JSON endpoints return HTTP **200** with `{ "ok": true, ... }` or `{ "ok": false, "err": "CODE", "msg": "..." }`.

Common error codes: `CMS.UNAVAILABLE`, `CMS.NOT_FOUND`, `CMS.INVALID_SLUG`, `CMS.CONFLICT`.

---

## `/cm` — structured content API

### List everything

```http
GET /cm
```

```json
{
  "ok": true,
  "slugs": [
    "sn/cms/hello-world",
    "sn/cms/guides/getting-started"
  ]
}
```

### Get one document (parsed)

```http
GET /cm/sn/cms/guides/getting-started
```

```json
{
  "ok": true,
  "kit": "sn/cms",
  "slug": "guides/getting-started",
  "frontmatter": { "title": "...", "tags": ["guide"] },
  "preamble": "<p>...</p>",
  "sections": { "overview": { "title": "...", "html": "...", "sections": {} } }
}
```

`agent_context` is **never** returned on this endpoint.

### Raw editor mode

```http
GET /cm/sn/cms/guides/getting-started?raw=1
```

Returns `{ frontmatter, markdown, hash }` for round-trip editing. `agent_context` is **included** in raw mode.

### Content tree

```http
GET /cm/sn/cms/_tree
```

Returns a hierarchical tree of slugs for one kit (for file-tree UIs).

### Folder → form mapping

```http
GET /cm/sn/cms/_meta?folder=guides
```

Uses `cms_metadata` in `kit.yaml`; falls back to `_default`. Response: `{ "ok": true, "form": "cms-guide" }` (empty string if unmapped).

Form field definitions for editors: `GET /fm/{kitDirName}/_def/{formName}` (still uses dot kit dir in the `fm` path, e.g. `sn.cms`).

---

## `/ct` — fast HTML rendering

Renders cached Markdown through a named kit template **without starting the Lua VM**. Frontmatter is converted to Go template data; the primary variable is `.post` (same shape as `sn.cms.get` in Lua).

### Route pattern

```http
GET /ct/{namespace}/{kit_name}/{template}/{slug…}
```

| Segment | Required | Notes |
|---------|----------|-------|
| `namespace`, `kit_name` | Yes | Slash form (`sn/cms`) |
| `template` | Yes | Basename of `tp/{template}.gohtml` — **no default** |
| `slug…` | Yes | Content path under `ct/` (may contain slashes) |

Missing template or unknown slug → **HTML error page** (embedded error templates), not JSON.

### Template data

```text
.post          → { frontmatter, preamble, sections, full_html, warnings, source_path }
.kit           → { namespace, kit_name, name }
.slug          → content slug string
```

Example template (`tp/render.gohtml`):

```html
<title>{{ index .post.frontmatter "title" }}</title>
<div class="content">{{ index .post "full_html" | safeHTML }}</div>
```

Use `safeHTML` only for harness-generated HTML (`preamble`, `sections.*.gohtml`, `full_html`), never for raw user input.

### Render cache

- Key: `sn.cms|render|guides/getting-started` (internal kit dir + template + slug).
- TTL: `cms_render_cache_ttl_sec` on the kit, else **5 minutes**.
- Response header: `X-Cache: HIT` or `MISS`.
- Invalidated when the underlying `ct/` file changes.

### Reverse proxy pattern

Expose a clean public URL while keeping the harness path explicit internally:

```text
Public:     https://my-site.com/guides/getting-started
Proxy to:   http://127.0.0.1:8080/ct/sn/cms/render/guides/getting-started
```

Caddy example:

```caddyfile
handle /guides/* {
  rewrite * /ct/sn/cms/render{path}
  reverse_proxy 127.0.0.1:8080
}
```

Adjust `rewrite` to match your template basename and slug layout.

---

## Kit pages (`/kt`) — YAML, Lua merge, and variables

Kit UI pages are defined under `pg/` and served at `/kt/{ns}/{name}/{page}`.

### Discovery rules

- One page per **basename** in `pg/`.
- `pg/home.yaml` + `pg/home.lua` → single page `home` (YAML parsed first, then Lua merge).
- `pg/home.yaml` only, or `pg/home.lua` only — both allowed.
- If both `home.yaml` and `home.json` existed, only one extension wins per basename (yaml + lua only today).

### Page contract

Every page must provide non-empty strings:

- `name` — page id and default template basename (`tp/{name}.gohtml`)
- `path` — HTTP path (may include kit prefix, e.g. `/kt/sn/cms/render`)
- `title` — human title

| Source | When validated |
|--------|----------------|
| YAML only | At kit load (discovery) |
| Lua only | At first render (after merge) |
| YAML + Lua | YAML must be valid if present; full contract after merge at render |

Contract failures on `/kt/...` return an **HTML error page** (same family as static file errors), not JSON.

### `pg/*.lua` merge

The merge script runs in the **page variable sandbox** (not a full flow): `page`, `ctx`, `sn.cms`, `sn.json`, and `ctx.db` when the kit has a database — but **no flow invocation**.

Patterns:

```lua
-- Mutate global page table, return nothing
page.title = "Dynamic " .. page.title
```

```lua
-- Return replacement table
return {
  name = "home",
  path = "/",
  title = "Home",
  hero = "welcome",
}
```

Top-level keys on the merged table (except reserved routing keys) become **template variables** alongside evaluated `variables:` snippets from YAML.

### Page `variables:` (YAML)

Legacy dynamic pages still use multiline Lua in `pg/*.yaml`:

```yaml
name: render
path: /kt/sn/cms/render
title: Post
variables:
  post: |
    local slug = ctx.kit.query.slug or ""
    if slug == "" then return nil end
    return sn.cms.get(slug)
```

Prefer **`/ct/...`** for public post pages when you do not need Lua; keep `/kt/...` for authenticated or highly dynamic views.

---

## Authentication and production

- CMS JSON routes follow the same harness auth model as the rest of the API (Bearer token in production). See [Configuration Guide](/configuration-guide).
- `/ct` HTML responses are typically **public** when mounted behind a site reverse proxy — restrict at the edge if content is non-public.
- `agent_context` is for AI/editor tooling in Lua and raw mode only; do not rely on its absence in Lua if untrusted code can run in flows.

---

## Operations checklist

### Enable CMS for a kit

1. Add `ct/` with at least one `.md` file.
2. Add `tp/` templates if you use `/ct` or kit pages.
3. Optionally set `cms_full_html: true` if templates need full-document HTML.
4. Restart harness or rely on file watcher for parse cache updates.

### Verify after deploy

```bash
# Harness healthy
curl -s http://127.0.0.1:8080/hl | jq .

# Content visible
curl -s http://127.0.0.1:8080/cm/sn/cms/hello-world | jq .

# HTML path
curl -s -D - http://127.0.0.1:8080/ct/sn/cms/render/hello-world | head
```

Integration SRE:

```bash
sentinel harness start -p ../SRE/test --daemon
curl -s http://127.0.0.1:8080/ct/sn/cms/render/guides/getting-started
```

### Clear caches

| Goal | Action |
|------|--------|
| Force full re-parse | Stop harness, remove `.sentinel/cms.db`, start harness |
| Force HTML refresh only | Wait for TTL, edit `ct/` file, or DELETE+recreate content |
| Per-kit TTL change | Set `cms_render_cache_ttl_sec` in `kit.yaml`, reload kit |

### Hot reload

- Saving `ct/**/*.md` updates the parse cache via the project watcher.
- `full_html` is **not** regenerated on hot reload when `cms_full_html` is true — only on cold start. Restart harness after bulk content imports if you depend on `full_html`.
- `/ct` render cache entries for the changed slug are invalidated automatically.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|----------------|-----|
| `CMS.UNAVAILABLE` | No SRE root or cache failed to open | Check harness logs; verify `.sentinel/cms.db` not locked by another process (`sentinel ps`) |
| `CMS.NOT_FOUND` | Slug typo or file not under `ct/` | `GET /cm` to list slugs; confirm path |
| `/ct` 404 HTML “template missing” | No `tp/{template}.gohtml` | Add template; template name in URL is required |
| `/ct` empty `post` | `cms_full_html: false` and template expects `full_html` | Enable flag and restart, or use `sections` / `preamble` |
| `/kt` HTML “page contract invalid” | Missing `name`/`path`/`title` after merge | Fix YAML or `pg/*.lua` return table |
| Stale public HTML | Render cache within TTL | Lower TTL, touch file, or wait |
| `cms.db` huge | Many kits/slugs | Normal; delete file to compact after cleanup |

---

## WordPress content API (optional)

When WordPress proxy is enabled, separate routes under `/cm/wp/...` talk to remote WordPress — not the git-native `ct/` CMS. Do not confuse with `/cm/sn/cms/...`.

---

## Design constraints (by intent)

| Constraint | Rationale |
|------------|-----------|
| No Lua in Markdown frontmatter | Predictable parse cost at scale |
| No default `/ct` template | Explicit routing; proxies stay unambiguous |
| No global layout in `kit.yaml` | Layout lives in `tp/*.gohtml` per site design |
| Slash kit paths in `/cm` and `/ct` | Matches `/kt/{ns}/{name}` mental model |
| Parse vs render cache split | JSON/API can update without storing HTML; `/ct` stays fast |

---

## Spec and code map

| Area | Location |
|------|----------|
| Parse + frontmatter | `internal/cms/` |
| Render cache | `internal/cms/render_cache.go` |
| HTTP handlers | `internal/api/cms_handlers.go`, `cms_write_handlers.go`, `ct_handlers.go` |
| Routes | `internal/api/gateway.go` |
| File watcher | `internal/orchestrator/project_watcher_cms.go` |
| Page merge | `internal/kit/discover.go`, `internal/templates/lua_executor.go` |
| Routes spec | `system-specs/api.yaml` → `cms:` |

When behavior changes, update this guide, `05-KIT-DEVELOPMENT.md` (CMS section), and `system-specs/api.yaml`.
