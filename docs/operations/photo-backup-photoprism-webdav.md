# Photo Backup to PhotoPrism WebDAV

## Status

**Phase 1 implementation:** feature-branch implementation for Pocket Lab-managed photo and video backup from enrolled secondary Android/Termux devices to the Server Phone's existing PhotoPrism originals storage.

**Bounded production acceptance:** the backend also supports a short-lived, server-issued acceptance fixture. It is intended for one deliberately bounded test photo and does not expand the normal collection-wide UI workflow. The fixture path and bytes are agent-owned; the caller cannot provide a source path.

**Runtime qualification:** the feature branch still requires release-bound qualification on the real Server Phone and at least one enrolled secondary Android/Termux phone before production acceptance. A synthetic or isolated candidate result is not production evidence. Until the deployed branch is qualified, treat physical runtime behavior as **UNVALIDATED ON SERVER PHONE**.

## Product boundary

Photo Backup is a Pocket Lab backup workflow, not PhotoPrism Import and not generic file synchronization.

```text
Devices UI
  -> FastAPI /api/lite/*
  -> NATS / JetStream semantic command
  -> Pocket Lab worker
  -> targeted node command
  -> pocketlab_node_agent.py
  -> constrained rclone WebDAV copy
  -> Caddy / Tailscale HTTPS
  -> PhotoPrism originals
  -> PhotoPrism native delayed indexing
```

FastAPI and NATS carry control data only. Photo and video bytes travel directly from the enrolled device to PhotoPrism WebDAV. The frontend never receives a WebDAV credential and never talks to NATS.

## Source and destination policy

Eligible Android media roots are bounded to the enrolled device's Camera/DCIM, Pictures, and Movies/Video collections. Hidden files, `.nomedia` trees, thumbnails, caches, temporary folders, downloads/documents, and unsupported file types are excluded.

Android storage permission is explicit. Enrollment remains successful when media permission is unavailable; photo backup is simply shown as not ready. On a Termux device, the operator can run `termux-setup-storage` once and approve Android's storage/photos-and-videos permission, then return to Pocket Lab.

The destination is derived from backend PhotoPrism and Caddy/Tailscale state. Phase 1 uses a stable per-device namespace:

```text
PhotoPrism originals/
  PocketLab/
    Devices/
      <stable-node-id>/
        DCIM/
        Pictures/
        Movies/
```

The node cannot provide an arbitrary URL, path, rclone flag, remote, or command.

## Bounded acceptance workflow

Do not use a collection-wide backup as the first production test when the source contains personal media. Use the backend-owned acceptance fixture only after the read-only destination, capacity, agent, and authorization preflight passes.

1. An authenticated operator requests `POST /api/lite/devices/{node_id}/photo-backup/acceptance-fixture` for an enrolled secondary device.
2. FastAPI verifies the fresh agent heartbeat, rclone capability, Pictures access, and secondary-device eligibility. It returns an opaque fixture ID with a 30-minute expiry; no source path is returned or stored.
3. The operator submits that ID to the normal `POST /api/lite/devices/{node_id}/photo-backup` action. The backend forces the source scope to the fixed `pictures` collection and revalidates the fixture while holding the admission lock. Client-supplied collections cannot widen the scope.
4. The secondary agent creates a metadata-free JPEG only at its fixed `Pictures/PocketLabAcceptance/<fixture-id>.jpg` location. It refuses symlinks, refuses to overwrite different bytes, inventories exactly that one object, and transfers it to `Pictures/PocketLabAcceptance/<fixture-id>.jpg` inside the server-owned `PocketLab/Devices/<node-id>/` namespace.
5. The normal NATS/JetStream command, scoped WebDAV credential, staging/finalization, progress, evidence, and credential-revocation lifecycle remains in force. A repeated request for the same completed fixture is reconciled through the normal ledger and does not create a duplicate object.

This route is an operational acceptance surface, not a frontend filesystem or shell surface. It must be released and deployed through the normal reviewed workflow before it can be used against production phones. If the installed runtime does not expose this route, do not substitute a broad backup.

## Destination enrollment and recovery

The Server Phone originals filesystem is enrolled by the backend during the protected admission capacity check. The backend resolves the canonical originals directory, rejects symlinked or non-writable targets, computes the filesystem-bound fingerprint, and atomically writes the private destination identity anchor only when no anchor exists. The anchor is private state and is not an operator-supplied fingerprint.

