---
title: "The `.sentinel/` Directory"
description: "Machine-local harness state for one SRE. Gitignored (see repo .gitignore)."
---

# The `.sentinel/` Directory

Machine-local harness state for one SRE. **Gitignored** (see repo `.gitignore`). Do not commit secrets, databases, or uploads.

Paths below assume default `data_dir: ".sentinel"` in config (see `system-specs/config.yaml`). Override with `SENTINEL_DATA_DIR` or `data_dir` in `.sentinel/config.json` — all `{data_dir}/…` paths move with it.

**Separate from SRE `.sentinel/`:** the dashboard CLI also uses `~/.sentinel/dashboard.db` (and related keys) for operator-console metadata when not scoped to a project attach path.

---

## Layout (default)

```
{sre-root}/.sentinel/
  config.json              # Harness infra config (required)
  state.db                 # Harness state SQLite (+ optional SQLCipher)
  vault.db                 # Secrets SQLite (created when vault passphrase set)
  cms.db                   # Markdown parse cache (bbolt) — rename to md-cache.db proposed
  harness-{port}.pid       # Daemon PID (per API port)
  marketplace-instance.json
  crash/                   # Safety / crash artifacts
  certs/                   # TLS material (if tls.enabled)
  pub-keys/                # Dashboard Ed25519 public keys for /hl auth
  git-deploy-key           # Optional deploy key material
  git-keys/                # Additional git SSH keys
  docker-templates/        # Seeded compose templates (from embedded assets)
  archive/                 # Rotated DB archives (logging.retention)
  backups/                 # Backup manager artifact retention
  data/
    {ns}.{name}.db         # Per-kit SQLite (sn.db)
    pg_connections.json    # Postgres pool registry (URLs in vault)
    uploads/               # Form file uploads
  cache/
    responses/             # Form static response cache
```

Repo root may also contain **`storage-points.local.json`** (gitignored) — S3 endpoint definitions for backups/CMS, not inside `.sentinel/`.

---

## File reference

