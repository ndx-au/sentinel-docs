---
title: "HTTP API Reference"
description: "Reference for Sentinel HTTP endpoints, authentication, request and response data, pagination, event streams, and WebSockets."
type: Reference
tags: [api]
status: stable
---

<!-- ndx-ste-mode: description -->

# HTTP API Reference

Complete reference for every Sentinel HTTP endpoint. This document covers request formats, response structures, authentication, error handling, pagination, streaming, and WebSocket protocols.

---

## Introduction

Sentinel exposes one HTTP API for flows, triggers, logs, source files, secrets, and other operations. The CLI and Dashboard use this API. [Harness HTTP route reference](/harness-http-routes) lists prefixes, keyhole behavior, and dashboard rewrites.

### Design Philosophy

The API follows several important design principles that differ from conventional REST APIs:

1. **Always HTTP 200.** Every response returns HTTP status code 200, even errors. The actual success or failure is communicated in the JSON response body. This simplifies client logic for AI agents and automation scripts that consume the API -- they never need to handle HTTP-level error branching. The only exception is WebSocket upgrade requests, which use standard HTTP upgrade semantics.

2. **Brevity Regime.** Paths and query parameters use short names to reduce tokens in agent prompts. Example prefixes include `/fl` for flows and `/ex` for executions. Other examples include `/tr` for triggers and `/lg` for logs. Query parameters include `?lv=` for level and `?h=` for history.

3. **Auth-Exempt Routes.** Certain routes bypass the gateway authentication entirely. Webhooks (`/wh/*` and `/kt/{ns}/{name}/wh/*`) use their own per-endpoint authentication (HMAC signatures, CIDR allow-lists). TLS certificate endpoints (`/cert/*`) must be unauthenticated so clients can retrieve certificates for pinning. The configuration status endpoint (`/api/config`) is also public so the Dashboard can discover the server's capabilities before authenticating.

4. **JSON Everywhere.** All authenticated endpoints accept and return `application/json`. Forms are the sole exception, accepting `application/x-www-form-urlencoded` and `multipart/form-data` for HTML form submissions.

---

## Quick Reference Table