First enrollment is allowed only after the operator has independently verified the intended PhotoPrism originals mount, ownership, permissions, available capacity, and absence of a conflicting identity. A matching existing anchor is reused. A malformed anchor, changed filesystem identity, different destination, or stale placement fails closed with `destination_identity_mismatch`; never delete, regenerate, or rebind that anchor as a normal retry.

The admission capacity formula remains unchanged: retain the 10% hard reserve and the larger of 15% of total storage or 2 GiB as the planning reserve. Capacity, identity, WebDAV route readiness, fresh secondary heartbeat, and active-job exclusion are rechecked at the mutation boundary. The backend writes sanitized lifecycle evidence; the agent and UI never receive the private volume fingerprint or backend credential.

If a first enrollment or bounded transfer fails, leave existing identity state and user media untouched, allow the short-lived fixture to expire, and retry only after the reported prerequisite is resolved. If an identity mismatch is reported, stop and use the separately authorized protected recovery procedure. There is no automatic rollback that removes a PhotoPrism destination copy; indexed destination media is retained according to the PhotoPrism backup-retention contract.

## Credential lifecycle

Pocket Lab creates a short-lived PhotoPrism app password scoped to WebDAV for one admitted backup. The raw value is kept server-side only long enough to provision the job.

NATS receives only an opaque `credential_ref`. Before one-time delivery, the backend encrypts the short-lived handoff at rest with a Pocket Lab runtime key stored separately with mode `0600`. The target agent resolves that reference once through an authenticated internal FastAPI endpoint over HTTPS. The agent writes a private temporary rclone config with mode `0600`, runs the bounded copy, and removes the temporary directory afterward.

The raw app password must never be written to normal Lite state, audit/evidence output, browser state, NATS command payloads, logs, process arguments, or long-lived configuration. Credential cleanup is required on success, cancellation, failure, stale-job recovery, device removal, and expiry. Revocation evidence is truthful: if PhotoPrism revocation cannot be confirmed, Pocket Lab records a bounded **revocation pending** state and the worker recovery loop retries it instead of claiming the credential was revoked.

## Copy and conflict semantics

Phase 1 is copy-only:

- no `rclone sync`;
- no source-deletion propagation;
- no bidirectional synchronization;
- no generic rsync media backup;
- no destination purge/delete workflow.

Remote inventory uses size and modification time so unchanged files can be skipped without hashing every media file. If a destination name already exists with different metadata, Pocket Lab uses a deterministic version suffix rather than overwriting it.

Each transfer first writes an unsupported temporary name and then performs a same-WebDAV server-side move to the final name. A cancelled or interrupted temporary object is ignored by the retry flow and is not treated as a completed media item.

## Storage safety

The capacity probe runs against the actual PhotoPrism originals filesystem.

- hard reserve: **10% of total Server Phone storage**;
- planning reserve: **max(15% of total, hard reserve, 2 GiB)**;
- safe planning budget: `free - planning reserve`;
- hard transfer budget: `free - hard reserve`.

When the full eligible source set does not fit the safe budget, Pocket Lab selects complete files deterministically, newest first with stable timestamp/path tie-breaking. It reports required bytes, planned bytes, transferred bytes, remaining bytes, and remaining items. Free space is checked again before each file transfer. No file is intentionally started if doing so would cross the hard reserve.

Only one fleet photo-backup transfer is admitted against the Server Phone destination at a time.

## Retry and interruption model

Repeated start requests for the same active device backup are idempotent. A second device receives a retryable busy result while another fleet photo backup is active. Worker redelivery reconciles the existing operation and does not rotate credentials or republish a duplicate node start command.

Completed files remain complete. Retries re-inventory the destination and skip matching completed objects. An interrupted or cancelled run therefore resumes by copying only work that is still incomplete.

The node persists only a small non-secret active-job marker. If the node-agent process restarts, it reports the prior run as interrupted after reconnect and clears the marker only after the backend acknowledges that terminal state. The worker separately reconciles stale jobs and pending credential revocations.

Cancellation terminates the active rclone child, keeps completed destination files, removes local temporary configuration, requests immediate credential revocation, and keeps retrying revocation if the first attempt cannot be confirmed.

## PhotoPrism processing truth

A successful WebDAV transfer does not claim that PhotoPrism has already indexed and rendered every new item. After bytes finish transferring, the UI can show **Transfer complete. PhotoPrism is processing the new media in the background.**

