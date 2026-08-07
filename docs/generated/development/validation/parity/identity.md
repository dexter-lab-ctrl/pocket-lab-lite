---
title: "Identity Parity Specification"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 44a849b588fbdf72c3f81bf6f44ee5beef37bfd3c290bd1247a85d7ba4f0135c
generator: scripts/docs/parity/generate_parity.py
---

# Identity Parity Specification
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## 1. Current status

| Repository | Fixture | Mock browser | Live API | Live UI | Live Termux | Runtime parity | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| verified | partial | verified | observed | observed | observed | partial | partial |

## 2. Repository-backed flow

```text
React/Vite PWA screen: identity
→ Caddy same-origin proxy
→ FastAPI: /api/lite/identity
→ repository authorities: identity-runtime-projection, invite-identity-registry
→ sanitized projection / selector / rendered UI
```

## 3. Backend authorities

| Authority | Kind | Repository location | Writer | Reader | Frontend exposure |
| --- | --- | --- | --- | --- | --- |
| identity-runtime-projection | service-projection | identity readiness projection | identity backend services | lite identity service | allowlisted sanitized FastAPI projection |
| invite-identity-registry | sqlite-and-state | device identity and invite lifecycle | fleet invite services | identity and fleet readers | allowlisted sanitized FastAPI projection |

## 4. FastAPI routes

| Method | Endpoint | Backend sources | Freshness | Degraded behavior | Sanitization |
| --- | --- | --- | --- | --- | --- |
| GET | /api/lite/identity | identity-runtime-projection, invite-identity-registry | prepared projection revision | safe stale/degraded/unavailable state | allowlist |

## 5. Frontend selectors and screens

| Selectors/presentation | Query keys | Screens |
| --- | --- | --- |
| direct-render | liteQueryKeys.resource(/api/lite/identity) | identity |

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

- src/lite/LiteIdentity.stories.jsx

## 8. Mocked-browser scenarios

- tests/e2e/lite-mocked.spec.ts

## 9. Live API observation

Status: **observed**

| Observation | Route adapter | Extractor | Path | API ↔ Termux comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| status | primary | path | status | exact | high |
| summary | primary | path | summary | exact | high |
| target_count | primary | count | targets | exact | high |
| identity_guard | primary | path | identity_guard.status | exact | high |
| protected_host | primary | path | protected_server_host | exact | high |

## 10. Live UI observation

Status: **observed**. Screen: `identity`. Required projects: live-desktop, live-mobile.

Browser capture uses visible semantics, accessible controls, existing stable screen identifiers, bounded text, exact backend-derived identity checks, and privacy redaction.

## 11. Live Termux observation

Status: **observed**. The Termux lane uses the same allowlisted GET adapters through the managed read-only SSH alias and the phone loopback API, or an explicitly configured safe tunnel. It never reads databases, credentials, or environment secrets and never restarts services.

## 12. Field-level semantic comparisons

| Mapping | Boundary | Backend observation | Frontend observation | Comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| identity-status-presentation | live-api-live-ui | status | screen_text | intentional-presentation-map | critical |
| identity-summary | live-api-live-ui | summary | screen_text | text-contains | medium |
| identity-password-redaction | live-api-live-ui | $ | screen_text | safe-redaction | critical |

## 13. Mapped presentation differences

| Mapping | Comparator | Allowlisted presentation |
| --- | --- | --- |
| identity-status-presentation | intentional-presentation-map | {"degraded": ["Review"], "failed": ["Attention"], "healthy": ["Access readiness", "Ready"], "mismatch": ["mismatch", "repair", "rejoin"], "ready": ["Access readiness", "Ready"], "unknown": ["Checking access", "Checking access protection", "Access readiness"]} |

Different user-facing wording or formatting is not drift when an allowlisted deterministic mapping proves equivalent meaning.

## 14. Detected drift

| Comparison | Boundary | Severity | Project | Explanation |
| --- | --- | --- | --- | --- |

No promoted semantic drift is recorded for this domain.

## 15. Accepted limitations

- Credential values are never observable parity fields.
- Identity guard and protected server-host authority fields are planned and may remain unavailable until identity bootstrap services are implemented.

## 16. Unsupported operations

- Identity mismatch repair/rejoin must remain explicit and fail closed.

## 17. Known gaps

- The current tab is direct-rendered and has no dedicated selector layer.
- Identity guard and protected server-host projections are not fully implemented.

## 18. Evidence hashes

| Evidence | SHA-256 / semantic fingerprint |
| --- | --- |
| backend-identity | 976e3f8ec36cf62cbd95dbae4859e80011574947e177948655ed1dde7db8a133 |
| browser-identity-live-desktop | 9e956219646ac14a0b9a7b36240b3e54b5e555767d684d439b968b71cd21395e |
| browser-identity-live-mobile | 2a03d0996239f1c0ce3121ad1b3d6ae20ad589b953e97be572032c53bd5ff1b1 |
| observation-backend | d481f5125f8cab4356d1d164c9a1518483b786097fee788764bc6dbaa0dae757 |
| observation-live_desktop | 0c116788f2a43c3ebb778f963a0872cbf73a59d83d9b6632825a8024080b9da7 |
| observation-live_mobile | 0c116788f2a43c3ebb778f963a0872cbf73a59d83d9b6632825a8024080b9da7 |
| observation-termux | d481f5125f8cab4356d1d164c9a1518483b786097fee788764bc6dbaa0dae757 |
| playwright-report | 5d578784ed5d4ca4c79556b65c6e065fa0c782a022736487aa5bb118a7fb926d |
| runtime-comparison | 75e2ce0ba27765b03d32f62fc29d6280bc7679b56a6e64f675fefff76b62e6ca |
| termux-identity | b38a29cfbdbef34cfce8664dd6a74cc4fd05a846204f5c7cae1a23e8dbeb6a8a |

No raw API payload, database row, hostname, username, private address, browser trace, or screenshot is stored in the promoted baseline.

## 19. Release and source binding

| Baseline schema | Release tag | Source commit | Promoted at |
| --- | --- | --- | --- |
| 2.0.0 | lite-2026.08.07.1 | c44493ede19f45299277d4da3af215dfe4ea8db3 | 2026-08-07T07:16:22Z |

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
| partial | partial | 8 | 2 | 0 | 0 | 2 | 0 |
