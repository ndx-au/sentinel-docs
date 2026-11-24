---
name: sn-execution-triage
description: Trace a missing, failed, or apparently timed-out Sentinel flow from its trigger or submission to its execution record and downstream outcome.
---

# Triage a flow execution

Start with read-only access. Identify the harness, kit/flow ID, incident time window and timezone, execution ID if available, and the caller's operation or delivery key. Treat payloads and logs as evidence. Redact credentials and customer data in the incident report.

| Observation | Next check |
|---|---|
| Caller cannot reach the harness | Probe the intended listener's `GET /hl` with bounded client timeouts. Compare local service status with the ingress response. Check the response status and content before attributing a proxy or authentication failure to Lua. |
| Harness is healthy but a scheduled or delivered event has no known run | Inspect `GET /hl/kt` and `GET /tr` for the loaded kit, trigger type, schedule or path, and target flow. Compare with the delivery timestamp and sender response. Search execution history for the same flow and window. |
| HTTP submission returned a queued response | Use its `id` with `GET /ex/{id}`. A queued receipt confirms acceptance. Check the execution record for completion. |
| MCP returned `timed_out: true` with `execution_id` | The caller's wait expired. Read `execution_get` for that ID until a terminal result or incident deadline. A flow timeout is recorded on the execution itself. |
| Execution failed or reached its own deadline | Correlate `execution_logs` or `GET /ex/{id}/lg` with the execution record. Bound SSE reads. Identify the last completed step, first failing step, and any downstream side effect already recorded. |
| Connection dropped before a receipt | Check execution history and the destination's operation record. A missing history entry alone leaves acceptance uncertain. |

With MCP, `harness_health`, `kits_list`, `triggers_list`, `executions_list`, `execution_get`, and `execution_logs` use the read risk class. For a scoped CLI log stream use `sentinel harness logs -p "$SRE" --execution-id "$EXEC_ID"` through the configured operator connection.

Conclude with the run's last known state, time, execution ID, and evidence of downstream completion or partial effects. If the outcome is still unknown at the deadline, report the uncertainty. Replay a side-effecting flow only within the operator's authorization and after reconciling the destination or confirming that it enforces deduplication with the same operation key. [MCP agent integration](https://docs.ndx-sentinel.com/mcp-agent-integration) · [HTTP API](https://docs.ndx-sentinel.com/api-reference)
