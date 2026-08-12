---
title: "Frontend state ownership"
description: "Combines service worker, TanStack Query, Dexie safe snapshots, Zustand UI-only state, XState guided flows, API client, error boundaries, and generated fixtures without owning backend truth."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Frontend state ownership

Combines service worker, TanStack Query, Dexie safe snapshots, Zustand UI-only state, XState guided flows, API client, error boundaries, and generated fixtures without owning backend truth.

## Why it exists

Combines service worker, TanStack Query, Dexie safe snapshots, Zustand UI-only state, XState guided flows, API client, error boundaries, and generated fixtures without owning backend truth.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:frontend-state` |
| Owner | Lite UI |
| Execution owner | React |
| Data owner | FastAPI; Dexie is safe read-only fallback |
| Recovery owner | TanStack revalidation and UI workflows |
| Runtime owner | Browser |
| Runtime process | React |
| Runtime platform | Browser / installed PWA |
| Security boundary | browser |
| Confidence | verified |

## Responsibilities

- Combines service worker, TanStack Query, Dexie safe snapshots, Zustand UI-only state, XState guided flows, API client, error boundaries, and generated fixtures without owning backend truth.

## Inputs

- Safe GET responses
- saved snapshots

## Outputs

- Rendered view models
- write requests

## Health signals

- query freshness
- saved-state metadata

## Failure modes

- offline
- stale snapshot

## Recovery behavior

- refetch on reconnect
- write actions stay disabled

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `Frontend state libraries have distinct ownership`
- protected_by: `Browser trust boundary`
- protected_by: `Browser trust boundary`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_control_plane_sqlite_p3.py`
- verified_by: `tests/backend/test_lite_device_health_d4.py`
- verified_by: `tests/backend/test_lite_devices_d2_d3.py`
- verified_by: `tests/backend/test_lite_e1_e3_e4_transactional_prepared_scheduler.py`
- verified_by: `tests/backend/test_lite_fastapi_runtime_diagnostics.py`
- verified_by: `tests/backend/test_lite_phase3b_security_system_probe_revisions.py`
- verified_by: `tests/backend/test_lite_phase3c_system_aggregates.py`
- verified_by: `tests/backend/test_lite_phase4_phase5_adaptive_runtime.py`
- verified_by: `tests/backend/test_lite_premium_tab_polish.py`
- verified_by: `tests/backend/test_lite_revision_sync_n4_n5.py`
- verified_by: `tests/backend/test_lite_security_f11_events_contract.py`
- verified_by: `tests/backend/test_lite_security_f12_f14_stability_contract.py`
- verified_by: `tests/backend/test_lite_security_f3_summary_contract.py`
- verified_by: `tests/backend/test_lite_security_f9_etag_contract.py`
- verified_by: `tests/backend/test_lite_security_s7_saved_state_history.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Prepared read, health, readiness, diagnostics, and evidence APIs`
- depends_on: `React / Vite PWA`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/frontend-state.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `src/hooks/useLiteQuery.js`
- `src/lib/liteSafeSnapshots.js`
- `src/machines/liteSecurityCheckMachine.js`
- `src/stores/liteUiStore.js`
