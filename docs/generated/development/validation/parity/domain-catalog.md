---
title: "Domain Parity Catalog"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Domain Parity Catalog
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Domain | Status | Backend | API | Selector | Storybook | Mocked browser | Live Termux |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Backup & Restore | ready-with-accepted-limitations | backup-state-file, backup-manifest, backup-receipt | recovery-summary, recovery-details, recovery-operations, recovery-backup-history | selectRecoveryScreenView | verified | verified | unvalidated |
| Devices | partial | device-current-state, device-heartbeats, device-supervisor-state | fleet | selectDevicesScreenView | verified | verified | runtime-source-verified |
| Apps | partial | app-current-state, app-action-lifecycle | catalog, app-actions | selectLiteCatalogView | verified | verified | runtime-source-verified |
| Security | partial | security-scan-runs, security-findings, security-compact-state | security-summary, security-profile, security-history | selectSecurityScreenView | verified | verified | runtime-source-verified |
| Rules | planned | workflow-current-state | rules | unverified | partial | partial | unvalidated |
| Releases | partial | installed-release-identity, release-runtime-projection | release-status | source-derived | partial | partial | runtime-source-verified |
