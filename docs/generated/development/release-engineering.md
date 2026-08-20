---
title: "Release engineering"
description: "Release qualification is explicit and does not make live, Android, or long-duration checks part of every edit loop."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 4c506f3c2d7eb0f19e0dc657293a3905cafc1cf98b6dc043ee40e1e881280a7a
schema_revision: 1
validation_status: generated
---

# Release engineering

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Release qualification is explicit and does not make live, Android, or long-duration checks part of every edit loop.

Run `task lite:check:release` with a running isolated stack and `LITE_E2E_LIVE=1`, then `task lite:release:dry-run`. Artifact validation checks required PWA files, checksum, optional release manifest identity, and forbidden development/state/secret entries.
