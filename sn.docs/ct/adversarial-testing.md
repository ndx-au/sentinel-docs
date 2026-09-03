---
title: "Adversarial Testing & Probe Runner"
description: "Adversarial testing is the practice of deliberately trying to break your system to find bugs before your users do."
type: Guide
tags: [testing]
status: stable
---

# Adversarial Testing & Probe Runner

## Introduction

Adversarial testing is the practice of deliberately trying to break your system to find bugs before your users do. Sentinel includes a built-in adversarial testing framework designed to systematically probe every API endpoint, validate the API contract, discover security vulnerabilities, and stress-test the harness under load.

### Testing Philosophy

Traditional testing (unit tests, integration tests) verifies that your system works correctly when used as intended. Adversarial testing goes further: it verifies that your system behaves correctly (or at least safely) when used incorrectly, maliciously, or under extreme conditions. This includes:

- **Malformed input** -- What happens when a client sends invalid JSON, wrong content types, or missing required fields? The harness should return a structured error, not crash or leak stack traces.
- **Boundary conditions** -- What happens with empty strings, zero-length arrays, extremely long inputs, negative numbers, or Unicode characters? The harness should handle these gracefully.
- **Path traversal attacks** -- Can a client read files outside the SRE directory by manipulating URL paths (e.g., `/cm/../../etc/passwd`)? This must never succeed.
- **Concurrent access** -- What happens when 20 clients simultaneously submit flow executions? Does the harness maintain consistency?
- **Authentication bypass** -- Do protected endpoints actually reject unauthenticated requests? Do auth-exempt routes work without tokens?

The adversarial testing framework automates these checks across all API endpoints, producing structured results that can be integrated into CI/CD pipelines.

### Two Approaches

There are two ways to use adversarial testing in Sentinel:

1. **Probe Runner CLI** (`cmd/simulator -mode probe`) -- An automated tool that generates and executes probes against a running harness. It produces structured output (human-readable tables or machine-readable JSONL) and is designed for integration into CI/CD pipelines. This is the primary approach for regression testing.

2. **Agent Skill** (`/sn-go-adversarial`) -- An AI-driven approach where an agent autonomously discovers the API surface, generates probes, executes them, diagnoses failures, fixes bugs, and re-verifies. This is used during development when you want an AI assistant to find and fix bugs in a test-debug-fix cycle.

Both approaches work by sending HTTP requests against a running harness and evaluating responses against the API contract. The API contract states that every response must be HTTP 200 with a JSON body. Errors are communicated in the body as `{ok: false, err: "CODE", msg: "..."}`. A probe "passes" when the response conforms to this contract (even if the response indicates an error -- a well-formatted error response is correct behavior).

---

## Quick Start

### Run Probes Against a Live Harness

```bash
# Build the probe runner
go build -o simulator ./cmd/simulator

# Start your harness in another terminal
sentinel harness start -p /path/to/your/sre

# Run health probes (the simplest and fastest test)
./simulator -mode probe -feature health

# Run ALL probes across all feature areas
./simulator -mode probe -feature all

# Output as machine-readable JSONL for CI/CD integration
./simulator -mode probe -feature flows -jsonl
```

### Example Output

The probe runner produces a formatted table showing each probe's result, the HTTP method and path tested, and the latency:

```
Sentinel Probe Runner
  Target:  http://localhost:8080
  Feature: health
  Workers: 1

Generated 8 probes

  [PASS] HL-001               GET /hl                              12ms
  [PASS] HL-002               GET /hl/kt                             8ms
  [PASS] HL-003               POST /hl/reload                      45ms
  [PASS] HL-004               GET /hl                               6ms
  [PASS] HL-005               GET /api/config                       5ms
  [PASS] HL-KT-001            POST /hl/kt/sn/probe/rl              22ms
  [PASS] HL-KT-002            POST /hl/kt/zz/nonexistent/rl         4ms
  [PASS] HL-KT-003            POST /hl/kt/sn/probe/off             31ms

--- Summary ---
Category       Total  Pass  Fail Error
----------     ----- ----- ----- -----
happy              3     3     0     0
format             2     2     0     0
TOTAL              5     5     0     0

All 8 probes passed.
```

