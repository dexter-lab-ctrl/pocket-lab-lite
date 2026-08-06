---
title: "Runtime Verification Matrix"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Runtime Verification Matrix
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Promoted runtime baseline: **verified coverage-only (semantic parity unvalidated)**; release: **lite-2026.08.05.2**. Promotion is explicit, sanitized, hash-bound, and ordinary generation never reads live captures.

| Domain | Repository | Fixture | Mock browser | Live API | Live UI | Live Termux | Semantic parity | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Home | verified | partial | verified | unvalidated | unvalidated | unvalidated | unvalidated | partial |
| Apps | verified | partial | verified | unvalidated | unvalidated | unvalidated | unvalidated | partial |
| Devices | verified | partial | verified | unvalidated | unvalidated | unvalidated | unvalidated | partial |
| Security | verified | partial | verified | unvalidated | unvalidated | unvalidated | unvalidated | partial |
| Identity | verified | partial | verified | unvalidated | unvalidated | unvalidated | unvalidated | partial |
| Rules | verified | partial | verified | unvalidated | unvalidated | unvalidated | unvalidated | partial |
| Backup & Restore | verified | verified | verified | verified | verified | verified | unvalidated | ready-with-accepted-limitations |
