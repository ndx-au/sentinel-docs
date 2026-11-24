---
title: "Agent Skills Library"
description: "Install and create public Sentinel Agent Skills (sre-* and sn-*) that pair AI agent workflows with deterministic Sentinel kits, MCP, HTTP API, and webhooks."
type: Guide
tags: [agents, skills, mcp]
status: stable
---

<!-- ndx-ste-mode: description -->

# Agent Skills Library

Sentinel ships a public library of **Agent Skills** (`SKILL.md` packages) in the [`sentinel-docs` repository (`skills/`)](https://github.com/ndx-au/sentinel-docs/tree/main/skills). Any AI coding harness that supports the standard `SKILL.md` format — including Antigravity, Claude Code, Cursor, Codex, and OpenCode — can install and activate these skills on demand.

---

## Why Sentinel-Specific Skills?

Generic agent skills rely on ad-hoc shell scripts or repeated prompt instructions. Sentinel skills split work cleanly between **agent judgment** and **deterministic Sentinel execution**:

- **The Agent Skill (`SKILL.md` + `references/`)** teaches the agent when to activate, what inputs to gather, how to invoke Sentinel, and how to inspect results, logs, and traces.
- **The Sentinel SRE Layer (Kits, Flows, Triggers, Vault)** performs repeatable procedural work in sandboxed Lua, stores credentials in the encrypted vault, enforces execution policies and operator approvals, and exposes triggers over **MCP**, **HTTP API**, and **Webhooks**.

---

## Naming Taxonomy: `sre-*` vs `sn-*`

Skills use two prefixes so agents and operators can immediately tell whether a skill edits SRE files or orchestrates a running harness:

| Prefix | Scope | Examples |
|---|---|---|
| `sre-*` | **Sentinel Runtime Environment** — authoring kits, flows, connectors, modules, triggers, forms, content planes (`fcms`/`ccms`/`wpcms`), and kit-backed procedural automation. | `sre-kit-author`, `sre-backup-monitor` |
| `sn-*` | **Sentinel Platform** — meta-skills, invoking/observing a running harness via MCP, HTTP API, or webhooks, CLI operations, and cross-domain business orchestration. | `sn-skill-creator`, `sn-webhook-triage` |

### Agent Skills vs. SRE Skill Twins

- **Agent Skills (`skills/<name>/SKILL.md`)** are reusable cross-harness instruction packages installed into your AI agent harness.
- **SRE Skill Twins (`*.lua.md`, `kit.yaml.md`)** are per-file Markdown companions auto-spawned by the harness inside an SRE to store persistent context alongside code files.

### Relationship to `sre-init`

- **`ndx-au/sentinel-docs` (`skills/`)** is the canonical public Agent Skills library for installing skills into any AI harness.
- **`ndx-au/sre-init`** provides starter kits, bundles, and optional SRE-embedded skills copied when running `sentinel sre init --with-bundle`.

---

## Skills for operators

| When you need to… | Install this skill |
|---|---|
| Bring a new host or an existing SRE online. | [`sn-harness-deploy`](https://github.com/ndx-au/sentinel-docs/tree/main/skills/sn-harness-deploy) |
| Roll out a kit revision or recover from a failed rollout. | [`sre-kit-release`](https://github.com/ndx-au/sentinel-docs/tree/main/skills/sre-kit-release) |
| Find out whether a timed-out request ran and what it changed. | [`sn-execution-triage`](https://github.com/ndx-au/sentinel-docs/tree/main/skills/sn-execution-triage) |
| Prove a kit SQLite backup can restore the expected data. | [`sn-kit-db-recovery`](https://github.com/ndx-au/sentinel-docs/tree/main/skills/sn-kit-db-recovery) |

Use the skill name in the installation command below.

## The Meta-Skill: `sn-skill-creator`

The foundational skill in the library is **`sn-skill-creator`** (`skills/sn-skill-creator/SKILL.md`). Use it to design and scaffold new `sre-*` or `sn-*` skills on demand for any problem domain.

`sn-skill-creator` guides an agent through:

1. **Discovering the live Sentinel environment** — reading MCP resources (`sentinel://kits`, `sentinel://flows`, `sentinel://harness/status`) or inspecting local SRE files.
2. **Splitting judgment from procedural work** — deciding what stays in `SKILL.md` versus what becomes a kit (`fl/`, `cn/`, `md/`, `fm/`, `events.yaml`).
3. **Selecting the invocation surface** — MCP (`flow_run`, `event_emit`), HTTP API (`POST /fl/{ns}.{name}/{flow}/run`, `GET /ex/{id}`, `GET /ex/{id}/lg`), Webhooks (`/wh/*`), Triggers (`cron`, `webhook`, `event`, `form`), or CLI (`sentinel sre flow run`).
4. **Enforcing security & public-safety boundaries** — vault-only secrets (`ctx.secret`), `.sentinel/execution-policy.json` and `sentinel approvals`, least-privilege MCP risk classes, and zero leakage of internal operational details.
5. **Validating & testing** — running `sentinel sre validate`, `sentinel sre test`, and `python3 tools/validate_skills.py`.

---

## Installation

### Using `npx skills`

```bash
npx skills add ndx-au/sentinel-docs --skill sn-skill-creator
```

### Manual Installation

Clone `sentinel-docs` and copy the skill folder into your harness's skills directory:

| Harness | Project-Scoped Path | Global Path |
|---|---|---|
| Antigravity | `.agents/skills/<skill-name>/` | `~/.gemini/config/skills/<skill-name>/` |
| Claude Code | `.claude/skills/<skill-name>/` | `~/.claude/skills/<skill-name>/` |
| Cursor | `.cursor/skills/<skill-name>/` | `~/.cursor/skills/<skill-name>/` |
| Codex | `.agents/skills/<skill-name>/` | `~/.agents/skills/<skill-name>/` |
| OpenCode | `.opencode/skills/<skill-name>/` | `~/.config/opencode/skills/<skill-name>/` |

```bash
git clone https://github.com/ndx-au/sentinel-docs.git
mkdir -p /path/to/your-project/.agents/skills
cp -r sentinel-docs/skills/sn-skill-creator /path/to/your-project/.agents/skills/
```

---

## Contributing & Validating Skills

When adding or updating a skill in `sentinel-docs/skills/`:

1. Follow the `sre-*` or `sn-*` naming prefix and keep `SKILL.md` concise (delegate bulky reference material to `references/`).
2. Register the skill in `skills/manifest.yaml` and `skills/README.md`.
3. Run the automated validator and public-safety linter:

```bash
python3 tools/validate_skills.py
```

---

## Related Docs

- [MCP Agent Integration](/mcp-agent-integration) — connect AI agents to a running harness over streamable HTTP or stdio.
- [Kit Development Guide](/kit-development) — kit structure, flows, connectors, modules, forms, and skill twins.
- [Security Readiness](/security-readiness) — execution policies, operator approvals, FS Control, and MCP credential audiences.
- [HTTP API Reference](/api-reference) — brevity endpoints, authentication, and SSE log streaming.