A "PASS" means the harness responded correctly according to the API contract. A "FAIL" means the harness violated the contract (returned a non-200 status code, returned invalid JSON, returned file system contents for a traversal attempt, etc.).

---

## Probe Runner CLI Reference

```
Usage: simulator -mode probe [flags]

Flags:
  -mode probe          Enable probe mode (required)
  -addr string         Harness address (default "localhost:8080")
  -feature string      Feature to probe (default "health")
  -concurrent int      Max parallel probes (default 1)
  -timeout duration    Per-probe timeout (default 30s)
  -token string        Bearer token for authenticated probes
  -jsonl               Output as JSONL (one JSON object per line)
```

**Flag details:**

- `-mode probe` -- Switches the simulator from its default activity generation mode to probe mode. This flag is required for adversarial testing.
- `-addr` -- The address of the harness to probe. Use `localhost:8080` for local testing, or `staging.example.com:8080` for remote testing. Do not include the `http://` prefix.
- `-feature` -- Which set of probes to run. Each feature corresponds to a group of API endpoints. Use `all` to run everything.
- `-concurrent` -- How many probes to run simultaneously. Higher values stress-test the harness's concurrency handling. Start with 1 for debugging, increase to 5-20 for stress testing.
- `-timeout` -- Maximum time to wait for each probe's HTTP response. Increase this if probing a slow or remote harness.
- `-token` -- Bearer token for probing a harness in production mode. Without this, authenticated endpoints will return AUTH.REQUIRED errors (which may be the expected behavior you are testing).
- `-jsonl` -- Output one JSON object per line instead of the formatted table. Use this for piping results to scripts, log aggregators, or CI/CD systems.

### Available Features

Each feature corresponds to a group of API endpoints and generates probes across multiple categories (happy path, boundary, malformed, traversal, etc.):

| Feature | What It Tests | Probe Count | Description |
|---------|--------------|-------------|-------------|
| `health` | `/hl`, `/hl/kt`, `/hl/reload`, `/hl/kt/{ns}/{name}/rl\|off\|on`, `/api/config` | 8 | Harness health, kit inventory (`on` field), full SRE reload, per-kit lifecycle (uses `sn.probe` on test SRE), and config status. |
| `flows` | `/fl`, `/fl/{id}/run`, `/ex`, `/ex/{id}` | 10 | Flow listing, execution, execution history, and execution detail. Tests both successful execution and error cases (nonexistent flows, malformed parameters). |
| `secrets` | `/sc` CRUD, upsert, malformed input | 8 | Vault operations: creating, reading, updating, and deleting secrets. Tests for SQL injection in secret names, oversized values, and idempotent upsert behavior. |
| `triggers` | `/tr` CRUD, invalid types, empty fields | 7 | Trigger management: creating cron and event triggers, listing, deletion. Tests invalid cron expressions, empty trigger names, and nonexistent trigger IDs. |
| `forms` | `/fm` list, render, submissions, stats | 5 | Form system: listing forms, rendering form HTML, submitting form data, and querying submission statistics. |
| `cms` | `/cm` list, get, traversal attempts | 4 | CMS content: listing entries, fetching by slug, and path traversal attacks attempting to read files outside the CMS directory. |
| `source` | `/src/*` read, write, traversal | 4 | Source file management: reading and writing SRE source files, with traversal probes attempting to escape the SRE directory. |
| `config` | `/cfg/project` read/write | 2 | Project configuration: reading and writing sentinel.yaml settings. |
| `kits` | `/kt/{ns}/{name}` pages, assets, traversal | 3 | Kit serving: fetching kit pages, static assets, and traversal probes attempting to leak kit.yaml or escape the kit directory. |
| `webhooks` | `/wh/*` unknown hooks, traversal, large payload | 4 | Webhook handling: posting to nonexistent webhook paths, path traversal through webhook URLs, and oversized payload handling. |
| `all` | Everything above | ~55 | Runs all probe sets. This is the recommended option for full regression testing. |

