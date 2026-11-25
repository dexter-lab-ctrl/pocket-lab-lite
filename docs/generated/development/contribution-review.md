---
title: "Contribution and review"
description: "Keep changes targeted and main clean."
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

# Contribution and review

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Keep changes targeted and main clean.

Before review: run quick/full gates as appropriate, generated contract/docs drift checks, `git diff --check`, and generated-artifact cleanup. Do not commit `.orig`, `.rej`, `.pytest_cache`, raw HAR, accidental `dist`, Storybook static output, Allure output, state databases, or secrets.