All available API routes at a glance. Routes marked with (public) bypass bearer token authentication.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/hl` | Health check and system status |
| `GET` | `/hl/kt` | List all discovered kits (includes `on` per kit) |
| `GET` | `/mcp` | MCP sidecar status and catalog (no tokens) |
| `POST` | `/hl/reload` | Reload all kits and flows from SRE |
| `POST` | `/hl/kt/{ns}/{name}/rl` | Reload one kit from disk |
| `POST` | `/hl/kt/{ns}/{name}/off` | Disable kit at runtime |
| `POST` | `/hl/kt/{ns}/{name}/on` | Enable kit and reload from disk |
| `GET` | `/api/config` | Configuration status (public) |
| `GET` | `/fl` | List all flows |
| `GET` | `/fl/{ns}.{name}/{flow}` | Get flow details |
| `POST` | `/fl/{ns}.{name}/{flow}/run` | Execute a flow |
| `GET` | `/ex` | List executions (with pagination) |
| `GET` | `/ex/{id}` | Get execution details |
| `GET` | `/ex/{id}/lg` | Stream execution logs (SSE) |
| `GET` | `/lg` | Stream all logs (SSE) |
| `GET` | `/lg/live` | Stream unified logs (SSE) |
| `GET` | `/tr` | List triggers |
| `POST` | `/tr` | Create trigger |
| `GET` | `/tr/{id}` | Get trigger details |
| `DELETE` | `/tr/{id}` | Delete trigger |
| `POST` | `/tr/{id}/enable` | Enable trigger |
| `POST` | `/tr/{id}/disable` | Disable trigger |
| `ANY` | `/wh/*` | Global webhook endpoint (public) |
| `ANY` | `/kt/{ns}/{name}/wh/*` | Kit-scoped webhook (public) |
| `GET` | `/fm` | List all forms (JSON) |
| `GET` | `/fm/{stub}` | Render form (HTML) |
| `POST` | `/fm/{stub}` | Submit form (HTML) |
| `GET` | `/fm/{stub}/stats` | Form statistics |
| `GET` | `/fm/{stub}/submissions` | List form submissions |
| `GET` | `/fm/{stub}/submissions/{uuid}` | Get single submission |
| `DELETE` | `/fm/submissions/{uuid}` | Delete submission |
| `POST` | `/fm/{stub}/clear-cache` | Clear form response cache |
| `GET` | `/rsp/{stub}/{uuid}` | Get cached form response |
| `GET` | `/sc` | List secrets (metadata only) |
| `POST` | `/sc` | Create or update secret |
| `DELETE` | `/sc/{name}` | Delete secret |
| `GET` | `/src/*` | Get source file by SRE path |
| `PUT` | `/src/*` | Update source file by SRE path |
| `GET` | `/{folder}/*` | Get source by kit folder |
| `PUT` | `/{folder}/*` | Update source by kit folder |
| `GET` | `/cn` | List connectors |
| `GET` | `/md` | List modules |
| `GET` | `/cfg/project` | Get sentinel.yaml |
| `PUT` | `/cfg/project` | Update sentinel.yaml |
| `GET` | `/git/info` | Git repository info |
| `GET` | `/git/st` | Git status (modified/staged/untracked) |
| `GET` | `/git/diff` | Show file diff |
| `GET` | `/git/show` | Show file at revision |
| `POST` | `/git/commit` | Commit changes |
| `POST` | `/git/pull` | Git pull |
| `POST` | `/git/push` | Git push |
| `POST` | `/git/sync` | Pull then push |
| `POST` | `/git/discard` | Discard file changes |
| `GET` | `/git/credentials` | Get SSH credential status |
| `POST` | `/git/credentials` | Store SSH credentials |
| `DELETE` | `/git/credentials` | Delete SSH credentials |
| `POST` | `/git/credentials/generate` | Generate new SSH keypair |
| `GET` | `/cert/ca.crt` | Download CA certificate (public) |
| `GET` | `/cert/server.crt` | Download server certificate (public) |
| `GET` | `/cm` | List CMS content slugs |
| `GET` | `/cm/{kitName}/{slug}` | Get CMS content by slug |
| `GET` | `/st` | List storage points |
| `POST` | `/st` | Create storage point |
| `GET` | `/st/{id}` | Get storage point |
| `PUT` | `/st/{id}` | Update storage point |
| `DELETE` | `/st/{id}` | Delete storage point |
| `POST` | `/st/{id}/test` | Test storage connectivity |
| `GET` | `/pg` | List PostgreSQL connections |
| `POST` | `/pg` | Add PostgreSQL connection |
| `DELETE` | `/pg/{name}` | Remove PostgreSQL connection |
| `POST` | `/pg/test` | Test PostgreSQL connection |
| `POST` | `/pg/{name}/reconnect` | Reconnect PostgreSQL pool |
| `GET` | `/bk/plans` | List backup plans |
| `GET` | `/bk/plans/{id}` | Get backup plan |
| `POST` | `/bk/plans` | Create backup plan |
| `PUT` | `/bk/plans/{id}` | Update backup plan |
| `DELETE` | `/bk/plans/{id}` | Delete backup plan |
| `GET` | `/bk/runs` | List backup runs |
| `GET` | `/bk/runs/{id}` | Get backup run |
| `POST` | `/bk/plans/{id}/run` | Run backup plan immediately |
| `GET` | `/ws` | Upgrade to multiplexed WebSocket |
| `GET` | `/ws/{channel}` | Upgrade to channel WebSocket |
| `GET` | `/ws/cfg` | Get WebSocket subsystem configuration |
| `PUT` | `/ws/cfg` | Update WebSocket subsystem configuration |
| `GET` | `/ws/cn` | List WebSocket connections |
| `GET` | `/ws/cn/{name}` | Get WebSocket connection |
| `DELETE` | `/ws/cn/{name}` | Close WebSocket connection |
| `GET` | `/lib` | List API library vendors |
| `POST` | `/lib` | Create vendor |
| `GET` | `/lib/schema` | Get vendor collection JSON schema |
| `GET` | `/lib/export` | Export all vendors as one JSON bundle |
| `POST` | `/lib/import` | Import one vendor collection |
| `POST` | `/lib/import-all` | Import all vendors from one JSON bundle |
| `POST` | `/lib/scrape` | Scrape docs and generate a vendor collection with a registered LLM |
| `GET` | `/lib/{id}` | Get vendor details |
| `PUT` | `/lib/{id}` | Update vendor |
| `DELETE` | `/lib/{id}` | Delete vendor |
| `GET` | `/lib/{id}/export` | Export one vendor collection |
| `POST` | `/lib/{id}/ep` | Create endpoint |
| `PUT` | `/lib/{id}/ep/{epId}` | Update endpoint |
| `DELETE` | `/lib/{id}/ep/{epId}` | Delete endpoint |
| `POST` | `/lib/{id}/ep/{epId}/call` | Create call template |
| `PUT` | `/lib/{id}/ep/{epId}/call/{callId}` | Update call template |
| `DELETE` | `/lib/{id}/ep/{epId}/call/{callId}` | Delete call template |
| `GET` | `/docker` | List Docker stacks |
| `GET` | `/docker/{stub}` | Get Docker stack details |
| `POST` | `/docker/{stubs}/up` | Start Docker stacks |
| `POST` | `/docker/{stubs}/down` | Stop Docker stacks |
| `POST` | `/docker/{stub}/save` | Save Docker stack configuration |
| `DELETE` | `/docker/{stub}` | Delete Docker stack |
| `GET` | `/docker/{stub}/logs` | Stream Docker stack logs |
| `GET` | `/mk/kits` | List marketplace kits |
| `POST` | `/mk/install` | Install marketplace kit |
| `POST` | `/mk/update` | Update marketplace kit |
| `DELETE` | `/mk/kits/{id}` | Remove marketplace kit |
| `GET` | `/mk/license` | License status |
| `POST` | `/mk/license` | Activate license |
| `DELETE` | `/mk/license` | Clear license |
| `GET` | `/mk/auth` | Marketplace auth status |
| `POST` | `/mk/auth/login` | Marketplace login |
| `POST` | `/mk/auth/poll` | Poll login status |
| `POST` | `/mk/auth/logout` | Marketplace logout |

---

## Base URL

By default, Sentinel listens on `http://localhost:8080`. The port is configured in `.sentinel/config.json` (the per-machine infrastructure configuration file that is gitignored):

```json
{
  "api": {
    "port": 8080
  }
}
```

If TLS is enabled, an HTTPS server starts on the configured TLS port (default 8443) instead. All examples in this document use `http://localhost:8080` for brevity. Substitute your actual host and port as needed.

---

## Authentication

Sentinel supports two authentication methods, plus a debug mode that relaxes requirements for local development.

### Bearer Token Authentication

The primary authentication method for API clients, scripts, and AI agents. Include the token in the `Authorization` header:

```
Authorization: Bearer <your-token>
```

Tokens are configured in `.sentinel/config.json`:

```json
{
  "api": {
    "tokens": ["my-secret-token-1", "my-secret-token-2"]
  }
}
```

**curl example:**
```bash
curl -H "Authorization: Bearer my-secret-token" http://localhost:8080/fl
```

### Signature-Based Authentication (Dashboard)

The Sentinel Dashboard uses Ed25519 signature-based authentication. The Dashboard signs each request with its private key and sends the signature in the `X-Sn-Sig` header. The harness verifies the signature against registered public keys stored in the SRE's `.sentinel/` directory. This is handled automatically by the Dashboard and is not typically used by API clients directly.

### Debug Mode

When `debug_mode` is enabled in `.sentinel/config.json`, bearer token validation is skipped entirely. However, IP whitelist enforcement remains active. This means only requests from whitelisted IP addresses (typically `127.0.0.1` and `::1` for localhost) are allowed, but they do not need to present a token.

Debug mode is intended for local development only. Never enable it in production.

**curl example (debug mode, localhost):**
```bash
# No Authorization header needed in debug mode
curl http://localhost:8080/fl
```

### IP Whitelisting

In debug mode, requests are restricted to IPs listed in the whitelist. In production mode, IP whitelisting is not enforced (bearer tokens or signatures are used instead). The whitelist supports both individual IPs and CIDR ranges:

```json
{
  "api": {
    "ip_whitelist": ["127.0.0.1", "::1", "192.168.1.0/24"]
  }
}
```

### Auth-Exempt Routes

The following routes bypass all gateway authentication. They either have no authentication at all, or use their own independent authentication mechanisms:

| Route Pattern | Reason |
|---------------|--------|
| `GET /api/config` | Dashboard needs to discover server capabilities before authenticating |
| `/wh/*` | Webhooks use per-endpoint auth (HMAC, CIDR, rate limits) |
| `/kt/{ns}/{name}/wh/*` | Kit-scoped webhooks, same as above |
| `GET /cert/ca.crt` | Clients must retrieve CA cert before they can establish TLS |
| `GET /cert/server.crt` | Diagnostic endpoint for certificate inspection |

---

## Response Format

### Success Responses

Successful responses return the JSON body directly. Some endpoints include an `ok: true` field. Others return the data directly without a wrapper. The exact shape depends on the endpoint (documented per-endpoint below).

### Error Responses

All errors are returned as HTTP 200 with an error object in the body:

```json
{
  "code": "DOMAIN.ACTION",
  "msg": "Human-readable error message",
  "req_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

- **`code`**: A structured error code such as `AUTH.REQUIRED`, `RESOURCE.NOT_FOUND`, or `CMS.UNAVAILABLE`. Use this for programmatic error handling.
- **`msg`**: A human-readable description of what went wrong. Suitable for logging or displaying to users.
- **`req_id`**: A UUID v4 generated for every request. This is also returned in the `X-Request-ID` response header. Use it when reporting issues or correlating logs.

**How to detect errors:** If the response contains a `code` field, the request failed. If `code` is absent, the request succeeded.

---

## Pagination

Several list endpoints support pagination using `limit` and `offset` query parameters:

- **`limit`**: Maximum number of items to return. Defaults vary by endpoint (typically 20). Maximum is usually 100.
- **`offset`**: Number of items to skip before returning results. Defaults to 0.

Form submissions use page-based pagination instead:
- **`page`**: Page number, 1-based. Defaults to 1.
- **`page_size`**: Items per page. Defaults to 50, maximum 100.
- **`has_more`**: Boolean indicating whether more pages exist.

**curl example (paginated executions):**
```bash
# Get the second page of 10 executions
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/ex?limit=10&offset=10"
```

---

## SSE (Server-Sent Events)

Sentinel uses Server-Sent Events for real-time log streaming. SSE is a simple, browser-native protocol where the server pushes events to the client over a long-lived HTTP connection.

### How SSE Works in Sentinel

When you connect to an SSE endpoint, the server holds the connection open and sends events as they occur. Each event has the following SSE format:

```
id: 42
event: log
data: {"id":42,"ts":1707576000,"lv":"info","msg":"Processing order","eid":"exec_abc123"}

```

- **`id`**: A monotonically increasing log entry ID. Used for resume support through the `Last-Event-ID` header.
- **`event`**: The event type. Currently always `log` for log entries.
- **`data`**: This JSON log event includes `id` (log ID), `ts` (Unix timestamp), `lv` (debug/info/warn/error), and `msg` (message). Scoped events include `eid` (execution ID). Events with an available trace ID include `tid`.

### Follow Mode

By default, SSE endpoints return all existing logs and then close the connection (one-shot mode). To keep the connection open and receive new logs as they arrive, add `follow=true`:

```bash
# One-shot: get existing logs, then connection closes
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/ex/exec_abc123/lg

# Follow: stream logs continuously until client disconnects
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/ex/exec_abc123/lg?follow=true"
```

### Resume Support

If a client disconnects and reconnects, it can send the `Last-Event-ID` header with the ID of the last event it received. The server will resume streaming from that point, ensuring no logs are missed:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  -H "Last-Event-ID: 42" \
  "http://localhost:8080/lg?follow=true"
```

### Polling Interval

The server polls for new log entries every 500 milliseconds. An SSE event can arrive up to a half-second after the server writes the log.

### JavaScript Example

```javascript
const eventSource = new EventSource('http://localhost:8080/ex/exec_abc123/lg?follow=true', {
  headers: { 'Authorization': 'Bearer my-token' }
});

eventSource.addEventListener('log', (e) => {
  const log = JSON.parse(e.data);
  console.log(`[${log.lv}] ${log.msg}`);
});

// Server sends a comment ": stream complete" when follow=false and all logs are sent
eventSource.addEventListener('end', () => {
  eventSource.close();
});

eventSource.addEventListener('error', () => {
  // Connection lost -- EventSource will auto-reconnect with Last-Event-ID
});
```

---

## Health and Status

### Health Check

```
GET /hl
```

This endpoint returns the system status, uptime, version, and health of each component. The Dashboard polls it for status indicators.

Use this endpoint first to make sure that Sentinel is running and healthy.

**When to use:** Monitoring, health probes (for example Kubernetes liveness/readiness), verifying the server is up after deployment.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/hl
```

**Response:**
```json
{
  "status": "ok",
  "mode": "dev",
  "up": 12345,
  "time": 1707576000,
  "ver": "1.0.0",
  "project": "my-project",
  "components": {
    "state_db": "ok",
    "flow_manager": "ok",
    "scheduler": "ok",
    "webhook_router": "ok",
    "event_bus": "ok",
    "ws": "ok",
    "docker": {
      "ok": true,
      "stacks": 3
    }
  },
  "marketplace": {
    "license_type": "free",
    "tier": "community",
    "valid": true,
    "grace_period": false,
    "blocked": false
  }
}
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"ok"` if all components are healthy, `"degraded"` if any component is unhealthy |
| `mode` | string | `"dev"` if debug mode is on, `"prod"` otherwise |
| `up` | integer | Uptime in seconds since the harness started |
| `time` | integer | Current server time as Unix timestamp |
| `ver` | string | Binary version string (for example `"v0.1.1-dev"`) |
| `project` | string | SRE project name (derived from the SRE root directory name) |
| `components` | object | Health status of each internal component |
| `marketplace` | object | Marketplace license status (present only if marketplace is configured) |

**Component statuses:** Each component reports `"ok"`, `"unavailable"` (not configured), or `"unhealthy"`. If any component is unhealthy, the top-level `status` becomes `"degraded"`.

**Error conditions:** This endpoint rarely fails. If the server is running, it will respond. If it does not respond, the server is down.

### MCP sidecar status

```
GET /mcp
```

Operator snapshot of the optional MCP sidecar. Always HTTP 200. `enabled` is false when the harness was started without `--mcp`. The catalog is still returned so the dashboard can teach the surface. Never includes tokens, vault values, or occupy license keys.

**When to use:** The Dashboard MCP page uses this endpoint (`GET /mcp`, BFF `GET /api/dashboard/mcp`). Operator scripts can inspect binding, listener, and risk limits without an MCP session.

**Response (abbreviated):** `{ok, enabled, url, bind, listen, loopback, auth, risk_classes, aliases, disabled, start_hint, clients, tools, resources, prompts}`.

See [MCP Agent Integration](/mcp-agent-integration).

### List Kits

```
GET /hl/kt
```

This endpoint returns all kits that the harness discovered and loaded from the SRE directory. Each kit has a directory and a `kit.yaml` manifest. The Dashboard uses this endpoint to fill the kit explorer sidebar.

**When to use:** Discovering which kits are available, checking if a kit has UI pages, listing available kits for an AI agent.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/hl/kt
```

**Response:**
```json
{
  "ok": true,
  "kits": [
    {
      "namespace": "sn",
      "name": "core",
      "kit_name": "core",
      "description": "Core flows and modules",
      "version": "1.0.0",
      "has_ui": true,
      "page_count": 2,
      "form_count": 1,
      "on": true
    }
  ]
}
```

**Response fields (each kit):**

| Field | Type | Description |
|-------|------|-------------|
| `namespace` | string | Kit namespace (for example `"sn"`, `"acme"`) |
| `name` | string | Display name from manifest |
| `kit_name` | string | Kit name from `kit.yaml` (`kit-name`) |
| `description` | string | Human-readable description from `kit.yaml` |
| `version` | string | Kit version from manifest |
| `has_ui` | boolean | Whether the kit has UI page templates |
| `page_count` | integer | Number of registered pages |
| `form_count` | integer | Number of registered forms |
| `on` | boolean | Operational enable state (`kit_runtime`. Default `true`) |
| `ic` | string | Resolved catalog icon filename under `pb/` (`kt.ic.svg`, `.png`, or `.jpg` — first match wins) |
| `th` | string | Resolved card thumbnail filename (`kt.th.*`) |
| `hr` | string | Resolved hero banner filename (`kt.hero.*`) |
| `has_icon` | boolean | `true` when `ic` is set (legacy) |
| `has_thumb` | boolean | `true` when `th` is set |
| `has_hero` | boolean | `true` when `hr` is set |

Extension priority for each basename is **svg → png → jpg**. See **Kit development** → kit catalog images.

### Reload SRE

```
POST /hl/reload
```

This endpoint reloads all kits and flows from the SRE directory. It scans the root and parses each `kit.yaml` manifest. It discovers flows in `fl/` directories and registers their triggers again.

After file changes outside the API, use this endpoint. Examples include direct edits and Git pulls.

Note: If hot-reload is enabled in `sentinel.yaml`, the harness automatically detects file changes and reloads. This endpoint is for manual forced reloads.

**When to use:** After editing files on disk, after `git pull`, after installing a marketplace kit, or whenever flows seem stale.

**curl example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" http://localhost:8080/hl/reload
```

**Response:**
```json
{
  "ok": true,
  "msg": "SRE reloaded successfully",
  "kits_loaded": 3,
  "flows_registered": 12,
  "flows_removed": 2
}
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `kits_loaded` | integer | Kits registered after reload |
| `flows_registered` | integer | Flows registered after reload |
| `flows_removed` | integer | Stale flows unregistered during reload |

Disabled kits remain off after reload (`kit_runtime` is re-applied). See `specs/kitlife.md`.

**Error conditions:**
- `sre_root_unknown`: SRE root path not configured.
- `reload_unavailable`: Reload function not available (internal harness error).
- `reload_failed`: Reload failed (for example parse error in a `kit.yaml`).

### Reload One Kit

```
POST /hl/kt/{ns}/{name}/rl
```

Reloads a single kit directory `{ns}.{name}/` from disk: manifest, flows, forms, and page cache. `{name}` is the manifest `kit-name`, not the directory slug.

If the kit is disabled (`on: false`), manifest and forms still reload. Flows and triggers stay off until `POST .../on`.

**curl example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/hl/kt/sn/core/rl
```

**Response:**
```json
{
  "ok": true,
  "msg": "kit reloaded",
  "ns": "sn",
  "name": "core",
  "flows_added": 2,
  "flows_removed": 1,
  "flows_unchanged": 5,
  "on": true
}
```

**Error conditions:** `KIT_NOT_FOUND`, `RELOAD_FAILED`, `reload_unavailable`, `sre_root_unknown`.

### Disable Kit

```
POST /hl/kt/{ns}/{name}/off
```

Stops all flows and triggers for the kit without deleting files. State persists in `kit_runtime` across reload and restart.

**Optional body:**
```json
{ "reason": "debugging payment kit" }
```

**Response:**
```json
{
  "ok": true,
  "msg": "kit disabled",
  "ns": "sn",
  "name": "core",
  "on": false,
  "flows_stopped": 8,
  "triggers_removed": 14
}
```

While disabled, `POST /fl/{kit-flow}/run` and `GET /kt/{ns}/{name}/...` return `KIT_DISABLED`.

**Error conditions:** `KIT_NOT_FOUND`, `RELOAD_FAILED`, `reload_unavailable`.

### Enable Kit

```
POST /hl/kt/{ns}/{name}/on
```

Re-enables the kit in `kit_runtime` and runs a full per-kit reload (registers flows and triggers).

**Response:**
```json
{
  "ok": true,
  "msg": "kit enabled",
  "ns": "sn",
  "name": "core",
  "on": true,
  "flows_registered": 8
}
```

**Error conditions:** `KIT_NOT_FOUND`, `RELOAD_FAILED`, `reload_unavailable`, `sre_root_unknown`.

---

## Flows

Flows are the fundamental unit of execution in Sentinel. Each flow is a Lua script that lives in a kit's `fl/` directory. Flows are auto-discovered -- you never list them in `kit.yaml`.

### List Flows

```
GET /fl
```

Returns all discovered flows across all kits, along with their metadata, parameters, associated triggers, and run statistics. This is the primary endpoint for discovering what a Sentinel instance can do.

**When to use:** Listing available automations, building a flow picker UI, discovering flow parameters for an AI agent.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/fl
```

**Response:**
```json
{
  "flows": [
    {
      "id": "sn-core-agent:assistant",
      "name": "assistant",
      "desc": "AI assistant flow",
      "ver": "1.0.0",
      "kit": "sn.core-agent",
      "params": {
        "message": "string",
        "context": "string"
      },
      "triggers": ["tr_abc123"],
      "stats": {
        "last_run": "2026-02-10T11:30:00Z",
        "run_count": 1
      }
    }
  ]
}
```

**Response fields (each flow):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Full flow ID in format `{ns}-{name}:{flow}` (for example `sn-core-agent:assistant`) |
| `name` | string | Flow filename without `.lua` extension |
| `desc` | string | Description from the flow's skill twin (`.lua.md` file) |
| `ver` | string | Version from the kit's `kit.yaml` |
| `kit` | string | Kit directory name (for example `sn.core-agent`) |
| `params` | object | Expected parameters and their types |
| `triggers` | array | IDs of triggers attached to this flow |
| `stats` | object | Run statistics: `last_run` (ISO8601) and `run_count` |

### Get Flow Details

```
GET /fl/{id}
```

Returns details for a single flow.

**When to use:** Inspecting a specific flow before executing it, checking its parameters or trigger configuration.

**Path parameters:**
- `{id}` -- Flow ID in `{ns}-{name}:{flow}` format (for example `sn-core-agent:assistant`).

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/fl/sn-core-agent:assistant
```

**Response:** Same structure as a single item from the list endpoint above.

**Error conditions:**
- `RESOURCE.NOT_FOUND`: No flow with that ID exists.

### Execute Flow

```
POST /fl/{id}/run
```

Triggers an execution of the specified flow. The request body is passed to the flow as parameters, accessible inside the Lua `main()` function through the function's parameters or the trigger context. Flow execution is **asynchronous** -- this endpoint returns immediately with an execution ID. Use `/ex/{id}` to poll for completion, or `/ex/{id}/lg` to stream logs in real-time.

**When to use:** Running a flow on-demand from the CLI, Dashboard, or an external system. This is the "manual trigger" mechanism.

**Path parameters:**
- `{id}` -- Flow ID in `{ns}-{name}:{flow}` format.

**Request body:** Any valid JSON object. All key-value pairs become available as flow parameters.

**curl example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "context": "greeting"}' \
  http://localhost:8080/fl/sn-core-agent:assistant/run
```

**Response:**
```json
{
  "id": "exec_abc123",
  "fid": "sn-core-agent:assistant",
  "status": "queued"
}
```

**Response fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique execution ID. Use this to poll status or stream logs. |
| `fid` | string | Flow ID that was executed |
| `status` | string | Always `"queued"` on initial response |

**Error conditions:**
- `RESOURCE.NOT_FOUND`: Flow does not exist.
- `REQUEST.INVALID`: Request body is not valid JSON.

---

## Executions

Executions represent individual runs of a flow. Each execution has a lifecycle: `queued` -> `running` -> `completed` (or `failed`). Execution data is stored in the SQLite state database and includes timing, status, errors, and logs.

### List Executions

```
GET /ex
```

Returns a paginated list of execution history, optionally filtered by flow ID or status. Results are ordered by start time, most recent first.

**When to use:** Viewing execution history, monitoring recent runs, finding failed executions, auditing flow activity.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Maximum items to return (max: 100) |
| `offset` | integer | 0 | Number of items to skip |
| `flow` | string | (none) | Filter by flow ID (for example `sn-core-agent:assistant`) |
| `status` | string | (none) | Filter by status: `queued`, `running`, `completed`, or `failed` |

**curl examples:**
```bash
# List recent executions
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/ex

# List failed executions for a specific flow
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/ex?flow=sn-core-agent:assistant&status=failed&limit=5"

# Paginate through results
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/ex?limit=10&offset=20"
```

**Response:**
```json
{
  "execs": [
    {
      "id": "exec_abc123",
      "fid": "sn-core-agent:assistant",
      "status": "completed",
      "st": 1707574200,
      "ed": 1707574205,
      "err": null
    }
  ]
}
```

**Response fields (each execution):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique execution identifier |
| `fid` | string | Flow ID that was executed |
| `status` | string | `queued`, `running`, `completed`, or `failed` |
| `st` | integer | Start time as Unix timestamp |
| `ed` | integer | End time as Unix timestamp (0 if still running) |
| `err` | string/null | Error message if `status` is `failed`, otherwise null |

### Get Execution Details

```
GET /ex/{id}
```

Returns detailed information about a specific execution, including its parameters, return value, and error details.

**When to use:** Checking if a specific execution completed, retrieving its result, diagnosing why it failed.

**Path parameters:**
- `{id}` -- Execution ID (for example `exec_abc123`).

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/ex/exec_abc123
```

**Response:**
```json
{
  "id": "exec_abc123",
  "fid": "sn-core-agent:assistant",
  "status": "completed",
  "st": 1707574200,
  "ed": 1707574205,
  "err": null
}
```

**Error conditions:**
- `RESOURCE.NOT_FOUND`: No execution with that ID exists.

### Stream Execution Logs (SSE)

```
GET /ex/{id}/lg
```

Streams log entries for a specific execution using Server-Sent Events. If the execution is still running, use `follow=true` to receive logs in real-time as they are written by the flow.

**When to use:** Watching a flow's progress in real-time, debugging a running flow, capturing log output for a completed execution.

**Path parameters:**
- `{id}` -- Execution ID.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lv` | string | (all) | Filter by log level: `debug`, `info`, `warn`, `error` |
| `follow` | string | `false` | Set to `true` to keep the stream open for new logs |

**curl example:**
```bash
# Stream logs for a completed execution (one-shot)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/ex/exec_abc123/lg

# Follow logs for a running execution
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/ex/exec_abc123/lg?follow=true&lv=info"
```

**SSE event format:**
```
id: 1
event: log
data: {"id":1,"ts":1707574200,"lv":"info","msg":"Processing order","eid":"exec_abc123"}
```

**JavaScript example:**
```javascript
const eventSource = new EventSource(
  'http://localhost:8080/ex/exec_abc123/lg?follow=true'
);

eventSource.addEventListener('log', (e) => {
  const log = JSON.parse(e.data);
  console.log(`[${log.lv}] ${log.msg}`);
});

// When follow=false, server sends a comment when done
eventSource.addEventListener('end', () => {
  eventSource.close();
});

eventSource.addEventListener('error', () => {
  eventSource.close();
});
```

### Stream Logs (All)

```
GET /lg
```

Streams log entries across all executions. This is a firehose of all log output from the entire harness. Useful for a global monitoring view.

**When to use:** Global log monitoring, watching all flow activity across the system.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lv` | string | (all) | Filter by log level: `debug`, `info`, `warn`, `error` |
| `follow` | string | `false` | Set to `true` for continuous streaming |

**curl example:**
```bash
# Stream all error logs continuously
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/lg?lv=error&follow=true"
```

### Stream Logs (Unified)

```
GET /lg/live
```

Streams flow, connector, and trigger logs in a unified SSE format. This provides a categorized view that the Dashboard uses for its tabbed log viewer.

**When to use:** Dashboard integration, categorized log viewing.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tab` | string | `all` | Filter category: `all`, `flows`, `http`, `triggers` |

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/lg/live?tab=flows"
```

---

## Triggers

Triggers define how flows are invoked automatically. Sentinel supports four trigger types: `cron` (scheduled), `webhook` (HTTP callback), `event` (internal event bus), and `manual` (API-only, no automatic invocation). Triggers are created either declaratively in flow code or through the API.

### List Triggers

```
GET /tr
```

Returns all registered triggers across all flows.

**When to use:** Viewing all scheduled jobs, finding webhook URLs, auditing trigger configuration.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | string | (all) | Filter by type: `cron`, `webhook`, `event`, `manual` |
| `flow` | string | (all) | Filter by flow ID |

**curl example:**
```bash
# List all triggers
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/tr

# List only cron triggers
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8080/tr?type=cron"

# List triggers for a specific flow
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8080/tr?flow=sn-core-agent:heartbeat"
```

**Response:**
```json
{
  "triggers": [
    {
      "id": "cr_abc123",
      "flow": "sn-core-agent:heartbeat",
      "type": "cron",
      "src": "flow",
      "on": true,
      "created": "2026-02-10T00:00:00Z",
      "last": "2026-02-10T12:00:00Z",
      "schedule": "0 * * * *",
      "tz": "UTC"
    }
  ]
}
```

**Response fields (each trigger):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique trigger ID (for example `cr_` for cron and `wh_` for webhook) |
| `flow` | string | Flow ID this trigger invokes |
| `type` | string | `cron`, `webhook`, `event`, or `manual` |
| `src` | string | Origin: `flow` (declared in Lua) or `api` (created through API) |
| `on` | boolean | Whether the trigger is currently enabled |
| `created` | string | Creation timestamp (ISO8601) |
| `last` | string | Last invocation timestamp (ISO8601) |
| `schedule` | string | Cron expression (only for cron triggers) |
| `tz` | string | Timezone for cron schedule (only for cron triggers) |

### Create Trigger

```
POST /tr
```

Creates a new trigger for a flow. The request body varies depending on the trigger type.

**When to use:** Setting up a cron schedule for a flow, registering a webhook endpoint, subscribing a flow to an event.

**Cron trigger example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "flow": "sn-core-agent:heartbeat",
    "type": "cron",
    "schedule": "*/5 * * * *",
    "tz": "America/New_York"
  }' \
  http://localhost:8080/tr