---

## Usage Examples

### Test a Single Feature

When you are working on a specific area of the codebase, run only the relevant probes to get fast feedback:

```bash
# After modifying flow execution handlers
./simulator -mode probe -feature flows

# After changing secrets/vault code
./simulator -mode probe -feature secrets

# After updating webhook routing
./simulator -mode probe -feature webhooks
```

### Test Against a Remote Harness

Probe a staging or production harness to verify it is configured correctly:

```bash
# Probe a staging server (no authentication)
./simulator -mode probe -addr staging.example.com:8080 -feature all

# Probe with authentication token (production mode)
./simulator -mode probe -addr staging.example.com:8080 -token "my-api-token" -feature all
```

### Parallel Probing for Stress Testing

Use the `-concurrent` flag to test how the harness handles simultaneous requests:

```bash
# Run 10 probes concurrently to test basic concurrency
./simulator -mode probe -feature all -concurrent 10

# Heavy stress test: 20 concurrent probes with a short timeout
# This tests whether the harness degrades gracefully under load
./simulator -mode probe -feature flows -concurrent 20 -timeout 5s
```

### Machine-Readable Output (JSONL)

JSONL (JSON Lines) output produces one JSON object per line, making it easy to process with standard Unix tools:

```bash
# Save results to a file
./simulator -mode probe -feature all -jsonl > probe-results.jsonl

# Filter for failures only
./simulator -mode probe -feature all -jsonl | grep '"result":"fail"'

# Pretty-print failures for human review
./simulator -mode probe -feature all -jsonl \
  | grep '"result":"fail"' \
  | python3 -m json.tool

# Count pass/fail totals
./simulator -mode probe -feature all -jsonl \
  | python3 -c "
import sys, json
results = [json.loads(l) for l in sys.stdin if '__summary__' not in l]
p = sum(1 for r in results if r['result'] == 'pass')
f = sum(1 for r in results if r['result'] == 'fail')
print(f'Pass: {p}  Fail: {f}  Total: {p+f}')
"
```

### JSONL Output Format

Each line is a self-contained JSON object representing one probe result:

```json
{"id":"HL-001","cat":"happy","method":"GET","path":"/hl","result":"pass","http":200,"ms":12}
{"id":"FL-002","cat":"state","method":"POST","path":"/fl/nonexistent.kit/noflow/run","result":"pass","http":200,"ok":false,"err":"flow_not_found","ms":3}
{"id":"SRC-002","cat":"traversal","method":"GET","path":"/src/../../etc/passwd","result":"pass","http":200,"ms":1}
```

The final line is always a summary:

```json
{"id":"__summary__","result":"pass","data":{"passed":52,"failed":0,"errors":0,"total":52}}
```

**Field reference:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Probe identifier (e.g., `HL-001`, `FL-003`). The prefix indicates the feature area. |
| `cat` | string | Probe category: happy, boundary, malformed, auth, traversal, concurrency, state, format |
| `method` | string | HTTP method used (GET, POST, PUT, DELETE) |
| `path` | string | Endpoint path that was probed |
| `result` | string | `pass` (contract satisfied), `fail` (contract violated), or `error` (probe itself failed) |
| `http` | int | HTTP status code received from the harness |
| `ok` | bool | Parsed `ok` field from response body, if present |
| `err` | string | Error code from response body, or probe-level error description |
| `msg` | string | Error message for additional context |
| `ms` | int | Latency in milliseconds from request sent to response received |
| `detail` | string | Additional context for failures (what was expected vs. what was received) |

---

## Probe Categories

Every endpoint is tested across multiple categories. Each category targets a different class of potential bugs. Understanding these categories helps you interpret probe results and prioritize fixes.

### Happy Path

**What it tests:** Standard, correct usage of the endpoint. Does the endpoint work as documented when given valid inputs?

**Why it matters:** Happy path failures indicate fundamental bugs -- the endpoint does not work at all, even under ideal conditions. These should be fixed first.

