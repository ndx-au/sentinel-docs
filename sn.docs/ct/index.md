---
title: "Sentinel Documentation"
description: "Sentinel uses one Go binary to discover, manage, and execute Lua workflows from a folder of plain files."
type: Overview
tags: [overview]
status: stable
---

<!-- ndx-ste-mode: description -->

# Sentinel Documentation

## What is Sentinel?

Sentinel is a **git-native orchestration harness**. A single Go binary discovers, manages, and executes Lua workflows from a folder of plain files.

> - **Git-Native:** Git tracks changes to the project files. You can audit those changes, restore earlier versions, and keep a remote copy.

> - **Orchestration:** Sentinel coordinates work across your IT systems. You control what runs, where it runs, and when it runs.

> - **Harness:** The harness provides tools that run and control workflows. Code or AI agents can direct these tools. Code defines repeatable processing. LLM output can vary for the same input.

> - **Lua:** Lua is the programming language for Sentinel workflows. It supports embedded use. Humans and AI agents can read and write the workflow code.

> - **Plain Files:** Humans can read and edit the files with a text editor. AI agents can work with the same files. Git can track changes to these files.

You can define automation in Lua, track it in Git, and run it without Redis, Celery, or Kubernetes.

The **harness** and the **SRE** have separate roles. The harness provides the runtime, API server, trigger engine, secret vault, and state database. The SRE (Sentinel Runtime Environment) contains kits, flows, connectors, modules, and configuration files. The harness reads the SRE and discovers its components. Git tracks the project files as the source of truth.

Sentinel provides context for AI agents. Each code file gets a paired `.md` skill twin. The HTTP API uses short endpoint prefixes to reduce token use: `/fl`, `/ex`, `/lg`, `/tr`, `/wh`. The runtime uses a single binary and an SRE folder.

---

## Documentation Roadmap

### New Users

If you are encountering Sentinel for the first time, start here and read in order:

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| 1 | [Getting Started](/getting-started) | 15 min | What Sentinel is, how to install it, create your first project, write and run a flow, understand core concepts |

### Flow Developers

For anyone writing Lua flows, building kits, or designing workflow automations:

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| 2 | [Lua API Reference](/lua-api) | 30 min | Complete API reference for Lua flows -- context object, HTTP client, WebSocket bus, database access, cryptography, JSON, time utilities, CMS content access, built-in modules and connectors |
|  | [Agentic AI operator guide](/agentic-ai-operator) | 20 min | Vault + API Library + Agents validate/release + `sn.ai.chat` flow smoke + traces. Canary/rollback semantics |
|  | [Agentic AI UAT trail](/agentic-ai-uat) | 60 min | Hands-on acceptance checklist with sample data. Sandbox SRE at `../SRE/agentic-uat` |
|  | [RAG retrieval evaluation](/rag-evaluation) | 10 min | Fixture CI gate (`go test ./internal/rag`), dashboard eval summary, tool-loop error golden fixtures |
|  | [AI provider extension](/ai-provider-extension) | 15 min | Add Go runtime adapters, defer table, `adapter_status` dashboard fields, validation probes |
| 3 | [Kit Development Guide](/kit-development) | 45 min | Creating kits with flows, forms, pages, and UIs. Kit.yaml manifest. Databases and assets. Skill twins for AI context |
| 4 | [Workflows and Patterns](/workflows-and-patterns) | 30 min | Common workflow patterns, webhook handling, event cascades, error handling strategies, testing approaches |
| 5 | [Triple-Access Pattern](/triple-access-pattern) | 45 min | Building services accessible through CLI, REST API, and Lua simultaneously. Architecture layering. Agent optimization |

### API Integrators

