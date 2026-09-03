---
title: "Agentic AI — operator guide"
description: "End-to-end path for enabling LLM flows in an SRE: API Library + Vault → Agents validate → release controls → flow (sn.ai.chat) → trace in dashboard."
type: Playbook
tags: [ai]
status: stable
---

# Agentic AI — operator guide

End-to-end path for enabling LLM flows in an SRE: **API Library + Vault → Agents validate → release controls → flow (`sn.ai.chat`) → trace in dashboard**.

Architecture reference: [`specs/agentic-ai.md`](https://github.com/ndx-au/sentinel/blob/main/specs/agentic-ai.md). Lua API details: [`02-LUA-API.md`](/lua-api) (AI / Memory / RAG sections).

Harness regression: `go test ./internal/api -run TestAgenticAIOperatorPath` exercises this chain with a mock provider (no live API key required).

---

## Prerequisites

- Harness built and pointed at an SRE: `sentinel -p /path/to/sre`
- Dashboard reachable (default proxy: `http://localhost:9090` when using `sentinel dashboard start`)
- An API key for a supported provider (`openai`, `anthropic`, or `gemini` adapters ship in the harness)
- Starter kits installed: `sentinel sre init --with-bundle core` (from [ndx-video/sre-init](https://github.com/ndx-au/sre-init) or `--with-local ../sre-init`)

The **core** bundle includes `sn.core-agent` with `sn.md.agent.run` (persona + memory + optional RAG + `sn.ai.chat`) and the `sn-core-agent:assistant` flow. The **examples** bundle adds `sn.eg-support` / `sn.eg-rag-chat` flows that call `sn.ai.chat` directly. Install **examples** for additional chat smoke patterns:

```bash
sentinel sre init my-project --with-bundle core
sentinel sre bundle install examples
```

---

## 1. Store the provider key (Vault)

Never put API keys in API Library records or `sentinel.yaml`. Use the vault:

**Dashboard:** Secrets page → create secret (e.g. `openai_api_key`).

**CLI:**

```bash
sentinel -p my-project secret set openai_api_key
# paste key at prompt
```

**HTTP:** `POST /sc` with `{ "name": "openai_api_key", "value": "sk-..." }`.

---

## 2. Register an AI-capable vendor (API Library)

Create or edit a vendor with `meta.capabilities.ai = true`, a `meta.auth.secret_ref` pointing at the vault entry, and `meta.runtime` routing fields.

**Dashboard:** API Library → New vendor → enable AI capability → set secret ref → set runtime provider + default model.

**Minimal vendor meta (OpenAI example):**

```json
{
  "capabilities": { "ai": true, "chat": true },
  "auth": { "secret_ref": "openai_api_key" },
  "runtime": {
    "provider": "openai",
    "default_model": "gpt-4o-mini",
    "allowed_models": ["gpt-4o-mini", "gpt-4o"]
  }
}
```

**OpenRouter example** (slashy model slugs; keep `provider` set so the slug is not split on `/`):

```json
{
  "capabilities": { "ai": true, "chat": true },
  "auth": { "secret_ref": "openrouter_api_key" },
  "runtime": {
    "provider": "openrouter",
    "default_model": "openai/gpt-4o-mini",
    "allowed_models": ["openai/gpt-4o-mini", "google/gemini-2.0-flash"]
  }
}
```

**HTTP:** `POST /lib` with vendor body, or `PUT /lib/{id}` to update.

On harness start, `BuildClientFromLibrary` registers providers from these records. Flows call `sn.ai` — not raw HTTP connectors.

---

## 3. Validate credentials (Agents → Providers)

**Dashboard:** Agents (`/agents`) → **Providers** tab → select vendor → **Validate**.

**HTTP:** `POST /lib/{vendor_id}/validate`

A successful probe stores `meta.auth.validation.status = "valid"` on the vendor and writes an audit event. Validation uses a read-only provider probe (e.g. `GET /v1/models` for OpenAI-compatible vendors).

If validation fails, check vault secret name, provider adapter (`runtime.provider`), and network egress before running flows. Unsupported adapters return `unsupported_adapter` (not `unchecked` or `invalid`). Agents → Providers shows `adapter_status` for each vendor.

---

## 4. Enable release controls (Agents → Release)

**Dashboard:** Agents → **Release** tab.

| Field | Operator intent |
|-------|-----------------|
| `ai_enabled` | Master switch for `sn.ai` |
| `memory_enabled` | Master switch for `sn.memory` (also requires Memory settings enabled) |
| `rag_enabled` | Master switch for `sn.rag` (also requires RAG subsystem initialized) |
| `canary_percent` | Partial rollout — see below |
| `rollback_active` | Emergency off — disables all three subsystems immediately |

**HTTP:** `GET /ai/release`, `PUT /ai/release`

For a full smoke, set `ai_enabled` on, `canary_percent` to `100`, `rollback_active` off.

### Canary semantics (AI-S02)

- **Per execution, not per agent/project.** Cohort is chosen from `ctx.execution_id` (fallback: `ctx.flow_name`) via stable FNV hashing.
- **Uniform across subsystems.** One `canary_percent` on the Release panel gates `sn.ai`, `sn.memory`, and `sn.rag` together — matching the single dashboard control surface.
- **Rollback wins.** When `rollback_active` is true, all three behave as disabled regardless of canary.
- Flows outside the cohort receive `"sn.ai is disabled"` (and analogous memory/RAG errors). Guard with `if sn.ai and sn.ai.enabled then` or handle errors in `pcall`.

---

## 5. Run a flow that calls `sn.ai.chat`

Example: `sn.eg-support/fl/handle_ticket.lua` (examples bundle) classifies a ticket and optionally replies via `sn.ai.chat`.

**Manual run (HTTP):**

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"I cannot log in after the upgrade"}' \
  "http://localhost:8080/fl/sn-eg-support:handle_ticket/run"
```

**CLI:** use the dashboard flow runner or trigger via webhook/cron as configured in the kit.

Expected behavior when AI is enabled and in canary cohort:

- Flow returns JSON with a `reply` field from the model (or a fallback string if AI is off).
- Harness records an AI trace for the chat request.

If you see `"sn.ai is disabled"`, check Release tab (enabled + canary + rollback), execution logs, and that the flow run has a normal `ctx.execution_id`.

---

## 6. Verify the trace (Agents → Traces)

**Dashboard:** Agents → **Traces** tab — recent chat operations with provider, model, token usage, latency, and success flag.

**HTTP:**

```bash
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8080/ai/traces?limit=10"
curl -s -H "Authorization: Bearer $TOKEN" "http://localhost:8080/ai/traces/{id}"
```

Related observability:

- **Metrics** tab / `GET /ai/metrics?window_hours=24`
- **Audit** tab / `GET /ai/audit?limit=12` (includes provider validation events)

---

## Smoke checklist

| Step | Verify |
|------|--------|
| Vault secret exists | `GET /sc` or Secrets page |
| AI vendor in API Library | `meta.capabilities.ai`, `secret_ref`, `runtime.provider` |
| Validate provider | Status `valid` on vendor / Agents Providers card |
| Release | `ai_enabled`, `canary_percent=100`, rollback off |
| Run flow | `POST /fl/{id}/run` returns `ok: true` with model reply |
| Trace | Agents Traces or `GET /ai/traces` shows successful `chat` operation |

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `sn.ai is disabled` | Release off, rollback on, or execution outside canary cohort |
| Provider not found | Vendor missing `runtime.provider` or harness not restarted after library change |
| Validation `invalid` | Wrong key or blocked egress |
| Validation `unsupported_adapter` | `runtime.provider` has no harness adapter — see [AI provider extension](/ai-provider-extension) defer table |
| No traces | Chat never succeeded; check flow logs (`GET /ex/{id}/lg`) |
| Adapter `unsupported` on Providers tab | Vendor registered in API Library but `runtime.provider` is deferred — flows cannot call `sn.ai` until an adapter ships or you use an OpenAI-compatible workaround |

---

## Evaluation regression (AI-S04)

Harness CI gates retrieval quality and tool-loop error shaping without live API keys:

```bash
go test ./internal/rag -count=1 -run TestRetrievalEvalRegression
go test ./internal/ai -count=1 -run TestToolLoopErrorGoldenFixtures
```

Dashboard RAG overview (`/rag`) surfaces the same embedded retrieval summary as `GET /rag/overview` → `evaluation`. Full thresholds, fixture paths, and optional live SRE smoke: [RAG retrieval evaluation](/rag-evaluation).

---

## Related docs

- [Lua API — AI / Memory / RAG](/lua-api)
- [AI provider extension](/ai-provider-extension) — add adapters, defer table, validation probes
- [RAG retrieval evaluation](/rag-evaluation)
- [Harness HTTP routes — `/ai/*`, `/lib/*`](/harness-http-routes)
- [Kit development — starter kits](/kit-development)
- [Agentic AI spec](https://github.com/ndx-au/sentinel/blob/main/specs/agentic-ai.md)