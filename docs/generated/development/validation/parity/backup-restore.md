---
title: "Backup & Restore Parity Specification"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Backup & Restore Parity Specification
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## 1. Current status

| Repository | Fixture | Mock browser | Live API | Live UI | Live Termux | Runtime parity | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| verified | verified | verified | verified | verified | verified | unvalidated | ready-with-accepted-limitations |

## 2. Repository-backed flow

```text
React/Vite PWA screen: recovery
→ Caddy same-origin proxy
→ FastAPI: /api/lite/recovery/summary, /api/lite/recovery/details, /api/lite/recovery/operations, /api/lite/recovery/backups
→ repository authorities: backup-manifest, backup-manifest-index, backup-receipt, backup-state-file, database-backup-table, database-restore-table, recovery-current-state, recovery-operations, restore-checkpoint, restore-preview, restore-run
→ sanitized projection / selector / rendered UI
```

## 3. Backend authorities

| Authority | Kind | Repository location | Writer | Reader | Frontend exposure |
| --- | --- | --- | --- | --- | --- |
| backup-manifest | json-manifest | backup_root/manifests/{backup_id}.json | lite_backup_manifest.write_manifest | lite_backup_manifest.read_manifest | api_manifest allowlist |
| backup-manifest-index | sqlite-table | backup_manifest_index | control-plane projection writer | prepared recovery projections | prepared projection only |
| backup-receipt | json-receipt | backup_root/receipts/{backup_id}.json | lite_backup_manifest.write_receipt | lite_backup_manifest.read_receipt | api_receipt allowlist |
| backup-state-file | json-state | state_dir/backup_state.json | lite_backup | lite_backup.recovery_status | allowlisted summary only |
| database-backup-table | sqlite-table | security_database_backups | lite_database_recovery | database recovery projection | sanitized metadata |
| database-restore-table | sqlite-table | security_database_restores | lite_database_recovery | database recovery projection | sanitized metadata |
| recovery-current-state | sqlite-table | recovery_current_state | recovery projection writer | prepared recovery projections | prepared projection only |
| recovery-operations | sqlite-table | recovery_operations | recovery operation lifecycle | CONTROL_PLANE.recovery_operation_history | sanitized history |
| restore-checkpoint | checkpoint | backup_root/restore-checkpoints/{checkpoint_id}.json | lite_backup.apply_restore | lite_backup.get_restore_checkpoint | identifier and status only |
| restore-preview | json-preview | backup_root/restore-previews/{preview_id}.json | lite_backup.create_restore_preview | lite_backup.get_restore_preview | allowlisted preview |
| restore-run | json-run | backup_root/restore-runs/{restore_id}.json | lite_backup.apply_restore | lite_backup.get_restore_run | sanitized status and counts |

## 4. FastAPI routes

| Method | Endpoint | Backend sources | Freshness | Degraded behavior | Sanitization |
| --- | --- | --- | --- | --- | --- |
| GET | /api/lite/recovery/backups?limit={limit}&cursor={cursor} | backup-manifest | manifest ordering | invalid cursor returns sanitized 400 | api_manifest allowlist |
| GET | /api/lite/recovery/receipts/{backup_id} | backup-receipt | immutable per backup update | 404 sanitized | api_receipt allowlist |
| GET | /api/lite/recovery/database | database-backup-table, database-restore-table | prepared database recovery state | safe summary | allowlist |
| GET | /api/lite/recovery/details | backup-manifest, restore-preview, restore-checkpoint, restore-run, database-backup-table, database-restore-table | detail read on Manage intent | last-good safe details when available | allowlist |
| GET | /api/lite/recovery/operations?limit={limit}&cursor={cursor} | recovery-operations | prepared projection revision | invalid cursor returns sanitized 400 | allowlist |
| GET | /api/lite/recovery/summary | recovery-current-state, backup-state-file, backup-manifest-index | summary ETag/revision and last-good semantics | safe saved-state summary | allowlist |