For developers building external integrations against the Sentinel HTTP API:

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| 6 | [HTTP API Reference](/api-reference) | 45 min | All REST endpoints, authentication, flow execution, execution history and logs, trigger management, forms, secrets, webhooks, git operations, error codes |
|  | [Harness HTTP routes](/harness-http-routes) | 10 min | Canonical `/hl/*`, `/kt/*`, gateway/keyhole behavior, dashboard proxy mapping — complements `system-specs/api.yaml` |
|  | [MCP Agent Integration](/mcp-agent-integration) | 15 min | Connect Cursor and other MCP clients to a running harness. Bind/listen flags, tools, debugging |
|  | [The `.sentinel/` directory](/sentinel-directory) | 15 min | Gitignored harness artifacts — what each file is, what depends on it, backup/restore notes |
|  | [fcms — file CMS (operator guide)](/sentinel-cms) | 25 min | **fcms** plane: `ct/` content, `/fcms` JSON (legacy `/cm`), `/fcms/render` HTML (legacy `/ct`), `cms.db` |
|  | [Content planes (fcms / ccms / wpcms)](/content-planes) | 20 min | Pluralistic content model, Graphile **1880**, `dd/` migrations, dashboard Collections, ports |

### Content planes (roadmap)

| Plane | Guide | Notes |
|-------|-------|--------|
| **fcms** | [17-SENTINEL-CMS.md](/sentinel-cms) | File CMS — technical writing, agent docs |
| **ccms** | [24-CONTENT-PLANES.md](/content-planes) | Collection CMS — Postgres + Graphile. Collections dashboard |
| **wpcms** | [14-WORDPRESS.md](/wordpress) | WordPress platform — dedicated ingress port |

### System Administrators

For anyone deploying, configuring, securing, or monitoring Sentinel in production:

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| 7 | [Configuration Guide](/configuration-guide) | 30 min | Two-layer configuration system, sentinel.yaml and .sentinel/config.json schemas, environment variables, three security layers, deployment checklist, performance tuning |
| 8 | [Edge Deployment Guide](/edge-deployment) | 15 min | Cloudflare + Caddy + Sentinel architecture, Full (Strict) SSL, Caddyfile reverse proxy, production deployment checklist |

### CLI Users

For managing Sentinel entirely from the command line:

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| 9 | [CLI Reference](/cli-reference) | 20 min | All CLI commands and flags, configuration management, secret management, database operations, kit and flow commands |

### QA and Testing Engineers

For building and running automated test suites against Sentinel:

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| 10 | [Adversarial Testing and Probe Runner](/adversarial-testing) | 20 min | Probe runner CLI with structured JSONL output, 8 probe categories, activity simulator, AI-driven test-debug-fix cycles, CI/CD integration |

### Storage and Media

For configuring S3-compatible object storage and CMS media management:

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| 11 | [Storage Points](/storage) | 15 min | S3-compatible object storage (AWS S3, Backblaze B2, Garage), stub-based CMS URL expansion, backup upload destinations, provider configuration, dashboard walkthrough |

### Docker and Local Service Management

For operators using Docker-backed compose stacks or running Sentinel inside containers:

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| 13 | [Docker and Container Deployment](/docker-and-containers) | 15 min | Docker detection, feature availability, generated PostgreSQL, container deployment, and Docker socket privileges |

### WordPress Operators

For operators running the managed WordPress control-plane kit:

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| 14 | [WordPress with sn.wp-central](/wordpress) | 10 min | Local `wp-central` bootstrap, managed stack startup, first-run WordPress install, dedicated integration user creation, Application Password generation, and storing WordPress credentials in the Sentinel vault |

### Marketplace and Licensing

For managing licenses, installing marketplace kits, and understanding DRM:

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| 12 | [Licensing and occupy](/licensing) | 20 min | CE/Enterprise, occupy leases, prepaid slots, cloudless org-license, SMTP notices |
|  | [NDX Trust / SOC2](/ndx-trust-soc2) | 15 min | NDX Pty Ltd Type II program vs harness SOC2-ready controls |

### Troubleshooting

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| -- | [Troubleshooting and FAQ](/troubleshooting-faq) | 10 min | Common issues and their solutions, diagnostic steps |

---

## "I want to..." Quick Links

These task-oriented links take you directly to the section you need:

