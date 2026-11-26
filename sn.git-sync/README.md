# sn.git-sync

Runs a scheduled `git sync` on this SRE every 5 minutes, **gated to the production VM** via a machine-local Sentinel vault secret (`prod_git_sync_enabled`).

Because `.sentinel/vault.db` is machine-local and gitignored, this works identically whether the host runs `sndev` or a release binary, and never triggers on developer or staging checkouts.

## Compatibility Matrix

| Component | Requirement | Notes |
|---|---|---|
| Sentinel harness | `>= 0.3.0` (or `sndev`) | Uses `cron()`, `sn.http`, `sn.json`, `sn.db`, `ctx.secret` |
| Vault | Initialized on production VM | Gate secret lives in `.sentinel/vault.db` |
| Git SSH / remote | Configured on production VM | Used by harness `POST /git/sync` or `POST /git/pull` |

## Vault Secret Inventory

Configure these on the **production VM only** (do not set `prod_git_sync_enabled` on dev or staging):

| Secret Key | Required | Default | Purpose |
|---|---|---|---|
| `prod_git_sync_enabled` | Yes (on prod) | *(unset = disabled)* | Set to `true` to enable the 5-minute sync on this host |
| `prod_git_sync_mode` | No | `sync` | `sync` (`POST /git/sync`) or `pull` (`POST /git/pull`) |
| `prod_harness_url` | No | `http://127.0.0.1:8290` | Local harness base URL |
| `prod_harness_token` | If auth enabled | *(none)* | Bearer token for authenticated harness API calls |
| `prod_reload_kit` | No | `sn/docs` | Kit path (`{ns}/{name}`) reloaded via `POST /hl/kt/{ns}/{name}/rl` when `HEAD` changes (`none` to disable) |

## Enable on the Production VM

```bash
sentinel sre secret set prod_git_sync_enabled true -p /path/to/sentinel-docs
# Optional — if the production harness requires Bearer auth:
sentinel sre secret set prod_harness_token YOUR_API_TOKEN -p /path/to/sentinel-docs
# Optional — if you only want pull (never push) on the prod VM:
sentinel sre secret set prod_git_sync_mode pull -p /path/to/sentinel-docs
```

## Disable / Rollback

```bash
sentinel sre secret set prod_git_sync_enabled false -p /path/to/sentinel-docs
# Or disable the kit immediately via API:
curl -sS -X POST http://127.0.0.1:8290/hl/kt/sn/git-sync/off
```
