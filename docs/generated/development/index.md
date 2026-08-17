---
title: "Development documentation"
description: "Everything in this section is generated for Ubuntu/WSL2 maintainers. Development tooling is not a production dependency and is not included in `dist.zip`."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 65a74e4abf0c0da3178307346cab000076511caf826cf3cad30fa9634abf0faa
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