```

**Webhook trigger example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "flow": "sn-core-agent:stripe-handler",
    "type": "webhook",
    "path": "/api/stripe",
    "auth": "hmac",
    "key": "whsec_...",
    "alg": "sha256",
    "sig_hdr": "Stripe-Signature"
  }' \
  http://localhost:8080/tr
```

**Event trigger example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "flow": "sn-core-agent:order-handler",
    "type": "event",
    "event": "order.completed"
  }' \
  http://localhost:8080/tr
```

**Response:** The created trigger object (same structure as the list response).

### Get Trigger Details

```
GET /tr/{id}
```

Returns details for a specific trigger.

**When to use:** Inspecting a trigger's configuration, checking when it last fired.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/tr/cr_abc123
```

**Response:** A single trigger object (same structure as the list response).

**Error conditions:**
- `RESOURCE.NOT_FOUND`: No trigger with that ID exists.

### Delete Trigger

```
DELETE /tr/{id}
```

Permanently removes a trigger. The associated flow is not deleted, only the trigger linkage. Cron triggers are unscheduled, webhook paths are unregistered, and event subscriptions are removed.

**When to use:** Removing a scheduled job, decommissioning a webhook endpoint.

**curl example:**
```bash
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/tr/cr_abc123
```

**Response:**
```json
{
  "status": "deleted",
  "id": "cr_abc123"
}
```

