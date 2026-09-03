---
title: "CLI Reference"
description: "Complete reference for the sentinel command-line interface, covering every command, flag, environment variable, and common workflow."
type: Reference
tags: [cli]
status: stable
---

# CLI Reference

Complete reference for the `sentinel` command-line interface, covering every command, flag, environment variable, and common workflow.

---

## Introduction

Sentinel ships as a single static binary called `sentinel`. This binary serves as both the orchestration harness (the runtime engine that executes Lua flows) and the management CLI (used to initialize projects, manage secrets, install kits, and perform administrative tasks).

The fundamental operating model is:

1. You point Sentinel at a **project directory** (called an SRE -- Sentinel Runtime Environment) using the `-p` flag.
2. The harness loads all kits, flows, connectors, modules, forms, and pages from that directory.
3. It starts an HTTP API server that exposes endpoints for executing flows, managing triggers, querying logs, and more.
4. Optionally, a web dashboard can be started alongside the harness for visual management.

Every command operates against a project directory. If you omit `-p`, the current working directory is assumed. For clarity and safety, it is strongly recommended to always specify `-p` with an absolute path.

---

## Installation

### Building from Source

Sentinel is written in Go. You need Go 1.25 or later installed on your system.

**Development build** (includes debug mode support):

```bash
git clone <repository-url>
cd sentinel
go build -tags dev -o sentinel ./cmd/sentinel
```

The `-tags dev` flag enables development features such as `api.debug_mode`, which allows the harness to run without requiring authentication tokens. This is the build you should use during local development and testing.

**Release build** (production, smaller binary, no debug mode):

```bash
go build -ldflags="-s -w" -o sentinel ./cmd/sentinel
```

The `-ldflags="-s -w"` flags strip the symbol table and debug information, producing a smaller binary. Release builds enforce that `api.debug_mode` cannot be set to `true` -- the harness will refuse to start if debug mode is enabled in the configuration.

**On Windows:**

```bash
go build -tags dev -o sentinel.exe ./cmd/sentinel
```

After building, the binary is available as `./sentinel` (or `./sentinel.exe` on Windows). You can copy it anywhere on your system or add it to your PATH.

**Verify the installation:**

```bash
./sentinel version
# Output: sentinel version v0.1.1-dev (or similar)
```

### Build Script

The repository includes a convenience build script:

```bash
# Development build
./build.sh

# Release build
./build.sh -r
```

---

## Global Flags

These flags are available on every command and subcommand. They are defined as persistent flags on the root command and are inherited by all child commands.

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--project <path>` | `-p` | `.` | Path to the SRE project directory. This is the most important flag -- it tells Sentinel where to find kits, flows, configuration, and databases. Always use an absolute path in scripts and CI/CD pipelines. |
| `--debug` | | `false` | Enable debug-level logging. When set, the harness outputs verbose log messages including kit loading details, flow registration, trigger scheduling, and internal state changes. Useful for troubleshooting startup issues or understanding execution flow. |
| `--json` | | `false` | Output structured JSON instead of human-readable text. When enabled, all log output and command results are formatted as JSON objects. This is essential for scripting, piping output to `jq`, or integrating with log aggregation systems. |
| `--no-color` | | `false` | Disable ANSI color codes in output. Use this when running in environments that do not support color (CI logs, file redirection, screen readers). |
| `--no-input` | `-n` | `false` | Non-interactive mode. Instead of prompting for input, the command will fail with an error if user input would be required. Essential for CI/CD pipelines and automated scripts where no human is present. |
| `--force-reset` | | `false` | Force kill any conflicting Sentinel processes and delete stale PID files before proceeding. Use this when a previous harness or dashboard process did not shut down cleanly and left behind a PID file that prevents a new instance from starting. |
| `--host <url>` | | `""` | Remote harness URL for CLI commands that communicate with a running harness over HTTP. Defaults to the value of the `SENTINEL_HOST` environment variable if set. Example: `--host http://192.168.1.10:8080`. |
| `--token <token>` | | `""` | Bearer token for authenticating API requests to a running harness. Defaults to the value of the `SENTINEL_API_KEY` environment variable if set. Required when the harness has authentication tokens configured. |

**Examples:**

```bash
# Start with explicit project path and debug logging
./sentinel harness start -p /home/user/my-project --debug

# Run a flow on a remote harness with authentication
./sentinel run sn-core-agent:assistant --host http://prod-harness:8080 --token "my_secret_token"

# Non-interactive init for CI
./sentinel sre init my-project --no-input
```

---

## Environment Variables

Environment variables provide an alternative to flags and configuration files. They are especially useful for secrets (which should never appear in command-line arguments where they could be visible in process listings) and for container/CI environments.

### Core Runtime Variables

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `SENTINEL_VAULT_PASSPHRASE` | Passphrase for encrypting the vault database (AES-256-GCM). Required if the vault is encrypted. | (none) | Minimum 32 characters recommended. The vault stores all secrets accessed by `ctx.secret()` in Lua flows. |
| `SENTINEL_STATE_PASSPHRASE` | Passphrase for encrypting the state database (SQLCipher). Only used when `state.encrypt_db` is `true` in config. | (none) | If empty and `encrypt_db` is true, the vault passphrase is used as fallback. |
| `SENTINEL_DATA_DIR` | Override the data directory path. | `.sentinel` | Normally set in `.sentinel/config.json`. The environment variable overrides the file value. |
| `SENTINEL_PORT` | Override the API listen port. | `8080` | Equivalent to the `api.port` config field. |
| `SENTINEL_DEBUG` | Enable debug mode. Set to `1` or `true`. | (disabled) | Equivalent to `--debug` flag. |
| `SENTINEL_LOG_LEVEL` | Set the minimum log level: `debug`, `info`, `warn`, or `error`. | `info` | Overrides `log.level` in config file. |
| `SENTINEL_LOG_FORMAT` | Set the log output format: `json` or `text`. | `text` | Overrides `log.format` in config file. |

### CLI and Remote Access Variables

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `SENTINEL_HOST` | URL of the harness API for remote CLI commands. | `http://localhost:8080` | Used by commands like `run`, `logs`, `status` when operating against a remote harness. |
| `SENTINEL_API_KEY` | Bearer token for authenticating CLI requests to the harness. | (none) | Stored here instead of command-line arguments to avoid exposure in process listings. |

### Marketplace Variables

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `SENTINEL_MARKETPLACE_URL` | Override kit catalog URL. | `https://kits.ndx.au` | SKM |
| `SENTINEL_LICENSE_URL` | Override occupy/register HQ. | `https://license.ndx.au` | ndxHQ |
| `SENTINEL_LICENSE_KEY` | License key for marketplace access. Alternative to storing it in config. | (none) | Overrides `marketplace.license_key` in config file. |

