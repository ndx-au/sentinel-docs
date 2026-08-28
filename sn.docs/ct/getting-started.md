---
title: "Getting Started with Sentinel"
description: "Welcome to Sentinel. This guide is your starting point -- whether you are a developer who wants to automate workflows, an operations engineer evaluating orchestration tools, or an AI agent consuming this documentation programmatically."
---

# Getting Started with Sentinel

Welcome to Sentinel. This guide is your starting point -- whether you are a developer who wants to automate workflows, an operations engineer evaluating orchestration tools, or an AI agent consuming this documentation programmatically. By the end of this guide, you will have a running Sentinel instance with your first flow executing successfully.

---

## What is Sentinel?

Sentinel is a **git-native orchestration harness** for defining, scheduling, and executing automated workflows. At its core, it is a single compiled Go binary (the "harness") that reads a folder of Lua scripts, YAML configurations, and supporting files (the "SRE" -- Sentinel Runtime Environment), and brings them to life as a fully functional automation platform with an HTTP API, a web dashboard, a trigger engine, an encrypted secret vault, and a state database.

**The problem Sentinel solves** is this: most orchestration tools force you to choose between simplicity (drag-and-drop UIs with limited logic) and power (complex infrastructure with message brokers, worker pools, and container orchestration). Sentinel eliminates that trade-off. You write real code in Lua -- a lightweight, readable scripting language -- and Sentinel handles everything else. No Redis. No Celery. No Kubernetes. No Docker Compose files with twelve services. Just one binary and one folder.

**What makes Sentinel different from tools like Airflow, n8n, or Zapier?**

- **Real code, not YAML pipelines or visual nodes.** Your flows are Lua scripts with full programming constructs: loops, conditionals, error handling, string manipulation, HTTP calls. You are not limited to what a UI builder exposes.
- **Git-native by design.** Your entire project lives in a plain directory that you commit to Git. There is no separate database of workflow definitions, no export/import dance, no configuration drift. Git is the source of truth.
- **Single binary deployment.** The `sentinel` binary embeds everything: the Lua runtime, an SQLite state database, an encrypted vault, a web server, a cron scheduler, and a WebSocket bus. You copy the binary to a server, point it at a folder, and you are running.
- **AI-first architecture.** Every code file gets an auto-generated `.md` "skill twin" that provides persistent context for AI agents. The HTTP API uses a brevity regime (short two-character endpoints like `/fl`, `/ex`, `/lg`) optimized for token-efficient consumption by language models. Sentinel is designed to be operated by humans and AI agents equally well.
- **Kit-based modularity.** Logic is organized into "kits" -- self-contained directories with their own flows, forms, databases, connectors, and web pages. Kits are the unit of reuse: you can share them, install them from a marketplace, or compose multiple kits in one project.

---

## How Sentinel Works

Understanding the architecture will help everything else make sense. There are only a few moving parts:

### The Harness (Go Binary)

The harness is the `sentinel` binary itself. It is the engine that does all the work:
- Starts an HTTP API server (default port 8080)
- Discovers and loads kits from the SRE directory
- Registers flows and their triggers (cron schedules, webhook endpoints, event listeners)
- Executes Lua flows in a sandboxed virtual machine when triggered
- Manages an encrypted secret vault for API keys and credentials
- Maintains an SQLite database of execution history, logs, and state
- Provides a WebSocket bus for real-time events

You do not modify the harness. It is a compiled binary that you download or build once.

### The SRE (Sentinel Runtime Environment)

The SRE is just a folder -- your project directory. It contains:
- `sentinel.yaml` -- your project's identity (name, version, description)
- `.sentinel/` -- machine-local state (config, vault, databases) that is gitignored
- Kit directories (e.g., `sn.core-agent/`, `acme.billing/`) containing all your logic

A single git repo can contain multiple SREs in subfolders. The default (1:1) model places the SRE at the repo root, but you can also use `-p` to place SREs in subdirectories (e.g., `sentinel sre init -p central --wp-central` and `sentinel sre init -p edge --wp-edge` in the same repo).

When the harness starts, it scans the SRE directory, discovers all kits, registers all flows and triggers, and begins serving the API. Everything the harness needs is in this folder.

