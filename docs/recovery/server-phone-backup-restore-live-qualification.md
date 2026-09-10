# Server Phone Backup and Restore Live Qualification

Date: 2026-09-08

Decision: **NOT QUALIFIED**

This is a qualification record for the merged Enterprise Backup & Recovery
implementation at `2a11ad60df22daccd298279771407337f16c7435`. The attached
qualification instructions authorized one controlled destructive restore, but
the supported write API required an authenticated Owner session that was not
available to this task. No backup, preview, checkpoint, restore, service
restart, or destructive storage operation was performed.

## Status summary

| Area | Result | Evidence |
| --- | --- | --- |
| Dev-PC repository identity | PASS | `main` and `origin/main` at `2a11ad60df22daccd298279771407337f16c7435`; local working tree clean before this report |
| Server Phone repository identity | PASS with limitation | Same commit and `main`; 105 pre-existing added working-tree entries prevented a clean-tree assertion. Nothing was changed or cleaned. |
| SSH/runtime access | PASS | Repository SSH check exited 0; sanitized Termux capture `20260908T141044Z-8821e8d1` passed |
| Baseline FastAPI safe reads | PASS with degraded state | Recovery endpoints returned HTTP 200, but both reported `read_degraded=true` and `projection_too_old` |
| Recovery projection freshness | FAIL | Summary age approximately `5.45e9 ms`; details had the same stale timestamp; thresholds are 60 s and 90 s |
| Full encrypted backup | BLOCKED | Supported POST returned HTTP 401 `authentication_required`; no request was queued |
| Restic snapshot/verification | UNVALIDATED | No live backup was accepted, so no new snapshot exists for this qualification |
| Backup scope/content boundary | UNVALIDATED | No real manifest was produced or inspected |
| Destructive selected restore | BLOCKED | No verified restore point from this run and no authenticated mutation path |
| SQLite restore integrity | UNVALIDATED | No restore occurred |
| OPA restored revision proof | UNVALIDATED | Baseline OPA proof passed; restore proof was not attempted |
| PhotoPrism runtime | PASS baseline | Catalog reports installed/running/healthy; local and same-origin health probes returned HTTP 200 |
| PhotoPrism media untouched | NOT APPLICABLE | No backup or restore mutation occurred |
| MariaDB logical adapter | BLOCKED / NOT IMPLEMENTED | MariaDB binaries exist, but repository source has no registered PhotoPrism metadata dump/restore adapter and the app restore apply route remains unsupported |
| NATS | PASS baseline | NATS status returned HTTP 200 and connected; JetStream was enabled in the sanitized runtime capture |
| Worker/agent/supervisor | PASS baseline | Sanitized runtime capture reported worker, node-agent, and core supervisor online |
| Interrupted rollback | UNVALIDATED | No live restore was started |
| ENOSPC rollback | UNVALIDATED | No production-safe bounded disk-exhaustion injection exists; filling real storage was prohibited |

## Baseline evidence

The repository-owned bounded runtime capture reported Android 16, ARM64,
Termux, Caddy, FastAPI, NATS, worker, node-agent, supervisor, SQLite, and
PhotoPrism runtime presence. It also confirmed that sanitized output removed
raw paths, media paths, network identity, and secrets.

Safe baseline API observations:

- `/api/lite/recovery/summary`: HTTP 200; `data_source=prepared_sqlite`,
  `source_revision=166`, `projection_revision=166`,
  `read_degraded=true`, `degraded_reason=projection_too_old`,
  `refresh_pending=false`.
- `/api/lite/recovery/details`: HTTP 200 with the same stale projection
  condition and a saved timestamp of 2026-07-07.
- `/api/lite/system/sqlite-health`: HTTP 200, `status=healthy`, schema
  revision 31; the read itself still reported a degraded/stale prepared age.
- `/api/lite/diagnostics/runtime/full`: HTTP 200,
  `authoritative_execution_registry=true`,
  `diagnostic_source=worker_prepared_sqlite`, no runnable pending mailbox work,
  one unregistered mailbox domain.
- `/api/lite/policy`: HTTP 200, engine healthy, loopback-only, browser not
  exposed. Active, known-good, repository, and observed OPA revision all
  matched `plr-7d16c0da282a92a8e0734dbfd7bd0a5c`.
- Direct loopback OPA revision query: HTTP 200 and the same revision.
- `/api/lite/catalog`: HTTP 200; PhotoPrism was installed/running/healthy and
  its backup profile reported media excluded.
- `/api/nats/status`: HTTP 200 and connected.
- `/api/lite/status`: HTTP 200 but overall `degraded`; six known devices were
  unreachable in the saved fleet view.
- MariaDB client/server binaries were discoverable and reported versions, but
  this does not prove a running PhotoPrism metadata database or a supported
  backup adapter.

The live identity projection reported an active configured Owner, no active
human session, and no OIDC sign-in method. The attempted supported request:

```text
POST /api/lite/recovery/backup
{"include_event_journal":true,"include_app_data":true,"dry_run":false,
 "reason":"server-phone-live-recovery-qualification"}
```

returned:

```text
HTTP 401
reason_code=authentication_required
message=Sign in before making this change.
```

No credentials, session cookies, CSRF tokens, API tokens, or process
environments were read, printed, or synthesized. The browser connector had
only an empty tab, so no authenticated UI session was available either.

## Root cause: `projection_too_old`

The stale condition is real and is not a React warning artifact.

The current source contract sets recovery summary freshness to 10 seconds with
a 60-second maximum stale age, and recovery details to 15 seconds with a
90-second maximum stale age. `ControlPlaneStore.prepared_only_read()` derives
the prepared age from the canonical SQLite projection `updated_at`. When it
loads the old Recovery snapshot, its in-memory `prepared_at` is backdated by
that age. The recovery subprojection cache also has a 60-second internal TTL.

The scheduler's source-unchanged path calls `mark_prepared_current()`, but that
callback refreshes only the API process-local timestamp; it does not persist a
new SQLite freshness timestamp. Production projection execution is worker
owned, so an API process cannot repair this by rebuilding the read in the
request path. The live diagnostics additionally showed one unregistered
mailbox domain and zero runnable pending work. The observed result is a
Recovery projection last committed on 2026-07-07 being served as HTTP 200 while
the prepared-read guard correctly marks it too old.

No code-level fix was applied during this qualification, because the
qualification instructions prohibit product changes. The required fix remains
to make the worker-owned Recovery source-revision/dirty/probe lifecycle persist
or safely refresh the prepared projection under the existing bounded scheduler,
while retaining the 60/90-second fail-closed thresholds. A later qualification
must prove idle freshness, mutation freshness, and a genuinely stuck-projection
degraded result.

## Existing functionality reused or audited

The implementation and live checks were kept within the existing architecture:

- FastAPI `/api/lite/recovery/*` control routes.
- NATS/JetStream command submission and the existing worker.
- Existing SQLite canonical state and prepared projections.
- Existing SQLite online backup and database recovery service.
- Existing maintenance/recovery lock and restore transaction/checkpoint/rollback
  machinery.
- Existing versioned manifest and restic integration.
- Existing sanitized evidence and lifecycle records.
- Existing OPA supervisor/revision contract.
- Existing App Catalog and PhotoPrism storage-mapping/media exclusion policy.
- Repository-owned SSH/runtime capture and sanitized runtime diagnostics.

No second SQLite store, browser NATS client, browser shell execution, alternate
restic implementation, or media archive was introduced or used.

## Backup scope

The following is the source-defined intended scope, not a live-verified
restore-point manifest because authentication blocked creation:

- canonical Pocket Lab Lite SQLite control-plane state, through the existing
  online-backup/database-recovery path;
- Identity & Access continuity records, without exposing credential values;
- Devices, fleet, enrollment, lifecycle, and governance state;
- Security configuration, scan profiles, history, findings, coverage summaries,
  sanitized evidence metadata, and backend-owned sanitized evidence;
- Rules/OPA policy lifecycle metadata, active/candidate/known-good posture,
  revisions, approvals, and source/bundle metadata where registered;
- App Catalog registration, lifecycle, route, safe configuration, storage
  mapping metadata, and PhotoPrism safe application metadata/configuration;
