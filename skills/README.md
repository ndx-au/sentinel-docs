# Sentinel Agent Skills Library

The canonical public library of **Agent Skills** (`SKILL.md` packages) for working with **Sentinel** — building Sentinel Runtime Environments (SREs), authoring kits and Lua flows, and orchestrating any business domain through Sentinel's MCP server, HTTP API, webhooks, triggers, and CLI.

> **Public & Self-Contained:** Every skill in this directory is safe for public use and references only public Sentinel documentation at [docs.ndx-sentinel.com](https://docs.ndx-sentinel.com).

---

## Taxonomy: `sre-*` vs `sn-*`

Skills use two prefixes to separate SRE-level authoring from platform-wide orchestration:

| Prefix | Scope | Examples |
|---|---|---|
| `sre-*` | **Sentinel Runtime Environment** — authoring kits, flows, connectors, modules, triggers, forms, pages, content planes (`fcms`/`ccms`/`wpcms`), SRE config, and procedural tasks backed by Sentinel kits. | `sre-kit-author`, `sre-backup-monitor`, `sre-cms-publisher` |
| `sn-*` | **Sentinel Platform** — meta-skills, invoking/observing a running harness via MCP, HTTP API, or webhooks, CLI operations, and cross-domain business orchestration. | `sn-skill-creator`, `sn-harness-ops`, `sn-webhook-triage` |

### Agent Skills vs. SRE Skill Twins

Sentinel has two complementary concepts — keep them distinct:

- **Agent Skills (`skills/<name>/SKILL.md`)** live in this repository (or in an agent harness's skills directory). They teach AI agents *how* to perform multi-step workflows, invoke Sentinel, and design kits.
- **SRE Skill Twins (`*.lua.md`, `kit.yaml.md`)** live inside a Sentinel SRE next to each code file. They are auto-spawned by the harness to store file-specific context, decisions, and notes alongside that code.

### Relationship to `sre-init`

- **`sentinel-docs/skills/`** (this directory) is the **canonical public Agent Skills library** for installing Sentinel skills into any AI coding harness.
- **`ndx-au/sre-init`** focuses on starter kits, bundles, and optional SRE-embedded skills copied during `sentinel sre init --with-bundle`.

---

## Available Skills

This catalog mirrors [`manifest.yaml`](./manifest.yaml).

| Skill | Prefix | Status | Purpose |
|---|---|---|---|
| [`sn-skill-creator`](./sn-skill-creator/SKILL.md) | `sn-` | `stable` | Sentinel-specific meta-skill for creating new `sre-*` and `sn-*` skills that pair agent judgment with deterministic Sentinel kits, triggers, MCP, HTTP API, and webhooks. |
| [`sn-harness-deploy`](./sn-harness-deploy/SKILL.md) | `sn-` | `stable` | Bring a harness online and verify its listener, kit inventory, and workload. |
| [`sre-kit-release`](./sre-kit-release/SKILL.md) | `sre-` | `stable` | Validate, test, promote, and verify a kit revision with a rollback path. |
| [`sn-execution-triage`](./sn-execution-triage/SKILL.md) | `sn-` | `stable` | Trace a missing or failed execution and reconcile uncertain submissions. |
| [`sn-kit-db-recovery`](./sn-kit-db-recovery/SKILL.md) | `sn-` | `stable` | Back up kit SQLite data and verify a restore in an offline SRE. |

---

## Installation

All skills follow the standard `SKILL.md` Agent Skills layout (a required `SKILL.md` with optional references and templates), compatible with Antigravity, Claude Code, Cursor, Codex, OpenCode, and `npx skills`.

### Using `npx skills` (if installed)

```bash
npx skills add ndx-au/sentinel-docs --skill sn-skill-creator
```

### Manual Copy into Any Harness

Clone this repository and copy the desired skill folder(s) into your harness's skills directory:

| Harness | Project-Scoped Path | Global Path |
|---|---|---|
| Antigravity | `.agents/skills/<skill-name>/` | `~/.gemini/config/skills/<skill-name>/` |
| Claude Code | `.claude/skills/<skill-name>/` | `~/.claude/skills/<skill-name>/` |
| Cursor | `.cursor/skills/<skill-name>/` | `~/.cursor/skills/<skill-name>/` |
| Codex | `.agents/skills/<skill-name>/` | `~/.agents/skills/<skill-name>/` |
| OpenCode | `.opencode/skills/<skill-name>/` | `~/.config/opencode/skills/<skill-name>/` |

Example:

```bash
git clone https://github.com/ndx-au/sentinel-docs.git
mkdir -p /path/to/your-project/.agents/skills
cp -r sentinel-docs/skills/sn-skill-creator /path/to/your-project/.agents/skills/
```

---

## Adding or Evolving Skills

This library is designed for continuous evolution:

1. **Use `sn-skill-creator`** to design and scaffold new `sre-*` or `sn-*` skills.
2. **Follow progressive disclosure**: keep `SKILL.md` focused and concise (under ~500 lines); place detailed references in `references/` and starter files in `templates/`.
3. **Register the skill** in [`skills/manifest.yaml`](./manifest.yaml) and add a row to the table above.
4. **Validate before committing**:

```bash
python3 tools/validate_skills.py
```

The validator checks frontmatter, naming prefixes (`sre-*` / `sn-*`), relative links, manifest sync, and public-safety rules (blocking private paths, staging hosts, and hardcoded credentials).
