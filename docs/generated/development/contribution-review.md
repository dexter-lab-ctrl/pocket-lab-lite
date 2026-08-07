---
title: "Contribution and review"
description: "Keep changes targeted and main clean."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 32ff658c98f0c55536b08f6952e47ef3b123ec37a95516cd56123197ec0ab64c
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
