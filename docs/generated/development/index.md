---
title: "Development documentation"
description: "Everything in this section is generated for Ubuntu/WSL2 maintainers. Development tooling is not a production dependency and is not included in `dist.zip`."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 4a1f2cf64180dfd6a19c437f4770e4192db9cf7eb5347417c9f7a401837e2b8f
schema_revision: 1
validation_status: generated
---

# Development documentation

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Everything in this section is generated for Ubuntu/WSL2 maintainers. Development tooling is not a production dependency and is not included in `dist.zip`.

## Fast path

```bash
task lite:setup:check
task lite:check:quick
task lite:docs:check
```

The verified WSL2 browser is selected through `task lite:playwright:preflight`; no machine-specific path is committed.
