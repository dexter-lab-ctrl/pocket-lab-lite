---
title: "Security profiles"
description: "Canonical Quick, Full and App Check scope, tools, exclusions, ownership and stale behavior."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: 54cdffab5aadcb8ce9c1640b776b703d6472e810cdd991c54dadef893f7bcfe5
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Security profiles

| Profile | Default | Tools | Targets checked | Targets skipped | Freshness | Unsupported behavior |
| --- | --- | --- | --- | --- | --- | --- |
| `quick` — Quick Safety Check | yes | Lynis, Trivy | Termux host posture, Pocket Lab Lite source/runtime metadata, safe configuration posture | photos and media, backup payloads, scanner caches, PROot rootfs, generated runtime history | 180 | not applicable |
| `full` — Full Local Check | no | Lynis, Trivy | Termux host, Pocket Lab Lite, runtime config, selected PROot Ubuntu areas, PhotoPrism app/config/runtime, backup metadata | photos and media, Android shared storage, backup payloads, restore checkpoints, logs and caches | 900 | not applicable |
| `app` — App Check | no | Trivy, route/config posture checks | PhotoPrism route, app files, settings, backup metadata, action state | photos and media, PhotoPrism originals/import/cache/sidecars/index database | 300 | safe 404 with no scanner execution |

## Main summary semantics

- **main summary:** latest completed Security posture with active-progress overlay where present
- **saved state:** read-only safe snapshot explicitly marked saved/stale
- **partial degraded:** coverage gaps and scanner availability remain explicit
- **source:** security compact summary and canonical SQLite run state
