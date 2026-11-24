# Sentinel Kit & Lua Flow Blueprint

Use this reference when creating an `sre-*` skill (or hybrid skill) that scaffolds or edits Sentinel kits, Lua flows, connectors, modules, forms, or tests.

Public docs: [Kit Development](https://docs.ndx-sentinel.com/kit-development), [Lua API Reference](https://docs.ndx-sentinel.com/lua-api), [Configuration Guide](https://docs.ndx-sentinel.com/configuration-guide).

---

## Kit Discovery & Directory Layout

A kit is a flat directory directly under the SRE root whose name contains a `.` (`{ns}.{name}`) and contains a `kit.yaml` manifest. Only create the subdirectories actually needed:

```text
{ns}.{name}/
├── kit.yaml              # Required manifest
├── README.md             # Human/operator docs + secret inventory
├── fl/                   # Flows (.lua) — auto-discovered; NEVER list in kit.yaml
│   ├── sync.lua
│   └── sync_test.lua     # Tests using sn.test.*
├── cn/                   # Connectors (.lua) — external services (sn.cn.*)
├── md/                   # Modules (.lua) — reusable pure logic (sn.md.*)
├── fm/                   # Form definitions (.yaml) — stub kf.{ns}.{name}.{form}
├── pg/                   # Page definitions (.yaml) — presence makes it a UI kit
├── tp/                   # Go templates (.gohtml) — convention: tp/{page}.gohtml
├── pb/                   # Public static assets → /kt/{ns}/{name}/pb/*
├── ct/                   # fcms Markdown content → /fcms & /fcms/render
└── dd/                   # ccms ordered *.sql migrations (or legacy SQLite schema)
```

### Naming Conventions
- **Kit directory:** `{ns}.{name}` (e.g. `acme.billing`, `ops.monitor`).
- **Kit URL path:** dot splits into segments → `/kt/{ns}/{name}/...` (e.g. `/kt/acme/billing/pb/app.css`).
- **Canonical flow path (HTTP/CLI):** `{ns}.{name}/{flow}` (e.g. `acme.billing/charge`). Legacy internal colon ID: `{ns}-{name}:{flow}` (e.g. `acme-billing:charge`).
- **Skill twins:** The harness auto-spawns `.md` companions (`sync.lua.md`, `kit.yaml.md`) next to eligible code files (`.lua`, `.yaml`, `.yml`, `.js`, `.css`, `.gohtml`, `.xml`, `.xhtml`).

### Minimal `kit.yaml`

```yaml
name: Billing Workflows
version: "1.0.0"
description: Deterministic payment and invoice orchestration
public: false
```

---

## Two First-Class Lua Flow Patterns

### Pattern A — Lifecycle Hooks (Cron, Webhook, Event, Manual)
`setup`, `main`, and `cleanup` are **required**; `failed` and `timeout` are **optional** (omitting `failed` uses an automatic no-op).

```lua
triggers = {
  cron("0 */6 * * *"),
  webhook("/billing/sync", { auth = "hmac", key = "billing_hmac_secret" }),
}

local JOB_KEY = "billing:sync"
local MAX_ATTEMPTS = 3
local lease_held = false

function setup()
  -- Optional initialization; keep top-level file free of host I/O
end

local function derive_op_key(params)
  if params.trigger_type == "cron" then
    local tid = params.trigger_id or "cron"
    local sched = params.scheduled_at or sn.time.now()
    return "billing:cron:" .. tostring(tid) .. ":" .. tostring(sched)
  end
  local raw = params.id or params.event_id or params.operation_id
  if not raw or raw == "" then
    error("missing stable delivery/operation key")
  end
  return "billing:" .. tostring(raw)
end

function main(params)
  local op_key = derive_op_key(params)
  ctx.log("info", "Starting sync", "trigger", params.trigger_type, "op_key", op_key, "exec_id", ctx.execution_id)

  -- 1. For cron ticks, enforce flow-level skip exclusion via an owner-fenced job lease
  if params.trigger_type == "cron" then
    sn.db.exec([[
      CREATE TABLE IF NOT EXISTS job_leases (
        job_key TEXT PRIMARY KEY,
        owner_exec_id TEXT NOT NULL,
        lease_until TEXT NOT NULL
      )
    ]])
    local ins_lease = sn.db.exec(
      "INSERT OR IGNORE INTO job_leases (job_key, owner_exec_id, lease_until) VALUES (?, ?, datetime('now', '+5 minutes'))",
      { JOB_KEY, ctx.execution_id }
    )
    local acquired = (ins_lease.rows_affected == 1)
    if not acquired then
      local take_lease = sn.db.exec(
        "UPDATE job_leases SET owner_exec_id = ?, lease_until = datetime('now', '+5 minutes') WHERE job_key = ? AND lease_until < datetime('now')",
        { ctx.execution_id, JOB_KEY }
      )
      acquired = (take_lease.rows_affected == 1)
    end
    if not acquired then
      return { skipped = true, reason = "job_lease_active", op_key = op_key }
    end
    lease_held = true
  end

  -- 2. Atomic operation claim with classified failure states and bounded retries
  sn.db.exec([[
    CREATE TABLE IF NOT EXISTS operation_claims (
      op_key TEXT PRIMARY KEY,
      status TEXT NOT NULL,
      owner_exec_id TEXT NOT NULL,
      attempts INTEGER NOT NULL DEFAULT 1,
      lease_until TEXT NOT NULL,
      next_retry_at TEXT DEFAULT (datetime('now')),
      updated_at TEXT DEFAULT (datetime('now'))
    )
  ]])
  local ins = sn.db.exec(
    "INSERT OR IGNORE INTO operation_claims (op_key, status, owner_exec_id, attempts, lease_until) VALUES (?, 'processing', ?, 1, datetime('now', '+5 minutes'))",
    { op_key, ctx.execution_id }
  )
  local claimed = (ins.rows_affected == 1)
  if not claimed then
    local take = sn.db.exec(
      [[UPDATE operation_claims
        SET status = 'processing', owner_exec_id = ?, attempts = attempts + 1,
            lease_until = datetime('now', '+5 minutes'), updated_at = datetime('now')
        WHERE op_key = ?
          AND attempts < ?
          AND ((status = 'failed_retryable' AND next_retry_at <= datetime('now'))
               OR (status = 'processing' AND lease_until < datetime('now')))]],
      { ctx.execution_id, op_key, MAX_ATTEMPTS }
    )
    claimed = (take.rows_affected == 1)
  end
  if not claimed then
    local existing = sn.db.query_one("SELECT status, attempts FROM operation_claims WHERE op_key = ?", { op_key })
    return {
      duplicate = true,
      op_key = op_key,
      status = existing and existing.status or "unknown",
      attempts = existing and existing.attempts or 0,
    }
  end

  -- 3. Execute bounded work (inside lease TTL) and classify failures explicitly
  local sec_ok, token = pcall(function() return ctx.secret("billing_api_token") end)
  if not sec_ok or not token or token == "" then
    sn.db.exec(
      "UPDATE operation_claims SET status = 'failed_terminal', updated_at = datetime('now') WHERE op_key = ? AND owner_exec_id = ?",
      { op_key, ctx.execution_id }
    )
    error("missing required vault secret: billing_api_token")
  end

  local ok, resp = pcall(sn.http.get, "https://api.example.com/v1/items", {
    headers = {
      ["Authorization"] = "Bearer " .. token,
      ["Idempotency-Key"] = op_key,
    },
    timeout_ms = 15000,  -- milliseconds (default 10000; clamped to 30000 max)
  })
  if not ok then
    -- Ambiguous transport/timeout failure: mark unknown_outcome unless provider idempotency is verified
    sn.db.exec(
      "UPDATE operation_claims SET status = 'unknown_outcome', updated_at = datetime('now') WHERE op_key = ? AND owner_exec_id = ?",
      { op_key, ctx.execution_id }
    )
    error("transport error (reconcile by op_key): " .. tostring(resp))
  end
  if resp.status == 429 or resp.status >= 500 then
    sn.db.exec(
      "UPDATE operation_claims SET status = 'failed_retryable', next_retry_at = datetime('now', '+30 seconds'), updated_at = datetime('now') WHERE op_key = ? AND owner_exec_id = ?",
      { op_key, ctx.execution_id }
    )
    error("transient upstream status: " .. tostring(resp.status))
  end
  if resp.status ~= 200 then
    sn.db.exec(
      "UPDATE operation_claims SET status = 'failed_terminal', updated_at = datetime('now') WHERE op_key = ? AND owner_exec_id = ?",
      { op_key, ctx.execution_id }
    )
    error("permanent upstream status: " .. tostring(resp.status))
  end

  local data = sn.json.dec(resp.body)

  -- 4. Authoritative completion: require rows_affected == 1 before reporting completion
  local done = sn.db.exec(
    "UPDATE operation_claims SET status = 'completed', updated_at = datetime('now') WHERE op_key = ? AND owner_exec_id = ?",
    { op_key, ctx.execution_id }
  )
  if done.rows_affected ~= 1 then
    local auth = sn.db.query_one("SELECT status FROM operation_claims WHERE op_key = ?", { op_key })
    return {
      ownership_lost = true,
      op_key = op_key,
      authoritative_status = auth and auth.status or "unknown",
    }
  end
  return { synced = #data, op_key = op_key }
end

function cleanup()
  -- Owner-conditional release ONLY if this execution acquired the job lease
  if lease_held then
    sn.db.exec(
      "DELETE FROM job_leases WHERE job_key = ? AND owner_exec_id = ?",
      { JOB_KEY, ctx.execution_id }
    )
    lease_held = false
  end
end

-- Optional hook (no-op if omitted)
function failed()
  ctx.log("error", "Sync flow failed", "exec_id", ctx.execution_id)
end
```

### Pattern B — Trigger-Return (Form Submissions)
Used for flows wired to web forms in `events.yaml`. Keep raw PII (such as email addresses) out of logs and response payloads — persist it only to the intended destination and return a safe receipt/correlation ID:

```lua
return {
  triggers = {
    event("kf.acme.billing.contact"),
  },
  run = function(ctx)
    local form = ctx.form or ctx.data or {}
    -- Route raw form values only to their intended destination store/service.
    if not form.email or form.email == "" then
      error("missing required email field")
    end
    ctx.log("info", "Contact submission accepted", "receipt_id", ctx.execution_id)
    return { received = true, receipt_id = ctx.execution_id }
  end,
}
```

> **Lifecycle form listeners (`main(params)`):** When a Pattern A flow is wired to a form in `events.yaml`, dots in the form stub become nested tables on `ctx.fm` — for example `ctx.fm.kf.acme.billing.contact.email` (or `ctx.data.email`).

Form wiring in `events.yaml`:
```yaml
events:
  "kf.acme.billing.contact":
    flows:
      - "acme-billing:handle-contact"
```

---

## Lua Sandbox & Built-in API Surface

- **Allowed stdlib:** `base` (`pairs`, `ipairs`, `type`, `tostring`, `tonumber`, `pcall`, `xpcall`, `error`), `table`, `string`, `math`.
- **Blocked:** `io.*`, `os.*`, `debug.*`, `loadfile`, `dofile`, `load`.
- **Metadata rule:** Flow inspection has no host APIs and a 100 ms budget. Keep top-level declarations pure — perform HTTP, DB, FS, secret, and AI calls inside hooks (`setup`/`main`/`run`).

| Namespace | Key Functions / Properties |
|---|---|
| `ctx` | `ctx.log(level, msg, ...)`, `ctx.secret("key")`, `ctx.fs(op, path[, content])`, `ctx.execution_id`, `ctx.flow_name`, `ctx.trigger_type`, `ctx.started_at`, `ctx.params`, `ctx.req`, `ctx.fm` *(nested by stub dots)*, `ctx.form` *(Pattern B)*, `ctx.data` *(Note: `ctx.get`/`ctx.set` are stubs — use `sn.db` for persistence)* |
| `sn.http` | `get(url, opts)`, `post(url, body, opts)`, `put(...)`, `del(...)` (`opts`: `{headers, timeout_ms}`; `timeout_ms` in ms, default `10000`, clamped to `30000` max; 16 MiB response cap) |
| `sn.json` | `enc(tbl)`, `dec(str)`, `sn.null` |
| `sn.db` | `exec(sql, params?)`, `query(sql, params?)`, `query_one(sql, params?)`, `transaction(fn)` — **always pass positional parameters as a Lua array table `{v1, v2}`** |
| `sn.crypto` | `hmac_sha256(key, data)`, `sha256(data)`, `random_bytes(n)` |
| `sn.time` / `sn.sleep` | `sn.time.now()` (RFC3339), `sn.sleep(seconds)` (max 300s) |
| `sn.ws` | Named persistent connections (opt-in): `open(name, url, opts?)`, `send(name, data, binary?)`, `receive(name, timeout_ms?)`, `request(name, data, timeout_ms?)`, `close(name)` (keep handshake/reconnect logic in `cn/*.lua`) |
| `sn.ai` / `sn.memory` / `sn.rag` | `sn.ai.chat({...})`, `sn.ai.complete({...})`, `sn.memory.add/get_recent(...)`, `sn.rag.search({...})` — guard for disabled/canary states |
| `sn.cms` | Query `fcms` Markdown content from flows |
| `sn.backup` | Read-only observation: `plans()`, `runs(opts)`, `running()`, `status()` |
| `sentinel` | `sentinel.emit("domain.event", payload_table)` |
| `sn.cn.*` / `sn.md.*` | Connectors (`cn/`) and Modules (`md/`) — always guard with `sn.cn = sn.cn or {}` / `sn.md = sn.md or {}` |
| `sn.test` | `ok`, `eq`, `neq`, `type`, `contains`, `throws` (used in `*_test.lua`) |

---

## Common Pitfalls to Avoid

1. **String-concatenating SQL or passing scalar bind args** — Always pass a Lua table: `sn.db.query("SELECT * FROM t WHERE id = ?", { id })`.
2. **Using `timeout` instead of `timeout_ms`** — `sn.http` expects `timeout_ms` in milliseconds (default `10000`, max `30000`).
3. **Logging secrets or raw PII** — Never pass `ctx.secret(...)` or raw form PII to `ctx.log(...)` or flow return payloads.
4. **Listing flows in `kit.yaml`** — Flows are auto-discovered from `fl/*.lua`.
5. **Adding `template:` to page YAML** — Templates resolve by convention (`tp/{page}.gohtml`).
6. **Forgetting `events.yaml`** — Form submissions will not invoke flows until wired in `events.yaml`.
7. **Using `ctx.get`/`ctx.set` for state** — They are stubs; persist state in `sn.db` (kit-scoped SQLite) or PostgreSQL.
8. **Editing trigger-bearing flows directly in a live SRE** — Stage and test in an isolated test SRE first so hot-reload/reloads cannot fire unfinished cron or webhook triggers against live targets.
9. **Putting machine-specific config in `sentinel.yaml`** — `sentinel.yaml` is git-tracked project behavior; ports, tokens, TLS, and MCP client ACLs belong in gitignored `.sentinel/config.json`.
