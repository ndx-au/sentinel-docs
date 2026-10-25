---
title: "Configuration Guide"
description: "Reference for shared project configuration, local infrastructure configuration, security, backups, and deployment."
type: Guide
tags: [configuration]
status: stable
---

<!-- ndx-ste-mode: description -->

# Configuration Guide

Comprehensive guide to Sentinel configuration, security, deployment, and performance tuning.

---

## Introduction

Sentinel uses a **two-layer configuration** system. One layer stores behavior that the team shares. The other layer stores infrastructure details for each machine. Developers can clone the shared configuration from Git. Ports, encryption keys, and database paths remain private to each machine.

**Why two layers?**

A team of five developers shares Git synchronization, hot reload behavior, and project metadata. Alice uses port 8080. Bob uses port 9000 because another service uses port 8080. Alice uses TLS, and Bob uses HTTP for development. They use different vault passphrases. Machine details stay outside Git so they do not conflict.

The two layers solve this by putting shared configuration in `sentinel.yaml` (committed to git) and machine-specific configuration in `.sentinel/config.json` (gitignored).

**Configuration loading order:**

1. Built-in defaults (hardcoded in the binary).
2. `.sentinel/config.json` file (overrides defaults).
3. Environment variables with `SENTINEL_` prefix (override file values).
4. Command-line flags (override everything).

This means you can always override any setting temporarily through environment variables or flags without modifying files.

---

## sentinel.yaml (Git-Tracked)

**Location:** Project root (for example `my-project/sentinel.yaml`)

**Purpose:** Team-shared behavior configuration. Everything in this file describes how the project behaves, not how the infrastructure is set up. Every team member gets the same configuration when they clone the repository.

**Tracked in git:** Yes. Commit this file to version control.

**Created by:** `sentinel sre init` command.

### Complete Schema

```yaml
# ── Project Metadata ────────────────────────────────────────────────
# These fields identify the project. They are displayed in the dashboard
# and included in API responses from the /hl (health) endpoint.

name: my-project
# Required. The human-readable name of the project.
# This appears in the dashboard header and in log output.

version: 1.0.0
# Optional. Semantic version of the project.
# Used for tracking deployments and displayed in health checks.

description: My Sentinel automation project
# Optional. A brief description of what this project does.
# Displayed in the dashboard overview and health endpoint.

# ── Editor Extensions ───────────────────────────────────────────────
# Maps file extensions to syntax highlighting modes for editors and IDEs.
# This is advisory metadata used by tools that integrate with Sentinel.

editor_exts:
  lua: lua
  yaml: yaml

# ── Git Sync ────────────────────────────────────────────────────────
# Controls how Sentinel interacts with git for automatic version control.
# When enabled, the harness automatically commits and optionally pushes
# changes to the remote repository.

git:
  sync: auto
  # How git sync operates. Options:
  #   auto   - Automatically commit and push on a timer (default)
  #   manual - Only sync when explicitly triggered via API or dashboard
  #   off    - Disable git sync entirely

  push: true
  # Whether to push commits to the remote after committing.
  # Set to false if you only want local commits (e.g., for audit trail).

  interval: 5m
  # How often to check for changes and commit. Uses Go duration format:
  #   30s, 1m, 5m, 10m, 1h, etc.
  # Shorter intervals mean more granular history but more git operations.

  include_backups: false
  # Whether to include database backup files in git commits.
  # Usually false because backup files are large and change frequently.

  on_conflict: alert
  # What to do when a git conflict is detected during sync. Options:
  #   alert  - Log a warning and pause sync until manually resolved
  #   branch - Create a new branch with the conflicting changes
  #   pause  - Pause sync entirely until the user intervenes

# ── Hot Reload ──────────────────────────────────────────────────────
# Controls how the harness responds to file changes while running.
# Hot reload watches the project directory for changes and updates
# the running state without requiring a restart.

hotreload:
  yaml: full
  # How YAML file changes (kit.yaml, form definitions, page definitions)
  # are handled. Options:
  #   full - Reload everything: re-parse manifests, re-register forms,
  #          re-discover pages, rebuild navigation (may briefly interrupt)
  #   safe - Only reload files that can be safely updated without
  #          affecting running executions (conservative approach)
```

### What Does NOT Belong in sentinel.yaml

The following configuration must never be placed in `sentinel.yaml`. They belong in `.sentinel/config.json` or environment variables:

- `api.port` -- Machine-specific (different developers use different ports).
- `api.tokens` -- Security credentials (never commit to git).
- `log.level`, `log.format` -- Developer preference.
- `tls.*` -- Machine-specific certificates and hostnames.
- `vault_passphrase` -- Secret (never commit to git).
- `state.*` -- Machine-specific database configuration.
- `lua.*` -- Machine-specific performance tuning.
- `marketplace.*` -- Per-user authentication and licensing.

### Examples

**Minimal project:**

```yaml
name: my-project
version: 1.0.0
description: My first Sentinel project
```

This is all you need to get started. The harness will use defaults for everything else.

**Complex project with git sync and careful hot-reload:**

```yaml
name: e-commerce-platform
version: 2.1.0
description: Complete e-commerce workflow automation

git:
  sync: auto
  push: true
  interval: 10m
  include_backups: true
  on_conflict: branch

hotreload:
  yaml: safe
```

---

## .sentinel/config.json (Gitignored)

**Location:** `.sentinel/config.json` inside the project directory (for example `my-project/.sentinel/config.json`)

**Purpose:** Machine-specific infrastructure configuration. Everything in this file describes how the harness runs on this particular machine -- ports, security, performance tuning, database configuration, and marketplace credentials.

**Tracked in git:** No. The `.sentinel/` directory is gitignored by default. This file must never be committed because it contains security-sensitive configuration (tokens, passphrases) and machine-specific values (ports, paths, hostnames).

