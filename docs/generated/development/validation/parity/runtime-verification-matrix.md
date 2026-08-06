---
title: "Runtime Verification Matrix"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Runtime Verification Matrix
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Promoted runtime baseline: **verified**; release: **lite-2026.08.05.2**. Promotion is explicit, sanitized, hash-bound, and ordinary generation never reads live captures.

| Domain | Source | Fixture | Mock browser | Live API | Live Termux | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Backup & Restore | verified | verified | verified | verified | verified | verified |
| Devices | verified | verified | verified | unvalidated | runtime-source-verified | partial |
| Apps | verified | verified | verified | unvalidated | runtime-source-verified | partial |
| Security | verified | verified | verified | unvalidated | runtime-source-verified | partial |
| Rules | partial | partial | partial | unvalidated | unvalidated | planned |
| Releases | verified | verified | partial | unvalidated | runtime-source-verified | partial |