### Application Variables

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `SENTINEL_PROJECT_DIR` | Default project root directory. | `.` | Equivalent to the `-p` flag default. |
| `SENTINEL_SRE_LOCATION` | SRE directory path for dashboard auto-discovery. | (none) | Used by the dashboard to locate harness instances. |

### Precedence Rules

When the same setting is specified in multiple places, the following precedence applies (highest to lowest):

1. Command-line flags (e.g., `--port 9000`)
2. Environment variables (e.g., `SENTINEL_PORT=9000`)
3. Configuration file (`.sentinel/config.json`)
4. Built-in defaults

---

## Core Commands

These are the fundamental commands for initializing projects and running the harness.

### init

Initialize a new Sentinel project (SRE). The init command assumes it runs at the **repository root** (current working directory). It creates repo-level files (CLAUDE.md, .gitignore, etc.) in cwd and SRE-level files (sentinel.yaml, kits, etc.) in the path specified by `-p`/`--project`.

A single git repo may contain multiple SREs in subfolders. Repo-level files are only written if they do not already exist, making it safe to run `init` multiple times for different SREs in the same repo.

```bash
./sentinel sre init [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `-p`, `--project` | `.` | Path to the SRE directory (relative to cwd). Defaults to current directory, meaning repo root = SRE root (1:1 mode). |
| `--minimal` | `false` | Skip the interactive wizard but still create the standard scaffold. |
| `--starter-kits` | `true` | Install the bundled starter kits into the project scaffold. |
| `--wp-central` | `false` | Add the `sn.wp-central` project profile and install the `sn.wp-central` starter kit. Suppresses default starter kits and skips the interactive wizard. |
| `--wp-edge` | `false` | Add the `sn.wp-edge` project profile and install the `sn.wp-edge` starter kit. Suppresses default starter kits and skips the interactive wizard. |
| `--with-kit` | none | After scaffold creation, install one or more marketplace kits. Accepts comma-separated values and repeated flags. |
| `--with-bundle` | none | After scaffold creation, install one or more bundles. Resolves from SKM with local fallback. Accepts comma-separated values and repeated flags. |
| `--no-input` | `false` | Use all defaults without prompting. In interactive mode, the init command asks for project name, description, and whether to enable vault encryption. |

The wizard **name** field is metadata only -- it populates `sentinel.yaml` but does not affect directory names. The SRE directory is determined solely by the `-p`/`--project` flag.

**What it creates:**

```
repo-root/                         # Where init is run (cwd)
  CLAUDE.md                        # AI assistant orientation (repo-level)
  .claude/skills/                  # SRE guidance skills (repo-level)
  .gitignore                       # Ignores .sentinel/ and _data/ (repo-level)
  .gitattributes                   # Line ending normalization (repo-level)

  sre-path/                        # SRE root (defaults to "." for 1:1 mode)
    sentinel.yaml                  # Project metadata (name, version, description)
    sentinel.yaml.md               # Skill twin for AI agent context
    .sentinel/                     # Machine-local data (gitignored)
      config.json                  # Infrastructure configuration
    tests/                         # Test directory
    sn.core-agent/                 # Base agent starter kit (if --starter-kits)
    sn.core-rag/                   # Base RAG starter kit
    sn.tools-http/                 # Tool connector starter kit
    sn.supervisor/                 # Supervisor starter kit
    sn.eg-support/                 # Example support kit
    sn.eg-itops/                   # Example IT ops kit
    sn.eg-rag-chat/                # Example retrieval-backed chat kit
    sn.example-support/            # Legacy example support compatibility kit
    sn.example-itops/              # Legacy example IT ops compatibility kit
```

Repo-level files (CLAUDE.md, .gitignore, .gitattributes, .claude/skills/) skip creation if they already exist, so running init for a second SRE in the same repo will not overwrite them.

`sn.wp-central/` and `sn.wp-edge/` are intentionally not part of the default starter-kit set. Use `--wp-central`, `--wp-edge`, or `--with-bundle wp-central|wp-edge` when you want those profiles. `--wp-central` and `--wp-edge` suppress default starter kits and skip the interactive wizard, since the user has already expressed intent via the flag.

When `--wp-central` is selected, `sentinel sre init` also writes `docker-compose.wp-central.yaml` into the SRE root so the managed WordPress stack can be started directly with `sentinel harness start --compose-up wp-central`.
For local development, that compose file currently uses floating `:latest` WordPress and MariaDB images and persists data under `./_data/wp-central/`.
The generated `sentinel.yaml` also includes `wp_central.port: 8800`, which is the dedicated WordPress ingress port for `sn.wp-central`.

**Examples:**

```bash
# 1:1 mode: repo root is the SRE (default)
./sentinel sre init
# Prompts for: name, description, vault encryption preference

# SRE in a subfolder (multi-SRE repo)
./sentinel sre init -p edge-sre --wp-edge

# Multiple SREs in one repo
./sentinel sre init -p central --wp-central
./sentinel sre init -p edge --wp-edge
# Creates: central/sentinel.yaml, central/sn.wp-central/,
#          edge/sentinel.yaml, edge/sn.wp-edge/,
#          CLAUDE.md at repo root (written once, skipped on second init)

# Profile flags suppress defaults and skip wizard
./sentinel sre init -p my-edge --wp-edge
# Creates: my-edge/sentinel.yaml, my-edge/sn.wp-edge/, CLAUDE.md (at repo root)

# Fully automated (for CI/CD or scripts)
./sentinel sre init --no-input --minimal

# Scaffold an sn.wp-central project and boot its managed stack
./sentinel sre init -p my-central --wp-central
./sentinel harness start -p ./my-central --compose-up wp-central --wp-port 8800

# Scaffold, then install marketplace kits
./sentinel sre init --with-kit acme.billing,acme.search