- Recovery history, checkpoints and lifecycle/audit metadata that belong to the
  selected restore point;
- release/runtime configuration that is canonical and non-secret.

The source audit found two material limitations that prevent claiming this as a
complete live restore contract:

1. The generic selected restic restore promotes allowlisted `state/*` files but
   treats the embedded `database-backup/*` package as metadata-only; the
   dedicated SQLite restore route is separate and was not invoked by the
   generic selected restore path.
2. PhotoPrism app restore apply is explicitly unsupported, and no registered
   MariaDB logical dump/restore adapter exists.

These are `MISSING / DEFERRED` product qualification items, not evidence of a
successful full-system restore.

## Explicit exclusions

The source contract and app catalog baseline exclude:

- Android shared/user storage;
- `/sdcard`-style user storage and `/storage/emulated/*`;
- PhotoPrism originals, imports containing media, photos, videos, thumbnails,
  sidecars, and recreatable media caches;
- any other user photo/video/media payload accessible to PhotoPrism;
- `node_modules`, `.venv`, temporary caches, scanner caches, temporary logs,
  generated `dist`/build output;
- the configured backup repository and its internals;
- unrelated restore checkpoints;
- raw scanner output, raw evidence, raw credentials, passwords, tokens,
  private keys, NATS credentials, Vault material, and runtime secret values.

Because no real manifest was produced, actual content-boundary proof remains
`UNVALIDATED`. No live operation changed media or Android storage.

## Restore contract

The source contract requires an explicit selected `backup_id`, a ready preview
bound to the manifest checksum and current target revision, confirmation, the
global recovery/maintenance guard, a pre-restore checkpoint, fenced writers,
atomic promotion, SQLite/policy/service health checks, lifecycle evidence, and
truthful rollback status. A post-mutation failure must report
`failed_with_rollback` or `failed_rollback_required`.

None of those destructive phases were executed in this qualification. The
following remain `UNVALIDATED`: selected-point verification, preview binding,
checkpoint creation, SQLite promotion/integrity, policy reactivation, service
health convergence, interrupted rollback, and media preservation after a real
restore.

## UI behavior

The merged source contains timestamped bounded/cursor history and selected
restore-point action surfaces. The live UI was not qualified because the
browser had no authenticated session and no backup could be created. No claim
is made for mobile/desktop live rendering, active backup stages, active restore
stages, failure/rollback states, accessibility, or offline saved-state
behavior from this run.

## Validation commands and results

Local validation:

```text
python3 -m py_compile [the nine changed backend/router/worker files]
PASS (exit 0)

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/backend/test_lite_recovery.py
FAIL at collection: ModuleNotFoundError: No module named 'fastapi'

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_recovery.py
17 passed, 1 warning in 3.03s

git diff --check
PASS (exit 0)

source the configured nvm runtime && nvm use 24.16.0 && npm run build
PASS; Vite transformed 2190 modules and generated the PWA service worker.
```

Live non-mutating validation:

```text
bash scripts/docs/runtime/check_termux_ssh.sh
PASS; managed SSH alias and Termux verification succeeded.

PATH=".../.venv/bin:$PATH" bash scripts/docs/runtime/capture_termux_runtime.sh
PASS; sanitized capture 20260908T141044Z-8821e8d1.

GET /api/lite/recovery/summary
HTTP 200; read_degraded=true; degraded_reason=projection_too_old.

GET /api/lite/recovery/details
HTTP 200; read_degraded=true; degraded_reason=projection_too_old.

POST /api/lite/recovery/backup with the required full-backup flags
HTTP 401; authentication_required; no queue acceptance.
```

The local working tree remains unchanged except for this intentionally
uncommitted report. No commit, push, branch creation, PR, merge, tag, release,
remote cleanup, or Server Phone cleanup was performed.

## Live validation still required

An operator must first sign in through the supported Owner/Enterprise session
flow and provide an authenticated browser or API execution context without
exposing its credentials. After the Recovery projection issue and baseline
degradation are resolved, repeat the following on the real Server Phone:

1. Capture baseline identity, health, SQLite, OPA revision, NATS, worker,
   agent/supervisor, PhotoPrism, MariaDB capability, capacity, and media
   fingerprints using sanitized probes.
2. Create and verify a real full restore point through the FastAPI endpoint with
   event journal and app data enabled. Confirm a format-versioned manifest,
   encrypted restic snapshot, component checksums, database validation, staging
   cleanup, and bounded history entry.
3. Prove the manifest includes canonical SQLite/application metadata and
   excludes Android storage and all PhotoPrism media. Do not enumerate or read
   user media to prove exclusion.
4. Resolve or explicitly register the PhotoPrism MariaDB metadata adapter. If
   unavailable, keep that result `BLOCKED / NOT IMPLEMENTED` and do not claim
   complete PhotoPrism restoration.
5. Make a harmless, backend-owned differentiator, create a selected-backup
   preview, and verify the preview is bound to backup ID, manifest checksum,
   target revision, and preview ID.
6. Perform the one explicitly authorized controlled restore only after preview,
   confirmation, checkpoint, maintenance guard, free-space, and writer-fence
   checks pass. Verify SQLite integrity/schema/foreign keys, exact OPA active
   revision, FastAPI/NATS/worker/service health, App Catalog, PhotoPrism route,
   Security, Recovery, audit, and evidence convergence.
7. Exercise repository-supported interrupted-restore fault injection and prove
   rollback health. Do not kill arbitrary production processes.
8. Mark disk-exhaustion rollback `UNVALIDATED` unless a bounded injection exists;
   never fill real Termux, Android shared, media, or backup-repository storage.
9. Re-run the idle and mutation Recovery freshness checks and require no
   `projection_too_old` during healthy operation.

## Risks

- Schema incompatibility must fail closed; unsupported future manifest formats
  must not be reinterpreted.
- Secret-bearing runtime state is not safely recoverable by this qualification;
  no secret recovery mechanism was proven.
- PhotoPrism/MariaDB metadata restoration is not implemented by a registered
  adapter.
- The generic selected restore path requires explicit SQLite/app integration
  before it can support the stated complete system-state guarantee.
- Termux interruption, disk exhaustion, and rollback behavior remain live
  unknowns.
- Disk exhaustion can leave staging/checkpoints competing with the target
  repository; bounded free-space guards and cleanup need live proof.
- OPA policy reactivation and exact post-restore revision proof need a real
  restore, not only a baseline read.
- The Server Phone had 105 pre-existing added working-tree entries; their
  ownership and deployment hygiene were not changed by this run.
- Six unreachable known devices and one unregistered projection mailbox domain
  mean the baseline was not a fully converged healthy runtime.

## Enterprise value

The merged implementation establishes the intended governed control-plane
boundary: FastAPI controls the operation, the worker executes it, SQLite remains
canonical, restic remains encrypted, and restore lifecycle/evidence are
backend-owned. The qualification evidence also demonstrates why enterprise
confidence requires more than HTTP 200: stale prepared Recovery state, missing
runtime convergence, absent MariaDB integration, and unavailable authenticated
operator context must remain visible and fail closed.

## Remediation Round 1

Date: 2026-09-08

Branch: `fix/recovery-live-qualification-blockers`

Base: `2a11ad60df22daccd298279771407337f16c7435`

Decision: local remediation is validated. Destructive live requalification is
blocked by the supported authentication gate and was not attempted.

### Root cause and correction

The original `projection_too_old` result was a real lifecycle defect, not an
HTTP or React presentation issue. The prepared Recovery snapshot retained its
canonical 2026-07-07 `updated_at`. The worker's source-unchanged reconciliation
updated API-process-local prepared state, but the API read path had no durable
worker completion timestamp to consume after restart or in the API/worker
split. It therefore computed age from the old canonical snapshot and returned
HTTP 200 with `read_degraded=true` once the 60/90-second fences were exceeded.

Two additional source-level causes were verified. Recovery details included
unrelated fleet/storage revisions, so continuously changing heartbeat state
kept re-dirtying a projection that did not consume that data. Recovery's
adaptive worker cadence was also `900/3600` seconds for summary and
`1200/3600` seconds for details, which could never satisfy the 60/90-second
prepared-read fences.

