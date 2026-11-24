---
name: sn-harness-deploy
description: Bring a new or existing Sentinel Runtime Environment online on a host or in a container and verify the intended harness, kits, and service endpoint.
---

# Deploy a Sentinel harness

Identify the release, intended absolute SRE path, service account, listener, and process owner (foreground shell, service manager, or container). Resolve the path as the account that will run the harness. Multiple SREs can share a repository. Check the current listener and supervisor before starting a process.

1. Select the Sentinel release artifact for the host OS and architecture through the operator's release channel. Check its published verification material and run `sentinel version -p "$SRE"`. For an existing service, compare its configured executable or image with the one you inspected.
2. For an existing SRE, locate its `sentinel.yaml` and inspect the intended kit revisions. For a new bare SRE, run `sentinel sre init -p "$SRE" --minimal --no-input` **from the intended repository root**. Init also writes repository-level files in the current directory. If scaffold files conflict, inspect the files before proceeding. A bare scaffold can legitimately contain zero kits.
3. Check the machine-local `.sentinel/` configuration, storage permissions, configured port, and required vault inputs under the service identity. Supply credentials through the deployment's secret mechanism. In containers, persist the SRE and runtime state across replacement. Docker access is optional unless the workload manages containers. [Container deployment](https://docs.ndx-sentinel.com/docker-and-containers)
4. Review enabled kits and their cron, event, and webhook effects before startup. Use the existing supervisor's start action, or `sentinel harness start -p "$SRE" --port "$PORT"` for a foreground launch. Use the agreed port and bind configuration. If startup fails, read that process's startup logs before attempting a second launch.
5. Check `sentinel harness status -p "$SRE" --port "$PORT"` and the configured listener's `GET /hl`. Compare `GET /hl/kt` with the expected inventory using the deployment's authenticated operator access. For a serving workload, request one known read-only route through its intended ingress and check its content. A healthy listener with the wrong kit inventory can indicate a different SRE.

Record the binary version, SRE, process owner, listener, loaded kits, and the result of the workload check. If the local check succeeds and ingress fails, investigate the proxy target, TLS, and route mapping before restarting the harness. [Getting started](https://docs.ndx-sentinel.com/getting-started) · [Harness HTTP routes](https://docs.ndx-sentinel.com/harness-http-routes)