**Error conditions:**
- `RESOURCE.NOT_FOUND`: No trigger with that ID exists.

### Enable/Disable Trigger

```
POST /tr/{id}/enable
POST /tr/{id}/disable
```

Toggles a trigger on or off without deleting it. A disabled trigger retains its configuration but does not fire. This is useful for temporarily pausing a cron job or muting a webhook during maintenance.

**When to use:** Pausing a scheduled job, temporarily muting a webhook, maintenance windows.

**curl examples:**
```bash
# Disable a trigger
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/tr/cr_abc123/disable

# Re-enable it
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/tr/cr_abc123/enable
```

**Response:**
```json
{
  "status": "enabled",
  "id": "cr_abc123",
  "enabled": true
}
```

---

## Webhooks

Webhook endpoints are how external services (such as Stripe, GitHub, Slack, and Telegram) send data into Sentinel. Webhook routes are **auth-exempt** -- they bypass the gateway's bearer token authentication entirely. Instead, each webhook trigger defines its own authentication (`hmac`, `bearer`, `header`, CIDR allow-lists, or rate limits).

### Global Webhook

```
ANY /wh/*
```

The catch-all route for global webhooks. It accepts any HTTP method, including GET, POST, PUT, and DELETE. The path after `/wh/` is matched against registered webhook triggers' `path` field.

**When to use:** Receiving callbacks from external services like Stripe, GitHub, or any SaaS platform that sends webhooks.

**How routing works:** When a webhook trigger is created with `path: "/api/stripe"`, incoming requests to `POST /wh/api/stripe` are routed to that trigger's associated flow. The full request body, headers, and query parameters are passed to the flow.

**curl example (simulating an incoming webhook):**
```bash
curl -X POST http://localhost:8080/wh/api/stripe \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: t=1234,v1=abc123..." \
  -d '{"type": "payment_intent.succeeded", "data": {"id": "pi_123"}}'
```

**Response:** The flow's return value (serialized as JSON), or an error if no matching webhook trigger exists.

**Error conditions:**
- `WEBHOOK.NOT_FOUND`: No webhook trigger matches the given path.

### Kit Webhooks

```
ANY /kt/{ns}/{name}/wh/*
```

Kit-scoped webhook endpoint. Functions identically to the global webhook but is namespaced under a specific kit. This allows multiple kits to define webhooks with the same path without conflicts.

**Path parameters:**
- `{ns}` -- Kit namespace (for example `sn`).
- `{name}` -- Kit name (for example `core`).

**curl example:**
```bash
curl -X POST http://localhost:8080/kt/sn/core-agent/wh/hook \
  -H "Content-Type: application/json" \
  -d '{"event": "push", "ref": "refs/heads/main"}'
```

---

## Forms

The form system provides server-rendered HTML forms with submission tracking, response caching, and automatic flow triggering. Forms are defined as YAML files in a kit's `fm/` directory.

### Render Form (HTML)

```
GET /fm/{stub}
```

Renders the form as a complete HTML page. The form definition (fields, labels, validation) comes from the YAML file. The HTML is generated using Go templates with the kit's template system.

**When to use:** Displaying a form to end users in a browser.

**Path parameters:**
- `{stub}` -- The form's URL stub (defined in the form YAML).

**curl example:**
```bash
curl http://localhost:8080/fm/contact
```

**Response:** Complete HTML page (`Content-Type: text/html`).

