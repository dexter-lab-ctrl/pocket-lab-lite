---
title: "Live Termux Verification Guide"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Live Termux Verification Guide
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

```text
VS Code WSL2
→ managed hardened SSH alias
→ one bounded read-only verifier
→ sanitized backend projection
→ live FastAPI query
→ optional Playwright observation
→ normalized evidence
```

The verifier never copies a database, prints raw rows, reads credentials, writes to the phone, or restarts services. Missing SSH configuration reports **runtime-unavailable**, not PASS.
