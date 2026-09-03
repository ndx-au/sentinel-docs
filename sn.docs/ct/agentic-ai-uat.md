---
title: "Agentic AI — UAT trail"
description: "Hands-on acceptance trail for M1 — Agentic AI completion. Work through each section in order; sample payloads are copy-paste ready."
type: Playbook
tags: [ai, uat]
status: stable
---

# Agentic AI — UAT trail

Hands-on acceptance trail for **M1 — Agentic AI completion**. Work through each section in order; sample payloads are copy-paste ready.

| Reference | Path |
|-----------|------|
| Architecture spec | [`specs/agentic-ai.md`](https://github.com/ndx-au/sentinel/blob/main/specs/agentic-ai.md) |
| Operator guide | [`21-AGENTIC-AI-OPERATOR.md`](/agentic-ai-operator) |
| Provider extension | [`23-AI-PROVIDER-EXTENSION.md`](/ai-provider-extension) |
| UAT SRE (no git) | `E:\_CODE\SRE\agentic-uat` |

**Time:** ~60–90 minutes with a live API key. **Without a key:** you can still complete sections marked *(no key)*.

---

## 0 — UAT sandbox

The trail uses a dedicated SRE outside the harness repo:

```
E:\_CODE\SRE\agentic-uat
```

### 0.1 Create (if missing)

From PowerShell:

```powershell
$UAT = "E:\_CODE\SRE\agentic-uat"
$HARNESS = "E:\_CODE\sentinel"
$SRE_INIT = "E:\_CODE\sre-init"

New-Item -ItemType Directory -Force -Path $UAT | Out-Null
Set-Location $UAT

& "$HARNESS\sndev.exe" -n sre init --minimal `
  --with-local $SRE_INIT `
  --with-bundle core `
  --with-bundle examples
```

### 0.2 Vault passphrase (required for secrets)

Edit `.sentinel\config.json` and set:

```json
"vault_passphrase": "uat-trail-2026!"
```

On first harness start the vault database is created. You may also export:

```powershell
$env:SENTINEL_VAULT_PASSPHRASE = "uat-trail-2026!"
```

### 0.3 Environment shortcuts

Create `.env` in the UAT root (gitignored by default `.gitignore`):

```dotenv
HARNESS_URL=http://127.0.0.1:8080
SENTINEL_VAULT_PASSPHRASE=uat-trail-2026!
# After first start, paste token from .sentinel/config.json → api.tokens[0].token
SENTINEL_API_KEY=
```

### 0.4 Verify kits

```powershell
& "$HARNESS\sndev.exe" -p $UAT sre test sn.core-agent/md -f agent -v
& "$HARNESS\sndev.exe" -p $UAT sre test sn.core-agent/fl -f assistant -v
```

| Check | Pass |
|-------|------|
| `sn.core-agent` present with `md/agent.lua` | ☐ |
| Kit tests pass | ☐ |

---

## 1 — Start harness and dashboard

The **dashboard starts standalone** (healthy without a harness). Attach the UAT harness from **Instances** when ready, or start the harness first and connect manually.

```powershell
$UAT = "E:\_CODE\SRE\agentic-uat"
$HARNESS = "E:\_CODE\sentinel"

# Terminal A — dashboard (no harness required; -d auto-clears stale PID/port)
& "$HARNESS\sndev.exe" dashboard start -p $UAT -d

# Terminal B — harness API (when you are ready for flow/API tests)
& "$HARNESS\sndev.exe" -p $UAT start -d
```

**Attach harness in dashboard:** open **http://localhost:9090/instances** → connect to `localhost:8080` (SRE path `E:\_CODE\SRE\agentic-uat`).

Optional: `dashboard start localhost:8080 -p $UAT -d` tries attachment after listen but still starts if the harness is down.

Open **http://localhost:9090** (dashboard) or **http://127.0.0.1:8080** (API direct, after harness is up).

### Dashboard troubleshooting

| Symptom | Fix |
|---------|-----|
| `not yet healthy` on `-d` start | Rebuild recent `sndev`; check `C:\Users\<you>\.sentinel\dashboard-9090.log`. |
| `PID file exists` (foreground) | Confirm delete, or use `-d` to auto-replace. |
| Attach 502 on Instances | Start harness (Terminal B) first, then connect. |
| Port 9090 in use (foreground) | Confirm kill, or use `-d` to auto-replace. |

Copy the API bearer token from `.sentinel\config.json`:

```powershell
(Get-Content "$UAT\.sentinel\config.json" | ConvertFrom-Json).api.tokens[0].token
```

Set `$TOKEN` for curl examples:

```powershell
$TOKEN = "<paste-token>"
$BASE = "http://127.0.0.1:8080"
```

| Check | Pass |
|-------|------|
| Harness starts without errors | ☐ |
| Dashboard loads `/agents` | ☐ |
| Token works: `curl -s -H "Authorization: Bearer $TOKEN" $BASE/hl` | ☐ |

---

## 2 — Vault secret

**Sample secret name:** `openai_api_key_uat`  
**Sample value:** your real `sk-...` key (or a mock key if you only test validation failure paths).

### CLI

```powershell
$env:SENTINEL_VAULT_PASSPHRASE = "uat-trail-2026!"
& "$HARNESS\sndev.exe" -p $UAT secret set openai_api_key_uat
# paste key at prompt
```

### HTTP

```bash
curl -s -X POST "$BASE/sc" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"openai_api_key_uat","value":"sk-YOUR-KEY-HERE"}'
```

| Check | Pass |
|-------|------|
| Secret listed on Secrets page or `GET /sc` | ☐ |

---

## 3 — Register AI vendors (API Library)

### 3.1 OpenAI — primary smoke vendor

**Vendor ID:** `openai-uat`

```bash
curl -s -X POST "$BASE/lib" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "openai-uat",
    "display_name": "OpenAI UAT",
    "auth_type": "bearer",
    "meta": {
      "capabilities": { "ai": true, "chat": true },
      "auth": { "secret_ref": "openai_api_key_uat" },
      "runtime": {
        "provider": "openai",
        "default_model": "gpt-4o-mini",
        "allowed_models": ["gpt-4o-mini", "gpt-4o"]
      }
    }
  }'
