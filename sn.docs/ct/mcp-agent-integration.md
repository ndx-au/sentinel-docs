---
title: "MCP Agent Integration"
description: "Connect AI coding agents (Cursor, Claude Desktop, Hermes, custom MCP clients) to a running Sentinel harness so they can inspect SREs, validate kits, run executions, reload kits, read source, and scaffold components — without round-tripping through the HTTP API."
type: Guide
tags: [mcp]
status: stable
---

# MCP Agent Integration

Connect AI coding agents (Cursor, Claude Desktop, Hermes, custom MCP clients) to a running Sentinel harness so they can inspect SREs, validate kits, run executions, reload kits, read source, and scaffold components — without round-tripping through the HTTP API.

MCP runs **in-process** with the harness (streamable HTTP). Clients that only speak **stdio** use `sentinel mcp stdio` as a thin bridge to the same server.

---

## Prerequisites

1. A Sentinel SRE project initialized (`sentinel sre init` or an existing repo).
2. The harness running with MCP enabled.
3. An MCP client that supports **streamable HTTP** (Cursor 2025+, Claude Code, etc.) or **stdio** via the bridge.

---

## Dashboard

The dashboard **MCP** page (`GET /mcp`, Background section after Agents) is a read-only operator console: sidecar on/off, bind/URL/auth, risk ceiling, connection snippets, named clients (no tokens), and the tool/resource/prompt catalog.

- Dashboard BFF: `GET /api/dashboard/mcp` → harness `GET /mcp`
- Catalog is shown even when the sidecar is off (ceiling from `mcp.risk_classes` / default `read,validate`)
- Starting MCP still requires `sentinel harness restart -p <sre> --mcp` (no in-UI start)
- The page does not invoke tools or edit `mcp.clients`

---

## Start the harness with MCP

```bash
# Default: bind 127.0.0.1, listen on API port + 100 (8080 → 8180)
# Default risk profile: read,validate only
sentinel harness start -p /path/to/my-project --mcp

# Full agent control plane (execute + write + admin)
sentinel harness start -p /path/to/my-project --mcp --mcp-risk all

# Custom listen port
sentinel harness start -p /path/to/my-project --mcp --mcp-listen 9001 --mcp-risk all

# Bind all interfaces (LAN/Tailscale — trusted networks only)
sentinel harness start -p /path/to/my-project --mcp --mcp-bind 0.0.0.0 --mcp-listen 8180 --mcp-risk all

# Background daemon with MCP
sentinel harness start -p /path/to/my-project --mcp --mcp-risk all -d
```

| Flag | Default | Description |
|------|---------|-------------|
| `--mcp` | off | Enable the MCP server alongside the harness |
| `--mcp-bind` | `127.0.0.1` | Bind address (`127.0.0.1`, `0.0.0.0`, `::`, `localhost`, or hostname) |
| `--mcp-listen` | API port + 100 | TCP port for MCP streamable HTTP |
| `--mcp-port` | (alias) | Deprecated alias for `--mcp-listen` |
| `--mcp-risk` | `read,validate` | Comma-separated risk classes, or `all`. This is the **ceiling** for every client. |
| `--mcp-aliases` | off | Also register `sentinel_*` tool names (off by default) |

On startup the harness prints the MCP URL and enabled risk classes.

If `--mcp-bind` is not loopback, a warning is printed — combine network controls with harness auth (see **Authentication** below).

### Risk classes

Every tool is annotated with a risk class. Only tools whose class is enabled are registered.

| Class | Meaning | Examples |
|-------|---------|----------|
| `read` | No side effects | `kits_list`, `source_read`, `execution_logs`, `git_status` |
| `validate` | Read-only validation | `validate`, `diagnose` |
| `execute` | Runs flows / emits events | `flow_run`, `event_emit` |
| `write` | Creates SRE files | `scaffold_create` |
| `admin` | Harness/kit lifecycle | `harness_reload_sre`, `kit_enable`, `kit_disable` |

Secret **values** are never exposed. There is no `secret_set` tool.

**Read-only operator profile** (default): `--mcp` or `--mcp-risk read,validate`.

**Full coding-agent profile:** `--mcp-risk all`.

Optional config in `.sentinel/config.json`:

