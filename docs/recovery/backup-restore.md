# Backup and Restore

Pocket Lab Lite supports encrypted, timestamped restore points through the existing
FastAPI → NATS/JetStream → worker operation model. The SQLite control-plane database
remains canonical; the existing online-backup and database recovery transaction is
included rather than copied into a second store.

## Backup

User-facing action:

```text
Backup Now
```

The backend queues the full restore-point operation through FastAPI, NATS / JetStream,
and the worker. A restore point contains Lite control-plane state, Identity & Access
continuity records, Devices/fleet state, Security history and sanitized evidence
metadata, Rules/OPA lifecycle state, App Catalog and safe PhotoPrism configuration
metadata, Recovery history, and the verified SQLite online-backup package.

Each point has a versioned manifest, timestamp, snapshot ID, component results,
checksums, and an encrypted restic repository reference. It is not restorable until
manifest, component, and repository verification pass. History is bounded and
cursor-paginated through `GET /api/lite/recovery/backups`.

## Backup location selection

Backup locations are backend-owned records on the protected Server Phone. The
default private location remains the normal destination. Additional removable
or configured locations are admitted only when the backend discovers them under
its trusted candidate policy; the browser never submits an arbitrary filesystem
path, connects to storage directly, or receives a raw path in an API response.
Each location has an opaque `location_id`, a stable repository identity, a
sanitized display label, and bounded health/capacity state. The Android system
folder picker is **not implemented** in this release, so the UI truthfully
shows backend-discovered candidates and does not imply that a native picker is
available.

Selection, discovery, and forgetting use the existing FastAPI → NATS/JetStream
→ worker command path and the protected `backup.location.manage` policy action.
Only the protected Server Phone target is selectable; device selection is not a
separate browser concern. Location changes are serialized with backup/restore
work, and a location cannot be forgotten while it is the active default.

Every new manifest and receipt records the immutable location identity and
repository fingerprint. History remains bound to the location that produced
it, even after the current selection changes. A forgotten or unavailable
location remains visible in history with a truthful unavailable state, but
verification, preview, and restore fail closed until the backend discovers the
location again. Restore staging and checkpoints remain on the active Server
Phone while the source read uses the manifest's recorded repository.

The location registry stores private paths only in the backend control-plane
database. It does not copy restic passwords, tokens, or other secrets to
removable storage. Android shared/media roots, runtime/database paths,
symlinks, nested repositories, and unsafe storage mappings are rejected before
registration.

The backup contract excludes Android shared storage (`/storage/emulated/*` and
`/sdcard`-style paths), PhotoPrism originals/import media/photos/videos/thumbnails
and recreatable caches, raw scanner output, `node_modules`, `.venv`, temporary
caches/logs, build output, the backup repository, and raw secrets. Registered app
storage mappings are treated as media and fail closed when a safe metadata boundary
cannot be proven.

## Restore

User-facing action:

```text
Restore
```

Restore must select an explicit `backup_id`, pass a verified preview bound to the
manifest checksum and current Recovery target revision, and require a clear
confirmation before execution. The backend acquires the global backup/restore guard,
creates a pre-restore checkpoint, fences affected writers through existing database
maintenance/restore machinery, validates SQLite and policy readiness, and commits
only after health checks. A post-mutation failure rolls back from the checkpoint and
reports `failed_with_rollback` or `failed_rollback_required` truthfully.

The UI should explain:

- what will be restored;
- what may change;
- whether a backup was verified;
- whether recovery is ready;
- how to cancel safely.

Personal Owner mode may create a backup without a second approver under the existing
policy model. Enterprise destructive recovery continues to use the configured OPA
and approval governance; this feature does not bypass it. Passwords, tokens, private
keys, restic credentials, private runtime paths, raw evidence, and command payloads
are never placed in manifests, API responses, UI payloads, logs, or receipts.

The PhotoPrism MariaDB logical-dump adapter remains unavailable unless the repository
has a registered service-specific metadata database configuration and validator;
media is never used as a fallback. Live Termux interruption, disk exhaustion,
service restart, OPA reactivation, and controlled restore qualification require
operator-run validation on the Server Phone.

## Validation

```bash
curl -s http://127.0.0.1:8080/api/lite/recovery
```

Expected result:

```text
Recovery state is returned as a user-friendly summary.
```
