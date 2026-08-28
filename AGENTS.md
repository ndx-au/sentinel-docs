# sentinel-docs

Sentinel SRE serving the public Sentinel docs via the fcms plane. Staging: https://sn-docs.dwp.solutions (staging-host, harness :8290). Production: https://docs.ndx-sentinel.com (user-managed VM).

- Content lives in `sn.docs/ct/*.md` (frontmatter: `title`, `description`).
- Templates: `sn.docs/tp/*.gohtml`; static assets: `sn.docs/pb/`.
- Do not edit `~/code/sentinel` from here. Do not run `sentinel` without `-p` at any parent directory.
- `.sentinel/` is machine-local, never commit it.
