---
title: "API-to-Frontend Field Mapping"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 8a90a66c46a250cebfd7e62993f9c541fa1c293fd7e4dd880cc399353b42bff4
generator: scripts/docs/parity/generate_parity.py
---

# API-to-Frontend Field Mapping
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| ID | Source | Target | Transformation | Sensitivity | Test |
| --- | --- | --- | --- | --- | --- |
| api-status-selector | status | status | normalizeRecoveryStatus | public-summary | parity-selector-status |
| api-backup-selector | last_backup | latest_backup | normalizeRecoveryBackup allowlist | public-summary | parity-selector-backup |
| api-preview-selector | latest_restore_preview | restore_preview | normalizeRecoveryPreview allowlist | public-summary | parity-selector-preview |

Intentional presentation transformations are semantic and are not treated as parity failures.