**Auto-created:** Yes. When the harness starts for the first time and this file does not exist, it is created automatically with default values. You can also create it during `sentinel sre init` if you choose to configure vault encryption.

### Complete Schema Reference

The following is the complete configuration schema with every field documented, including its type, default value, and purpose.

```json
{
  "data_dir": ".sentinel",
  "keyhole": "blocked",
  "vault_passphrase": "",
  "log": {
    "level": "info",
    "format": "text"
  },
  "api": {
    "port": 8080,
    "debug_mode": true,
    "tokens": [],
    "ip_whitelist": []
  },
  "tls": {
    "enabled": false,
    "port": 8443,
    "cert_dir": "",
    "hosts": ["localhost"],
    "ips": ["127.0.0.1"]
  },
  "state": {
    "busy_timeout": 5000,
    "encrypt_db": false,
    "state_passphrase": ""
  },
  "lua": {
    "pool_size": 10,
    "registry_size": 256,
    "execution_timeout": 30
  },
  "ws": {
    "enabled": false,
    "max_connections": 100,
    "max_message_size_kb": 64,
    "read_buffer_kb": 4,
    "write_buffer_kb": 4,
    "handshake_timeout_ms": 10000,
    "ping_interval_ms": 30000,
    "pong_timeout_ms": 10000,
    "inbound_drop_threshold": 32,
    "outbound_drop_threshold": 32
  },
  "logging": {
    "connectors": {
      "enabled": true,
      "level": "smart",
      "slow_threshold_ms": 1000
    },
    "triggers": {
      "enabled": true
    },
    "rotation": {
      "max_db_size_mb": 100,
      "max_log_age_days": 30,
      "archive_path": ".sentinel/archive/"
    }
  },
  "marketplace": {
    "url": "https://kits.ndx.au",
    "license_url": "https://license.ndx.au",
    "license_key": "",
    "telemetry_enabled": true,
    "next_check": ""
  }
}
```

### Field-by-Field Reference

#### Top-Level Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `data_dir` | string | `".sentinel"` | Directory where Sentinel stores all runtime data: databases, caches, PID files, certificates, and logs. Relative to the project root. You rarely need to change this. |
| `keyhole` | string | `"blocked"` | Default-kit escape hatch. Only matters when `sentinel.yaml` sets `default_kit`. `blocked` disables the normal `/kt/...` kit scheme on the root router (the default kit owns `GET /*` for pages). **`GET /hl/kt`** still lists kits. `header` leaves normal kit routes in place but requires `X-Sentinel-Keyhole` plus a valid Bearer token. Any other non-empty slash-free value is treated as a URL prefix, so `"_"` exposes the normal kit routes under `/_/kt/...`. See [Harness HTTP route reference](/harness-http-routes). |
| `vault_passphrase` | string | `""` | Passphrase for encrypting the vault database. Can also be set through `SENTINEL_VAULT_PASSPHRASE` environment variable (recommended -- the env var is more secure than storing the passphrase in a file). When both are set, the environment variable takes precedence. |

#### log -- Harness Log Output

Controls the harness process's own log output (what you see in the terminal or log files).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `log.level` | string | `"info"` | Minimum log level. One of: `debug`, `info`, `warn`, `error`. Debug level produces very verbose output including every HTTP request, Lua VM pool operation, and file watcher event. |
| `log.format` | string | `"text"` | Log output format. One of: `text` (human-readable with timestamps), `json` (structured JSON objects, one per line). Use `json` in production for log aggregation systems like ELK, Datadog, or Loki. |

#### api -- HTTP API Server

Controls the main HTTP API server that the harness exposes.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `api.port` | int | `8080` | TCP port for the HTTP API server. Ports 8080-8090 are within the dashboard's auto-discovery range. Valid range: 1-65535. |
| `api.debug_mode` | bool | `true` | When `true`, the API server does not require bearer token authentication. Requests are still subject to IP whitelist if configured. In production builds (compiled without `-tags dev`), setting this to `true` causes a validation error and the harness refuses to start. |
| `api.tokens` | string[] | `[]` | List of valid bearer tokens for API authentication. When `debug_mode` is `false`, at least one token is required. Use tokens with at least 64 cryptographically random characters. Multiple tokens allow different clients to use different credentials (and you can rotate one without disrupting others). |
| `api.ip_whitelist` | string[] | `[]` | List of allowed IP addresses or CIDR ranges. When non-empty, only requests from listed IPs are accepted, even if they provide a valid token. Supports both individual IPs (`192.168.1.1`) and CIDR notation (`10.0.0.0/8`). When empty, all IPs are allowed (subject to token auth). |

#### ip_filters -- Harness and wp-proxy CIDR rules

Top-level `ip_filters` in `.sentinel/config.json` apply to the **harness** listener and **wp-proxy**. They do not belong under `api`. The first matching rule wins. If no rule matches, the harness allows traffic. Saved YAML can retain `service: dashboard` for round trips. The dashboard uses its own listen whitelist (`WhitelistMiddleware`). Lua `ctx.fs` uses a separate plane. It denies access until an FS Control policy grants access.

Do not confuse `ip_filters` with `api.ip_whitelist` (debug-mode catch-all on the harness API).

#### tls -- Transport Layer Security

