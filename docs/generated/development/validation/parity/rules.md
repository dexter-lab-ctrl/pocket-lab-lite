---
title: "Rules Parity Specification"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 0b555a4643cccbb5d48b5dd4e1492fc4487803cb12ab52681cdbd77e6e2bac27
generator: scripts/docs/parity/generate_parity.py
---

# Rules Parity Specification
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## 1. Current status

| Repository | Fixture | Mock browser | Live API | Live UI | Live Termux | Runtime parity | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| verified | partial | verified | observed | observed | observed | partial | partial |

## 2. Repository-backed flow

```text
React/Vite PWA screen: rules
→ Caddy same-origin proxy
→ FastAPI: /api/lite/policy
→ repository authorities: workflow-current-state
→ sanitized projection / selector / rendered UI
```

## 3. Backend authorities

| Authority | Kind | Repository location | Writer | Reader | Frontend exposure |
| --- | --- | --- | --- | --- | --- |
| workflow-current-state | policy-state | OPA/policy advisory state | policy backend service | lite policy service | allowlisted sanitized FastAPI projection |

## 4. FastAPI routes

| Method | Endpoint | Backend sources | Freshness | Degraded behavior | Sanitization |
| --- | --- | --- | --- | --- | --- |
| GET | /api/lite/policy | workflow-current-state | prepared projection revision | safe stale/degraded/unavailable state | allowlist |

## 5. Frontend selectors and screens

| Selectors/presentation | Query keys | Screens |
| --- | --- | --- |
| direct-render | liteQueryKeys.resource(/api/lite/policy) | rules |

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

- src/lite/LiteRules.stories.jsx

## 8. Mocked-browser scenarios

- tests/e2e/lite-mocked.spec.ts

## 9. Live API observation

Status: **observed**

| Observation | Route adapter | Extractor | Path | API ↔ Termux comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| status | primary | path | status | exact | high |
| engine_healthy | primary | path | engine.healthy | exact | critical |
| summary | primary | path | summary | exact | high |
| protection_enabled | primary | path | protection_enabled | exact | high |
| requires_confirmation | primary | path | requires_confirmation | exact | high |
| allowed_action_count | primary | count | allowed_actions | exact | high |

## 10. Live UI observation

Status: **observed**. Screen: `rules`. Required projects: live-desktop, live-mobile.

Browser capture uses visible semantics, accessible controls, existing stable screen identifiers, bounded text, exact backend-derived identity checks, and privacy redaction.

## 11. Live Termux observation

Status: **observed**. The Termux lane uses the same allowlisted GET adapters through the managed read-only SSH alias and the phone loopback API, or an explicitly configured safe tunnel. It never reads databases, credentials, or environment secrets and never restarts services.

## 12. Field-level semantic comparisons

| Mapping | Boundary | Backend observation | Frontend observation | Comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| rules-status-presentation | live-api-live-ui | status | screen_text | intentional-presentation-map | critical |
| rules-engine-health-presentation | live-api-live-ui | engine_healthy | screen_text | intentional-presentation-map | critical |
| rules-summary | live-api-live-ui | summary | screen_text | text-contains | medium |
| rules-sanitized-ui | live-api-live-ui | $ | screen_text | safe-redaction | critical |

## 13. Mapped presentation differences

| Mapping | Comparator | Allowlisted presentation |
| --- | --- | --- |
| rules-status-presentation | intentional-presentation-map | {"degraded": ["Protected changes paused", "Changes blocked"], "failed": ["Protected changes paused", "Changes blocked"], "ready": ["Rules ready", "Safety Rules are active for protected changes", "Fail-closed ready"], "unavailable": ["Protected changes paused", "Changes blocked"], "unknown": ["Protected changes paused", "Changes blocked"]} |
| rules-engine-health-presentation | intentional-presentation-map | {"false": ["Protected changes paused", "Changes blocked"], "true": ["Rules ready", "Safety Rules are active for protected changes", "Fail-closed ready"]} |

Different user-facing wording or formatting is not drift when an allowlisted deterministic mapping proves equivalent meaning.

## 14. Detected drift

| Comparison | Boundary | Severity | Project | Explanation |
| --- | --- | --- | --- | --- |

No promoted semantic drift is recorded for this domain.

## 15. Accepted limitations

- The current product contract is a protection-mode policy surface, not a general arbitrary rule engine.

## 16. Unsupported operations

- Planned trigger/condition/action automation is not marked verified.

## 17. Known gaps

- Per-rule identity and execution history are planned, not present in the current API.

## 18. Evidence hashes

| Evidence | SHA-256 / semantic fingerprint |
| --- | --- |
| backend-rules | e0a1d3f18c690bb04ce5f037c5852c8080f72f08404bb0ee2604549b98a70da9 |
| browser-rules-live-desktop | 11c6bac98ce3184af7b903dddb8749f2e3bac25faf540f1af428cc3e5b155af2 |
| browser-rules-live-mobile | a3b029f192002ac8dcdec9e270e746257bc43b40098449cdd7ecde71832e60f2 |
| observation-backend | 98c0b2e070d96d05f1f86fcf24a77f4b53d45561f6af6b89adc512d9ef50398e |
| observation-live_desktop | 4a86f224a424dadc54163630acae433452e59517ff4d46692e2398a34128ce17 |
| observation-live_mobile | 4a86f224a424dadc54163630acae433452e59517ff4d46692e2398a34128ce17 |
| observation-termux | 98c0b2e070d96d05f1f86fcf24a77f4b53d45561f6af6b89adc512d9ef50398e |
| playwright-report | 2327e3f46af50c663807512084239fcbb26650df0147e09767f07dfb1a685e53 |
| runtime-comparison | 405b5ac408de70bf3055afffd62c5dcd5475c107ac9e56548c18fe17b7b31347 |
| termux-rules | 056a31376585cdb1bb096ae214915a1679ac92383c0e4924ee912b7a51ae5d31 |

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
| partial | partial | 12 | 2 | 0 | 0 | 0 | 0 |
