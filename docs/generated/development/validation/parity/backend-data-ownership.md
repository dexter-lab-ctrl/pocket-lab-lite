---
title: "Backend Data Ownership Catalog"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 8a90a66c46a250cebfd7e62993f9c541fa1c293fd7e4dd880cc399353b42bff4
generator: scripts/docs/parity/generate_parity.py
---

# Backend Data Ownership Catalog
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Entity | Authority | Writer | Transaction | Projection | Retention | Recovery | Frontend |
| --- | --- | --- | --- | --- | --- | --- | --- |
| app-action-lifecycle | app action lifecycle state | app workers | backend-owned atomic or SQLite transaction | app-actions | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| app-current-state | app catalog and lifecycle current state | app worker and projection writers | backend-owned atomic or SQLite transaction | catalog | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| backup-manifest | backup_root/manifests/{backup_id}.json | lite_backup_manifest.write_manifest | temp file + fsync + replace | recovery-backup-history | backup retention policy | manifest checksum | api_manifest allowlist |
| backup-manifest-index | backup_manifest_index | control-plane projection writer | SQLite transaction | recovery-summary/recovery-details | manifest lifecycle | rebuild from manifests | prepared projection only |
| backup-receipt | backup_root/receipts/{backup_id}.json | lite_backup_manifest.write_receipt | temp file + fsync + replace | recovery-backup-receipt | aligned with manifest | sanitized evidence reference | api_receipt allowlist |
| backup-state-file | state_dir/backup_state.json | lite_backup | atomic JSON replace | recovery-summary | latest pending and operation state | last-good file read | allowlisted summary only |
| database-backup-table | security_database_backups | lite_database_recovery | SQLite transaction | recovery-database | maintenance policy | verified database backup | sanitized metadata |
| database-restore-table | security_database_restores | lite_database_recovery | SQLite transaction | recovery-database | maintenance policy | restore run state | sanitized metadata |
| device-current-state | durable device registry and prepared fleet projection | fleet services and reconciliation | backend-owned atomic or SQLite transaction | fleet | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| device-heartbeats | sanitized heartbeat projection | node agents | backend-owned atomic or SQLite transaction | fleet | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| device-supervisor-state | sanitized supervisor evidence | agent supervisors | backend-owned atomic or SQLite transaction | fleet | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| identity-runtime-projection | identity readiness projection | identity backend services | backend-owned atomic or SQLite transaction | identity | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| installed-release-identity | installed release identity | release workflow | backend-owned atomic or SQLite transaction | release-status | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| invite-identity-registry | device identity and invite lifecycle | fleet invite services | backend-owned atomic or SQLite transaction | identity | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| lite-status-service | lite_status service composition | worker/agent telemetry and prepared projections | backend-owned atomic or SQLite transaction | lite-status | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| recovery-current-state | recovery_current_state | recovery projection writer | SQLite transaction | recovery-summary/recovery-details | current row per recovery entity | last-good projection | prepared projection only |
| recovery-operations | recovery_operations | recovery operation lifecycle | SQLite transaction | recovery-operations | cursor-paginated history | operation reconciliation | sanitized history |
| restore-checkpoint | backup_root/restore-checkpoints/{checkpoint_id}.json | lite_backup.apply_restore | created before state mutation | recovery-details | recovery policy | rollback source | identifier and status only |
| restore-preview | backup_root/restore-previews/{preview_id}.json | lite_backup.create_restore_preview | atomic JSON write | recovery-details | bounded recovery evidence | recreate preview | allowlisted preview |
| restore-run | backup_root/restore-runs/{restore_id}.json | lite_backup.apply_restore | phase updates | recovery-details | recovery policy | last-run evidence | sanitized status and counts |
| security-compact-state | compact security state files | security state coordinator | backend-owned atomic or SQLite transaction | security-summary | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| security-findings | sanitized finding state | security worker | backend-owned atomic or SQLite transaction | security-summary | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| security-scan-runs | security scan run state | security worker | backend-owned atomic or SQLite transaction | security-summary | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| system-health-projection | system current-state projections | phase3b projection writers | backend-owned atomic or SQLite transaction | lite-status | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
| workflow-current-state | OPA/policy advisory state | policy backend service | backend-owned atomic or SQLite transaction | rules | repository-defined current and last-good state | backend-owned reconciliation and last-good behavior | allowlisted sanitized FastAPI projection |
