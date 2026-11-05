---
title: "Validation and Allure-compatible evidence"
description: "Every recorded gate includes command, commit, platform, start/end timestamps, exit code, result, bounded output, and artifact paths."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: a9188e4b2432db9d3279414b81aeec4c68f000a01c80a752fd41bbc678c780f0
schema_revision: 1
validation_status: generated
---

# Validation and Allure-compatible evidence

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Every recorded gate includes command, commit, platform, start/end timestamps, exit code, result, bounded output, and artifact paths.

`task lite:validation:evidence` generates `allure-results/`, a validation manifest, readiness matrix, and test artifact index. `task lite:allure` also creates a bounded local HTML evidence index. The upstream Allure UI is optional and must use an independently provisioned pinned CLI; it is not a server-phone dependency.
