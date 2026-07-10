# Pocket Lab Lite Security SQLite Design Lock — S0–S2

**Status:** Patch-provided design lock. Repository findings below are verified against the uploaded repository snapshot. Runtime behavior on the server phone remains unvalidated until the validation commands are run there.

## Scope

This document locks the first SQLite increment to:

- **S0:** repository inventory and design constraints;
- **S1:** backend-only SQLite connection, migration, schema, and health primitives;
- **S2:** an inactive Security repository, non-destructive legacy import, and optional shadow comparison.

S3 dual-write, SQLite-backed API reads, SQLite dedupe authority, retention jobs,
backup/restore workflow integration, and frontend changes are intentionally out
of scope.

## Verified current persistence flow

The active Security store remains JSON under `POCKETLAB_STATE_DIR`:

```text
$POCKETLAB_STATE_DIR/security/security_state.json
$POCKETLAB_STATE_DIR/security/runs/<run_id>.json
$POCKETLAB_STATE_DIR/security/evidence/<run_id>/*.json
$POCKETLAB_STATE_DIR/security/compact/*.json
```

`api_fastapi/services/lite_security_evidence.py` owns path creation, safe run-id handling, atomic JSON writes, redaction, state/run reads, evidence writes, compact reads, and bounded run listing.

`api_fastapi/services/lite_security.py` owns:

- default/current Security state;
- API-side queued-run recording and rollback;
- worker-side running, intermediate, and terminal state writes;
- Quick, Full, and App scan execution;
- compact summary/freshness/profile/history/progress/details projections;
- FastAPI memory caches;
- revision/ETag material;
- active-run and recent-completion dedupe views;
- Security SSE event payloads.

`api_fastapi/routers/lite.py` records `queued` before publishing `pocketlab.commands.lite.security.scan`, removes the queued record when publication fails, and continues to expose the established Security API surface.

`api_fastapi/services/domain_commands.py` handles the worker command and calls `lite_security.run_security_scan()` through `asyncio.to_thread`. `runtime/workers/pocketlab_worker.py` remains the durable NATS/JetStream consumer.

The verified Lite startup script launches the Python worker as PM2 process
`pocket-worker` and the FastAPI service as `pocket-api`. Both inherit the
backend state-directory environment; neither process is replaced or bypassed
by the SQLite foundation.

## Verified writers and readers

### API-process writers

- `POST /api/lite/security/check`
- backward-compatible `POST /api/lite/security/scan`
- `POST /api/lite/security/apps/{app_id}/check`
- `lite_security.record_queued_run()` before NATS publication
- `lite_security.discard_queued_run()` when publication fails

### Worker-process writers

- `domain_commands.handle_lite_security_scan()`
- `lite_security.mark_running()`
- intermediate `_write_intermediate_running_state()` calls
- Quick, Full, and App terminal run writers
- `lite_security_evidence.write_run()`
- `lite_security_evidence.write_evidence()`
- `_write_security_state()` plus compact projection writes

### Readers

- `/api/lite/security/summary`
- `/api/lite/security/freshness`
- `/api/lite/security/profiles/{profile}`
- `/api/lite/security/history`
- `/api/lite/security/details/{run_id}`
- `/api/lite/security/evidence/{run_id}/summary`
- `/api/lite/security/events`
- `/api/lite/security/progress`
- `/api/lite/security`
- `/api/lite/security/runs/{run_id}`
- `/api/lite/security/evidence/{run_id}`
- Security frontend TanStack Query, ETag, SSE, and polling-fallback paths

## Verified lifecycle and transition model

| State | Current meaning | Active | SQLite S2 normalization |
| --- | --- | ---: | --- |
| `queued` | FastAPI accepted and recorded the request before NATS publish | yes | `queued` |
| `running` | worker owns scan execution | yes | `running` |
| `succeeded` | complete result and evidence saved | no | `succeeded` |
| `degraded` | complete with partial/review results | no | `degraded` |
| `failed` | failure representation supported by progress/timeline contracts | no | `failed` |
| aliases such as `accepted`, `working`, `in_progress` | supported by live progress/SSE contracts | yes | retained as active S2 statuses |
| `completed`, `success`, `done` | compatibility aliases | no | normalized to `succeeded` |
| `cancelled` / `canceled` | stream/repository compatibility state | no | `cancelled` |

The current production writer primarily persists `queued`, `running`, `succeeded`, and `degraded`. SQLite S2 accepts the wider established progress vocabulary so later phases can migrate without schema churn.

## Verified normalization and dedupe

- Profiles are normalized by `lite_security_policy.normalize_scan_profile()` to `quick`, `full`, or `app`.
- App Check currently normalizes through `lite_security_policy.normalize_app_id()` and supports the verified `photoprism` target.
- Run ids are sanitized by `lite_security_evidence.safe_run_id()` and bounded to 120 characters.
- Existing API dedupe is JSON/compact-read based:
  - `active_scan_state()` prevents another matching active profile/app request;
  - `recent_completed_scan_state()` suppresses a repeat for 45 seconds by default;
  - the low-power product currently checks active state before issuing another scan.
- S2 adds inactive transactional reservation primitives but does **not** make them authoritative.

## Verified history, cache, freshness, and streaming behavior

- JSON run listing scans up to 40 run files to build history and returns a default 20-entry history.
- split history defaults to 20 and is bounded by the configured maximum.
- no repository-owned Security retention/deletion job was found; current bounds are read/query bounds rather than destructive retention.
- compact files include summary, freshness, progress, history index, profile-latest, coverage, per-profile views, and run details.
- FastAPI memory caches use shorter TTLs while Security is live.
- compact responses use revision-derived ETags and support `If-None-Match` / `304`.
- SSE `/security/events` emits sanitized bounded progress/revision fields; polling `/security/progress` remains the fallback.