**Examples:**
```bash
# Flow list returns valid JSON array
# Probe FL-001: GET /fl -> expect HTTP 200, valid JSON with ok:true
./simulator -mode probe -feature flows
```

### Boundary

**What it tests:** Edge cases, empty inputs, extreme values, Unicode characters, very long strings, zero and negative numbers. These are inputs that are technically valid (or at least not malicious) but push the system to its limits.

**Why it matters:** Boundary bugs are among the most common in production. A system that works with normal inputs but fails with an empty string, a very long name, or a Unicode character is fragile. Boundary probes catch these issues.

**Examples:**
```
FL-006: GET /fl?limit=0         -> should handle gracefully (return empty or default)
FL-007: GET /fl?limit=-1        -> should handle gracefully (return error or default)
FL-008: GET /fl?limit=999999    -> should cap at maximum or handle gracefully
SC-008: POST /sc with name=500 chars -> should accept or reject with clear error
```

### Malformed

**What it tests:** Invalid JSON, wrong content types, missing required fields, garbage data. These simulate clients that send broken requests, either due to bugs in the client code or deliberate fuzzing.

**Why it matters:** Malformed input probes ensure the harness does not crash, panic, or leak internal error details when receiving garbage. Every malformed request should receive a clean `{ok: false, err: "REQUEST.INVALID", msg: "..."}` response.

**Examples:**
```
FL-004: POST /fl/sn.probe/succeed/run with body "not json" -> should return error
SC-007: POST /sc with raw text body -> should return error
TR-005: POST /tr with raw text -> should return error
```

### Auth

**What it tests:** Authentication enforcement. Do protected endpoints reject unauthenticated requests? Do auth-exempt routes (like the health endpoint) work without tokens?

**Why it matters:** Authentication bugs are security vulnerabilities. An endpoint that should require authentication but does not is an open door for unauthorized access.

**How to test both modes:**
```bash
# With token (tests that authenticated requests succeed)
./simulator -mode probe -feature all -token "valid-token"

# Without token (tests that protected routes reject, auth-exempt routes accept)
./simulator -mode probe -feature all
```

### Traversal

**What it tests:** Path injection and directory escape attempts. These probes attempt to read files outside the intended scope by manipulating URL paths with `..`, URL-encoded characters, and other traversal techniques.

**Why it matters:** Path traversal is a critical security vulnerability. If any traversal probe succeeds (returns file contents it should not), it must be fixed immediately. These probes test both raw traversal (`../../etc/passwd`) and encoded traversal (`..%2F..%2Fetc%2Fpasswd`).

**Examples:**
```
CM-003: GET /cm/../../etc/passwd        -> must NOT return file contents
CM-004: GET /cm/..%2F..%2Fetc%2Fpasswd  -> must NOT return file contents
SRC-002: GET /src/../../etc/passwd      -> must NOT return file contents
KT-002: GET /kt/../../etc/hosts         -> must NOT return /etc/hosts
KT-003: GET /kt/sn/probe/pb/../../kit.yaml -> must NOT leak kit.yaml
```

**A traversal probe "PASS" means the harness correctly blocked the attempt.** A "FAIL" means the harness returned contents it should not have -- this is a security vulnerability that must be fixed immediately.

### State

**What it tests:** Operations that depend on system state: querying nonexistent resources, deleting already-deleted items, operating on resources that were just created or modified by another probe.

**Why it matters:** State-related bugs often manifest as panics, null pointer dereferences, or inconsistent error messages. A harness should return clean error responses for nonexistent resources, not crash or return confusing errors.

**Examples:**
```
FL-002: POST /fl/nonexistent.kit/noflow/run  -> should return {ok: false}
SC-005: DELETE /sc/probe_nonexistent_secret   -> should not panic
TR-002: GET /tr/nonexistent_trigger_id        -> should return clean error
```

### Concurrency

**What it tests:** Simultaneous requests, race conditions, and resource contention. Amplified by the `-concurrent` flag.

