---
title: "Security Parity Specification"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 44a849b588fbdf72c3f81bf6f44ee5beef37bfd3c290bd1247a85d7ba4f0135c
generator: scripts/docs/parity/generate_parity.py
---

# Security Parity Specification
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## 1. Current status

| Repository | Fixture | Mock browser | Live API | Live UI | Live Termux | Runtime parity | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| verified | partial | verified | observed | observed | observed | verified-with-mapped-presentation | verified |

## 2. Repository-backed flow

```text
React/Vite PWA screen: security
→ Caddy same-origin proxy
→ FastAPI: /api/lite/security/summary, /api/lite/security/profiles/quick, /api/lite/security/history?limit=20
→ repository authorities: security-compact-state, security-findings, security-scan-runs
→ sanitized projection / selector / rendered UI
```

## 3. Backend authorities

| Authority | Kind | Repository location | Writer | Reader | Frontend exposure |
| --- | --- | --- | --- | --- | --- |
| security-compact-state | compact-projection | compact security state files | security state coordinator | split security read API | allowlisted sanitized FastAPI projection |
| security-findings | sqlite-and-evidence | sanitized finding state | security worker | lite security service | allowlisted sanitized FastAPI projection |
| security-scan-runs | sqlite-table | security scan run state | security worker | lite security service | allowlisted sanitized FastAPI projection |

## 4. FastAPI routes

| Method | Endpoint | Backend sources | Freshness | Degraded behavior | Sanitization |
| --- | --- | --- | --- | --- | --- |
| GET | /api/lite/security/history?limit={limit} | security-scan-runs | prepared projection revision | safe stale/degraded/unavailable state | allowlist |
| GET | /api/lite/security/profiles/{profile} | security-scan-runs, security-findings, security-compact-state | prepared projection revision | safe stale/degraded/unavailable state | allowlist |
| GET | /api/lite/security/summary | security-compact-state | ETag/revision | saved summary | allowlist |

## 5. Frontend selectors and screens

| Selectors/presentation | Query keys | Screens |
| --- | --- | --- |
| selectSecuritySummaryView, selectSecurityScreenView, selectSecurityProfileView | liteQueryKeys.security, liteQueryKeys.securityProfile, liteQueryKeys.securityHistory | security |

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

- src/lite/LiteSecurity.stories.jsx

## 8. Mocked-browser scenarios

- tests/e2e/lite-mocked.spec.ts

## 9. Live API observation

Status: **observed**

| Observation | Route adapter | Extractor | Path | API ↔ Termux comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| status | primary | path | status | exact | high |
| summary | primary | path | summary | exact | high |
| score | primary | path | score | exact | high |
| active_scan | primary | path | scan_progress.active_scan | exact | high |
| profile | primary | path | last_run.scan_profile | exact | high |
| finding_count | primary | path | findings_count | exact | high |

## 10. Live UI observation

Status: **observed**. Screen: `security`. Required projects: live-desktop, live-mobile.

Browser capture uses visible semantics, accessible controls, existing stable screen identifiers, bounded text, exact backend-derived identity checks, and privacy redaction.

## 11. Live Termux observation

Status: **observed**. The Termux lane uses the same allowlisted GET adapters through the managed read-only SSH alias and the phone loopback API, or an explicitly configured safe tunnel. It never reads databases, credentials, or environment secrets and never restarts services.

## 12. Field-level semantic comparisons

| Mapping | Boundary | Backend observation | Frontend observation | Comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| security-summary-presentation | live-api-live-ui | status | screen_text | intentional-presentation-map | critical |
| security-primary-action | live-api-live-ui | $ | button_names | presence | high |
| security-profile-presentation | live-api-live-ui | profile | screen_text | intentional-presentation-map | medium |
| security-sanitized-ui | live-api-live-ui | $ | screen_text | safe-redaction | critical |

## 13. Mapped presentation differences

| Mapping | Comparator | Allowlisted presentation |
| --- | --- | --- |
| security-summary-presentation | intentional-presentation-map | {"degraded": ["Needs attention", "Review"], "failed": ["needs attention"], "healthy": ["No urgent safety issues", "Safe", "Protected"], "running": ["Checking safety", "Checking"], "unknown": ["checking"]} |
| security-profile-presentation | intentional-presentation-map | {"app": ["App Check", "PhotoPrism"], "full": ["Full Local Check", "Full"], "quick": ["Quick", "Safety Check"]} |

Different user-facing wording or formatting is not drift when an allowlisted deterministic mapping proves equivalent meaning.

## 14. Detected drift

| Comparison | Boundary | Severity | Project | Explanation |
| --- | --- | --- | --- | --- |

No promoted semantic drift is recorded for this domain.

## 15. Accepted limitations

- Raw scanner output and sensitive paths are intentionally excluded.

## 16. Unsupported operations

- The browser never runs Lynis, Trivy, shell, PM2, or NATS commands.

## 17. Known gaps

- A missing scanner is runtime-unavailable, not semantic drift.

## 18. Evidence hashes

| Evidence | SHA-256 / semantic fingerprint |
| --- | --- |
| backend-security | e867a89289f457f8fa68f71a06b929b0449b9618303c265f26c69235c34cb51e |
| browser-security-live-desktop | 6b3d0849871147e2bd43ff8b6c12c8dffafec449a1a8e8b765c66a7bc6a36e6f |
| browser-security-live-mobile | 76df3ef0b65d2f3021d0f7016b5cf77c3f48338e80743845df101d1e2123b2a0 |
| observation-backend | 3b2cae7b3fcde01bdc94c7486e9be517a0f2119b760d4570baf1525fc7ba251b |
| observation-live_desktop | 3cfcdbbe5c0f707338e3bc7216b00624092248534b7e96322ef4a2b3b2f30ca5 |
| observation-live_mobile | 3cfcdbbe5c0f707338e3bc7216b00624092248534b7e96322ef4a2b3b2f30ca5 |
| observation-termux | 3b2cae7b3fcde01bdc94c7486e9be517a0f2119b760d4570baf1525fc7ba251b |
| playwright-report | e5db3fbc6a27b2e50d0c8dfb61a66c49d4d3b1ac5fd900e481c30278860c4dc4 |
| runtime-comparison | c791b467b9c2b8c658ae5960329abd8615c1b62edb5ee3fe82d916a08728e0a6 |
| termux-security | 5e06a5765e7688a26ec131557e0d34058a0134e6f14ba5b3c4eb6ec2e506305b |

No raw API payload, database row, hostname, username, private address, browser trace, or screenshot is stored in the promoted baseline.

## 19. Release and source binding

| Baseline schema | Release tag | Source commit | Promoted at |
| --- | --- | --- | --- |
| 2.0.0 | lite-2026.08.06.2 | ae54d3adf6c544d040fb923a1894f66b2a92513c | 2026-08-06T18:14:18Z |

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
| verified-with-mapped-presentation | verified | 11 | 4 | 0 | 0 | 0 | 0 |
