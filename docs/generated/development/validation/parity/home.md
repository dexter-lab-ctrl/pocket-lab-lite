---
title: "Home Parity Specification"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Home Parity Specification
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## 1. Current status

| Repository | Fixture | Mock browser | Live API | Live UI | Live Termux | Runtime parity | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| verified | partial | verified | unvalidated | unvalidated | unvalidated | unvalidated | partial |

## 2. Repository-backed flow

```text
React/Vite PWA screen: home
→ Caddy same-origin proxy
→ FastAPI: /api/lite/status, /api/lite/release
→ repository authorities: installed-release-identity, lite-status-service, system-health-projection
→ sanitized projection / selector / rendered UI
```

## 3. Backend authorities

| Authority | Kind | Repository location | Writer | Reader | Frontend exposure |
| --- | --- | --- | --- | --- | --- |
| installed-release-identity | release-state | installed release identity | release workflow | release status service | allowlisted sanitized FastAPI projection |
| lite-status-service | service-projection | lite_status service composition | worker/agent telemetry and prepared projections | lite_status.lite_status | allowlisted sanitized FastAPI projection |
| system-health-projection | prepared-projection | system current-state projections | phase3b projection writers | Lite status composition | allowlisted sanitized FastAPI projection |

## 4. FastAPI routes

| Method | Endpoint | Backend sources | Freshness | Degraded behavior | Sanitization |
| --- | --- | --- | --- | --- | --- |
| GET | /api/lite/status | lite-status-service, system-health-projection | status revision and checked_at | safe stale/degraded/unavailable state | allowlist |
| GET | /api/lite/release | installed-release-identity | prepared projection revision | safe stale/degraded/unavailable state | allowlist |

## 5. Frontend selectors and screens

| Selectors/presentation | Query keys | Screens |
| --- | --- | --- |
| buildLiteHomeOverview | liteQueryKeys.status, liteQueryKeys.release | home |

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

- src/lite/LiteHome.stories.jsx

## 8. Mocked-browser scenarios

- tests/e2e/lite-mocked.spec.ts

## 9. Live API observation

Status: **unvalidated**

| Observation | Route adapter | Extractor | Path | API ↔ Termux comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| overall_status | primary | path | overall | exact | high |
| server_identity_expected | primary | presence | device.name | exact | high |
| cpu_percent | primary | path | telemetry.cpu_usage_percent | numeric-tolerance | high |
| memory_usage_mb | primary | path | telemetry.memory_usage_mb | numeric-tolerance | high |
| storage_free_mb | primary | path | telemetry.free_space_mb | numeric-tolerance | high |
| service_count | primary | count | services | exact | high |
| read_degraded | primary | path | read_degraded | exact | high |

## 10. Live UI observation

Status: **unvalidated**. Screen: `home`. Required projects: live-desktop, live-mobile.

Browser capture uses visible semantics, accessible controls, existing stable screen identifiers, bounded text, exact backend-derived identity checks, and privacy redaction.

## 11. Live Termux observation

Status: **unvalidated**. The Termux lane uses the same allowlisted GET adapters through the managed read-only SSH alias and the phone loopback API, or an explicitly configured safe tunnel. It never reads databases, credentials, or environment secrets and never restarts services.

## 12. Field-level semantic comparisons

| Mapping | Boundary | Backend observation | Frontend observation | Comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| home-overall-presentation | live-api-live-ui | overall_status | screen_text | intentional-presentation-map | high |
| home-server-identity | live-api-live-ui | server_identity_expected | server_identity_visible | boolean-equivalence | high |
| home-cpu-format | live-api-live-ui | cpu_percent | home_cpu_note | percentage-format | medium |
| home-sanitized-ui | live-api-live-ui | $ | screen_text | safe-redaction | critical |

## 13. Mapped presentation differences

| Mapping | Comparator | Allowlisted presentation |
| --- | --- | --- |
| home-overall-presentation | intentional-presentation-map | {"degraded": ["review recommended", "need your attention"], "failed": ["needs attention"], "healthy": ["workspace ready", "self hosted workspace is ready"], "unknown": ["checking", "temporarily unavailable"]} |
| home-cpu-format | percentage-format | {"format": "bounded equivalent"} |

Different user-facing wording or formatting is not drift when an allowlisted deterministic mapping proves equivalent meaning.

## 14. Detected drift

| Comparison | Boundary | Severity | Project | Explanation |
| --- | --- | --- | --- | --- |

No promoted semantic drift is recorded for this domain.

## 15. Accepted limitations

- CPU, memory, and storage presentation may be rounded or unit-formatted.

## 16. Unsupported operations

- Home never executes system operations directly.

## 17. Known gaps

- Live runtime semantic evidence remains explicit and release-bound.

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
