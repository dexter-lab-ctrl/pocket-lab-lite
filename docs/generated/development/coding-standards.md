---
title: "Coding and architecture standards"
description: "Changes must preserve Android/Termux, ARM64, low-power, same-origin, and backend-owned execution boundaries."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: fefe0c5cceac58a0729f043356fd8b6d9e3a38a21372e4c8853fcf608d3c4e11
schema_revision: 1
validation_status: generated
---

# Coding and architecture standards

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Changes must preserve Android/Termux, ARM64, low-power, same-origin, and backend-owned execution boundaries.

- Frontend code never executes shell commands or connects directly to NATS.
- FastAPI remains the control API; workers, agents, and supervisors own execution and recovery.
- Safe read caches never store secrets, raw logs, invite tokens, bootstrap secrets, or write responses.
- Generated files must be deterministic, bounded, sanitized, and source-fingerprinted.
- Identity and Rules behavior is not claimed beyond verified source contracts.
