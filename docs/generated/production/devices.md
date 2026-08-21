---
title: "Devices and onboarding"
description: "Device onboarding is backend-owned: invite creation \u2192 audit evidence \u2192 copyable bootstrap command \u2192 identity guard \u2192 safe acceptance \u2192 env write \u2192 node agent/supervisor start \u2192 heartbeats in Devices."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 8b7e457bdeb6cbdf9bf6dc80faa75c6bbcbe4b1a448ea3d2c75c39d81a65f0a0
schema_revision: 1
validation_status: generated
---

# Devices and onboarding

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Device onboarding is backend-owned: invite creation → audit evidence → copyable bootstrap command → identity guard → safe acceptance → env write → node agent/supervisor start → heartbeats in Devices.

Duplicate names and invites are blocked case-insensitively and separator-insensitively. Identity mismatches fail closed. A lost heartbeat changes a durable enrolled device to Offline/Stale; it does not implicitly delete enrollment.