Controls HTTPS/TLS encryption for the API server.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `tls.enabled` | bool | `false` | Enable TLS. When `true`, the harness starts an more HTTPS listener on `tls.port`. The HTTP listener on `api.port` continues to operate. |
| `tls.port` | int | `8443` | TCP port for the HTTPS listener. Must not conflict with `api.port`. Valid range: 1-65535. |
| `tls.cert_dir` | string | `""` | Directory where CA and server certificates are stored. If empty, defaults to `{data_dir}/certs/` (typically `.sentinel/certs/`). The harness auto-generates a self-signed CA and server certificate on first start if they do not exist. |
| `tls.hosts` | string[] | `["localhost"]` | DNS hostnames to include in the server certificate's Subject Alternative Name (SAN) field. Add all hostnames that clients will use to connect (for example `harness-01.internal`, `myhost.example.com`). |
| `tls.ips` | string[] | `["127.0.0.1"]` | IP addresses to include in the server certificate's SAN field. Add all IPs that clients will use to connect. Each value must be a valid IP address. |

#### state -- State Database

Controls the SQLite state database where execution history, trigger state, and operational data are stored.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `state.busy_timeout` | int | `5000` | SQLite busy timeout in milliseconds. When a database lock is held by another operation, new operations wait up to this many milliseconds before returning a "database is locked" error. Increase this value if you see lock errors under heavy concurrency. |
| `state.encrypt_db` | bool | `false` | Enable SQLCipher encryption for the state database. When `true`, the state database is encrypted at rest using the passphrase from `SENTINEL_STATE_PASSPHRASE` (or `SENTINEL_VAULT_PASSPHRASE` as fallback). |
| `state.state_passphrase` | string | `""` | Passphrase for state database encryption. **Important:** Set this only through the `SENTINEL_STATE_PASSPHRASE` environment variable. Do not store it in the configuration file. The configuration file field exists for internal loading purposes. |

#### lua -- Lua VM Configuration

Controls the Lua virtual machine pool that executes flows.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lua.pool_size` | int | `10` | Maximum number of Lua VM instances (LStates) in the pool. Each concurrent flow execution requires one VM instance. If all instances are in use, new execution requests queue until one becomes available. Increase this for projects with many concurrent flows. Minimum: 1. |
| `lua.registry_size` | int | `256` | Initial registry size for new Lua VM instances. The registry is where Lua stores references to tables, functions, and userdata. Larger values use more memory per VM. They can improve performance for flows with many Lua objects. Minimum: 1. |
| `lua.execution_timeout` | int | `30` | Default execution timeout in seconds. If a flow's `main()` function does not return within this time, the execution is terminated and the `failed(err)` callback is invoked. Individual flows can override this. Minimum: 1. |

#### ws -- WebSocket Bus

Controls the WebSocket subsystem used for real-time communication between the harness, dashboard, and connected clients.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ws.enabled` | bool | `false` | Enable the WebSocket subsystem. WebSocket upgrades and flow-managed sockets stay inactive until this is enabled. The dashboard Sockets page can toggle this live and persists the change back to `.sentinel/config.json`. |
| `ws.max_connections` | int | `100` | Maximum number of concurrent WebSocket connections. Each dashboard browser tab and each programmatic client uses one connection. Minimum: 1. |
| `ws.max_message_size_kb` | int | `64` | Maximum size of a single WebSocket message in kilobytes. Messages larger than this are rejected. Minimum: 1. |
| `ws.read_buffer_kb` | int | `4` | WebSocket read buffer size in kilobytes per connection. Increase for high-throughput scenarios. |
| `ws.write_buffer_kb` | int | `4` | WebSocket write buffer size in kilobytes per connection. Increase for high-throughput scenarios. |
| `ws.handshake_timeout_ms` | int | `10000` | Maximum time in milliseconds to wait for the WebSocket handshake to complete. |
| `ws.ping_interval_ms` | int | `30000` | Interval in milliseconds between WebSocket ping frames sent to clients. Ping frames keep the connection alive and detect disconnected clients. Minimum: 1000. |
| `ws.pong_timeout_ms` | int | `10000` | Maximum time in milliseconds to wait for a pong response to a ping frame. If the client does not respond within this time, the connection is closed. Minimum: 1000. |
| `ws.inbound_drop_threshold` | int | `32` | Sustained send-buffer overflow streak that disconnects an overloaded inbound subscriber. Minimum: 1. |
| `ws.outbound_drop_threshold` | int | `32` | Sustained send-buffer overflow streak that disconnects an overloaded outbound subscriber. Minimum: 1. |

Cross-origin browser upgrades to `/ws` are allowed only for same-origin requests, loopback origins, or origins explicitly listed in the API CORS configuration. When `ws.enabled` is `false`, upgrade requests are rejected but admin management endpoints remain available so operators can enable the subsystem from the dashboard.

#### logging -- Detailed Logging Configuration

Controls fine-grained logging for connectors, triggers, and log rotation.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `logging.connectors.enabled` | bool | `true` | Enable logging of connector (external API) calls. When enabled, every `sn.cn.*` call in Lua flows is logged with timing, status, and (depending on level) request/response details. |
| `logging.connectors.level` | string | `"smart"` | Connector logging verbosity. Options: `smart` (log errors and slow calls above threshold), `verbose` (log every call with full details), `off` (no connector logging). |
| `logging.connectors.slow_threshold_ms` | int | `1000` | In `smart` mode, connector calls that take longer than this many milliseconds are logged as slow calls. Useful for identifying performance bottlenecks in external API integrations. |
| `logging.triggers.enabled` | bool | `true` | Enable logging of trigger events (cron fires, webhook receipts, event emissions). |
| `logging.rotation.max_db_size_mb` | int | `100` | Maximum size of the log database in megabytes before rotation occurs. When the database exceeds this size, older records are archived and the main database is compacted. |
| `logging.rotation.max_log_age_days` | int | `30` | Maximum age of log records in days. Records older than this are archived during rotation. |
| `logging.rotation.archive_path` | string | `".sentinel/archive/"` | Directory where archived log databases are stored during rotation. |

#### marketplace -- Sentinel Kit Marketplace