**Why it matters:** Concurrency bugs are difficult to reproduce in normal testing but common in production. They manifest as database locks, corrupted state, or duplicate operations. Running probes concurrently exposes these issues.

```bash
# Run 20 parallel flow executions to test for race conditions
./simulator -mode probe -feature flows -concurrent 20
```

### Format

**What it tests:** Response schema validation. Does every response conform to the API contract? Are required fields present? Is the JSON well-formed?

**Why it matters:** API consumers (especially AI agents) depend on consistent response formats. A response that is missing the `ok` field, returns non-JSON content, or uses a non-200 status code breaks the API contract.

**Examples:**
```
HL-004: GET /hl -> verify status, mode, ver fields exist
All probes implicitly check: HTTP 200, valid JSON, ok field present
```

---

## Activity Simulator (Dashboard Testing)

The simulator also has its original activity generation mode for testing the dashboard's live-logs view. This mode creates realistic-looking traffic patterns that exercise the harness's logging, execution, and webhook systems.

```bash
# Build the simulator
go build -o simulator ./cmd/simulator

# Run with default settings (medium intensity, 5 minutes)
./simulator

# Low intensity for 1 minute (background noise for dashboard testing)
./simulator -intensity low -duration 1m

# High intensity against a remote harness (stress testing)
./simulator -addr staging.example.com:8080 -intensity high -duration 10m
```

### Simulator Flags

```
Usage: simulator [flags]

Flags:
  -mode string         Mode: simulate|probe (default "simulate")
  -addr string         Harness address (default "localhost:8080")
  -intensity string    Activity intensity: low/medium/high (default "medium")
  -duration duration   How long to run (default 5m)
```

### What the Simulator Generates

| Action | Frequency | Description |
|--------|-----------|-------------|
| Webhooks | 40% | POST to `/wh/*` with random payloads and varying source IP headers |
| Flow runs | 30% | POST to `/fl/{id}/run` with randomized test parameters |
| HTTP logs | 30% | Simulated connector activity logged for dashboard observation |

### Intensity Levels

| Level | Rate | Use Case |
|-------|------|----------|
| `low` | 1 event every 5-10s | Background noise for dashboard testing, minimal resource usage |
| `medium` | 1 event every 1-3s | Normal development, realistic traffic patterns |
| `high` | 3-5 events/second | Stress testing, latency measurement, capacity planning |

---

## Autonomous Adversarial Testing (Agent Skill)

For AI-assisted development, the `/sn-go-adversarial` skill enables autonomous test-debug-fix cycles. When an agent (such as Claude) is given a directive like "test the webhook system," it performs a complete adversarial testing cycle without human intervention:

1. **Discovers** the API surface for the specified feature by reading handler code and route registrations
2. **Scaffolds** a test fixture kit (`sn.probe/`) in the test SRE if one does not already exist
3. **Generates** probes across all 8 categories, tailored to the specific endpoints
4. **Executes** probes via HTTP requests against the running harness
5. **Diagnoses** failures by reading the handler source code and correlating with the error response
6. **Fixes** bugs with minimal, focused patches to the handler code
7. **Re-probes** to verify that the fix resolved the issue without introducing new failures
8. **Reports** structured results with a summary table and detailed findings

### Using the Skill

The skill is invoked naturally through conversation:

```
User: "Test and debug the webhook system"
User: "Run adversarial tests on form submissions"
User: "Find bugs in the vault/secrets API"
User: "Comprehensive test of flow execution"
```

The agent handles the entire cycle autonomously. It reads source code to understand the implementation, generates appropriate probes, runs them, and fixes any issues it finds. This is particularly effective for catching edge cases that manual testing misses.

### Test Fixture Kit: sn.probe

The adversarial system uses a standardized test kit that provides predictable targets for probes. Having known-good and known-bad flows ensures that probe assertions can be precise (e.g., "this flow should always succeed" or "this flow should always fail with a specific error").

