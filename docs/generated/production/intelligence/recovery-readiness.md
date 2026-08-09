---
title: "Recovery readiness"
description: "Plain-language recovery readiness from promoted evidence."
generated: true
audience: production
confidence: release-promoted
---

# Recovery readiness

<div class="pl-scorecard-hero"><span>Overall</span><strong>degraded</strong><small>Reason: <code>projection_too_old</code></small></div>

<div class="pl-scorecard-grid">
<div class="pl-scorecard-item"><span>Operational health</span><strong>degraded</strong><small>degraded</small></div>
<div class="pl-scorecard-item"><span>Evidence freshness</span><strong>degraded</strong><small>stale</small></div>
<div class="pl-scorecard-item"><span>Write safety</span><strong>degraded</strong><small>blocked</small></div>
<div class="pl-scorecard-item"><span>Fresh restore preview required</span><strong>degraded</strong><small>True</small></div>
<div class="pl-scorecard-item"><span>Restore currently allowed</span><strong>degraded</strong><small>False</small></div>
<div class="pl-scorecard-item"><span>Projection refresh pending</span><strong>healthy</strong><small>False</small></div>
<div class="pl-scorecard-item"><span>Completed restore evidence</span><strong>healthy</strong><small>13</small></div>
</div>

## What should I do next?

Refresh and explicitly promote runtime evidence before a guarded restore write.