```json
{
  "mcp": {
    "risk_classes": ["read", "validate", "execute", "write", "admin"],
    "aliases": false,
    "disabled": ["scaffold_create"],
    "max_log_chars": 20000,
    "clients": [
      {
        "name": "readonly-cursor",
        "match": { "kind": "bearer", "token": "<same value as api.tokens>" },
        "risk_classes": ["read", "validate"]
      },
      {
        "name": "signed-agent",
        "match": { "kind": "ed25519", "key_name": "cursor-agent" },
        "risk_classes": ["read", "validate", "execute"]
      }
    ]
  }
}
```

CLI `--mcp-risk` overrides `mcp.risk_classes` when set and remains the **ceiling**. `mcp.clients` entries are intersected with that ceiling (a client cannot gain a class the harness omitted). Unmatched authenticated callers get the ceiling. `tools/list` for a session only includes the intersection; denied calls still fail closed if a stale client caches a tool.

### Granular permissions

Beyond risk classes, each `mcp.clients[]` entry may scope individual tools, resources, and prompts. Evaluation is **fail closed**:

1. Global `mcp.disabled`
2. Risk ceiling + client `risk_classes` intersection
3. Client `deny_tools` (wins over allow)
4. Client `allow_tools` — when non-empty, only listed **canonical** tool names are registered (aliases follow when `mcp.aliases` / `--mcp-aliases` is on)
5. Resources: `deny_resources` then optional `allow_resources` (prefix match on URI)
6. Prompts: `deny_prompts` then optional `allow_prompts` (exact name)

`allow_tools` never bypasses the risk ceiling — e.g. listing `harness_reload_sre` while the ceiling is `read,validate` still omits that admin tool.

Completions return empty when the parent prompt or resource is out of scope.

Example — grant only inspection tools while keeping execute risk for a single runner:

```json
{
  "mcp": {
    "risk_classes": ["read", "validate", "execute", "write", "admin"],
    "clients": [
      {
        "name": "cursor-inspect",
        "match": { "kind": "bearer", "token": "<token-a>" },
        "risk_classes": ["read", "validate", "execute"],
        "allow_tools": ["kits_list", "flow_get", "source_read", "flows_list"],
        "deny_tools": ["secrets_list"],
        "allow_resources": ["sentinel://project/", "sentinel://kits", "sentinel://kit/"],
        "deny_resources": ["sentinel://harness/license"],
        "allow_prompts": ["review_sre", "debug_failed_flow"],
        "deny_prompts": ["add_flow"]
      }
    ]
  }
}
```

Unknown tool names in `allow_tools` / `deny_tools` log a harness startup warning (typo guard).

### Tool names (breaking)

`tools/list` registers **canonical names only** (`flow_run`, `kits_list`, `source_read`, …). `sentinel_*` aliases are **off** unless `mcp.aliases` is true or `--mcp-aliases` is set. Existing agents that called `sentinel_flow_run` must switch to `flow_run` or enable aliases.

---

## Authentication

MCP uses the **same auth as the harness HTTP API** when `api.debug_mode` is `false`:

| Method | Client setup |
|--------|----------------|
| **Bearer token** | Add `Authorization: Bearer <token>` in MCP client headers (`api.tokens` in `.sentinel/config.json`) |
| **Ed25519 keypair** | Register pubkey in `{SRE}/.sentinel/pub-keys/*.pub`, run `sentinel mcp proxy` or `sentinel mcp stdio --sign` |

In **debug mode**, MCP skips token/signature and enforces `api.ip_whitelist` only (same as the harness API).

### Bearer token (Cursor)

```json
{
  "mcpServers": {
    "sentinel": {
      "url": "http://127.0.0.1:8180",
      "headers": {
        "Authorization": "Bearer YOUR_API_TOKEN"
      }
    }
  }
}
```

### Keypair via signing proxy

```bash
sentinel dashboard keygen --name cursor-agent
echo '<public-key-b64>' > /path/to/sre/.sentinel/pub-keys/cursor-agent.pub
sentinel harness start -p /path/to/sre --mcp --mcp-risk all
sentinel mcp proxy --upstream http://127.0.0.1:8180 --keypair-name cursor-agent
```

Point Cursor at the proxy URL printed by the command (no auth headers needed).

---

## Connect Cursor

Add to the project `.cursor/mcp.json` (or global Cursor MCP settings). **Production harnesses require auth** — use bearer headers or the signing proxy.

