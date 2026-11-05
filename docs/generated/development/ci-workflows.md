---
title: "CI workflow to task mapping"
description: "CI uses the Lite task surface rather than reintroducing full-product workflows."
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

# CI workflow to task mapping

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

CI uses the Lite task surface rather than reintroducing full-product workflows.

- `lite-quality.yml: task lite:check:quick`
- `lite-quality.yml: task lite:docs:check`
- `lite-quality.yml: task lite:docs:generate`
- `lite-quality.yml: task lite:evidence:parity:check`
- `lite-quality.yml: task lite:evidence:parity:generate`
- `lite-quality.yml: task lite:parity:api`
- `lite-quality.yml: task lite:parity:backend`
- `lite-quality.yml: task lite:parity:contracts:check`
- `lite-quality.yml: task lite:parity:selectors`
- `lite-quality.yml: task lite:photo-backup:candidate:full`
- `lite-quality.yml: task lite:test:docs`
- `lite-quality.yml: task lite:test:storybook`
