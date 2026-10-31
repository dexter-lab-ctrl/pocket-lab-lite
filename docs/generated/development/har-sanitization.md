---
title: "HAR capture and sanitization"
description: "Raw HAR files are transient and ignored. Only sanitized HAR output may be retained as evidence."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: e016738d17a8886f9e0dc1c1b718e9fdae1c59c7af09d5b2b9d21151c7135cf0
schema_revision: 1
validation_status: generated
---

# HAR capture and sanitization

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Raw HAR files are transient and ignored. Only sanitized HAR output may be retained as evidence.

`task lite:har:sanitize INPUT=<raw.har> OUTPUT=<safe.har>` removes authorization, cookies, credentials, NATS user info, Restic/Tailscale secrets, private keys, and sensitive query/header fields. `task lite:har:inspect` reports failed or duplicate Lite requests and heavy first-paint responses.
