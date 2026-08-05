---
title: "Backend Data Ownership Catalog"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Backend Data Ownership Catalog
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Entity | Authority | Writer | Transaction | Projection | Retention | Recovery | Frontend |
| --- | --- | --- | --- | --- | --- | --- | --- |
| backup-state-file | state_dir/backup_state.json | lite_backup | atomic JSON replace | recovery-summary | latest pending and operation state | last-good file read | allowlisted summary only |
| backup-manifest | backup_root/manifests/{backup_id}.json | lite_backup_manifest.write_manifest | temp file + fsync + replace | recovery-backup-history | backup retention policy | manifest checksum | api_manifest allowlist |
| backup-receipt | backup_root/receipts/{backup_id}.json | lite_backup_manifest.write_receipt | temp file + fsync + replace | recovery-backup-receipt | aligned with manifest | sanitized evidence reference | api_receipt allowlist |
| restore-preview | backup_root/restore-previews/{preview_id}.json | lite_backup.create_restore_preview | atomic JSON write | recovery-details | bounded recovery evidence | recreate preview | allowlisted preview |
| restore-checkpoint | backup_root/restore-checkpoints/{checkpoint_id}.json | lite_backup.apply_restore | created before state mutation | recovery-details | recovery policy | rollback source | identifier and status only |
| restore-run | backup_root/restore-runs/{restore_id}.json | lite_backup.apply_restore | phase updates | recovery-details | recovery policy | last-run evidence | sanitized status and counts |
| backup-manifest-index | backup_manifest_index | control-plane projection writer | SQLite transaction | recovery-summary/recovery-details | manifest lifecycle | rebuild from manifests | prepared projection only |
| recovery-operations | recovery_operations | recovery operation lifecycle | SQLite transaction | recovery-operations | cursor-paginated history | operation reconciliation | sanitized history |
| recovery-current-state | recovery_current_state | recovery projection writer | SQLite transaction | recovery-summary/recovery-details | current row per recovery entity | last-good projection | prepared projection only |
| database-backup-table | security_database_backups | lite_database_recovery | SQLite transaction | recovery-database | maintenance policy | verified database backup | sanitized metadata |
| database-restore-table | security_database_restores | lite_database_recovery | SQLite transaction | recovery-database | maintenance policy | restore run state | sanitized metadata |