## Verified privacy and backup constraints

- `lite_security_policy.redact_value()` is the centralized recursive redaction boundary.
- JSON evidence writes are redacted before persistence.
- scanner skip patterns now exclude `*.db`, `*.sqlite`, `*.sqlite3`, and their WAL/SHM companions for Quick, Full, and App checks.
- the current Lite backup policy enumerates selected state files/directories and does not yet explicitly include the Security JSON tree or the new SQLite database. SQLite online backup/restore integration is therefore **planned**, not implemented in S0–S2.

## Verified state-directory, tests, and inspection tooling

- `POCKETLAB_STATE_DIR` resolves through `runtime/core/control_plane_core.py`; when unset it defaults to `<POCKETLAB_BASE_DIR>/state`.
- Security persistence/progress coverage is spread across `tests/backend/test_lite_security.py`, `tests/backend/test_lite_api.py`, and the F3/F7/F9/F11/F12-F14 Security contract files.
- `scripts/dev/check-lite-api.sh` exercises the public Lite Security read endpoint through FastAPI.
- no existing repository-native script was found that initializes, inspects, imports, or compares an application SQLite Security store; the S1/S2 operational scripts fill that verified gap.

## SQLite design lock

### Database path

```text
$POCKETLAB_STATE_DIR/pocketlab-lite.sqlite3
```

Optional override:

```text
POCKETLAB_LITE_DB_PATH
```

The implementation rejects Android shared-storage paths and applies best-effort `0700` parent / `0600` database permissions.

### Schema ownership

SQLite is backend-only. The Python FastAPI/worker code owns access through standard-library `sqlite3`. The browser, React, Node build tooling, Caddy, and NATS do not access the database.

Tables introduced in migration `0001_security_store.sql`:

- `schema_migrations`
- `security_scan_runs`
- `security_scan_progress_events`
- `security_scan_findings`
- `security_scan_evidence_refs`
- `security_scan_tool_runs`
- `security_profile_snapshots`
- `domain_revisions`
- `security_store_metadata` for bounded import/shadow provenance

`operation_leases` is intentionally missing in S1. The active-key uniqueness constraint is the initial transactional primitive.

### Connection policy

Every application connection configures and verifies:

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 20000;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA wal_autocheckpoint = 1000;
```

Only bounded, allow-listed environment overrides are accepted. Connections are per operation; no cross-thread/process global cursor is introduced.

The connection package includes an online-backup primitive so a later Recovery
phase can use SQLite's consistent backup API instead of copying live WAL/SHM
files. The current Backup & Restore workflow is not changed by S0–S2.

### JSON compatibility strategy

Default production behavior remains:

```text
POCKETLAB_LITE_SECURITY_STORE_MODE=json
POCKETLAB_LITE_SECURITY_SQLITE_SHADOW_READ=0
```

The supported rollout values are validated as `json`, `dual`, and `sqlite`, but S0–S2 implements no dual writes and no SQLite read cutover.

The importer:

- reads `security_state.json`, `runs/*.json`, and evidence references;
- never rewrites or deletes source JSON/evidence;
- upserts by stable run id;
- normalizes profiles, app ids, statuses, timestamps, findings, tools, and evidence paths;
- records bounded provenance;
- can be previewed and rerun;
- skips an unchanged source checksum unless an operator explicitly requests a forced re-import;
- hashes only explicitly requested small evidence files.

Optional shadow mode independently compares bounded JSON and SQLite projections, records only checksums and mismatch field names, and never changes the JSON-backed API response.

## Startup decision and operational hooks

Automatic API/worker startup migration was intentionally not added in S0–S2.
The current PM2/bootstrap paths start API and worker processes independently,
and production Security operation must remain JSON-backed even if SQLite is
unavailable. Instead, the patch supplies explicit, idempotent hooks:

```text
scripts/lite/security-db-migrate.py
scripts/lite/security-db-check.py
scripts/lite/security-db-import.py
scripts/lite/security-db-compare.py
```

Repository construction also applies migrations, which is used only by tests,
tools, and opt-in shadow comparison in this phase. A later rollout phase can
add bounded startup integration after server-phone validation.

## Migration and rollback constraints

- migrations are ordered, checksummed, transactional, and idempotent;
- an applied checksum/name change fails closed;
- a schema newer than the runtime fails closed;
- no destructive down migration exists;
- current JSON files remain the rollback source;
- disabling shadow mode and keeping store mode `json` restores the pre-cutover behavior;
- database/WAL/SHM files must not be manually removed while processes may be connected.

## Security and privacy rules

- parameterized SQL for all data values;
- centralized redaction before writes;
- bounded JSON metadata;
- no raw scanner output;
- no environment-file contents;
- no tokens, passwords, API keys, private keys, NATS credentials, or bootstrap secrets;
- relative evidence paths only;
- no unrestricted user-media paths;
- logs contain error types/run ids, not sensitive payloads.

## Intentionally out of scope for S0–S2

- switching `/api/lite/security/*` reads to SQLite;
- worker/API dual-write;
- SQLite authoritative dedupe;
- scan execution in FastAPI;
- NATS replacement;
- frontend or PWA changes;
- retention/VACUUM/checkpoint scheduling;
- SQLite online backup and restore integration;
- stale lease recovery;
- schema downgrade/destructive migration;
- release/tag generation.
