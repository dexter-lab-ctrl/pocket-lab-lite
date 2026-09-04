---
title: "Prepared projection catalog"
description: "Canonical sources, prepared storage, freshness, invalidation, pressure and cache ownership."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: 7a04d48cbced7352987872cd788f4c0e50dbf1f45c1189eabf8880382a490ed5
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Prepared projection catalog

| Domain | Canonical source | Storage | Reader | Frontend | Fresh/stale | Degraded behavior | Diagnostics |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `fleet` | durable enrollment plus live heartbeat/runtime truth | device_current_state / enrolled_devices | `GET /api/lite/fleet` | `src/lite/LiteDevices.jsx` | 30/90s | preserve enrolled devices and show Offline/Stale | projection_refresh_state and fleet diagnostics |
| `recovery` | backup manifests, restore plans, checkpoints, and worker lifecycle | recovery_current_state / recovery_operations | `GET /api/lite/recovery/summary` | `src/lite/LiteRecovery.jsx` | 60/300s | show last valid summary with stale reason | recovery projection freshness and action progress |
| `security` | security_scan_runs and sanitized compact state | security_scan_runs and compact security files | `GET /api/lite/security/summary` | `src/lite/LiteSecurity.jsx` | 180/900s | show latest completed or saved partial state truthfully | freshness, progress, durable consumer health |
| `apps.catalog` | catalog definitions plus live route/runtime resolver | app_catalog_current | `GET /api/lite/catalog` | `src/lite/LiteCatalog.jsx` | 60/180s | show last valid catalog and disable unsafe actions | apps.catalog projection state |
| `apps.lifecycle` | app runtime resolver and worker lifecycle | app_lifecycle_current | `GET /api/lite/apps/{app_id}/lifecycle` | `src/lite/LiteCatalog.jsx` | 30/120s | retain last canonical state and mark stale | apps.lifecycle projection state |
| `apps.actions` | normalized action readiness and action lifecycle | app_action_current / app_action_lifecycle | `GET /api/lite/apps/{app_id}/actions` | `src/lite/LiteCatalog.jsx` | 15/90s | disable delivery-dependent actions | apps.actions projection state |
| `home` | prepared summaries from system, fleet, apps, security, recovery, and release | phase3b_current_state and domain revisions | `GET /api/lite/status` | `src/lite/LiteHome.jsx` | 60/180s | show last valid summary and review guidance | system current-state projection diagnostics |

![Prepared projection flow](../../assets/diagrams/projection-flow.light.svg#only-light)
![Prepared projection flow](../../assets/diagrams/projection-flow.dark.svg#only-dark)