### Submit Form

```
POST /fm/{stub}
```

Submits form data. Accepts standard HTML form encoding. After submission, any flows subscribed to this form's events are automatically triggered with the form data.

**When to use:** This is the form's `action` URL. Browsers submit to this endpoint when the user clicks the submit button.

**Request content types:** `application/x-www-form-urlencoded` or `multipart/form-data` (for file uploads).

**curl example:**
```bash
curl -X POST http://localhost:8080/fm/contact \
  -d "email=user@example.com&message=Hello&name=Alice"
```

**Response:** Depends on the form's `on_submit` template -- either an HTML response page or an HTTP redirect.

### Get Form Statistics

```
GET /fm/{stub}/stats
```

Returns detailed information about a form, including its field definitions, subscribed flows, and template variables. This is the JSON metadata endpoint for a form (as opposed to the HTML render endpoint above).

**When to use:** Dashboard form inspector, programmatic form discovery, checking which flows subscribe to a form.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/fm/contact/stats
```

**Response:**
```json
{
  "ok": true,
  "form": {
    "stub": "contact",
    "name": "Contact",
    "desc": "Contact form",
    "on_submit": "default-response",
    "static_cache_ttl": 3600,
    "has_password": false,
    "public": true,
    "fields": [
      {
        "name": "email",
        "type": "email",
        "label": "Email",
        "required": true
      }
    ],
    "url_stub": "contact",
    "kit_dir": "sn.core-agent"
  },
  "subscribed_flows": ["sn-core-agent:contact-handler"],
  "variables": {
    "key": "value"
  }
}
```

### List Form Submissions

```
GET /fm/{stub}/submissions
```

Returns a paginated list of all submissions for a form, with optional filtering by status or search text.

**When to use:** Viewing submission history, searching for specific submissions, monitoring form activity.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `search` | string | (none) | Text filter applied to submission data |
| `status` | string | (all) | Filter: `pending`, `processing`, `completed`, `failed` |
| `page` | integer | 1 | Page number (1-based) |
| `page_size` | integer | 50 | Items per page (max 100) |

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/fm/contact/submissions?status=completed&page=1&page_size=10"
```

**Response:**
```json
{
  "ok": true,
  "submissions": [
    {
      "id": "uuid-123",
      "stub": "contact",
      "submitted_at": 1707574200,
      "status": "completed",
      "ip_address": "203.0.113.10",
      "flows_executed": ["sn-core-agent:contact-handler"]
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 50,
  "has_more": false
}
```

### Get Single Submission

```
GET /fm/{stub}/submissions/{uuid}
```

Returns the full details of a specific form submission, including the submitted data, flow execution results, and any uploaded files.

**When to use:** Inspecting a submission's data, checking flow results, viewing upload details.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/fm/contact/submissions/uuid-123
```

**Response:**
```json
{
  "ok": true,
  "submission": {
    "id": "uuid-123",
    "stub": "contact",
    "submitted_at": 1707574200,
    "status": "completed",
    "ip_address": "203.0.113.10",
    "user_agent": "Mozilla/5.0",
    "form_data": {
      "email": "user@example.com",
      "message": "Hello from the form"
    },
    "flows_executed": ["sn-core-agent:contact-handler"],
    "flow_returns": {
      "sn-core-agent:contact-handler": { "ok": true, "msg": "Email sent" }
    },
    "flow_errors": {},
    "uploads": [],
    "url_stub": "contact"
  }
}
```

### Delete Submission

```
DELETE /fm/submissions/{uuid}
```

Permanently deletes a form submission and its associated data.

**When to use:** Data cleanup, GDPR compliance, removing test submissions.

**curl example:**
```bash
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/fm/submissions/uuid-123
```

**Response:**
```json
{
  "ok": true,
  "msg": "Submission deleted"
}
```

### Clear Response Cache

```
POST /fm/{stub}/clear-cache
```

Clears all cached form responses for a form. By default, form responses are cached permanently (keyed by submission UUID). This endpoint purges all cached responses for the given form stub.

**When to use:** After changing form templates, clearing stale cached responses, debugging.

**curl example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/fm/contact/clear-cache
```

**Response:**
```json
{
  "ok": true,
  "msg": "Cache cleared"
}
```

### Get Cached Response

```
GET /rsp/{stub}/{uuid}
```

Retrieves the cached HTML response for a specific form submission. After a form is submitted, the response page is cached and can be retrieved by the submission's UUID.

**When to use:** Displaying a "thank you" page after submission, retrieving a previously generated response.

**curl example:**
```bash
curl http://localhost:8080/rsp/contact/uuid-123
```

**Response:** Cached HTML page (`Content-Type: text/html`).

### List Forms (JSON)

```
GET /fm
```

Returns a summary of all forms across all kits. This is the JSON listing endpoint used by the Dashboard to populate the forms management view.

**When to use:** Dashboard form listing, programmatic form discovery.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/fm
```

**Response:**
```json
{
  "ok": true,
  "forms": [
    {
      "stub": "contact",
      "name": "Contact",
      "desc": "Contact form",
      "fields": 4,
      "submissions": 12,
      "has_password": false,
      "cache_count": 3,
      "url_stub": "contact",
      "kit_dir": "sn.core-agent",
      "last_submission": 1707574200
    }
  ],
  "total": 1
}
```

---

## Secrets

Secrets are encrypted key-value pairs stored in the Sentinel vault (AES-256-GCM encryption at rest). They are used to store API tokens, passwords, and other sensitive values that flows access through `ctx.secret("name")` in Lua.

### List Secrets

```
GET /sc
```

Returns metadata for all secrets. **Secret values are never returned by this endpoint** -- only names, creation dates, and update dates.

**When to use:** Viewing which secrets are configured, auditing secret management.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/sc
```

**Response:**
```json
{
  "secrets": [
    {
      "name": "slack_token",
      "created_at": "2026-02-09T00:00:00Z",
      "updated_at": "2026-02-10T11:30:00Z"
    }
  ]
}
```

### Create/Update Secret

```
POST /sc
```

Creates a new secret or updates an existing one. If a secret with the given name already exists, its value is overwritten.

**When to use:** Storing API keys, setting up credentials for connectors, rotating secrets.

**curl example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "slack_token",
    "value": "xoxb-1234567890-abcdef",
    "description": "Slack bot token for notifications",
    "tags": ["slack", "prod"]
  }' \
  http://localhost:8080/sc
