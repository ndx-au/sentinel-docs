---
title: "SQLCipher rollout checklist"
description: "Operator approvals and verification required before installing an encrypted database copy."
type: Guide
tags: [security, storage, release]
status: draft
---

<!-- ndx-ste-mode: description -->

# SQLCipher rollout checklist

Use this checklist with the [offline migration runbook](/sqlcipher-offline-migration).
A conversion test does not authorise installation or customer changes. Record
owner names, approvals, timestamps and evidence in the deployment's restricted
change system. This document records no completed operational approval.

## Before the maintenance window

- [ ] Identify affected state/dashboard stores from configuration and the service
  account. Exclude vault, content, RAG/session and kit stores from this procedure.
- [ ] Approve the change, expected outage, communications, rollback deadline and
  the owner who can stop or restore the service.
- [ ] Validate a representative nonproduction conversion and restore using the
  exact target binary, key source, SQLCipher implementation and filesystem.
- [ ] Verify archive checksums and release provenance. Confirm native CGO/SQLCipher
  functionality; a successful help/version command alone is insufficient.
- [ ] Verify source format/schema support, disk and memory headroom and measured
  outage duration. Check hard-link and directory-sync support.
- [ ] Confirm key custody, retrieval by the service account, escrow/recovery,
  rotation dependencies and dashboard fixed-key limitations. Keep values out of
  command logs and the change record.
- [ ] Define recovery-set retention, access controls, encrypted backup storage and
  disposal. Preserve the prior binary and configuration.

## During the approved outage

- [ ] Stop all writers, workers and scheduled jobs; disable automatic restart.
- [ ] Checkpoint and integrity-check with source-compatible tooling. Resolve any
  WAL/journal condition; never remove a sidecar to bypass a check.
- [ ] Create and restore-test the complete backup. Prepare two independent,
  checkpointed, byte-identical disposable plaintext copies in a private directory.
- [ ] Run the converter with explicit copies, an absent output and a protected
  key environment variable. Require exit zero and retain redacted evidence.
- [ ] Check input/backup hashes, logical equality, output encryption, wrong-key
  and unkeyed rejection, output permissions and absence of output sidecars.
- [ ] Inspect any failed/partial attempt. Never install it or overwrite an existing
  output. Use the documented recovery procedure.
- [ ] Obtain the operator's final installation approval with the verified result
  available for review. Preserve the recovery set before installing output.
- [ ] Install with the intended service identity, private directories and 0600 file
  mode. Deliver the matching runtime key and configuration.
- [ ] Start the exact target binary. Exercise state/dashboard read/write operations,
  authentication, logs and monitoring before reopening traffic and jobs.

## Close or roll back

- [ ] Record successful smoke/restore evidence and the decision to reopen traffic.
- [ ] If validation fails, stop writers and restore the full recovery set with its
  compatible prior binary/configuration/key. Keep fail-closed encryption enforced
  in the new version.
- [ ] If cutover accepted writes, approve reconciliation or data loss before any
  rollback that replaces them with an older backup.
- [ ] Remove temporary key variables. Retain sensitive staging files/backups under
  restricted access until their approved cleanup date; delete only reviewed copies.
- [ ] Record the final owner decision, restore point, observations and follow-up
  actions. No certification or attestation follows from completing this checklist.
