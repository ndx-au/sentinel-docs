# sn.docs — Sentinel Docs kit

fcms kit serving the public Sentinel documentation.

- `ct/` — Markdown source of truth (frontmatter: `title`, `description`)
- `tp/` — Go templates for `/fcms/render`
- `pb/` — static assets (CSS, favicon)
- `pg/` — kit pages (`home` landing at `/`)

## Compatibility Matrix

| Sentinel version | Compatibility |
|------------------|---------------|
| pre-ccms-headgres-absorption (2026-07+) | ✓ fcms plane, canonical `/fcms` routes |
