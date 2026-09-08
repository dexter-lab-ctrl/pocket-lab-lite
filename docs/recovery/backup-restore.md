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
