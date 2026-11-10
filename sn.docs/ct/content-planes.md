---
title: "Content planes — fcms, ccms, wpcms"
description: "Sentinel content planes: fcms for files, ccms for collections, and wpcms for WordPress."
type: Guide
tags: [cms]
status: stable
---

<!-- ndx-ste-mode: description -->

# Content planes — fcms, ccms, wpcms

Sentinel orchestration works without a content plane.

When you publish content, select **one primary public plane** for each site origin. Do not use two primary planes on the same origin.

| Plane | Code | Truth store | Default surface |
|-------|------|-------------|-----------------|
| File CMS | **fcms** | Git Markdown in kit `ct/` | Harness `/fcms`, `/fcms/render` |
| Collection CMS | **ccms** | Postgres + Graphile | Graphile **:1880**. Editor on harness `/ccms/...`. Dashboard **Collections** |
| WordPress | **wpcms** | WP + MariaDB | Dedicated WP ingress (**8800** legacy default. Target convention **1800**) |
| Automation | (core) | Kits, vault, state | Harness **8080** |

Never call the whole product “CMS” without the plane name.

---

## Ports (dedicated, not merged)

| Service | Default host port |
|---------|-------------------|
| Harness API / automation | **8080** |
| Graphile (ccms reflective API) | **1880** (bind `127.0.0.1` by default) |
| wpcms ingress | **8800** (kept as runtime default this release. Target **1800** for new installs) |

Postgres for the Graphile data plane binds **localhost-only** by default (`127.0.0.1:15432` in the template). Do not put Graphile and WordPress on the same public port.

---

## fcms (file CMS)

- Source: kit `ct/**/*.md` (git is truth).
- Canonical routes: **`/fcms`**, **`/fcms/render`**.
- Legacy aliases (deprecation window): `/cm`, `/ct`.
- Cache: `.sentinel/cms.db` (name historical. Product language is **fcms**).
- Full guide: [17-SENTINEL-CMS.md](/sentinel-cms).
- Reference kit naming: prefer **fcms** in docs. Existing `sn.cms` remains valid with deprecation toward fcms vocabulary.

---

## ccms (collection CMS)

Absorbs Headgres collection-CMS value into the harness (one binary).

### Layout (per kit)

```text
{ns}.{name}/
  kit.yaml            # optional ccms_theme: <theme-name>
  dd/                 # ordered SQL migrations (lexicographic)
    001_*.sql
  collections/        # identity, publication, GraphQL overrides
    pages.yaml
  forms/
    draft/*.md        # not shippable
    pub/*.md          # MD + YAML frontmatter; prefer collection: name
                      # (skill twins `*.md.md` are ignored by form discovery)
  themes/<name>/      # optional XSLT themes (ccms.list/detail/form/saved)
  tp/                 # optional legacy gohtml white-label
  fl/                 # OPTIONAL after-save plugins only
```

### Collection descriptor

```yaml
name: pages
title: Pages
source:
  schema: public
  table: pages
keys:
  - name: id
    type: bigint
fields:
  - name: title
    column: title
    expose: public
  - name: published
    column: published
    expose: editor
publication:
  public: false          # true enables anonymous /ccms/.../collections/...
  row_policy: published
```

`forms/pub` means shippable form, **not** anonymous access. Public browse requires
`publication.public: true`, an enabled kit, and `data_plane.public_graphile_url`.

### Form frontmatter

```yaml
name: pages
collection: pages       # preferred; binds to collections/pages.yaml
table: pages            # legacy adapter when collection: is absent
schema: public
title: Pages
template: form.gohtml   # optional kit tp/ editor
list_template: list.gohtml  # optional kit tp/ list
fields:
  - column: slug
    type: text
    required: true
```

### Themes

- Kit setting `ccms_theme` (separate from fcms `cms_theme`).
- Manifest slots: `ccms.list`, `ccms.detail`, `ccms.form`, `ccms.saved`.
- Presentation XML is internal (`urn:ndx:sentinel:ccms:1`); not a public XML API.
- An explicit broken theme fails visibly; it does not fall back to an unrelated layout.

### Writes and validation

- Editor submit: harness → **Graphile HTTP** (no superuser SQL bypass).
- Public reads use **`public_graphile_url` only** (never the editor/owner peer).
- `sentinel ccms validate` — L0 structure + L1 live catalog.
- `sentinel ccms migrate` — conscious apply of `dd/*.sql` (never on harness start / kit install).
- Production: **dump/backup before migrate**.

### Data plane compose

Embedded template: `graphile-dataplane` (`internal/static/docker-templates/graphile-dataplane.yaml`).

The template uses **`graphile/postgraphile:4`** (PostGraphile v4) with `--simple-collections both`. Postgres binds to `127.0.0.1:15432` by default. Graphile binds to `127.0.0.1:1880`. Both bindings allow local access only.

The template uses Postgres host port **15432** by default.

If that port is in use, set `SENTINEL_CCMS_PG_HOST_PORT` in Compose. Point `data_plane.database_url` at the same host port.

Graphile stays on **1880** unless you override `SENTINEL_GRAPHILE_PORT`.

```yaml
# sentinel.yaml
data_plane:
  enabled: true
  graphile_port: 1880
  graphile_url: http://127.0.0.1:1880
  public_graphile_url: http://127.0.0.1:1881   # scoped anonymous-read peer
  database_url: postgres://OWNER:ENCODED_PASSWORD@DB_HOST:5432/CCMS_DB # migrate/catalog only; prefer env
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

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/ccms/status` | harness | Data plane + migrations + form count |
| GET | `/ccms/forms` | harness | Live pub form catalog |
| GET/POST | `/ccms/{ns}/{name}/forms/{form}` | harness | Editor render / Graphile submit |
| GET | `/ccms/{ns}/{name}/forms/{form}/list` | harness | Editor list surface |
| GET | `/ccms/{ns}/{name}/collections/{collection}` | anonymous if published | Public list HTML |
| GET | `/ccms/{ns}/{name}/collections/{collection}/{key}` | anonymous if published | Public detail HTML |

### Dashboard

**Collections** (sidebar → `/collections`) replaces Headgres-studio. It provides plane descriptions, data plane status, migration lists, and a catalog of public forms. Catalog links currently open harness editors at the attached origin; the dashboard session is not forwarded. Dedicated BFF editor routes are deferred; see [CCMS XML themes](/ccms-xml-themes) for the verified scope and remaining contract work.

### Lua

Default submit is **zero Lua**. Collection form submit does not invoke kit flows. Optional after-save Lua plugins are out of scope for this MVP (re-introduce only when a real kit needs them, with skill twins).

### After migrate: restart Graphile

The data plane uses PostGraphile **without** `--watch`. After new migrations, `sentinel ccms migrate` **auto-restarts** the `graphile` service.

If the restart fails, use:

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
- fcms HTML (`/fcms/render` or legacy `/ct`) often sits behind CDN. Graphile is an API peer, not a static site.

---

## CLI quick reference

```bash
sentinel ccms status -p ./sre
sentinel ccms migrate -p ./sre
sentinel ccms validate -p ./sre
sentinel ccms install-refkit -p ./sre
```

Related: [Kit Development](/kit-development), [CLI Reference](/cli-reference), [Harness routes](/harness-http-routes), [WordPress](/wordpress).