The correction keeps the fences intact. The read-only prepared store now
consumes the worker-owned durable `projection_refresh_state.last_completed_at`
only when it is valid, error-free, and at least as new as the canonical source
snapshot. The scheduler marks the durable signal dirty when claiming work and
clears it only after the normal worker reconciliation persists completion.
Recovery details no longer depend on unrelated fleet heartbeat revisions. The
worker cadence is now bounded inside the fences, including jitter:

| Projection | Active | Stable | Maximum | Prepared max-stale fence |
| --- | ---: | ---: | ---: | ---: |
| `recovery.summary` | 8s | 30s | 54s | 60s |
| `recovery.details` | 15s | 45s | 81s | 90s |

A genuinely old or failed durable completion still trips
`projection_too_old`; the stale-projection safety behavior was not removed.

### Remediation implemented

- Format-2 selected full restores now require the embedded canonical SQLite
  package and restore it through the existing guarded database transaction.
- The transaction validates the staged package ID, database hash, integrity,
  schema, migration checksums, foreign keys, canonical projection parity,
  registered state-file checksums, staging containment, and symlink safety.
- Registered Pocket Lab state files are checkpointed and restored in the same
  governed transaction as SQLite. Post-restore service restart/readiness
  validation runs before commit; failure follows the existing rollback result
  states.
- Snapshot existence is checked in the configured encrypted repository before
  selected restore use. Unsupported future manifest formats fail closed.
- The existing format-1 path remains available only for its compatible legacy
  contract; format-2 is the complete selected full-restore path.
- The backup/restore fault seam already owned by the restore transaction is
  retained for deterministic pre/post-promotion failure tests. No arbitrary
  production process killing was added.
- PhotoPrism media remains excluded. A PhotoPrism/MariaDB logical metadata
  adapter is still not registered, so that component remains
  `BLOCKED / NOT IMPLEMENTED` rather than being replaced with an ad hoc dump.

### Existing functionality reused

The remediation extends, rather than duplicates, the existing architecture:

- `ControlPlaneProjectionStore.prepared_only_read()` and the durable
  `projection_refresh_state` table remain the prepared-read contract.
- `ProjectionScheduler`, semantic source revisions, worker dirty signals and
  adaptive runtime cadence remain the worker-owned projection machinery.
- `lite_database_recovery` continues to own `online_backup`, database
  integrity/schema/foreign-key/migration validation, the database recovery
  lock, maintenance mode, transaction journal, checkpoint, promotion and
  rollback.
- Existing `lite_restore_transaction` fault injection and journal semantics are
  reused for selected full restore.
- Existing `lite_backup_manifest`, restic repository/password-file handling,
  bounded manifest history and API sanitization remain authoritative.
- Existing registered state inventory, canonical app-storage mapping and
  PhotoPrism media exclusion policy remain the source of backup scope.
- Existing FastAPI authorization and Personal/Enterprise governance paths were
  not weakened or bypassed.

### Files changed

Canonical implementation and test paths:

- `pocket-lab-final-structure/runtime/api_fastapi/services/adaptive_runtime.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_backup.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_database_recovery.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/lite_semantic_revisions.py`
- `pocket-lab-final-structure/runtime/api_fastapi/services/projection_scheduler.py`
- `tests/backend/test_lite_recovery.py`
- `docs/recovery/server-phone-backup-restore-live-qualification.md`

Generator-owned outputs were regenerated with `task lite:docs:generate`; the
changed projections are under `contracts/generated/`,
`docs/generated/development/`, `docs/generated/enterprise/`,
`docs/generated/production/`, and `docs/generated/assets/knowledge/`. They were
not hand-edited.

### Backup scope

The existing format-2 backup path creates one timestamped, encrypted restic
restore point and includes, where present:

- canonical Pocket Lab SQLite state through the existing online-backup path;
- Lite runtime/control-plane state, device records and heartbeats, invite
  lifecycle, device audit/command evidence, Rules/protection state, OPA policy
  metadata, app catalog/install metadata, route/storage mapping metadata and
  Recovery metadata;
- bounded backend-owned sanitized Security evidence/history and audit/history
  metadata;
- the selected application's registered metadata/configuration paths only;
- versioned manifest, component results, checksums, repository snapshot ID,
  timestamps and restorable/verification state.

The canonical manifest uses format version 2, stable `backup_id`, timestamps,
component results, encrypted restic metadata, manifest checksum and
`restorable=false` until verification succeeds. Browser/API projections expose
friendly component labels and never expose backend command payloads, private
repository paths or secret-bearing values.

### Explicit exclusions

The policy excludes, fail closed where classification is ambiguous:

- Android shared/user storage, `/sdcard`-style storage and
  `/storage/emulated/*`;
- PhotoPrism originals, imports containing media, photos, videos, media files,
  thumbnails and recreatable media caches;
- `node_modules`, `.venv`, cache folders, scanner caches, temporary scanner
  output, temporary logs and generated frontend build/dist output;
- backup repository internals, unrelated restore checkpoints and transient
  process/runtime caches;
- raw scanner output, raw evidence, raw session/CSRF/API/invite/NATS tokens,
  private keys, Vault secrets, restic passwords and other backend secret values.

PhotoPrism/MariaDB metadata is not claimed as included until a registered
service-specific logical dump, integrity verification and restore adapter is
implemented.

### Restore contract

For a selected verified `backup_id`, the backend binds restore to the manifest
checksum, snapshot ID, target revision and `preview_id`. Preview is required
and explicit confirmation is required. The selected snapshot must exist in the
configured encrypted repository. The backend acquires the existing global
operation/recovery and maintenance guards, creates a pre-restore checkpoint,
validates the isolated staged package and registered destinations, then routes
SQLite plus registered state files through one guarded database transaction.

The transaction reuses writer fencing, checkpoint, atomic promotion, database
integrity/schema/foreign-key/migration checks and post-restore validation. It
commits only after Lite API/service health validation passes. Any failure after
mutation attempts rollback from the checkpoint and reports
`failed_with_rollback`; rollback failure reports
`failed_rollback_required`. It never reports success for a partial mutation.

### Projection contract

Material Recovery changes continue to dirty the worker-owned semantic source
revision. A worker claim is durably marked active/dirty, and a successful
unchanged reconciliation supplies a durable `last_completed_at` while keeping
the semantic revision stable. Prepared reads use that worker completion only as
the freshness proof; they do not execute collectors or projectors. The API
therefore serves current prepared state after process restart while preserving
the 10/15-second normal stale indicators and 60/90-second fail-closed maximums.

The scheduler cadence, dirty mailbox, durable completion state and frontend
TanStack query invalidation now operate under one bounded contract. Tests cover
idle freshness, backup/verify/preview/restore-related recovery mutation paths,
unrelated fleet heartbeat stability, and a genuinely stuck projection still
degrading.

### UI behavior

The existing Recovery UI remains summary-first and uses the bounded backend
history contract rather than treating only `latest` as authoritative. It
supports timestamped restore-point summaries, lazy detail/preview/confirmation
surfaces, selected `backup_id` verification and restore, truthful backend-owned
backup/restore stages, failure/rollback states, saved/offline state and
projection-refreshing state. The mocked mobile/desktop Recovery flows and
Storybook coverage remain passing. No frontend NATS, shell, restic, database or
secret handling was introduced.

### Local validation

The following evidence was captured on the remediation branch:

