# Sentinel Skill Architecture Patterns

Use this reference when deciding how to structure a new Sentinel skill, which prefix (`sre-*` vs `sn-*`) to use, and how to divide responsibilities between the agent skill and the Sentinel SRE.

Public docs: [Overview](https://docs.ndx-sentinel.com/), [Kit Development](https://docs.ndx-sentinel.com/kit-development), [Workflows & Patterns](https://docs.ndx-sentinel.com/workflows-and-patterns), [Triple-Access Pattern](https://docs.ndx-sentinel.com/triple-access-pattern).

---

## Prefix Decision Matrix

| Prefix | Primary Responsibility | Requires SRE Files on Disk? |
|---|---|---|
| `sre-*` | Authoring, refactoring, validating, or operating SRE components (kits, Lua flows, connectors, modules, forms, pages, content planes, `sentinel.yaml`) or encapsulating procedural host/SRE tasks inside a kit. | Usually yes (or scaffolds one via CLI/MCP). |
| `sn-*` | Platform-level orchestration across any business domain — invoking flows, emitting events, calling webhooks, inspecting executions/logs/traces, or operating a harness via MCP, HTTP API, or CLI. | No — only needs access to a running harness (or webhook endpoint). |

---

## The 5 Canonical Sentinel Skill Archetypes

### 1. Procedural SRE Kit Skill (`sre-*`)
**Best for:** Repeatable system, operational, or data-processing work on the host/SRE where Sentinel runs (scheduled maintenance, file ingestion via `ctx.fs`, SQLite/Postgres sync, backup monitoring via `sn.backup`, WebSocket device control via `sn.ws`).
- **Agent role:** Gathers configuration/parameters, scaffolds or updates the kit, verifies vault secrets exist, runs `sentinel sre validate` + `sentinel sre test`, reloads the kit, and smoke-tests execution.
- **Sentinel role:** Runs the deterministic Lua flow(s) in `fl/`, stores state in `sn.db`, accesses files only through FS Control (`ctx.fs`), and keeps secrets in `.sentinel/vault.db`.

### 2. MCP Orchestration Skill (`sn-*`)
**Best for:** AI agents driving business workflows on a running Sentinel harness without touching SRE files directly (e.g., running reports, triggering incident runbooks, emitting domain events, diagnosing failed jobs).
- **Agent role:** Reads MCP resources (`sentinel://flows`, `sentinel://executions/recent`, `sentinel://diagnostics/latest`), calls `flow_run` or `event_emit`, inspects `execution_logs`, and summarizes results.
- **Sentinel role:** Enforces MCP risk classes (`read`, `validate`, `execute`, `write`, `admin`) and per-client ACLs, executes the flow, and records audit trails and logs.

### 3. Webhook & Event Pipeline Skill (`sn-*` or `sre-*`)
**Best for:** Event-driven business orchestration across external SaaS tools (Stripe, GitHub, CRM, Slack, Telegram, ERP) or internal event cascades.
- **Agent role:** Configures or invokes webhook endpoints (`/wh/{path}` or `/kt/{ns}/{name}/wh/{path}`), designs `event("domain.*")` fan-out via `sentinel.emit(...)`, wires form submissions via `events.yaml`, verifies HMAC/Bearer/Header auth, and specifies deduplication keys and overlap behavior.
- **Sentinel role:** Handles rate limiting, CIDR allowlists, constant-time HMAC/secret verification, async execution, and bounded event fan-out.

#### Concurrency, Idempotency & Overlap Contracts
External webhooks routinely retry (at-least-once delivery), and scheduled jobs can overlap across ticks. Every webhook or scheduled skill must specify:

1. **Trigger-Aware Stable Key & Recoverable Atomic Claim:**
   - **Branch key derivation by trigger type:**
     - **Webhook / Event / Manual:** Require and validate a stable provider event ID/header (e.g. Stripe `params.id` scoped as `"stripe:" .. account_id .. ":" .. event_id`) or caller-supplied `operation_id`. Reject missing keys — **never** fall back to `ctx.execution_id` (reserve `ctx.execution_id` for correlation and lease ownership).
     - **Cron:** Derive the logical tick key from `params.trigger_id` and `params.scheduled_at` (e.g. `"billing:cron:" .. tostring(params.trigger_id) .. ":" .. tostring(params.scheduled_at)`), and pair it with a separate job-level lease for `skip` across distinct ticks.
   - Use an explicit **`processing` → `completed` / `failed_retryable` / `failed_terminal` / `unknown_outcome`** lifecycle with `lease_until` and `attempts` cap:
     - **`failed_retryable`**: confirmed transient error (e.g. HTTP 429/5xx) with `attempts < max_attempts` and backoff (`next_retry_at`).
     - **`failed_terminal`**: permanent failure (missing vault secret, 4xx rejection, invalid input) — do not auto-retry.
     - **`unknown_outcome`**: ambiguous transport timeout/disconnect after sending a side-effecting request — reconcile with the downstream provider (or require a verified downstream `Idempotency-Key` contract) before takeover.
   - **Authoritative completion check:** Always check `rows_affected == 1` on `UPDATE operation_claims SET status = 'completed' WHERE op_key = ? AND owner_exec_id = ?`. If `rows_affected ~= 1`, ownership was lost after takeover — query and return the authoritative state instead of claiming completion.
2. **Schedule Overlap Policy (Cron Flows) with Fenced Lease Ownership:**
   - **Important runtime behavior:** Sentinel's cron wrapper (`SkipIfStillRunning`) only guards the scheduler's dispatch callback, which invokes asynchronous `ExecuteFlow` and returns immediately. **A slow flow WILL overlap the next cron tick unless the flow enforces exclusion itself.**
   - **`skip` (fenced flow-level exclusion):**
     - Track `local lease_held = false` and set it **only** when atomic acquisition succeeds (`INSERT OR IGNORE` or expired-lease `UPDATE` with `rows_affected == 1`, storing `owner_exec_id = ctx.execution_id`).
     - Constrain all work inside a hard bound shorter than `lease_until` (or renew via `UPDATE job_leases SET lease_until = ... WHERE job_key = ? AND owner_exec_id = ?` checking `rows_affected == 1` and aborting/fencing writes if ownership is lost).
     - In `cleanup()`, release **only** when `lease_held` is true **and** conditional on `owner_exec_id`: `DELETE FROM job_leases WHERE job_key = ? AND owner_exec_id = ?` — so a denied contender or expired owner can never release another run's lease.
   - **`queue` (single-consumer drain):** Enqueue pending work rows in `sn.db` and let one lease-holding consumer drain items in order.
   - **`parallel`:** Only when concurrent runs are safe; partition work with per-item atomic claims in `sn.db` so two runs never send duplicate alerts or mutate the same record.

### 4. Agentic AI & Knowledge Skill (`sre-*` or `sn-*`)
**Best for:** Workflows that call LLMs (`sn.ai.chat`, `sn.ai.complete`), maintain episodic memory (`sn.memory`), or query RAG (`sn.rag`) inside Sentinel flows.
- **Agent role:** Guides vault secret setup, API Library vendor registration (`meta.capabilities.ai`, `meta.auth.secret_ref`, `meta.runtime.provider`), provider validation (`POST /lib/{id}/validate`), release/canary controls (`GET`/`PUT /ai/release`), flow authoring, and trace inspection (`GET /ai/traces`).
- **Sentinel role:** Mediates provider calls, enforces release/rollback/canary gates and agent usage budgets, and records AI traces.
- Public docs: [Agentic AI Operator Guide](https://docs.ndx-sentinel.com/agentic-ai-operator).

### 5. Content Plane & Kit Web UI Skill (`sre-*`)
**Best for:** Publishing content or building human-in-the-loop web forms and dashboards using Sentinel's content planes:
- **`fcms` (File CMS):** Git-tracked Markdown in `{ns}.{name}/ct/`, served via `/fcms` (JSON) and `/fcms/render` (HTML).
- **`ccms` (Collection CMS):** Postgres + PostGraphile (`:1880`), ordered migrations in `dd/*.sql` (`sentinel ccms migrate`), `collections/*.yaml`, `forms/pub/*.md`.
- **`wpcms` (WordPress):** Managed WordPress stack behind Sentinel ingress (`:8800`) and vault-backed REST API credentials.
- **Kit UI (`pg/`, `fm/`, `tp/`, `pb/`):** YAML forms wired through `events.yaml` to Lua flows with Go `text/template` responses.
- Public docs: [Content Planes](https://docs.ndx-sentinel.com/content-planes), [fcms Operator Guide](https://docs.ndx-sentinel.com/sentinel-cms).

---

## Choosing the Right Primitive

| Need | Right Sentinel Primitive |
|---|---|
| Teach AI agents *when* and *how* to solve a domain task using Sentinel | **Agent Skill** (`skills/{sre\|sn}-{name}/SKILL.md`) |
| Persist notes/context about a specific SRE code file | **SRE Skill Twin** (`*.lua.md`, `kit.yaml.md`, auto-spawned by harness) |
| Package a domain's flows, connectors, modules, forms, and schema | **Kit** (`{ns}.{name}/` with `kit.yaml`) |
| Execute deterministic multi-step business or system logic | **Flow** (`{ns}.{name}/fl/{flow}.lua`) |
| Wrap an external API or protocol (HTTP, SMTP, WebSocket, SaaS) | **Connector** (`{ns}.{name}/cn/{name}.lua` → `sn.cn.*`) |
| Share pure internal logic, parsing, or formatting across flows | **Module** (`{ns}.{name}/md/{name}.lua` → `sn.md.*`) |
| Trigger a flow on schedule, HTTP push, internal event, or form | **Trigger** (`cron()`, `webhook()`, `event()`, or `fm/` + `events.yaml`) |
| Store an API key, password, or signing secret | **Vault Secret** (`sentinel sre secret set <key> -p <sre>` + `ctx.secret("key")`) |

### Rule of Thumb: Keep Flows Coherent
Do not split a single business procedure into dozens of micro-flows. Keep orchestration readable in one coherent flow (`fl/*.lua`), extract external service calls into `cn/*.lua`, and extract reusable pure logic into `md/*.lua`.
