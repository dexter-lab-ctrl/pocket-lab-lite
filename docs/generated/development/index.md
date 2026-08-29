---
title: "Development documentation"
description: "Everything in this section is generated for Ubuntu/WSL2 maintainers. Development tooling is not a production dependency and is not included in `dist.zip`."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 469ea6d43377d3911f1d69c40ef4718b8c1dc749316dc9bd0ad006cff217e80b
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
