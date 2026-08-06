---
title: "Domain Parity Catalog"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 44a849b588fbdf72c3f81bf6f44ee5beef37bfd3c290bd1247a85d7ba4f0135c
generator: scripts/docs/parity/generate_parity.py
---

# Domain Parity Catalog
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Domain | Repository status | Backend | API | Selectors | Mocked browser | Live API | Live UI | Live Termux | Semantic parity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Home | verified | lite-status-service, system-health-projection, installed-release-identity | /api/lite/status, /api/lite/release | buildLiteHomeOverview | verified | observed | observed | observed | verified-with-mapped-presentation |
| Apps | verified | app-current-state, app-action-lifecycle | /api/lite/catalog, /api/lite/apps/photoprism/actions, /api/lite/apps/lifecycle | selectLiteCatalogAppSummary, selectPhotoPrismActionsView, selectPhotoPrismManageView | verified | observed | observed | observed | verified-with-mapped-presentation |
| Devices | verified | device-current-state, device-heartbeats, device-supervisor-state | /api/lite/fleet | selectDevicesScreenView, selectLiteDeviceCard, selectRemoteAccessHealthView | verified | observed | observed | observed | verified-with-mapped-presentation |
| Security | verified | security-scan-runs, security-findings, security-compact-state | /api/lite/security/summary, /api/lite/security/profiles/quick, /api/lite/security/history?limit=20 | selectSecuritySummaryView, selectSecurityScreenView, selectSecurityProfileView | verified | observed | observed | observed | verified-with-mapped-presentation |
| Identity | partial | identity-runtime-projection, invite-identity-registry | /api/lite/identity | direct-render | verified | observed | observed | observed | partial |
| Rules | partial | workflow-current-state | /api/lite/policy | direct-render | verified | observed | observed | observed | partial |
| Backup & Restore | ready-with-accepted-limitations | backup-state-file, backup-manifest, backup-receipt | /api/lite/recovery/backups, /api/lite/recovery/database, /api/lite/recovery/details, /api/lite/recovery/operations, /api/lite/recovery/summary | selectRecoverySummaryView, selectRecoveryScreenView | verified | observed | observed | observed | partial |
