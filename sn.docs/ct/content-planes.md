---
title: "Content planes — fcms, ccms, wpcms"
description: "Sentinel is pluralistic: orchestration always works without a content plane. When you publish content, pick one primary public plane per site origin (dual-primary on the same origin is unsupported)."
type: Guide
tags: [cms]
status: stable
---

# Content planes — fcms, ccms, wpcms

Sentinel is **pluralistic**: orchestration always works without a content plane. When you publish content, pick **one primary public plane** per site origin (dual-primary on the same origin is unsupported).

| Plane | Code | Truth store | Default surface |
|-------|------|-------------|-----------------|
| File CMS | **fcms** | Git Markdown in kit `ct/` | Harness `/fcms`, `/fcms/render` |
| Collection CMS | **ccms** | Postgres + Graphile | Graphile **:1880**; editor on harness `/ccms/...`; dashboard **Collections** |
| WordPress | **wpcms** | WP + MariaDB | Dedicated WP ingress (**8800** legacy default; target convention **1800**) |
| Automation | (core) | Kits, vault, state | Harness **8080** |

Never call the whole product “CMS” without the plane name.

---

## Ports (dedicated, not merged)

| Service | Default host port |
|---------|-------------------|
| Harness API / automation | **8080** |
| Graphile (ccms reflective API) | **1880** (bind `127.0.0.1` by default) |
| wpcms ingress | **8800** (kept as runtime default this release; target **1800** for new installs) |

Postgres for the Graphile data plane binds **localhost-only** by default (`127.0.0.1:15432` in the template). Do not put Graphile and WordPress on the same public port.

---

## fcms (file CMS)

- Source: kit `ct/**/*.md` (git is truth).
- Canonical routes: **`/fcms`**, **`/fcms/render`**.
- Legacy aliases (deprecation window): `/cm`, `/ct`.
- Cache: `.sentinel/cms.db` (name historical; product language is **fcms**).
- Full guide: [17-SENTINEL-CMS.md](/sentinel-cms).
- Reference kit naming: prefer **fcms** in docs; existing `sn.cms` remains valid with deprecation toward fcms vocabulary.

---

## ccms (collection CMS)

Absorbs Headgres collection-CMS value into the harness (one binary).

### Layout (per kit)

```text
{ns}.{name}/
  kit.yaml
  dd/                 # ordered SQL migrations (lexicographic)
    001_*.sql
  forms/
    draft/*.md        # not shippable
    pub/*.md          # MD + YAML frontmatter → schema/table/columns
                      # (skill twins `*.md.md` are ignored by form discovery)
  tp/                 # optional gohtml white-label
  fl/                 # OPTIONAL after-save plugins only
```

### Form frontmatter

```yaml
name: pages
table: pages
schema: public
title: Pages
template: form.gohtml   # optional kit tp/
fields:
  - column: slug
    type: text
    required: true
```

### Writes and validation

- Editor submit: harness → **Graphile HTTP** (no superuser SQL bypass).
- `sentinel ccms validate` — L0 structure + L1 live catalog.
- `sentinel ccms migrate` — conscious apply of `dd/*.sql` (never on harness start / kit install).
- Production: **dump/backup before migrate**.

### Data plane compose

Embedded template: `graphile-dataplane` (`internal/static/docker-templates/graphile-dataplane.yaml`).

Image pin: **`graphile/postgraphile:4`** (PostGraphile v4) with `--simple-collections both` and **localhost-only** host binds for Postgres (`127.0.0.1:15432` by default) and Graphile (`127.0.0.1:1880`).

**Port conflicts:** template default Postgres host port is **15432**. If that port is already taken (e.g. another local Postgres such as workhours on bilbo), set `SENTINEL_CCMS_PG_HOST_PORT` (compose) and point `data_plane.database_url` at the same host port. Graphile stays on **1880** unless you override `SENTINEL_GRAPHILE_PORT`.

```yaml
# sentinel.yaml
data_plane:
  enabled: true
  graphile_port: 1880
  database_url: postgres://sentinel:sentinel@127.0.0.1:15432/sentinel_ccms
```

```bash
# If 15432 is busy:
#   export SENTINEL_CCMS_PG_HOST_PORT=25435
#   # and use …@127.0.0.1:25435/… in data_plane.database_url

# seed compose stub, then:
docker compose -f docker-compose.dataplane.yaml up -d
sentinel ccms migrate -p ./sre   # auto-restarts Graphile when migrations applied
sentinel ccms validate -p ./sre
sentinel ccms status -p ./sre
sentinel ccms install-refkit -p ./sre   # sn.ccms-pages-posts
```

### HTTP

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ccms/status` | Data plane + migrations + form count |
| GET | `/ccms/forms` | Live pub form catalog |
| GET/POST | `/ccms/{ns}/{name}/forms/{form}` | Editor render / Graphile submit |
| GET | `/ccms/{ns}/{name}/forms/{form}/list` | Minimal list surface |

### Dashboard

**Collections** (sidebar → `/collections`) is the Headgres-studio successor: plane copy, live data-plane status, migration lists, and a pub forms catalog with deep links to harness editors. Not a second studio binary.

### Lua

Default submit is **zero Lua**. Collection form submit does not invoke kit flows. Optional after-save Lua plugins are out of scope for this MVP (re-introduce only when a real kit needs them, with skill twins).

### After migrate: restart Graphile

The data-plane compose pins PostGraphile **without** `--watch`. `sentinel ccms migrate` **auto-restarts** the `graphile` compose service when new migrations were applied. If auto-restart fails, use:

```bash
docker compose -f docker-compose.dataplane.yaml restart graphile
```

---

## wpcms

Unchanged product plane. Dedicated ingress only. See [14-WORDPRESS.md](/wordpress). Graphile is not the WP API.

---

## Reverse proxy notes

- Terminate TLS for harness, Graphile (`:1880`), and WP ingress as **separate** upstreams when exposing publicly.
- Prefer IP allowlists per port rather than path-multiplexing Graphile under the harness host for MVP.
- fcms HTML (`/fcms/render` or legacy `/ct`) often sits behind CDN; Graphile is an API peer, not a static site.

---

## CLI quick reference

```bash
sentinel ccms status -p ./sre
sentinel ccms migrate -p ./sre
sentinel ccms validate -p ./sre
sentinel ccms install-refkit -p ./sre
```

Related: [Kit Development](/kit-development), [CLI Reference](/cli-reference), [Harness routes](/harness-http-routes), [WordPress](/wordpress).