```
sn.probe/
  kit.yaml              # Kit manifest with namespace "sn" and name "probe"
  fl/
    succeed.lua         # Always succeeds, returns known data structure
    fail.lua            # Always calls error() with "deliberate_failure"
    timeout.lua         # Sleeps past the timeout limit to test timeout handling
    echo.lua            # Returns whatever parameters it receives (for input testing)
    state-rw.lua        # Tests ctx.get/ctx.set round-trip (state management)
    secret-read.lua     # Reads a known secret from vault (vault integration)
    emit-event.lua      # Emits a known event (event bus integration)
    slow.lua            # 5-second deliberate delay, then succeeds
  fm/
    simple.yaml         # Basic text form with name and email fields
    validated.yaml      # Form with required fields and regex validation
    protected.yaml      # Password-protected form
  pg/
    index.html          # Test page for kit UI serving probes
  pb/
    test.txt            # Static asset for /kt/sn/probe/pb/test.txt probes
```

This kit is auto-scaffolded by the agent when it runs the adversarial skill. You can also create it manually in your test SRE for use with the probe runner CLI.

### Agent Report Format

After completing a probe cycle, the agent produces a structured report:

```
## Adversarial Test Report: Webhooks

Date: 2026-02-28
Harness commit: a1b2c3d
Test SRE: /home/user/test-sre
Mode: debug

### Summary
| Category     | Probes | Pass | Fail | Fixed |
|--------------|--------|------|------|-------|
| Happy path   |      3 |    3 |    0 |     0 |
| Boundary     |      2 |    1 |    1 |     1 |
| Malformed    |      2 |    2 |    0 |     0 |
| Auth         |      3 |    3 |    0 |     0 |
| Traversal    |      2 |    2 |    0 |     0 |
| Concurrency  |      1 |    1 |    0 |     0 |
| State        |      2 |    2 |    0 |     0 |
| Format       |      2 |    2 |    0 |     0 |
| **Total**    | **17** |**16**|  **1**|  **1**|

### Failures Found & Fixed
1. PROBE-WH-007: 50MB payload caused OOM -> Added 10MB body limit in webhook router -> fixed

### Observations
- Webhook HMAC verification correctly rejects invalid signatures
- Rate limiting works but allows burst of 5 before throttling
```

---

## Integration with CI/CD

The probe runner is designed for CI/CD integration. The following examples show how to incorporate adversarial testing into your deployment pipeline.

### Basic Health Check (Post-Deployment Verification)

Run this script immediately after deploying a new version to verify the harness is healthy:

```bash
#!/bin/bash
# ci/probe-health.sh -- Run after deployment to verify basic health

set -euo pipefail

./simulator -mode probe -feature health -jsonl | tail -1 | python3 -c "
import sys, json
summary = json.loads(sys.stdin.read())
if summary['data']['failed'] > 0:
    print(f'FAILED: {summary[\"data\"][\"failed\"]} probes failed')
    sys.exit(1)
print(f'OK: {summary[\"data\"][\"passed\"]} probes passed')
"
```

### Full Regression Suite (Nightly Build)

Run the complete probe suite as part of a nightly build to catch regressions:

```bash
#!/bin/bash
# ci/probe-all.sh -- Nightly regression suite

set -e

echo "=== Sentinel Probe Suite ==="

# Start harness in background with a test SRE
sentinel harness start -p ./test-sre --daemon --no-input
sleep 3  # Wait for harness to initialize

# Run all probes with moderate concurrency
./simulator -mode probe -feature all -concurrent 5 -jsonl > results.jsonl

# Parse results
FAILED=$(grep '"result":"fail"' results.jsonl | wc -l)
ERRORS=$(grep '"result":"error"' results.jsonl | wc -l)
PASSED=$(grep '"result":"pass"' results.jsonl | wc -l)

echo "Results: $PASSED passed, $FAILED failed, $ERRORS errors"

# Stop harness
sentinel harness stop -p ./test-sre

# Fail the build if any probes failed
if [ "$FAILED" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
    echo "FAILURES:"
    grep -E '"result":"(fail|error)"' results.jsonl | python3 -m json.tool
    exit 1
fi

echo "All probes passed."
```

### Feature-Specific Gate (Pre-Merge Check)

