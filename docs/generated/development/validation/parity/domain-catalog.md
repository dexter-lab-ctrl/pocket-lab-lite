---
title: "Domain Parity Catalog"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Domain Parity Catalog
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Domain | Repository status | Backend | API | Selectors | Mocked browser | Live API | Live UI | Live Termux | Semantic parity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Home | partial | lite-status-service, system-health-projection, installed-release-identity | /api/lite/status, /api/lite/release | buildLiteHomeOverview | verified | unvalidated | unvalidated | unvalidated | unvalidated |
| Apps | partial | app-current-state, app-action-lifecycle | /api/lite/catalog, /api/lite/apps/photoprism/actions, /api/lite/apps/lifecycle | selectLiteCatalogAppSummary, selectPhotoPrismActionsView, selectPhotoPrismManageView | verified | unvalidated | unvalidated | unvalidated | unvalidated |
| Devices | partial | device-current-state, device-heartbeats, device-supervisor-state | /api/lite/fleet | selectDevicesScreenView, selectLiteDeviceCard, selectRemoteAccessHealthView | verified | unvalidated | unvalidated | unvalidated | unvalidated |
| Security | partial | security-scan-runs, security-findings, security-compact-state | /api/lite/security/summary, /api/lite/security/profiles/quick, /api/lite/security/history?limit=20 | selectSecuritySummaryView, selectSecurityScreenView, selectSecurityProfileView | verified | unvalidated | unvalidated | unvalidated | unvalidated |
| Identity | partial | identity-runtime-projection, invite-identity-registry | /api/lite/identity | direct-render | verified | unvalidated | unvalidated | unvalidated | unvalidated |
| Rules | partial | workflow-current-state | /api/lite/policy | direct-render | verified | unvalidated | unvalidated | unvalidated | unvalidated |
| Backup & Restore | ready-with-accepted-limitations | backup-state-file, backup-manifest, backup-receipt | /api/lite/recovery/summary, /api/lite/recovery/details, /api/lite/recovery/operations, /api/lite/recovery/backups | selectRecoverySummaryView, selectRecoveryScreenView | verified | verified | verified | verified | unvalidated |