```text
python3 -m py_compile \
  pocket-lab-final-structure/runtime/api_fastapi/services/lite_backup.py \
  pocket-lab-final-structure/runtime/api_fastapi/services/lite_backup_policy.py \
  pocket-lab-final-structure/runtime/api_fastapi/services/lite_backup_manifest.py \
  pocket-lab-final-structure/runtime/api_fastapi/services/lite_database_recovery.py \
  pocket-lab-final-structure/runtime/api_fastapi/services/lite_restore_transaction.py \
  pocket-lab-final-structure/runtime/api_fastapi/services/lite_recovery_subprojections.py \
  pocket-lab-final-structure/runtime/api_fastapi/services/lite_core_projections.py \
  pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py \
  pocket-lab-final-structure/runtime/workers/pocketlab_worker.py
PASS; exit 0.

PYTHONPATH=tests:pocket-lab-final-structure/runtime \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q \
tests/backend/test_lite_recovery.py \
tests/backend/test_lite_phase4_phase5_adaptive_runtime.py
42 passed, 1 warning in 4.62s.

PYTHONPATH=tests:pocket-lab-final-structure/runtime \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q \
tests/backend/test_lite_recovery.py \
tests/backend/test_lite_projection_semantic_hardening.py
28 passed, 1 warning in 4.94s.

PYTHONPATH=tests:pocket-lab-final-structure/runtime \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q \
tests/backend/test_lite_api.py -k 'recovery or backup or restore or projection'
30 passed, 302 deselected, 1 warning in 6.52s.

Focused broader Recovery/security/storage suites
82 passed, 1 warning in 11.88s.

Broader Recovery/security/storage/fault suites
60 passed, 1 warning in 26.39s.

PATH="$PWD/.venv/bin:$PATH" task lite:api:check
PASS Lite API checks passed.

source /home/dj/.nvm/nvm.sh && nvm use 24.16.0 && npm run build
PASS; 2190 modules transformed and the PWA service worker was generated.

task lite:docs:generate
PASS; deterministic contract, platform, runtime, architecture, knowledge,
enterprise, SchemaSpy and diagram projections regenerated.

source /home/dj/.nvm/nvm.sh && nvm use 24.16.0 >/dev/null && \
PATH="$PWD/.venv/bin:$PATH" task lite:check
PASS; all 18 functional gate checks passed, followed by successful Allure
aggregation:
371 backend tests, 196 frontend unit tests, 27 mocked E2E tests with 7 skips,
188 canonical Storybook stories plus 10 representative renders, accessibility,
contract/build/diff checks, redaction, browser/docs checks, 60 documentation
platform tests, and generated documentation consistency.
The gate emitted 1 deprecation warning and the repository's existing OpenAPI
warnings; no check failed.

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q \
tests/backend/test_lite_recovery.py
UNVALIDATED in the system interpreter: collection failed because FastAPI is
not installed. The repository .venv run above is the validated result.
```

The full gate's authoritative recorded artifacts report exit code 0 for every
functional check and for the final Allure aggregation. No commit, push, PR,
merge, tag or GitHub mutation was performed.

### MISSING / DEFERRED

- PhotoPrism/MariaDB metadata logical backup, verification and restore adapter:
  `BLOCKED / NOT IMPLEMENTED`; arbitrary `mysqldump` substitution was not used.
- A real authenticated Owner session/OIDC context was unavailable, so no live
  backup or destructive selected restore was authorized or attempted.
- Live ENOSPC qualification remains `UNVALIDATED`; no real storage was filled.
- The local deterministic restore fault seam is tested, but live Termux
  interruption and rollback qualification remains `UNVALIDATED`.
- Live OPA reactivation, exact post-restore policy revision, service-specific
  application metadata convergence and media-untouched proof remain
  `UNVALIDATED`.

## Live Requalification After Remediation

### Deployment evidence

The Server Phone began on base `2a11ad60df22daccd298279771407337f16c7435`,
branch `main`. Its 106 pre-existing working-tree artifacts were left untouched.
The remediation runtime files were copied using bounded per-file `scp` after
the environment reported that `rsync` was unavailable. Remote SHA-256 values
matched the local files for `lite_backup.py`, `lite_control_plane_store.py`,
`lite_database_recovery.py`, `projection_scheduler.py`,
`lite_semantic_revisions.py` and `adaptive_runtime.py`; all six compiled
remotely.
Only `pocket-api` and `pocket-worker` were restarted for the deployment. The
final PM2 status showed Caddy, API, NATS, node-agent, OPA, telemetry, worker,
PhotoPrism and core supervisor online. No remote repository cleanup or
destructive restore was performed.

Sanitized runtime capture after the final deployment:

```text
PASS sanitized Termux runtime capture created:
20260908T155127Z-3dc14b0b
```

The capture remained sanitized and bounded; it did not print credentials,
private paths, raw evidence or media paths.

### Recovery freshness proof

The final safe API read returned:

```text
summary: HTTP 200, read_degraded=false, degraded_reason="",
         projection_age_ms=5156, refresh_pending=false, revision=180
details: HTTP 200, read_degraded=false, degraded_reason="",
         projection_age_ms=15722, refresh_pending=false, revision=180
```

A bounded five-sample idle probe after the final cadence deployment also
returned `read_degraded=false`, empty `degraded_reason` and
`refresh_pending=false` for both endpoints at every sample. The observed
summary/details ages in milliseconds were:

| Sample | Summary age | Details age | Result |
| ---: | ---: | ---: | --- |
| 0 | 18,175 | 12,918 | pass |
| 1 | 26,235 | 20,973 | pass |
| 2 | 34,289 | 29,029 | pass |
| 3 | 42,339 | 37,078 | pass |
| 4 | 50,405 | 45,162 | pass |

The overall Lite status still reported degraded because six known devices were
unreachable. That fleet condition is separate from the prepared Recovery read
contract; it did not produce `projection_too_old` in this probe.

### Authentication gate and live qualification matrix

The supported full-backup write was attempted once with the normal endpoint
and required full-backup flags. It returned `HTTP 401` with
`reason_code=authentication_required`. No credential store, token, cookie or
secret was accessed. No operation was queued.

| Qualification item | Result | Evidence/state |
| --- | --- | --- |
| Server Phone identity/runtime baseline | `VERIFIED` | Sanitized capture and PM2/API/NATS/OPA/PhotoPrism baseline passed. |
| Recovery summary freshness | `VERIFIED` | Final HTTP 200, fresh prepared read; five idle samples passed. |
| Recovery details freshness | `VERIFIED` | Final HTTP 200, fresh prepared read; five idle samples passed. |
| Real encrypted full Backup | `BLOCKED` | Supported write returned `401 authentication_required`. |
| Complete manifest scope/exclusions | `UNVALIDATED` live | Local scope/policy/tests pass; no real restore point was created. |
| Restic verification | `UNVALIDATED` live | Local fake-restic/contract coverage; no live point. |
| Bounded timestamped history | `UNVALIDATED` live | Local bounded history contract; no live point. |
| Selected backup preview/differentiator | `UNVALIDATED` live | Local selected-preview binding coverage; no live differentiator. |
| Selected full restore | `BLOCKED` | No authenticated Owner context; destructive mutation not attempted. |
| SQLite health after selected restore | `UNVALIDATED` live | Local canonical transaction test passed. |
| OPA reactivation/exact restored revision | `UNVALIDATED` live | Baseline revision matched; post-restore proof needs a real restore. |
| Devices/Security/Identity/App Catalog convergence | `UNVALIDATED` live | No post-restore state transition occurred. |
| PhotoPrism route/settings convergence | `UNVALIDATED` live | Baseline route/health passed; metadata restore not exercised. |
| PhotoPrism/MariaDB metadata adapter | `BLOCKED` | No registered service-specific adapter exists. |
| Android/media untouched proof | `UNVALIDATED` live | No real restore executed; policy excludes these paths. |
| Audit/evidence after restore | `UNVALIDATED` live | No restore lifecycle was started. |
| Interrupted restore rollback | `UNVALIDATED` live | Local fault seam exists and is covered; no live injection. |
| ENOSPC rollback | `UNVALIDATED` | No safe bounded production seam was available; no storage filled. |
| Final post-mutation Recovery freshness | `UNVALIDATED` live | Fresh idle runtime proven; no mutation/restore lifecycle occurred. |

### Required future live qualification sequence

An operator must sign in through the supported Owner/Enterprise session flow and
provide an authenticated browser or API context without exposing credentials.
The future controlled run must then create and verify a real format-2 encrypted
restore point, inspect only sanitized manifest/scope projections, verify the
Android and PhotoPrism media exclusions, and create a harmless backend-owned
differentiator. The operator must preview that selected `backup_id`, confirm
the bound manifest checksum/target revision/preview ID, and explicitly
authorize the destructive restore.