```

**Dashboard:** API Library → New vendor → paste the same `meta` fields.

### 3.2 Ollama — unsupported adapter demo *(no key)*

**Vendor ID:** `ollama-uat` — exercises `unsupported_adapter` / dashboard `adapter_status`.

First store a dummy secret:

```bash
curl -s -X POST "$BASE/sc" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"ollama_key_uat","value":"local-not-used"}'
```

Register vendor:

```bash
curl -s -X POST "$BASE/lib" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "ollama-uat",
    "display_name": "Ollama UAT (deferred)",
    "auth_type": "bearer",
    "meta": {
      "capabilities": { "ai": true, "chat": true },
      "auth": { "secret_ref": "ollama_key_uat" },
      "runtime": {
        "provider": "ollama",
        "default_model": "llama3"
      }
    }
  }'
```

Restart harness after library changes if providers do not appear:

```powershell
# Ctrl+C Terminal A, then start again
& "$HARNESS\sndev.exe" -p $UAT start
```

| Check | Pass |
|-------|------|
| `openai-uat` in API Library | ☐ |
| `ollama-uat` in API Library | ☐ |

---

## 4 — Validate providers (Agents → Providers)

### OpenAI

```bash
curl -s -X POST "$BASE/lib/openai-uat/validate" \
  -H "Authorization: Bearer $TOKEN"
```

**Expect:** `status: valid` (with a real key and egress). Audit event written.

### Ollama *(no key)*

```bash
curl -s -X POST "$BASE/lib/ollama-uat/validate" \
  -H "Authorization: Bearer $TOKEN"
