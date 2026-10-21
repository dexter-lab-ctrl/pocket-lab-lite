---
title: "Validation and Allure-compatible evidence"
description: "Every recorded gate includes command, commit, platform, start/end timestamps, exit code, result, bounded output, and artifact paths."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: dc0c9fab65a82aa57a1321aac30b15e8de230784e591c894c37a45c5e15c3631
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
