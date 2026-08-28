# sentinel-docs

Public documentation for Sentinel, implemented as a Sentinel SRE served through
the **fcms** plane (file CMS). Staging: **https://sn-docs.dwp.solutions**
(staging-host). Production: **https://docs.ndx-sentinel.com** (dedicated VM).

## Layout

```
sentinel.yaml          SRE root config (port 8290, default_kit: sn.docs)
sn.docs/
  kit.yaml             fcms kit (public, cms_full_html, 600s render cache)
  ct/                  Markdown source of truth — one .md per doc, frontmatter:
                       title, description. index.md is the landing page.
  ct/README.md         old-filename → slug mapping (MAP block, used by relink)
  tp/                  Go templates (docs.gohtml = render, home.gohtml = landing)
  pb/                  static assets (style.css, favicon.ico)
  pg/home.yaml         default-kit catch-all page at /
  fl/                  smoke tests (validated by `sentinel sre validate`)
tools/relink.py        rewrites old relative doc links → /slug links
```

## Run locally

```bash
sentinel harness start -p . -d --port 8290
curl http://127.0.0.1:8290/hl
# JSON:  /fcms , /fcms/sn/docs/<slug>
# HTML:  /fcms/render/sn/docs/docs/<slug>
# assets: /kt/sn/docs/pb/*
```

## Adding a doc

Add `sn.docs/ct/<slug>.md` with `title`/`description` frontmatter, add the slug
to the sidebar nav in `sn.docs/tp/docs.gohtml`, and link it from `index.md`.
`ct/` changes are picked up by the harness file watcher — no reload needed.
Changes to `kit.yaml`, `tp/`, or `pg/` require `POST /hl/kt/sn/docs/rl` (kit
reload) or a harness restart.

## Deployment (production VM)

The prod VM runs the same SRE repo. Required setup:

1. **Checkout**: clone `github.com/ndx-au/sentinel-docs` to the VM (polling
   target: `main` branch).
2. **Harness**: `sentinel harness start -p <repo> -d --port 8290`. The harness
   binds `0.0.0.0` — firewall the port to the reverse proxy only (on staging-host:
   UFW allows 172.17/172.18 docker bridges so the caddy container reaches the
   host process; replicate that pattern).
3. **public_url**: production overrides `public_url` in `sentinel.yaml` to
   `https://docs.ndx-sentinel.com` (or use an env/config override if the
   harness supports one — staging keeps the sn-docs value; do not commit the
   prod override to `main` if it would break staging, prefer per-host config).
4. **Reverse proxy** (Caddy or equivalent) on the VM:
   ```
   docs.ndx-sentinel.com {
       encode gzip
       handle /kt/sn/docs/pb/* {
           reverse_proxy 127.0.0.1:8290
       }
       handle {
           rewrite * /fcms/render/sn/docs/docs{path}
           reverse_proxy 127.0.0.1:8290
       }
   }
   ```
   Public URLs are clean slugs: `/getting-started` →
   `/fcms/render/sn/docs/docs/getting-started`. The JSON API (`/fcms/...`,
   `/cm/...`) is intentionally NOT routed publicly.
5. **Deploy model**: harness-native polling of `main` (a Sentinel trigger/flow
   inside this SRE, not crontab). On new `main`: pull, and the file watcher
   picks up `ct/` changes automatically; `kit.yaml`/`tp/`/`pg/` changes need a
   kit reload (`POST /hl/kt/sn/docs/rl`) or harness restart. Later: a GH CI
   workflow (proxmox runner) replaces dumb polling and conditionally issues the
   kit reload.
6. **main protection**: enable branch protection + PR workflow once prod is
   operational.

## Staging (staging-host) wiring

- Zone `sn-docs.dwp.solutions` → staging-host Tailscale IP, covered by the
  `*.dwp.solutions` wildcard cert.
- `the host reverse-proxy config`: `@sndocs host` handle → `host.docker.internal:8290`
  (same rewrite rules as the prod block above).