```

**Expect:** `unsupported_adapter` (not `unchecked`).

### Dashboard

Agents → **Providers** tab:

| Vendor | Adapter badge | Pass |
|--------|---------------|------|
| OpenAI UAT | `active` | ☐ |
| Ollama UAT | `unsupported` + hint linking `docs/23-AI-PROVIDER-EXTENSION.md` | ☐ |

---

## 5 — Release controls

Enable AI for full smoke. **Sample release payload:**

```bash
curl -s -X PUT "$BASE/ai/release" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ai_enabled": true,
    "memory_enabled": true,
    "rag_enabled": false,
    "canary_percent": 100,
    "rollback_active": false
  }'
```

**Dashboard:** Agents → **Release** — match the same values.

| Check | Pass |
|-------|------|
| `GET /ai/release` shows `ai_enabled: true`, `canary_percent: 100` | ☐ |
| Rollback off | ☐ |

---

## 6 — Core agent flow (`sn-core-agent:assistant`)

**Sample params:**

```json
{
  "agent_id": "uat-bot",
  "session_id": "trail-session-1",
  "message": "Summarize what Sentinel agentic AI provides in two sentences.",
  "model": "gpt-4o-mini",
  "persona": {
    "name": "UAT Assistant",
    "mission": "Verify harness AI path end-to-end.",
    "goals": ["Be concise", "Confirm sn.ai.chat works"]
  }
}
```

### HTTP

```bash
curl -s -X POST "$BASE/fl/sn-core-agent:assistant/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "uat-bot",
    "session_id": "trail-session-1",
    "message": "Summarize what Sentinel agentic AI provides in two sentences.",
    "model": "gpt-4o-mini"
  }'
```

### CLI

```powershell
& "$HARNESS\sndev.exe" -p $UAT run sn-core-agent:assistant `
  --params-json '{"agent_id":"uat-bot","session_id":"trail-session-1","message":"Hello from UAT trail","model":"gpt-4o-mini"}'
```

**Expect:** `ok: true`, body includes `reply` with model text (not `"sn.ai is disabled"`).

| Check | Pass |
|-------|------|
| Flow succeeds | ☐ |
| `reply` is non-empty | ☐ |

---

## 7 — Memory continuity (second turn)

Same `agent_id` + `session_id`, new message:

```bash
curl -s -X POST "$BASE/fl/sn-core-agent:assistant/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "uat-bot",
    "session_id": "trail-session-1",
    "message": "What was my first question in this session?",
    "model": "gpt-4o-mini"
  }'
```

**Expect:** Model references prior turn (memory hydrated via `sn.md.agent.run` → `agent_memory`).

**Dashboard:** Agents → **Memory** — session `trail-session-1` shows turns.

| Check | Pass |
|-------|------|
| Second turn acknowledges prior context | ☐ |
| Memory inventory lists session | ☐ |

---

## 8 — Examples flow (`sn-eg-support:handle_ticket`)

```bash
curl -s -X POST "$BASE/fl/sn-eg-support:handle_ticket/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"I cannot log in after the upgrade. This is urgent."}'
```

**Sample expected shape:**

```json
{
  "ok": true,
  "priority": "high",
  "escalate": true,
  "reply": "<model-generated support reply>"
}
```

| Check | Pass |
|-------|------|
| Flow returns `reply` | ☐ |
| `priority` / `escalate` populated | ☐ |

---

## 9 — Canary partial rollout *(no key for math-only check)*

Set canary to **0** — all executions should see AI disabled:

```bash
curl -s -X PUT "$BASE/ai/release" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ai_enabled":true,"memory_enabled":true,"rag_enabled":false,"canary_percent":0,"rollback_active":false}'
```

Run assistant again:

```bash
curl -s -X POST "$BASE/fl/sn-core-agent:assistant/run" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"This should fail canary","agent_id":"uat-bot","session_id":"canary-test"}'
```

**Expect:** Error / `sn.ai is disabled` in flow result.