New projects initialized with `sentinel sre init` include repo-level files (`CLAUDE.md`, `.gitignore`, `.gitattributes`, operator `README.md`) and a minimal `sentinel.yaml` — **no kits by default**. Install starter content from [ndx-video/sre-init](https://github.com/ndx-au/sre-init) with `--with-bundle core`, `--starter-kits`, or `--with-local ../sre-init` (air-gap). WordPress profiles: `--wp-central` / `--wp-edge` (skip wizard, install WP kits only). Marketplace kits: `--with-kit` / `--with-bundle` when SKM is configured.

### Kits

Kits are the organizational unit. Rather than throwing all your Lua scripts into one directory, you group related logic into kits. Each kit is a directory with a `kit.yaml` manifest and subdirectories for different types of content (flows, connectors, modules, forms, pages).

Kit directories follow a `{namespace}.{name}` naming convention. For example, `sn.core-agent` is a built-in starter kit in the `sn` namespace. You might create `acme.billing` for your billing logic or `acme.notifications` for notification workflows.

### Flows

Flows are Lua scripts that do actual work. Every flow has up to four lifecycle functions:

- `setup()` -- runs first, for initialization (optional)
- `main()` -- the primary logic (required)
- `cleanup()` -- runs after main completes, even on success (optional)
- `failed(err)` -- runs only if main throws an error (optional)

Flows are discovered automatically from `fl/` directories inside kits. You do not need to register them anywhere -- just create a `.lua` file in the right place and restart (or let hot-reload pick it up).

### Triggers

Triggers connect flows to events. A flow without a trigger can still be run manually via the API or dashboard, but triggers let you automate execution. There are five types: cron (time-based schedules), webhook (incoming HTTP POST), event (internal pub/sub), manual (explicit API call), and form (user submission).

### Everything is Git-Tracked

Because the SRE is a plain folder, you simply `git init`, commit your files, and push. The `.sentinel/` directory is automatically gitignored (it contains machine-specific state like databases and vault files). Everything else -- your flows, kit manifests, forms, pages, connector definitions -- lives in Git. Deployment is `git pull` followed by a restart.

---

## Prerequisites

**Required:**
- **Git** -- Must be installed and available in your PATH. Sentinel uses Git for version tracking, the dashboard's git operations panel, and hot-reload change detection.

**Operating system support:**
- **Linux** -- Recommended for production deployments. Tested on Ubuntu, Debian, and Fedora.
- **macOS** -- Fully supported for development. Works on both Intel and Apple Silicon.
- **Windows** -- Supported for development. Use `sentinel.exe` instead of `sentinel` in all commands. Not recommended for production.

**Not required:**
- No Docker, no container runtime
- No database server (SQLite is embedded)
- No message broker (triggers are built in)
- No language runtime (Lua VM is embedded in the binary)

---

## Quick Start (5 minutes)

This walkthrough takes you from zero to a running Sentinel instance with an executed flow. Every step explains what is happening and why.

### 1. Get the Binary

Download the pre-built binary for your platform, or build from source:

```bash
# If building from source (requires Go 1.25+):
go build -tags dev -o sentinel ./cmd/sentinel

# Verify it works:
./sentinel version
# Output: vX.Y.Z-dev (build YYYY-MM-DD)
```

On Windows, the binary is `sentinel.exe`. All subsequent examples use `sentinel` -- substitute `sentinel.exe` on Windows.

### 2. Initialize a New Project

```bash
mkdir my-project && cd my-project && git init
sentinel sre init
```

**What this does:** The `init` command runs at the repository root (current working directory). It creates two categories of files:

**Repo-level files** (written to cwd, skipped if they already exist):
- `CLAUDE.md` -- AI assistant orientation for the project.
- `.claude/skills/` -- built-in SRE guidance skills.
- `.gitignore` -- Ignores `.sentinel/` and `_data/` directories.
- `.gitattributes` -- Line ending normalization.

**SRE-level files** (written to the path specified by `-p`/`--project`, defaults to `.`):
- `sentinel.yaml` -- The project manifest. Contains the project name, description, and version. This file is git-tracked and defines your project's identity.
- `.sentinel/config.json` -- Machine-local configuration (API port, log level, TLS settings). This is gitignored because it varies per deployment.
- `.sentinel/vault.db` -- The encrypted secret vault (created on first use).
- Bundled starter kits such as `sn.core-agent/`, `sn.core-rag/`, `sn.tools-http/`, `sn.supervisor/`, `sn.eg-support/`, `sn.eg-itops/`, `sn.eg-rag-chat/`, plus the legacy `sn.example-support/` and `sn.example-itops/` compatibility kits.
- Optional WordPress profiles: `sentinel sre init --wp-central` installs `sn.wp-central/`, and `sentinel sre init --wp-edge` installs `sn.wp-edge/`. Profile flags (`--wp-central`, `--wp-edge`) suppress default starter kits and skip the interactive wizard.
- Optional post-init provisioning: `sentinel sre init ... --with-kit acme.foo,acme.bar` and `sentinel sre init ... --with-bundle core,wp-central`.
- `sentinel sre init --wp-central` also seeds `docker-compose.wp-central.yaml` so a local managed WordPress stack can be started with `sentinel harness start --compose-up wp-central`.
- That development compose file uses floating `:latest` WordPress and MariaDB images and persists the WordPress stack under `./_data/wp-central/`.
- `sn.wp-central` also expects a dedicated WordPress ingress port. By default that is `8800`, configurable via `wp_central.port` in `sentinel.yaml` or `--wp-port` on the CLI.

For multi-SRE repos, use `-p` to place each SRE in a subfolder (e.g., `sentinel sre init -p central --wp-central`). Repo-level files are written once and shared across all SREs.

For the full local WordPress bootstrap path, including the first-run install, dedicated integration user, Application Password generation, and vault setup, see [WordPress with sn.wp-central](/wordpress).

**Why two config files?** The `sentinel.yaml` file tracks project behavior that should be consistent across all environments (name, version, feature flags). The `.sentinel/config.json` file holds infrastructure settings that change per machine (which port to listen on, TLS certificate paths, marketplace credentials). This separation keeps secrets and machine-specific details out of your git repository.

### 3. Start the Harness

```bash
sentinel harness start
# Or, if your SRE is in a subfolder:
# sentinel harness start -p ./my-project
```

**What happens at startup:**

1. The harness reads `sentinel.yaml` from the specified path to identify the project.
2. It loads `.sentinel/config.json` for machine-local settings (port, logging, etc.).
3. It scans the SRE directory for kit directories (any folder matching the `{namespace}.{name}` pattern with a `kit.yaml` file).
4. For each discovered kit, it loads flows from `fl/`, registers connectors from `cn/`, loads modules from `md/`, and indexes forms from `fm/`.
5. It parses trigger definitions and schedules cron jobs, registers webhook endpoints, and subscribes to event channels.
6. It starts the HTTP API server on the configured port (default 8080).
7. It starts the WebSocket bus for real-time event streaming.

You should see output like:

```
Sentinel vX.Y.Z starting...
  Project: my-project
  API:     http://localhost:8080
  Kits:    6 loaded (starter kits)
  Flows:   6+ registered
  Triggers: 0 active
Press Ctrl+C to stop
```

**Verify it is running:**

```bash
curl http://localhost:8080/hl
```

This hits the health endpoint (`/hl`) and returns a structured JSON response showing the status of all subsystems.

### 4. Start the Dashboard (Optional)

Open a second terminal:

```bash
sentinel dashboard start localhost:8080
```

**What this does:** Starts a separate web UI process on port 9090 and attaches it to the harness you named. The dashboard is a BFF (Backend For Frontend) proxy -- it provides a user-friendly interface for managing flows, viewing executions, browsing kits, editing files, and monitoring the system. It communicates with the harness API behind the scenes.

You can also use the longer form:

```bash
sentinel dashboard start localhost:8080
```

Open your browser to `http://localhost:9090` to see the dashboard.

The dashboard is optional. Everything it does can also be done via the REST API or CLI. But it is very useful for development, debugging, and demonstration.

Recent operator pages beyond flows include:
- `/storage` for S3-compatible storage points
- `/backups` for scheduled PostgreSQL and folder backups
- `/rag` for the retrieval control plane

When Docker is available on the attached harness, the RAG page also offers `Enable Managed RAG`, which provisions and initializes the single harness-level RAG PostgreSQL stack automatically.

The RAG page now exposes the full operator path for retrieval setup:
- select the PostgreSQL connection for the RAG store
- select an explicit embedding provider from configured AI providers that support embeddings
- choose the embedding model, task type, dimensions, and batch size
- configure watch folders for text and multimodal ingestion

For multimodal retrieval, operators typically:
1. configure a provider such as Gemini on the `/agents` page with a valid API key or secret
2. verify the provider shows embedding capability and configured secret status
3. select that provider in `/rag` as the `Embedding Provider`
4. choose the embedding model and initialize or backfill the corpus

### 5. Create Your First Flow

Create a file at `my-project/sn.core-agent/fl/hello.lua` with the following content:

```lua
-- hello.lua: A simple greeting flow
-- This flow demonstrates the basic lifecycle functions.

function setup()
    -- setup() runs first. Use it for initialization.
    -- It is optional -- you can omit it entirely.
    ctx.log("info", "Setting up hello flow")
end

function main(params)
    -- main(params) is where your logic lives. This is the only required function.
    -- The ctx global provides logging, secrets, execution metadata, and more.
    -- The params argument is a Lua table containing trigger data passed to this execution.
    ctx.log("info", "Hello from Sentinel!")

    -- Access trigger parameters (passed as the params argument to main)
    local name = (params and params.name) or "World"

    -- Return a value -- it will be serialized to JSON and stored with the execution
    return { message = "Hello, " .. name .. "!", timestamp = sn.time.now() }
end

function cleanup()
    -- cleanup() runs after main() completes, whether it succeeded or failed.
    -- Use it to release resources, close connections, etc.
    ctx.log("info", "Cleaning up hello flow")
end

function failed(err)
    -- failed(err) runs ONLY if main() throws an error.
    -- Use it for error-specific handling (alerts, rollback, etc.).
    ctx.log("error", "Hello flow failed: " .. err)
end
```

If hot-reload is enabled in your `sentinel.yaml` (it is by default for new projects), the harness will detect the new file automatically. Otherwise, restart the harness.

### 6. Execute the Flow

**Via the REST API:**

```bash
curl -X POST http://localhost:8080/fl/sn-core-agent:hello/run \
  -H "Content-Type: application/json" \
  -d '{"name": "Alice"}'
```

The response will include an execution ID:

```json
{"ok": true, "eid": "exec_abc123", "fid": "sn-core-agent:hello", "st": "completed"}
```

**Via the Dashboard:**

1. Open `http://localhost:9090`
2. Navigate to the Flows section
3. Find `sn-core-agent:hello`
4. Enter parameters: `{"name": "Alice"}`
5. Click Run

### 7. View Execution Results

**Via the REST API:**

```bash
# Get execution details
curl http://localhost:8080/ex/exec_abc123

# Stream execution logs (Server-Sent Events)
curl http://localhost:8080/ex/exec_abc123/lg
```

**Via the Dashboard:**

Click on the execution in the Executions panel to see status, timing, logs, and the returned value.

---

## Core Concepts Deep Dive

Now that you have a running instance, let us explore each concept in detail.

### Flows

A flow is an executable Lua script that performs work. Flows are the fundamental unit of logic in Sentinel.

**Lifecycle functions:**

Every flow can define up to four functions. Only `main()` is required:

| Function | When It Runs | Required? | Typical Use |
|----------|-------------|-----------|-------------|
| `setup()` | First, before main | No | Initialize state, validate preconditions, acquire resources |
| `main()` | After setup | Yes | Core business logic |
| `cleanup()` | After main, always | No | Release resources, send completion notifications |
| `failed(err)` | Only if main errors | No | Error alerting, rollback, incident logging |

The execution order is: `setup()` then `main()` then `cleanup()`. If `main()` throws an error, `failed(err)` runs before `cleanup()`.

**The `ctx` global:**

Inside every flow, you have access to the `ctx` global object. It provides:

```lua
ctx.log(level, message)     -- Log a message ("info", "warn", "error", "debug")
ctx.get(key)                -- Reserved (not yet wired — always returns nil)
ctx.set(key, value)         -- Reserved (not yet wired — no-op)
ctx.secret(name)            -- Retrieve an encrypted secret from the vault
ctx.params                  -- Parsed request fields (webhook/manual triggers)
ctx.req                     -- HTTP request metadata (webhook/manual triggers)
ctx.execution_id            -- The unique ID of this execution
ctx.trigger_type            -- How this flow was triggered ("manual", "cron", "webhook", etc.)
```

**Sandbox restrictions:**

Flows run in a sandboxed Lua VM. You cannot access the filesystem directly, spawn processes, or use `os.execute()`. All external interaction goes through the Sentinel API (`sn.*` namespaces). This is a security feature -- it means a flow cannot compromise the host system.

**Auto-discovery:**

Flows are discovered automatically from `fl/` directories inside kits. The flow ID is derived from the kit directory and filename:

```
sn.core-agent/fl/hello.lua      --> Flow ID: sn-core-agent:hello
acme.billing/fl/invoice.lua     --> Flow ID: acme-billing:invoice
```

You do not need to register flows in `kit.yaml` or any configuration file. Just create the `.lua` file in the right directory.

### Kits

A kit is a self-contained directory that groups related logic, data, and UI together.

**Naming convention:**

Kit directories follow the `{namespace}.{name}` pattern:
- `sn.core-agent` -- namespace "sn" (Sentinel built-in), name "core-agent"
- `acme.billing` -- namespace "acme" (your organization), name "billing"
- `acme.notifications` -- namespace "acme", name "notifications"

The namespace helps avoid naming collisions when combining kits from different sources (your own, the marketplace, third parties).

**Directory structure:**

```
acme.billing/
  kit.yaml           # Kit manifest (name, description, version, dependencies)
  fl/                # Flows -- Lua scripts that do work
    invoice.lua
    invoice.lua.md   # Skill twin (auto-generated, AI context)
    payment.lua
    payment.lua.md
  cn/                # Connectors -- reusable service wrappers
    stripe.lua
  md/                # Modules -- shared Lua libraries
    currency.lua
  fm/                # Forms -- YAML-defined web forms
    new-invoice.yaml
  pg/                # Pages -- YAML-defined web UI pages
    dashboard.yaml
  tp/                # Trigger definitions (YAML)
    schedules.yaml
  pb/                # Public assets (CSS, JS, images)
    styles.css
  dd/                # Data definitions (schemas, seed data)
    schema.sql
```

Not every kit needs every subdirectory. A minimal kit is just a `kit.yaml` and one flow in `fl/`. The kit.yaml manifest looks like:

```yaml
name: billing
namespace: acme
description: Invoice and payment processing workflows
version: 1.0.0
```

Flows are auto-discovered from `fl/` -- you do NOT list them in kit.yaml.

### Triggers

Triggers define when and how a flow executes. There are five types:

**Cron triggers** run flows on a schedule using standard cron expressions:

```
Schedule: "0 2 * * *"  (daily at 2:00 AM)
Schedule: "*/5 * * * *" (every 5 minutes)
Schedule: "0 9 * * MON" (every Monday at 9:00 AM)
```

**Webhook triggers** expose an HTTP endpoint that external services can POST to. When Stripe, GitHub, or any service sends a webhook, Sentinel receives it and executes the linked flow with the payload as parameters:

```
Endpoint: /wh/stripe-payment
Method:   POST
Auth:     HMAC signature verification
```

**Event triggers** listen for internal events emitted by other flows. This enables flow-to-flow communication and event-driven architectures:

```
Pattern: "order.created"    (exact match)
Pattern: "order.*"          (wildcard -- any order event)
```

**Manual triggers** are the simplest: you call the API or click Run in the dashboard. Every flow supports manual execution regardless of other triggers.

**Form triggers** execute a flow when a user submits a web form defined in the kit's `fm/` directory.

### Executions

An execution is a single run of a flow. Every time a flow runs (whether by cron, webhook, manual invocation, or any other trigger), Sentinel creates an execution record with a unique ID.

**Execution lifecycle:**

```
queued --> running --> completed
                  \-> failed
```

**What gets tracked:**
- **Execution ID** -- unique identifier (e.g., `exec_abc123`)
- **Flow ID** -- which flow ran (e.g., `sn-core-agent:hello`)
- **Status** -- `queued`, `running`, `completed`, or `failed`
- **Start time** and **end time**
- **Trigger type** -- what caused the execution (manual, cron, webhook, event, form)
- **Logs** -- all `ctx.log()` output, stored and streamable via SSE
- **Return value** -- whatever `main()` returned, serialized to JSON
- **Error** -- if failed, the error message

Executions are stored in the SQLite state database at `.sentinel/state.db` and are queryable via the API.

### Secrets

Secrets are encrypted key-value pairs for storing sensitive data like API keys, passwords, and tokens.

**Storage:** Secrets live in `.sentinel/vault.db`, encrypted with AES-256-GCM. This file is gitignored -- secrets never enter version control.

**Setting secrets:**

```bash
# Via CLI
sentinel secret set stripe_api_key sk-live-abc123

# Via API
curl -X POST http://localhost:8080/sc/stripe_api_key \
  -H "Content-Type: application/json" \
  -d '{"value": "sk-live-abc123"}'
```

**Using secrets in flows:**

```lua
function main(params)
    local api_key = ctx.secret("stripe_api_key")
    -- Use the key for API calls
    local resp = sn.http.post("https://api.stripe.com/v1/charges", {
        headers = { Authorization = "Bearer " .. api_key },
        body = sn.json.enc({ amount = 2000, currency = "usd" })
    })
    return { status = resp.status }
end
```

### The Lua API

Inside flows, you have access to a rich set of APIs through the `ctx` and `sn` global namespaces:

| Namespace | Purpose | Examples |
|-----------|---------|---------|
| `ctx.*` | Execution context | `ctx.log()`, `ctx.secret()`, `ctx.params`, `ctx.req`, `ctx.execution_id` |
| `sn.http.*` | HTTP client | `sn.http.get(url, opts)`, `sn.http.post(url, opts)`, `sn.http.put()`, `sn.http.delete()` |
| `sn.ws.*` | WebSocket bus | `sn.ws.broadcast(channel, data)`, `sn.ws.send(client, data)` |
| `sn.db.*` | Kit-scoped SQLite | `sn.db.query(sql, params)`, `sn.db.exec(sql, params)` |
| `sn.json.*` | JSON encoding/decoding | `sn.json.enc(table)`, `sn.json.dec(string)` |
| `sn.crypto.*` | Cryptography | `sn.crypto.hmac(alg, key, data)`, `sn.crypto.sha256(data)` |
| `sn.time.*` | Time utilities | `sn.time.now()`, `sn.time.format()` |
| `sn.cms.*` | CMS content access | `sn.cms.list(collection)`, `sn.cms.get(collection, slug)` |
| `sn.sleep(n)` | Pause execution | `sn.sleep(5)` -- sleep 5 seconds (max 300) |
| `sn.md.*` | Built-in modules | AI helpers, session management, routing |
| `sn.cn.*` | Built-in connectors | HTTP, SMTP, file operations |
| `sentinel.emit()` | Event emission | `sentinel.emit("order.created", {id = 123})` |

See the [Lua API Reference](/lua-api) for complete documentation of every function.

### Skill Twins

Every code file in a kit automatically gets a paired `.md` file called a "skill twin." For example:

| Code File | Skill Twin |
|-----------|-----------|
| `fl/invoice.lua` | `fl/invoice.lua.md` |
| `cn/stripe.lua` | `cn/stripe.lua.md` |
| `kit.yaml` | `kit.yaml.md` |
| `fm/contact.yaml` | `fm/contact.yaml.md` |

**Why do skill twins exist?** They provide persistent, human-readable context that AI agents can read to understand the purpose, design decisions, usage patterns, and caveats of the associated code. When an AI agent is asked to modify `invoice.lua`, it can first read `invoice.lua.md` to understand what the flow does, what its dependencies are, and what patterns it follows.

Skill twins are auto-generated with a template when the code file is first created. You can (and should) enrich them with additional context over time. They are git-tracked alongside the code they describe.

---

## Directory Structure

After running `sentinel sre init`, your project looks like this (1:1 mode where repo root = SRE root):

```
repo-root/                          # Git repository root (where init runs)
  CLAUDE.md                         # AI assistant orientation (repo-level)
  .claude/skills/                   # SRE guidance skills (repo-level)
  .gitignore                        # Ignores .sentinel/ and _data/ (repo-level)
  .gitattributes                    # Line ending normalization (repo-level)

  sentinel.yaml                     # Project manifest (SRE-level, git-tracked)
                                    #   - name, description, version
                                    #   - git settings, hot-reload toggle
  .sentinel/                        # Machine-local state (gitignored)
    config.json                     #   - API port, log level, TLS settings
    vault.db                        #   - Encrypted secret storage (AES-256-GCM)
    state.db                        #   - Execution history, logs, audit trail
    cms.db                          #   - Markdown parse cache (bbolt; see docs/16-SENTINEL-DIRECTORY.md)
    certs/                          #   - TLS certificates (if configured)
    data/
      uploads/                      #   - Form file uploads
      sn.core.db                    #   - Per-kit SQLite database

  sn.core-agent/                    # Starter agent kit
  sn.core-rag/                      # Starter RAG kit
  sn.tools-http/                    # Starter tool connector kit
  sn.supervisor/                    # Starter supervisor kit
    kit.yaml                        #   Kit manifest
    kit.yaml.md                     #   Skill twin for manifest
    fl/                             #   Flows directory
      assistant.lua                 #     Example flow
      assistant.lua.md              #     Skill twin for the flow
    cn/                             #   Connectors directory (reusable service wrappers)
    md/                             #   Modules directory (shared Lua libraries)
    fm/                             #   Forms directory (YAML form definitions)
    pg/                             #   Pages directory (web UI definitions)
    pb/                             #   Public assets (CSS, JS, images)
    tp/                             #   Trigger definitions (YAML)
    dd/                             #   Data definitions (schemas, seed data)
```

For a **multi-SRE repo** (e.g., `sentinel sre init -p central --wp-central` then `sentinel sre init -p edge --wp-edge`):

```
repo-root/                          # Shared repo root
  CLAUDE.md                         # Repo-level (written once)
  .claude/skills/                   # Repo-level (written once)
  .gitignore                        # Repo-level (written once)
  .gitattributes                    # Repo-level (written once)

  central/                          # First SRE
    sentinel.yaml
    .sentinel/
    sn.wp-central/

  edge/                             # Second SRE
    sentinel.yaml
    .sentinel/
    sn.wp-edge/
```

Key observations:
- Repo-level files (CLAUDE.md, .gitignore, .gitattributes, .claude/skills/) live at the git repository root and are shared across all SREs in the repo. They are only written if they do not already exist.
- SRE-level files (sentinel.yaml, .sentinel/, kits) live in the SRE path specified by `-p` (defaults to `.` for 1:1 mode).
- Everything under `.sentinel/` is gitignored. It contains databases, secrets, and machine-specific configuration.
- Everything else is git-tracked. Your flows, kit manifests, forms, pages, and skill twins all live in version control.
- Kit directories are flat at the SRE root. There is no nested hierarchy -- kits sit side by side.
- Flow auto-discovery means you never need to register a flow anywhere. Just put a `.lua` file in a kit's `fl/` directory.

---

## Common First Tasks

### Create a New Kit

```bash
sentinel sre kit new --namespace acme --name billing --description "Billing and invoicing workflows"
```

This creates the `acme.billing/` directory with a `kit.yaml` manifest and the standard subdirectory structure. You can then start adding flows to `acme.billing/fl/`.

### Add a Cron-Triggered Flow

Create `sn.core-agent/fl/daily-report.lua`:

```lua
function main(params)
    ctx.log("info", "Generating daily report...")

    -- Query your kit database for today's data
    local rows = sn.db.query("SELECT count(*) as total FROM orders WHERE date = ?", {sn.time.now()})
    ctx.log("info", "Orders today: " .. rows[1].total)

    -- Send the report via HTTP
    local token = ctx.secret("slack_webhook_url")
    sn.http.post(token, {
        body = sn.json.enc({
            text = "Daily report: " .. rows[1].total .. " orders processed"
        })
    })

    return { orders = rows[1].total }
end
```

Then define the trigger directly in the flow using `triggers = { cron("0 8 * * *") }` (daily at 8 AM).

### Set Up a Webhook Receiver

Create `sn.core-agent/fl/github-webhook.lua`:

```lua
function main(params)
    local event_type = params.event
    local payload = params.payload and sn.json.dec(params.payload)

    ctx.log("info", "GitHub event received: " .. (event_type or "unknown"))

    if event_type == "push" then
        ctx.log("info", "Push to " .. (payload.ref or "unknown branch"))
        -- Trigger a deployment, send a notification, etc.
    end

    return { ok = true, event = event_type }
end
```

Register the webhook endpoint and test it:

```bash
# Test locally
curl -X POST http://localhost:8080/wh/github \
  -H "Content-Type: application/json" \
  -d '{"event": "push", "payload": {"ref": "refs/heads/main"}}'
```

### Create a Web Form

1. Define the form in `sn.core-agent/fm/feedback.yaml`:

```yaml
name: feedback
stub: user-feedback
fields:
  - name: email
    type: email
    label: Your Email
    required: true
  - name: rating
    type: select
    label: How would you rate us?
    options: ["Excellent", "Good", "Fair", "Poor"]
    required: true
  - name: comments
    type: textarea
    label: Additional Comments
    required: false
```

2. Create a flow that handles submissions in `sn.core-agent/fl/feedback-handler.lua`:

```lua
function main(params)
    local email = ctx.fm.feedback.email
    local rating = ctx.fm.feedback.rating
    local comments = ctx.fm.feedback.comments

    ctx.log("info", "Feedback received from " .. (email or "unknown"))

    -- Store in kit database
    sn.db.exec(
        "INSERT INTO feedback (email, rating, comments, created_at) VALUES (?, ?, ?, ?)",
        {email, rating, comments, sn.time.now()}
    )

    return { ok = true, message = "Thank you for your feedback!" }
end
```

3. Access the form at `http://localhost:8080/kt/sn/core-agent/fm/feedback`

---

## Next Steps

Now that you have a running Sentinel instance and understand the core concepts, here is where to go next depending on what you want to do:

| Goal | Read This |
|------|-----------|
| Learn the complete Lua API available inside flows | [Lua API Reference](/lua-api) |
| Build complex kits with forms, pages, and databases | [Kit Development Guide](/kit-development) |
| Master workflow patterns (webhooks, events, error handling) | [Workflows and Patterns](/workflows-and-patterns) |
| Understand all HTTP API endpoints for integration | [HTTP API Reference](/api-reference) |
| Configure security, TLS, and production deployment | [Configuration Guide](/configuration-guide) |
| Deploy to production with Cloudflare and Caddy | [Edge Deployment Guide](/edge-deployment) |
| Learn all CLI commands and flags | [CLI Reference](/cli-reference) |
| Set up automated testing and probes | [Adversarial Testing](/adversarial-testing) |
| Configure S3-compatible object storage | [Storage Points](/storage) |
| Install marketplace kits and manage licenses | [Licensing and Marketplace](/licensing) |
| Troubleshoot common issues | [Troubleshooting and FAQ](/troubleshooting-faq) |

---

## Architecture Diagram

```
                     Users / API Clients / AI Agents
                                  |
                                  v
                  +-------------------------------+
                  |       Dashboard UI            |
                  |    http://localhost:9090      |
                  |   (separate process, BFF)     |
                  +---------------+---------------+
                                  |
                             REST API
                                  |
                                  v
+----------------------------------------------------------------+
|                      Harness (Go binary)                        |
|                     http://localhost:8080                       |
|----------------------------------------------------------------|
|                                                                |
|  +--------------+  +------------------+  +------------------+  |
|  | Lua VM       |  | Trigger Engine   |  | Secret Vault     |  |
|  | - sandboxed  |  | - cron scheduler |  | - AES-256-GCM    |  |
|  | - per-flow   |  | - webhook server |  | - vault.db       |  |
|  | - pooled     |  | - event bus      |  +------------------+  |
|  +--------------+  | - form handler   |                        |
|                    +------------------+  +------------------+  |
|  +--------------+                        | Kit System       |  |
|  | State DB     |  +------------------+  | - auto-discovery |  |
|  | - SQLite     |  | WebSocket Bus    |  | - per-kit DB     |  |
|  | - executions |  | - real-time push |  | - hot-reload     |  |
|  | - logs       |  | - SSE fallback   |  +------------------+  |
|  | - audit      |  +------------------+                        |
|  +--------------+                        +------------------+  |
|                                          | Content Cache    |  |
|                                          | - CMS (bbolt)   |  |
|                                          +------------------+  |
+----------------------------------------------------------------+
                                  |
                    SRE Directory (git-tracked folder)
                                  |
              +-------------------+-------------------+
              |                   |                   |
         sn.core-agent/     acme.billing/       acme.blog/
         kit.yaml            kit.yaml            kit.yaml
         fl/ cn/ md/         fl/ cn/ md/         fl/ md/ pg/
         fm/ pg/ pb/         fm/                 fm/ pb/
```

**1:1 deployment model:** One harness instance serves exactly one SRE. If you need to run multiple projects, run multiple harness instances on different ports. This keeps things simple, isolated, and easy to reason about.

---

## Getting Help

- **Health check** -- `curl http://localhost:8080/hl` returns a structured status of all subsystems
- **CLI help** -- `sentinel --help` or `sentinel [command] --help` for any subcommand
- **Real-time logs** -- View in the dashboard or stream via `curl http://localhost:8080/ex/{id}/lg`
- **System specs** -- Machine-readable YAML files in `system-specs/` define every API, schema, and convention
- **Troubleshooting** -- See [Troubleshooting and FAQ](/troubleshooting-faq) for common issues and solutions
- **Documentation hub** -- Return to the [Documentation Index](/index) for the full list of guides

---

**You are ready to build.** Pick a guide from the Next Steps table above, or return to the [Documentation Index](/index) to find exactly what you need.