Controls integration with the Sentinel Kit Marketplace (SKM) for installing, updating, and licensing kits.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `marketplace.url` | string | `"https://kits.ndx.au"` | Kit catalog / device login (SKM). |
| `marketplace.license_url` | string | `"https://license.ndx.au"` | Occupy/register HQ ([ndxHQ](https://github.com/ndx-au/ndxHQ)). |
| `marketplace.license_key` | string | `""` | Activated license key (for example `sk_free_...` or `sk_ent_...`). Set automatically by `sentinel license activate`. Can also be set through `SENTINEL_LICENSE_KEY` environment variable. |
| `marketplace.telemetry_enabled` | bool | `true` | Allow sending anonymized system information (OS, architecture, Sentinel version) with phone-home requests. No project data or secrets are ever included. |
| `marketplace.next_check` | string | `""` | ISO 8601 timestamp for an optional check-in schedule. Occupy uses an in-memory heartbeat and does not write this field. |

---

## Environment Variables

Environment variables override values from `.sentinel/config.json`. They are the recommended way to set sensitive passphrases. API bearer token authority is different: harness auth tokens are configured in `.sentinel/config.json` (`api.tokens`), while operator `.env` tokens are client-side defaults for CLI/curl/agents.

### Precedence

When the same setting is available in multiple places:

```
Command-line flag  >  Environment variable  >  config.json  >  Built-in default
```

### Mapping Rules

Environment variables use the `SENTINEL_` prefix. **Only allowlisted variables** are loaded into harness config. Any other `SENTINEL_*` variable in the process environment is ignored (and listed in load diagnostics if unmarshal fails).

**Never** set `SENTINEL_API` on the harness process — it breaks startup. Use `HARNESS_URL` or `SENTINEL_HOST` in operator `.env` for API clients only.

Allowlisted mappings:

| Environment Variable | Configuration Key | Example Value |
|---------------------|------------|---------------|
| `SENTINEL_VAULT_PASSPHRASE` | `vault_passphrase` | `my_secret_passphrase_32_chars_min` |
| `SENTINEL_STATE_PASSPHRASE` | `state.state_passphrase` | `another_passphrase_32_chars_min` |
| `SENTINEL_DATA_DIR` | `data_dir` | `.sentinel` |
| `SENTINEL_PORT` | `api.port` | `9000` |
| `SENTINEL_DEBUG` | (flag override) | `1` |
| `SENTINEL_LOG_LEVEL` | `log.level` | `debug` |
| `SENTINEL_LOG_FORMAT` | `log.format` | `json` |
| `SENTINEL_MARKETPLACE_URL` | `marketplace.url` | `https://custom-marketplace.example.com` |
| `SENTINEL_LICENSE_KEY` | `marketplace.license_key` | `sk_free_abc123...` |
| `HARNESS_URL` | (CLI `--host` default, with `SENTINEL_HOST`) | `http://127.0.0.1:8080` |
| `SENTINEL_HOST` | (CLI `--host` default) | `http://prod-harness:8080` |
| `SENTINEL_API_KEY` | (CLI `--token` default) | `token_abc123...` |
| `SENTINEL_API_TOKEN` | (CLI `--token` alias) | same as API key |

**Not loaded into harness configuration:** `SENTINEL_API`, `HARNESS_URL`, `SENTINEL_API_KEY`, `SENTINEL_API_TOKEN`, and any other non-allowlisted `SENTINEL_*` vars.

**Blocked (startup error):** `SENTINEL_API`

**systemd pattern:** put `SENTINEL_VAULT_PASSPHRASE` in `.sentinel/harness.env` (see `harness.env.example` from `sentinel sre init`). Keep operator `.env` for tokens and `HARNESS_URL` only.

### Token Authority And Migration

Sentinel uses a deliberate split to avoid ambiguous token ownership:

- **Harness auth authority:** `.sentinel/config.json` -> `api.tokens`.
- **Operator/client defaults:** `.env` -> `SENTINEL_API_KEY` / `SENTINEL_API_TOKEN`.

Startup validation does not auto-copy tokens from `.env` into `config.json`.
If production startup fails with `api.tokens cannot be empty`, do this explicitly:

1. Generate a token (`openssl rand -base64 48`).
2. Add it to `.sentinel/config.json` under `api.tokens`.
3. Copy one token into `.env` as `SENTINEL_API_KEY` for CLI/curl/agent clients.

This keeps server-side auth configuration and client-side convenience configuration separate and auditable.

---

## Security Configuration

Sentinel provides three independent security layers. Each can be enabled independently depending on your threat model and deployment environment.

### Layer 1: Authentication (Bearer Token)

Protects API endpoints from unauthorized access. When enabled, every API request must include a valid bearer token in the `Authorization` header.

**Step-by-step setup:**

1. Generate one or more cryptographically random tokens (minimum 64 characters each):

```bash
# Generate a strong random token
openssl rand -base64 48
# Output: something like "dG9rZW4gYWJjMTIzIHZlcnkgbG9uZyByYW5kb20gc3RyaW5nIG1pbmlt..."
```

2. Add the tokens to `.sentinel/config.json`:

```json
{
  "api": {
    "debug_mode": false,
    "tokens": [
      "dG9rZW4gYWJjMTIzIHZlcnkgbG9uZyByYW5kb20gc3RyaW5nIG1pbmlt...",
      "YW5vdGhlcl90b2tlbl9taW5pbXVtXzY0X2NoYXJzX2RlZjQ1NnV2dy4u..."
    ],
    "ip_whitelist": [
      "10.0.0.0/8",
      "192.168.1.0/24"
    ]
  }
}
```

3. Use the token in API requests:

```bash
curl -H "Authorization: Bearer dG9rZW4gYWJjMTIzIHZlcnkgbG9uZyByYW5kb20gc3RyaW5nIG1pbmlt..." \
  http://localhost:8080/hl
```

4. Set the token as an environment variable for CLI usage:

```bash
export SENTINEL_API_KEY="dG9rZW4gYWJjMTIzIHZlcnkgbG9uZyByYW5kb20gc3RyaW5nIG1pbmlt..."
./sentinel harness status -p /path/to/project
```

**Auth-exempt routes:**

Certain routes bypass bearer token authentication by design:

| Route | Method | Reason |
|-------|--------|--------|
| `/api/config` | GET | Non-sensitive configuration status used by the dashboard for discovery. |
| `/wh/*` | ANY | Global webhooks use their own authentication (HMAC signatures, CIDR restrictions, rate limits). |
| `/kt/{ns}/{name}/wh/*` | ANY | Kit-scoped webhooks use their own authentication. |
| `/cert/ca.crt` | GET | CA certificate distribution for TLS pinning. Must be publicly accessible. |
| `/cert/server.crt` | GET | Server certificate for diagnostics. |

External webhook callers (such as Stripe, GitHub, and Slack) do not need a Sentinel bearer token. Webhooks authenticate using their own mechanisms defined in the flow's trigger configuration.

**Dashboard token management:**

The dashboard stores a bearer token per harness instance for proxied requests:

1. An administrator configures `api.tokens` in the harness's `.sentinel/config.json`.
2. The administrator copies one token from that array.
3. In the dashboard, navigate to the harness configuration page and paste the token.
4. The token is stored in the dashboard's local database (`~/.sentinel/dashboard.db`), which is encrypted.
5. The dashboard attaches the stored token to all proxied API requests to that harness.

**Best practices:**

- Use cryptographically random tokens of at least 64 characters.
- Create separate tokens for different clients (dashboard, CI/CD, external integrations) so you can rotate one without disrupting others.
- Combine tokens with IP whitelisting for defense in depth.
- Rotate tokens quarterly. If you suspect a compromised token, rotate it immediately.

### Layer 2: Encryption at Rest (AES-256-GCM / SQLCipher)

Protects sensitive data stored on disk from unauthorized file access. There are two encrypted databases:

**Vault database** (`.sentinel/vault.db`): Stores all secrets (API keys, tokens, passwords) encrypted with AES-256-GCM. The vault passphrase is the encryption key.

**State database** (`.sentinel/state.db`): Stores execution history, trigger state, backup plans/runs, and other operational data. Encryption is optional and uses SQLCipher.

**Step-by-step setup:**

1. Generate strong passphrases (minimum 32 characters, random):

```bash
# Vault passphrase
openssl rand -base64 32
# State passphrase (can be the same or different)
openssl rand -base64 32
```

2. Set passphrases as environment variables:

```bash
export SENTINEL_VAULT_PASSPHRASE="your_vault_passphrase_minimum_32_chars"
export SENTINEL_STATE_PASSPHRASE="your_state_passphrase_minimum_32_chars"
```

3. Enable state database encryption in `.sentinel/config.json`:

```json
{
  "state": {
    "encrypt_db": true
  }
}
```

4. Start the harness (passphrases must be set before starting):

```bash
./sentinel harness start -p /path/to/project
```

5. Make sure that encryption is active:

```bash
# The vault database should not be readable as plain text
file .sentinel/vault.db
# Expected: "data" or "SQLite 3.x database" (encrypted content)

# Attempting to open it with a standard SQLite client should fail
sqlite3 .sentinel/vault.db "SELECT * FROM secrets;"
# Expected: "file is not a database" (because it is encrypted)
```

**Best practices:**

- Store passphrases in a secure secret manager, such as HashiCorp Vault, AWS Secrets Manager, or Azure Key Vault. Inject them through environment variables at runtime.
- Never commit passphrases to git or store them in plain text files.
- Use different passphrases for vault and state databases for compartmentalized security.
- Test that you can restart the harness with the passphrases before deploying to production.

### Layer 3: Transport Encryption (TLS/SSL)

Protects data in transit between clients and the harness. When enabled, the harness serves HTTPS in addition to HTTP.

**Step-by-step setup:**

1. Configure TLS in `.sentinel/config.json`:

```json
{
  "tls": {
    "enabled": true,
    "port": 8443,
    "cert_dir": ".sentinel/certs",
    "hosts": ["harness-01.internal", "harness-01"],
    "ips": ["10.0.5.21", "127.0.0.1"]
  }
}
```

2. Start the harness. On first start with TLS enabled, it automatically generates:
   - A self-signed Certificate Authority (CA) key and certificate.
   - A server key and certificate signed by the CA.
   - Both are stored in the `cert_dir` directory.

3. Download the CA certificate for clients to trust:

```bash
curl -k https://localhost:8443/cert/ca.crt > ca.crt
```

4. Use the CA certificate for pinned HTTPS connections:

```bash
curl --cacert ca.crt https://localhost:8443/hl
```

5. Distribute the CA certificate to all clients, dashboards, and CI/CD systems that need to connect.

**Updating hostnames or IPs:**

If you change `tls.hosts` or `tls.ips` after certificate generation, regenerate the server certificate:

```bash
# Delete existing certificates
rm .sentinel/certs/server.crt .sentinel/certs/server.key

# Restart the harness (it will regenerate the server certificate with the new SANs)
./sentinel harness start -p /path/to/project
```

The CA certificate does not need to be regenerated unless you want to rotate the entire chain.

**Best practices:**

- Always enable TLS in production, even for internal networks.
- Use certificate pinning (`--cacert ca.crt`) rather than disabling certificate verification (`-k`).
- Include all hostnames and IPs that clients will use in the `hosts` and `ips` arrays.
- Certificates are generated with a 10-year validity period. Plan certificate rotation accordingly.
- Consider using your organization's internal CA instead of self-signed certificates for production. Replace the files in `cert_dir` with your own CA-signed certificates.

### Audit Logging

Security-relevant events are logged automatically by the harness. These include:

- Authentication attempts (success and failure) with source IP addresses.
- Certificate generation and expiration warnings.
- Vault access events (secret read, write, delete).
- API access patterns.
- Configuration changes.

To enable structured audit logging suitable for a SIEM or log aggregation system, configure JSON log format:

```json
{
  "log": {
    "level": "info",
    "format": "json"
  }
}
```

**Example audit log entries:**

```
{"time":"2026-03-06T12:00:00Z","level":"INFO","msg":"API request authorized","source":"192.168.1.1","method":"GET","path":"/hl"}
{"time":"2026-03-06T12:00:05Z","level":"INFO","msg":"Vault secret accessed","secret":"slack_token","action":"read"}
{"time":"2026-03-06T12:00:10Z","level":"WARN","msg":"Certificate expiring","days_remaining":30,"cert":"server.crt"}
{"time":"2026-03-06T12:01:00Z","level":"WARN","msg":"Authentication failed","source":"10.0.0.99","reason":"invalid_token"}
```

---

## Lua VM Configuration

The Lua VM pool is one of the most important performance-related configuration. Understanding how it works helps you tune it correctly.

**How the pool works:**

Sentinel maintains a pool of initialized Lua VMs (LStates). For each execution, the harness takes a VM from the pool and loads the flow. After execution, it returns the VM to the pool. This avoids creating and destroying a VM for each run.

**Tuning guidelines:**

| Setting | Small project (< 5 kits) | Medium project (5-20 kits) | Large project (20+ kits) |
|---------|--------------------------|----------------------------|--------------------------|
| `pool_size` | 5 | 10 (default) | 20-50 |
| `registry_size` | 128 | 256 (default) | 512 |
| `execution_timeout` | 30 (default) | 30 (default) | 60 |

- **pool_size**: Set the pool size for the expected number of concurrent flow executions. For 3 simultaneous cron triggers and occasional manual runs, a pool of 5-10 is sufficient. For bursts of webhook traffic, increase the pool size.

- **registry_size**: Increase this if your flows create many Lua tables, closures, or userdata objects. The default of 256 is sufficient for most flows. Memory impact: approximately 2 KB per registry slot per VM instance.

- **execution_timeout**: This value limits how long a flow can run. Slow external APIs can need longer timeouts. Set a default that supports those calls. Use shorter timeouts for quick operations.

**Example -- high-concurrency configuration:**

```json
{
  "lua": {
    "pool_size": 25,
    "registry_size": 512,
    "execution_timeout": 60
  }
}
```

---

## Logging Configuration

Sentinel has two separate logging systems: the harness process log (controlled by `log.*`) and the detailed operational log (controlled by `logging.*`).

### Harness Process Log (log.*)

These are harness logs. The terminal shows them for foreground operation. The systemd journal shows them when the harness runs as a service.

| Level | What it includes |
|-------|-----------------|
| `error` | Only critical errors that indicate something is broken. |
| `warn` | Errors plus warnings about degraded conditions (slow queries, approaching limits, cert expiration). |
| `info` | Warnings plus normal operational events (harness started, kit loaded, flow executed). **Recommended for production.** |
| `debug` | Everything, including internal details of every HTTP request, Lua pool checkout/return, file watcher events, and configuration loading steps. **Very verbose.** Use only for troubleshooting. |

### Connector Logging (logging.connectors.*)

Logs every external API call made by Lua flows through the `sn.cn.*` connector interface.

- **`smart` mode** (default): Logs only errors and calls that exceed `slow_threshold_ms`. This gives you visibility into problems without flooding the logs during normal operation.
- **`verbose` mode**: Logs every connector call with full timing, URL, status code, and response size. Useful during development to understand exactly what external calls your flows are making.
- **`off` mode**: No connector logging. Use in production if connector call volume is extremely high and you do not need the visibility.

### Trigger Logging (logging.triggers.*)

Logs trigger-related events: cron trigger fires, webhook receipts, and event emissions. Enabled by default. Disable if you have very frequent triggers (for example every-second cron jobs) and the log volume is too high.

### Log Rotation (logging.rotation.*)

The harness stores operational logs in a SQLite database. Over time, this database grows. Log rotation controls when old records are archived.

- **`max_db_size_mb`**: When the log database exceeds this size, a rotation is triggered. Archived logs are moved to `archive_path`. Default: 100 MB.
- **`max_log_age_days`**: Records older than this many days are archived during rotation. Default: 30 days.
- **`archive_path`**: Directory where archived log databases are stored. Default: `.sentinel/archive/`. Archived databases can be queried directly with SQLite tools if needed.

---

## Marketplace Configuration

The Sentinel Kit Marketplace (SKM) is the distribution platform for published kits. Configuration is stored in `.sentinel/config.json` under the `marketplace` key.

**Initial setup:**

1. Authenticate: `sentinel login`.
2. Activate a license: `sentinel license activate sk_free_<key>`.
3. Install kits: `sentinel sre kit install <kit-id>`.

**Telemetry:**

When `telemetry_enabled` is `true`, the harness includes basic system information (OS, architecture, Sentinel version, kit count) with phone-home verification requests. No project data, secrets, flow content, or personally identifiable information is ever sent. Set to `false` to disable.

**Optional check-in:**

Occupy heartbeats stay in memory (~60s). `marketplace.next_check` is reserved for a real optional check-in schedule and is not written by occupy. Leave it empty unless you are configuring optional check-in separately.

**Private marketplace:**

For enterprise deployments with a private marketplace instance, change `marketplace.url` to your private instance's URL:

```json
{
  "marketplace": {
    "url": "https://marketplace.internal.example.com"
  }
}
```

---

## WebSocket Configuration

The WebSocket subsystem is disabled by default. Administrators can enable it in `.sentinel/config.json` or on the dashboard Sockets page. Enable it only for harness-managed sockets or browser subscriptions.

**When to adjust WebSocket configuration:**

- **Many dashboard users**: If more than 100 users can open the dashboard simultaneously, increase `max_connections`.
- **Large log volumes**: Increase `max_message_size_kb` if individual log entries or execution results are very large (above 64 KB).
- **Unstable network connections**: Decrease `ping_interval_ms` and `pong_timeout_ms` to detect disconnections faster, or increase them to be more tolerant of network latency.
- **Activation policy**: Leave `ws.enabled` as `false` until you need websocket features.
- **Slow subscribers**: Tune `inbound_drop_threshold` and `outbound_drop_threshold` to disconnect overloaded subscribers sooner or later depending on how bursty your workload is.

---

## Performance Tuning

### Recommended Settings by Scale

| Setting | Development | Small Production | Large Production |
|---------|-------------|-----------------|------------------|
| `lua.pool_size` | 5 | 10 | 25-50 |
| `lua.execution_timeout` | 30 | 30 | 60-120 |
| `state.busy_timeout` | 5000 | 5000 | 10000-15000 |
| `ws.max_connections` | 10 | 50 | 200-500 |
| `logging.connectors.level` | verbose | smart | smart |
| `logging.rotation.max_db_size_mb` | 50 | 100 | 500 |
| `logging.rotation.max_log_age_days` | 7 | 30 | 90 |
| `log.level` | debug | info | warn |
| `log.format` | text | json | json |

### Database Performance

The state database uses SQLite with WAL (Write-Ahead Logging) mode for good concurrent read/write performance. Key tuning parameters:

- **`state.busy_timeout`**: How long to wait for a database lock. Increase this if you see "database is locked" errors. A value of 10000 (10 seconds) handles most concurrency scenarios.

- **Periodic optimization**: Run `sentinel db optimize --kit <kit-id>` periodically (weekly or monthly) to REINDEX, ANALYZE, and VACUUM kit databases. This is especially important for kits with heavy write activity.

- **Database size**: Monitor `.sentinel/data/*.db` file sizes. If a kit database grows very large, consider archiving old data within your Lua flows.

### Memory Usage

Each Lua VM instance uses approximately 1-5 MB of memory depending on `registry_size` and the complexity of loaded modules. With the default pool size of 10, the Lua subsystem uses approximately 10-50 MB of RAM. Adjust `pool_size` based on available memory.

---

## Configuration Validation

After you modify `.sentinel/config.json`, make sure that the configuration is valid before you start the harness.

**Method 1: Start with debug logging**

```bash
./sentinel harness start -p /path/to/project --debug
```

The harness validates all configuration on startup and reports any errors. With `--debug`, you also see the loaded configuration values.

**Method 2: Audit the project**

```bash
./sentinel audit /path/to/project
```

The audit command checks the project structure and configuration for common issues.

**Common validation errors:**

| Error | Cause | Solution |
|-------|-------|----------|
| `invalid log level "verbose"` | Log level must be debug, info, warn, or error. | Use one of the valid values. |
| `api.tokens cannot be empty in production mode` | Debug mode is off but no tokens configured. | Add tokens or enable debug mode. |
| `debug mode is disabled in production builds` | Release build with debug_mode: true. | Set debug_mode to false and configure tokens. |
| `tls.port conflicts with api.port` | Both set to the same port number. | Use different port numbers. |
| `invalid lua.pool_size 0: must be at least 1` | Pool size set to zero or negative. | Set to at least 1. |

---

## Backup and Recovery

### What to Back Up

| File/Directory | Contains | Priority |
|----------------|----------|----------|
| `sentinel.yaml` | Project metadata and behavior configuration | High (but recoverable from git) |
| `.sentinel/config.json` | Infrastructure configuration | Medium (can be recreated) |
| `.sentinel/vault.db` | Encrypted secrets | **Critical** (secrets cannot be recovered without backup) |
| `.sentinel/state.db` | Execution history, trigger state | Medium (operational data) |
| `.sentinel/data/*.db` | Kit databases | High (application data) |
| `.sentinel/certs/` | TLS certificates | Low (can be regenerated) |

### Backup Procedures

**Vault backup:**

```bash
# Stop the harness first to ensure consistency
./sentinel harness stop -p /path/to/project

# Copy the vault database
cp .sentinel/vault.db /secure-backups/vault-$(date +%Y%m%d).db

# Restart
./sentinel harness start -p /path/to/project --daemon
```

**Kit database backup (online -- harness can be running):**

```bash
./sentinel db backup --kit acme.billing --output /backups/acme.billing-$(date +%Y%m%d).db
```

**Full project backup:**

```bash
# Stop harness
./sentinel harness stop -p /path/to/project

# Archive the entire .sentinel directory
tar czf /backups/sentinel-data-$(date +%Y%m%d).tar.gz .sentinel/

# Restart
./sentinel harness start -p /path/to/project --daemon
```

### Recovery Procedures

**Restore vault:**

```bash
./sentinel harness stop -p /path/to/project
cp /secure-backups/vault-20260306.db .sentinel/vault.db
./sentinel harness start -p /path/to/project --daemon
```

**Restore kit database:**

```bash
./sentinel harness stop -p /path/to/project
./sentinel db restore --kit acme.billing --from /backups/acme.billing-20260306.db
./sentinel harness start -p /path/to/project --daemon
```

**Important notes:**

- Always stop the harness before restoring databases to prevent corruption.
- Vault backups are only useful if you also have the vault passphrase. Store the passphrase separately from the backup.
- Test your recovery procedure periodically to make sure that backups are valid.

---

## Deployment Checklist

### Pre-Deployment (1-2 hours)

- [ ] **Review threat model**: What are you protecting? Who can attack? What is the impact of a breach?
- [ ] **Build release binary**: `go build -ldflags="-s -w" -o sentinel ./cmd/sentinel` (no debug mode).
- [ ] **Configure authentication tokens**: Generate at least one 64+ character random token. Set `api.debug_mode` to `false`.
- [ ] **Configure encryption passphrases**: Generate 32+ character random passphrases for vault and optionally state database.
- [ ] **Enable TLS**: Set `tls.enabled` to `true`. Configure `tls.hosts` and `tls.ips` with all valid names and addresses.
- [ ] **Set IP whitelists**: If behind a load balancer, restrict to the load balancer's IPs.
- [ ] **Disable debug logging**: Set `log.level` to `info` or `warn`. Set `log.format` to `json` for log aggregation.
- [ ] **Tune Lua VM**: Set `lua.pool_size` based on expected concurrency. Review `lua.execution_timeout`.
- [ ] **Configure log rotation**: Set appropriate `max_db_size_mb` and `max_log_age_days` for your retention policy.
- [ ] **Test secrets**: Make sure that flows can access all required vault secrets.
- [ ] **Test all flows**: Run each flow manually. Make sure that it produces the expected result.
- [ ] **Verify webhooks**: Send example payloads. Make sure that routing and signature verification produce the expected results.

### Deployment Steps

```bash
# 1. Generate credentials
TOKEN=$(openssl rand -base64 48)
VAULT_PASS=$(openssl rand -base64 32)
STATE_PASS=$(openssl rand -base64 32)

# 2. Configure the harness (edit .sentinel/config.json)
# Set api.debug_mode=false, api.tokens=["$TOKEN"], tls.enabled=true, etc.

# 3. Start the harness
SENTINEL_VAULT_PASSPHRASE="$VAULT_PASS" \
SENTINEL_STATE_PASSPHRASE="$STATE_PASS" \
./sentinel harness start -p /opt/my-project --daemon

# 4. Verify TLS
curl --cacert .sentinel/certs/ca.crt \
  -H "Authorization: Bearer $TOKEN" \
  https://localhost:8443/hl

# 5. Verify auth rejection
curl -H "Authorization: Bearer invalid_token" \
  https://localhost:8443/hl
# Should return: {"ok":false,"err":"UNAUTHORIZED","msg":"..."}
```

### Post-Deployment

- [ ] **Monitor logs**: Watch for errors and warnings during the first hours of operation.
- [ ] **Test all endpoints**: Test API access from production clients with valid tokens.
- [ ] **Verify webhook delivery**: Make sure that external services can reach the webhook endpoints.
- [ ] **Set up log rotation monitoring**: Make sure that log archives appear on schedule.
- [ ] **Document certificate expiration date**: Record when TLS certificates expire (10-year validity by default).
- [ ] **Set up monitoring alerts**: Configure alerts for harness health endpoint failures.
- [ ] **Schedule regular backups**: Set up automated backup of vault.db and kit databases.
- [ ] **Plan credential rotation**: Schedule quarterly rotation of tokens and passphrases.

---

## Troubleshooting

### Port Already in Use

```bash
# Find what is using the port
lsof -i :8080

# Use a different port
./sentinel harness start -p ./project --port 9000

# Or force kill an existing Sentinel process
./sentinel harness start -p ./project --force-reset
```

### Vault Locked

```bash
# Error: vault locked

# The vault passphrase is not set. Set it and restart:
export SENTINEL_VAULT_PASSPHRASE="your_passphrase_here"
./sentinel harness start -p ./project
```

### TLS Certificate Errors

```bash
# Error: certificate verification failed

# Download the CA certificate and use it for pinning
curl -k https://localhost:8443/cert/ca.crt > ca.crt
curl --cacert ca.crt https://localhost:8443/hl

# If you changed tls.hosts or tls.ips, regenerate the server certificate
rm .sentinel/certs/server.crt .sentinel/certs/server.key
./sentinel harness start -p ./project  # Regenerates on startup
```

### Database Locked Errors

```bash
# Error: database is locked

# Increase the busy timeout
# Edit .sentinel/config.json: "state": { "busy_timeout": 15000 }

# Or optimize the database to reduce lock contention
./sentinel db optimize --kit <kit-id>
```

### Slow Startup

If the harness takes a long time to start, investigate with debug logging:

```bash
./sentinel harness start -p ./project --debug 2>&1 | head -100
```

Common causes:
- Many kits with large CMS content directories (many .md files to parse).
- Database migrations running on first start after an upgrade.
- Network connectivity issues when phone-home is enabled.
- Large flow files that take time to parse and register.

---

## Best Practices Summary

1. **Separate configuration layers**: Put behavior in `sentinel.yaml`, infrastructure in `.sentinel/config.json`, and secrets in environment variables.
2. **Never commit secrets**: Keep passphrases in environment variables. Keep API tokens in gitignored files (`.sentinel/config.json`, operator `.env`).
3. **Enable all three security layers in production**: Authentication (tokens), encryption at rest (vault + state passphrase), and encryption in transit (TLS).
4. **Use strong credentials**: Minimum 64-character random tokens, minimum 32-character random passphrases.
5. **Enable structured logging in production**: Set `log.format` to `json` for compatibility with log aggregation systems.
6. **Tune the Lua pool for your workload**: Set `lua.pool_size` based on expected concurrent flow executions.
7. **Use `smart` connector logging**: It captures errors and slow calls without the volume of `verbose` mode.
8. **Back up the vault regularly**: The vault contains secrets that cannot be recovered without a backup.
9. **Rotate credentials quarterly**: Schedule rotation for tokens, passphrases, and certificates.
10. **Test your recovery procedure**: Periodically make sure that you can restore from backups and that all passphrases are still available.