The restore must be allowed to acquire the global guard, create its checkpoint,
fence writers, restore the canonical SQLite package and registered state,
validate OPA's exact active revision, restart only required services, verify
FastAPI/NATS/worker/agent/supervisor/App Catalog/Security/Recovery/PhotoPrism
health, and record audit/evidence. It must compare protected media fingerprints
before and after without reading media contents. The operator should exercise
the repository-supported interrupted-operation seam and any future bounded
ENOSPC seam only in an isolated qualification target, then repeat the idle and
mutation freshness probes. If the MariaDB adapter remains absent, the run must
retain `BLOCKED / NOT IMPLEMENTED` for PhotoPrism metadata restoration.

### Live validation status

The remediation fixed and live-qualified the prepared Recovery freshness
blocker. It did not qualify a real Backup/Restore cycle because the supported
authentication context was unavailable, and it did not claim PhotoPrism
metadata completeness without the required adapter. The Server Phone was left
running with the deployed remediation and no destructive state change.

## Qualification Owner Harness

This appended closure supersedes the earlier authentication-blocked snapshot
above. It records the separately authorized isolated Server Phone
qualification run. The harness used the normal FastAPI write path and the
existing NATS/JetStream/worker command path; it did not talk to NATS from the
browser, clone a human session, or read or create real credentials.

### VERIFIED

- The repository-owned qualification Owner contract was used only while the
  isolated qualification gates were explicitly enabled. It required the
  local test and qualification headers, did not accept a browser role header,
  and mapped the request to the sanitized `qualification-owner` actor through
  the normal authentication, authorization and audit path.
- Normal API requests created the real full-backup, verify, preview and
  selected-restore commands below. The backup was not a mock, dry-run or
  frontend-side archive operation.
- After qualification, the API and worker process environments were restored
  to production/disabled qualification controls without printing environment
  values. Identity-table checks found zero rows for the synthetic
  `qualification-owner` principal across human identities, credentials,
  sessions, enterprise memberships, enrollment claims and recovery-code
  batches.
- An unauthenticated direct write returned `401` after the gates were disabled,
  and the API log recorded `POST /api/lite/recovery/backup ... 401
  Unauthorized`. A final Caddy probe timed out while the API was unstable, so
  the final Caddy rejection is `UNVALIDATED`, not a claimed pass.

### UNVALIDATED

- The harness is not production authentication evidence. A supported human
  Owner/Enterprise session and browser-mediated live UI qualification remain
  required.
- No real password, token, cookie, private key, NATS credential or other
  backend secret was accessed, copied or persisted by this qualification.

## End-to-End Live Backup and Restore Closure

### Closure decision

`PARTIAL / NOT QUALIFIED` is the truthful end-to-end result. A real encrypted
full backup, verification, bounded history, selected preview and destructive
restore request were exercised. The selected restore then failed during
post-restore validation and completed with a verified rollback. Because the
restore did not succeed, this branch must not be described as production-ready
or as having completed the live restore contract.

### Live operation evidence

| Operation | ID | Result |
| --- | --- | --- |
| Full backup | `0a3a1ec814f74040b374b90154549bb7` | `VERIFIED`: format 2, 133,618,430 bytes, restic snapshot `7645641d8b7d726652886fa828868ef945fe0d6011d106a10bfce1550b20ec16`, final status `verified`, `restorable=true`. |
| Verify command | `ae2a8cabafb44540907390d279318f39` | `VERIFIED`: selected manifest and restic/component checks passed; final verification status was `verified`. |
| Preview command | `34130442c39d4b0aa7e2ee8686f80e2c` | `VERIFIED`: preview was generated through the normal API/worker path. |
| Bound preview | `preview-0a3a1ec814f74040b374b90154549bb7-7108a1c165a4` | `VERIFIED`: bound to the selected backup, manifest checksum `08ccc8624969059141fc3f772346b5387cc8cad8c0076853da44ab56a78569c9`, target revision `8123790365472551168`, and `restore_allowed=true`; the change sample was bounded to 500 entries. |
| Selected restore | `e6f395c542214acdb9277442f206d9da` | `VERIFIED`: explicit `backup_id`, preview ID and confirmation were accepted; checkpoint, writer fencing, staging, promotion and rollback ran. Final result was `failed_with_rollback`, not success. |

The live backup manifest validated Backup metadata, Lite runtime state,
PhotoPrism application metadata, PhotoPrism safe configuration, the Pocket Lab
database and sanitized Security evidence. SQLite integrity, quick-check,
foreign-key validation, schema/migration checks and component checks passed;
the recorded canonical database contained 40 tables. The history endpoint
returned bounded newest-first rows with `has_more=true` rather than loading an
unbounded list.

The selected restore used the supported display-model update as a harmless
backend-owned differentiator. It changed the display-only value to
`Qualification Restore Marker A` before the backup/restore attempt; the
failed-with-rollback run did not prove a successful return to the backed-up
value. It did not change physical device identity.

### Restore transaction result

The restore acquired the global recovery/maintenance path, created its
pre-restore checkpoint, fenced PhotoPrism writers, validated and promoted the
staged package, and reached `validating_active`. Post-restore validation then
failed at the recorded `post_restore_validation` stage. The transaction
rolled back the canonical database and registered state, restarted the
required application path, and verified checkpoint/database parity. The run
file reported `failed_with_rollback`, rollback status `rolled_back`, matched
database and byte hashes, and cleaned its staging directory.

The command lifecycle fix is also live-verified: the worker acknowledged the
exact command and the command row ended as `status=failed`,
`lifecycle_stage=failed`, with attention active. It did not publish a false
`command.succeeded` or `lite.restore.completed` event for a
`failed_with_rollback` result. The observed validation failure is not proof of
the exact underlying service race; a bounded PhotoPrism HTTP-readiness retry
and sanitized post-restore check diagnostics are implemented locally but were
not deployed for a third destructive attempt.

### Scope and safety result

- The live point excluded Android shared/user storage and
  `/storage/emulated/*`, PhotoPrism originals/import media/photos/videos,
  thumbnails and recreatable caches, scanner caches and temporary output,
  `node_modules`, `.venv`, generated build output, temporary logs, the backup
  repository itself and unrelated restore checkpoints.
- The live PhotoPrism metadata component used the registered SQLite driver and
  validated the metadata database/configuration without reading media. A
  service-specific MariaDB logical backup/restore adapter is still absent; the
  implementation fails closed for a MariaDB configuration and does not claim
  MariaDB completeness.
- No manifest, API payload, UI payload, audit record or log in this run was
  allowed to contain passwords, password hashes, tokens, private keys, API
  keys, NATS credentials, restic passwords, raw evidence or private Android
  paths.
- The rollback preserved the pre-restore differentiator and therefore did not
  provide a successful post-restore media-untouched/convergence assertion.
  Media and Android storage were not targeted by the restore path; the full
  live fingerprint comparison remains required.

### Projection and runtime closure

The local root-cause fix is now source-owned and regression-tested. The old
healthy-runtime `projection_too_old` condition came from two mismatched
contracts: Recovery summary/details were served with outer stale fences of
10s/60s and 15s/90s, while internal Recovery source caches and mutation paths
could outlive those fences and material Recovery changes did not uniformly
advance the source revision and durable dirty signal. A prepared read could
therefore return HTTP 200 while its committed projection was older than the
allowed freshness contract.

The code-level fix keeps the stale protection and aligns the layers:

- Recovery source caches are bounded at 5 seconds for summary inputs and 8
  seconds for details inputs, with a 30-second hard source-cache ceiling.
- Backup, verify, preview, checkpoint, restore, database-recovery,
  application-backup, maintenance and policy/config transitions invalidate
  the relevant semantic source revision and durable dirty signal.
- The scheduler/worker rehydrates dirty Recovery jobs and commits the prepared
  SQLite projection; Recovery details compose committed prepared app
  lifecycle state instead of recursively launching live collectors.
- The API retains the 10s/60s summary and 15s/90s details stale/degraded
  fences, and frontend query invalidation remains tied to backend-owned
  revisions rather than hiding the warning.

