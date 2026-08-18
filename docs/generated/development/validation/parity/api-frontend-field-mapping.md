---
title: "API-to-Frontend Field Mapping"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 0b555a4643cccbb5d48b5dd4e1492fc4487803cb12ab52681cdbd77e6e2bac27
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