# Scaffold, then install starter bundles
./sentinel sre init --with-bundle core,wp-central
```

**Notes:**

- The `sentinel.yaml` file contains team-shared configuration (name, version, git sync settings). It should be committed to version control.
- The `.sentinel/` directory contains machine-specific configuration, databases, and secrets. It is gitignored by default and must never be committed.
- If vault encryption is enabled during init, you will need to set `SENTINEL_VAULT_PASSPHRASE` before starting the harness.
- Run `sentinel sre validate` after modifying starter kits or adding new kits.

### start

Start the harness API server. The harness discovers all kits in the project directory, loads flows, registers triggers, initializes databases, and begins serving HTTP requests.

```bash
./sentinel harness start [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--port <int>` | `8080` | HTTP port for the API server. Ports 8080-8090 are within the dashboard's auto-discovery range. |
| `--wp-port <int>` | (from `sentinel.yaml`, default `8800`) | Dedicated `sn.wp-central` WordPress ingress port. Only applies when `wp_central.enabled` is true. Overrides `wp_central.port` for that run. |
| `-d`, `--daemon` | `false` | Run the harness as a background process. The parent waits for the child to become healthy (up to 10s) before exiting. PID file: `{SRE}/.sentinel/harness-{port}.pid`. |
| `--drop-web-cache` | `false` | Clear all web caches (CMS content cache, template cache) on startup. Useful when content files have changed outside of hot-reload detection. |
| `--compose-up <value>` | (none) | Start Docker Compose stacks before the harness. Use `all` to start all stacks, or provide a comma-separated list of stub names. |
| `--mcp` | `false` | Start an MCP (Model Context Protocol) server alongside the harness for AI agent tooling. |
| `--mcp-bind <addr>` | `127.0.0.1` | MCP bind address. Use `127.0.0.1` (default) for localhost-only, or `0.0.0.0` / `::` to accept remote clients on trusted networks. |
| `--mcp-listen <int>` | API port + 100 | MCP HTTP listen port (e.g. API `8080` → MCP `8180`). |
| `--mcp-port <int>` | (alias) | Deprecated alias for `--mcp-listen`. |
| `--mcp-risk <list>` | `read,validate` | Comma-separated risk classes (`read`,`validate`,`execute`,`write`,`admin`) or `all`. Ceiling for every MCP client. |
| `--mcp-aliases` | `false` | Also register `sentinel_*` tool names (canonical names only by default). |

**MCP server:** When `--mcp` is set, MCP clients attach via streamable HTTP at `http://<mcp-bind>:<mcp-listen>/`. Default risk profile is read+validate only; pass `--mcp-risk all` for execute/write/admin tools. Canonical tool names only unless `--mcp-aliases` / `mcp.aliases`. `flow_run` waits for completion by default. Production mode requires the same auth as the harness API (Bearer token or Ed25519 signature). See **[MCP Agent Integration](/mcp-agent-integration)** for Cursor/Hermes setup, auth, resources, prompts, and the full tool list.

**Required environment variables:**

- `SENTINEL_VAULT_PASSPHRASE` -- Required if the vault database is encrypted.
- `SENTINEL_STATE_PASSPHRASE` -- Required if `state.encrypt_db` is `true` in config.

**Example output:**

```
Harness starting on http://localhost:8080
Press Ctrl+C to stop
```

**Daemon mode:**

When `--daemon` is set, the process forks into the background. The parent polls the child's health endpoint for up to 10s, then exits with a success/warning message. The PID file at `{SRE}/.sentinel/harness-{port}.pid` is used by `stop`, `restart`, `reload`, and `status` commands to locate the instance. If the PID file already exists and the process is dead, it is auto-cleaned. If the process is alive, the start command will fail unless `--force-reset` is specified.

**Examples:**

```bash
# Basic foreground start
./sentinel harness start -p /home/user/my-project

# Start on a custom port as a daemon
./sentinel harness start -p /home/user/my-project --port 9000 --daemon

# Start with Docker Compose stacks
./sentinel harness start -p /home/user/my-project --compose-up all

# Start wp-central with a dedicated WordPress ingress port
./sentinel harness start -p /home/user/my-central --compose-up wp-central --wp-port 8800

# Start with cache clearing and debug logging
./sentinel harness start -p /home/user/my-project --drop-web-cache --debug

# Start with MCP for AI agents (Cursor, Claude Desktop, Hermes, etc.)
./sentinel harness start -p /home/user/my-project --mcp --mcp-risk all

# MCP on a custom port, reachable from LAN (trusted networks only)
./sentinel harness start -p /home/user/my-project --mcp --mcp-bind 0.0.0.0 --mcp-listen 8180 --mcp-risk all
```

**Cursor MCP config example** (`.cursor/mcp.json` or project MCP settings). Full guide: [18-MCP-AGENT-INTEGRATION.md](/mcp-agent-integration).

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

Use `--mcp-listen` if the default (API port + 100) conflicts with another service.

### mcp proxy

Localhost signing proxy for MCP clients that cannot send dynamic `X-Sn-Sig` headers. Signs each request with a dashboard keypair and forwards to the upstream MCP server.

```bash
./sentinel mcp proxy --upstream http://127.0.0.1:8180
./sentinel mcp proxy --upstream http://127.0.0.1:8180 --listen 127.0.0.1:8190 --keypair-name cursor-agent
```

| Flag | Default | Description |
|------|---------|-------------|
| `--upstream` | (required) | Upstream MCP URL |
| `--listen` | `127.0.0.1:0` | Local bind host:port |
| `--home` | `$HOME` | Home dir with `.sentinel/dashboard.db` |
| `--keypair-name` | first keypair | Dashboard keypair name |

### mcp stdio

Stdio bridge for Hermes / Claude Desktop. Mirrors tools, resources, and prompts from an upstream streamable-HTTP MCP server.

```bash
./sentinel mcp stdio --upstream http://127.0.0.1:8180 --token YOUR_API_TOKEN
./sentinel mcp stdio --upstream http://127.0.0.1:8180 --sign --keypair-name cursor-agent
```

| Flag | Default | Description |
|------|---------|-------------|
| `--upstream` | (required) | Upstream MCP URL |
| `--token` | | Bearer token for upstream auth |
| `--sign` | `false` | Sign requests with a dashboard keypair |
| `--home` | `$HOME` | Home dir with `.sentinel/dashboard.db` |
| `--keypair-name` | first keypair | Dashboard keypair name when `--sign` |

Register the matching public key on the harness SRE: `{SRE}/.sentinel/pub-keys/{name}.pub`. Generate with `sentinel dashboard keygen`.

### stop

Stop a running harness. Discovers instances via port-stamped PID files. If multiple instances are running, prompts for selection or use `--port` to target directly.

```bash
./sentinel harness stop [flags]
```

| Flag | Description |
|------|-------------|
| `--port <int>` | Target a specific instance by port |
| `--compose-down <value>` | Also stop Docker stacks (`all` or comma-separated) |

### status

Show health status of running harness instance(s). Queries the `/hl` endpoint.

```bash
./sentinel harness status [flags]
```

| Flag | Description |
|------|-------------|
| `--port <int>` | Show status for a specific instance |

### restart

Stop the harness and start a fresh process (new PID) on the same port.

```bash
./sentinel harness restart [flags]
```

| Flag | Description |
|------|-------------|
| `--port <int>` | Target a specific instance by port |
| `--mcp` | Restart with MCP server enabled (passed through to `harness start`) |
| `--mcp-bind <addr>` | MCP bind address when `--mcp` is set |
| `--mcp-listen <int>` | MCP listen port when `--mcp` is set |
| `--mcp-port <int>` | Deprecated alias for `--mcp-listen` |
| `--mcp-risk <list>` | MCP risk classes when `--mcp` is set |
| `--mcp-aliases` | Register `sentinel_*` tool name aliases when `--mcp` is set |

### reload

Send SIGUSR1 to the running harness. It re-reads config, rediscovers kits, and reloads flows/triggers without restarting.

```bash
./sentinel harness reload [flags]
```

| Flag | Description |
|------|-------------|
| `--port <int>` | Target a specific instance by port |

### logs

Stream logs from the running harness via the `/lg` SSE endpoint.

```bash
./sentinel harness logs [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `-f`, `--follow` | `false` | Stream logs in real-time |
| `--level <string>` | (all) | Filter by level: debug, info, warn, error |
| `--execution-id <string>` | (all) | Filter by execution ID |

Also available as `sentinel logs` at the top level.

### wp-proxy

Manage a standalone WordPress reverse proxy. Boots only the WP gateway without flows, triggers, orchestrator, marketplace, Lua, or WebSocket.

```bash
./sentinel wp-proxy start|stop|status|restart|reload [flags]
```

`wp-proxy start` flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--port <int>` | `8800` | Port to listen on |
| `-d`, `--daemon` | `false` | Run in background |

### ps

Show all running Sentinel services (harness, dashboard, wp-proxy) in a unified table.

```bash
./sentinel ps
```

### doctor

Run pre-flight diagnostics: config validation, kit checks, database accessibility, port availability, and running instance health.

```bash
./sentinel doctor
```

### ccms (collection CMS)

```bash
./sentinel ccms status -p ./sre
./sentinel ccms migrate -p ./sre      # dump/backup production first; then restart Graphile (no --watch)
./sentinel ccms validate -p ./sre
./sentinel ccms install-refkit -p ./sre
```

Applies kit `dd/*.sql` to the Graphile data-plane Postgres and validates `forms/pub` collection forms. Does **not** run on harness start. After migrate, restart the Graphile container so PostGraphile re-introspects (compose omits `--watch`). See [Content planes](/content-planes).

### upgrade

Check for and install binary updates from GitHub Releases.

```bash
./sentinel upgrade [flags]
```

| Flag | Description |
|------|-------------|
| `--check` | Only check for updates, don't download |
| `--yes` | Download without prompting |
| `--url <string>` | Override release API URL |

---

## Dashboard Commands

The dashboard is a standalone web UI that connects to one or more harness instances. It provides visual management of flows, executions, logs, triggers, kits, forms, and secrets. The dashboard runs as its own HTTP server (default port 9090) and proxies API requests to the attached harness.

The dashboard's `/rag` page is also the operator surface for Sentinel retrieval. It includes:
- PostgreSQL connection selection for the RAG backend
- explicit embedding provider selection
- embedding model, task type, dimensions, and batch size controls
- watch-folder ingestion controls
- modality-aware search and test chat
- lifecycle operations such as backfill, reindex, rebuild indexes, and `Re-embed Stale`

### dashboard start

Start the web dashboard server.

```bash
./sentinel dashboard start [host:port] [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--sre-location <path>` | (none) | Optional local SRE path for dashboard features that need filesystem access. |
| `--port <int>` | `9090` | HTTP port for the dashboard web server. |
| `--harness <host:port>` | (none) | Explicit harness address. Overrides the positional argument if both are provided. |
| `--daemon` | `false` | Run the dashboard in the background. PID is written to `~/.sentinel/dashboard.pid`. |

**Discovery behavior:**

If you do not supply a harness address, the dashboard scans localhost ports 8080-8090 and auto-attaches to the first healthy harness it finds.

**Examples:**

```bash
# Start dashboard attached to a harness
./sentinel dashboard start localhost:8085

# Start on custom port pointing to a specific harness
./sentinel dashboard start --port 9091 --harness localhost:9000

# Start with local SRE path available for file-aware features
./sentinel dashboard start localhost:8085 --sre-location /home/user/my-project

# Start as background service
./sentinel dashboard start localhost:8085 --daemon
```

### dashboard stop

Stop the running dashboard process.

```bash
./sentinel dashboard stop
```

### dashboard status

Display the dashboard's current status, including whether it is running, which port it is listening on, and which harness runtime it is currently attached to.

```bash
./sentinel dashboard status
```

### dashboard attach

Register a harness runtime with the dashboard and mark it as the current target. If the dashboard server is already running, the command prints its URL. If it is not running, the command tells you how to start it.

```bash
./sentinel dashboard attach <host:port>
```

**Examples:**

```bash
./sentinel dashboard attach localhost:8080
./sentinel dashboard attach prod-harness.internal:8085
```

### dashboard detach

Detach the dashboard from its current harness runtime. The dashboard will continue running but will not display any harness data until re-attached.

```bash
./sentinel dashboard detach
```

### dashboard keygen

Generate an Ed25519 keypair for dashboard-to-harness authentication. This is used in production environments where the dashboard needs to authenticate its proxied requests to the harness.

```bash
./sentinel dashboard keygen --name <keypair-name>
```

**Flags:**

| Flag | Required | Description |
|------|----------|-------------|
| `--name <string>` | Yes | A human-readable name for this keypair (e.g., `laptop`, `ci-server`, `prod-dashboard`). |

The private key is stored in the dashboard's local database (`~/.sentinel/dashboard.db`). The corresponding public key must be registered with the target harness for authentication to work.

### dashboard add-runtime

Manually add a harness runtime entry to the dashboard. Use this for harness instances running outside the auto-discovery port range (8080-8090) or on remote machines.

```bash
./sentinel dashboard add-runtime <host:port> [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--name <string>` | (none) | A friendly display name for this runtime in the dashboard UI. |

**Examples:**

```bash
./sentinel dashboard add-runtime localhost:9000 --name "dev-local"
./sentinel dashboard add-runtime 192.168.1.50:8080 --name "staging"
```

### dashboard remove-runtime

Remove a manually-added runtime entry from the dashboard.

```bash
./sentinel dashboard remove-runtime <host:port>
```

### dashboard list-runtimes

List all known runtimes, including both auto-discovered instances (from scanning ports 8080-8090) and manually-added entries.

```bash
./sentinel dashboard list-runtimes
```

---

## Kit Management Commands

Kits are the fundamental unit of organization in Sentinel. Each kit is a self-contained directory containing flows, connectors, modules, forms, pages, templates, and assets.

### kit new

Scaffold a new kit directory with the standard structure.

```bash
./sentinel sre kit new <namespace.name> [flags]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `namespace.name` | Yes | The kit identifier in `{namespace}.{name}` format. Example: `acme.billing`, `sn.diag`. |

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--desc <string>` | (none) | A short description of the kit's purpose. Written to the `description` field in `kit.yaml`. |
| `--no-commit` | `false` | Skip the automatic git commit that normally follows kit creation. |

**What it creates:**

```
{namespace}.{name}/
  kit.yaml                  # Kit manifest (name, version, description)
  fl/                       # Flows directory
  cn/                       # Connectors directory
  md/                       # Modules directory
```

**Examples:**

```bash
./sentinel sre kit new acme.billing --desc "Payment processing workflows"
./sentinel sre kit new sn.diag --desc "Diagnostics" --no-commit
```

### kit validate

Validate one or more kits, or all kits in the project if no kit IDs are provided.

```bash
./sentinel sre validate [kit-id ...]
```

This command checks:
- `kit.yaml` loadability
- `README.md` presence
- `Compatibility Matrix` presence in the README
- `.lua.md` skill twins for Lua artifacts
- `_test.lua` coverage for Lua artifacts
- lightweight tool-schema guardrails

### kit diff

Show kits that have been modified since the harness last started or reloaded. Compares on-disk file modification times against harness uptime.

```bash
./sentinel sre kit diff
```

If the harness is offline, lists all kits with "unknown" status.

### kit list

List all kits discovered in the project directory. The harness scans the project root for directories matching the `{namespace}.{name}` pattern that contain a `kit.yaml` manifest file.

```bash
./sentinel sre kit list [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--json` | `false` | Output the list as JSON instead of a formatted table. |
| `--filter <prefix>` | (none) | Filter kits by namespace prefix. Example: `--filter sn` shows only kits in the `sn` namespace. |

**Example output:**

```
Kit              Has UI    Path
acme.billing     true      acme.billing/
sn.core-agent    false     sn.core-agent/
sn.diag          false     sn.diag/
```

### kit install

Install a kit from the Sentinel Kit Marketplace (SKM). Requires prior authentication via `sentinel login`.

```bash
./sentinel sre kit install <kit-id>[@version]
```

The command downloads the kit archive from the marketplace, verifies its Ed25519 signature, and extracts it into the project root directory.

**Examples:**

```bash
# Install latest version
./sentinel sre kit install acme.billing

# Install specific version
./sentinel sre kit install acme.billing@1.2.0
```

### kit update

Update an installed marketplace kit to the latest available version.

```bash
./sentinel sre kit update <kit-id>
```

**Examples:**

```bash
./sentinel sre kit update acme.billing
```

### kit marketplace

List all marketplace-installed kits in the current project, including their version, vendor, and signature timestamp.

```bash
./sentinel sre kit marketplace
```

**Example output:**

```
KIT              VERSION  VENDOR       SIGNED
acme.billing     1.2.0    acme-corp    2026-03-01T00:00:00Z
```

### kit remove

Remove a marketplace-installed kit from the project.

```bash
./sentinel sre kit remove <kit-id>
```

### bundle install

Install one or more bundles. Resolves bundles from SKM to get the exact kit list, then downloads and installs each kit with signature verification. Falls back to local starter kits if SKM is unreachable.

```bash
./sentinel sre bundle install <bundle[@version]> [bundle...]
```

**Examples:**

```bash
./sentinel sre bundle install core
./sentinel sre bundle install core@1.0.0
./sentinel sre bundle install wp-central
./sentinel sre bundle install core,examples
```

### bundle update

Update an installed bundle to the latest version from SKM.

```bash
./sentinel sre bundle update <bundle>
```

### bundle remove

Remove bundle tracking metadata. Does not uninstall the individual kits.

```bash
./sentinel sre bundle remove <bundle>
```

### bundle list

List available bundles from SKM. Falls back to local bundle definitions if SKM is unreachable.

```bash
./sentinel sre bundle list
```

### bundle status

Show installed bundles and their versions.

```bash
./sentinel sre bundle status
```

---

## Flow Management Commands

Flows are the core executable units in Sentinel -- Lua scripts that perform business logic, integrations, and automation.

### flow run

Execute a flow manually. This is an alias for the top-level `sentinel run` command, placed under `flow` for discoverability.

```bash
./sentinel flow run <flow-id> [flags]
```

| Flag | Description |
|------|-------------|
| `--async` | Don't wait for completion |
| `--param <key=value>` | Set parameter (repeatable) |
| `--params-json <json>` | Set parameters as JSON string |
| `--params-file <path>` | Set parameters from JSON file |

**Examples:**

```bash
./sentinel flow run sn.core/assistant --param user=test
./sentinel run sn.core/assistant --params-json '{"message":"hello"}'
```

### flow list

List all flows discovered within a specific kit. Flows are auto-discovered from the `fl/` directory inside each kit.

```bash
./sentinel flow list --kit <kit-id>
```

**Example output:**

```
Name                  Path
process-payment       fl/process-payment.lua
generate-invoice      fl/generate-invoice.lua
handle-refund         fl/handle-refund.lua
```

### flow new

Create a new flow file within a kit. This scaffolds a Lua file with the standard function signatures (`setup`, `main`, `cleanup`, `failed`) and a corresponding `.md` skill twin file. Use `--preset agent` for an opinionated agent starter.

```bash
./sentinel sre flow new <flow-name> --kit <kit-id> [--preset agent]
```

Related presets:

```bash
./sentinel sre flow new assistant --kit sn.my-kit --preset agent
./sentinel connector new lookup --kit sn.my-kit --preset tool
./sentinel module new knowledge --kit sn.my-kit --preset rag
```

### run

Execute a flow immediately. This triggers the flow's `main()` function and returns the result.

```bash
./sentinel run <flow-id> [flags]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `flow-id` | Yes | The fully-qualified flow identifier in `{namespace}-{name}:{flow}` format. Example: `sn-core-agent:assistant`. |

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--params-json <json>` | (none) | JSON string of parameters to pass to the flow's `main()` function. |
| `--async` | `false` | Start the flow execution asynchronously and return the execution ID immediately instead of waiting for completion. |

**Examples:**

```bash
# Run a flow synchronously
./sentinel run sn-core-agent:assistant

# Run with parameters
./sentinel run sn-core-agent:assistant --params-json '{"message": "Hello, world!"}'

# Run asynchronously (returns execution ID)
./sentinel run sn-core-agent:assistant --async
```

---

## Secrets Commands

Sentinel includes a built-in encrypted vault for storing sensitive values like API keys, tokens, and passwords. Secrets stored in the vault are accessible from Lua flows via `ctx.secret("secret_name")`.

### secret ls

List all secrets stored in the vault. By default, only metadata (name, creation date, last updated date) is shown -- values are not displayed.

```bash
./sentinel secret ls [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--show` | `false` | Include the decrypted secret values in the output. Use with caution. |

**Example output:**

```
Name              Created                  Updated
slack_token       2026-02-09T00:00:00Z     2026-02-10T11:30:00Z
github_token      2026-02-08T00:00:00Z     2026-02-08T00:00:00Z
```

### secret set

Create a new secret or update an existing one.

```bash
./sentinel secret set <name> [value] [flags]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `name` | Yes | The secret name. Used to retrieve the value in Lua via `ctx.secret("name")`. |
| `value` | No | The secret value. If omitted, the command enters interactive mode (prompting for the value with masked input) or reads from stdin with `--stdin`. |

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--stdin` | `false` | Read the secret value from standard input. Useful for piping from files or other commands. |
| `--interactive` | `false` | Prompt for the value with masked input (dots instead of characters). |
| `--description <string>` | (none) | Optional description of the secret's purpose. |
| `--tags <string>` | (none) | Comma-separated tags for organizing secrets (e.g., `prod,api,stripe`). |

**Examples:**

```bash
# Set directly (value visible in process listing -- avoid in production)
./sentinel secret set slack_token xoxb-1234567890

# Interactive mode (value is masked)
./sentinel secret set api_key --interactive
# Enter value for api_key: ••••••••••••••

# From file
./sentinel secret set api_key --stdin < /path/to/secret.txt

# With metadata
./sentinel secret set stripe_key --description "Stripe live API key" --tags "prod,payments"
```

### secret rm

Delete a secret from the vault.

```bash
./sentinel secret rm <name> [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--yes` | `false` | Skip the confirmation prompt. |

**Examples:**

```bash
# With confirmation prompt
./sentinel secret rm slack_token

# Skip confirmation (for scripts)
./sentinel secret rm slack_token --yes
```

---

## Database Commands

Each kit can have its own SQLite database, stored at `.sentinel/data/{kit-id}.db`. These commands allow you to inspect, query, optimize, and back up kit databases from the command line.

### db status

Display the status of a kit's database, including file size, table count, and whether encryption is enabled.

```bash
./sentinel db status [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--kit <kit-id>` | (none) | The kit whose database to inspect. |

### db query

Execute a read-only SQL query (SELECT or PRAGMA) against a kit's database and display the results.

```bash
./sentinel db query "<sql>" --kit <kit-id>
```

Only SELECT and PRAGMA statements are allowed for safety. Write operations must be performed through Lua flows.

**Examples:**

```bash
./sentinel db query "SELECT COUNT(*) FROM invoices" --kit acme.billing
./sentinel db query "PRAGMA table_info(invoices)" --kit acme.billing
```

### db optimize

Run database optimization: REINDEX (rebuild indexes), ANALYZE (update query planner statistics), and VACUUM (reclaim unused space and defragment the database file).

```bash
./sentinel db optimize --kit <kit-id>
```

Run this periodically on databases with heavy write activity to maintain query performance.

### db backup

Create a backup copy of a kit's database file.

```bash
./sentinel db backup --kit <kit-id> [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--output <path>` | (auto-generated) | Destination file path for the backup. If omitted, a timestamped filename is generated. |

**Examples:**

```bash
./sentinel db backup --kit acme.billing
./sentinel db backup --kit acme.billing --output /backups/acme.billing-20260306.db
```

### db restore

Restore a kit's database from a previously created backup file.

```bash
./sentinel db restore --kit <kit-id> --from <backup-path>
```

**Important:** The harness should be stopped before restoring a database. Restoring while the harness is running may cause data corruption.

**Examples:**

```bash
./sentinel harness stop -p /home/user/my-project
./sentinel db restore --kit acme.billing --from /backups/acme.billing-20260306.db
./sentinel harness start -p /home/user/my-project
```

### backup

Inspect the harness-level backup subsystem for folder archives and PostgreSQL dump plans.

#### backup list

```bash
./sentinel backup list
```

Lists configured backup plans with type, enabled state, cron schedule, target, and retention count.

#### backup runs

```bash
./sentinel backup runs
./sentinel backup runs --limit 50
./sentinel backup runs --status failed
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--limit <int>` | `20` | Maximum number of runs to show |
| `--status <string>` | `""` | Optional filter by status (`running`, `success`, `failed`) |

#### backup running

```bash
./sentinel backup running
```

Shows currently running backup jobs from recent persisted harness state.

#### backup status

```bash
./sentinel backup status
```

Shows a summary of total plans, enabled plans, running jobs, and recent failures.

`sentinel backup` is distinct from `sentinel db backup`:
- `sentinel db backup` is kit-scoped SQLite backup tooling
- `sentinel backup` is the harness-managed subsystem for scheduled PostgreSQL and folder backups

---

## Testing Commands

### test

Run Lua test files for a kit or a specific directory within a kit. Test files must follow the naming convention `*_test.lua` and be located within the kit directory.

```bash
./sentinel sre test <target> [flags]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `target` | Yes | Kit ID or path within a kit to test. Examples: `acme.billing`, `acme.billing/fl`. |

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `-v` | `false` | Verbose output showing each test function's name, duration, and result. |
| `-f <pattern>` | (none) | Filter: only run test functions whose names contain this substring. |

**Test file structure:**

Test files contain functions prefixed with `test_`. Each function is executed independently.

```lua
-- acme.billing/fl/payment_test.lua

function test_payment_success()
  local result = process_payment({invoice_id = "inv_test", amount = 1000})
  sn.test.ok(result.ok, "Payment should succeed")
end

function test_payment_invalid_amount()
  local result = process_payment({invoice_id = "inv_test", amount = -100})
  sn.test.ok(not result.ok, "Should reject negative amount")
end
```

**Example output:**

```
Testing acme.billing...
  test_payment_success (0.2ms)
  test_payment_invalid_amount (0.5ms)
---
2 tests, 0 failures
```

**Examples:**

```bash
# Run all tests in a kit
./sentinel sre test acme.billing

# Run only flow tests
./sentinel sre test acme.billing/fl

# Run with verbose output, filtering by name
./sentinel sre test acme.billing -v -f payment
```

### audit

Validate the structure and configuration of an SRE project. The audit command checks for common issues such as missing `kit.yaml` files, invalid directory names, broken flow references, and configuration errors.

```bash
./sentinel audit [path]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `path` | No | Path to the SRE directory to audit. Defaults to the current directory. |

**Examples:**

```bash
./sentinel audit
./sentinel audit /home/user/my-project
```

---

## Marketplace Authentication Commands

The Sentinel Kit Marketplace (SKM) is a repository of published kits. These commands manage your authentication and licensing for marketplace access.

### login

Authenticate with the SKM using the OAuth 2.0 Device Code Flow. This is the same flow used by GitHub CLI and similar tools -- you are given a URL and a code to enter in your browser.

```bash
./sentinel login
```

**Flow:**

1. The CLI initiates a device authorization request to the SKM.
2. A verification URL and a user code are displayed.
3. Your default browser opens to the verification URL automatically.
4. You enter the code in the browser and approve the authorization.
5. The CLI polls for completion and stores the resulting tokens at `~/.sentinel/auth.json`.

**Example output:**

```
To authenticate, visit: https://kits.ndx.au/device
Enter code: ABCD-1234
Waiting for authorization...
Login successful!
```

### logout

Remove stored marketplace authentication tokens from `~/.sentinel/auth.json`.

```bash
./sentinel logout
```

### license activate

Activate a marketplace license key. License keys are Ed25519-signed tokens that determine your access tier (community, professional, enterprise).

```bash
./sentinel license activate <license-key>
```

The command parses and verifies the Ed25519 signature on the key, then stores it in `.sentinel/config.json` under `marketplace.license_key`.

**License key formats:**

- `sk_free_...` -- Community tier (free)
- `sk_ent_...` -- Enterprise tier

**Example output:**

```
License activated!
  Type: free
  ID:   lic_abc123
  Tier: community
  Expires: 2027-01-01
```

### license show

Display information about the currently activated license, including the tier, expiration date, and license ID.

```bash
./sentinel license show
```

### license clear

Remove the stored license key from the configuration. This does not revoke the license on the marketplace server -- it only removes the local copy.

```bash
./sentinel license clear
```

---

## Configuration Commands

Read and write `.sentinel/config.json` (per-machine infrastructure config).

### config get

Retrieve a configuration value by its dot-notation key path.

```bash
./sentinel config get <key>
./sentinel config get api.port        # prints: 8080
./sentinel config get log.level       # prints: info
./sentinel config get tls --json      # prints: {"enabled": false, ...}
```

### config set

Set a configuration value. Auto-coerces the value to int, bool, or string. Validates the resulting config after write.

```bash
./sentinel config set <key> <value>
```

**Examples:**

```bash
./sentinel config set api.port 9000
./sentinel config set log.level debug
./sentinel config set tls.enabled true
```

### config list

Show the full configuration as formatted JSON.

```bash
./sentinel config list
```

### config path

Print the resolved path to `.sentinel/config.json`.

```bash
./sentinel config path
```

---

## Logs Command

### logs

Stream logs from the running harness via the `/lg` SSE endpoint. Logs are colour-coded by level with human-readable timestamps. Also available as `sentinel harness logs`.

```bash
./sentinel logs [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `-f`, `--follow` | `false` | Stream logs in real-time (like `tail -f`) |
| `--execution-id <id>` | (all) | Filter to a specific execution |
| `--level <level>` | (all) | Filter by minimum level: `debug`, `info`, `warn`, `error` |

**Examples:**

```bash
# Stream all logs in real-time
./sentinel logs -f

# View only errors
./sentinel logs --level error

# Tail logs for a specific execution
./sentinel harness logs -f --execution-id exec_abc123
```

---

## Documentation Commands

These commands generate documentation artifacts from kit definitions.

### docs gen-schema

Generate schema documentation from a kit's database definition. Outputs a YAML or Markdown representation of all tables, columns, indexes, and their types.

```bash
./sentinel docs gen-schema --kit <kit-id> [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--output <path>` | (stdout) | Write output to a file instead of stdout. |

### docs gen-plan

Generate a care plan template for a kit. A care plan documents the kit's purpose, dependencies, maintenance schedule, and operational procedures.

```bash
./sentinel docs gen-plan --kit <kit-id> [flags]
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--output <path>` | (stdout) | Write output to a file instead of stdout. |

---

## API Library Commands

### lib schema

Print the JSON schema for vendor-packaged API Library collections.

```bash
./sentinel lib schema [output-file]
```

### lib export

Export one vendor as a JSON collection.

```bash
./sentinel lib export <vendor-id> [output-file]
```

### lib export-all

Export the entire API Library as one JSON bundle. This is the easiest way to persist the library inside the SRE or commit it to git.

```bash
./sentinel lib export-all [output-file]
```

### lib import

Import one vendor-packaged JSON collection.

```bash
./sentinel lib import <json-file>
```

### lib import-all

Import a multi-vendor JSON bundle.

```bash
./sentinel lib import-all <json-file>
```

---

## Help and Version

### --help

Display help information for any command. Every command and subcommand supports the `--help` flag, which shows a description, available flags, and usage examples.

```bash
./sentinel --help
./sentinel harness start --help
./sentinel sre kit new --help
./sentinel dashboard start --help
```

### version

Display the Sentinel version string and build information.

```bash
./sentinel version
```

**Example output:**

```
sentinel version v0.1.1-dev
```

---

## Output Formats

Sentinel supports three output modes that can be controlled with global flags.

### Default (Pretty)

Human-readable output with aligned columns and ANSI colors. This is the default when running in a terminal.

```
ID              Flow                    Type      Enabled
cr_abc123       sn-core-agent:heartbeat       CRON      true
wh_def456       acme-billing:webhook          WEBHOOK   true
```

### JSON (--json)

Machine-readable JSON output. Every response is a JSON object with at minimum an `ok` field. Error responses include `err` (error code) and `msg` (human-readable message).

```json
{"ok": true, "data": [...]}
{"ok": false, "err": "NOT_FOUND", "msg": "Flow not found: acme.billing/nonexistent"}
```

Use this mode for scripting and automation:

```bash
./sentinel sre kit list --json | jq '.data[] | .name'
```

### Debug (--debug)

Verbose output that includes detailed log messages about internal operations. Debug output goes to stderr while command results go to stdout, so they can be separated in scripts.

```
[2026-03-06 12:00:00] DEBUG: Loading kit acme.billing from acme.billing/
[2026-03-06 12:00:00] DEBUG: Discovered 3 flows in acme.billing/fl/
[2026-03-06 12:00:00] DEBUG: Registering cron trigger cr_abc123 for acme.billing/daily-report
[2026-03-06 12:00:00] DEBUG: Kit acme.billing loaded successfully
```

---

## Common Workflows

### First Project Setup

This walkthrough covers creating a new project, adding a kit with a flow, and running it.

```bash
# Step 1: Build the binary (if not already done)
go build -tags dev -o sentinel ./cmd/sentinel

# Step 2: Initialize a new project
./sentinel sre init my-project
# Follow the interactive prompts or use --no-input for defaults

# Step 3: Start the harness and dashboard together
./sentinel harness start -p my-project
# Harness: http://localhost:8080
# Dashboard: http://localhost:9090

# Step 4: Open the dashboard in your browser
# Navigate to http://localhost:9090 to see the UI

# Step 5: Create a new kit
./sentinel sre kit new acme.hello --desc "Hello world example" -p my-project

# Step 6: Add a flow (create the file manually in the kit)
# Create my-project/acme.hello/fl/greet.lua with your flow logic

# Step 7: The harness hot-reloads automatically when files change.
# Run the flow:
./sentinel run acme.hello/greet -p my-project
```

### Adding and Using Secrets

Secrets allow your flows to access sensitive values like API keys without hardcoding them.

```bash
# Step 1: Set a secret (interactive mode for safety)
./sentinel secret set stripe_api_key --interactive -p my-project
# Enter value for stripe_api_key: ••••••••••••••

# Step 2: Verify the secret was stored
./sentinel secret ls -p my-project

# Step 3: Use in a Lua flow
# In your .lua file:
#   local key = ctx.secret("stripe_api_key")

# Step 4: Run the flow
./sentinel run acme.billing/charge -p my-project
```

### Creating and Testing Flows

```bash
# Step 1: Create a kit if you don't have one
./sentinel sre kit new acme.test --desc "Test flows" -p my-project

# Step 2: Create your flow file
# Write my-project/acme.test/fl/example.lua

# Step 3: Create a test file
# Write my-project/acme.test/fl/example_test.lua

# Step 4: Run tests
./sentinel sre test acme.test -p my-project -v

# Step 5: Run the flow manually to verify
./sentinel run acme.test/example -p my-project

# Step 6: Check execution logs
./sentinel logs --execution-id <exec-id-from-step-5>
```

### Debugging Issues

When things are not working as expected, follow this systematic approach:

```bash
# Step 1: Check if the harness is running and healthy
./sentinel harness status -p my-project

# Step 2: Audit the project structure for configuration errors
./sentinel audit my-project

# Step 3: Restart with debug logging to see detailed output
./sentinel harness start -p my-project --debug

# Step 4: Check execution logs for errors
./sentinel logs --level error

# Step 5: If the harness won't start (stale PID file), force reset
./sentinel harness start -p my-project --force-reset

# Step 6: If databases seem corrupted, try optimization
./sentinel db optimize --kit acme.billing -p my-project
```

### Production Deployment

```bash
# Step 1: Build a release binary (no debug mode)
go build -ldflags="-s -w" -o sentinel ./cmd/sentinel

# Step 2: Configure authentication tokens
# Edit .sentinel/config.json:
#   "api": { "debug_mode": false, "tokens": ["<64+ char random token>"] }

# Step 3: Set encryption passphrases
export SENTINEL_VAULT_PASSPHRASE="<32+ character random passphrase>"
export SENTINEL_STATE_PASSPHRASE="<32+ character random passphrase>"

# Step 4: Enable TLS (edit .sentinel/config.json)
#   "tls": { "enabled": true, "port": 8443, "hosts": ["your-hostname"], "ips": ["your-ip"] }

# Step 5: Start as daemon
./sentinel harness start -p /opt/my-project --daemon

# Step 6: Verify
curl -H "Authorization: Bearer <your-token>" https://localhost:8443/hl
```

---

## Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `project not found` | The `-p` path does not point to a valid SRE directory. | Verify the directory exists and contains `sentinel.yaml`. |
| `vault locked` | The vault is encrypted but `SENTINEL_VAULT_PASSPHRASE` is not set. | Set the environment variable before starting the harness. |
| `port already in use` | Another process is listening on the requested port. | Use a different `--port` value, or use `--force-reset` to kill the conflicting Sentinel process. |
| `invalid flow ID` | The flow identifier does not match `{namespace}-{name}:{flow}` format. | Use the correct format, e.g., `acme-billing:process-payment`. |
| `secret not found` | The requested secret does not exist in the vault. | Create it with `sentinel secret set`. |
| `flow timeout` | The flow's `main()` function exceeded the execution timeout. | Increase `lua.execution_timeout` in `.sentinel/config.json` (default: 30 seconds). |
| `debug mode is disabled in production builds` | A release build has `api.debug_mode: true` in config. | Set `api.debug_mode` to `false` and configure `api.tokens` with at least one authentication token. |
| `api.tokens cannot be empty in production mode` | `api.debug_mode` is `false` but no tokens are configured. | Add at least one token to `api.tokens` in `.sentinel/config.json`, or set `api.debug_mode` to `true` for development. |

---

## Best Practices

1. **Always use `-p` with absolute paths** in scripts and automation to avoid confusion about which project directory is being targeted.
2. **Set secrets via environment variables or interactive mode**, never as command-line arguments where they appear in process listings and shell history.
3. **Use `--json` for scripting** to get structured, parseable output that can be piped to `jq` or processed by other tools.
4. **Enable `--debug` when troubleshooting** to see detailed internal logging of kit loading, flow registration, and execution steps.
5. **Run `audit` regularly** to catch configuration issues, missing files, and structural problems before they cause runtime errors.
6. **Use `--force-reset` sparingly** -- it kills all matching processes and deletes PID files. Only use when a clean shutdown failed.
7. **Back up data before major changes** using `db backup` for kit SQLite files and `backup` commands for harness-level PostgreSQL or folder plans.
8. **Test flows before scheduling them** with cron triggers. Use `sentinel run` manually first to verify correct behavior.
9. **Use daemon mode in production** (`--daemon`) and manage the process with your system's service manager (systemd, supervisord, etc.).
10. **Keep the binary and SRE separate** -- the Sentinel binary should not live inside the SRE project directory. Store it in `/usr/local/bin` or similar.
