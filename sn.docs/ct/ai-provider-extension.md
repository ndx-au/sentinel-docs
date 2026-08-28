---
title: "AI provider extension guide"
description: "How to add a Go runtime adapter for a new meta.runtime.provider value in API Library. Operators register vendors in the dashboard; the harness wires adapters at bootstrap via BuildClientFromLibrary."
---

# AI provider extension guide

How to add a Go **runtime adapter** for a new `meta.runtime.provider` value in API Library. Operators register vendors in the dashboard; the harness wires adapters at bootstrap via `BuildClientFromLibrary`.

Architecture reference: [`specs/agentic-ai.md`](https://github.com/ndx-au/sentinel/blob/main/specs/agentic-ai.md). Operator smoke path: [`21-AGENTIC-AI-OPERATOR.md`](/agentic-ai-operator).

---

## Registry model (locked)

| Concern | Location |
|---------|----------|
| Vendor records | API Library `api_vendors` (`meta.capabilities.ai`, `meta.auth.secret_ref`) |
| Credentials | Vault only — never plaintext in library JSON |
| Adapter list | `internal/ai/adapters.go` — single source for runtime, validation, dashboard |
| Runtime wiring | `BuildClientFromLibrary` → `RegisterRuntimeAdapter` |
| Flow calls | `sn.ai.*` — not Lua connectors |

There is **no** parallel provider registry. Dashboard Agents → Providers surfaces `adapter_status` (`active` | `unsupported` | `inactive`) when a vendor is AI-capable.

---

## Shipped and deferred adapters

| `runtime.provider` | Status | Notes |
|--------------------|--------|-------|
| `openai` | **shipped** | OpenAI-compatible base URL; use for DeepSeek, Together, and other `/v1` APIs via `meta.runtime.base_url` |
| `openrouter` | **shipped** | OpenAI-compatible alias; default `https://openrouter.ai/api/v1`; sets `HTTP-Referer: https://ndx.au` and `X-Title: NDX Sentinel`. Keep slashy model slugs (`openai/gpt-4o-mini`) with `runtime.provider` already set to `openrouter` so the harness does not split the slug on `/`. |
| `anthropic` | **shipped** | Native Anthropic Messages API |
| `gemini` | **shipped** | Google Generative Language API |
| `azure-openai` | **deferred** | Often OpenAI-compatible — workaround: `runtime.provider: "openai"` + Azure `base_url` if your deployment matches the OpenAI client shape |
| `ollama` | **deferred** | Local runtime; different API surface than OpenAI chat completions |
| `groq` | **deferred** | OpenAI-compatible candidate for a future thin alias |
| `mistral` | **deferred** | OpenAI-compatible candidate for a future thin alias |
| `cohere` | **deferred** | Distinct API; needs dedicated adapter |
| `deepseek` | **workaround** | Register vendor with `runtime.provider: "openai"` and `base_url: "https://api.deepseek.com"` (see `TestBuildClientFromLibraryUsesRuntimeBaseURLForOpenAICompatibleVendors`) |

---

## Provider interface

Defined in `internal/ai/types.go`:

```go
type Provider interface {
    Name() string
    Chat(ctx context.Context, req ChatRequest) (*ChatResponse, error)
    Complete(ctx context.Context, req CompleteRequest) (*CompleteResponse, error)
    ChatStream(ctx context.Context, req ChatRequest, handler StreamHandler) (*ChatResponse, error)
    Embed(ctx context.Context, req EmbedRequest) (*EmbedResponse, error)
    Models() []string
    SupportsTools() bool
    SupportsStreaming() bool
}
```

Common errors (`ErrAuth`, `ErrRateLimit`, `ErrModel`, …) live in the same package. Map HTTP status codes from vendor APIs to these where practical so policy, traces, and tool-loop classification stay consistent.

---

## Adding a new adapter (checklist)

### 1. Implement the provider

Copy the pattern from an existing adapter:

| Adapter | File | Notes |
|---------|------|-------|
| OpenAI-compatible | `internal/ai/openai.go` | Best starting point for `/v1/chat/completions` vendors |
| Anthropic | `internal/ai/anthropic.go` | Messages API, tool-use blocks |
| Gemini | `internal/ai/gemini.go` | Embed + generateContent |

Constructor signature: `NewFooProvider(apiKey, baseURL string) *FooProvider`. `Name()` must return the **`runtime.provider` string** operators will set in API Library (e.g. `"groq"`).

### 2. Register in the central adapter registry

Edit `internal/ai/adapters.go`:

- Add the name to `SupportedRuntimeProviders()`.
- Add a `case` in `IsRuntimeAdapterImplemented`.
- Add a `case` in `RegisterRuntimeAdapter` that calls `client.RegisterProvider(NewFooProvider(...))`.

`runtime.go` calls `RegisterRuntimeAdapter` — do not duplicate switch arms elsewhere.

### 3. Add credential validation probe

Edit `internal/ai/provider_validation.go` → `ValidateProviderCredentials`:

- Add a `case` with a read-only HTTP probe (typically `GET …/models` or vendor-specific health endpoint).
- Return `Status: "valid"` / `"invalid"` with a short message.
- Unsupported providers already return `unsupported_adapter` via `IsRuntimeAdapterImplemented`.

Validation is triggered from the dashboard/API: `POST /lib/{vendor_id}/validate`.

### 4. Model catalog (optional)

If the adapter ships known model IDs for dashboard pricing hints, add them to `internal/ai/model_catalog.go` → `KnownModels`.

### 5. API Library vendor meta shape

Minimal AI vendor record:

```json
{
  "capabilities": { "ai": true, "chat": true, "embedding": false, "tool_use": true },
  "auth": { "secret_ref": "my_vendor_key" },
  "runtime": {
    "provider": "openai",
    "base_url": "https://api.example.com/v1",
    "default_model": "model-id",
    "allowed_models": ["model-id"]
  }
}
```

| Field | Purpose |
|-------|---------|
| `capabilities.ai` | Required for harness bootstrap to consider the vendor |
| `auth.secret_ref` | Vault key name |
| `runtime.provider` | Selects Go adapter (`adapters.go`) |
| `runtime.base_url` | Passed to OpenAI-compatible adapters |
| `runtime.default_model` | Default when this is the only registered provider |

### 6. Tests

Follow `internal/ai/runtime_test.go`:

```bash
go test ./internal/ai -count=1 -run "BuildClientFromLibrary|ValidateProvider|Adapter"
```

Add:

- `TestBuildClientFromLibraryRegisters…` — vendor in library + vault secret → `client.GetProvider("yourname")` ok
- `TestValidateProvider…` — mock HTTP transport in `provider_validation_test.go`
- Dashboard: `go test ./internal/dashboard -count=1 -run Agent` — `adapter_status: "active"` for wired vendors

Regression harness path (no live key): `go test ./internal/api -run TestAgenticAIOperatorPath`.

---

## Operator visibility

When `runtime.provider` has no adapter:

- Bootstrap logs: `ai: provider registered in library but runtime adapter is not implemented`
- Agents → Providers: `adapter_status: "unsupported"` with `adapter_message` pointing here
- Validate: `status: "unsupported_adapter"` (distinct from `unchecked` or `invalid`)

Restart the harness after library changes so `BuildClientFromLibrary` re-runs.

---

## Related docs

- [Agentic AI operator guide](/agentic-ai-operator) — Vault, validate, release, smoke
- [Lua API — `sn.ai`](/lua-api)
- [Harness HTTP routes — `/lib/*`, `/ai/*`](/harness-http-routes)
- [Agentic AI spec](https://github.com/ndx-au/sentinel/blob/main/specs/agentic-ai.md)