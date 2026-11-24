---
title: "CI workflow to task mapping"
description: "CI uses the Lite task surface rather than reintroducing full-product workflows."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 412f31ab2d7232d94e8e1c885b19c4b1bd4f6a75ef4524c47ff5b65507754e26
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