```json
{
  "mcpServers": {
    "sentinel": {
      "url": "http://127.0.0.1:8180",
      "headers": {
        "Authorization": "Bearer YOUR_API_TOKEN"
      }
    }
  }
}
```

For keypair auth without embedding tokens, use `sentinel mcp proxy` and set `"url"` to the proxy address.

Replace `8180` with your `--mcp-listen` value. If the harness API uses a non-default port, MCP defaults to **API port + 100** unless you set `--mcp-listen` explicitly.

**Remote dev (SSH / Tailscale):** bind MCP to an address reachable from your machine:

```bash
sentinel harness start -p ./my-project --mcp --mcp-bind 0.0.0.0 --mcp-listen 8180 --mcp-risk all
```

Then point Cursor at `http://<host-ip>:8180` with bearer headers or via `sentinel mcp proxy` on your dev machine. Restrict with firewall rules — authenticated MCP access is harness-equivalent control within the enabled risk classes.

---

## Connect Hermes / Claude Desktop (stdio)

```bash
# Bearer
sentinel mcp stdio --upstream http://127.0.0.1:8180 --token YOUR_API_TOKEN

# Or Ed25519 signing (dashboard keypair)
sentinel mcp stdio --upstream http://127.0.0.1:8180 --sign --keypair-name cursor-agent
```

Example Hermes config:

```yaml
mcp_servers:
  sentinel:
    command: "sentinel"
    args: ["mcp", "stdio", "--upstream", "http://127.0.0.1:8180", "--token", "YOUR_API_TOKEN"]
```

---

## Available MCP tools

Canonical names only (see **Tool names** above). Each tool carries MCP annotations from its risk class (`readOnlyHint` for read/validate, `destructiveHint` for admin, `openWorldHint` for `flow_run` / `event_emit`).

| Tool | Risk | Purpose |
|------|------|---------|
| `harness_health` | read | Status, uptime, version, risk classes, components |
| `project_info` | read | Project name, root, mode, yaml presence |
| `capabilities` | read | Vault/cron/webhook/AI/RAG/backup/git flags |
| `license_status` | read | Occupy/registration: edition, slot held, lease until, deny reason (**never the license key**) |
| `harness_reload_sre` | admin | Full SRE reload |
| `flows_list` / `flow_get` | read | Discover flows and parameter schemas |
| `flow_run` | execute | Run a flow; **waits** for a terminal status by default |
| `execution_get` / `executions_list` | read | Poll execution status and history |
| `execution_logs` | read | Bounded, redacted execution logs |
| `kits_list` / `kit_get` | read | Kit inventory and manifest |
| `kit_reload` / `kit_enable` / `kit_disable` | admin | Per-kit lifecycle |
| `triggers_list` | read | Cron, webhook, and event triggers |
| `secrets_list` | read | Vault secret **names** only |
| `source_read` | read | Symlink-safe read under SRE root |
| `scaffold_create` | write | Create kit/flow/connector/module scaffolding |
| `validate` / `diagnose` | validate | Kit validation and aggregated diagnostics |
| `connectors_list` / `modules_list` | read | `cn/` and `md/` inventory |
| `event_emit` | execute | Emit an internal event |
| `git_status` / `git_diff` | read | SRE git status and diff |

### `flow_run` wait (breaking)

`flow_run` waits for a terminal execution by default (`wait: true`, `timeout_ms` default `60000`, cap `300000`). While waiting it emits MCP progress (`queued` → `running` → status / log snippet) and honors client cancellation. On timeout it returns the current status plus `execution_id` and `timed_out: true` — not a tool error. Pass `wait: false` to restore queue-and-return (`status: "queued"`). Prefer this over polling `execution_get` unless you opted out of wait.

After `scaffold_create`, call `kit_reload` or `harness_reload_sre` before running new flows (requires `admin`).

### Resources

Prefer resources before `source_read`. Initialize includes short SRE instructions (project root, canonical names, risk profile, vault/occupy guidance) — not a dump of `AGENTS.md`. Completions cover kit names, flow ids, and prompt args (`add_flow.kit`, `debug_failed_flow.flow_id`).

