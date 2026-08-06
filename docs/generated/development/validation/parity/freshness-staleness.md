---
title: "Data Freshness and Staleness Policy"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Data Freshness and Staleness Policy
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Projection | Fresh | Stale | Last-good | Offline | UI label | Status |
| --- | --- | --- | --- | --- | --- | --- |
| recovery-summary | 30 | 300 | True | True | Showing saved state | verified |
| recovery-details | 45 | 300 | True | True | Saved recovery details | verified |
| recovery-backup-history | 60 | 900 | True | True | Saved first page only | verified |

Freshness conflicts fail the relevant boundary; saved state must never be presented as live.
