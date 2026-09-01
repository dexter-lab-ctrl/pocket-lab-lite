---
title: "Validation and Allure-compatible evidence"
description: "Every recorded gate includes command, commit, platform, start/end timestamps, exit code, result, bounded output, and artifact paths."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 4a1f2cf64180dfd6a19c437f4770e4192db9cf7eb5347417c9f7a401837e2b8f
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
