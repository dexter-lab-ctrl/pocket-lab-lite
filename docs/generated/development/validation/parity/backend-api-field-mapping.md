---
title: "Backend-to-API Field Mapping"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 0b555a4643cccbb5d48b5dd4e1492fc4487803cb12ab52681cdbd77e6e2bac27
generator: scripts/docs/parity/generate_parity.py
---

# Backend-to-API Field Mapping
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| ID | Source | Target | Transformation | Sensitivity | Test |
| --- | --- | --- | --- | --- | --- |
| recovery-status | recovery current status | status | normalize status enum | public-summary | parity-recovery-status |
| recovery-summary | recovery summary | summary | allowlisted text | public-summary | parity-recovery-summary |
| latest-backup-id | manifest.backup_id | last_backup.backup_id | direct stable identifier | evidence-identifier | parity-latest-backup-id |
| verification-status | manifest.verification_status | last_backup.verification_status | normalized enum | public-summary | parity-verification-status |
| preview-id | restore preview.preview_id | latest_restore_preview.preview_id | direct stable identifier | evidence-identifier | parity-preview-id |
| restore-allowed | restore preview.restore_allowed | latest_restore_preview.restore_allowed | derived guard boolean | public-summary | parity-restore-allowed |
| checkpoint-id | checkpoint.checkpoint_id | pre_restore_checkpoint.checkpoint_id | direct stable identifier | evidence-identifier | parity-checkpoint-id |
| restore-id | restore run.restore_id | last_restore.restore_id | direct stable identifier | evidence-identifier | parity-restore-id |

Intentional presentation transformations are semantic and are not treated as parity failures.
