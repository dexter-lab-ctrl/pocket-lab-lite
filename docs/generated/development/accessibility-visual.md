---
title: "Accessibility, visual, and performance gates"
description: "Desktop browser evidence is useful but does not prove Android production performance."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 29e9c74dfdc556deb069f31fdfab7a21589f67ad7d6ceade6a332b18ad1e25c3
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
