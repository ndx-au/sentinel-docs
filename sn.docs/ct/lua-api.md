---
title: "Lua API Reference"
description: "Complete reference for the Lua API available inside Sentinel flows. This document covers the sandboxed execution environment, the flow lifecycle, every available API function, and common patterns for building robust automation flows."
---

# Lua API Reference

Complete reference for the Lua API available inside Sentinel flows. This document covers the sandboxed execution environment, the flow lifecycle, every available API function, and common patterns for building robust automation flows.

---

## Introduction

Sentinel flows are written in Lua and executed inside a sandboxed virtual machine (VM). The sandbox provides a controlled environment where flow code can make HTTP requests, interact with databases, send WebSocket messages, access secrets, and emit events -- but cannot access the host file system, execute system commands, or load arbitrary libraries.

### Why a Sandbox?

Flows are user-authored code. In a multi-tenant or production environment, you need guarantees that a flow cannot:

- Read or write arbitrary files on the server
- Execute shell commands or spawn processes
- Load malicious Lua libraries
- Access memory or state from other flows
- Interfere with the harness process itself

The sandbox achieves this by providing a curated set of APIs (the `sn.*` namespace) while removing dangerous Lua standard library functions. Think of it as a "browser for server automation" -- powerful enough to do useful work, restricted enough to be safe.

### What Is Available

Every flow has access to:

