# sentinel-docs

Sentinel SRE serving the public Sentinel docs via the fcms plane. Staging: https://sn-docs.dwp.solutions (bilbo, harness :8290). Production: https://docs.ndx-sentinel.com (user-managed VM).

- Content lives in `sn.docs/ct/*.md` (frontmatter: `title`, `description`, required `type`, plus `tags` / `status`).
- `ct/index.md` is the fcms landing page. `ct/README.md` is the filename MAP. Do not generate over either.
- After `ct/` edits: `python3 tools/bundle_docs.py` (writes `notebooklm/` only — never into `ct/`).
- Templates: `sn.docs/tp/*.gohtml`; static assets: `sn.docs/pb/`.
- Do not edit `~/code/sentinel` from here. Do not run `sentinel` without `-p` at any parent directory.
- `.sentinel/` is machine-local, never commit it.
