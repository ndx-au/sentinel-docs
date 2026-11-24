---
name: sre-example-kit-workflow
description: >-
  <Third-person description of the procedural SRE workflow this skill builds or
  operates using a Sentinel kit. State exact triggers: authoring/updating the kit,
  configuring triggers/secrets, validating in staging, and promoting safely.>
---

# <Kit Workflow Title> (`sre-<name>`)

<One-sentence summary of the procedural task encapsulated as a Sentinel kit.>

## Kit Architecture

Target kit directory: `{ns}.{name}/` (Canonical flow path: `{ns}.{name}/<flow>`; legacy colon ID: `{ns}-{name}:<flow>`).

```text
{ns}.{name}/
├── kit.yaml                 # Kit manifest
├── fl/
│   ├── <main-flow>.lua      # Primary procedural flow (Pattern A lifecycle hooks)
│   └── <main-flow>_test.lua # Unit tests using sn.test.*
├── cn/                      # Optional: external API connectors (sn.cn.*)
└── md/                      # Optional: shared pure-Lua helpers (sn.md.*)
```

> **Note:** The harness auto-spawns skill twin companions (`*.lua.md`, `kit.yaml.md`) alongside code files to store per-file SRE context.

## Concurrency, Idempotency & Overlap Policy

- **Idempotency key (branch by trigger type):**
  - Webhooks / events / manual: require and validate `<provider event ID or operation_id>` (never fall back to `ctx.execution_id`).
  - Cron: derive logical tick key from `params.trigger_id` and `params.scheduled_at`.
  - Claim atomically in `sn.db` with classified states (`processing` → `completed` / `failed_retryable` / `failed_terminal` / `unknown_outcome`), bounded `attempts`, and verify `rows_affected == 1` on authoritative completion; propagate the same key as the downstream `Idempotency-Key`.
- **Schedule overlap policy (cron):** Sentinel's cron wrapper dispatches `ExecuteFlow` asynchronously, so slow flows can overlap across ticks unless the flow enforces exclusion itself. Choose and implement:
  - `skip`: owner-fenced atomic lease row in `sn.db` (`local lease_held = false`, set only on `rows_affected == 1`, bound work inside `lease_until` or renew with `owner_exec_id`, and release in `cleanup()` **only** when `lease_held` is true AND `WHERE job_key = ? AND owner_exec_id = ?`),
  - `queue`: persistent work table drained by a single lease-holding consumer, or
  - `parallel`: per-item atomic claims in `sn.db`.

## Vault Secret Inventory

Configure these secrets via `sentinel sre secret set <key> -p <sre>` (never hardcode in Lua or YAML):

| Secret Key | Used By | Purpose |
|---|---|---|
| `<example_secret>` | `fl/<main-flow>.lua` | <Brief purpose> |

## Procedure

### 1. Stage in an Isolated Test SRE (Never Edit Live Triggers In-Place)

Hot-reload and kit reloads immediately register `cron`, `webhook`, and `event` triggers. Always author and test trigger-bearing changes in a separate staging/test SRE using test vault credentials and harmless destinations.

- Check if `{ns}.{name}/` already exists in `<test-sre>` (MCP `kits_list` or `ls`).
- If new, scaffold via CLI or MCP `scaffold_create`:
  ```bash
  sentinel sre kit new {ns}.{name} --desc "<description>" -p <test-sre>
  ```

### 2. Implement Flows, Connectors & Triggers

- Keep orchestration in `fl/*.lua`, external service calls in `cn/*.lua`, and pure helpers in `md/*.lua`.
- Declare triggers (`cron(...)`, `webhook(...)`, `event(...)`) in the top-level `triggers = { ... }` table of the flow.
- Use `setup()`, `main(params)`, and `cleanup()` (required) plus optional `failed()` / `timeout()` lifecycle hooks for triggered/manual flows.
- Pass positional SQL parameters as a Lua table (`sn.db.query("... WHERE id = ?", { id })`), use `timeout_ms` on `sn.http.*`, and fetch secrets via `ctx.secret(...)`.

### 3. Validate & Smoke-Test in Staging

```bash
sentinel sre validate -p <test-sre>
sentinel sre test {ns}.{name}/ -p <test-sre>
```

Against the staging harness:
- Reload the kit: MCP `kit_reload` (requires `admin`) or `POST /hl/kt/{ns}/{name}/rl`.
- Smoke-run manually:
  - CLI: `sentinel sre flow run {ns}.{name}/<main-flow> -p <test-sre> --params-json '{"operation_id":"smoke_001"}'`
  - MCP: `flow_run` with `flow_id: "{ns}.{name}/<main-flow>"`
  - HTTP: `POST /fl/{ns}.{name}/<main-flow>/run` (returns `{id, fid, status}`), then poll `GET /ex/{id}` and `GET /ex/{id}/lg`.
- Verify duplicate delivery handling (re-run with the same `operation_id` / event key) and overlap behavior.

### 4. Promote & Rollback Plan

- **Promote:** Commit validated kit files to Git, pull/deploy into the target SRE, reload the kit (`POST /hl/kt/{ns}/{name}/rl` or MCP `kit_reload`), and verify registered triggers (`GET /tr` or MCP `triggers_list`).
- **Rollback (if promotion fails):**
  1. Immediately disable the kit: `POST /hl/kt/{ns}/{name}/off` (or MCP `kit_disable`).
  2. Revert to the prior Git revision (`git checkout <prev-rev> -- {ns}.{name}/` or `git revert`).
  3. Reload and re-enable (`POST /hl/kt/{ns}/{name}/rl` then `POST /hl/kt/{ns}/{name}/on`).

## Security & Approvals

- If the flow uses `ctx.fs`, restricted HTTP/SMTP, or raw DB operations under agent authority, verify `sentinel approvals --help` on the installed Sentinel binary (security-readiness builds) and document the required `.sentinel/execution-policy.json` grants and `sentinel approvals grant -p <sre>` workflow — or stop with a compatibility error if approvals are unavailable.
- Keep `kit.yaml` `public: false` unless anonymous web access is explicitly intended.

## Verification Checklist

- [ ] `sentinel sre validate -p <test-sre>` passes with zero errors.
- [ ] `sentinel sre test {ns}.{name}/ -p <test-sre>` passes.
- [ ] All required vault secrets are documented (names only).
- [ ] Staging smoke run and duplicate-event/overlap checks pass without hitting live destinations.
- [ ] Registered triggers verified after promotion and rollback steps confirmed.