| Namespace | Purpose |
|-----------|---------|
| `ctx` | Execution context: logging, state, secrets, form data, PostgreSQL |
| `sn.http` | HTTP client for calling external APIs |
| `sn.ws` | WebSocket client with persistent connections and message bus |
| `sn.db` | Kit-scoped SQLite database |
| `sn.backup` | Read-only backup subsystem observation |
| [`sn.ai`](#ai-snai) | AI chat, completion, embedding, and token accounting |
| [`sn.memory`](#memory-snmemory) | Episodic memory management |
| [`sn.rag`](#rag-snrag) | Retrieval-augmented document ingestion and search |
| `sn.json` | JSON encoding and decoding |
| `sn.crypto` | Cryptographic functions (HMAC, SHA256, random bytes) |
| `sn.time` | Time utilities |
| `sn.sleep` | Pause execution |
| `sn.cms` | Content cache access (CMS kits only) |
| `sn.md` | Built-in modules (shared Lua libraries) |
| `sn.cn` | Built-in connectors (pre-built integrations) |
| `sn.lib` | API library service (vendor/endpoint management) |
| `sentinel` | Core functions (event emission) |

### What Is NOT Available

The following Lua standard library functions are removed from the sandbox:

- `io.*` -- No file I/O (use `sn.cn.file.exec()` for controlled file operations)
- `os.*` -- No system commands (exception: `os.date` is available for time formatting)
- `debug.*` -- No debug introspection
- `package.*` -- No `require()` or module loading
- `load()`, `loadstring()` -- No dynamic code evaluation
- `dofile()` -- No file execution

If you need file operations, use the built-in file connector (`sn.cn.file.exec()`). If you need to call an external service, use `sn.http`. The sandbox channels all external interaction through auditable, rate-limitable APIs.

Long-running operational work such as scheduled backups remains harness-owned. Lua flows can observe backup state and react to backup lifecycle events, but they do not become the scheduler or worker for those jobs.

The AI-facing namespaces are feature-gated from the Agents dashboard release controls. When a subsystem is off, outside the canary cohort, or under rollback, calls return explicit errors such as `"sn.ai is disabled"`, `"sn.memory is disabled"`, or `"sn.rag is disabled"`.

Canary rollout uses stable hashing on `ctx.execution_id` (fallback: `ctx.flow_name`). With `canary_percent` at 25, roughly 25% of executions land in the active cohort; `rollback_active` disables all three subsystems regardless of canary. Check `sn.ai.enabled` (refreshed per execution after `ctx` exists) before calling, or handle the disabled error in `pcall`.

---

## Flow Lifecycle

Every Lua flow must define four lifecycle functions: `setup`, `main`, `cleanup`, and `failed`. Missing required hooks fail registration. `timeout` is optional.

```lua
function setup()
  -- Called once before main(). Use for initialization:
  -- opening WebSocket connections, creating database tables,
  -- validating preconditions.
end

function main(params)
  -- The core logic of your flow. This is where the work happens.
  -- Called after setup() completes successfully.
  -- params is a Lua table containing trigger data (webhook fields,
  -- event metadata, cron metadata, etc.). See "main(params)" below.
  -- Return a table to pass data back to the caller.
end

function cleanup()
  -- Always runs last after setup/main (and after failed() when those error).
  -- Use for resource cleanup: closing connections, flushing buffers.
end

function failed(err)
  -- Called when setup() or main() throws, then cleanup() still runs.
  -- The err parameter is the error message string.
  -- Use for error-specific cleanup or alerting.
end
```

### Lifecycle Order

1. Success: `setup` → `main` → `cleanup`
2. Setup fails: `setup` → `failed` → `cleanup`
3. Main fails: `setup` → `main` → `failed` → `cleanup`

### Important Notes

- **`ctx` is a global, not a parameter.** Unlike some frameworks, `ctx` is injected into the global scope before your functions are called. You access it directly: `ctx.log("info", "hello")`, not `function main(ctx)`.
- **`main(params)` receives a params table.** The `params` argument is a Lua table containing trigger-specific data. For webhooks, it contains the merged query string and body fields plus trigger metadata (`trigger_type`, `trigger_id`, `trigger_path`). For cron triggers, it contains `trigger_type`, `trigger_id`, `trigger_name`, and `scheduled_at`. For event triggers, it contains `event_id`, `event_pattern`, `event_source`, `event_payload`, and `event_time`. For manual runs via `POST /fl/{id}/run`, it contains the request body fields. If no params are available, `params` may be `nil` -- always guard access.
- **`ctx.params` mirrors the parsed request fields.** For webhook and manual triggers, `ctx.params` is a Lua table containing the merged query string and body fields (same data as the top-level keys in `params`). For cron and event triggers, `ctx.params` is not set.
- **`ctx.req` contains HTTP request metadata.** For webhook and manual triggers, `ctx.req` is a table with `method` (string), `path` (string), `headers` (table of lowercase key-value pairs), and `files` (array of file objects with `field`, `name`, `type`, `size`, `data` fields). For cron and event triggers, `ctx.req` is not set.
- **Return values from `main()` are captured.** If `main()` returns a Lua table, it is serialized as JSON and stored as the execution result. It is also returned to the caller for synchronous webhook triggers.
- **Flow metadata is auto-discovered.** You do not need a `flow = {}` metadata table. Flows are discovered from the `fl/` directory and their ID is derived from the kit name and filename.

### Minimal Flow Example

```lua
function main(params)
  ctx.log("info", "Hello from Sentinel!")
  return {ok = true, msg = "It works"}
end
```

### Complete Flow Example

```lua
function setup()
  -- Ensure our database table exists
  sn.db.exec([[
    CREATE TABLE IF NOT EXISTS orders (
      id TEXT PRIMARY KEY,
      amount REAL,
      status TEXT DEFAULT 'pending',
      created_at TEXT
    )
  ]])
end

function main(params)
  ctx.log("info", "Processing incoming order")

  -- Get order data from trigger context
  local order_id = "ord_" .. sn.crypto.random_bytes(8)

  -- Store in database
  sn.db.exec(
    "INSERT INTO orders (id, amount, status, created_at) VALUES (?, ?, ?, ?)",
    {order_id, 99.99, "pending", sn.time.now()}
  )

  -- Call external API
  local resp = sn.http.post(
    "https://api.example.com/process",
    sn.json.enc({order_id = order_id}),
    {
      headers = {Authorization = "Bearer " .. ctx.secret("api_token")},
      timeout_ms = 10000
    }
  )

  if resp.status ~= 200 then
    error("API call failed: HTTP " .. resp.status .. " - " .. resp.body)
  end

  -- Update status
  sn.db.exec("UPDATE orders SET status = ? WHERE id = ?", {"completed", order_id})

  -- Notify other flows
  sentinel.emit("order.completed", {order_id = order_id, amount = 99.99})

  ctx.log("info", "Order processed: " .. order_id)
  return {ok = true, order_id = order_id}
end

function cleanup()
  ctx.log("debug", "Cleanup complete")
end

function failed(err)
  ctx.log("error", "Order processing failed: " .. err)
  -- Could send an alert here via sn.http or sentinel.emit
end
```

---

## Context (ctx)

The `ctx` object is a global that provides execution context, logging, state management, and secret access. It is available in all four lifecycle functions (`setup`, `main`, `cleanup`, `failed`).

**Important:** During harness dry-run (flow registration at startup), `ctx` is `nil`. If your flow has top-level code outside of the lifecycle functions, always guard `ctx` access:

```lua
if ctx and ctx.kit then
  -- safe to use ctx
end
```

### Fields

#### ctx.execution_id

```lua
local eid = ctx.execution_id
-- Returns: "exec_abc123"
```

A unique identifier for this specific execution. Every time a flow runs, it gets a new execution ID. Use this for logging, correlation, and looking up execution results.

**Type:** string

#### ctx.flow_name

```lua
local name = ctx.flow_name
-- Returns: "sn-core-agent:assistant"
```

The full flow ID, including the kit namespace and name. The format is `{ns}-{name}:{flow}` where `{ns}.{name}` is the kit directory and `{flow}` is the Lua filename without the `.lua` extension.

**Type:** string

#### ctx.trigger_type

```lua
local trigger = ctx.trigger_type
-- Returns: "cron" | "webhook" | "event" | "manual" | "form"
```

Indicates how this flow execution was triggered. This is useful when a flow can be triggered by multiple mechanisms and needs to behave differently depending on the source.

| Value | Meaning |
|-------|---------|
| `"manual"` | Triggered via `POST /fl/{id}/run` API call |
| `"cron"` | Triggered by a cron schedule |
| `"webhook"` | Triggered by an incoming webhook request |
| `"event"` | Triggered by an internal event (via `sentinel.emit()`) |
| `"form"` | Triggered by a form submission |

**Type:** string

### Backup Observation (`sn.backup`)

The harness exposes read-only backup subsystem inspection to Lua.

#### `sn.backup.plans()`

Returns all configured backup plans.

```lua
local plans, err = sn.backup.plans()
if err == nil then
  for _, plan in ipairs(plans) do
    ctx.log("info", "backup plan", "name", plan.name, "schedule", plan.schedule)
  end
end
```

#### `sn.backup.runs(opts)`

Returns recent backup runs. Optional `opts` fields:
- `limit`
- `status`

```lua
local runs, err = sn.backup.runs({ limit = 10, status = "failed" })
if err == nil then
  for _, run in ipairs(runs) do
    ctx.log("warn", "backup issue", "plan", run.plan_name, "error", run.error_message)
  end
end
```

#### `sn.backup.running()`

Returns the currently active in-process backup jobs known to this harness instance.

```lua
local running = sn.backup.running()
if #running > 0 then
  ctx.log("info", "backup jobs active", "count", #running)
end
```

#### `sn.backup.status()`

Returns a small backup summary:
- `plan_count`
- `enabled_count`
- `running_count`
- `recent_failures`

```lua
local status, err = sn.backup.status()
if err == nil and status.running_count > 0 then
  ctx.log("info", "backup subsystem busy", "running", status.running_count)
end
```

### Backup Events

Flows can subscribe to backup lifecycle events through normal event triggers:

- `backup.schedule.synced`
- `backup.run.started`
- `backup.run.completed`
- `backup.run.failed`

```lua
triggers = {
  event("backup.run.failed"),
}

function main(params)
  ctx.log("error", "backup failed", "plan", params.plan_name, "error", params.error_message)
  return {ok = true}
end
```

#### ctx.started_at

```lua
local ts = ctx.started_at
-- Returns: "2026-02-10T12:00:00Z" (ISO8601)
```

The timestamp when this execution started. Useful for calculating elapsed time or logging.

**Type:** string (ISO8601 format)

#### ctx.params

```lua
local name = ctx.params.name
local email = ctx.params.email
```

Available for **webhook** and **manual** triggers. Contains the merged query string and parsed body fields as a Lua table. For JSON request bodies, each top-level key becomes a field in `ctx.params` with its value stringified. For form-urlencoded bodies, each field becomes a string entry. Query parameters are included; body fields take precedence on key conflicts.

This is the same data available as top-level keys in the `params` argument to `main(params)`, but without the trigger metadata keys (`trigger_type`, `trigger_id`, etc.).

**Type:** table or nil (nil for cron/event triggers)

**Note:** All values in `ctx.params` are strings. JSON objects and arrays are stringified. Use `sn.json.dec()` to parse complex values.

#### ctx.req

```lua
local method = ctx.req.method       -- "POST", "GET", etc.
local path = ctx.req.path           -- "/wh/stripe"
local content_type = ctx.req.headers["content-type"]
local auth = ctx.req.headers["authorization"]
```

Available for **webhook** and **manual** triggers. Contains HTTP request metadata.

| Field | Type | Description |
|-------|------|-------------|
| `method` | string | HTTP method (`"GET"`, `"POST"`, etc.) |
| `path` | string | Request path |
| `headers` | table | Request headers with **lowercase** keys |
| `files` | table (array) | Uploaded files (multipart only) |

Each file object in `ctx.req.files` has:

| Field | Type | Description |
|-------|------|-------------|
| `field` | string | Form field name |
| `name` | string | Original filename |
| `type` | string | MIME type |
| `size` | number | File size in bytes |
| `data` | string | Base64-encoded file content |

**Type:** table or nil (nil for cron/event triggers)

#### ctx.fm (Form Context)

Available **only** when the flow was triggered by a form submission (`ctx.trigger_type == "form"`). Provides access to the submitted form data, organized by form stub and field name.

```lua
-- Access form fields: ctx.fm.{stub}.{field}
local email = ctx.fm.contact.email
local message = ctx.fm.contact.message

-- Every submission gets a UUID
local submission_id = ctx.fm.contact.uuid
```

**Type coercion:** Form field values are automatically coerced to appropriate Lua types based on the field type defined in the form YAML:

| Form Field Type | Lua Type | Example |
|-----------------|----------|---------|
| `text` | string | `"Hello world"` |
| `email` | string | `"user@example.com"` |
| `number` | number (float) | `42.5` |
| `checkbox` | boolean | `true` / `false` |
| `select` | string | `"option-a"` |
| `multiselect` | table of strings | `{"option-a", "option-b"}` |
| `date` | string | `"2026-02-10"` (YYYY-MM-DD) |
| `file` | string | Upload ID (for file retrieval) |

**Note:** When `ctx.trigger_type` is `"form"`, the additional fields `ctx.kit` (kit directory name) are also available.

#### ctx.kit

```lua
local kit_name = ctx.kit
-- Returns: "sn.core-agent"
```

The kit directory name that owns this flow. Available in all trigger contexts.

**Type:** string

### Methods

#### ctx.fs(op, path[, content[, "append"]])

Filesystem access through FS Control. Default-deny: a matching policy must grant the executing kit. Ops are `read`, `write`, `append`, and `delete` only — there is no `listdir`.

```lua
local body = ctx.fs("read", "sn.mine/data/note.txt")
ctx.fs("write", "sn.mine/data/out.txt", body)
ctx.fs("append", "sn.mine/data/log.txt", "line\n")
ctx.fs("delete", "sn.mine/data/tmp.txt")
```

Kit identity for policy matching uses the same first-hyphen flow-id parse as `sn.db` / `sn.cms` / `sn.ws` (`ops-code-progress:scan` → kit `ops.code-progress`).

#### ctx.log(level, message)

Writes a log entry associated with this execution. Logs are stored in the state database and can be streamed in real-time via the SSE API (`GET /ex/{id}/lg`).

```lua
ctx.log("info", "Processing order " .. order_id)
ctx.log("warn", "Unexpected field encountered: " .. field_name)
ctx.log("error", "Failed to connect to payment API")
ctx.log("debug", "Full response: " .. sn.json.enc(data))
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `level` | string | Log level: `"debug"`, `"info"`, `"warn"`, or `"error"` |
| `message` | string | The log message text |

**Log level guidance:**
- `debug`: Verbose information useful only during development. Hidden in Dashboard by default.
- `info`: Normal operational messages. "Processing started", "Order completed", etc.
- `warn`: Something unexpected but not fatal. "Retrying after timeout", "Missing optional field".
- `error`: Something went wrong. "API call failed", "Database write error".

**Visibility:**
- The Dashboard execution view shows the last 100 log entries.
- Stream logs in real-time via `GET /ex/{id}/lg?follow=true`.
- Filter logs by level in the API: `GET /lg?lv=error`.

#### ctx.get(key)

**Status: Not yet wired.** This function currently always returns `nil`. It is reserved for a future execution-scoped key-value state store. Do not use `ctx.get()` to access trigger parameters -- use the `params` argument to `main(params)` instead, or `ctx.params` for the parsed request fields.

```lua
-- WRONG: ctx.get() does not return trigger data
local name = ctx.get("name")  -- always returns nil

-- RIGHT: use the params argument to main()
function main(params)
  local name = params and params.name or "default"
end
```

#### ctx.set(key, value)

**Status: Not yet wired.** This function currently does nothing (no-op). It is reserved for a future execution-scoped key-value state store.

#### ctx.secret(key)

Retrieves an encrypted secret from the Sentinel vault. Secrets are stored encrypted at rest using AES-256-GCM and are only decrypted in memory when accessed.

```lua
local token = ctx.secret("slack_token")
local password = ctx.secret("db_password")
local api_key = ctx.secret("stripe_api_key")
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `key` | string | The secret name (as stored via `POST /sc`) |

**Returns:** The decrypted secret value as a string.

**Raises:** Error if the secret does not exist. Always wrap in `pcall` if you want to handle missing secrets gracefully:

```lua
local ok, token = pcall(function() return ctx.secret("optional_token") end)
if not ok then
  ctx.log("warn", "Optional token not configured, skipping notification")
  return
end
```

#### ctx.pg(name)

Returns a PostgreSQL database handle for the named connection pool. Connection pools are configured via the `/pg` API endpoints and their credentials are stored in the vault.

```lua
local db = ctx.pg("main")

-- Query rows
local rows = db.query("SELECT id, name FROM users WHERE active = $1", {true})
for _, row in ipairs(rows) do
  ctx.log("info", row.id .. ": " .. row.name)
end

-- Execute statements
db.exec("INSERT INTO users (id, name) VALUES ($1, $2)", {"user_123", "Alice"})

-- Single row
local user = db.query_one("SELECT * FROM users WHERE id = $1", {"user_123"})
if user then
  ctx.log("info", "Found: " .. user.name)
end
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | The PostgreSQL connection pool name (as configured via `POST /pg`) |

**Returns:** A database handle object with `query()`, `query_one()`, and `exec()` methods.

**Note:** PostgreSQL uses `$1`, `$2`, etc. for parameter placeholders (not `?` like SQLite).

---

## HTTP Client (sn.http)

The HTTP client allows flows to make outbound HTTP requests to external APIs. It supports GET, POST, PUT, and DELETE methods with configurable headers and timeouts. All requests are synchronous -- the flow blocks until the response is received or the timeout expires.

### sn.http.get(url, options?)

Makes an HTTP GET request.

```lua
-- Simple GET
local resp = sn.http.get("https://api.example.com/users/123")

-- GET with headers and timeout
local resp = sn.http.get("https://api.example.com/users", {
  headers = {
    Authorization = "Bearer " .. ctx.secret("api_token"),
    Accept = "application/json"
  },
  timeout_ms = 5000
})

if resp.status == 200 then
  local data = sn.json.dec(resp.body)
  ctx.log("info", "Found " .. #data.users .. " users")
else
  ctx.log("error", "API error: HTTP " .. resp.status .. " - " .. resp.body)
end
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | yes | The full URL to request |
| `options` | table | no | Request options (see Options table below) |

**Returns:** A response object (see Response Object below).

### sn.http.post(url, body, options?)

Makes an HTTP POST request with a request body.

```lua
local payload = sn.json.enc({
  name = "Alice",
  email = "alice@example.com",
  role = "admin"
})

local resp = sn.http.post("https://api.example.com/users", payload, {
  headers = {
    Authorization = "Bearer " .. ctx.secret("api_token"),
    ["Content-Type"] = "application/json"
  },
  timeout_ms = 10000
})

if resp.status == 201 then
  local created = sn.json.dec(resp.body)
  ctx.log("info", "User created with ID: " .. created.id)
else
  ctx.log("error", "Failed to create user: " .. resp.body)
end
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | yes | The full URL to request |
| `body` | string | yes | Request body (typically JSON-encoded) |
| `options` | table | no | Request options |

### sn.http.put(url, body, options?)

Makes an HTTP PUT request. Same signature as `post()`.

```lua
local resp = sn.http.put(
  "https://api.example.com/users/123",
  sn.json.enc({status = "active"}),
  {timeout_ms = 5000}
)
```

### sn.http.del(url, options?)

Makes an HTTP DELETE request. Same signature as `get()`.

```lua
local resp = sn.http.del("https://api.example.com/users/123", {
  headers = {Authorization = "Bearer " .. ctx.secret("api_token")}
})

if resp.status == 204 then
  ctx.log("info", "User deleted")
end
```

### Options Table

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `headers` | table | `{}` | Key-value pairs of HTTP headers. Keys are header names, values are header values. |
| `timeout_ms` | integer | `30000` | Request timeout in milliseconds. If the server does not respond within this time, the request fails with an error. |

### Response Object

All HTTP methods return a response object with the following fields:

```lua
{
  status = 200,             -- HTTP status code (integer)
  body = "...",             -- Response body as a string
  headers = {               -- Response headers (lowercase keys)
    ["content-type"] = "application/json",
    ["x-rate-limit"] = "100"
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | integer | HTTP status code (200, 404, 500, etc.) |
| `body` | string | Response body as a raw string. Parse JSON with `sn.json.dec()`. |
| `headers` | table | Response headers. Header names are lowercased. |

### Real-World Examples

**Calling the Stripe API:**
```lua
function main(params)
  local resp = sn.http.post(
    "https://api.stripe.com/v1/charges",
    "amount=2000&currency=usd&source=tok_visa",
    {
      headers = {
        Authorization = "Bearer " .. ctx.secret("stripe_secret_key"),
        ["Content-Type"] = "application/x-www-form-urlencoded"
      },
      timeout_ms = 15000
    }
  )

  if resp.status == 200 then
    local charge = sn.json.dec(resp.body)
    ctx.log("info", "Charge created: " .. charge.id)
    return {ok = true, charge_id = charge.id}
  else
    ctx.log("error", "Stripe error: " .. resp.body)
    return {ok = false, error = resp.body}
  end
end
```

**Calling the GitHub API:**
```lua
function main(params)
  local resp = sn.http.get(
    "https://api.github.com/repos/acme/myrepo/pulls?state=open",
    {
      headers = {
        Authorization = "token " .. ctx.secret("github_token"),
        Accept = "application/vnd.github.v3+json",
        ["User-Agent"] = "Sentinel-Flow"
      },
      timeout_ms = 10000
    }
  )

  if resp.status == 200 then
    local prs = sn.json.dec(resp.body)
    ctx.log("info", "Found " .. #prs .. " open pull requests")
    return {ok = true, count = #prs, prs = prs}
  else
    error("GitHub API failed: " .. resp.status)
  end
end
```

**Posting to a Slack Webhook:**
```lua
function main(params)
  local resp = sn.http.post(
    ctx.secret("slack_webhook_url"),
    sn.json.enc({
      text = "Deployment complete!",
      channel = "#deployments"
    }),
    {
      headers = {["Content-Type"] = "application/json"},
      timeout_ms = 5000
    }
  )

  if resp.status ~= 200 then
    ctx.log("error", "Slack notification failed: " .. resp.body)
  end
end
```

---

## WebSocket Bus (sn.ws)

The WebSocket bus provides harness-managed WebSocket connections. Unlike the HTTP client where each request is independent, WebSocket connections persist beyond flow execution. The Go harness owns all socket I/O -- flows open connections, send messages, and receive responses, but the actual TCP sockets are managed by the harness process. The subsystem is disabled by default; an administrator must enable it in `.sentinel/config.json` or from the dashboard Sockets page before `sn.ws.*` operations will work. This means:

1. **Connections survive flow completion.** A flow can open a connection in `setup()`, use it in `main()`, and it remains open for other flows or subsequent executions to use.
2. **Multiple flows can share connections.** A connection opened by one flow can be used by any other flow in the same kit (or any flow, if the connection is not private).
3. **Kit scoping for security.** Connections can be marked `private = true`, which restricts access to flows within the owning kit.
4. **Automatic reconnection.** Connections can be configured with exponential backoff reconnection, and reconnect attempts reuse the original headers and subprotocol.

### sn.ws.open(name, url, opts?)

Opens a named outbound WebSocket connection. The name is used by all subsequent operations to reference this connection.

```lua
-- Simple connection
sn.ws.open("my-api", "wss://api.example.com/ws")

-- Connection with full options
sn.ws.open("discord", "wss://gateway.discord.gg/?v=10&encoding=json", {
  headers = {Authorization = "Bot " .. ctx.secret("discord_token")},
  private = true,         -- only this kit's flows can access
  subprotocol = "json",   -- WebSocket subprotocol header
  reconnect = {           -- auto-reconnect on disconnect
    max_tries = 5,        -- maximum reconnection attempts
    base_ms = 1000,       -- initial backoff interval
    max_ms = 30000        -- maximum backoff interval (cap)
  }
})
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Unique connection name. Must be URL-safe. |
| `url` | string | yes | WebSocket URL (ws:// or wss://) |
| `opts` | table | no | Connection options (see below) |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `headers` | table | `{}` | HTTP headers sent during the WebSocket handshake |
| `private` | boolean | `false` | If true, only flows in the same kit can access this connection |
| `subprotocol` | string | `""` | WebSocket subprotocol (Sec-WebSocket-Protocol header) |
| `reconnect` | table | `nil` | Auto-reconnect configuration. If nil, no automatic reconnection. |
| `reconnect.max_tries` | integer | -- | Maximum reconnection attempts before giving up |
| `reconnect.base_ms` | integer | -- | Initial backoff delay in milliseconds |
| `reconnect.max_ms` | integer | -- | Maximum backoff delay in milliseconds (exponential backoff cap) |

**Raises:** Error if the name is invalid, already in use, or the connection pool is full.

If `reconnect` is enabled, Sentinel reuses the original handshake headers and subprotocol on each reconnect attempt.

### sn.ws.close(name)

Closes a named connection and removes it from the manager. After closing, the name can be reused by a new `open()` call.

```lua
sn.ws.close("my-api")
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Connection name to close |

### sn.ws.send(name, data, binary?)

Sends a message to a named connection. This is non-blocking -- the message is queued for sending and the function returns immediately.

```lua
-- Send text message
sn.ws.send("my-api", sn.json.enc({op = "ping"}))

-- Send binary message
sn.ws.send("my-api", raw_bytes, true)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Connection name |
| `data` | string | yes | Message payload |
| `binary` | boolean | no | If true, send as a binary WebSocket frame. Default: false (text). |

### sn.ws.request(name, data, timeout_ms?)

Sends a message and synchronously waits for the next message that arrives after the send completes. This implements a simple request-reply pattern, but it does not add protocol-level correlation.

```lua
local resp = sn.ws.request("my-api", sn.json.enc({op = "query", id = 1}), 5000)
local data = sn.json.dec(resp.data)
ctx.log("info", "Query result: " .. data.result)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Connection name |
| `data` | string | yes | Message to send |
| `timeout_ms` | integer | no | Timeout in milliseconds. Default: 5000. |

**Returns:** `{data = "...", bin = false}` -- The next message received on this connection after the request is sent.

**Raises:** Error on timeout or if the connection is closed.

**Important:** This function returns the first message observed after the send, regardless of whether it is a response to your specific request. If the server sends unsolicited messages, you may receive one of those instead. For protocols that multiplex multiple request-response pairs over a single connection, use `send()` and `receive()` separately with your own correlation logic.

### sn.ws.receive(name, timeout_ms?)

Waits for the next message on a named connection without sending anything first.

```lua
local msg = sn.ws.receive("my-api", 10000)
ctx.log("info", "Received: " .. msg.data)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | Connection name |
| `timeout_ms` | integer | no | Timeout in milliseconds. Default: 5000. |

**Returns:** `{data = "...", bin = false}`

**Raises:** Error on timeout or closed connection.

### sn.ws.broadcast(channel, data, binary?)

Sends a message to all clients subscribed to a bus channel. This is the bridge between Lua flows and browser clients connected via `/ws` or `/ws/{channel}` endpoints. Returns the number of connections that received the message.

```lua
local count = sn.ws.broadcast("notifications", sn.json.enc({
  type = "alert",
  msg = "New order received",
  timestamp = sn.time.now()
}))
ctx.log("info", "Broadcast to " .. count .. " clients")
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `channel` | string | yes | Bus channel name |
| `data` | string | yes | Message payload |
| `binary` | boolean | no | If true, send as binary. Default: false. |

**Returns:** Integer -- the number of connections that received the message.

### sn.ws.status(name)

Returns the current status of a named connection.

```lua
local st = sn.ws.status("my-api")
ctx.log("info", "Connection " .. st.name .. " is " .. st.st)
ctx.log("info", "Messages sent: " .. st.ms .. ", received: " .. st.mr)
```

**Returns:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Connection name |
| `st` | string | `"connected"`, `"disconnected"`, or `"reconnecting"` |
| `dir` | string | `"in"` (inbound) or `"out"` (outbound) |
| `priv` | boolean | Whether the connection is private (kit-scoped) |
| `ca` | integer | Created-at Unix timestamp |
| `ms` | integer | Total messages sent |
| `mr` | integer | Total messages received |
| `md` | integer | Messages dropped due to backpressure or receive-queue overflow |

### sn.ws.list()

Lists all visible WebSocket connections. Private connections from other kits are hidden. Kit-scoped Lua visibility remains limited to the current kit plus shared sockets even though HTTP management of `/ws/cn*` is admin-only.

```lua
local conns = sn.ws.list()
for _, c in ipairs(conns) do
  ctx.log("info", c.name .. ": " .. c.st .. " (" .. c.ms .. " sent, " .. c.mr .. " received)")
end
```

**Returns:** Array of status objects (same structure as `sn.ws.status()`).

### Event Bus Integration

Incoming WebSocket messages are automatically published to the Sentinel event bus. Other flows can subscribe to these events using event triggers. This creates a powerful pattern: one flow opens a WebSocket connection, and many flows react to incoming messages.

**Event patterns:**

| Pattern | When it fires |
|---------|---------------|
| `ws:pub:{name}` | Message received on a public connection named `{name}` |
| `ws:kit:{kit}:{name}` | Message received on a private connection `{name}` in kit `{kit}` |
| `ws:{name}:open` | Connection `{name}` opened |
| `ws:{name}:close` | Connection `{name}` closed |
| `ws:pub:{channel}` | Message published to bus channel `{channel}` |

### Complete WebSocket Example

```lua
-- sn.core-agent/fl/ws-monitor.lua
-- Opens a WebSocket to an external status service, sends periodic pings,
-- and broadcasts health status to all connected Dashboard clients.

function setup()
  sn.ws.open("monitor", "wss://status.example.com/ws", {
    reconnect = {max_tries = 10, base_ms = 2000, max_ms = 60000}
  })
end

function main(params)
  -- Send a status request and wait for response
  local resp = sn.ws.request("monitor", '{"op":"status"}', 5000)
  local status = sn.json.dec(resp.data)

  -- Broadcast to Dashboard clients subscribed to the "status" channel
  local count = sn.ws.broadcast("status", sn.json.enc({
    service = "example",
    healthy = status.ok,
    latency = status.latency_ms,
    checked = sn.time.now()
  }))

  ctx.log("info", "Status check complete, broadcast to " .. count .. " clients")
  return {ok = true, healthy = status.ok}
end

function cleanup()
  sn.ws.close("monitor")
end
```

---

## Database (sn.db)

Every kit gets its own isolated SQLite database. The database file is stored at `.sentinel/data/{kit-name}.db` within the SRE directory. Other kits cannot access it unless explicitly imported in `kit.yaml`.

SQLite is a full-featured relational database that supports transactions, indexes, JSON functions, and most SQL operations. It is ideal for storing flow state, caching API responses, tracking processed items, and building simple CRUD applications.

### sn.db.exec(sql, params?)

Executes a SQL statement that modifies data (INSERT, UPDATE, DELETE) or schema (CREATE TABLE, ALTER TABLE, etc.). Returns a result object with metadata about the operation.

```lua
-- Create a table
sn.db.exec([[
  CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    created_at TEXT DEFAULT (datetime('now'))
  )
]])

-- Insert a row
local result = sn.db.exec(
  "INSERT INTO users (id, name, email) VALUES (?, ?, ?)",
  {"user_1", "Alice", "alice@example.com"}
)
-- result = {ok = true, rows_affected = 1, last_insert_id = 0}

-- Update rows
local result = sn.db.exec(
  "UPDATE users SET name = ? WHERE id = ?",
  {"Alice Smith", "user_1"}
)
-- result.rows_affected = 1

-- Delete rows
sn.db.exec("DELETE FROM users WHERE id = ?", {"user_1"})
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sql` | string | yes | SQL statement to execute |
| `params` | table (array) | no | Positional parameters for `?` placeholders |

**Returns:** `{ok = true, rows_affected = N, last_insert_id = N}`

**Note:** Use `?` for parameter placeholders. Never concatenate user input into SQL strings -- this prevents SQL injection.

### sn.db.query(sql, params?)

Executes a SELECT query and returns all matching rows as an array of tables. Each table has keys matching the column names.

```lua
-- Query all rows
local users = sn.db.query("SELECT * FROM users")
-- Returns: [{id = "user_1", name = "Alice", email = "alice@example.com"}, ...]

-- Query with parameters
local users = sn.db.query(
  "SELECT * FROM users WHERE name LIKE ? ORDER BY created_at DESC",
  {"%Alice%"}
)

-- Iterate results
for _, user in ipairs(users) do
  ctx.log("info", user.id .. ": " .. user.name .. " <" .. user.email .. ">")
end

-- Empty result
local users = sn.db.query("SELECT * FROM users WHERE id = ?", {"nonexistent"})
-- Returns: {} (empty array, not nil)
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `sql` | string | yes | SELECT statement |
| `params` | table (array) | no | Positional parameters |

**Returns:** Array of tables. Each table has keys matching column names. Returns an empty array if no rows match.

### sn.db.query_one(sql, params?)

Convenience function that executes a SELECT query and returns only the first row. Useful when you expect exactly one result (e.g., looking up by primary key).

```lua
local user = sn.db.query_one(
  "SELECT * FROM users WHERE id = ?",
  {"user_1"}
)

if user then
  ctx.log("info", "Found: " .. user.name)
else
  ctx.log("info", "User not found")
end
```

**Returns:** A single table (row) or `nil` if no rows match.

### sn.db.transaction(fn)

Executes a function within a database transaction. If the function completes without error, the transaction is committed. If the function throws an error, the transaction is rolled back and the error is re-thrown.

```lua
-- Transfer funds atomically
sn.db.transaction(function()
  sn.db.exec(
    "UPDATE accounts SET balance = balance - ? WHERE id = ?",
    {100, "account_a"}
  )
  sn.db.exec(
    "UPDATE accounts SET balance = balance + ? WHERE id = ?",
    {100, "account_b"}
  )
  -- Both succeed or both fail
end)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `fn` | function | The function to execute within the transaction |

**Raises:** Re-throws any error from within the function (after rolling back).

### Schema Design Best Practices

1. **Always use `CREATE TABLE IF NOT EXISTS`.** Flows may run many times. Putting table creation in `setup()` with `IF NOT EXISTS` makes flows idempotent.

2. **Use TEXT for IDs.** SQLite does not have a native UUID type. Store IDs as TEXT. Generate them with `sn.crypto.random_bytes(16)`.

3. **Use ISO8601 for timestamps.** Store timestamps as TEXT in ISO8601 format (`sn.time.now()`). SQLite's `datetime()` functions work with this format.

4. **Add indexes for query patterns.** If you query by a column frequently, create an index:
   ```lua
   sn.db.exec("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
   ```

5. **Use transactions for multi-step writes.** Any time you need multiple INSERTs or UPDATEs to be atomic, wrap them in `sn.db.transaction()`.

6. **Keep databases small.** SQLite is not designed for massive datasets. If you are storing millions of rows, consider using PostgreSQL (`ctx.pg()`) instead.

### Database Isolation

Each kit gets its own database file:
- **Location:** `.sentinel/data/{kit-name}.db`
- **Access:** By default, only flows within the kit can access its database.
- **Cross-kit access:** If explicitly imported in `kit.yaml`, one kit can read another kit's database. This is unusual and should be avoided unless necessary.

---

## JSON (sn.json)

JSON encoding and decoding for converting between Lua tables and JSON strings. These functions are essential since most external APIs communicate in JSON.

### sn.json.enc(table)

Encodes a Lua table to a JSON string.

```lua
local data = {
  name = "Alice",
  age = 30,
  tags = {"admin", "user"},
  address = {
    city = "Portland",
    state = "OR"
  }
}

local json_str = sn.json.enc(data)
-- Returns: '{"address":{"city":"Portland","state":"OR"},"age":30,"name":"Alice","tags":["admin","user"]}'
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `table` | table | The Lua table to encode |

**Returns:** JSON string.

**Note:** Lua tables with string keys become JSON objects. Lua tables with integer keys become JSON arrays. Mixed tables (both string and integer keys) produce undefined results -- avoid them.

### sn.json.dec(string)

Decodes a JSON string into a Lua table.

```lua
local json_str = '{"name":"Alice","status":"active","count":42}'
local data = sn.json.dec(json_str)

ctx.log("info", data.name)    -- "Alice"
ctx.log("info", data.status)  -- "active"
ctx.log("info", tostring(data.count))  -- "42"
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `string` | string | The JSON string to decode |

**Returns:** Lua table.

**Raises:** Error if the JSON is malformed. Use `pcall` for untrusted input:

```lua
local ok, data = pcall(sn.json.dec, maybe_invalid_json)
if not ok then
  ctx.log("error", "Invalid JSON: " .. tostring(data))
  return {ok = false, error = "Invalid JSON input"}
end
```

**Null handling:** JSON `null` values are decoded to a special sentinel value `sn.null` (not Lua's `nil`, because `nil` would make the key disappear from the table entirely):

```lua
local json_str = '{"name":"Alice","middle":null}'
local data = sn.json.dec(json_str)

if data.middle == sn.null then
  ctx.log("info", "Middle name is explicitly null")
end

-- Note: data.nonexistent is nil (key does not exist)
-- data.middle is sn.null (key exists with null value)
```

---

## Cryptography (sn.crypto)

Cryptographic functions for hashing, signing, and generating random values. These are commonly used for webhook signature verification and token generation.

### sn.crypto.hmac_sha256(key, message)

Computes an HMAC-SHA256 signature. This is the standard mechanism for verifying webhook signatures from services like Stripe, GitHub, and Shopify.

```lua
-- Note: For webhook triggers, HMAC signature verification is handled
-- automatically by the harness when configured in the trigger definition.
-- You do not need to verify signatures manually in your flow code.
-- This example shows manual verification for non-webhook use cases.

local secret = ctx.secret("webhook_secret")
local body = sn.json.enc(ctx.params)  -- reconstruct body from parsed params
local computed_sig = sn.crypto.hmac_sha256(secret, body)

-- Compare with the signature from the incoming request
if computed_sig ~= ctx.req.headers["x-signature"] then
  ctx.log("warn", "Invalid webhook signature")
  return {ok = false, error = "Invalid signature"}
end
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `key` | string | The HMAC key (typically a shared secret) |
| `message` | string | The message to sign (typically the raw request body) |

**Returns:** Hex-encoded HMAC-SHA256 signature string.

### sn.crypto.sha256(data)

Computes a SHA-256 hash of the input data.

```lua
local hash = sn.crypto.sha256("password123")
-- Returns: hex-encoded hash string (64 characters)

ctx.log("info", "Hash: " .. hash)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `data` | string | Data to hash |

**Returns:** Hex-encoded SHA-256 hash string (64 characters).

**Note:** SHA-256 alone is not suitable for password hashing. For password storage, use a purpose-built algorithm like bcrypt or argon2 (via an external API).

### sn.crypto.random_bytes(n)

Generates cryptographically secure random bytes using the operating system's secure random number generator.

```lua
local token = sn.crypto.random_bytes(32)
-- Returns: 64-character hex string (32 bytes encoded as hex)

local short_id = sn.crypto.random_bytes(8)
-- Returns: 16-character hex string

ctx.log("info", "Generated token: " .. token)
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `n` | integer | Number of random bytes to generate |

**Returns:** Hex-encoded string of `2 * n` characters.

**Use cases:** Generating session tokens, creating unique identifiers, producing nonces for cryptographic operations.

---

## Time (sn.time)

Time utilities for getting the current time.

### sn.time.now()

Returns the current time as an ISO8601 string in UTC.

```lua
local ts = sn.time.now()
-- Returns: "2026-02-10T12:00:00Z"

ctx.log("info", "Current time: " .. ts)
```

**Returns:** ISO8601 timestamp string in UTC (e.g., `"2026-02-10T12:00:00Z"`).

**Note:** `os.date` is also available in the sandbox for more flexible time formatting:

```lua
local formatted = os.date("%Y-%m-%d %H:%M:%S")
```

---

## Sleep (sn.sleep)

### sn.sleep(seconds)

Pauses flow execution for the specified number of seconds. Useful for rate limiting, retry backoff, and polling loops.

```lua
-- Wait 2 seconds between retries
for i = 1, 5 do
  ctx.log("info", "Attempt " .. i)
  local resp = sn.http.get("https://api.example.com/status")
  if resp.status == 200 then
    return {ok = true}
  end
  sn.sleep(2)
end
return {ok = false, error = "All retries exhausted"}
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `seconds` | number | Number of seconds to sleep (can be fractional, e.g., `0.5`) |

**Limits:**
- **Maximum sleep:** 300 seconds (5 minutes). Sleeping longer raises an error.
- **Flow timeout:** Flows have a default execution timeout of 30 seconds (configurable per flow). Sleeping counts against this timeout. If your flow needs to sleep for extended periods, increase the flow timeout in the kit configuration.

---

## AI (sn.ai)

Harness-provided LLM API. Providers are configured by operators through the dashboard (API Library + Vault); flows call `sn.ai` and do not make raw provider HTTP requests.

`sn.ai.enabled` is a boolean reflecting release controls. When AI is disabled, every function returns `nil` and an error string `"sn.ai is disabled"`.

### Error convention

All `sn.ai` call functions return `(result, err)` on failure:

```lua
local resp, err = sn.ai.chat({ messages = { { role = "user", content = "hi" } } })
if err then
  error(err)
end
```

### sn.ai.chat(params)

Chat completion with optional tool calling. When `tools` are supplied, the harness runs a bounded tool loop: the model may request tools, Lua targets execute, results are fed back, and the loop repeats until the model finishes or limits are hit.

```lua
local function get_status(args)
  return { service = args.service, status = "healthy" }
end

local resp, err = sn.ai.chat({
  model = "claude-sonnet-4",
  provider = "anthropic",          -- optional; defaults from API Library
  system = "You are a concise ops assistant.",
  messages = {
    sn.ai.msg.user("Is billing healthy?"),
  },
  tools = {
    {
      name = "get_status",
      description = "Return service health",
      parameters = {                -- alias: input_schema
        type = "object",
        properties = {
          service = { type = "string", description = "Service name" },
        },
        required = { "service" },
      },
      target = get_status,          -- Lua function, or dotted path string
    },
  },
  max_tokens = 1024,
  temperature = 0.2,
})
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `messages` | array | Chat messages (`role`, `content`; optional `tool_call_id` for tool results) |
| `model` | string | Model id (optional; uses API Library default) |
| `provider` | string | Provider id (optional) |
| `system` | string | System prompt (optional) |
| `tools` | array | Tool definitions (see example above) |
| `tool_choice` | string | `auto`, `required`, `none`, or a tool name |
| `max_tokens` | integer | Max output tokens |
| `temperature` | number | Sampling temperature |
| `stop` | array | Stop sequences |
| `max_iterations` | integer | Max tool-loop rounds (default `8`) |
| `max_turns` | integer | Alias for `max_iterations` |
| `tool_timeout_ms` | integer | Per-tool timeout in ms (default `10000`) |
| `max_tool_payload_bytes` | integer | Max encoded tool-result payload (default `65536`) |

**Tool `target`:** A Lua function, or a string resolved to a global function (e.g. `"sn.md.my_tools.fetch"`). The function receives one table (`args`) and must return `(result, err)` where `err` is `nil` on success.

**Returns:** Table with `message`, `usage`, `finish_reason`, `model`, and optional `tool_calls`.

| Field | Description |
|-------|-------------|
| `message` | `{ role, content, tool_call_id?, name? }` |
| `tool_calls` | Array of `{ id, name, args }` when the model requested tools |
| `usage` | `{ input_tokens, output_tokens, total_tokens, estimated_cost_cents, cost_available }` |
| `finish_reason` | e.g. `stop`, `tool_use`, `max_tokens` |

#### Tool-loop error classes

When a tool call fails, the harness encodes structured errors in the tool-result payload fed back to the model (`executeToolCalls` in `internal/ai/lua_api.go`). Each failed tool appears as:

```json
{
  "id": "call-1",
  "name": "get_status",
  "ok": false,
  "error": {
    "class": "runtime",
    "message": "tool get_status failed: boom"
  }
}
```

| Class | Trigger | Operator hint |
|-------|---------|---------------|
| `not_found` | Tool name missing from the `tools` map, or `target` is nil | Fix tool registration / `target` binding in the flow |
| `timeout` | `context.DeadlineExceeded` or harness `ErrTimeout` during `callLuaTool` | Increase `tool_timeout_ms` or shorten tool work |
| `runtime` | Lua target returns `(nil, err)`, protected call fails, or other execution error | Inspect tool Lua logic and flow logs |

Golden fixtures and CI regression: `internal/ai/testdata/tool_loop_error_fixtures.json`, `go test ./internal/ai -run TestToolLoopErrorGoldenFixtures`. See also [RAG & eval guide](/rag-evaluation).

Failed tool rounds record a `tool_loop` trace with `error_class`, `error_message`, and per-class counts in trace metadata (Agents → Traces).

### sn.ai.complete(params)

Single-prompt completion (no tool loop).

```lua
local resp, err = sn.ai.complete({
  prompt = "Summarize: " .. sn.json.enc(metrics),
  model = "gpt-4o-mini",
  max_tokens = 500,
})
-- resp.text, resp.finish_reason, resp.usage
```

Alias: `sn.ai.cmp`.

### sn.ai.stream(params)

Streaming chat. Accepts the same parameters as `sn.ai.chat` plus `on_chunk`:

```lua
local resp, err = sn.ai.stream({
  messages = { { role = "user", content = "Write a haiku" } },
  on_chunk = function(chunk)
    ctx.log("info", chunk.delta or "")
  end,
})
```

Each chunk is `{ delta, done, finish_reason? }`. Returns the final aggregated response in the same shape as `sn.ai.chat`.

### sn.ai.embed(params)

Generate embedding vectors.

```lua
local resp, err = sn.ai.embed({
  input = { "first sentence", "second sentence" },  -- or a single string
  model = "text-embedding-3-small",
  provider = "openai",
})
-- resp.embeddings[1] is an array of floats; resp.model; resp.usage.tokens
```

Alias: `sn.ai.emb`.

### sn.ai.count_tokens(text)

Estimates token count for a string. Returns a number.

```lua
local n = sn.ai.cnt("hello world")
```

### sn.ai.msg.*

Message helpers for building `messages` arrays:

| Function | Returns |
|----------|---------|
| `sn.ai.msg.user(content)` | `{ role = "user", content = ... }` |
| `sn.ai.msg.asst(content)` | `{ role = "assistant", content = ... }` |
| `sn.ai.msg.sys(content)` | `{ role = "system", content = ... }` |
| `sn.ai.msg.tool(id, content)` | `{ role = "tool", tool_call_id = id, content = ... }` |

### Agent flow pattern

Guard when AI may be disabled; compose memory and tools in kit logic:

```lua
function main(params)
  if not (sn.ai and sn.ai.enabled) then
    return { ok = false, err = "AI_DISABLED" }
  end

  local messages = {
    { role = "system", content = "You are a support agent." },
    { role = "user", content = params.message or "Hello" },
  }

  local resp, err = sn.ai.chat({ messages = messages, model = params.model })
  if err then
    return nil, err
  end

  return { ok = true, reply = resp.message.content }
end
```

Operator setup: enable `sn.ai` on the Agents dashboard, register an AI-capable API Library vendor, and store the API key in Vault. Step-by-step smoke: [`21-AGENTIC-AI-OPERATOR.md`](/agentic-ai-operator). Architecture: [`specs/agentic-ai.md`](https://github.com/ndx-au/sentinel/blob/main/specs/agentic-ai.md).

---

## Memory (sn.memory)

Episodic conversational memory backed by harness SQLite storage. Enable from the Agents dashboard (Memory tab). Isolated by `agent_id` and `session_id`.

`sn.memory.enabled` reflects release and settings. When disabled, functions return `nil, "sn.memory is disabled"`.

### sn.memory.add(agent_id, session_id, role, content)

Append a message to a session.

```lua
local added, err = sn.memory.add("support-bot", "sess-42", "user", "Reset my password")
-- added.message_id, added.token_count
```

### sn.memory.get_recent(agent_id, session_id, opts?)

Returns an array of `{ role, content, tool_call_id? }` messages, most recent retained up to `opts.limit` (default `20`).

```lua
local history, err = sn.memory.get_recent("support-bot", "sess-42", { limit = 10 })
```

### sn.memory.compact(agent_id, session_id)

Runs compaction for a session. Returns token counts, optional summary, and checkpoint metadata:

```lua
local result, err = sn.memory.compact("support-bot", "sess-42")
-- result.before_tokens, result.after_tokens, result.removed_count,
-- result.checkpoint_id?, result.summary?, result.last_checkpoint?
```

### sn.memory.cleanup()

Deletes expired sessions per TTL settings. Returns `{ deleted_sessions }`.

### sn.memory.status(agent_id?, session_id?)

Returns configuration and, when ids are provided, session stats (`exists`, `message_count`, `token_count`, `compact_count`, `last_checkpoint`, `lineage_depth`).

Kit wrappers (e.g. `sn.md.agent_memory` in `sn.core-agent`) add validation and defaults on top of this API.

---

## RAG (sn.rag)

Document ingestion and retrieval backed by PostgreSQL (with pgvector when configured). Initialize and enable RAG from the dashboard RAG page before calling these functions.

`sn.rag.enabled` reflects release and settings. When disabled, functions return `nil, "sn.rag is disabled"` (or `false, err` for `delete`).

### sn.rag.search(params)

Search indexed documents. The harness picks lexical or hybrid (RRF) retrieval based on runtime configuration.

```lua
local docs, err = sn.rag.search({
  query = "database failover runbook",
  limit = 5,
  min_score = 0.2,
  tags = { "ops", "runbook" },
  updated_after = "2026-01-01T00:00:00Z",
  project_scope = "my-project",   -- optional; defaults from execution context
  agent_scope = "support-bot",
})
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search text (required) |
| `limit` | integer | Max results |
| `min_score` | number | Minimum relevance score |
| `source_refs` | array | Filter by exact source refs |
| `source_prefixes` | array | Filter by source ref prefix |
| `tags` | array | Filter by document tags |
| `modalities` | array | Filter by modality |
| `updated_after` / `updated_before` | string | ISO8601 time window |
| `project_scope` / `agent_scope` | string | ACL scope overrides |

**Returns:** `{ query, summary, results }` where each result includes `document_id`, `chunk_id`, `title`, `source_ref`, `content`, `citation`, `score`, `metadata`, and scope fields.

### sn.rag.upsert(params)

Insert or update a document (chunked and embedded by the harness).

```lua
local resp, err = sn.rag.upsert({
  document_id = "runbook-db-failover",
  title = "DB Failover",
  source_ref = "docs/db-failover.md",
  content = "Step 1: verify replica lag...",
  metadata = { category = "ops" },
})
-- resp.document_id, resp.chunk_count
```

### sn.rag.delete(document_id) / sn.rag.hard_delete(document_id)

Permanently remove a document. Returns `true` on success, or `false, err` on failure.

### sn.rag.soft_delete(document_id)

Mark a document deleted without removing rows immediately. Returns lifecycle metadata.

### sn.rag.reembed(document_id)

Re-chunk and re-embed a document. Returns `{ document_id, action, lifecycle_state, chunk_count, updated_at }`.

### RAG + chat pattern

```lua
local docs, err = sn.rag.search({ query = params.question, limit = 5 })
if err then
  return nil, err
end

local context = ""
for i, row in ipairs(docs.results or {}) do
  context = context .. "\n[" .. i .. "] " .. (row.content or "")
end

local resp, err = sn.ai.chat({
  messages = {
    { role = "system", content = "Answer using the provided docs. Cite sources." },
    { role = "user", content = params.question .. "\n\nDocs:" .. context },
  },
})
```

---

## Built-in Modules (sn.md)

Modules are shared Lua libraries that any flow can call. They are defined in a kit's `md/` directory and register whichever public tables/functions they choose under `sn.md.*`.

### How Modules Work

Modules are Lua files in a kit's `md/` directory. They typically expose named helper tables such as `sn.md.persona_templates`, `sn.md.agent_memory`, or `sn.md.agent`.

### Starter-Kit Module Examples

```lua
local prompt = sn.md.persona_templates.compose({
  name = "Support Agent",
  mission = "Close tickets with clear next steps."
})

local recent = sn.md.agent_memory.get_recent({
  agent_id = "agent-1",
  session_id = "session-1",
  limit = 10,
})

local result, err = sn.md.agent.run({
  agent_id = "agent-1",
  session_id = "session-1",
  message = "Summarize the failover runbook.",
  persona = { name = "Support Agent", mission = "Close tickets with clear next steps." },
  rag = { limit = 5 },
})
```

---

## Built-in Connectors (sn.cn)

Connectors are pre-built integrations that provide standardized access to external services. They are defined in a kit's `cn/` directory and register public tables/functions under `sn.cn.*`.

### How Connector Namespacing Works

Connector names are defined by the connector itself. Current starter-kit examples include `sn.cn.http_json` and `sn.cn.rag_ingest`.

### Starter-Kit Connector Examples

```lua
local resp, err = sn.cn.http_json.call({
  method = "POST",
  url = "https://api.example.com/data",
  body = {key = "value"}
})

local result, err = sn.cn.rag_ingest.call({
  title = "Deploy Notes",
  source_ref = "docs/deploy-notes.md",
  content = "blue green rollout checklist",
})
```

### SMTP Connector (sn.cn.smtp)

Sends email via SMTP. Useful for notifications and alerts.

```lua
sn.cn.smtp.exec({
  server = "smtp.gmail.com",
  port = 587,
  from = "bot@example.com",
  password = ctx.secret("gmail_app_password"),
  to = "admin@example.com",
  subject = "Alert: Flow Failed",
  body = "The order processing flow failed at " .. sn.time.now()
})
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `server` | string | yes | SMTP server hostname |
| `port` | integer | yes | SMTP port (587 for TLS, 465 for SSL) |
| `from` | string | yes | Sender email address |
| `password` | string | yes | SMTP password or app-specific password |
| `to` | string | yes | Recipient email address |
| `subject` | string | yes | Email subject line |
| `body` | string | yes | Email body (plain text) |

### File Connector (sn.cn.file)

Performs controlled file operations within the SRE directory. This is the sanctioned way to write files from within the sandbox.

```lua
-- Write a file (overwrite mode)
sn.cn.file.exec({
  mode = "overwrite",
  path = "sn.log/output/report.jsonl",
  content = sn.json.enc({test = "result"}) .. "\n"
})

-- Append to a file
sn.cn.file.exec({
  mode = "append",
  path = "sn.log/output/report.jsonl",
  content = sn.json.enc({test = "another result"}) .. "\n"
})
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `mode` | string | yes | `"overwrite"` to replace file contents, `"append"` to add to end |
| `path` | string | yes | File path relative to SRE root |
| `content` | string | yes | Content to write |

**Returns:** `{written = true, bytes = N}` on success.

---

## Core Functions (sentinel)

The `sentinel` global provides core harness functions.

### sentinel.emit(event_name, data?)

Emits an event to the Sentinel event bus. Any flow with an event trigger matching this event name will be executed with the provided data.

```lua
-- Simple event
sentinel.emit("order.completed", {
  order_id = "order_123",
  total = 99.99,
  customer = "alice@example.com"
})

-- Wildcard matching: flows listening for "order.*" will be triggered

-- Event without data
sentinel.emit("system.maintenance_start")
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `event_name` | string | yes | Event name. Supports dot-separated namespacing. Subscribers can use `*` wildcards. |
| `data` | table | no | Event payload. Passed to the triggered flow as parameters. |

**Use cases:**
- Decoupling flows: An order flow emits `order.completed`, and separate flows handle notifications, analytics, and inventory updates independently.
- Fan-out: One event triggers multiple flows simultaneously.
- Cross-kit communication: A flow in one kit emits an event that triggers flows in other kits.

---

## CMS (sn.cms)

The CMS API provides access to parsed Markdown content from the kit's `ct/` directory. Markdown files are parsed into structured data with frontmatter metadata, a preamble, and a recursive section tree. Content is cached in memory and automatically refreshed when files change.

### Availability

`sn.cms` is only available in flows belonging to kits that have a `ct/` content directory. If you call `sn.cms` functions from a flow in a kit without a `ct/` directory, all calls safely return `nil, "cms: cache not initialized"` -- they do not throw errors.

### Kit Scoping

`sn.cms` is automatically scoped to the calling flow's own kit. A flow in `acme.blog` can only access content from `acme.blog/ct/`, not from other kits. This is enforced by the harness and cannot be bypassed.

### ctx Guard

During harness startup (flow registration dry-run), `ctx` is `nil`. If your flow has any top-level code that accesses `ctx`, guard it:

```lua
if ctx and ctx.kit then
  -- safe to use ctx
end
```

### sn.cms.get(slug)

Retrieves a single content entry by its slug.

```lua
local entry, err = sn.cms.get("hello-world")
if err then
  ctx.log("warn", "CMS error: " .. err)
  return {ok = false, error = err}
end

-- Access frontmatter
ctx.log("info", "Title: " .. entry.frontmatter.title)
ctx.log("info", "Date: " .. entry.frontmatter.date)
ctx.log("info", "Tags: " .. table.concat(entry.frontmatter.tags, ", "))

-- Access preamble (HTML before first heading)
ctx.log("info", "Preamble: " .. entry.preamble)

-- Access sections
for slug, section in pairs(entry.sections) do
  ctx.log("info", "Section: " .. section.title .. " (level " .. section.level .. ")")
end
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `slug` | string | Content slug. Either the `slug` field from YAML frontmatter or the filename without `.md`. Supports path slugs like `"tutorials/getting-started"`. |

**Returns:** `(entry_table, nil)` on success, `(nil, error_string)` on failure.

**Entry table fields:**

| Field | Type | Description |
|-------|------|-------------|
| `frontmatter` | table | Parsed YAML frontmatter (see fields below) |
| `preamble` | string | Rendered HTML from content before the first heading. Empty string if the document starts with a heading. |
| `sections` | table | Map of sections keyed by slug (recursive structure) |
| `full_html` | string | Complete document HTML. Only populated when `cms_full_html: true` is set in `kit.yaml`. Empty string otherwise. |
| `warnings` | array | Validation warning tables `{field, message}` for any frontmatter issues |
| `source_path` | string | Absolute path to the source `.md` file on disk |
| `mtime` | string | ISO8601 modification time of the source file |

**Frontmatter table fields:**

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Document title |
| `slug` | string | Content slug (canonical identifier) |
| `date` | string | Publication date (RFC3339 or YYYY-MM-DD) |
| `description` | string | Short description |
| `tags` | array | Tag strings |
| `agent_context` | table | AI agent context block. Available in Lua only -- stripped from `/cm/*` REST API responses. |
| `meta` | table | Any unrecognized frontmatter fields |

**Section structure:** Each section in the `sections` map contains:

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Original heading text |
| `slug` | string | URL-safe slug, scoped to parent, deduplicated with `-2`, `-3` suffixes |
| `level` | integer | Heading level (1-6) |
| `html` | string | Rendered HTML of content directly under this heading |
| `sections` | table | Nested child sections (same recursive structure) |

### sn.cms.list(prefix?)

Lists all content slugs for the calling kit.

```lua
-- List all content
local slugs, err = sn.cms.list()
if err then
  ctx.log("warn", "CMS error: " .. err)
  return {ok = false}
end

ctx.log("info", "Found " .. #slugs .. " content entries")
for _, slug in ipairs(slugs) do
  ctx.log("info", "  - " .. slug)
end

-- List only blog posts (by prefix)
local blog_slugs, err = sn.cms.list("blog/")
-- Returns only slugs starting with "blog/": "blog/hello-world", "blog/intro", etc.
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prefix` | string | no | Filter slugs by prefix. Only slugs starting with this prefix are returned. |

**Returns:** `(slugs_array, nil)` on success, `(nil, error_string)` on failure.

### Complete CMS Examples

**Blog index flow -- lists all posts and returns metadata:**
```lua
function main(params)
  local slugs, err = sn.cms.list()
  if err then
    return {ok = false, error = err}
  end

  local posts = {}
  for _, slug in ipairs(slugs) do
    local entry, getErr = sn.cms.get(slug)
    if entry then
      table.insert(posts, {
        slug = slug,
        title = entry.frontmatter.title,
        date = entry.frontmatter.date,
        description = entry.frontmatter.description,
        tags = entry.frontmatter.tags,
      })
    end
  end

  -- Sort by date descending
  table.sort(posts, function(a, b)
    return (a.date or "") > (b.date or "")
  end)

  return {ok = true, posts = posts, total = #posts}
end
```

**Blog post render flow -- handles not-found gracefully:**
```lua
function main(params)
  -- Guard: ctx is nil during harness registration dry-run
  if not ctx then return end

  local slug = params and params.slug
  if not slug or slug == "" then
    return {ok = false, error = "slug required"}
  end

  local entry, err = sn.cms.get(slug)
  if err then
    ctx.log("info", "CMS lookup failed for slug=" .. slug .. ": " .. err)
    return {ok = false, not_found = true}
  end

  return {
    ok = true,
    title = entry.frontmatter.title,
    date = entry.frontmatter.date,
    description = entry.frontmatter.description,
    preamble = entry.preamble,
    sections = entry.sections,
    full_html = entry.full_html,
  }
end
```

**Cross-reference:** CMS content is also accessible via the REST API. See [HTTP API Reference: Content (CMS)](/api-reference#content-cms) for external endpoint documentation.

---

## Accessing Services from Lua

Beyond the built-in APIs documented above, Sentinel flows can access additional services that implement the Triple-Access Pattern. These services expose Lua APIs alongside their CLI and REST interfaces, ensuring consistent behavior across all access methods.

### API Library Service (sn.lib)

The API library service manages vendor definitions, endpoints, and call templates. It is accessible from Lua flows:

```lua
-- List vendors
local vendors = sn.lib.vendor_list({limit = 10, offset = 0})
local data = sn.json.dec(vendors)

-- Create an endpoint
local ep = sn.lib.endpoint_create({
  vendor_id = "openai",
  name = "Chat Completions",
  path = "/v1/chat/completions",
  method = "POST"
})

-- Flexible query
local result = sn.lib.query({
  entity_type = "endpoint",
  filter = {vendor_id = "openai"},
  limit = 50
})

-- Bulk import
sn.lib.import(sn.json.enc({
  vendors = {...},
  endpoints = {...},
  calls = {...}
}))
```

### Building New Services

If you are building a new service that needs to be accessible from CLI, REST API, and Lua flows simultaneously, follow the [Triple-Access Pattern](/triple-access-pattern) guide.

---

## Error Handling

Lua errors in flows are caught by the harness and recorded in the execution log. However, for robust flows, you should handle errors explicitly using `pcall` (protected call).

### Basic Error Handling with pcall

`pcall` calls a function in protected mode. If the function succeeds, `pcall` returns `true` followed by the function's return values. If the function throws an error, `pcall` returns `false` followed by the error message.

```lua
-- Dangerous: if JSON is invalid, the flow crashes
local data = sn.json.dec(untrusted_input)

-- Safe: handle the error gracefully
local ok, result = pcall(function()
  return sn.json.dec(untrusted_input)
end)

if not ok then
  ctx.log("error", "JSON parse error: " .. tostring(result))
  return {ok = false, error = "Invalid JSON"}
end

-- result now contains the decoded data
ctx.log("info", "Parsed successfully: " .. result.name)
```

### Common pcall Patterns

**Wrapping HTTP calls:**
```lua
local ok, resp = pcall(function()
  return sn.http.get("https://unreliable-api.example.com/data", {timeout_ms = 5000})
end)

if not ok then
  ctx.log("error", "HTTP request failed: " .. tostring(resp))
  return {ok = false, error = "API unreachable"}
end

if resp.status ~= 200 then
  ctx.log("warn", "API returned " .. resp.status)
  return {ok = false, error = "API error: " .. resp.status}
end
```

**Wrapping secret access:**
```lua
local ok, token = pcall(function() return ctx.secret("optional_integration") end)
if not ok then
  ctx.log("info", "Optional integration not configured, skipping")
  return {ok = true, skipped = true}
end
```

---

## Common Patterns

### Retry Logic with Exponential Backoff

```lua
function retry(fn, max_attempts, base_delay)
  local attempt = 0
  local last_err = nil

  while attempt < max_attempts do
    attempt = attempt + 1
    local ok, result = pcall(fn)

    if ok then
      return result
    end

    last_err = result
    ctx.log("warn", "Attempt " .. attempt .. " failed: " .. tostring(last_err))

    if attempt < max_attempts then
      local delay = base_delay * (2 ^ (attempt - 1))
      if delay > 30 then delay = 30 end  -- cap at 30 seconds
      ctx.log("info", "Retrying in " .. delay .. " seconds...")
      sn.sleep(delay)
    end
  end

  error("All " .. max_attempts .. " attempts failed. Last error: " .. tostring(last_err))
end

function main(params)
  local result = retry(function()
    local resp = sn.http.get("https://flaky-api.example.com/data", {timeout_ms = 5000})
    if resp.status ~= 200 then
      error("HTTP " .. resp.status)
    end
    return sn.json.dec(resp.body)
  end, 3, 2)

  return {ok = true, data = result}
end
```

### Batch Processing

```lua
function main(params)
  local items = sn.db.query("SELECT * FROM queue WHERE status = 'pending' LIMIT 50")
  ctx.log("info", "Processing " .. #items .. " items")

  local succeeded = 0
  local failed = 0

  for _, item in ipairs(items) do
    local ok, err = pcall(function()
      -- Process each item
      local resp = sn.http.post(
        "https://api.example.com/process",
        sn.json.enc({id = item.id, data = item.data}),
        {timeout_ms = 10000}
      )

      if resp.status ~= 200 then
        error("API error: " .. resp.status)
      end

      sn.db.exec("UPDATE queue SET status = 'completed' WHERE id = ?", {item.id})
    end)

    if ok then
      succeeded = succeeded + 1
    else
      failed = failed + 1
      ctx.log("error", "Failed to process item " .. item.id .. ": " .. tostring(err))
      sn.db.exec("UPDATE queue SET status = 'failed', error = ? WHERE id = ?",
        {tostring(err), item.id})
    end
  end

  ctx.log("info", "Batch complete: " .. succeeded .. " succeeded, " .. failed .. " failed")
  return {ok = true, succeeded = succeeded, failed = failed, total = #items}
end
```

### Pagination (Fetching All Pages from an External API)

```lua
function main(params)
  local all_items = {}
  local page = 1
  local per_page = 100

  while true do
    local resp = sn.http.get(
      "https://api.example.com/items?page=" .. page .. "&per_page=" .. per_page,
      {
        headers = {Authorization = "Bearer " .. ctx.secret("api_token")},
        timeout_ms = 10000
      }
    )

    if resp.status ~= 200 then
      error("API error on page " .. page .. ": HTTP " .. resp.status)
    end

    local data = sn.json.dec(resp.body)

    for _, item in ipairs(data.items) do
      table.insert(all_items, item)
    end

    ctx.log("info", "Fetched page " .. page .. " (" .. #data.items .. " items)")

    -- Check if there are more pages
    if #data.items < per_page then
      break
    end

    page = page + 1
    sn.sleep(0.5) -- Rate limit courtesy
  end

  ctx.log("info", "Total items fetched: " .. #all_items)
  return {ok = true, items = all_items, total = #all_items}
end
```

### Idempotent Processing (Deduplication)

```lua
function setup()
  sn.db.exec([[
    CREATE TABLE IF NOT EXISTS processed_events (
      event_id TEXT PRIMARY KEY,
      processed_at TEXT
    )
  ]])
end

function main(params)
  local event_id = params and params.event_id

  -- Check if already processed
  local existing = sn.db.query_one(
    "SELECT event_id FROM processed_events WHERE event_id = ?",
    {event_id}
  )

  if existing then
    ctx.log("info", "Event " .. event_id .. " already processed, skipping")
    return {ok = true, skipped = true}
  end

  -- Process the event
  -- ... your logic here ...

  -- Mark as processed
  sn.db.exec(
    "INSERT INTO processed_events (event_id, processed_at) VALUES (?, ?)",
    {event_id, sn.time.now()}
  )

  return {ok = true, processed = true}
end
```

---

## Debugging Tips

1. **Use `ctx.log("debug", ...)` liberally.** Debug logs are hidden by default in the Dashboard but visible when streaming logs with `?lv=debug`. Add debug logs for variable values, function entry/exit, and decision points.

2. **Serialize tables for logging.** Lua cannot print tables directly. Use `sn.json.enc()` to log table contents:
   ```lua
   ctx.log("debug", "Response data: " .. sn.json.enc(data))
   ```

3. **Use `pcall` to isolate failures.** When debugging, wrap suspect code in `pcall` to catch errors without crashing the entire flow:
   ```lua
   local ok, err = pcall(function()
     -- code that might fail
   end)
   if not ok then
     ctx.log("error", "Failed: " .. tostring(err))
   end
   ```

4. **Check `ctx.trigger_type`.** If your flow behaves differently depending on the trigger, log the trigger type to verify you are in the right code path:
   ```lua
   ctx.log("info", "Triggered by: " .. ctx.trigger_type)
   ```

5. **Stream logs during development.** While developing a flow, keep a terminal open with:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8080/lg?lv=debug&follow=true"
   ```
   This gives you a real-time view of all log output as you trigger flows.

6. **Inspect the execution result.** After running a flow, check the execution details:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/ex/{exec_id}
   ```
   The `err` field contains the error message if the flow failed.

7. **Use the Dashboard.** The Dashboard's execution view shows logs, timing, and results in a graphical interface. It is often easier to debug visually than via curl commands.

---

## Sandbox Restrictions (Complete Reference)

For security, the following Lua standard library functions are **NOT available** in the sandbox:

| Removed | Reason |
|---------|--------|
| `io.*` | File I/O -- use `sn.cn.file.exec()` instead |
| `os.execute`, `os.remove`, `os.rename`, `os.tmpname`, `os.getenv`, `os.exit` | System commands -- too dangerous |
| `os.date` | **Available** (exception) -- safe for time formatting |
| `debug.*` | Debug introspection -- could inspect harness internals |
| `package.*` | Module loading -- prevents loading untrusted libraries |
| `load()`, `loadstring()` | Dynamic code evaluation -- prevents code injection |
| `dofile()`, `require()` | File loading -- sandbox escape vector |

**Why these restrictions exist:** Flows are user-authored code running on your server. Without sandboxing, a malicious or buggy flow could read your secrets, delete files, execute shell commands, or exfiltrate data. The sandbox provides a safe execution environment while still giving flows access to powerful, auditable APIs.

**What to use instead:**
- Need file I/O? Use `sn.cn.file.exec()`.
- Need to call an external service? Use `sn.http.*`.
- Need to store data? Use `sn.db.*` or `ctx.pg()`.
- Need shared logic? Put it in a module (`sn.md.*`).
- Need time formatting? Use `os.date()` (it is available).

---

## Best Practices

1. **Always use transactions for multi-step database operations.** If two writes need to succeed or fail together, wrap them in `sn.db.transaction()`.

2. **Validate webhook signatures.** When receiving webhooks from external services, always verify the HMAC signature before processing the payload.

3. **Log important operations.** Use `ctx.log()` at appropriate levels. This is your primary debugging tool in production.

4. **Set reasonable HTTP timeouts.** Always specify `timeout_ms` for HTTP requests. The default of 30 seconds is often too long. A timeout of 5-10 seconds is reasonable for most API calls.

5. **Handle errors gracefully with pcall.** Any operation that might fail (JSON parsing, HTTP requests, database queries, secret retrieval) should be wrapped in `pcall` if the flow needs to continue or return a meaningful error.

6. **Never hardcode secrets.** Store all tokens, passwords, and API keys in the vault via `POST /sc` and access them with `ctx.secret("name")`.

7. **Type-check form data.** Even though form field type coercion is applied automatically, verify that the data matches your expectations before processing.

8. **Batch database writes.** Use `sn.db.transaction()` for inserting multiple rows. This is faster (one disk sync instead of many) and atomic.

9. **Name WebSocket connections descriptively.** Use names that describe the remote service (e.g., `"discord"`, `"slack-bot"`, `"status-monitor"`). Always close connections in `cleanup()`.

10. **Create tables in setup().** Put `CREATE TABLE IF NOT EXISTS` statements in `setup()` so your database schema is always ready before `main()` runs. The `IF NOT EXISTS` makes it idempotent.