Local regression evidence covers idle operation and backup, verify, preview,
restore, database-recovery and app-backup mutations. During this live closure,
Recovery summary/details were observed non-degraded after the worker restart
(ages approximately 50.8s and 50.7s, within their respective max-stale
windows). The mandatory live runtime gate is still open: `system.nats_remote`
remained `projection_too_old` at approximately 35.6 million milliseconds, and
the final PM2 sample showed all processes online but API/worker restart counts
of 22/42 with short API uptime. This is runtime-pressure evidence, not a
successful stable end-to-end freshness qualification.

### Current closure status

| Gate | Status | Evidence |
| --- | --- | --- |
| Qualification Owner isolation and cleanup | `VERIFIED` | Gates disabled; synthetic identity-related row counts zero; direct unauthenticated `401` observed. |
| Real encrypted full backup | `VERIFIED` | Backup ID, format-2 manifest, restic snapshot and component validation above. |
| Verify and timestamped bounded history | `VERIFIED` | Verify command succeeded; history was newest-first and bounded. |
| Selected preview binding | `VERIFIED` | Preview bound to backup ID, manifest checksum, target revision and preview ID. |
| Selected destructive restore request | `VERIFIED` | Explicit confirmation, checkpoint and mutation path executed. |
| Successful selected restore | `MISSING / DEFERRED` | Run failed during post-restore validation and rolled back safely. |
| Rollback truthfulness | `VERIFIED` | Worker/domain lifecycle ended `failed`, run result `failed_with_rollback`; no false success event. |
| Exact post-restore OPA revision and decision | `UNVALIDATED` | Restore did not reach a successful post-restore convergence assertion. |
| Devices/Security/Identity/App Catalog/PhotoPrism convergence | `UNVALIDATED` | No successful restore state exists to compare. |
| Live stable Recovery/NATS freshness | `UNVALIDATED` | Recovery reads were fresh in one sample; NATS remained stale and runtime was unstable. |
| Interrupted rollback and ENOSPC qualification | `UNVALIDATED` | Local fault coverage exists; no additional destructive live injection was run. |

### Live validation still required

1. Repeat one controlled selected restore after the runtime is stable and the
   deployed PhotoPrism readiness diagnostics are available; do not reuse the
   failed run as a success proof.
2. Prove the display differentiator returns to the backed-up value and verify
   SQLite integrity/foreign keys, exact OPA active/known-good revision and
   decision, NATS/worker readiness, Devices, Security, Identity, App Catalog,
   Recovery and PhotoPrism route/settings convergence.
3. Capture before/after fingerprints for registered Android and PhotoPrism
   media roots without reading or archiving their contents, and prove they are
   unchanged after a successful restore.
4. Exercise the repository-supported interrupted-restore rollback seam in the
   isolated target and qualify a bounded ENOSPC seam if one becomes available;
   otherwise retain `UNVALIDATED`.
5. Re-run idle and mutation Recovery freshness probes with a healthy
   `system.nats_remote` projection, and qualify the browser/UI flows for the
   timestamped history and selected restore states.
6. If a deployment uses PhotoPrism/MariaDB rather than the live SQLite driver,
   implement and qualify the registered service-specific logical dump,
   integrity validation and restore adapter before claiming full app metadata
   coverage.

The branch remains uncommitted. No commit, push, merge, tag, release or
GitHub PR operation was performed.

## Final Runtime Stabilization

This section supersedes the earlier runtime-pressure snapshot while retaining
its historical evidence. The final qualification resumed from the existing
restore journal and did not start a replacement restore during stabilization.

The original healthy-runtime `projection_too_old` cause was a real lifecycle
defect: the API/worker split retained an old prepared `updated_at` without a
durable worker completion timestamp, Recovery details were dirtied by unrelated
fleet revisions, and the old 900/1200-second adaptive cadences exceeded the
60/90-second prepared-read fences. The correction uses the durable
`projection_refresh_state.last_completed_at` proof, Recovery-specific dirty
signals, bounded source caches, Recovery-only detail inputs, and scheduler
cadences that remain inside the outer fences. A genuinely stuck projection
still degrades fail closed.

The final deployed runtime used the patched bounded manifest-summary cache,
the retired legacy `apps.backup:photoprism` scheduler mailbox, and the
three-attempt restore-staging cleanup path. The API and worker remained online
through the final idle window with PM2 restart counts stable at `22` and `42`.
Five post-isolation samples returned HTTP 200 and `read_degraded=false` for
Recovery summary, Recovery details, and `system.nats_remote`; observed age
ranges were approximately 348--8,983 ms, 1,659--17,768 ms, and
2,593--102,135 ms respectively. Recovery summary/details remained below their
60/90-second maximum stale fences. Recovery maintenance reported `ready`.

Qualification controls were disabled after the run and the API was restarted
with production/disabled qualification settings. Synthetic
`qualification-owner` identity and membership counts were zero. A POST to the
backup write route returned HTTP 401 through both the direct API and Caddy;
safe GET reads remain intentionally available without that write authority.

## Successful Selected Restore Qualification

The final selected restore used a fresh restore point rather than reusing the
earlier failed point:

| Operation | Result |
| --- | --- |
| Backup | `7541d16ec9c141a2bc7458ea8ac6b7dd`; format 2, encrypted, verified and restorable; restic snapshot `663fd9edb80d9728ae4b0ee9b93a94e5443107f1446416b61d67210e19cee118`. |
| Backup content | 17,883 included files: 17,871 state records, 9 database-package records, 2 application records and 1 other record. Included sets were Backup metadata, Lite runtime state, PhotoPrism application metadata, PhotoPrism safe configuration, Pocket Lab database and sanitized Security evidence. |
| Verify | Manifest checksum, snapshot existence, encrypted repository integrity and component validation all passed; the restore point remained `verified` and `restorable=true`. |
| Preview | `preview-7541d16ec9c141a2bc7458ea8ac6b7dd-d330131c1437`; bound to the selected backup, manifest and current target revision before confirmation. |
| Selected restore | `3141eb3f9ac1413caf98b39faf8aa6fc`; completed with journal phase `committed`, terminal status `committed`, database recovery completed, checkpoint created, service restart succeeded and health validation passed. |

The backend-owned differentiator was `Qualification Rollback Marker B` before
the backup and was changed to `Qualification Restore Marker B` only after the
backup point was created and before restore. The selected restore returned the
display value to the backed-up `Qualification Rollback Marker B` marker. The
successful restore validation also
proved SQLite integrity, quick-check, foreign-key cleanliness, schema and
migration compatibility, App Catalog/PhotoPrism application validation,
Security projection health, Recovery projection health, fleet health and
Identity readiness. The exact active, known-good and repository OPA revision
after restore was `plr-568a6e9c23a6e3e13725ed5f130e4774`.

The protected media inventory was not read as content. Its structural
fingerprint before and after the successful restore was identical:
`5b8cc536681530fb8ba10c0cfe11ed11bd9c86118b6346abd0f31d4b0d78818f`.
The backup contained zero media markers and the restore promoted zero media
markers. The whole-system health summary still reported the pre-existing
offline agent/supervisor baseline; that environmental condition is distinct
from the healthy API, worker, NATS, Recovery, Security, Identity, Rules,
App Catalog and PhotoPrism control-plane checks above.

## Failure Injection Qualification

The existing restore transaction fault seam was used after the successful
restore, at `after_sqlite_promotion`, with the same fresh backup. Restore
`ee917a37a1ca4d34bf244c2b467f205e` reached promotion and failed with the
sanitized category `test_fault_injected` at the promotion stage. It ended as
`failed_with_rollback`, journal phase `rolled_back`, rollback status
`rolled_back`, rollback attempted, checkpoint projection matched, and API/
worker restart was allowed. The rollback restored 18,232 expected files and
18,232 files were reported restored; the application service was restarted.
No success event was emitted for the failed restore.

That injected run exposed a Termux staging-removal race in the prior cleanup
`finally` path. The canonical `lite_backup.py` cleanup now retries bounded
removal, records `removed`/`not_present`/`failed`, and converts cleanup failure
to `failed_rollback_required` instead of claiming completion. The repository
regression test for a transient removal failure passes, the patched file was
deployed and compiled on the Server Phone, and the backend-owned cleanup
operation removed the injected run's staging directory. A second destructive
injection solely to observe the retry branch live was not run; that narrow
live retry observation remains `UNVALIDATED`.

## Final Production Readiness Decision

