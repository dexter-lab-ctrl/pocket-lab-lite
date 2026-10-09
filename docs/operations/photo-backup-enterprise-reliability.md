# Photo Backup reliability workstream (unvalidated)

This change is an incremental implementation, **not P0–P4 completion**. Per-transfer capacity is rechecked against both planning and hard limits; oversized items are deferred rather than stopping all smaller media, and source size/mtime is rechecked before transfer.

## Current readiness and previous backup history

The server reports current readiness separately from the latest job result. Current admission requires a working source, PhotoPrism runtime, secure route, and **positive planning-space budget**. A previous error cannot override the current status headline. Backend reason codes differentiate PhotoPrism stopped/unreachable and hard/planning storage blocks. Older job reason codes remain readable.

## Storage admission

The destination's actual filesystem supplies total/free bytes. Credential redemption checks the current planning budget before disclosing a transfer credential. Pocket Lab retains a hard 10% reserve and a preferred 15% reserve (minimum 2 GiB). When the planning budget is zero, new transfers are blocked even when the hard reserve has not been exhausted. Concurrent non-Pocket-Lab writers may reduce free space; measured capacity is not an absolute guarantee.

## Repair

Termux repair runs only the fixed `pkg install -y rclone` invocation, bounded at 300 seconds. Package-manager failures, timeouts, and verification failures are distinct sanitized outcomes. An agent reports success only when installation and verification succeed. This does not yet provide a durable server-side repair operation state machine.

## Destinations

`server-photoprism-originals` is the only supported WebDAV transfer destination. Removable volumes, NAS, other enrolled nodes and object storage are listed as unsupported. These entries cannot be selected for transfer, and no arbitrary path, URL, or filesystem migration occurs. Disaster recovery remains separate from storing originals on the Server Phone.

## Limitations and qualification

Streaming inventory, durable per-object checkpoints, stronger integrity verification, independent destination adapters, repair lifecycle durability, mounting/identity enforcement for newly supported storage and full UX/test coverage remain deferred. No tests, lint, build, docs generators, GitHub Actions inspection, or device qualification were performed.

Suggested later DEV-PC qualification:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest tests/backend/test_lite_photo_backup.py tests/backend/test_lite_photo_backup_agent.py tests/backend/test_lite_photo_backup_reliability.py
npm run build
npx playwright test tests/e2e/lite-photo-backup.spec.ts
task lite:docs:check
task lite:check
```

Rollback: revert application commits, retain existing media and job history, and do not remove existing credential or PhotoPrism state. Physical Android/Termux behavior must be separately verified before deployment.


## P0 readiness continuation — source implementation, not qualified

The backend returns a versioned current readiness projection independently from
`latest_backup`. It exposes `source_ready`, `destination_operational`,
`safe_capacity_available`, `backup_admissible`, an ordered set of stable
reason-code blockers, sanitized remediation categories, and a checked timestamp.

A bounded, cached unauthenticated HTTPS OPTIONS probe checks whether the
configured same-origin PhotoPrism WebDAV route responds. An authentication
challenge is **route reachable**, not **credentials verified**; the
`webdav_authenticated` field is therefore null in this projection.
The worker still performs authenticated OPTIONS and PROPFIND using an
individually scoped, expiring PhotoPrism app password, and will not issue a
transfer command if its authenticated probe fails.

Current readiness checks never disclose passwords, filesystem paths or
upstream error bodies. The route probe times out in three seconds and caches
its sanitized classification for 20 seconds. Starting a new backup forces
a fresh probe and runtime check, and the worker rechecks runtime, route
and protected storage before creating transfer credentials. Both checks
fail closed on unavailable WebDAV or depleted planning reserve.

Only the existing fixed PhotoPrism originals destination is eligible.
A successful OPTIONS response does not prove WebDAV write permission,
mount identity or credential validity; these require worker-scoped
authentication and runtime qualification. A healthy control API is
not sufficient to mark photo backup ready.

### P0 qualification explicitly deferred

Tests for cache reuse, route challenge handling, forbidden/insecure origins,
independent readiness semantics and capacity classifications were added,
but **not executed**. No live media, Termux, HTTP or credential operation
was exercised in this implementation session. Extra failure-code taxonomy,
reservation conflicts, heartbeat field compatibility and mount identity
need runtime/contract verification before production qualification.


## P0 closure implementation — volume binding, heartbeat and lifecycle

The fixed PhotoPrism originals destination now stores a private, server-owned
identity anchor at `lite_photo_backup_destination_identity.json` within the
control-plane state directory. The binding includes the resolved originals
path, operating-system device identity and filesystem identity, represented
as a SHA-256 fingerprint; the raw path or disk identifiers are not exposed
to the UI. A mismatch fails closed with
`destination_identity_mismatch` and the anchor is not automatically
updated. An operator must verify/remount the original volume or perform a
separate, explicitly authorized migration; do not edit the binding blindly.
Initial anchoring is trust-on-first-use at the already configured originals
path, **not** external media attestation. Filesystem capacity, path permissions
and WebDAV access are still checked independently.

Fleet heartbeat freshness now uses `last_seen_epoch` from the fleet
registry first, then known timestamp variants. Timestamp-less legacy
records fail closed as `source_capabilities_stale` rather than being
presumed fresh. Confirm the agent is reporting fresh fleet heartbeats before
attempting a backup.

Cross-device destination exclusivity failures now include
`storage_reservation_conflict`. Credential expiry and node/backup
identity mismatch have distinct stable reason codes. The public job view
exposes only the sanitized `credential_revoke_status` (pending/revoked/none)
and never the internal credential reference or PhotoPrism auth identifier.
A pending credential revocation remains visible independently from current
backup readiness. The shared destination still uses its existing single-job
admission lock; this change does not introduce a multi-process quota scheduler.

**Source changes and regression cases were committed without execution.**
No tests, builds, CI inspection or live device qualification were performed.
Full runtime correctness and the exact device-volume behavior remain
**unvalidated**.
