---
title: "Incident runbooks"
description: "Runbooks are user guidance, not browser shell execution."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 688ce225848d1f3f338dd3e81e5d1fb07fca3306034af8f3bfc9463a48595722
schema_revision: 1
validation_status: generated
---

# Incident runbooks

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Runbooks are user guidance, not browser shell execution.

- NATS unavailable: verify listener, Tailnet reachability, credentials/config posture, and reconnect evidence.
- Worker consumer stalled: verify durable consumer health and watchdog recovery before restart.
- Agent stopped: verify supervisor, then use explicit recovery.
- Projection stale: preserve last valid state, rebuild prepared projection, and validate revision parity.
- Release verification failed: keep last-known-good PWA and investigate manifest/checksum/health.
