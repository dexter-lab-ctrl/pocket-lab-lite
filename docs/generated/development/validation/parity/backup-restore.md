---
title: "Backup & Restore Parity Specification"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 44a849b588fbdf72c3f81bf6f44ee5beef37bfd3c290bd1247a85d7ba4f0135c
generator: scripts/docs/parity/generate_parity.py
---

# Backup & Restore Parity Specification
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## 1. Current status

| Repository | Fixture | Mock browser | Live API | Live UI | Live Termux | Runtime parity | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| verified | verified | verified | observed | observed | observed | drift-detected | needs-review |

## 2. Repository-backed flow

```text
React/Vite PWA screen: recovery
→ Caddy same-origin proxy
→ FastAPI: /api/lite/recovery/backups, /api/lite/recovery/database, /api/lite/recovery/details, /api/lite/recovery/operations, /api/lite/recovery/summary
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

Status: **observed**

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
| maintenance_state | primary | path | maintenance.status | exact | high |
| last_restore_id | database | path | last_restore.restore_id | exact | critical |
| last_restore_status | database | path | last_restore.status | exact | critical |
| last_restore_completed_at | database | path | last_restore.completed_at | exact | high |
| latest_preview_id | database | path | latest_restore_preview.preview_id | exact | high |
| restore_allowed | database | path | latest_restore_preview.restore_allowed | exact | critical |
| fresh_preview_required | database | path | latest_restore_preview.requires_confirmation | exact | critical |
| restore_history_total | database | path | restore_history.total | exact | high |
| completed_restore_count | database | path | restore_history.completed | exact | high |
| preview_reference_count | database | path | restore_history.preview_references | exact | high |
| projection_reconciliation_status | database | path | projection_reconciliation.status | exact | high |

## 10. Live UI observation

Status: **observed**. Screen: `recovery`. Required projects: live-desktop, live-mobile.

Browser capture uses visible semantics, accessible controls, existing stable screen identifiers, bounded text, exact backend-derived identity checks, and privacy redaction.

## 11. Live Termux observation

Status: **observed**. The Termux lane uses the same allowlisted GET adapters through the managed read-only SSH alias and the phone loopback API, or an explicitly configured safe tunnel. It never reads databases, credentials, or environment secrets and never restarts services.

## 12. Field-level semantic comparisons

| Mapping | Boundary | Backend observation | Frontend observation | Comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| recovery-latest-backup-identity | live-api-live-ui | latest_backup_id | latest_backup_id | identity-match | critical |
| recovery-stale-semantics | live-api-live-ui | read_degraded | summary_label | intentional-presentation-map | critical |
| recovery-write-safety | live-api-live-ui | read_degraded | backup_action_disabled | boolean-equivalence | critical |
| recovery-status-presentation | live-api-live-ui | status | status_label | intentional-presentation-map | high |
| recovery-summary-presentation | live-api-live-ui | read_degraded | summary_label | intentional-presentation-map | high |
| recovery-sanitized-ui | live-api-live-ui | $ | screen_text | safe-redaction | critical |
| recovery-last-restore-identity | live-api-live-ui | last_restore_id | last_restore_id | identity-match | critical |
| recovery-last-restore-status | live-api-live-ui | last_restore_status | last_restore_status_label | intentional-presentation-map | critical |
| recovery-history-count | live-api-live-ui | completed_restore_count | restore_history_count | exact | high |
| recovery-historical-preview-safety | live-api-live-ui | fresh_preview_required | fresh_preview_required_visible | boolean-equivalence | critical |

## 13. Mapped presentation differences

| Mapping | Comparator | Allowlisted presentation |
| --- | --- | --- |
| recovery-stale-semantics | intentional-presentation-map | {"false": ["Recovery Ready", "Recovery is ready"], "true": ["Recovery information needs a refresh", "needs a refresh"]} |
| recovery-status-presentation | intentional-presentation-map | {"degraded": ["Review", "needs a refresh"], "failed": ["Attention", "needs attention"], "healthy": ["Protection ready", "Protected", "Ready"], "unknown": ["Checking", "Review"]} |
| recovery-summary-presentation | intentional-presentation-map | {"false": ["Recovery Ready", "Recovery is ready", "Backup and restore"], "true": ["Recovery information needs a refresh"]} |
| recovery-last-restore-status | intentional-presentation-map | {"completed": ["Restored", "Completed"], "failed": ["Needs review", "Failed"], "rolled_back": ["Rolled back safely", "Rolled back"]} |

Different user-facing wording or formatting is not drift when an allowlisted deterministic mapping proves equivalent meaning.

## 14. Detected drift

| Comparison | Boundary | Severity | Project | Explanation |
| --- | --- | --- | --- | --- |
| desktop-mobile-semantic-agreement | desktop-mobile | high | cross-viewport | desktop and mobile semantic surfaces differ |
| recovery-historical-preview-safety | live-api-live-ui | critical | live-desktop | boolean meaning differs or is not recognized |
| recovery-history-count | live-api-live-ui | high | live-desktop | values are not exactly equal |
| recovery-last-restore-identity | live-api-live-ui | critical | live-desktop | normalized values differ |
| recovery-last-restore-status | live-api-live-ui | critical | live-desktop | frontend presentation is outside the allowlisted mapping |
| recovery-latest-backup-identity | live-api-live-ui | critical | live-desktop | normalized values differ |
| recovery-stale-semantics | live-api-live-ui | critical | live-desktop | frontend presentation is outside the allowlisted mapping |
| recovery-summary-presentation | live-api-live-ui | high | live-desktop | frontend presentation is outside the allowlisted mapping |
| recovery-write-safety | live-api-live-ui | critical | live-desktop | boolean meaning differs or is not recognized |

Drift is valid review evidence; this page does not authorize changing backend or frontend behavior automatically.

## 15. Accepted limitations

- Status labels intentionally use Lite-friendly wording instead of raw backend enums.
- App restore apply remains explicitly unsupported where the repository reports it unavailable.
- Historical restore previews are evidence only and never authorize a new restore.

## 16. Unsupported operations

- Unsafe writes remain disabled while the recovery projection is stale.

## 17. Known gaps

- Live Termux and live browser semantic capture remain explicit; missing capture is not drift.

## 18. Evidence hashes

| Evidence | SHA-256 / semantic fingerprint |
| --- | --- |
| backend-recovery | 2a294575a10d0218269a4b3046687e1c3d9b9492b6e9c89606929a45296e4303 |
| browser-recovery-live-desktop | edb56c9b4f8b7da510c3b066bdf71281567499d39964e693eb6429cec15f7281 |
| browser-recovery-live-mobile | 19a1dad5d991a1bdeaeb317656957fd24ff74f2ed59f087049647e611179541b |
| observation-backend | 494b6c44757e3ea1ed3de8e0eb4c941142fd49473f6fda78fdae88d855daf301 |
| observation-live_desktop | f5b9b82c38397708c671b03aa68f5947d514f3a6ed07a22b8953c6d13de53b39 |
| observation-live_mobile | 97db123da33a13b865fcef3ea3693e435ba0e9e4022cb97c41a8c0deea809fa6 |
| observation-termux | 5523dadde5186a6ab511470fc58ef6ee8158cb11ec7b4afc00f8c683b37f9c57 |
| playwright-report | 2327e3f46af50c663807512084239fcbb26650df0147e09767f07dfb1a685e53 |
| runtime-comparison | 405b5ac408de70bf3055afffd62c5dcd5475c107ac9e56548c18fe17b7b31347 |
| termux-recovery | d8079d077e1a6510daa8e80bde23ff4f9b25b24d518d4c05f4ced1d4417ba913 |

No raw API payload, database row, hostname, username, private address, browser trace, or screenshot is stored in the promoted baseline.

## 19. Release and source binding

| Baseline schema | Release tag | Source commit | Promoted at |
| --- | --- | --- | --- |
| 2.0.0 | lite-2026.08.12.2 | a6e4abc37ee9cca62c27286c556607ff3e740561 | 2026-08-12T16:00:40Z |

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

| Runtime parity | Runtime status | Match | Mapped | Mismatch | Unsupported | Not observed | Not applicable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| drift-detected | needs-review | 27 | 5 | 9 | 0 | 0 | 0 |
