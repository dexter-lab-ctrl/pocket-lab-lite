---
title: "PhotoPrism"
description: "Provides the verified managed photo application under a same-origin Caddy path."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# PhotoPrism

Provides the verified managed photo application under a same-origin Caddy path.

## Why it exists

Provides the verified managed photo application under a same-origin Caddy path.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:photoprism` |
| Owner | Managed application |
| Execution owner | pocketlab-app-photoprism |
| Data owner | PhotoPrism application data |
| Recovery owner | App lifecycle worker |
| Runtime owner | PM2 / PROot Ubuntu |
| Runtime process | pocketlab-app-photoprism |
| Runtime platform | PROot Ubuntu on server host |
| Security boundary | application-container |
| Confidence | verified |

## Responsibilities

- Provides the verified managed photo application under a same-origin Caddy path.

## Inputs

- Same-origin app route
- approved media mapping

## Outputs

- PhotoPrism UI and health

## Health signals

- base-path status probe

## Failure modes

- route 404
- process stopped

## Recovery behavior

- route-aware repair
- process recovery

## Supported platforms

- Android/Termux
- ARM64

## Depends on / uses

- protected_by: `Application-container boundary`
- protected_by: `Application-container boundary`
- recovers_with: `PhotoPrism unavailable`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_app_catalog_runtime_truth.py`
- verified_by: `tests/backend/test_lite_control_plane_sqlite_p3.py`
- verified_by: `tests/backend/test_lite_device_health_d4.py`
- verified_by: `tests/backend/test_lite_e1_e3_e4_transactional_prepared_scheduler.py`
- verified_by: `tests/backend/test_lite_phase3a_apps_recovery_semantic_revisions.py`
- verified_by: `tests/backend/test_lite_security_s7_saved_state_history.py`
- verified_by: `tests/backend/test_lite_sqlite_performance.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_intelligence.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`
- verified_by: `tests/parity/test_planned_runtime_parity_policy.py`
- verified_by: `tests/parity/test_runtime_drift_reporting.py`

## Used by / backlinks

- depends_on: `Caddy same-origin proxy`
- depends_on: `Media readiness and app health probes`
- depends_on: `PROot Ubuntu application container`
- uses: `App installation`
- uses: `PhotoPrism operation`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/photoprism.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/install-photoprism-proot.sh`