The exercised control-plane Backup/Verify/Preview/selected-Restore path is
`QUALIFIED WITH LIMITATIONS`. This is not an unconditional whole-install
production-ready claim: live authenticated browser/UI qualification, an
ENOSPC rollback seam, and healthy Server Phone agent/supervisor/Tailscale
convergence remain open. The current PhotoPrism runtime uses SQLite; MariaDB
metadata remains fail-closed and is not claimed for a MariaDB deployment.

| Area | Result |
| --- | --- |
| Recovery idle freshness | PASS |
| Recovery mutation freshness | PASS |
| `system.nats_remote` freshness | PASS |
| API runtime stability | PASS; restart count stable at 22 |
| Worker runtime stability | PASS; restart count stable at 42 |
| Real encrypted Backup | PASS |
| Restic verification | PASS |
| Manifest scope | PASS |
| Secret exclusion | PASS |
| Media exclusion | PASS; structural fingerprint unchanged |
| PhotoPrism metadata Backup | PASS for current SQLite driver; MariaDB N/A/fail-closed |
| Selected Restore | PASS |
| SQLite restore | PASS |
| SQLite integrity | PASS |
| OPA exact revision | PASS |
| Devices convergence | PASS for the control-plane state |
| Security convergence | PASS |
| Identity convergence | PASS |
| Rules convergence | PASS |
| App Catalog convergence | PASS |
| PhotoPrism convergence | PASS for current SQLite application path |
| NATS | PASS |
| Worker | PASS |
| Agent | UNVALIDATED; existing offline baseline |
| Supervisor | UNVALIDATED; existing offline baseline |
| Tailscale | UNVALIDATED |
| Interrupted rollback | PASS; live promotion fault rolled back |
| ENOSPC | UNVALIDATED; no real storage was filled |
| Live UI | UNVALIDATED live; mocked desktop/mobile and accessibility gates pass |
| Qualification Owner disabled | PASS |
| Caddy isolation | PASS; unauthenticated write returned 401 |
| Full `task lite:check` | PASS after canonical documentation regeneration |
| Overall | QUALIFIED WITH LIMITATIONS |

No commit, push, merge, tag, release or GitHub PR operation was performed.

## Final Qualification Closure

This section is the final closure of the qualification sequence and supersedes
the earlier interim status tables above. It records the state after resuming
from the existing restore journal; no replacement restore was started during
this closure turn.

### Closure identity and worktree

| Item | Result |
| --- | --- |
| Branch | `fix/recovery-live-qualification-blockers` |
| Base / current main / origin main | `2a11ad60df22daccd298279771407337f16c7435` |
| Worktree | Intentionally dirty; the branch contains the existing implementation, generated projections and qualification evidence. |
| Reconciliation | 321 dirty entries were classified as canonical source, tests, generated output, qualification evidence/report, or known pre-existing changes; no unexpected artifact was identified. |
| Git mutation | No commit, push, PR, merge, tag, release or GitHub operation. |

### Recovery projection closure

The original healthy-runtime `projection_too_old` condition was caused by
three interacting lifecycle defects: prepared projections relied on an old
`updated_at` rather than durable worker completion proof; Recovery details
were dirtied by unrelated fleet revisions; and legacy adaptive probe intervals
could exceed the 60/90-second prepared-read fences. The implementation now
uses durable `projection_refresh_state.last_completed_at`, Recovery-specific
dirty signals, bounded semantic source caches, Recovery-only detail inputs and
cadences inside the outer stale fences. The protection remains fail closed for
a genuinely stuck projection.

One earlier bounded live probe also produced a transient
`SemanticSourceUnavailable`/`database_unavailable` result for the Recovery
summary while details and NATS remained healthy. The prepared last-good state
was retained safely and the next reads recovered without a service restart.
The new regression test forces the first `SQLITE_READS` admission to fail,
asserts the source probe fails closed, and proves the next probe recovers. No
production timeout or stale-read guard was weakened.

The final five-sample live window had:

- Recovery summary: healthy, `read_degraded=false`, `refresh_pending=false`,
  approximately 1.2--15.4 seconds old, below the 60-second maximum stale
  fence.
- Recovery details: healthy, `read_degraded=false`,
  `refresh_pending=false`, approximately 0.6--37.7 seconds old, below the
  90-second maximum stale fence.
- NATS readiness: healthy on every sample; 3 connections, 0 slow consumers,
  and 1 current Pocket Lab agent connection.
- PM2 restart counts unchanged across all samples: API 22, worker 42,
  node-agent 0, supervisor 1, NATS 1 and Caddy 1; all were online.
- Explicit Tailscale socket: backend `Running`, 2 peers, 1 online peer.

### Restore journal and staging closure

The successful selected restore remains authoritative:

- restore `3141eb3f9ac1413caf98b39faf8aa6fc`: journal `committed`, terminal
  status `committed`, checkpoint created, integrity/schema/migration/foreign
  key checks passed, OPA revision matched exactly, and post-restore health
  validation passed;
- fault restore `ee917a37a1ca4d34bf244c2b467f205e`: injected at
  `after_sqlite_promotion`, ended `failed_with_rollback`, journal phase
  `rolled_back`, checkpoint projection matched, and no success event was
  emitted;
- final journal audit found zero unresolved restore transactions;
- four known abandoned registered staging trees were removed through the
  backend bounded cleanup helper, including the identifier transcription
  correction discovered during this closure; the final backend inventory for
  the configured staging root reported zero restore staging directories;
- the live staging-cleanup retry branch was not forced with another
  destructive fault. A separate PM2-inherited namespace enumeration was too
  slow on the Android filesystem and was not replaced with raw path deletion.

### Runtime and ownership closure

The server-host fleet projection is `healthy`, with agent and supervisor
processes online, fresh, and converged (`state=ready`,
`last_good_projection=true`, `profile_ready=true`, `supervisor_ready=true`).
The enrolled compute peer remains `Offline`/stale with remote access false;
secondary-device end-to-end convergence is therefore not claimed.

Qualification isolation is closed: the runtime reported production mode,
qualification-owner mode disabled and test-auth bypass disabled; synthetic
identity, membership, credential, session, enrollment-claim, recovery-code and
WebAuthn rows were zero; and unauthenticated backup writes returned HTTP 401
through both the direct API and Caddy. No owner credential or token was
created, exposed or printed.

The current PhotoPrism deployment uses SQLite application metadata. The real
backup validated the PhotoPrism metadata database with quick-check, integrity,
foreign-key and table-count checks. MariaDB remains a separate fail-closed
adapter requirement for deployments that actually use MariaDB; no MariaDB
claim is made for this runtime.

The local isolated storage-fault harness completed 7/7 deterministic
failpoints with zero false successes, zero false accepts, zero partial outputs,
zero active-key leaks and an authoritative SQLite quick-check of `ok`. No
live storage fill or destructive ENOSPC injection was performed.

### Final qualification matrix

