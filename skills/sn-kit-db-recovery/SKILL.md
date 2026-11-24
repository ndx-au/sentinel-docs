---
name: sn-kit-db-recovery
description: Back up a Sentinel kit SQLite database and prove recovery in an offline drill SRE, or restore it to an explicitly selected recovery target.
---

# Recover a kit database

Identify the source SRE and kit ID. This workflow covers the kit-scoped SQLite database. PostgreSQL and folder backup plans have their own history under `sentinel backup runs -p "$SOURCE"`. A whole-SRE recovery also needs the deployed kit files, configuration, vault and any other state used by that workload. For encrypted state migrations, consult the [offline migration runbook](https://docs.ndx-sentinel.com/sqlcipher-offline-migration).

## Capture a recovery point

Use absolute paths. Select a new backup file in access-controlled storage outside the served and watched directories. Check that `db status` reports the expected database. If the database is missing, resolve the source before continuing.

```sh
sentinel db status --kit "$KIT" -p "$SOURCE"
sentinel db backup --kit "$KIT" -p "$SOURCE" --output "$BACKUP"
```

Record the kit revision, backup time, size and checksum. For an existing backup, verify its recorded checksum when available. Choose a read-only application check with a known expected value for that recovery point, such as the presence of a particular completed batch. Counts from a moving live database can legitimately differ.

## Prove the restore

Use a separate initialized SRE containing the matching kit revision. Verify the resolved target and its data directory are distinct from the source, including any shared mounts. Keep the target harness and other writers stopped. With the default layout, create the target's `.sentinel/data/` directory if missing, owned by the intended service account. Restore can fail when this parent directory is absent.

```sh
sentinel db restore --kit "$KIT" -p "$TARGET" --from "$BACKUP"
sentinel db query 'PRAGMA integrity_check' --kit "$KIT" -p "$TARGET"
```

Require an integrity result of `ok`, then use `sentinel db query` against the same target for the application check. Record expected and actual values, backup identity, and elapsed recovery time. Keep the drill offline when SQL suffices. Starting a restored kit can resume schedules and external writes.

For an explicitly requested in-place recovery, confirm the recovery point and data-loss window with the operator, quiesce the service through its supervisor, verify writers have stopped, and preserve the current database before replacing it. Run the same offline checks. Resume the supervised service only after they pass and verify a read-only workload signal. If verification fails, keep writers stopped and preserve both recovery points for diagnosis. [CLI reference](https://docs.ndx-sentinel.com/cli-reference)
