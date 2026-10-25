<!-- ndx-ste-mode: description -->

# sentinel-docs

This repository contains the public Sentinel documentation.
A Sentinel SRE serves it through the **fcms** plane (file CMS).
Staging uses **https://sn-docs.dwp.solutions**.
Production uses **https://docs.ndx-sentinel.com** on a dedicated VM.

## Layout

```
sentinel.yaml          SRE root config (port 8290, default_kit: sn.docs)
sn.docs/
  kit.yaml             fcms kit (public, cms_full_html, 600s render cache)
  ct/                  Markdown source of truth — one .md per doc, frontmatter:
                       title, description, type, tags, status.
                       index.md is the public landing page (do not overwrite).
  ct/README.md         old-filename → slug mapping (MAP block, used by relink)
  tp/                  Go templates (docs.gohtml = render, home.gohtml = landing)
  pb/                  static assets (style.css, favicon.ico)
  pg/home.yaml         default-kit catch-all page at /
  fl/                  smoke tests (validated by `sentinel sre validate`)
tools/relink.py        rewrites old relative doc links → /slug links
tools/bundle_docs.py   OKF / NotebookLM sidecar (writes notebooklm/ only)
notebooklm/            generated index.md + sentinel-docs.md — not fcms content
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

1. Create `sn.docs/ct/<slug>.md`.
2. Add `title`, `description`, and the required OKF `type`.
3. Select `Overview`, `Guide`, `Reference`, or `Playbook` for the type.
4. Add `tags` and `status`.
5. Add the slug to the sidebar in `sn.docs/tp/docs.gohtml`.
6. Link the document from `index.md`.
7. Regenerate the NotebookLM bundle:

```bash
python3 tools/bundle_docs.py
```

The script writes `notebooklm/index.md` and `notebooklm/sentinel-docs.md`.
The public homepage is `ct/index.md`.

Never write generated output into `ct/`.

The harness file watcher detects `ct/` changes without a reload.
Changes to `kit.yaml`, `tp/`, or `pg/` need a kit reload or harness restart.
The kit reload endpoint is `POST /hl/kt/sn/docs/rl`.

## Deployment (production VM)

The production VM runs the same SRE repository.

1. **Checkout**: Clone `github.com/ndx-au/sentinel-docs` to the VM. Poll the `main` branch.
2. **Harness**: Start `sentinel harness start -p <repo> -d --port 8290`.
   The harness binds `0.0.0.0`.
   Restrict the port so only the host reverse proxy can reach it.
   For a container proxy, permit its bridge network to reach the host process.
3. **public_url**: Set `public_url` in the production `sentinel.yaml` to `https://docs.ndx-sentinel.com`.
   Keep the staging value separate through configuration for each host.
   If the harness supports an environment or configuration override, you can use that override.
   If a production override breaks staging, do not commit it to `main`.
4. **Reverse proxy**: Configure Caddy or an equivalent reverse proxy on the VM:

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

   Public requests use clean slugs.
   The reverse proxy maps `/getting-started` to `/fcms/render/sn/docs/docs/getting-started`.
   It does not expose the JSON API (`/fcms/...`, `/cm/...`).
5. **Deploy model**: Use a Sentinel trigger and flow in this SRE to poll `main`.
   After new commits, pull `main`.
   The file watcher detects `ct/` changes.
   After `kit.yaml`/`tp/`/`pg/` changes, reload the kit with `POST /hl/kt/sn/docs/rl` or restart the harness.
   A future CI workflow can replace polling and request reloads when necessary.
6. **main protection**: After production is operational, enable branch protection and a PR workflow.

## Staging wiring

1. Point `sn-docs.dwp.solutions` at the staging host behind a private reverse proxy.
2. Configure TLS for that zone.
3. Forward requests to `127.0.0.1:8290` or the equivalent Docker host gateway.
4. Use the production rewrite rules above.
