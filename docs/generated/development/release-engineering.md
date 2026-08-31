---
title: "Release engineering"
description: "Release qualification is explicit and does not make live, Android, or long-duration checks part of every edit loop."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: d3d2e9f9374905a75e5417e625f75e57b28eaf31429b5558d56e82e511750e6e
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