## 5. Frontend selectors and screens

| Selectors/presentation | Query keys | Screens |
| --- | --- | --- |
| selectRecoverySummaryView, selectRecoveryScreenView | liteQueryKeys.recoverySummary, liteQueryKeys.recoveryDetails, liteQueryKeys.recoveryHistory | recovery |

## 6. Query and state ownership

| Layer | Owner | Responsibility | May store | Must not store |
| --- | --- | --- | --- | --- |
| tanstack-query | frontend-server-state | live FastAPI read cache, focused invalidation, stale/reconnect behavior across Lite tabs | sanitized Lite API projections; ETags; query timestamps | durable business authority; secrets; raw SQLite rows; write success before FastAPI confirmation |
| dexie | frontend-offline-snapshot | sanitized read-only fallback snapshots for explicitly eligible Lite GET projections | allowlisted safe Lite summaries; bounded snapshot metadata | write responses; credentials; raw manifests; raw evidence; private paths; identity or invite secrets |
| zustand | frontend-ui-state | harmless cross-tab overlay, navigation, selection, and feedback state | active tab; Manage/details open state; selected UI sections; toast and refresh feedback | authoritative backend status; device or app truth; backup or security completion truth; secrets |
| xstate | frontend-workflow-state | visible guided workflow coordination for risky or multi-step Lite actions | requested/queued/running UI stages; accepted command reference; confirmation state | durable operation truth; raw backend payloads; offline write queue |
| component-local | component | small component-local presentation state only | ephemeral disclosure state; copied-label feedback | backend authority; secrets; durable operation truth |
| storybook-msw | quality-fixtures | deterministic fixture rendering | synthetic sanitized scenarios | production truth; live credentials |
| playwright | browser-quality | mocked and explicit live browser semantic observation | bounded sanitized semantic observations; failure-only local artifacts | backend authority; raw secrets; phone identity; hostnames; usernames; private addresses |

FastAPI and repository authorities remain the source of truth. Frontend caches and workflow/UI state never become execution authority.

## 7. Storybook coverage

- src/lite/LiteRecoveryParity.stories.jsx

## 8. Mocked-browser scenarios

- tests/e2e/lite-parity.spec.ts

## 9. Live API observation

Status: **verified**

| Observation | Route adapter | Extractor | Path | API ↔ Termux comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| status | primary | path | status | exact | high |
| summary | primary | path | summary | exact | high |
| read_degraded | primary | path | read_degraded | exact | high |
| degraded_reason | primary | path | degraded_reason | exact | high |
| projection_age_ms | primary | path | projection_age_ms | numeric-tolerance | high |
| data_source | primary | path | data_source | exact | high |
| refresh_pending | primary | path | refresh_pending | exact | high |
| latest_backup_id | primary | path | latest_backup.backup_id | exact | high |
| verification_status | primary | path | latest_backup.verification_status | exact | high |
| restore_preview_status | primary | path | latest_restore_preview.status | exact | high |
| restore_allowed | primary | path | latest_restore_preview.restore_allowed | exact | high |
| last_restore_status | primary | path | last_restore.status | exact | high |
| maintenance_state | primary | path | maintenance.status | exact | high |
| database_protection_status | primary | path | database_protection.status | exact | high |

## 10. Live UI observation

Status: **verified**. Screen: `recovery`. Required projects: live-desktop, live-mobile.

Browser capture uses visible semantics, accessible controls, existing stable screen identifiers, bounded text, exact backend-derived identity checks, and privacy redaction.

## 11. Live Termux observation

Status: **verified**. The Termux lane uses the same allowlisted GET adapters through the managed read-only SSH alias and the phone loopback API, or an explicitly configured safe tunnel. It never reads databases, credentials, or environment secrets and never restarts services.

## 12. Field-level semantic comparisons

