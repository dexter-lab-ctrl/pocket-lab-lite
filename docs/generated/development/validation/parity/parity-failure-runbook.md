---
title: "Operational Runbook for Parity Failures"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Operational Runbook for Parity Failures
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## Symptoms

Stale or contradictory recovery status, missing backup history, a verified backup shown as unverified, restore readiness mismatch, or mocked/live divergence.

## Read-only verification

1. Run parity contract and fixture checks.
2. Query Recovery summary/details/history through FastAPI.
3. Inspect prepared-projection freshness and worker/NATS health without mutation.
4. Inspect safe Dexie metadata in browser DevTools; never treat it as authority.
5. Capture sanitized evidence.
6. Refresh projections through established safe backend paths only.

## Recovery

Do not edit SQLite or manifests manually. Restore or repair must use explicit backend-owned flows and existing confirmations.
