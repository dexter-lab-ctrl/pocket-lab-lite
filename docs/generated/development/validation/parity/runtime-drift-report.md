---
title: "Runtime Semantic Drift Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 8a90a66c46a250cebfd7e62993f9c541fa1c293fd7e4dd880cc399353b42bff4
generator: scripts/docs/parity/generate_parity.py
---

# Runtime Semantic Drift Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

A semantic mismatch is valid promoted evidence. It indicates that observed backend meaning and rendered UI meaning diverged under an allowlisted comparator. Missing or failed capture is reported separately and is not drift.

| Domain | Mapping | Severity | Finding |
| --- | --- | --- | --- |
| Apps | apps-open-capability | critical | boolean meaning differs or is not recognized |
| Apps | apps-open-capability | critical | boolean meaning differs or is not recognized |
| Backup & Restore | desktop-mobile-semantic-agreement | high | desktop and mobile semantic surfaces differ |
| Backup & Restore | recovery-historical-preview-safety | critical | boolean meaning differs or is not recognized |
| Backup & Restore | recovery-history-count | high | values are not exactly equal |
| Backup & Restore | recovery-last-restore-identity | critical | normalized values differ |
| Backup & Restore | recovery-last-restore-status | critical | frontend presentation is outside the allowlisted mapping |
| Backup & Restore | recovery-latest-backup-identity | critical | normalized values differ |
| Backup & Restore | recovery-stale-semantics | critical | frontend presentation is outside the allowlisted mapping |
| Backup & Restore | recovery-summary-presentation | high | frontend presentation is outside the allowlisted mapping |
| Backup & Restore | recovery-write-safety | critical | boolean meaning differs or is not recognized |
