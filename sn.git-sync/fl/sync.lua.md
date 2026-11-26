# skill twin: sn.git-sync/fl/sync.lua

Scheduled 5-minute flow (`cron("*/5 * * * *")`) that synchronizes the SRE git repository via the local harness `/git/sync` (or `/git/pull`) endpoint **only** when the machine-local vault secret `prod_git_sync_enabled` is `"true"`.

Design decisions:
- Fail-closed production gate using `.sentinel/vault.db` so dev/staging hosts never run git sync even when running `sndev`, and no internal hostnames are stored in this public repo.
- Owner-fenced `sn.db` `job_leases` row prevents overlapping runs across 5-minute ticks; `cleanup()` releases only if `lease_held` is true and `owner_exec_id` matches `ctx.execution_id`.
- Reloads `sn/docs` (configurable via `prod_reload_kit`) automatically when `HEAD` changes.
