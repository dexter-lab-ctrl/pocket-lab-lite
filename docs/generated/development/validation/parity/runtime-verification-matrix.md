---
title: "Runtime Verification Matrix"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 0b555a4643cccbb5d48b5dd4e1492fc4487803cb12ab52681cdbd77e6e2bac27
generator: scripts/docs/parity/generate_parity.py
---

# Runtime Verification Matrix
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Promoted runtime baseline: **needs-review**; release: **lite-2026.08.12.2**. Promotion is explicit, sanitized, hash-bound, and ordinary generation never reads live captures.

| Domain | Repository | Fixture | Mock browser | Live API | Live UI | Live Termux | Semantic parity | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Home | verified | partial | verified | observed | observed | observed | verified-with-mapped-presentation | verified |
| Apps | verified | partial | verified | observed | observed | observed | drift-detected | needs-review |
| Devices | verified | partial | verified | observed | observed | observed | verified-with-mapped-presentation | verified |
| Security | verified | partial | verified | observed | observed | observed | verified-with-mapped-presentation | verified |
| Identity | verified | partial | verified | observed | observed | observed | partial | partial |
| Rules | verified | partial | verified | observed | observed | observed | partial | partial |
| Backup & Restore | verified | verified | verified | observed | observed | observed | drift-detected | needs-review |
