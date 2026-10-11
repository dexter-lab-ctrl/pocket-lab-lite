---
title: "Contribution and review"
description: "Keep changes targeted and main clean."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 716da7264607de159cd8b4c7771bd185c20d702b77afbe0495f646e81d07ddef
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