Run probes for the specific feature area being changed before merging a pull request:

```bash
#!/bin/bash
# ci/probe-feature.sh -- Run before merging changes to a specific feature

FEATURE=${1:-"health"}  # Pass feature name as argument

./simulator -mode probe -feature "$FEATURE" -jsonl | tail -1 | python3 -c "
import sys, json
s = json.loads(sys.stdin.read())
failed = s['data']['failed']
if failed > 0:
    print(f'${FEATURE} probes: {failed} failures -- blocking merge')
    sys.exit(1)
print(f'${FEATURE} probes: all passed')
"
```

Usage:
```bash
# Before merging webhook changes
./ci/probe-feature.sh webhooks

# Before merging form changes
./ci/probe-feature.sh forms
```

### GitHub Actions Example

```yaml
name: Adversarial Probes
on:
  pull_request:
    branches: [main]

jobs:
  probe:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build
        run: |
          go build -tags dev -o sentinel ./cmd/sentinel
          go build -o simulator ./cmd/simulator

      - name: Start harness
        run: |
          ./sentinel sre init test-sre
          ./sentinel harness start -p ./test-sre --daemon --no-input &
          sleep 3

      - name: Run probes
        run: |
          ./simulator -mode probe -feature all -concurrent 5 -jsonl > results.jsonl
          FAILED=$(grep '"result":"fail"' results.jsonl | wc -l || true)
          if [ "$FAILED" -gt 0 ]; then
            echo "::error::$FAILED probe(s) failed"
            grep '"result":"fail"' results.jsonl | python3 -m json.tool
            exit 1
          fi

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: probe-results
          path: results.jsonl
```

---

## Combining Probe Runner and Simulator

A common development workflow uses both modes simultaneously:

```bash
# Terminal 1: Start harness
sentinel harness start -p ./my-sre

# Terminal 2: Run probes to verify everything works
./simulator -mode probe -feature all

# Terminal 3: Generate background activity for dashboard testing
./simulator -mode simulate -intensity medium -duration 30m

# Terminal 4: Watch live logs to observe both probe results and simulated activity
curl -N http://localhost:8080/lg/live
```

This setup lets you verify API correctness (probes), observe real-time behavior (simulator), and monitor the system's log output (live logs) all at once.

---

## Extending the Probe Runner

The probe runner is designed to be extended when new endpoints are added to the harness. To add probes for a new feature area, edit `cmd/simulator/main.go`:

1. **Add a new probe generation method** to the `ProbeRunner` struct:
   ```go
   func (r *ProbeRunner) fooProbes() []Probe {
       // Return a slice of probes for the "foo" feature
   }
   ```

2. **Register it in the `generateProbes()` switch statement** so it is included when `-feature foo` or `-feature all` is specified.

3. **Use the assertion helpers** to validate responses:

```go
func (r *ProbeRunner) fooProbes() []Probe {
    return []Probe{
        {
            ID: "FOO-001", Category: "happy", Method: "GET", Path: "/foo",
            Assert: assertOKResponse(),
        },
        {
            ID: "FOO-002", Category: "traversal", Method: "GET", Path: "/foo/../../etc/passwd",
            Assert: func(status int, body []byte, _ error) (bool, string) {
                if strings.Contains(string(body), "root:") {
                    return false, "path traversal succeeded -- SECURITY VULNERABILITY"
                }
                return true, ""
            },
        },
        {
            ID: "FOO-003", Category: "malformed", Method: "POST", Path: "/foo",
            Body: "not valid json",
            Assert: assertErrorResponse(),
        },
    }
}
```

### Assertion Helpers

| Helper | What It Checks | When to Use |
|--------|---------------|-------------|
| `assertHTTP200JSON()` | HTTP 200 + valid JSON (object or array) | For endpoints that return data without an `ok` field |
| `assertOKResponse()` | HTTP 200 + `{ok: true}` | For endpoints that should succeed |
| `assertErrorResponse()` | HTTP 200 + `{ok: false}` | For probes that should trigger an error (malformed input, nonexistent resource) |
| `assertOKWithField(f)` | HTTP 200 + `{ok: true, f: ...}` | For endpoints that should return a specific field |
| Custom function | Any custom validation logic | For traversal checks, specific error code validation, response body content checks |