| Area | Final status | Evidence / limitation |
| --- | --- | --- |
| Canonical SQLite backup and restore | `VERIFIED` | Existing online-backup/database-recovery, integrity, migration, foreign-key, lock, maintenance and transaction machinery exercised. |
| Versioned encrypted restore point | `VERIFIED` | Backup `7541d16ec9c141a2bc7458ea8ac6b7dd`, format 2, verified/restorable, snapshot `663fd9edb80d9728ae4b0ee9b93a94e5443107f1446416b61d67210e19cee118`. |
| Backup scope and exclusions | `VERIFIED` | Canonical control-plane state, policy, Security, sanitized evidence, app metadata/config and current SQLite PhotoPrism metadata included; Android/shared storage and PhotoPrism media excluded. |
| Secret redaction | `VERIFIED` | Manifest/API/UI/evidence redaction and generated redaction checks passed; no passwords, hashes, tokens, keys, NATS credentials or private paths exposed. |
| Timestamped bounded history | `VERIFIED` | Newest-first bounded history and selected `backup_id` detail/verify/preview/recover path covered. |
| Preview binding and confirmation | `VERIFIED` | Preview bound to backup ID, manifest checksum, target revision and preview ID; stale preview and missing confirmation are rejected. |
| Successful selected restore | `VERIFIED` | Restore `3141eb3f9ac1413caf98b39faf8aa6fc` committed and returned the backed-up differentiator. |
| Rollback after mutation failure | `VERIFIED` | Promotion fault restore `ee917a37a1ca4d34bf244c2b467f205e` rolled back 18,232 files truthfully. |
| OPA policy reactivation | `VERIFIED` for current SQLite deployment | Active, known-good and repository revision matched `plr-568a6e9c23a6e3e13725ed5f130e4774`; MariaDB deployment path not applicable. |
| PhotoPrism metadata | `VERIFIED` for current SQLite driver | Logical metadata validation passed; MariaDB adapter remains fail-closed and unqualified. |
| Media preservation | `VERIFIED` | Structural fingerprint unchanged; media contents were not read or archived. |
| Projection freshness | `VERIFIED` | Five live samples healthy and below summary/details stale fences; genuinely stuck projection test remains. |
| API/worker/runtime stability | `VERIFIED` | Five-sample PM2 counts unchanged; all required server-host services online. |
| Agent/supervisor convergence | `VERIFIED` for server host | Fleet projection ready and fresh; compute peer remains offline. |
| NATS/Tailscale local transport | `VERIFIED` | NATS agent connection and zero slow consumers; explicit Tailscale socket reports Running. |
| Qualification owner isolation | `VERIFIED` | Disabled flags, zero synthetic rows, unauthenticated direct/Caddy write 401. |
| ENOSPC safety | `VERIFIED` local-only | 7/7 isolated deterministic failpoints passed; live storage exhaustion was not attempted. |
| Staging cleanup retry branch | `PARTIAL` | Bounded retry implementation and regression test pass; no second destructive live fault was injected solely to observe retries. |
| Authenticated live Recovery UI | `UNVALIDATED` | Mocked desktop/mobile E2E, Storybook and accessibility passed; no authenticated Owner browser session was used against the live Server Phone. |
| Secondary-device end-to-end recovery | `UNVALIDATED` | The enrolled compute peer is currently offline. |
| Overall | `QUALIFIED WITH LIMITATIONS` | Control-plane backup/verify/preview/selected-restore is qualified; live UI, live ENOSPC, live retry observation, MariaDB deployments and secondary-peer convergence remain bounded limitations. |

### Final local validation

The final local gate evidence recorded exit code 0 for every command in
`task lite:check`, including:

- Python compilation and focused backend: the added focused recovery/storage/
  PhotoPrism/qualification selection passed `82` tests with one known
  Starlette/httpx deprecation warning;
- backend semantic gate: `170 passed, 163 deselected`;
- backend full gate: `388 passed, 1 warning`;
- frontend unit: `196 passed`;
- production PWA build: passed with the existing large-chunk warning;
- Storybook: `188` canonical stories and `10` representative renders;
- mocked Playwright: `27 passed, 7 skipped`;
- accessibility: `2 passed`;
- documentation browser: `60 passed`;
- strict documentation evidence: passed with `74` existing Redocly warnings,
  generated docs checks, strict MkDocs and runtime-network fencing;
- generated redaction: passed;
- `git diff --check`: passed.

The first API-check invocation was intentionally not counted as a product
failure: it used system `python3` without FastAPI. The same `task
lite:api:check` rerun with `.venv/bin` first on `PATH` passed, and the full
gate used that corrected environment.

### Remaining live qualification and risks

Before an unconditional production claim, an operator must still perform a
controlled authenticated UI sequence and, with explicit authorization, a
live Server Phone qualification that covers the currently offline peer,
PhotoPrism media immutability, the current SQLite metadata restore, audit
evidence, Recovery freshness after mutation, and any deployment-specific
MariaDB adapter. Do not perform a live destructive restore or fill storage
without explicit operator authorization.

Material risks remain schema compatibility for future/unknown formats, safe
secret recovery classes not represented by the current canonical mechanism,
PhotoPrism/MariaDB driver differences, Termux interruption during restic or
promotion, disk exhaustion, rollback failure after checkpoint mutation, and
OPA activation proof. The implementation fails closed for unsupported
formats, unsafe paths, unknown snapshots, invalid checksums, unavailable
policy activation and cleanup failure; it does not silently reinterpret or
claim partial recovery.

The resulting enterprise value is a governed, encrypted, auditable restore
point with selected-history recovery, explicit preview and confirmation,
checkpoint/rollback protection, policy and identity continuity, sanitized
operator evidence, media exclusion, truthful runtime freshness and a clear
boundary between qualified control-plane behavior and remaining physical
device qualification.

## Post-Qualification Follow-Up Coverage

Date: 2026-09-10

This section records the follow-up work performed from the frozen qualified
PR head `1aa331cec4e7b5c8bbc464e06990b42b856d2b33` on the local branch
`feat/recovery-qualification-followups`. It does not rewrite the historical
qualification sections above. No backup, verify, preview, restore, service
restart, storage allocation, credential access, or live qualification bypass
was used during this follow-up.

### B1 — Authenticated live Recovery UI

`UNVALIDATED`. The supported browser connector contained only an empty
`about:blank` tab and no normal authenticated Owner session. No qualification
Owner, test-auth bypass, copied cookie, CSRF proof, API token, or browser role
header was used to manufacture UI evidence. Existing mocked desktop/mobile
coverage, Storybook states, and accessibility coverage remain source/test
evidence only. A future operator run must use a real supported Owner session
to inspect timestamped history, selected-backup details, preview, confirmation,
active backup, active restore, rollback, and projection-refreshing states.

### B2 — Safe ENOSPC seam decision

`VERIFIED` for the safe local seam; `UNVALIDATED` for live disk exhaustion.
`lite_storage_faults.py` remains an allowlisted isolated fault mechanism and
the focused storage tests pass. The repository-owned long-gate dry run
selected only deterministic isolated low-storage behavior with zero live
allocation. No `--allow-storage-pressure`, real storage fill, or production
restore fault was invoked. This is the correct bounded decision for a live
Server Phone consumer until an operator authorizes an isolated target with a
measured reserve and an explicit allocation cap.

### B3 — Staging-cleanup retry decision

`PARTIAL / VERIFIED LOCALLY`. The backend cleanup helper uses bounded retry
evidence (`attempts` and a truthful failed status), and the regression test
simulates a transient Termux handle-release error: the first removal fails,
the second succeeds, and the staging tree is gone. No additional destructive
restore was forced solely to observe this branch live. If a future interrupted
restore naturally exercises it, the journal must remain the authority for a
cleanup failure and never be reported as successful recovery.

### B4 — PhotoPrism/MariaDB scope decision

`VERIFIED` for the current SQLite deployment; `UNVALIDATED / FAIL CLOSED` for
MariaDB deployments. The registered PhotoPrism adapter proves the configured
driver before inspecting metadata and rejects MySQL/MariaDB/PostgreSQL when no
logical adapter is registered. Focused tests cover SQLite metadata and the
MariaDB fail-closed path. The current Server Phone qualification used SQLite;
no MariaDB completeness claim is made, and no speculative adapter was added
on this branch.

### B5 — Secondary peer

`UNVALIDATED`. A bounded read-only fleet probe returned a healthy projection
with two records: one online server host and one offline compute peer;
`remote_access` was ready for the server host and false for the offline peer.
No enrollment, identity, repair, or restart action was attempted. Secondary
device recovery remains an operator qualification requirement after that peer
is online and converged.

### B6 — Bounded runtime soak

`VERIFIED` for read-only fleet/NATS stability; `UNVALIDATED` for an
authenticated Recovery projection soak. Six samples at 30-second intervals
returned healthy fleet state, bounded projection ages of approximately
0.6–18.8 seconds, `read_degraded=false`, no persistent refresh pending state,
one online/one offline peer, and connected NATS on every sample. This did not
read protected Recovery summary/details because no normal Owner session was
available, so it does not replace the prior five-sample authenticated Recovery
freshness window or prove a longer protected-read soak.

### Follow-up disposition

No source defect was found in these six seams that could be repaired safely
without changing the qualified PR. The follow-up branch therefore contains
qualification documentation only, remains local, is not pushed, and has no
second PR. The qualified PR remains frozen and must be reviewed independently
before any merge decision.
