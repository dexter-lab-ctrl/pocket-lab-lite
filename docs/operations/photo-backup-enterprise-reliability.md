# Photo Backup reliability workstream (unvalidated)

This change is an incremental implementation, **not P0–P4 completion**.

## Current readiness and previous backup history

The server reports current readiness separately from the latest job result. Current admission requires a working source, PhotoPrism runtime, secure route, and **positive planning-space budget**. A previous error cannot override the current status headline. Backend reason codes differentiate PhotoPrism stopped/unreachable and hard/planning storage blocks. Older job reason codes remain readable.

## Storage admission

The destination's actual filesystem supplies total/free bytes. Pocket Lab retains a hard 10% reserve and a preferred 15% reserve (minimum 2 GiB). When the planning budget is zero, new transfers are blocked even when the hard reserve has not been exhausted. Concurrent non-Pocket-Lab writers may reduce free space; measured capacity is not an absolute guarantee.

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
