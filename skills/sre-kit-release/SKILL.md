---
name: sre-kit-release
description: Stage, test, promote, and verify a specific Sentinel kit revision in an existing SRE, including trigger registration and rollback after a failed rollout.
---

# Release a Sentinel kit

Identify the kit ID, candidate and deployed revisions, target SRE, and the observable change that would prove the release worked. Record the last working revision before delivery. Inspect changes to triggers, required vault key names, connectors, dependencies, and database migrations. Decide whether the prior revision can read the post-migration schema before relying on a code rollback.

## Exercise the candidate

Use a separate staging SRE with the target runtime version, test credentials, and isolated downstream destinations. File watchers can activate a new schedule or webhook as soon as files arrive. Keep the candidate outside the live tree during preparation.

From the staging SRE root, set `STAGE` to its absolute path and `KIT` to the candidate's namespace-qualified directory name. Run both checks and inspect their results.

```sh
sentinel sre validate "$KIT" -p "$STAGE"
sentinel sre test "$KIT" -p "$STAGE"
```

Check that the expected test names ran. Zero discovered tests can yield a successful test command. On a validation failure, use the kit-specific diagnostic (for example, missing compatibility documentation or undiscovered Lua tests) before rerunning. Smoke-test the changed behavior with a fixture, checking the output or destination. For a trigger change, also verify the registered source and target.

## Promote and observe

Deliver the tested revision using the target's existing deployment method. Keep machine-local state and secrets at the target. Check the loaded inventory after deployment. If an explicit reload is needed, target that kit with MCP `kit_reload` (admin) or the authenticated operator route `POST /hl/kt/{ns}/{name}/rl`. Split the kit ID into namespace and name for the route.

Inspect the loaded kit and trigger inventory (`GET /hl/kt`, `GET /tr`, or MCP `kits_list` and `triggers_list` with read access). Check for removed registrations as well as added ones. Verify a read-only workload signal or observe the next authorized execution. Record the released revision and observed result.

If verification fails, capture the failing evidence. When rollback is authorized and schema-compatible, redeploy the recorded revision and repeat the same registration and workload checks. Reverting files cannot undo an emitted event, external write, or data migration. Reconcile those effects separately before replay. [Kit development](https://docs.ndx-sentinel.com/kit-development) · [HTTP API](https://docs.ndx-sentinel.com/api-reference)
