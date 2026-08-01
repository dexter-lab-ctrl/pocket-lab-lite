---
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 8937f6e2e2ba4f68e0af975279bf8bf383342aff03d7c9c0e4a5c4a564aea291
schema_revision: 1
validation_status: generated
---

# Devices and onboarding

Device onboarding is backend-owned: invite creation → audit evidence → copyable bootstrap command → identity guard → safe acceptance → env write → node agent/supervisor start → heartbeats in Devices.

Duplicate names and invites are blocked case-insensitively and separator-insensitively. Identity mismatches fail closed. A lost heartbeat changes a durable enrolled device to Offline/Stale; it does not implicitly delete enrollment.
