---
title: "Backup & Restore Parity Specification"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Backup & Restore Parity Specification
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

**Current status:** ready-with-accepted-limitations

## Repository-backed flow

```text
manifests / receipts / SQLite recovery state
→ FastAPI recovery summary, details, operations and cursor history
→ TanStack Query
→ selectRecoverySummaryView / selectRecoveryScreenView
→ LiteRecovery React surface
→ Storybook / Playwright / evidence
```

## Authorities

| ID | Kind | Location | Writer | Exposure |
| --- | --- | --- | --- | --- |
| backup-state-file | json-state | state_dir/backup_state.json | lite_backup | allowlisted summary only |
| backup-manifest | json-manifest | backup_root/manifests/{backup_id}.json | lite_backup_manifest.write_manifest | api_manifest allowlist |
| backup-receipt | json-receipt | backup_root/receipts/{backup_id}.json | lite_backup_manifest.write_receipt | api_receipt allowlist |
| restore-preview | json-preview | backup_root/restore-previews/{preview_id}.json | lite_backup.create_restore_preview | allowlisted preview |
| restore-checkpoint | checkpoint | backup_root/restore-checkpoints/{checkpoint_id}.json | lite_backup.apply_restore | identifier and status only |
| restore-run | json-run | backup_root/restore-runs/{restore_id}.json | lite_backup.apply_restore | sanitized status and counts |
| backup-manifest-index | sqlite-table | backup_manifest_index | control-plane projection writer | prepared projection only |
| recovery-operations | sqlite-table | recovery_operations | recovery operation lifecycle | sanitized history |
| recovery-current-state | sqlite-table | recovery_current_state | recovery projection writer | prepared projection only |
| database-backup-table | sqlite-table | security_database_backups | lite_database_recovery | sanitized metadata |
| database-restore-table | sqlite-table | security_database_restores | lite_database_recovery | sanitized metadata |

## API projections

| Method | Endpoint | Backend sources | Freshness | Offline |
| --- | --- | --- | --- | --- |
| GET | /api/lite/recovery/summary | recovery-current-state, backup-state-file, backup-manifest-index | summary ETag/revision and last-good semantics | safe-summary |
| GET | /api/lite/recovery/details | backup-manifest, restore-preview, restore-checkpoint, restore-run, database-backup-table, database-restore-table | detail read on Manage intent | safe-details |
| GET | /api/lite/recovery/operations?limit={limit}&cursor={cursor} | recovery-operations | prepared projection revision | first-page-only |
| GET | /api/lite/recovery/backups?limit={limit}&cursor={cursor} | backup-manifest | manifest ordering | first-page-only |
| GET | /api/lite/recovery/receipts/{backup_id} | backup-receipt | immutable per backup update | not-cached-by-default |
| GET | /api/lite/recovery/database | database-backup-table, database-restore-table | prepared database recovery state | safe-summary |

## Prohibited data

Raw SQLite rows, raw manifests, restic passwords, backend secrets, private paths, media paths, raw logs, NATS credentials, and phone identity are not parity artifacts.
