---
title: "Development documentation"
description: "Everything in this section is generated for Ubuntu/WSL2 maintainers. Development tooling is not a production dependency and is not included in `dist.zip`."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 1d1a1908e4d75d1473d9677cb188e48aef3bc35f8ff1542299d105e58877586f
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