Pocket Lab relies on PhotoPrism's native WebDAV-triggered delayed indexing behavior. Phase 1 does not start a broad full-library re-index after every backup.

## Import safety

PhotoPrism's existing **Import photos** action is a separate workflow. Phase 1 fails closed when a live phone-media mapping could make PhotoPrism Import move/delete the same source media that Pocket Lab is treating as a backup source. Backup via WebDAV originals must not be routed through PhotoPrism Import.

## Backup ownership and app removal

Pocket Lab-managed device backups live in the stable `PocketLab/Devices/<node-id>/` namespace under PhotoPrism originals and are treated as user backup media, not disposable app cache. This branch introduces no media-delete operation. Device removal stops future transfers and revokes outstanding credentials but preserves previously copied media. PhotoPrism removal continues to follow the repository's existing media-preservation contract; this feature does not make uninstall a backup-media deletion path.

## Safe-read boundary

Photo-backup GET endpoints are projection/read paths only. They do not create PhotoPrism directories, revoke credentials, or reconcile stale operations. Worker startup and the worker recovery watchdog own stale-job reconciliation, expired handoff cleanup, and pending credential-revocation retries.

## API surface

User-facing semantic reads and actions:

```text
GET  /api/lite/media-backup
GET  /api/lite/devices/{node_id}/photo-backup
POST /api/lite/devices/{node_id}/photo-backup/acceptance-fixture
POST /api/lite/devices/{node_id}/photo-backup
POST /api/lite/devices/{node_id}/photo-backup/cancel
POST /api/lite/devices/{node_id}/photo-backup/repair
```

Internal agent-only endpoints resolve one-time credentials, current capacity, and aggregate progress. They are authenticated with the enrolled node identity and are intentionally excluded from the public OpenAPI surface.

## UI ownership

**Devices** owns setup and control: source readiness, Camera/Pictures/Videos selection, start, live progress, partial-storage state, Retry, Stop backup, permission guidance, and tool-repair state.

**Apps -> PhotoPrism -> Manage** shows only lightweight backup truth: whether a device is ready, whether a backup is running, and the latest aggregate result. It points operational control back to Devices.

The UI never exposes raw filesystem paths, per-file inventories, raw rclone output, WebDAV credentials, app passwords, NATS subjects, or backend command payloads.

## Evidence and indexing

Fixture preparation is recorded as a sanitized `lite.photo_backup.acceptance_fixture.prepared` lifecycle event. The backup job then records its fixed source scope, destination contract, aggregate transfer counts, integrity mode, terminal state, and credential-revocation result without exposing paths or secrets. Successful WebDAV finalization proves that the object reached the authorized originals namespace; it does not by itself prove PhotoPrism indexing. Verify indexing separately through the supported PhotoPrism view or API and report transfer-complete/processing when indexing is still pending.

The generated fixture is disposable source media, but the destination copy is managed backup media. Do not delete the destination object merely to make test cleanup appear complete. Remove only the source fixture created by the acceptance session when that cleanup is explicitly safe and does not conflict with PhotoPrism retention or indexing.

## Validation

Development qualification should include:

```bash
python3 -m py_compile \
  pocket-lab-final-structure/runtime/api_fastapi/services/lite_photo_backup.py \
  pocket-lab-final-structure/runtime/agents/lite_photo_backup_agent.py \
  pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py \
  pocket-lab-final-structure/runtime/api_fastapi/routers/fleet.py

bash -n \
  pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-termux-packages.sh \
  pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/ensure-fleet-media-tools.sh

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q \
  tests/backend/test_lite_photo_backup.py \
  tests/backend/test_lite_photo_backup_agent.py

npm run build
npx playwright test tests/e2e/lite-photo-backup.spec.ts --project=mocked-desktop --project=mocked-mobile
task lite:api:check
task lite:check
git diff --check
```

Physical qualification must additionally verify real Android permission handling, secondary-device rclone installation, Tailscale HTTPS reachability, PhotoPrism WebDAV OPTIONS/PROPFIND/PUT/MOVE behavior through the deployed Caddy subpath, short-lived app-password creation/revocation (including pending-revocation retry), partial-storage behavior, network interruption/resume, agent and worker restart reconciliation, cancellation cleanup, source-deletion preservation, and PhotoPrism indexing after WebDAV writes.

Phase 1 intentionally does **not** claim a terminal “Available in PhotoPrism” state until runtime evidence can prove the native delayed index completed. The implemented UI truthfully stops at transfer completion plus PhotoPrism processing.