| Mapping | Boundary | Backend observation | Frontend observation | Comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| recovery-latest-backup-identity | live-api-live-ui | latest_backup_id | latest_backup_id | identity-match | critical |
| recovery-stale-semantics | live-api-live-ui | read_degraded | stale_warning_visible | boolean-equivalence | critical |
| recovery-write-safety | live-api-live-ui | read_degraded | backup_action_disabled | boolean-equivalence | critical |
| recovery-status-presentation | live-api-live-ui | status | status_label | intentional-presentation-map | high |
| recovery-summary-presentation | live-api-live-ui | read_degraded | summary_label | intentional-presentation-map | high |
| recovery-sanitized-ui | live-api-live-ui | $ | screen_text | safe-redaction | critical |

## 13. Mapped presentation differences

| Mapping | Comparator | Allowlisted presentation |
| --- | --- | --- |
| recovery-status-presentation | intentional-presentation-map | {"degraded": ["Review", "needs a refresh"], "failed": ["Attention", "needs attention"], "healthy": ["Protection ready", "Protected", "Ready"], "unknown": ["Checking", "Review"]} |
| recovery-summary-presentation | intentional-presentation-map | {"false": ["Recovery Ready", "Recovery is ready", "Backup and restore"], "true": ["Recovery information needs a refresh"]} |

Different user-facing wording or formatting is not drift when an allowlisted deterministic mapping proves equivalent meaning.

## 14. Detected drift

| Comparison | Boundary | Severity | Project | Explanation |
| --- | --- | --- | --- | --- |

No promoted semantic drift is recorded for this domain.

## 15. Accepted limitations

- Status labels intentionally use Lite-friendly wording instead of raw backend enums.
- App restore apply remains explicitly unsupported where the repository reports it unavailable.

## 16. Unsupported operations

- Unsafe writes remain disabled while the recovery projection is stale.

## 17. Known gaps

- Live Termux and live browser semantic capture remain explicit; missing capture is not drift.

## 18. Evidence hashes

| Evidence | SHA-256 / semantic fingerprint |
| --- | --- |

No raw API payload, database row, hostname, username, private address, browser trace, or screenshot is stored in the promoted baseline.

## 19. Release and source binding

| Baseline schema | Release tag | Source commit | Promoted at |
| --- | --- | --- | --- |
| 1.0.0 | lite-2026.08.05.2 | 3a81745fbd4c2fdeb17f2308a0d3fdbd5c2f3aa5 | 2026-08-06T07:48:03Z |

A legacy v1 baseline proves coverage only. It cannot upgrade semantic parity to verified.

## 20. Operator validation commands

```bash
task lite:parity:model:check
task lite:parity:contracts:check
task lite:parity:fixtures:check
LITE_PARITY_RELEASE_TAG=<release-tag> task lite:parity:runtime:capture
LITE_PARITY_RELEASE_TAG=<release-tag> task lite:parity:playwright:live
LITE_PARITY_RELEASE_TAG=<release-tag> task lite:parity:termux
task lite:parity:runtime:compare
LITE_PARITY_RELEASE_TAG=<release-tag> task lite:evidence:runtime:promote
task lite:evidence:runtime:check
```

## 21. Failure attribution guidance

- backend authority ≠ API projection
- API projection ≠ selector/direct presentation
- selector/direct presentation ≠ rendered UI
- mocked browser ≠ live browser
- live API ≠ Termux observation
- saved snapshot ≠ live API
- desktop ≠ mobile
- expected mapping ≠ actual wording
- capability advertised ≠ action available
- state machine ≠ rendered action state

Missing, failed, stale, or unavailable evidence is classified separately from drift.

## 22. Last promoted runtime result

| Runtime parity | Runtime status | Match | Mapped | Mismatch | Unsupported | Not observed |
| --- | --- | --- | --- | --- | --- | --- |
| unvalidated | unvalidated | 0 | 0 | 0 | 0 | 0 |