```

**Request fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Secret name (used in `ctx.secret("name")`) |
| `value` | string | yes | Secret value (encrypted at rest) |
| `description` | string | no | Human-readable description |
| `tags` | array | no | Tags for organization |

**Response:**
```json
{
  "ok": true
}
```

### Delete Secret

```
DELETE /sc/{name}
```

Permanently deletes a secret from the vault. Any flow that calls `ctx.secret("name")` for this secret will fail after deletion.

**When to use:** Removing decommissioned credentials, cleaning up test secrets.

**curl example:**
```bash
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/sc/slack_token
```

**Response:**
```json
{
  "ok": true
}
```

---

## Source Management

Source management endpoints allow reading and writing the raw source code of flows, connectors, modules, and configuration files. These endpoints support ETag-based conflict detection to prevent overwriting concurrent edits.

### Get/Update Source by Literal SRE Path

```
GET /src/*
PUT /src/*
```

Access a file by its literal path relative to the SRE root. The wildcard `*` is the file path within the SRE directory.

**When to use:** Reading or editing a specific file when you know its exact path.

**GET curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/src/sn.core-agent/fl/assistant.lua
```

**GET Response:**
```json
{
  "src": "function setup()\n  -- setup code\nend\n\nfunction main()\n  ctx.log(\"info\", \"Hello\")\nend",
  "etag": "abc123def456"
}
```

**PUT curl example:**
```bash
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "src": "function setup()\nend\n\nfunction main()\n  ctx.log(\"info\", \"Updated\")\nend",
    "etag": "abc123def456"
  }' \
  http://localhost:8080/src/sn.core-agent/fl/assistant.lua
```

**ETag conflict detection:** If the file changed after your GET request, the server returns a `RESOURCE.CONFLICT` error. This prevents concurrent editors from overwriting changes.

When you update a file, include the `etag` from the GET response.

**Error conditions:**
- `RESOURCE.NOT_FOUND`: File does not exist.
- `RESOURCE.CONFLICT`: ETag mismatch (file was modified since you read it).

### Get/Update Source by Kit Folder

```
GET /{folder}/*
PUT /{folder}/*
```

Access source files using the kit ID format. The `{folder}` is the two-letter subdirectory prefix (for example `fl` for flows, `cn` for connectors, `md` for modules). The wildcard must end with `/src` (for source code) or `/skill` (for the `.md` skill twin).

**When to use:** Accessing source code when you know the kit and flow name but prefer the structured path format.

**curl examples:**
```bash
# Get flow source
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/fl/sn-core-agent:assistant/src

# Get skill twin (the .lua.md file)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/fl/sn-core-agent:assistant/skill
```

### List Connectors / Modules

```
GET /cn
GET /md
```

Returns all discovered connectors or modules across all kits.

**When to use:** Discovering available connectors (for `sn.cn.*` calls), listing modules (for `sn.md.*` calls).

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/cn
```

**Response:**
```json
{
  "items": [
    {
      "id": "sn.tools-http.http-json",
      "name": "slack",
      "type": "connector"
    }
  ]
}
```

---

## Configuration

### Get Project Config

```
GET /cfg/project
```

Returns the contents of `sentinel.yaml`, the project-level configuration file that lives in the SRE root and is committed to git. This file contains project metadata (name, description, version) and behavioral configuration (hot-reload, git integration).

**When to use:** Reading the current project configuration, displaying project metadata in a UI.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/cfg/project
```

**Response:**
```json
{
  "yaml": "name: my-project\nversion: 1.0.0\ndescription: My SRE project\ngit: true\nhotreload: true",
  "etag": "abc123"
}
```

### Update Project Config

```
PUT /cfg/project
```

Updates `sentinel.yaml`. The entire file contents are replaced. Use the `etag` from the GET response for conflict detection.

**When to use:** Changing project configuration, updating the project name or version.

**curl example:**
```bash
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "yaml": "name: my-project\nversion: 1.1.0\ndescription: Updated project\ngit: true\nhotreload: true",
    "etag": "abc123"
  }' \
  http://localhost:8080/cfg/project
```

**Important:** Never put infrastructure configuration (`api.port`, `logging`, `security`) in `sentinel.yaml`. Those belong in `.sentinel/config.json`.

---

## Git Operations

Sentinel provides a full git integration layer, allowing the Dashboard and API clients to perform git operations without direct shell access. All git commands operate on the SRE repository.

### Get Repository Info

```
GET /git/info
```

Returns the current state of the git repository: remote URL, branch, sync status (ahead/behind), and whether the working tree is clean.

**When to use:** Checking if there are unpushed commits, displaying git status in a UI, verifying remote configuration.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/git/info
```

**Response:**
```json
{
  "enabled": true,
  "configured": true,
  "remote": "origin",
  "remoteUrl": "git@github.com:acme/repo.git",
  "branch": "main",
  "clean": false,
  "ahead": 2,
  "behind": 0,
  "error": null
}
```

### Get Status

```
GET /git/st
```

Returns lists of modified, staged, and untracked files. Equivalent to `git status --porcelain`.

**When to use:** Review changed files before you select what to commit.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/git/st
```

**Response:**
```json
{
  "modified": [
    { "path": "sn.core-agent/fl/test.lua", "status": "M" }
  ],
  "staged": [],
  "untracked": [
    { "path": "sn.core-agent/fl/new.lua", "status": "?" }
  ]
}
```

### Show Diff

```
GET /git/diff?f=path/to/file
```

Returns the uncommitted diff for a specific file. Equivalent to `git diff -- path/to/file`.

**Query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `f` | string | File path relative to the SRE root |

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/git/diff?f=sn.core-agent/fl/test.lua"
```

**Response:** Raw diff text (`Content-Type: text/plain`).

### Show File at Revision

```
GET /git/show?f=path/to/file&rev=HEAD
```

Returns the contents of a file at a specific git revision. Equivalent to `git show {rev}:{path}`.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `f` | string | (required) | File path relative to SRE root |
| `rev` | string | `HEAD` | Git revision (for example a commit SHA, branch name, tag, or `HEAD~1`) |

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/git/show?f=sn.core-agent/fl/test.lua&rev=HEAD~1"
```

**Response:** Raw file content.

### Commit Changes

```
POST /git/commit
```

Stages the specified files and creates a git commit. Equivalent to `git add {files} && git commit -m {msg}`.

**When to use:** Committing changes made through the source editing API or the Dashboard editor.

**curl example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "msg": "Update assistant flow to handle edge cases",
    "files": ["sn.core-agent/fl/assistant.lua", "sn.core-agent/fl/assistant.lua.md"]
  }' \
  http://localhost:8080/git/commit
```

**Response:**
```json
{
  "ok": true,
  "sha": "abc123def456"
}
```

### Git Sync Operations

```
POST /git/pull       # Pull from remote
POST /git/push       # Push to remote
POST /git/sync       # Pull then push (convenience)
POST /git/discard    # Discard uncommitted changes to a file
```

These endpoints perform standard git operations. Pull and push use the SSH credentials stored in the vault (see SSH credentials below). Sync is a convenience that performs a pull followed by a push.

**Discard example (revert a file to its last committed state):**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"f": "sn.core-agent/fl/test.lua"}' \
  http://localhost:8080/git/discard
```

### Git SSH Credentials

```
GET    /git/credentials          # Check if SSH credentials exist
POST   /git/credentials          # Store SSH key pair
DELETE /git/credentials          # Remove SSH credentials
POST   /git/credentials/generate # Generate a new Ed25519 keypair
```

SSH credentials are stored encrypted in the vault and used for git push/pull operations over SSH.

**Generate a new keypair:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/git/credentials/generate
```

---

## Certificates

Certificate endpoints allow clients to download the Sentinel CA certificate for TLS certificate pinning. These endpoints are **unauthenticated** by design -- a client needs to retrieve the CA certificate before it can establish a trusted TLS connection.

### Download CA Certificate

```
GET /cert/ca.crt
```

Downloads the Certificate Authority certificate in PEM format. Use this to configure TLS certificate pinning in clients that connect to this Sentinel instance over HTTPS.

**When to use:** Setting up TLS trust for Dashboard connections, configuring certificate pinning in scripts.

**curl example:**
```bash
curl -o ca.crt http://localhost:8080/cert/ca.crt
```

**Response:** PEM-encoded certificate (`Content-Type: application/x-pem-file`).

### Download Server Certificate

```
GET /cert/server.crt
```

Downloads the server's TLS certificate. This is primarily for diagnostic and debugging purposes.

**curl example:**
```bash
curl -o server.crt http://localhost:8080/cert/server.crt
```

### Get Configuration Status

```
GET /api/config
```

Returns non-sensitive configuration status. This is the only authenticated-exempt JSON endpoint (besides webhooks). The Dashboard calls this before authenticating to discover what features are available (including TLS, the vault, and Git).

**When to use:** Feature discovery, Dashboard initialization, checking server capabilities.

**curl example:**
```bash
curl http://localhost:8080/api/config
```

**Response:**
```json
{
  "tls": {
    "enabled": true,
    "port": 8443
  },
  "state": {
    "encrypt_db": true
  },
  "vault_initialized": true,
  "api": {
    "port": 8080,
    "debug_mode": false
  },
  "git": {
    "enabled": true
  },
  "security": {
    "has_keypair": false
  }
}
```

---

## Content (CMS)

The CMS (Content Management System) provides structured access to Markdown content stored in kit `ct/` directories. Markdown files are parsed into a structured format with frontmatter metadata, a preamble (content before the first heading), and a recursive section tree. Content is cached in memory and automatically refreshed when files change (if hot-reload is enabled).

CMS endpoints are available only when at least one kit in the SRE has a `ct/` subdirectory. If no kit has content, all CMS endpoints return `CMS.UNAVAILABLE`.

### List CMS Content Slugs

```
GET /cm
```

Returns all available content slugs across all kits. Each slug is prefixed with its kit name. Slugs can contain path segments for hierarchically organized content.

**When to use:** Building a content index, discovering available pages, generating a sitemap.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/cm
```

**Response:**
```json
{
  "ok": true,
  "slugs": [
    "acme.blog/hello-world",
    "acme.blog/tutorials/getting-started",
    "sn.docs/api-overview"
  ]
}
```

The slug format is `{kitName}/{contentSlug}`. The Markdown frontmatter can define a `slug` field. Otherwise, the content slug is the filename without `.md`. Subdirectories in `ct/` add path segments.

**Error conditions:**
- `CMS.UNAVAILABLE`: No kit in the SRE has a `ct/` directory.

### Get CMS Content

```
GET /cm/{kitName}/{contentSlug}
```

Returns the fully parsed content for a specific slug. The response includes frontmatter metadata, a preamble (HTML rendered from content before the first heading), and a recursive section tree.

**When to use:** Rendering a blog post, displaying documentation, serving structured content to a frontend.

**Path parameters:**
- `{kitName}` -- Kit directory name (for example `acme.blog`).
- `{contentSlug}` -- Content slug, which can contain path segments (for example `hello-world` or `tutorials/getting-started`).

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/cm/acme.blog/hello-world
```

**Response:**
```json
{
  "ok": true,
  "kit": "acme.blog",
  "slug": "hello-world",
  "frontmatter": {
    "title": "Hello World",
    "slug": "hello-world",
    "date": "2026-02-27",
    "description": "First post on the blog",
    "tags": ["intro", "blog"],
    "meta": {}
  },
  "preamble": "<p>This is the intro paragraph before any headings.</p>\n",
  "sections": {
    "getting-started": {
      "title": "Getting Started",
      "slug": "getting-started",
      "level": 2,
      "html": "<p>Everything you need to know to begin.</p>\n",
      "sections": {
        "installation": {
          "title": "Installation",
          "slug": "installation",
          "level": 3,
          "html": "<pre><code>npm install sentinel</code></pre>\n",
          "sections": {}
        }
      }
    },
    "next-steps": {
      "title": "Next Steps",
      "slug": "next-steps",
      "level": 2,
      "html": "<p>Where to go from here.</p>\n",
      "sections": {}
    }
  }
}
```

**Frontmatter fields:**

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Document title |
| `slug` | string | Content slug (the canonical identifier for this content) |
| `date` | string | Publication date (RFC3339 or YYYY-MM-DD format) |
| `description` | string | Short description / summary |
| `tags` | string[] | List of tag strings for categorization |
| `meta` | object | Any more frontmatter fields not recognized by the parser |

**Important:** The `agent_context` frontmatter field is always stripped from API responses. It is only available in Lua through `sn.cms.get()`. This allows content authors to include AI agent instructions in their Markdown that are visible to automation flows but never exposed to external API consumers.

**Preamble:** HTML string rendered from any content that appears before the first heading in the Markdown file. If the document starts immediately with a heading, the preamble is an empty string.

**Sections:** A recursive map keyed by section slug. Each section contains:

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Original heading text |
| `slug` | string | URL-safe slug, scoped to parent heading. Duplicate slugs are deduplicated with `-2`, `-3` suffixes |
| `level` | integer | Heading level (1-6) |
| `html` | string | Rendered HTML of the content directly under this heading (including paragraphs, code blocks, and tables) |
| `sections` | object | Nested child sections (same structure, recursively) |

**Error conditions:**

| Code | Condition |
|------|-----------|
| `CMS.NOT_FOUND` | No content with that slug exists in the specified kit |
| `CMS.UNAVAILABLE` | CMS cache not initialized (no kit has a `ct/` directory) |
| `CMS.INVALID_SLUG` | Path does not contain the required `{kitName}/{contentSlug}` format |

**curl example (nested slug):**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/cm/acme.blog/tutorials/getting-started
```

---

## Storage Points

Storage points represent S3-compatible object storage endpoints (such as AWS S3, Backblaze B2, and Garage). They allow flows to upload and manage files in cloud storage. Credentials are stored encrypted in the vault. See the [Storage Guide](/storage) for full documentation on configuring and using storage.

### List Storage Points

```
GET /st
```

Returns all registered storage points. Credentials are never included in the response.

**When to use:** Viewing configured storage backends, selecting a storage point for upload.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/st
```

**Response:**
```json
{
  "ok": true,
  "points": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "production-media",
      "stub": "img",
      "provider": "s3",
      "endpoint": "",
      "region": "us-east-1",
      "bucket": "my-media-bucket",
      "path_prefix": "media/",
      "public_url": "https://cdn.example.com/",
      "created_at": "2026-02-28T10:00:00Z",
      "updated_at": "2026-02-28T10:00:00Z"
    }
  ]
}
```

### Get Storage Point

```
GET /st/{id}
```

Returns a single storage point by its UUID.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/st/550e8400-e29b-41d4-a716-446655440000
```

**Response:**
```json
{
  "ok": true,
  "point": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "production-media",
    "stub": "img",
    "provider": "s3",
    "endpoint": "",
    "region": "us-east-1",
    "bucket": "my-media-bucket",
    "path_prefix": "media/",
    "public_url": "https://cdn.example.com/",
    "created_at": "2026-02-28T10:00:00Z",
    "updated_at": "2026-02-28T10:00:00Z"
  }
}
```

### Create Storage Point

```
POST /st
```

Creates a new storage point and stores its access credentials in the vault.

**When to use:** Adding a new S3 bucket, configuring Backblaze B2 storage, setting up Garage.

**curl example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "production-media",
    "stub": "img",
    "provider": "s3",
    "endpoint": "",
    "region": "us-east-1",
    "bucket": "my-media-bucket",
    "path_prefix": "media/",
    "public_url": "https://cdn.example.com/",
    "access_key": "AKIAIOSFODNN7EXAMPLE",
    "secret_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
  }' \
  http://localhost:8080/st
```

**Required fields:** `name`, `stub`, `provider`, `bucket`, `public_url`, `access_key`, `secret_key`.

**Provider values:** `s3` (AWS S3 or compatible), `b2` (Backblaze B2), `garage` (Garage).

**Response:**
```json
{
  "ok": true,
  "point": { ... }
}
```

### Update Storage Point

```
PUT /st/{id}
```

Updates an existing storage point. Same body as create. Leave `access_key` and `secret_key` empty to keep existing vault credentials.

**curl example:**
```bash
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "production-media-v2",
    "stub": "img",
    "provider": "s3",
    "bucket": "my-new-bucket",
    "public_url": "https://cdn2.example.com/",
    "access_key": "",
    "secret_key": ""
  }' \
  http://localhost:8080/st/550e8400-e29b-41d4-a716-446655440000
```

### Delete Storage Point

```
DELETE /st/{id}
```

Deletes a storage point and its vault credentials.

**curl example:**
```bash
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/st/550e8400-e29b-41d4-a716-446655440000
```

**Response:**
```json
{
  "ok": true
}
```

### Test Storage Point Connection

```
POST /st/{id}/test
```

Tests connectivity for a storage point by verifying that vault credentials exist and are accessible. This does not actually connect to the storage provider -- it only checks the local credential setup.

**curl example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/st/550e8400-e29b-41d4-a716-446655440000/test
```

**Response:**
```json
{
  "ok": true,
  "msg": "credentials found",
  "provider": "s3",
  "endpoint": "",
  "bucket": "my-media-bucket",
  "region": "us-east-1"
}
```

---

## PostgreSQL Connections

Manage PostgreSQL connection pools. These pools are used by Lua flows through `ctx.pg("name")`.

### List PostgreSQL Connections

```
GET /pg
```

Returns all configured PostgreSQL connections and their current status.

**curl example:**
```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8080/pg
```

### Add PostgreSQL Connection

```
POST /pg
```

Adds a new PostgreSQL connection pool. The submitted connection URL is encrypted into the vault, and `.sentinel/data/pg_connections.json` stores only the connection name plus a vault secret reference.

**curl example:**
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "main",
    "host": "localhost",
    "port": 5432,
    "database": "myapp",
    "user": "sentinel",
    "password": "secret"
  }' \
  http://localhost:8080/pg
```

### Remove PostgreSQL Connection

```
DELETE /pg/{name}
```

Removes a PostgreSQL connection pool by name.

**curl example:**
```bash
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/pg/main
```

### Test PostgreSQL Connection

```
POST /pg/test
```

Tests a PostgreSQL connection without saving it to either the vault or the persisted connection registry.

### Reconnect PostgreSQL Pool

```
POST /pg/{name}/reconnect
```

Reconnects an existing PostgreSQL pool (for example after a database restart).

---

## Backups

The backup subsystem is a harness-owned control plane for scheduled folder archives, single-file backups, and PostgreSQL dumps.

### List Backup Plans

```
GET /bk/plans
```

Returns all configured backup plans.

### Get Backup Plan

```
GET /bk/plans/{id}
```

Returns a single backup plan by ID.

### Create Backup Plan

```
POST /bk/plans
```

Example body:

```json
{
  "name": "nightly-artifacts",
  "backup_type": "folder",
  "enabled": true,
  "schedule": "0 2 * * *",
  "frequency": "daily",
  "compression_enabled": true,
  "source_path": "artifacts",
  "storage_point_id": "storage-uuid",
  "remote_prefix": "backups/nightly",
  "retention_count": 7
}
```

For PostgreSQL plans, use `backup_type: "postgres"` and `pg_connection` instead of `source_path`.

For local file plans, use `backup_type: "file"` and `source_path` pointing at a single file such as `.sentinel/state.db`, `.sentinel/vault.db`, `.sentinel/cms.db`, or `.sentinel/data/sn.db`.

### Update Backup Plan

```
PUT /bk/plans/{id}
```

Uses the same body shape as create.

### Delete Backup Plan

```
DELETE /bk/plans/{id}
```

Deletes the saved plan definition.

### List Backup Runs

```
GET /bk/runs
```

Supports `?limit=` for result count.

### Get Backup Run

```
GET /bk/runs/{id}
```

Returns a single backup run record.

### Run Backup Plan Immediately

```
POST /bk/plans/{id}/run
```

This endpoint runs the plan immediately and records the run in `backup_runs`. It applies local retention under `.sentinel/backups`. If the plan has a `storage_point_id`, it also uploads the artifact to object storage.

---

## API Library

The API Library stores vendor-packaged API definitions, endpoints, and callable templates in the local Sentinel library database. It supports single-vendor and multi-vendor JSON import/export, plus LLM-assisted scrape generation.

### Get Vendor Collection Schema

```
GET /lib/schema
```

Returns the canonical JSON schema for a vendor-packaged Sentinel API Library collection.

### Export All Vendors

```
GET /lib/export
```

Returns all vendors as one JSON bundle suitable for committing into the SRE and re-importing on a new deployment.

### Export One Vendor

```
GET /lib/{id}/export
```

Returns one vendor-packaged JSON collection for the specified vendor.

### Import One Vendor

```
POST /lib/import
```

Accepts one vendor-packaged JSON collection.

### Import All Vendors

```
POST /lib/import-all
```

Accepts a multi-vendor JSON bundle with a top-level `vendors` array.

### Scrape Docs Into A Vendor Collection

```
POST /lib/scrape
```

This endpoint fetches documentation URLs and sends the extracted content to a registered LLM provider and model. It validates the resulting JSON collection. It can also import the collection immediately.

Example body:

```json
{
  "vendor_id": "deepseek",
  "display_name": "DeepSeek",
  "provider": "openai",
  "model": "deepseek-chat",
  "docs_urls": [
    "https://api-docs.deepseek.com/api/introduction",
    "https://api-docs.deepseek.com/api/create-chat-completion"
  ],
  "notes": "Prefer chat and models endpoints first.",
  "import_immediately": true
}
```

### Backup Event Patterns

The harness emits these internal event-bus patterns for reactive flows:
- `backup.schedule.synced`.
- `backup.run.started`.
- `backup.run.completed`.
- `backup.run.failed`.

---

## WebSocket

Sentinel provides two WebSocket upgrade endpoints. The multiplexed endpoint (`/ws`) uses envelopes for multiple channels on one connection. Per-channel endpoints (`/ws/{channel}`) deliver raw messages for one channel. WebSockets are disabled by default. Administrators can enable them in `.sentinel/config.json` or on the dashboard Sockets page. Separate management endpoints provide configuration and outbound connection controls. Only administrators can use these management endpoints.

### Multiplexed WebSocket

```
GET /ws
```

Upgrades the HTTP connection to a multiplexed WebSocket. Clients send JSON envelopes to subscribe to channels, unsubscribe, and publish messages. The server sends envelopes back with acknowledgements, errors, and published messages.

If the websocket subsystem is disabled, the upgrade is rejected with standard HTTP `503 Service Unavailable`.

**When to use:** Use this endpoint for multiple subscriptions on one connection. Dashboard examples include notifications, status updates, and log streams.

**Envelope protocol:**

All messages (client-to-server and server-to-client) are JSON objects with an `op` (operation) field.

**Client-to-server operations:**

| Operation | Fields | Description |
|-----------|--------|-------------|
| `sub` | `ch` | Subscribe to a channel. Server responds with `ack`. |
| `unsub` | `ch` | Unsubscribe from a channel. Server responds with `ack`. |
| `pub` | `ch`, `data` | Publish a message to a channel. All subscribers (including this client) receive it. |

**Server-to-client operations:**

| Operation | Fields | Description |
|-----------|--------|-------------|
| `ack` | `ch` | Confirms a `sub` or `unsub` operation. |
| `pub` | `ch`, `data` | A message was published to a channel you are subscribed to. |
| `error` | `msg` | An error occurred (for example missing channel name). |

**Client-to-server examples:**
```json
{"op":"sub","ch":"notifications"}
{"op":"unsub","ch":"notifications"}
{"op":"pub","ch":"notifications","data":{"type":"alert","msg":"Server restarted"}}
```

**Server-to-client examples:**
```json
{"op":"ack","ch":"notifications"}
{"op":"pub","ch":"notifications","data":{"type":"alert","msg":"Server restarted"}}
{"op":"error","msg":"channel required for sub"}
```

**JavaScript example:**
```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  // Subscribe to channels
  ws.send(JSON.stringify({op: 'sub', ch: 'notifications'}));
  ws.send(JSON.stringify({op: 'sub', ch: 'status'}));
};

ws.onmessage = (event) => {
  const env = JSON.parse(event.data);

  switch (env.op) {
    case 'ack':
      console.log('Subscribed to:', env.ch);
      break;
    case 'pub':
      console.log(`[${env.ch}]`, env.data);
      break;
    case 'error':
      console.error('WS error:', env.msg);
      break;
  }
};

// Publish a message
ws.send(JSON.stringify({
  op: 'pub',
  ch: 'notifications',
  data: {type: 'test', msg: 'Hello from browser'}
}));
```

### Channel WebSocket

```
GET /ws/{channel}
```

Upgrades to a channel-specific WebSocket. Unlike the multiplexed endpoint, messages on this connection are **raw payloads** with no envelope wrapping. Every message sent by any client on this channel (or by Lua flows through `sn.ws.broadcast()`) is delivered as-is to all connected clients.

**When to use:** Simple, single-purpose real-time connections where envelope overhead is unnecessary. For example, a status dashboard page that only needs to show health updates.

**Path parameters:**
- `{channel}` -- Channel name (for example `status`, `notifications`, `live-data`).

**JavaScript example:**
```javascript
const ws = new WebSocket('ws://localhost:8080/ws/status');

ws.onmessage = (event) => {
  // No envelope -- event.data is the raw message
  const status = JSON.parse(event.data);
  document.getElementById('health').textContent = status.healthy ? 'OK' : 'DOWN';
};
```

### WebSocket Configuration

```
GET /ws/cfg
PUT /ws/cfg
```

Reads or updates websocket runtime configuration. These endpoints are admin-only and require dashboard signature authentication in production.

`GET /ws/cfg` returns the current configuration plus an `active` flag indicating whether the subsystem is started.

`PUT /ws/cfg` accepts:

```json
{
  "enabled": true,
  "inbound_drop_threshold": 32,
  "outbound_drop_threshold": 32
}
```

Changes are persisted to `.sentinel/config.json` and applied immediately without a full harness restart.

### List WebSocket Connections

```
GET /ws/cn
```

Returns all active outbound WebSocket connections created by Lua flows through `sn.ws.open()`. This does not list inbound browser connections to `/ws` or `/ws/{channel}`. Private kit-scoped connections are hidden from this unscoped management endpoint.

This endpoint is admin-only. In production it requires dashboard signature authentication rather than a bearer token.

**When to use:** Monitoring active outbound connections, debugging connection issues.

**curl example:**
```bash
curl -H "X-Sn-Sig: ..." http://localhost:8080/ws/cn
```

**Response:**
```json
{
  "ok": true,
  "items": [
    {
      "name": "my-api",
      "url": "wss://api.example.com/ws",
      "st": "connected",
      "dir": "out",
      "priv": false,
      "ca": 1709472000,
      "ms": 42,
      "mr": 38
    }
  ],
  "total": 1
}
```

**Response fields (each connection):**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Connection name (as passed to `sn.ws.open()`) |
| `url` | string | Remote WebSocket URL |
| `st` | string | Status: `connected`, `disconnected`, `reconnecting` |
| `dir` | string | Direction: `in` (inbound) or `out` (outbound) |
| `priv` | boolean | Whether this is a private (kit-scoped) connection |
| `ca` | integer | Created-at Unix timestamp |
| `ms` | integer | Total messages sent |
| `mr` | integer | Total messages received |
| `md` | integer | Messages dropped due to backpressure or receive-queue overflow |

### Get WebSocket Connection

```
GET /ws/cn/{name}
```

Returns details for a specific outbound WebSocket connection. Private kit-scoped connections are not exposed through this unscoped management endpoint.

This endpoint is admin-only.

**curl example:**
```bash
curl -H "X-Sn-Sig: ..." http://localhost:8080/ws/cn/my-api
```

**Response:**
```json
{
  "ok": true,
  "item": {
    "name": "my-api",
    "url": "wss://api.example.com/ws",
    "st": "connected",
    "dir": "out",
    "priv": false,
    "ca": 1709472000,
    "ms": 42,
    "mr": 38
  }
}
```

### Close WebSocket Connection

```
DELETE /ws/cn/{name}
```

Forcefully closes an outbound WebSocket connection. The connection is removed from the manager and cannot be reused. Flows will need to call `sn.ws.open()` again if they need a new connection with this name. Private kit-scoped connections cannot be closed through this unscoped management endpoint.

This endpoint is admin-only. Manual closes are audit logged.

**curl example:**
```bash
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/ws/cn/my-api
```

**Response:**
```json
{
  "ok": true,
  "msg": "connection closed"
}
```

---

## Error Codes

All error codes follow the `DOMAIN.ACTION` format. Here is the complete list:

| Code | Meaning | When it occurs |
|------|---------|----------------|
| `AUTH.REQUIRED` | Bearer token or signature required | Request to authenticated endpoint without credentials |
| `AUTH.INVALID` | Invalid or expired token/signature | Bearer token not in valid tokens list, or signature verification failed |
| `AUTH.IP_DENIED` | IP not in whitelist | Debug mode: request from non-whitelisted IP |
| `AUTH.RATE_LIMIT` | Rate limit exceeded | Too many requests from the same IP |
| `REQUEST.INVALID` | Malformed request | Examples: JSON parse error or missing Content-Type |
| `REQUEST.MISSING` | Required parameter missing | A required field was not provided |
| `RESOURCE.NOT_FOUND` | Resource does not exist | Flow, execution, trigger, or secret not found |
| `RESOURCE.CONFLICT` | ETag mismatch | Source file was modified since last read (concurrent edit) |
| `SYSTEM.ERROR` | Internal server error | Examples: unhandled panic or database error |
| `SYSTEM.TIMEOUT` | Operation timeout | Flow execution or HTTP operation timed out |
| `CMS.UNAVAILABLE` | CMS cache not initialized | No kit in the SRE has a `ct/` content directory |
| `CMS.NOT_FOUND` | Content slug not found | Requested CMS slug does not exist in the specified kit |
| `CMS.INVALID_SLUG` | Invalid slug format | Path is missing the required `{kitName}/{contentSlug}` structure |

---

## Rate Limiting

By default, Sentinel enforces a rate limit of **100 requests per second per IP address**. This is configurable in `.sentinel/config.json`:

```json
{
  "api": {
    "rate_limit": 200
  }
}
```

When the rate limit is exceeded, the response body contains:

```json
{
  "code": "AUTH.RATE_LIMIT",
  "msg": "Rate limit exceeded"
}
```

Rate limiting applies to all endpoints including auth-exempt routes. Each unique client IP gets its own counter.

---

## CORS (Cross-Origin Resource Sharing)

CORS is configured through the `cors_origins` setting in `.sentinel/config.json`. When configured, the following headers are set on responses:

- `Access-Control-Allow-Origin`: The matched origin.
- `Access-Control-Allow-Methods`: `GET, POST, PUT, DELETE, OPTIONS`.
- `Access-Control-Allow-Headers`: `Authorization, Content-Type, X-Request-ID`.
- `Access-Control-Expose-Headers`: `X-Request-ID`.
- `Access-Control-Max-Age`: `86400` (24 hours).

Preflight `OPTIONS` requests are handled automatically and return `204 No Content`.

---

## Best Practices

1. **Examine errors in the response body.** A `code` field indicates failure. All responses use HTTP 200, so status codes do not identify application errors.

2. **Use ETags for source editing.** When updating source files, always include the `etag` from the GET response. This prevents accidental overwrites from concurrent editors.

3. **Stream logs instead of polling.** For long-running flows, use the SSE endpoint `/ex/{id}/lg?follow=true` instead of repeatedly polling `/ex/{id}`. SSE is more efficient and provides real-time output.

4. **Use pagination for large result sets.** Pass `limit` and `offset` when you list executions or other large collections. Defaults suit interactive use. Automation can need different values.

5. **Cache form responses.** Form responses are cached permanently by default (keyed by submission UUID). The Dashboard retrieves cached responses directly instead of re-rendering.

6. **Use the health endpoint for monitoring.** The `/hl` endpoint provides component-level health status. Use it as a Kubernetes liveness probe or in monitoring dashboards. A `status` of `"degraded"` indicates at least one component is unhealthy.

7. **Store all credentials in the vault.** Never hardcode API tokens, passwords, or keys in flow source code. Use `POST /sc` to store them in the vault and access them through `ctx.secret("name")` in Lua.

8. **Prefer multiplexed WebSocket for multi-channel clients.** For multiple channels, use the `/ws` endpoint with envelopes. Avoid separate `/ws/{channel}` connections for each channel.
