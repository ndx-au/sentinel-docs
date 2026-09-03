---
title: "WordPress with Sentinel"
description: "This document describes the WordPress platform architecture for Sentinel, covering the central origin, preview rendering, and edge content delivery."
type: Guide
tags: [wordpress]
status: stable
---

# WordPress with Sentinel

This document describes the WordPress platform architecture for Sentinel, covering the central origin, preview rendering, and edge content delivery.

The intended boundary is:

- `sn.wp-central` is the only supported ingress for the managed WordPress stack
- operators use the normal WordPress admin UI for the initial install and editorial work
- Sentinel integrations use a dedicated WordPress user plus an Application Password
- the raw WordPress container is internal implementation detail, not the operator-facing entry point

## Three-Kit Architecture

The WordPress platform consists of three kits that work together:

| Kit | Runs on | Purpose |
|-----|---------|---------|
| `sn.wp-central` | Central harness | Manages the WordPress Docker stack, reverse proxy, change tracking, webhook delivery, and edge node registration |
| `sn.wp-preview` | Central harness | WYSIWYG preview rendering for editors; canonical template source for edge nodes |
| `sn.wp-edge` | Edge harness(es) | Public-facing content delivery from a local SQLite replica; receives incremental updates via webhooks |

The central harness runs both `sn.wp-central` and `sn.wp-preview`. Each edge deployment runs its own harness with `sn.wp-edge`. Content flows one way: WordPress to central to edge. Templates flow from preview (where they are developed) through the dispatch folder to edge nodes.

## Central Bootstrap

The following sections cover the local-development bootstrap path for a managed WordPress origin running behind Sentinel via `sn.wp-central`.

## Prerequisites

- Docker Desktop or a working Docker Engine on the local machine
- a Sentinel build with dev features enabled for local work
- an SRE initialized with `--wp-central`
- a vault passphrase configured if the local project encrypts the vault
- an S3-compatible bucket storage point configured for WordPress media publication

Example dev build:

```bash
go build -tags dev -o sentinel ./cmd/sentinel
```

## 1. Initialize a `wp-central` Project

Create a new SRE with the `wp-central` project profile:

```bash
sentinel sre init ./my-central --wp-central
```

This currently scaffolds:

- `sentinel.yaml` with a `wp_central` block
- `sn.wp-central/`
- `docker-compose.wp-central.yaml`

The generated compose file is for development. It currently uses floating `wordpress:latest` and `mariadb:latest` images.

## 2. Start Sentinel and the Dashboard

Start the local harness and dashboard:

```bash
sentinel harness start -p ./my-central --force-reset --wp-port 8800
```

Default ports:

- harness: `http://127.0.0.1:8080`
- dashboard: `http://127.0.0.1:9090`
- WordPress ingress: `http://127.0.0.1:8800`

The dedicated WordPress ingress port can be set in either place:

- `sentinel.yaml` via `wp_central.port`
- the CLI via `--wp-port`, which overrides `sentinel.yaml` for that run

## 3. Bring Up the Managed WordPress Stack

Use the dashboard Docker controls, or the CLI:

```bash
sentinel harness start -p ./my-central --compose-up wp-central
```

The development stack persists WordPress state under the SRE data tree:

- `./_data/wp-central/db`
- `./_data/wp-central/html`

These paths are intentionally not hidden. They are project-local runtime data, not kit source.

## 4. Complete the Initial WordPress Install

Use the dedicated Sentinel WordPress ingress, not the raw container port:

```text
http://127.0.0.1:8800/wp-admin/install.php
```

Do not use the naked WordPress container port as the primary operator path. Even in local development, the supported boundary is the Sentinel-managed WordPress ingress listener.

After installation, continue to access admin through:

```text
http://127.0.0.1:8800/wp-admin/
```

## 5. Create a Dedicated Integration User

Do not use the human admin account for Sentinel automation.

Create a dedicated user in WordPress, for example:

- username: `sentinel-sync`
- role: `Administrator` during local development

This user exists so Sentinel can use the REST API without depending on the operator's own login.

## 6. Generate an Application Password

For the dedicated integration user:

1. open the user profile page in WordPress admin
2. find the **Application Passwords** section
3. create a password such as `sentinel-wp-central-dev-pass`
4. copy the generated value immediately

Sentinel should use the Application Password, not the user's normal login password.

