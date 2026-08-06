---
title: "Devices Parity Specification"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Devices Parity Specification
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## 1. Current status

| Repository | Fixture | Mock browser | Live API | Live UI | Live Termux | Runtime parity | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| verified | partial | verified | unvalidated | unvalidated | unvalidated | unvalidated | partial |

## 2. Repository-backed flow

```text
React/Vite PWA screen: devices
→ Caddy same-origin proxy
→ FastAPI: /api/lite/fleet
→ repository authorities: device-current-state, device-heartbeats, device-supervisor-state
→ sanitized projection / selector / rendered UI
```

## 3. Backend authorities

| Authority | Kind | Repository location | Writer | Reader | Frontend exposure |
| --- | --- | --- | --- | --- | --- |
| device-current-state | sqlite-and-projection | durable device registry and prepared fleet projection | fleet services and reconciliation | lite fleet service | allowlisted sanitized FastAPI projection |
| device-heartbeats | event-projection | sanitized heartbeat projection | node agents | fleet projection reader | allowlisted sanitized FastAPI projection |
| device-supervisor-state | event-projection | sanitized supervisor evidence | agent supervisors | fleet projection reader | allowlisted sanitized FastAPI projection |

## 4. FastAPI routes

| Method | Endpoint | Backend sources | Freshness | Degraded behavior | Sanitization |
| --- | --- | --- | --- | --- | --- |
| GET | /api/lite/fleet | device-current-state, device-heartbeats, device-supervisor-state | heartbeat and projection revision | saved state marked stale | allowlist |

## 5. Frontend selectors and screens

| Selectors/presentation | Query keys | Screens |
| --- | --- | --- |
| selectDevicesScreenView, selectLiteDeviceCard, selectRemoteAccessHealthView | liteQueryKeys.fleet, liteQueryKeys.fleetHealthSummary | devices |

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

- src/lite/LiteDevices.stories.jsx

## 8. Mocked-browser scenarios

- tests/e2e/lite-mocked.spec.ts

## 9. Live API observation

Status: **unvalidated**

| Observation | Route adapter | Extractor | Path | API ↔ Termux comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| device_count | primary | count | devices | exact | high |
| server_identity_expected | primary | any | devices | exact | high |
| server_status | primary | find | status | exact | high |
| online_count | primary | count_where | devices | exact | high |
| remote_access_ready | primary | path | remote_access.ready | exact | high |
| remote_access_status | primary | path | remote_access.status | exact | high |
| tailscale_ip_present | primary | presence | remote_access.ip | exact | high |

## 10. Live UI observation

Status: **unvalidated**. Screen: `devices`. Required projects: live-desktop, live-mobile.

Browser capture uses visible semantics, accessible controls, existing stable screen identifiers, bounded text, exact backend-derived identity checks, and privacy redaction.

## 11. Live Termux observation

Status: **unvalidated**. The Termux lane uses the same allowlisted GET adapters through the managed read-only SSH alias and the phone loopback API, or an explicitly configured safe tunnel. It never reads databases, credentials, or environment secrets and never restarts services.

## 12. Field-level semantic comparisons

| Mapping | Boundary | Backend observation | Frontend observation | Comparator | Severity |
| --- | --- | --- | --- | --- | --- |
| devices-server-identity | live-api-live-ui | server_identity_expected | server_identity_visible | boolean-equivalence | critical |
| devices-server-state | live-api-live-ui | server_status | screen_text | state-machine-map | critical |
| devices-remote-access | live-api-live-ui | remote_access_ready | screen_text | intentional-presentation-map | high |
| devices-tailscale-exposure | live-api-live-ui | tailscale_ip_present | tailscale_ip_visible | boolean-equivalence | medium |
| devices-sanitized-ui | live-api-live-ui | $ | screen_text | safe-redaction | critical |

## 13. Mapped presentation differences

| Mapping | Comparator | Allowlisted presentation |
| --- | --- | --- |
| devices-server-state | state-machine-map | {"agent_stopped": ["Agent stopped"], "joining": ["Joining"], "offline": ["Offline"], "online": ["Online"], "repairing": ["Repairing"], "waiting": ["Waiting"]} |
| devices-remote-access | intentional-presentation-map | {"false": ["Remote access not ready"], "true": ["Remote access ready"]} |

Different user-facing wording or formatting is not drift when an allowlisted deterministic mapping proves equivalent meaning.

## 14. Detected drift

| Comparison | Boundary | Severity | Project | Explanation |
| --- | --- | --- | --- | --- |

No promoted semantic drift is recorded for this domain.

## 15. Accepted limitations

- Heartbeat freshness can move during capture; comparison records the observed revision.

## 16. Unsupported operations

- Healthy online devices are not removed without explicit confirmation.

## 17. Known gaps

- Per-device profile fields remain partial when the agent has not published them.

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
