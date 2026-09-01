---
title: "Accessibility, visual, and performance gates"
description: "Desktop browser evidence is useful but does not prove Android production performance."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: ae40f6fa0fb418913108c52f1c221f9f65fbf45bbd848604e6c14b20ebaf6585
schema_revision: 1
validation_status: generated
---

# Accessibility, visual, and performance gates

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Desktop browser evidence is useful but does not prove Android production performance.

Playwright checks serious/critical Axe findings, reduced motion, mobile/desktop rendering, console/API failures, and canonical screenshots. Existing Lighthouse and bundle-budget helpers remain Development-PC gates. Visual baselines must be reviewed before update.
