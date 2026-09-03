---
title: "RAG retrieval evaluation"
description: "Offline, fixture-driven retrieval benchmarks for the harness RAG stack. Live PG-backed eval against a running SRE is optional; CI gates on embedded fixtures in internal/rag/testdata/retrieval_eval_fixtures.json."
type: Guide
tags: [ai, rag]
status: stable
---

# RAG retrieval evaluation

Offline, fixture-driven retrieval benchmarks for the harness RAG stack. Live PG-backed eval against a running SRE is optional; **CI gates on embedded fixtures** in `internal/rag/testdata/retrieval_eval_fixtures.json`.

Architecture reference: [`specs/agentic-ai.md`](https://github.com/ndx-au/sentinel/blob/main/specs/agentic-ai.md) (AI-S04). Operator path for enabling RAG: [`21-AGENTIC-AI-OPERATOR.md`](/agentic-ai-operator).

---

## CI regression gate

Run from the harness repo root:

```bash
go test ./internal/rag -count=1
```

Named regression test (same thresholds as `TestEmbeddedRetrievalFixturesMeetBenchmarks`):

```bash
go test ./internal/rag -count=1 -run TestRetrievalEvalRegression
```

### Thresholds

Defined in `internal/rag/evaluation_test.go`:

| Metric | Minimum | Meaning |
|--------|---------|---------|
| `pass_rate` | `1.0` | Every fixture passes top-1 + required-document checks |
| `top1_accuracy` | `1.0` | Expected top document ranks first |
| `mean_reciprocal_rank` | `1.0` | MRR across all fixtures |

A failing run indicates retrieval ranking regression in hybrid RRF, lexical, or modality-scoped cases. Update fixtures intentionally when changing fusion behavior; do not lower thresholds without recording rationale in `.progress/`.

### Fixture harness

| Artifact | Role |
|----------|------|
| `internal/rag/evaluation.go` | `EvaluateEmbeddedRetrievalFixtures`, `EvaluateRetrievalFixtures` |
| `internal/rag/testdata/retrieval_eval_fixtures.json` | Golden lexical + semantic result sets per query |
| `internal/rag/evaluation_test.go` | `TestRetrievalEvalRegression` + config embedding checks |

Fixtures are deterministic: they supply pre-ranked lexical and semantic `SearchResult` slices and assert fused/filtered output — no live embedding API or PostgreSQL required.

---

## Dashboard summary

The RAG overview (`GET /rag/overview` via dashboard `/rag`) includes an `evaluation` object from `EvaluateEmbeddedRetrievalFixtures`:

| Field | Description |
|-------|-------------|
| `source` | `"embedded_golden_fixtures"` |
| `fixture_count` | Number of benchmark cases |
| `passed_count` | Cases that passed |
| `pass_rate` | `passed_count / fixture_count` |
| `top1_accuracy` | Fraction with correct top document |
| `mean_reciprocal_rank` | Average reciprocal rank of expected top doc |
| `config` | Active embedding/chunk settings snapshot |
| `cases[]` | Per-fixture `passed`, `top_document`, `missing_documents`, `reciprocal_rank` |

API coverage: `go test ./internal/api -run RagOverview` (see `internal/api/rag_handlers_test.go`).

---

## Tool-loop error golden fixtures

AI tool-loop failure classes (`not_found`, `timeout`, `runtime`) are documented separately:

- Fixtures: `internal/ai/testdata/tool_loop_error_fixtures.json`
- CI: `go test ./internal/ai -count=1 -run TestToolLoopErrorGoldenFixtures`
- Lua API: [`02-LUA-API.md` — Tool-loop error classes](/lua-api#tool-loop-error-classes)

---

## Optional live smoke (SRE runtime)

Fixture CI does not require a running harness. To validate RAG against a real SRE (PostgreSQL + embeddings configured in `.sentinel/config.json`):

```bash
./build.ps1   # or ./build.sh
.\sentinel.exe -p /path/to/sre harness start
```

Example local target (sibling of harness repo): `E:\_CODE\SRE\test` with kits `sn.roadmap-fixtures`, `sn.core-rag`, `sn.eg-rag-chat`. Run `sn-roadmap-fixtures:rag_guard_smoke` or inspect `/rag` overview evaluation panel.

If PG or embedding providers are not configured, skip live smoke — fixture CI remains the release gate.

---

## Related docs

- [Lua API — RAG (`sn.rag`)](/lua-api#rag-snrag)
- [Agentic AI operator guide](/agentic-ai-operator)
- [Agentic AI spec](https://github.com/ndx-au/sentinel/blob/main/specs/agentic-ai.md)