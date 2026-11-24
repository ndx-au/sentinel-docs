# Sentinel Invocation & Orchestration Surfaces

Use this reference when designing how an AI agent or external system invokes, observes, or manages Sentinel.

Public docs: [MCP Agent Integration](https://docs.ndx-sentinel.com/mcp-agent-integration), [HTTP API Reference](https://docs.ndx-sentinel.com/api-reference), [Harness HTTP Routes](https://docs.ndx-sentinel.com/harness-http-routes), [CLI Reference](https://docs.ndx-sentinel.com/cli-reference).

---

## 1. MCP Sidecar (Preferred for Connected AI Agents)

Start with:
```bash
sentinel harness start -p /path/to/sre --mcp --mcp-risk read,validate
# Full control plane (dev/trusted only):
sentinel harness start -p /path/to/sre --mcp --mcp-risk all
```

- **Default bind/port:** `127.0.0.1`, port `api.port + 100` (e.g. `8080` → `8180`).
- **Transports:** Streamable HTTP (`http://127.0.0.1:8180/`) or stdio bridge (`sentinel mcp stdio --upstream http://127.0.0.1:8180 --token YOUR_API_TOKEN` or `--sign --keypair-name <name>`).
- **Signing proxy (Ed25519):** `sentinel mcp proxy --upstream http://127.0.0.1:8180 --keypair-name <name>`.
- **Canonical tool names only** by default (`sentinel_*` aliases are off unless `--mcp-aliases` / `mcp.aliases: true`).

### MCP Risk Classes

| Risk Class | Tools |
|---|---|
| `read` | `harness_health`, `project_info`, `capabilities`, `license_status`, `flows_list`, `flow_get`, `execution_get`, `executions_list`, `execution_logs`, `kits_list`, `kit_get`, `triggers_list`, `secrets_list` *(names only)*, `source_read`, `connectors_list`, `modules_list`, `git_status`, `git_diff` |
| `validate` | `validate`, `diagnose` |
| `execute` | `flow_run`, `event_emit` |
| `write` | `scaffold_create` |
| `admin` | `harness_reload_sre`, `kit_reload`, `kit_enable`, `kit_disable` |

> **Wait behavior:** `flow_run` waits for terminal completion by default (`wait: true`, default `timeout_ms: 60000`, cap `300000`). On timeout it returns `{execution_id, timed_out: true}` rather than a tool error. Poll the returned `execution_id` with `execution_get` / `execution_logs` rather than re-submitting. Pass `wait: false` to queue-and-return.
>
> **After scaffolding:** Call `kit_reload` or `harness_reload_sre` (requires `admin`) before running newly created flows.

### MCP Resources (Prefer Before `source_read`)

- `sentinel://project/summary`, `sentinel://project/sentinel.yaml`, `sentinel://project/events.yaml`
- `sentinel://harness/status`, `sentinel://harness/license` *(never includes license key)*
- `sentinel://kits`, `sentinel://flows`, `sentinel://executions/recent`, `sentinel://diagnostics/latest`
- Templates: `sentinel://kit/{kit}/file/{+path}`, `sentinel://flow/{flow_id}`, `sentinel://execution/{execution_id}`

---

## 2. HTTP REST API (Brevity Regime)

- **Default base URL:** `http://localhost:8080`
- **Canonical flow execution route:** `POST /fl/{ns}.{name}/{flow}/run` (colon IDs like `ns-name:flow` are a legacy fallback).
- **Queued execution response:** Flow execution is asynchronous and returns:
  ```json
  {
    "id": "exec_abc123",
    "fid": "sn-core-agent:assistant",
    "status": "queued"
  }
  ```
  Capture `id` and poll `GET /ex/{id}` or stream `GET /ex/{id}/lg` (SSE) until a terminal status (`completed`, `failed`, `timeout`).
- **Error handling:** Handle HTTP transport failures and route-specific non-200 statuses (for example `403`/`429` on webhooks, `404`/`405`/`5xx`, or SSE disconnects) **separately** from JSON application errors (`{"ok": false, "err": "ERROR_CODE", "msg": "..."}`) which Sentinel API routes return in an HTTP 200 body. Do not require `ok: true` on endpoints like `POST /fl/.../run` whose documented success payload is `{id, fid, status}`.
- **Authentication:** `Authorization: Bearer YOUR_API_TOKEN` or Ed25519 signature (`X-Sn-Sig`). Webhooks (`/wh/*`, `/kt/{ns}/{name}/wh/*`) handle their own trigger-level auth.

### Bounded Waits & Reconciling Uncertain Submissions

- Always set explicit HTTP client timeouts (for example `curl --connect-timeout 5 --max-time 30`) and a bounded poll loop (max attempts / deadline) on `GET /ex/{id}`.
- **Identifier names:** HTTP `POST /fl/{ns}.{name}/{flow}/run` returns **`id`** (polled via `GET /ex/{id}`); MCP `flow_run` returns **`execution_id`** (polled via `execution_get`).
- **If an execution identifier was received** (HTTP `id` or MCP `execution_id` with `timed_out: true`): keep polling **that same identifier** until terminal status or your overall deadline. Never resubmit while the run is queued or running.
- **If acknowledgment was lost** (dropped TCP response on `POST /fl/.../run` or MCP disconnect after dispatch):
  1. Do **not** rely on scanning paginated execution history (`GET /ex`) to prove the first request was never enqueued — missing history entries cannot rule out an in-flight or delayed execution.
  2. If the kit provides an operation-status lookup keyed by `operation_id` (for example a read-only status flow querying `operation_claims`), query that first.
  3. Retry **only** with the **exact same `operation_id`** when the target flow enforces end-to-end idempotency (atomic claim + downstream `Idempotency-Key`) or is strictly read-only. Otherwise, report the outcome as **`unknown`** after the deadline and require operator reconciliation.

### Core Endpoints

| Surface | Method & Path | Notes |
|---|---|---|
| Health | `GET /hl` | Health + subsystem status |
| Kits | `GET /hl/kt`, `POST /hl/reload`, `POST /hl/kt/{ns}/{name}/rl` | List kits, full reload, per-kit reload |
| Kit toggle | `POST /hl/kt/{ns}/{name}/on` / `off` | Enable or disable a kit |
| Flows | `GET /fl`, `GET /fl/{id}`, `POST /fl/{ns}.{name}/{flow}/run` | Run flow (returns `{id, fid, status}`) |
| Executions | `GET /ex`, `GET /ex/{id}`, `GET /ex/{id}/lg` | History, detail, SSE log stream |
| Live logs | `GET /lg`, `GET /lg/live` | SSE log streams |
| Triggers | `GET /tr`, `POST /tr`, `DELETE /tr/{id}`, `POST /tr/{id}/enable\|disable` | Filter `?type=CRON\|WEBHOOK\|EVENT\|MANUAL&flow=` |
| Webhooks | `ANY /wh/*`, `ANY /kt/{ns}/{name}/wh/*` | Dispatches to registered webhook triggers |
| Vault | `GET /sc`, `POST /sc`, `DELETE /sc/{name}` | List names, set `{name, value}`, delete |
| API Library | `GET /lib`, `POST /lib`, `POST /lib/{id}/validate` | Manage & validate external/AI vendors |
| Agentic AI | `GET /ai/release`, `PUT /ai/release`, `GET /ai/traces`, `GET /ai/metrics` | Release/canary controls & traces |
| FS Control | `GET /fs/pl`, `POST /fs/pl`, `POST /fs/test` | Manage & test filesystem policies |
| Content | `GET /fcms`, `GET /fcms/render/...`, `GET /ccms/status`, `GET /ccms/forms` | fcms & ccms surfaces |
| Git | `GET /git/info`, `GET /git/st`, `POST /git/commit`, `POST /git/sync` | SRE git operations |

---

## 3. Triggers & Webhooks (Declared in Lua Flows)

Declare triggers in the top-level `triggers` table of any flow file (`{ns}.{name}/fl/{flow}.lua`):

```lua
triggers = {
  cron("*/5 * * * *"),
  cron("@hourly"),

  webhook("/orders/created", {
    auth = "hmac",                     -- "none" | "hmac" | "bearer" | "header"
    key = "orders_webhook_secret",     -- vault secret name
    alg = "sha256",                    -- "sha256" | "sha512" (hmac only)
    sig_hdr = "X-Signature",           -- hmac signature header
    -- hdr = "X-Secret-Token",         -- for auth = "header"
    -- cidrs = {"198.51.100.0/24"},    -- optional IP allowlist (example RFC 5737 range)
    -- trusted_proxies = {"127.0.0.1"},
    -- rps = 50,                       -- optional per-endpoint rate limit
  }),

  event("order.created"),              -- exact match
  event("payment.*"),                  -- wildcard (matches payment.paid, not "payment")
}
```

- **Webhook URL:** `{base}/wh{path}` (e.g. `POST http://localhost:8080/wh/orders/created`) or kit-scoped `{base}/kt/{ns}/{name}/wh/{path}`.
- **Security order:** rate limit → CIDR allowlist → auth (`hmac`/`bearer`/`header`) → flow execution.
- **Params injected into `main(params)`:**
  - Cron: `params.trigger_type` (`"cron"`), `params.trigger_id` (`cr_*`), `params.scheduled_at`.
  - Webhook: merged query + JSON body (body wins), `params.trigger_type` (`"webhook"`), `params.trigger_id` (`wh_*`), `params.trigger_path`, plus `ctx.params` and `ctx.req` (`{method, path, headers, files}`).
  - Event: `params.trigger_type` (`"event"`), `params.trigger_id` (`ev_*`), `params.event_pattern`, `params.event_source`, `params.event_payload`.
  - Manual: request body/query params + `params.trigger_type` (`"manual"`), `params.trigger_id` (`mn_*`), `ctx.params`, `ctx.req`.
  - Form: wired via `events.yaml` under stub `kf.{ns}.{name}.{form}`:
    - **Lifecycle flows (`main(params)`):** dots in the stub become nested tables on `ctx.fm` — e.g. `ctx.fm.kf.acme.billing.payment.invoice_id` (and shortcut `ctx.data.<field>`).
    - **Trigger-return flows (`run(ctx)`):** form fields are provided via `ctx.form` (and `ctx.data`), with kit metadata in `ctx.kit`.

---

## 4. CLI Quick Reference

Always pass `-p <sre-path>` when operating on a specific SRE:

```bash
# SRE & kit lifecycle
sentinel sre init <dir> --with-bundle core
sentinel sre kit new acme.billing --desc "Billing workflows" -p <sre>
sentinel sre flow new charge --kit acme.billing -p <sre>
sentinel sre validate -p <sre>
sentinel sre test acme.billing/ -p <sre>

# Harness lifecycle
sentinel harness start -p <sre> --mcp --mcp-risk read,validate
sentinel harness status -p <sre>
sentinel harness reload -p <sre>

# Execution, secrets & approvals
sentinel sre flow run acme.billing/charge -p <sre> --params-json '{"operation_id":"op_001"}'
sentinel sre secret set stripe_api_key -p <sre>
sentinel sre secret ls -p <sre>

# Operator approvals (requires a Sentinel security-readiness build; verify with `sentinel approvals --help`)
sentinel approvals runtime -p <sre>
sentinel approvals grant -p <sre> ...
```
