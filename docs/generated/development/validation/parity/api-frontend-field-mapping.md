---
title: "API-to-Frontend Field Mapping"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 44a849b588fbdf72c3f81bf6f44ee5beef37bfd3c290bd1247a85d7ba4f0135c
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