## 7. Store the Credentials in the Sentinel Vault

Store the WordPress integration credentials in the Sentinel vault so flows can retrieve them via `ctx.secret(...)`.

Recommended secret names:

- `wp_central_username`
- `wp_central_app_password`

Example:

```bash
sentinel secret set wp_central_username sentinel-sync -p ./my-central
sentinel secret set wp_central_app_password --interactive -p ./my-central
```

If you prefer stdin:

```bash
printf '%s' 'your application password here' | sentinel secret set wp_central_app_password --stdin -p ./my-central
```

Lua flows can then retrieve them with:

```lua
local user = ctx.secret("wp_central_username")
local pass = ctx.secret("wp_central_app_password")
```

Do not hardcode these values into `sentinel.yaml`, flow source, or git-tracked config files.

## 8. Bind a Dedicated Media Storage Point

`sn.wp-central` treats bucket-backed object storage as a standard prerequisite. WordPress media publication should target a reserved storage point, not `{sre}/_data`.

Create a storage point in the dashboard, then bind it in `sentinel.yaml`:

```yaml
wp_central:
  enabled: true
  port: 8800
  media_storage:
    storage_point_id: your-storage-point-id
```

Notes:

- the storage point ID is visible on the dashboard Storage page
- the bound point is marked with a small `WP` badge
- that reserved point should not be reused for unrelated backup or RAG selectors
- object storage is the intended home for media/binary publication; `_data/wp-central/*` is only for the managed WordPress runtime state

## 9. Verify the REST API Path

WordPress REST is currently expected to work through the Sentinel ingress. In local development, the site may expose REST routes using the fallback form:

```text
/index.php?rest_route=/wp/v2/...
```

That is acceptable for now. The important point is that requests go through `sn.wp-central`, not around it.

A quick smoke check with an Application Password:

```bash
curl --user 'sentinel-sync:APP_PASSWORD' \
  'http://127.0.0.1:8800/index.php?rest_route=/wp/v2/users/me'
```

If that succeeds, Sentinel has the credential shape it needs for local integration work.

## Operator Checklist

- initialize the SRE with `sentinel sre init --wp-central`
- start the harness and dashboard
- bring up the `wp-central` compose stack
- complete the first-run install at `/wp-admin/install.php`
- create a dedicated integration user
- generate an Application Password for that user
- store the username and Application Password in the Sentinel vault
- configure a dedicated S3-compatible storage point and bind its `storage_point_id` in `sentinel.yaml`
- keep using the dedicated `wp-central` ingress port for admin access

## Notes

- `WP_ENVIRONMENT_TYPE` is currently set to `local` in the dev compose template
- `_data/wp-central/*` should be backed up if the local instance matters
- vault backups only help if the vault passphrase is retained separately
- future `sn.wp-central` flows should read credentials from the vault rather than from ad hoc local files

---

## The `sn-wp` Mu-Plugin

The `sn.wp-central` kit includes a WordPress must-use plugin (`wp-plugin/sn-wp.php`) that is automatically loaded by WordPress. It provides four components:

### Change Tracker (`class-change-tracker.php`)

Hooks into WordPress post status transitions, term edits, and media changes to record events in a `wp_sn_wp_events` table. Each event receives a monotonically increasing sequence number used for cursor-based replication. Tracked event types:

- `post_published`, `post_updated`, `post_trashed`, `post_restored`, `post_deleted`
- `term_updated`, `term_deleted`
- `media_added`, `media_updated`, `media_deleted`

Only `post` and `page` post types are tracked. Revisions and autosaves are excluded.

### REST API (`class-rest-api.php`)

