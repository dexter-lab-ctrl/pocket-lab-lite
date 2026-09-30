---
title: "Contribution and review"
description: "Keep changes targeted and main clean."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 7fbc5b3d92e26b875c893ec2bc79ddf1c149e4689a023a1b21c71ad46b55c12a
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
