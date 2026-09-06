---
title: "Device capabilities"
description: "Canonical Lite capability states, evidence, freshness and degraded behavior."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: e3c315c145ce81cd685f2a30680a32d3183e678e7910115c738f22833683decc
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Device capabilities

| Capability | Verification | Freshness | Expiry | Degraded behavior | Source |
| --- | --- | --- | --- | --- | --- |
| `app_host` | device profile and heartbeat capability advertisement | 60 | stale | app actions remain visible but blocked when delivery is unsafe | `pocket-lab-final-structure/runtime/api_fastapi/services/lite_device_capabilities.py` |
| `media_storage` | device role and sanitized storage summary | 60 | stale | media connection actions are blocked | `pocket-lab-final-structure/runtime/api_fastapi/services/lite_device_capabilities.py` |
| `backup_target` | device role and backup target readiness | 60 | stale | storage backup remains unavailable | `pocket-lab-final-structure/runtime/api_fastapi/services/lite_device_capabilities.py` |
| `security_scanner` | server role and scanner tool posture | 300 | stale | saved Security state remains read-only and new checks are blocked | `pocket-lab-final-structure/runtime/api_fastapi/services/lite_device_capabilities.py` |
| `compute` | device role | 60 | stale | commands remain undeliverable until the agent reconnects | `pocket-lab-final-structure/runtime/api_fastapi/services/lite_device_capabilities.py` |

Canonical states: `verified`, `pending`, `unavailable`, `not_advertised`, `expired`, `stale`.