Restore full rollout:

```bash
curl -s -X PUT "$BASE/ai/release" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ai_enabled":true,"memory_enabled":true,"rag_enabled":false,"canary_percent":100,"rollback_active":false}'
```

| Check | Pass |
|-------|------|
| `canary_percent: 0` blocks chat | ☐ |
| `canary_percent: 100` restores chat | ☐ |

---

## 10 — Emergency rollback

```bash
curl -s -X PUT "$BASE/ai/release" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ai_enabled":true,"memory_enabled":true,"rag_enabled":true,"canary_percent":100,"rollback_active":true}'
```

Run assistant — **expect** disabled.

Clear rollback when done:

```bash
curl -s -X PUT "$BASE/ai/release" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"rollback_active":false,"canary_percent":100}'
```

| Check | Pass |
|-------|------|
| Rollback disables `sn.ai` immediately | ☐ |
| Clearing rollback re-enables | ☐ |

---

## 11 — Observability

### Traces

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/ai/traces?limit=5"
```

**Dashboard:** Agents → **Traces** — successful `chat` rows for sections 6–8.

### Metrics

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/ai/metrics?window_hours=24"
```

### Audit (validation events)

```bash
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/ai/audit?limit=10"
```

| Check | Pass |
|-------|------|
| Trace for successful assistant run | ☐ |
| Metrics show activity | ☐ |
| Audit includes provider validation | ☐ |

---

## 12 — Scaffold preset *(optional)*

Generate a new agent flow from harness scaffold:

```powershell
Set-Location $UAT
& "$HARNESS\sndev.exe" -p $UAT sre flow new my-uat-agent --kit sn.core-agent --preset agent -n
```

Open `sn.core-agent\fl\my-uat-agent.lua` — **expect** `sn.md.agent.run({...})`, not inlined persona/memory/chat.

| Check | Pass |
|-------|------|
| Generated flow delegates to `sn.md.agent.run` | ☐ |

---

## 13 — RAG *(optional — requires PG)*

Skip unless PostgreSQL + pgvector are configured in `sentinel.yaml` and RAG subsystem is initialized.

1. Enable `rag_enabled: true` on Release.
2. Ingest sample docs via `sn.core-rag` or dashboard RAG page.
3. Run assistant with RAG params:

```json
{
  "agent_id": "uat-bot",
  "session_id": "rag-trail",
  "message": "What does the runbook say about restart?",
  "rag": { "query": "service restart procedure", "limit": 3 }
}
```

**Expect:** `rag_hits` array in result when hits exist.

| Check | Pass |
|-------|------|
| RAG context prepended (optional) | ☐ |

---

## 14 — Harness regression *(no SRE required)*

From harness repo:

```powershell
cd E:\_CODE\sentinel
go test ./internal/api -count=1 -run TestAgenticAIOperatorPath
go test ./internal/ai -count=1 -run "BuildClient|Adapter"
go test ./internal/rag -count=1 -run TestRetrievalEvalRegression
go test ./internal/scaffold -count=1 -run Preset
```

| Check | Pass |
|-------|------|
| All commands exit 0 | ☐ |

---

## Final sign-off

| Area | Pass |
|------|------|
| Vault + API Library + validate | ☐ |
| Release + canary + rollback | ☐ |
| `sn-core-agent:assistant` + memory | ☐ |
| `sn-eg-support:handle_ticket` | ☐ |
| Traces / metrics / audit | ☐ |
| Unsupported adapter (`ollama-uat`) | ☐ |
| Scaffold preset (optional) | ☐ |

**Tester:** _______________ **Date:** _______________ **Harness build:** _______________

**Notes:**

---

## Related docs

- [Agentic AI operator guide](/agentic-ai-operator)
- [RAG retrieval evaluation](/rag-evaluation)
- [AI provider extension](/ai-provider-extension)
- [Agentic AI spec](https://github.com/ndx-au/sentinel/blob/main/specs/agentic-ai.md)