---
title: "Data Freshness and Staleness Policy"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 8a90a66c46a250cebfd7e62993f9c541fa1c293fd7e4dd880cc399353b42bff4
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
