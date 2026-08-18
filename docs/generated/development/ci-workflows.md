---
title: "CI workflow to task mapping"
description: "CI uses the Lite task surface rather than reintroducing full-product workflows."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 9a3315bec7d9d8bab7eca1653eedcac05ea544ed0bb81a797678b6fd8ee790b8
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
- `lite-quality.yml: task lite:test:docs`
- `lite-quality.yml: task lite:test:storybook`
