---
title: "Apps Parity Specification"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 8a90a66c46a250cebfd7e62993f9c541fa1c293fd7e4dd880cc399353b42bff4
generator: scripts/docs/parity/generate_parity.py
---

# Apps Parity Specification
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## 1. Current status

| Repository | Fixture | Mock browser | Live API | Live UI | Live Termux | Runtime parity | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| verified | partial | verified | observed | observed | observed | drift-detected | needs-review |

## 2. Repository-backed flow

```text
React/Vite PWA screen: catalog
→ Caddy same-origin proxy
→ FastAPI: /api/lite/catalog, /api/lite/apps/photoprism/actions, /api/lite/apps/lifecycle
→ repository authorities: app-action-lifecycle, app-current-state
→ sanitized projection / selector / rendered UI
```

## 3. Backend authorities

| Authority | Kind | Repository location | Writer | Reader | Frontend exposure |
| --- | --- | --- | --- | --- | --- |
| app-action-lifecycle | sqlite-and-projection | app action lifecycle state | app workers | lite app actions service | allowlisted sanitized FastAPI projection |
| app-current-state | prepared-projection | app catalog and lifecycle current state | app worker and projection writers | lite catalog services | allowlisted sanitized FastAPI projection |

## 4. FastAPI routes

| Method | Endpoint | Backend sources | Freshness | Degraded behavior | Sanitization |
| --- | --- | --- | --- | --- | --- |
| GET | /api/lite/apps/{app_id}/actions | app-action-lifecycle | prepared projection revision | safe stale/degraded/unavailable state | allowlist |
| GET | /api/lite/apps/lifecycle | app-current-state, app-action-lifecycle | prepared projection revision | safe stale/degraded/unavailable state | allowlist |
| GET | /api/lite/catalog | app-current-state | catalog revision | saved state | allowlist |

## 5. Frontend selectors and screens

| Selectors/presentation | Query keys | Screens |
| --- | --- | --- |
| selectLiteCatalogAppSummary, selectPhotoPrismActionsView, selectPhotoPrismManageView | liteQueryKeys.catalog, liteQueryKeys.appActions, liteQueryKeys.appLifecycle | catalog |

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

- src/lite/LiteCatalog.stories.jsx

## 8. Mocked-browser scenarios

- tests/e2e/lite-mocked.spec.ts

## 9. Live API observation

Status: **observed**

| Observation | Route adapter | Extractor | Path | API ↔ Termux comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| app_id | catalog | find | id | exact | high |
| app_name | catalog | find | name | exact | high |
| installed | catalog | find | installed | exact | high |
| runtime_status | catalog | find | status | exact | high |
| route_ready | catalog | find | access.route_ready | exact | high |
| open_enabled | catalog | find | actions.open | exact | high |
| action_status | actions | path | status | exact | high |

## 10. Live UI observation

Status: **observed**. Screen: `catalog`. Required projects: live-desktop, live-mobile.

Browser capture uses visible semantics, accessible controls, existing stable screen identifiers, bounded text, exact backend-derived identity checks, and privacy redaction.

## 11. Live Termux observation

Status: **observed**. The Termux lane uses the same allowlisted GET adapters through the managed read-only SSH alias and the phone loopback API, or an explicitly configured safe tunnel. It never reads databases, credentials, or environment secrets and never restarts services.

## 12. Field-level semantic comparisons

| Mapping | Boundary | Backend observation | Frontend observation | Comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| apps-canonical-name | live-api-live-ui | app_name | screen_text | text-contains | critical |
| apps-open-capability | live-api-live-ui | open_enabled | button_enabled.Open | boolean-equivalence | critical |
| apps-installed-manage | live-api-live-ui | installed | button_names | capability-map | high |
| apps-runtime-presentation | live-api-live-ui | runtime_status | screen_text | intentional-presentation-map | high |
| apps-sanitized-ui | live-api-live-ui | $ | screen_text | safe-redaction | critical |

## 13. Mapped presentation differences

| Mapping | Comparator | Allowlisted presentation |
| --- | --- | --- |
| apps-installed-manage | capability-map | {"false": ["Install"], "true": ["Manage"]} |
| apps-runtime-presentation | intentional-presentation-map | {"healthy": ["ready", "running"], "installed": ["installed"], "installing": ["installing"], "not_installed": ["setup needed", "install"], "ready": ["ready", "running"], "review": ["attention", "review"]} |

Different user-facing wording or formatting is not drift when an allowlisted deterministic mapping proves equivalent meaning.

## 14. Detected drift

| Comparison | Boundary | Severity | Project | Explanation |
| --- | --- | --- | --- | --- |
| apps-open-capability | live-api-live-ui | critical | live-desktop | boolean meaning differs or is not recognized |
| apps-open-capability | live-api-live-ui | critical | live-mobile | boolean meaning differs or is not recognized |

Drift is valid review evidence; this page does not authorize changing backend or frontend behavior automatically.

## 15. Accepted limitations

- PhotoPrism is the currently cataloged runtime app; cross-app coverage grows from the same contract.

## 16. Unsupported operations

- Restore apply and update apply remain unavailable unless separately implemented and validated.

## 17. Known gaps

- Application-owned media indexing is not a Pocket Lab parity authority.

## 18. Evidence hashes

| Evidence | SHA-256 / semantic fingerprint |
| --- | --- |
| backend-apps | f0d029d8c758adcd81e688c93b2a6db4d550643d7cb197b60c87e9a2cdd39b48 |
| browser-apps-live-desktop | 9c69f9760647c5dfd81620b9baa3e4adad65c8bb835feb48add682f7242b035f |
| browser-apps-live-mobile | 9ace18e0f911984ca9ec2a65997d345dd0dfea9c36063fb0a240de175c5ce14e |
| observation-backend | 3e5efbd03159faa6048d3e9dc183c40defe19db8c4922b6946ea8419d4a6253f |
| observation-live_desktop | e2e72f1331b4a930992384474af1f61737fd7605ddfe55bccdde144ad74d5b26 |
| observation-live_mobile | e2e72f1331b4a930992384474af1f61737fd7605ddfe55bccdde144ad74d5b26 |
| observation-termux | 3e5efbd03159faa6048d3e9dc183c40defe19db8c4922b6946ea8419d4a6253f |
| playwright-report | 2327e3f46af50c663807512084239fcbb26650df0147e09767f07dfb1a685e53 |
| runtime-comparison | 405b5ac408de70bf3055afffd62c5dcd5475c107ac9e56548c18fe17b7b31347 |
| termux-apps | 835e9f5a2ceecbc6276b4e59394ba4810b173e8c50f941ff10c9dfd576ea028b |

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
| drift-detected | needs-review | 12 | 4 | 2 | 0 | 0 | 0 |
