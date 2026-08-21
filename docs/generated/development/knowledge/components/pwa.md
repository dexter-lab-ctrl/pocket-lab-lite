---
title: "React / Vite PWA"
description: "Renders Lite screens and sends same-origin requests only to FastAPI through Caddy."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# React / Vite PWA

Renders Lite screens and sends same-origin requests only to FastAPI through Caddy.

## Why it exists

Renders Lite screens and sends same-origin requests only to FastAPI through Caddy.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:pwa` |
| Owner | Lite UI |
| Execution owner | React |
| Data owner | FastAPI source of truth |
| Recovery owner | Error boundaries and browser reload |
| Runtime owner | Browser |
| Runtime process | React |
| Runtime platform | Browser / installed PWA |
| Security boundary | browser |
| Confidence | verified |

## Responsibilities

- Renders Lite screens and sends same-origin requests only to FastAPI through Caddy.

## Inputs

- Prepared API responses

## Outputs

- Validated user requests

## Health signals

- error boundary
- frontend lifecycle challenge

## Failure modes

- backend unavailable
- saved state stale

## Recovery behavior

- read-only saved state
- quiet revalidation

## Evidence

- frontend lifecycle diagnostics

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- affected_by: `FastAPI owns the browser-facing control API`
- affected_by: `Frontend state libraries have distinct ownership`
- depends_on: `Caddy same-origin proxy`
- depends_on: `Frontend state ownership`
- protected_by: `Browser trust boundary`
- protected_by: `Browser trust boundary`
- recovers_with: `Caddy unavailable`
- recovers_with: `Pocket Lab UI unavailable`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_control_plane_sqlite_p3.py`
- verified_by: `tests/backend/test_lite_device_system_profile.py`
- verified_by: `tests/backend/test_lite_devices_d2_d3.py`
- verified_by: `tests/backend/test_lite_e1_e3_e4_transactional_prepared_scheduler.py`
- verified_by: `tests/backend/test_lite_fastapi_runtime_diagnostics.py`
- verified_by: `tests/backend/test_lite_identity_passkeys_rules_p1.py`
- verified_by: `tests/backend/test_lite_identity_rules_authorization.py`
- verified_by: `tests/backend/test_lite_phase3b_security_system_probe_revisions.py`
- verified_by: `tests/backend/test_lite_phase3c_system_aggregates.py`
- verified_by: `tests/backend/test_lite_phase4_phase5_adaptive_runtime.py`
- verified_by: `tests/backend/test_lite_premium_tab_polish.py`
- verified_by: `tests/backend/test_lite_security_f11_events_contract.py`
- verified_by: `tests/backend/test_lite_security_f3_summary_contract.py`
- verified_by: `tests/backend/test_lite_security_f7_split_read_contract.py`
- verified_by: `tests/backend/test_lite_security_f9_etag_contract.py`
- verified_by: `tests/backend/test_lite_security_s8_recovery.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/backend/test_lite_workload_admission.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `App Catalog`
- depends_on: `Browser`
- uses: `Backend-to-Frontend parity capture and verification`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/pwa.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `src/lib/liteApi.js`
- `src/lite/LiteApp.jsx`