Registers custom endpoints under the `sn-wp/v1` namespace:

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/sn-wp/v1/events` | GET | `edit_posts` | Event replay feed with `since_seq` and `limit` params |
| `/sn-wp/v1/edge/register` | POST | `edit_posts` | Register an edge node with callback URL and lease TTL |
| `/sn-wp/v1/edge/heartbeat` | POST | `edit_posts` | Renew edge node lease and report last acknowledged sequence |
| `/sn-wp/v1/status` | GET | Public | Health check with event count, max sequence, and active node count |

Edge nodes register themselves and maintain leases. Expired or tombstoned nodes stop receiving webhook deliveries.

### Webhook Delivery (`class-webhook.php`)

When the change tracker records an event, the webhook system delivers an HMAC-SHA256 signed payload to all active edge nodes. The payload is the JSON-encoded event row, signed with the `sn_wp_webhook_secret` WordPress option. Headers include:

- `X-SN-Signature`: hex-encoded HMAC-SHA256 of the raw JSON body
- `X-SN-Node-ID`: the target edge node identifier

Delivery is fire-and-forget (`blocking: false`) with a 5-second timeout. Failed deliveries are logged but do not block WordPress.

### Preview URL Rewriting (`class-preview.php`)

Rewrites the WordPress Preview button URL to point to the `sn.wp-preview` kit. When `sn_wp_preview_url` is set, clicking Preview in the WordPress editor navigates to:

```
{sn_wp_preview_url}/kt/sn/wp-preview/pg/preview?p={post_id}&preview=true&nonce={nonce}
```

The nonce is generated per-post using `wp_create_nonce('sn_wp_preview_' . $post->ID)`.

## Webhook Secret Configuration

The webhook HMAC secret must be configured in two places:

1. **WordPress side**: Set the `sn_wp_webhook_secret` option via WP-CLI or the database:

   ```bash
   wp option update sn_wp_webhook_secret 'your-shared-secret' --path=./_data/wp-central/html
   ```

2. **Edge side**: Store the same secret in each edge node's Sentinel vault:

   ```bash
   sentinel secret set wp_webhook_secret 'your-shared-secret' -p ./my-edge
   ```

The edge `webhook_ingest` flow verifies every incoming payload by computing `HMAC-SHA256(body, wp_webhook_secret)` and comparing it to the `X-SN-Signature` header. Mismatched signatures are rejected.

## Preview URL Configuration

To connect the WordPress Preview button to Sentinel preview rendering:

1. Set the `sn_wp_preview_url` WordPress option to the base URL of the central harness:

   ```bash
   wp option update sn_wp_preview_url http://127.0.0.1:8080 --path=./_data/wp-central/html
   ```

2. Ensure the integration user has at least `edit_posts` capability (required for draft/autosave REST API access).

3. The preview page is served at `/kt/sn/wp-preview/pg/preview`. It fetches the latest autosave first, falling back to the draft with `context=edit`.

When `sn_wp_preview_url` is empty (the default), the WordPress Preview button uses its standard behavior.

## Template Provisioning Workflow

Templates are developed in `sn.wp-preview` and promoted to edge nodes through a dispatch folder:

1. **Develop** -- edit templates in `sn.wp-preview/tp/`, styles in `pb/`, and page definitions in `pg/`. Preview against live WordPress drafts and published content.

2. **Promote** -- run the `promote_templates` flow to copy renderable assets (`tp/`, `pb/`, `pg/`) to the dispatch folder at `_data/wp-edge-kit/` on the central SRE. This is the release gate.

3. **Distribute** -- edge nodes sync from the dispatch folder. Options:
   - **rsync/SSH**: configure `wp_edge_rsync_ssh_key` on edge nodes for automated pull
   - **Manual copy**: download from central and place into the edge kit directories

Only renderable surface files are promoted. Lua modules, `kit.yaml`, and flow definitions are not included in the dispatch.

## Edge Node Bootstrap

To bring up a new edge node:

1. **Initialize** the edge SRE:

   ```bash
   sentinel sre init ./my-edge --wp-edge
   ```

2. **Configure secrets** in the edge vault:

   ```bash
   sentinel secret set wp_central_origin http://your-central:8800 -p ./my-edge
   sentinel secret set wp_central_username sentinel-sync -p ./my-edge
   sentinel secret set wp_central_app_password --interactive -p ./my-edge
   sentinel secret set wp_webhook_secret --interactive -p ./my-edge
   ```

3. **Sync templates** from the central dispatch folder to the edge kit's `tp/`, `pb/`, and `pg/` directories.

4. **Start the harness**:

   ```bash
   sentinel harness start -p ./my-edge
   ```

5. **Run initial content import**:

   ```bash
   curl -X POST http://127.0.0.1:8080/fl/sn-wp-edge:full_sync/run
   ```

6. **Register with central** (optional, for webhook delivery): the edge node should register itself via the `/sn-wp/v1/edge/register` endpoint with its callback URL.

7. **Verify health**:

   ```bash
   curl -X POST http://127.0.0.1:8080/fl/sn-wp-edge:sync-health/run
   ```

After bootstrap, the edge node maintains itself:

- `webhook_ingest` processes incoming content changes in real time
- `reconcile` runs every 15 minutes to catch any missed webhooks
- Page rendering reads exclusively from the local SQLite replica

---

## Production Topology

A typical production deployment separates the WordPress admin origin from the public-facing edge:

```
Public Internet
  |
  +-- example.com ----------> CF Worker (Astro wp-edge)
  |                           Renders content at the edge
  |                           Fetches from api.example.com
  |
  +-- api.example.com ------> External reverse proxy (Traefik / Caddy)
        |                     Path-based routing:
        |                       /wp-admin/*   -> wp-central (port 8800)
        |                       /wp-json/*    -> wp-central (port 8800)
        |                       /wp-login.php -> wp-central (port 8800)
        |                       /wp-content/* -> wp-central (port 8800)
        |                       /sn/*         -> harness API (port 8080)
        |
        +-- wp-central harness (port 8800)
              +-- WordPress container (127.0.0.1:18080)
              +-- MariaDB container (internal)
```

**Content editors** access `https://api.example.com/wp-admin/` for writing and editorial work. The wp-central proxy handles forwarded headers so WordPress sees `https://api.example.com` as its home URL.

**Preview flow**: Editor clicks Preview in wp-admin, mu-plugin rewrites the URL to `https://example.com/post/slug?preview=true&p=42`, the CF Worker fetches the draft from `api.example.com` and renders it with the same templates used for published content.

**Custom harness endpoints** (SEO data, custom integrations, kit APIs) are exposed via the harness on port 8080 and grafted into the `api.example.com` URL space by the reverse proxy under a path prefix like `/sn/`. This avoids needing a separate subdomain for harness APIs.

### Reverse Proxy Path Routing

Both Traefik and Caddy can route different paths on the same domain to different backend ports. This means the WordPress proxy (port 8800) and the harness API (port 8080) share a single domain without conflict.

**Traefik example** (dynamic config):

```yaml
http:
  routers:
    wp-admin:
      rule: >-
        Host(`api.example.com`) && (
          PathPrefix(`/wp-admin`) ||
          PathPrefix(`/wp-json`) ||
          PathPrefix(`/wp-login`) ||
          PathPrefix(`/wp-content`) ||
          PathPrefix(`/wp-includes`)
        )
      service: wp-central-proxy
      tls:
        certResolver: letsencrypt

    harness-api:
      rule: "Host(`api.example.com`) && PathPrefix(`/sn`)"
      service: harness-api
      tls:
        certResolver: letsencrypt

  services:
    wp-central-proxy:
      loadBalancer:
        servers:
          - url: "http://harness-host:8800"

    harness-api:
      loadBalancer:
        servers:
          - url: "http://harness-host:8080"
```

**Caddy example** (Caddyfile):

```
api.example.com {
    handle_path /sn/* {
        reverse_proxy harness-host:8080
    }
    handle {
        reverse_proxy harness-host:8800
    }
}
```

For horizontal scaling, Traefik can round-robin across multiple wp-central instances if they share the same MariaDB. The harness proxy is stateless for WordPress traffic.

---

## Memory And Resource Sizing

### Component Memory Usage

| Component | Typical Memory | Notes |
|-----------|---------------|-------|
| Go harness | 30-50 MB | Lua VM pool, SQLite, HTTP server. Grows with concurrent flow executions |
| WordPress container | 80-150 MB | PHP-FPM workers. Each request ~20-30 MB. Default 5 workers |
| MariaDB container | 256-400 MB | InnoDB buffer pool (set to 256 MB in dev compose). Largest consumer |
| Docker daemon | 50-100 MB | Container management overhead |

### Sizing Recommendations

| Profile | Memory | Use case |
|---------|--------|----------|
| Minimum | 1 GB | Single low-traffic site. Tune MariaDB buffer pool down to 128 MB |
| Comfortable | 2 GB | Production single site with headroom for traffic spikes and flow executions |
| With active kits | 4 GB | AI flows, RAG connectors, HTTP integrations that buffer large responses |

### Tuning Notes

**PHP-FPM worker count** is the key WordPress variable. Each concurrent request to WordPress forks a PHP worker at 20-30 MB. For a headless setup where the only WordPress traffic is the CF Worker fetching content plus editors in wp-admin, 3-5 workers is sufficient. Cap it in the Docker environment:

```yaml
environment:
  PM_MAX_CHILDREN: 5
```

**InnoDB buffer pool** (`innodb_buffer_pool_size`) is the single biggest MariaDB tuning knob. The dev compose sets it at 256 MB. For a small site with under 1000 posts, 128 MB is adequate. For sites with heavy media, custom fields, or WooCommerce, keep it at 256 MB or higher.

**Lua VM pool** allocates memory per concurrent flow execution. Under normal operation with a few scheduled flows, this is negligible. If kits run AI connector flows that buffer large API responses, memory adds up — size accordingly.

---

## WordPress Plugin Compatibility

Running WordPress headless means there is no WordPress frontend. The theme is effectively unused — visitors never see WordPress-rendered pages. This has significant implications for plugin compatibility.

### The Rule

If a plugin's value is in **storing and managing data** (admin side), it works. If its value is in **rendering frontend output** (theme side), it is useless in this setup.

### Plugins That Break

| Category | Why | Examples |
|----------|-----|---------|
| Page builders | Render via WordPress theme. No theme = no output | Elementor, WPBakery, Beaver Builder, Divi |
| SEO plugins (frontend rendering) | Meta tag injection assumes WordPress renders `<head>` | Yoast (meta tags useless), RankMath (meta tags useless) |
| Caching plugins | Cache a frontend that does not exist. May interfere with REST API responses | WP Super Cache, W3 Total Cache, LiteSpeed Cache |
| Comment plugins | Display comments on the WordPress frontend. No frontend = nowhere to show them | Disqus, wpDiscuz |
| Frontend form plugins | Render forms via shortcodes in the WordPress theme | Contact Form 7, WPForms, Gravity Forms (admin still works) |
| Popup, slider, and widget plugins | Inject output into the WordPress theme | OptinMonster, Slider Revolution |
| Security plugins (firewall) | Firewall rules inspect WordPress page requests that no longer exist | Wordfence (firewall useless, login security still works) |
| Analytics (frontend) | Inject tracking scripts into WordPress `<head>` | MonsterInsights, Google Analytics plugins |

### Plugins That Work Fine

| Category | Why | Examples |
|----------|-----|---------|
| Custom fields | Data stored in the database, exposed via REST API | Advanced Custom Fields (ACF), Meta Box, Pods |
| Custom post types | REST API exposes them natively | CPT UI, Toolset Types |
| Media management | Uploads work normally, URLs accessible via REST API | EWWW Image Optimizer, Smush, Regenerate Thumbnails |
| WooCommerce (admin) | Product management works. Storefront needs Astro templates | WooCommerce (admin + REST API) |
| Multilingual | Translation data stored in database, queryable via API | WPML, Polylang (need API integration in templates) |
| Backup plugins | Operate on database and files, do not need a frontend | UpdraftPlus, BackWPup |
| User and role management | Admin-side only | Members, User Role Editor |
| Scheduled publishing | WordPress cron publishes the post, REST API serves it | Built-in WordPress scheduling |

### Plugins That Partially Work

**Yoast / RankMath**: SEO metadata (title, description, Open Graph tags, focus keywords) is stored in `wp_postmeta` and available via the REST API. The data is usable — but you must read those fields in your edge templates and render your own `<meta>` tags. The plugin's on-page analysis score is meaningless since it analyzes WordPress theme output that no longer exists.

A Sentinel kit (e.g., `sn.wp-yoast`) can query the MariaDB `wp_postmeta` table directly for Yoast fields (`_yoast_wpseo_title`, `_yoast_wpseo_metadesc`, `_yoast_wpseo_focuskw`, `_yoast_wpseo_opengraph-title`, etc.) and expose them via a harness API endpoint. The edge renderer then fetches SEO data alongside content.

**Redirection plugins**: They intercept WordPress requests. In a headless setup, redirects need to happen at the CF Worker level or in the reverse proxy (Traefik/Caddy rules), not in WordPress.

**Gravity Forms / WPForms (admin side)**: Form building and submission management in wp-admin works. Frontend rendering does not — form display on the public site must be built as Astro components that POST to your own endpoints or a third-party form service.

**WooCommerce**: Product management, order processing, and the REST API work fully. The storefront (product pages, cart, checkout) needs to be built as Astro templates that consume the WooCommerce REST API. This is a significant frontend effort but gives you complete control over the shopping experience.
