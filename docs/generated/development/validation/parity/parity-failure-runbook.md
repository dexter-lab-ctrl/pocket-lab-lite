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

Stale or contradictory recovery status, missing backup history, a verified backup shown as unverified, restore readiness mismatch, mocked/live divergence, undocumented `400`/`404`/`503`, property-test timeout, or a bootstrap identity crash.

## Read-only verification

1. Verify the SSH loopback tunnel or local API without exposing the phone directly.
2. Compile the focused schema and inspect its selection manifest; it must contain only Recovery GET operations and no maintenance path.
3. Run parity contract and fixture checks.
4. Query Recovery summary/details/history through FastAPI.
5. Inspect prepared-projection freshness and worker/NATS health without mutation.
6. Capture bounded cold/warm latency evidence for slow reads.
7. Inspect safe Dexie metadata in browser DevTools; never treat it as authority.
8. Capture sanitized evidence and categorized Schemathesis summaries.

## Recovery

Do not edit SQLite or manifests manually. Invalid bootstrap identities fail closed before token creation or durable writes. Restore or repair must use explicit backend-owned flows and existing confirmations. Baselines are promoted only after explicit review evidence.
