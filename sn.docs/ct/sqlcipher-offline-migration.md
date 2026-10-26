---
title: "Offline SQLCipher migration"
description: "Convert verified copies of legacy plaintext state or dashboard databases without weakening encrypted startup."
type: Guide
tags: [security, storage, recovery]
status: draft
---

<!-- ndx-ste-mode: description -->

# Offline SQLCipher migration

This procedure prepares an encrypted copy. It does not install that copy or
approve a production change. Keep the affected service stopped during backup,
conversion, installation and validation. Obtain the service owner's approval
before an outage. Test the procedure on disposable data first.

Use the separate [rollout checklist](/sqlcipher-rollout-checklist) for installation.
Do not disable encryption or add plaintext fallback when startup rejects a file.
Never run the converter against a live database. It cannot determine whether a
path names a disposable copy; the operator must establish that boundary.

## Identify the store

Inventory paths from the intended instance's configuration and service identity.
Do not search unrelated home directories or customer volumes.

| Store | Location to verify | Treatment |
|---|---|---|
| Harness state | `<SRE>/<data_dir>/state.db`; `data_dir` defaults to `.sentinel` | Convert only an existing plaintext copy when `state.encrypt_db` is to be enabled. Encryption remains optional where explicitly configured off. |
| Dashboard | `<service home>/.sentinel/dashboard.db` | Convert an existing plaintext copy before using the corrected encrypted dashboard. |
| Vault | Configured vault database | Excluded. Values already use vault encryption; do not convert the file with this procedure. |
| Kit SQLite, content caches, RAG/session stores, PostgreSQL or MariaDB | Subsystem configuration | Excluded. Each needs its own assessment and procedure. |

Already encrypted databases, rekey, SQLCipher format upgrades, virtual or extension
tables, hidden columns and unsupported newer schemas need a separate review.
A logical verification mismatch stops conversion. Do not remove the check.

## Prepare recovery and keys

1. Record the current and target executable versions, configuration, service
   account, database paths and key source in a restricted change record.
2. Stop all writers, scheduled jobs, workers and service auto-restart. Verify that
   they have stopped. Use the source-compatible SQLite tooling to checkpoint WAL,
   check integrity and close all connections. If checkpoint or integrity fails,
   stop and investigate; do not delete sidecars to make a check pass.
3. Preserve the complete recovery set, including any required WAL/journal files,
   prior executable and configuration, ownership information and recovery keys.
   A copy of a running main database alone is not a verified backup.
4. Restore a test copy from that recovery set. Obtain two independent regular,
   byte-identical, checkpointed plaintext copies: one conversion input and one
   verified backup copy. Both must have no `-wal`, `-shm` or `-journal` sidecar.
   Keep the original recovery set separate and unchanged.
5. Confirm the target build has working CGO/SQLCipher support. Validate the exact
   target key source and the service's ability to retrieve it after restart.
   State uses `state.state_passphrase`, or the vault passphrase when that setting
   is empty and state encryption is enabled. Do not put these values in Git,
   issue bodies, shell arguments or command logs.
6. Dashboard currently uses the fixed compatibility passphrase defined by the
   target build. That key provides an OS-permission boundary, not independent key
   custody. The supplied conversion key must match the target build. A successful
   conversion with an arbitrary key does not prove runtime compatibility.

Use an operator-owned private working directory, restrictive permissions and a
filesystem supporting hard links and directory fsync. The converter refuses
symlinks and path aliases. It does not protect against another process with the
same OS privileges changing the working directory.

## Convert the disposable copies

Use the reviewed `sqlcipher-migrate` tool built from the same source and linked
SQLCipher implementation as the target release. The tool is currently an engineering
utility; verify its build provenance and availability before scheduling an outage.
Do not substitute an arbitrary online conversion service.

Load the target passphrase into a dedicated environment variable using approved
secret delivery or protected interactive input with echo disabled. Disable shell
tracing. The following command contains only the variable's name, never its value:

```sh
sqlcipher-migrate \
  --source-copy /private/migration/source-copy.db \
  --backup-copy /private/migration/verified-backup-copy.db \
  --output /private/migration/new-encrypted.db \
  --key-env SENTINEL_MIGRATION_KEY
```

All paths are examples in a private working directory. Supply explicit copy paths.
Output must not exist. The tool does not replace an existing file, install an
instance or choose a live path. Unset the temporary key variable afterward.

Success requires exit code zero and a JSON evidence record containing digests and
counts. Retain that record in restricted evidence storage. It contains no row data
or key, but digests and counts may still be sensitive.

The converter checks both inputs, uses SQLCipher export, preserves and compares
schema objects, typed rows, sequences and version metadata, and checks integrity
and foreign keys. It reopens output through the production encryption factory,
rejects a wrong key and an unkeyed schema read, checks checkpoint and close, then
syncs and publishes a new file without replacement. Input and backup hashes must
remain unchanged. No failed path falls back to plaintext.

## Interruption and recovery

A failure before publication leaves no installed database. Keep the recovery set
and copies unchanged. An abrupt stop can leave a private `.sqlcipher-copy-*`
staging directory. Treat its contents as sensitive. The owner must inspect or
quarantine it before removal. Rerun from the verified copies into a fresh output.
Do not reuse partial output or remove live WAL files.

An error after publication or during directory fsync can leave a verified output
while reporting failure. Do not retry over it. Inspect the evidence and file in
the private working area, then use a fresh output name if conversion is repeated.
Unsupported filesystem durability operations must fail; do not bypass them.

## Installation, downtime and rollback

Only the approved rollout process may install the verified result. While the
service remains stopped, preserve the prior installation and recovery set, install
the encrypted output with the intended ownership and mode, deliver the matching
key, and start the exact target binary. Validate normal state/dashboard operations,
key failures, logging and restore access before reopening traffic and jobs.

Expected downtime includes stopping and checkpointing, backup and restore checks,
copy/export/verification, installation and application smoke tests. Measure this on
a representative nonproduction copy; there is no universal fixed outage duration.
The full typed comparison uses memory proportional to row digests.

Before installation, rollback requires no database replacement because conversion
has not changed either input. After installation, keep all writers stopped and
restore the complete verified recovery set with its compatible prior binary,
configuration and key. Never make the new binary accept plaintext to roll back.
If writes occurred after cutover, obtain an explicit reconciliation or data-loss
decision before restoring an older backup. Do not silently discard those writes.

Tested engineering failures include a process interruption during export, a SQLite
page-limit/full failure, and injected checkpoint, close and sync errors. These do
not prove physical power-loss recovery or every operating system/filesystem. Key
custody, real restore exercises, runtime compatibility, capacity and rollout
approval remain the deployment owner's responsibility.