**Getting started and basics:**
- **Get started in 5 minutes** -- [Quick Start](/getting-started#quick-start-5-minutes).
- **Write my first flow** -- [Getting Started: Create Your First Flow](/getting-started#4-create-your-first-flow).
- **Understand core concepts** -- [Getting Started: Core Concepts Deep Dive](/getting-started#core-concepts-deep-dive).

**Building flows and kits:**
- **Learn the Lua API** -- [Lua API Reference](/lua-api).
- **Build a webhook receiver** -- [Workflows: Webhook Patterns](/workflows-and-patterns#webhook-patterns).
- **Schedule a cron job** -- [Workflows: Cron Patterns](/workflows-and-patterns#cron-patterns).
- **Create a web form** -- [Kit Development: Forms](/kit-development#forms-fm).
- **Call an external API** -- [Lua API: HTTP Client](/lua-api#http-client-snhttp).
- **Store data in a database** -- [Lua API: Database](/lua-api#database-sndb).
- **Build a CMS/blog kit** -- [Kit Development: CMS Kits](/kit-development#cms-kits).
- **Run or proxy a CMS site (`/cm`, `/ct`)** -- [Sentinel CMS operator guide](/sentinel-cms).
- **Query CMS content from a flow** -- [Lua API: CMS](/lua-api#cms-sncms).
- **Use WebSockets from a flow** -- [Lua API: WebSocket Bus](/lua-api#websocket-bus-snws).
- **Push real-time updates to the dashboard** -- [API Reference: WebSocket](/api-reference#websocket).
- **Build a reusable service layer** -- [Triple-Access Pattern](/triple-access-pattern).

**Operations and deployment:**
- **Deploy to production** -- [Edge Deployment Guide](/edge-deployment) or [Configuration: Deployment Checklist](/configuration-guide#deployment-checklist).
- **Secure my instance** -- [Configuration: Security](/configuration-guide#security-configuration).
- **Run managed WordPress behind Sentinel** -- [WordPress with sn.wp-central](/wordpress).
- **Debug a failed flow** -- [CLI: Viewing Logs](/cli-reference#flow-logs) or [Troubleshooting](/troubleshooting-faq).
- **Configure S3/B2/Garage storage** -- [Storage Points](/storage).
- **Understand Docker-backed stack management** -- [Docker and Container Deployment](/docker-and-containers).
- **Run Sentinel in a container with or without Docker socket access** -- [Docker and Container Deployment](/docker-and-containers).

**Harness development:**
- **Understand harness code architecture** -- [Harness Internals](/internals).
- **Trace bootstrap and subsystem wiring** -- [Harness Internals: Bootstrap](/internals#bootstrap-sequence).
- **Find the right internal package** -- [Harness Internals: Package map](/internals#package-map).

**Testing and quality:**
- **Test and find bugs autonomously** -- [Adversarial Testing and Probe Runner](/adversarial-testing).
- **Run probes against my harness** -- [Adversarial Testing: Quick Start](/adversarial-testing#quick-start).
- **Integrate probes into CI/CD** -- [Adversarial Testing: CI/CD](/adversarial-testing#integration-with-cicd).

**Marketplace and licensing:**
- **Install marketplace kits** -- [CLI Reference: Marketplace](/cli-reference#marketplace-commands).
- **Install bootstrap bundles** -- [CLI Reference: Bundle Install](/cli-reference#bundle-install).
- **Activate a license** -- [Licensing: Issue and Activate](/licensing#issuing-a-license).
- **Configure marketplace** -- [Configuration Guide: Marketplace](/configuration-guide#marketplace).
- **Understand occupy licensing** -- [Licensing](/licensing).
- **Set up OAuth for SKM** -- OAuth Setup Requirements.

---

## Architecture Overview

Sentinel follows a **1:1 deployment model**. One harness instance runs one SRE project. The harness does not provide a mode for multiple tenants, a shared worker pool, or a message broker.

```
                    Browser / API Client / AI Agent
                                |
                                v
                 +------------------------------+
                 |    Dashboard UI              |
                 |    (standalone process)      |
                 |    http://localhost:9090     |
                 |    BFF proxy to harness      |
                 +-------------+----------------+
                               |
                          REST API
                               |
                               v
+--------------------------------------------------------------+
|                    Harness (Go binary)                        |
|                    http://localhost:8080                      |
|--------------------------------------------------------------|
|                                                              |
|  +------------+  +----------------+  +-------------------+   |
|  | Lua VM     |  | Trigger Engine |  | Secret Vault      |   |
|  | (sandboxed |  | - Cron         |  | (AES-256-GCM)     |   |
|  |  flow exec)|  | - Webhook      |  | .sentinel/vault.db|   |
|  +------------+  | - Event        |  +-------------------+   |
|                  | - Form         |                          |
|  +------------+  | - Manual       |  +-------------------+   |
|  | State DB   |  +----------------+  | Kit System        |   |
|  | (SQLite)   |                      | (auto-discovery)  |   |
|  | executions |  +----------------+  +-------------------+   |
|  | logs, audit|  | WebSocket Bus  |                          |
|  +------------+  | (real-time)    |  +-------------------+   |
|                  +----------------+  | Content Cache     |   |
|                                      | (CMS, bbolt)      |   |
|                                      +-------------------+   |
+--------------------------------------------------------------+
                               |
                     SRE Directory (git-tracked)
                               |
         +---------------------+---------------------+
         |                     |                     |
    sn.core-agent/        acme.billing/         acme.blog/
    (starter kit)         (your kit)            (CMS kit)
```

**Key points about this architecture:**

- The **Dashboard** is a separate process that proxies requests to the harness. It provides a web UI for managing flows, viewing executions, browsing kits, and editing files. It runs on port 9090 by default.
- The **Harness** is the core engine running on port 8080 by default. It hosts the REST API, executes Lua flows in a sandboxed VM, manages triggers, and handles all state.
- The **SRE directory** is just a folder on disk. The harness reads it, discovers kits and flows automatically, and watches for changes when hot-reload is enabled.
- **No external dependencies.** The harness embeds SQLite for state and bbolt for caching. It also embeds an encrypted vault and a Lua VM.

---

## Harness Contributors

For engineers modifying the Go harness (`internal/*`, `cmd/sentinel/*`):

| # | Document | Time | What You Will Learn |
|---|----------|------|---------------------|
| 20 | [Harness Internals](/internals) | 45 min | Bootstrap wiring, package map, flow execution path, gateway middleware, kit discovery, hot reload, build/test conventions |

The code is the source of truth. This document lists the key files and subsystems. [Harness HTTP Routes](/harness-http-routes) and `system-specs/api.yaml` contain the API route catalogs.

---

## Core Concepts Quick Reference

These are the fundamental building blocks of every Sentinel project. Each is explained in depth in the [Getting Started guide](/getting-started#core-concepts-deep-dive).

| Concept | What It Is |
|---------|-----------|
| **SRE** (Sentinel Runtime Environment) | The project folder containing all your kits, configuration, and state. One SRE = one project. It is the unit of deployment and the root of your git repository. |
| **Flow** | A Lua script that performs work. Flows have a lifecycle of `setup()`, `main()`, `cleanup()`, and `failed(err)` functions. They run in a sandboxed VM with access to the Sentinel API. Discovered automatically from `fl/` directories inside kits. |
| **Kit** | A self-contained module directory (for example `sn.core-agent/`, `acme.billing/`) with a `kit.yaml` manifest. Kits contain flows, connectors, modules, forms, pages, databases, and assets. They are the unit of organization and reuse. |
| **Trigger** | A rule that causes a flow to execute. Five types: **cron** (schedule), **webhook** (HTTP POST), **event** (internal message), **manual** (API/dashboard), and **form** (user submission). Defined in YAML files inside `tp/` directories. |
| **Execution** | A single run of a flow, identified by an execution ID. Tracks status (`queued`, `running`, `completed`, `failed`), timing, logs, return value, and errors. |
| **Secret** | An encrypted key-value pair stored in the vault (`.sentinel/vault.db`). Used for API keys, passwords, tokens, and other sensitive data. Encrypted with AES-256-GCM. |
| **Connector** | A reusable Lua module that wraps an external service or protocol (for example HTTP, SMTP, file I/O). Lives in `cn/` directories inside kits. |
| **Module** | A reusable Lua module that provides shared logic (for example AI helpers, session management). Lives in `md/` directories inside kits. |
| **Skill Twin** | A `.md` file automatically paired with every code file (for example `flow.lua` gets `flow.lua.md`). Skill twins provide persistent context that helps AI agents understand the purpose, decisions, and patterns of the associated code. |

---

## Two-Layer Configuration

Sentinel uses two configuration files. This separation keeps infrastructure secrets out of Git. Project behavior stays in version control.

| File | Location | Git-tracked? | Contains |
|------|----------|-------------|----------|
| `sentinel.yaml` | SRE root | Yes | Project identity: `name`, `description`, `version`, `git` configuration, `hotreload` toggle. This is your project's public configuration. |
| `.sentinel/config.json` | `.sentinel/` directory | No (gitignored) | Machine-specific infrastructure: `api.port`, `log.level`, `tls.*` configuration, `marketplace.*` credentials. This varies per deployment. |

**Rule of thumb:** If a setting changes between machines (ports, paths, credentials), it goes in `.sentinel/config.json`. If it defines project behavior (name, version, features), it goes in `sentinel.yaml`.

See the [Configuration Guide](/configuration-guide) for complete schemas and examples.

---

## Security

Sentinel implements **three independent security layers** that can be enabled individually or together:

1. **Authentication** -- Bearer token protection for API endpoints.
2. **Encryption at Rest** -- SQLCipher for the state database, AES-256-GCM for the secret vault.
3. **Transport Encryption** -- Native TLS/SSL support or reverse proxy through Caddy/nginx.

See [Configuration Guide: Security](/configuration-guide#security-configuration) for setup instructions and [Edge Deployment](/edge-deployment) for production TLS architecture.

---

## System Specifications

Machine-readable YAML specification files live in the `system-specs/` directory at the repository root. These are authoritative and designed for code generation, tooling, and AI consumption.

| Spec File | What It Defines |
|-----------|----------------|
| `api.yaml` | All HTTP endpoints, request/response shapes, query parameters |
| `lua-api.yaml` | Complete Lua API surface available inside flows |
| `kits.yaml` | Kit directory structure and kit.yaml manifest schema |
| `forms.yaml` | Form YAML definitions, field types, and submission events |
| `triggers.yaml` | Trigger types, configuration options, and scheduling rules |
| `cli-commands.yaml` | CLI commands, subcommands, flags, and arguments |
| `config.yaml` | Configuration schemas for both sentinel.yaml and config.json |
| `security.yaml` | Authentication, encryption, TLS, and audit logging specs |
| `errors.yaml` | All error codes, messages, and HTTP response shapes |
| `file-structure.yaml` | Project layout conventions and directory purposes |
| `connectors.yaml` | Built-in connector APIs and extension points |
| `modules.yaml` | Built-in module APIs and extension points |
| `logging.yaml` | Logging system configuration and output formats |
| `docker.yaml` | Docker integration and container management |
| `README.yaml` | Spec directory metadata and index |

---

## Getting Help

- **System health** -- `curl http://localhost:8080/hl` returns a structured health check of all subsystems.
- **Real-time logs** -- View execution logs through the dashboard or the `/ex/{id}/lg` SSE endpoint.
- **CLI help** -- `sentinel --help` or `sentinel [command] --help` for any command.
- **Error codes** -- See [API Reference: Error Codes](/api-reference#error-codes) for a complete list.
- **Troubleshooting** -- See [Troubleshooting and FAQ](/troubleshooting-faq) for common issues.
- **Specifications** -- Parse `system-specs/*.yaml` for authoritative, machine-readable definitions.
- **Version** -- Run `sentinel version` to check your installed version.

---

## Additional Resources

| Resource | Purpose |
|----------|---------|
| `sre4agents.md` | Full SRE development reference for AI agents |
| `sre-url-map.md` | URL construction cheat sheet with complete routing table |
| `docs/20-INTERNALS.md` | Harness Go code architecture (contributors) |
| `system-specs/` | Machine-readable YAML specifications (authoritative) |

---

Current documentation version: **Sentinel v0.3.1+**

**Ready to build?** Start with the [Getting Started guide](/getting-started), or jump to a specific task using the quick links above.
