---
title: "Accessibility, visual, and performance gates"
description: "Desktop browser evidence is useful but does not prove Android production performance."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 47787a753658e4830e2595239c14e0e182f7a2b0c26dc2f5c7625d69910ece21
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
