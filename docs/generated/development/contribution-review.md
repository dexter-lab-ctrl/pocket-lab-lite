---
title: "Contribution and review"
description: "Keep changes targeted and main clean."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: e17dbd717d6e4459d1f614acc1786781126fc4fb64d5a0d27ac785bfaf061d49
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