| Path | Engine / format | Created by | Purpose | Depends on | Restore / notes |
|------|-----------------|------------|---------|------------|-----------------|
| **config.json** | JSON | `sentinel sre init`, first harness start | `api.port`, tokens, TLS, logging, marketplace, `data_dir`, websocket, rate limits | Harness, dashboard (read/write some keys) | Back up manually; no auto-rebuild. Wrong edit can block startup. |
| **state.db** | SQLite + WAL; optional **SQLCipher** | `init`, harness start | Executions, logs index, triggers metadata, backup plans/runs, RAG tables (`sentinel_rag_*`), storage point registry rows, etc. | Core harness, backup manager, RAG | `/bk` file backup; `encrypt_db` needs passphrase. **Do not Litestream** (sn2 policy). |
| **vault.db** | SQLite + WAL; **AES-256-GCM values** | `init` (if passphrase), first secret write | Encrypted secrets for flows, Postgres URLs, etc. | Vault API `/sc`, `ctx.secret`, pgmanager | File backup; wrong passphrase = empty DB appearance. Not SQLCipher file encryption. |
| **cms.db** | **bbolt** | `init`, harness start (`OpenContentCache`) | Parsed markdown cache for kits’ `md/` / CMS API — **not** a full CMS product | `internal/cms` builder, watcher, `/cm` handlers, forms/pages using CMS vars | Safe to delete → cold rebuild from `md/` on next start. Misnamed; **proposed: `md-cache.db`**. |
| **harness-{port}.pid** | text | `sentinel harness start --daemon` | CLI/service discovery (`sentinel ps`, stop) | Process management only | Regenerated; safe to remove if process dead. |
| **marketplace-instance.json** | JSON | First marketplace / phone-home use | Stable Ed25519 instance identity for SKM | `internal/marketplace` | Do not delete casually if licensed instance bound to ID. |
| **crash/** | files | Safety subsystem on panic | Last-known crash context for debugging | `internal/safety` | Optional retention cleanup. |
| **certs/** | PEM | TLS enable / `sentinel` PKI helpers | CA + server certs for HTTPS harness | TLS listeners | Regenerable; protect private keys. |
| **pub-keys/** | PEM/text | Dashboard key registration | Verify dashboard `X-Sn-Sig` to harness | Dashboard attach | Re-register from dashboard if lost. |
| **git-deploy-key** | SSH private key | Git sync setup | Deploy key for `sentinel.yaml` git settings | `internal/git` | Regenerate via git tooling; permissions 0600. |
| **git-keys/** | SSH keys | Optional multi-key git | Extra git remotes | Git subsystem | Same as deploy key. |
| **docker-templates/** | YAML/files | Dashboard seed on attach | Local copies of embedded Docker stacks | Docker handlers | Safe to re-seed from harness. |
| **archive/** | `.db` snapshots | Log retention / rotation config | Archived DB copies per `logging.retention` | Config `archive_path` | Optional git sync if `include_backups` in sentinel.yaml git settings. |
| **backups/** | tar.gz, dumps, etc. | Backup manager runs | Local retention before optional upload to storage points | `/bk` API, cron plans | Can re-download from object storage if uploaded. |
| **data/{ns}.{name}.db** | SQLite + WAL | Kit first DB use / schema apply | Kit-isolated `sn.db.*` data | Kit flows, `KitDatabaseManager` | Kit backup via `/bk` or care plans; **Litestream candidate (sn2, edge only)**. |
| **data/pg_connections.json** | JSON | Dashboard / API add connection | Names + vault secret refs for Postgres pools | `ctx.pg`, pgmanager | Recreate from dashboard; secrets in vault. |
| **data/uploads/** | binary | Form submissions | Uploaded files (`fm.{uuid}…`) | Forms system | Orphan risk if DB rows deleted without cleanup. |
| **cache/responses/** | files | Form static cache | Cached form responses (TTL) | Forms `static-cache-ttl` | Safe to purge; regenerates. |

---

## `cms.db` vs future flat-file CMS

Today **`cms.db` is only a markdown parse cache** (bbolt buckets: kit → slug → JSON `CacheEntry`). Source of truth remains git-tracked `md/` (and `ct/` for content trees). The harness rebuilds cache via `BuildCache` on startup and invalidates on file watch.

A future **flat-file CMS** (fast, git-native pages) would be a separate concern:

- Could reduce reliance on this cache or replace it with a different index filename.
- Renaming to **`md-cache.db`** clarifies ops/backups and avoids implying “CMS database” stores authoritative content.

---

## Renaming `cms.db` → `md-cache.db`

**Effort: small–medium** (~15–25 touch points, one migration hook).

| Area | Change |
|------|--------|
| `internal/app/app.go` | Open `md-cache.db`; on start, `rename` `cms.db` → `md-cache.db` if old exists |
| `cmd/sentinel/commands/init.go` | Create `md-cache.db` |
| Dashboard backups UI / `backups.js` | Preset path |
| Docs, `sn2/`, `system-specs/file-structure.yaml` | Text |
| Tests | Temp paths in `cms` package tests |

No on-disk format change (still bbolt). Existing installs need **one-time migration** on harness start.

---

## Documentation gaps (historical)

| Source | Coverage |
|--------|----------|
| `docs/00-GETTING-STARTED.md` | Partial tree; labels `cms.db` as “CMS cache/index” |
| `system-specs/file-structure.yaml` | Incomplete `.sentinel/` (missing cms.db, pid pattern, marketplace, crash, etc.) |
| `sn2/persistence-tiers.md` | Tier summary only |
| **This doc** | Intended inventory — update when adding new artifacts |

When adding a new file under `.sentinel/`, update this document and `system-specs/file-structure.yaml` in the same change.

---

## Related

- [04-CONFIGURATION-GUIDE.md](/configuration-guide) — `config.json` schema
- [11-STORAGE.md](/storage) — storage points and backups
- [sn2/persistence-tiers.md](https://github.com/ndx-au/sentinel/blob/main/sn2/persistence-tiers.md) — SQLCipher / Litestream policy
- `.claude/skills/sn-go-security/SKILL.md` — vault vs state encryption
