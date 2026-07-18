# Security S8 retention, database recovery, and maintenance

Pocket Lab Lite Security uses SQLite as the authoritative lifecycle store. Phase S8 extends the existing worker-owned Backup & Restore system; it does not create a second recovery path.

## Repository audit classification

| Area | Classification | Current shape |
| --- | --- | --- |
| Security SQLite schema and migrations | verified-existing | Migrations `0001`–`0003` already store Security runs, progress, findings, tools, evidence references, snapshots, revisions, and metadata. |
| Restic Backup & Restore | verified-existing | Worker-owned backup, verification, restore preview, checkpointing, health validation, receipts, and recovery UI already exist. |
| Progress-event retention | verified-existing | Bounded progress pruning exists and remains reused. |
| WAL pressure diagnostics and long-duration gates | verified-existing | Phase 5 gate infrastructure and WAL pressure testing remain the production-gate foundation. |
| Full Security run retention | patch-provided | Configurable protected-run calculation, dry-run/apply, bounded deletion, quick check, and maintenance records. |
| First-class SQLite online backup | patch-provided | Validated database packages are included in the existing recovery architecture and restic staging. |
| Atomic SQLite restore and rollback | patch-provided | Preview, explicit confirmation, maintenance marker, validated rollback copy, atomic replace, parity check, and automatic rollback. |
| Evidence-file deletion | planned, disabled | S8 generates a sanitized orphan manifest but never deletes evidence files. |
| Termux and Ubuntu S8 qualification | unvalidated until run | The shared long-gate runner now contains an S8 qualification gate for both platforms. |

## Additive migration plan

Phase S8 adds only `0004_security_maintenance.sql`. Historical migrations are unchanged.

The migration adds metadata tables for:

- bounded maintenance runs;
- verified database backup records;
- database restore records.

It deliberately does not duplicate Security runs, progress, findings, tool results, evidence references, profile snapshots, or existing restic manifests. The migration is idempotent, checksum-protected, valid for empty and populated databases, and preserves S6/S7 data.

Restore compatibility fails closed when:

- the backup schema is newer than the running Pocket Lab version;
- a migration is unknown;
- a migration name or checksum differs;
- a required core table is missing;
- integrity or quick checks fail.

## Runtime flow

```text
Recovery UI
→ FastAPI /api/lite/recovery/*
→ NATS/JetStream command
→ worker
→ retention / WAL checkpoint / SQLite online backup / atomic restore
→ sanitized maintenance and recovery evidence
→ FastAPI
→ Recovery UI
```

During database restore, the maintenance marker is understood by FastAPI middleware, the worker, and the core supervisor. New writes are paused, unrelated worker commands are deferred, and the supervisor does not fight the intentional maintenance window.

## Retention policy

Defaults are environment-backed:

```text
POCKETLAB_SECURITY_RETENTION_MAX_RUNS=200
POCKETLAB_SECURITY_RETENTION_MIN_PER_PROFILE=20
POCKETLAB_SECURITY_PROGRESS_RETENTION_DAYS=30
POCKETLAB_SECURITY_PROGRESS_MAX_ROWS=20000
POCKETLAB_SECURITY_FAILED_RETENTION_DAYS=90
POCKETLAB_SECURITY_RETENTION_BATCH_SIZE=50
```

Protected runs include active runs, minimum profile/app history, current snapshots, finding-delta comparison runs, and recent failed or cancelled runs. Child rows follow existing foreign-key rules. Evidence files remain untouched; an orphan-evidence manifest records referenced, unreferenced, missing, and hash-mismatched evidence.

## WAL policy

Normal maintenance uses `PRAGMA wal_checkpoint(PASSIVE)`. `TRUNCATE` is allowed only through an explicitly confirmed worker-owned maintenance command or the restore workflow, after writer quiescence and active-scan checks. Pocket Lab never manually removes WAL or SHM files.

## Database backup package

Each database package contains a consistent online SQLite backup plus schema, migration, per-artifact hashes, a package fingerprint, evidence-manifest, restore-preview, receipt, and sanitized manifest metadata. A package is marked verified only after independent integrity, quick-check, migration, core-table, database-hash, artifact-hash, and package-hash validation. Backup and restore share a crash-safe operating-system file lock, so concurrent recovery operations fail safely instead of racing.

## Restore policy

Restore is non-destructive until a ready preview and explicit confirmation exist. The worker validates the selected package, enters maintenance, checkpoints safely, creates and validates a rollback copy, stages and validates the replacement, fsyncs and atomically replaces the database, refreshes Security projections, checks JSON/SQLite parity, and leaves the rollback copy available. A post-replacement failure triggers automatic rollback and records a sanitized failed-restore audit row after the prior database is recovered.

The Recovery first paint stays compact with **Back Up Pocket Lab** and **Manage**. Database backup history and technical diagnostics are lazy-loaded in the existing responsive sheet: bottom sheet on mobile and right-side panel on desktop.

## Validation

Development validation:

```bash
task lite:security:s8:check
```

Destructive production qualification requires explicit opt-ins and should run first on Ubuntu, then on the Termux server phone. See the S8 gate commands in the implementation handover; gate evidence is written through the existing long-duration report framework.
