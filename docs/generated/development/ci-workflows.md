---
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 8937f6e2e2ba4f68e0af975279bf8bf383342aff03d7c9c0e4a5c4a564aea291
schema_revision: 1
validation_status: generated
---

# CI workflow to task mapping

CI uses the Lite task surface rather than reintroducing full-product workflows.

- `lite-quality.yml: task lite:check:quick`
- `lite-quality.yml: task lite:docs:check`
- `lite-quality.yml: task lite:docs:generate`
- `lite-quality.yml: task lite:test:storybook`