---

## Error Codes Reference

Probes validate against these error codes from the API contract. When a probe expects an error response, it checks that the error code matches the expected value for that type of request:

| Code | Meaning | Typical Trigger |
|------|---------|-----------------|
| `AUTH.REQUIRED` | Bearer token missing | Request without Authorization header in production mode |
| `AUTH.INVALID` | Bad bearer token | Request with incorrect token |
| `AUTH.IP_DENIED` | IP not whitelisted | Request from non-whitelisted IP when CIDR filtering is configured |
| `REQUEST.INVALID` | Malformed request body | Invalid JSON, wrong content type |
| `REQUEST.MISSING` | Required parameter missing | POST without required fields |
| `RESOURCE.NOT_FOUND` | Entity does not exist | GET/DELETE for nonexistent ID |
| `RESOURCE.CONFLICT` | ETag mismatch | PUT with stale ETag (optimistic concurrency) |
| `SYSTEM.ERROR` | Internal server error | Unexpected failures in handler code |
| `SYSTEM.TIMEOUT` | Operation timed out | Flow execution exceeded timeout |
| `FM_NOT_FOUND` | Form not found | Request for nonexistent form stub |
| `FM_AUTH` | Wrong form password | Incorrect password for protected form |
| `VALIDATION` | Field validation failed | Form submission with invalid field values |
| `CMS.NOT_FOUND` | CMS slug not found | Request for nonexistent CMS entry |
| `CMS.UNAVAILABLE` | CMS cache not initialized | CMS request before cache is built |

For the complete and authoritative list, see `system-specs/errors.yaml`.

---

## Troubleshooting

### "Harness not reachable"

```
Harness not reachable at http://localhost:8080
```

The harness is not running, or it is running on a different port. Start it first and verify it responds:

```bash
sentinel harness start -p /path/to/sre
curl http://localhost:8080/hl
```

If it is on a different port:
```bash
./simulator -mode probe -addr localhost:9000 -feature health
```

### Probes Fail With "connection error"

The harness crashed or became unresponsive during probing. This often happens when running stress tests with high concurrency. Check the harness logs for panics or errors:

```bash
sudo journalctl -u sentinel --since "5 minutes ago"
```

Common causes:
- Concurrent stress probes overwhelming the harness (reduce `-concurrent`)
- A probe triggered a panic in handler code (this is itself a bug to fix)
- The harness ran out of file descriptors (increase `LimitNOFILE` in systemd service)

Reduce concurrency and re-run:
```bash
./simulator -mode probe -feature all -concurrent 1
```

### Traversal Probes Show "FAIL"

**This is a security vulnerability.** If a traversal probe fails, it means the harness returned file system contents it should not have. The probe's `detail` field explains what was returned. Check the probe detail, identify which handler is vulnerable, and fix it immediately. Common fixes include:
- Adding `filepath.Clean()` and checking for `..` in paths
- Ensuring all path operations are relative to the SRE root
- Using `filepath.Rel()` to verify the resolved path is within bounds

### Many "FAIL" on Auth Probes in Debug Mode

In debug mode (no tokens configured), authentication is relaxed to IP-whitelist only. Auth probes that expect token rejection will see different behavior. This is expected. To test auth behavior accurately, configure tokens and use the `-token` flag:

```bash
# Check your mode
curl -s http://localhost:8080/hl | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Mode:', d.get('mode', 'unknown'))
"
```

### JSONL Output Has Unexpected Format

Ensure you are using the `-jsonl` flag and separating stdout from stderr:

```bash
# Correct: redirect only stdout, discard stderr
./simulator -mode probe -feature health -jsonl 2>/dev/null > results.jsonl

# Wrong: this mixes stderr messages into the JSONL output
./simulator -mode probe -feature health -jsonl &> results.jsonl
```