| URI | Content |
|-----|---------|
| `sentinel://project/summary` | Project info JSON |
| `sentinel://project/sentinel.yaml` | Project config file |
| `sentinel://project/events.yaml` | Event routing file |
| `sentinel://harness/status` | Health snapshot |
| `sentinel://harness/license` | Occupy/registration snapshot (no license key) |
| `sentinel://kits` | Kits inventory |
| `sentinel://flows` | Flows inventory |
| `sentinel://executions/recent` | Recent executions |
| `sentinel://diagnostics/latest` | Diagnose snapshot |
| `sentinel://docs/operator-manual` | Present only if `docs/operator-manual.md` exists |

Templates (symlink-safe, SRE-rooted):

| Template | Backed by |
|----------|-----------|
| `sentinel://kit/{kit}/file/{+path}` | `source_read` |
| `sentinel://flow/{flow_id}` | `flow_get` |
| `sentinel://execution/{execution_id}` | `execution_get` |

`sentinel mcp stdio` forwards upstream instructions, resource templates, and completions as well as tools/resources/prompts.

### Prompts

| Prompt | Purpose |
|--------|---------|
| `review_sre` | Structure, risks, validation, occupy, next actions |
| `debug_failed_flow` | Failed execution + logs + source workflow (`flow_id` optional) |
| `add_flow` | Scaffold flow with twins/tests (`kit`, `name`) |

---

## Debugging MCP issues

### Harness logs

MCP logs use structured fields `component=mcp`:

| Subsystem | Level | When |
|-----------|-------|------|
| `subsystem=http` | INFO | Every HTTP request (method, path, status, duration) |
| `subsystem=http` | ERROR | 5xx responses, handler panics (includes stack trace) |
| `subsystem=tools` | INFO | Tool invoked (`tool`, `risk`, `project`, truncated redacted args) |
| `subsystem=tools` | ERROR | Tool returned an error (`ok=false`) |

Enable debug logging in `.sentinel/config.json`:

```json
{
  "log": { "level": "debug" }
}
```

### Common failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `connection refused` | Harness not running or wrong port | `sentinel harness status -p <sre>`; verify `--mcp-listen` |
| Tool missing from client | Risk class not enabled or per-client intersection | Pass `--mcp-risk all` / include the class; check `mcp.clients` |
| `sentinel_*` tool missing | Aliases off by default | Use canonical names (`flow_run`) or `--mcp-aliases` / `mcp.aliases` |
| Flows fail to start | Occupy slot not held | Call `license_status` or read `sentinel://harness/license` |
| `port already in use` | Another process on MCP port | `--mcp-listen <free-port>` |
| Cursor shows no tools | Wrong URL, transport, or missing auth | URL must be `http://host:port`; add Bearer header or use `sentinel mcp proxy` |
| `AUTH.REQUIRED` in response | Production mode without credentials | Add Bearer header or signing proxy |
| Tool errors in agent | Missing subsystem (e.g. no flows loaded) | Check `harness_health`; run `harness_reload_sre` if admin enabled |
| Agent cannot reach remote MCP | Bound to 127.0.0.1 only | Restart with `--mcp-bind 0.0.0.0` and open firewall |

### Verify manually

```bash
curl -s -X POST http://127.0.0.1:8180/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Authorization: Bearer YOUR_API_TOKEN' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

Expect a JSON-RPC response with `serverInfo.name` = `sentinel-harness`.

---

## Security notes

- **Default bind `127.0.0.1`** — only local processes can connect; production mode still requires bearer or keypair auth.
- **Default risk `read,validate`** — mutation tools are off until explicitly enabled.
- **`--mcp-bind 0.0.0.0`** — exposes MCP to the network; use bearer tokens, keypair + TLS/VPN, and firewall rules.
- Authenticated MCP with `execute`/`write`/`admin` can **run flows**, **disable kits**, and **write scaffold files** — treat like root access to the SRE within those classes.
- Secret **values** are never exposed; logs and tool args are redacted for common token patterns.
- **`license_status` / `sentinel://harness/license`** never return the license key.
- **`source_read`** resolves symlinks and rejects paths outside the SRE root.
- Mutation tools (`scaffold_create`, kit lifecycle, SRE reload) share a per-SRE write lock.
- **`sentinel mcp proxy` / `stdio`** bind or speak locally by default — do not expose them to the network.

---

## Related docs

- [CLI Reference — harness start](/cli-reference#start) — all flags
- [Harness HTTP routes](/harness-http-routes) — REST API parity, including `GET /mcp`
- Dashboard operator page: `/mcp` (BFF `/api/dashboard/mcp`)
- `system-specs/mcp.yaml` — machine-readable MCP spec
