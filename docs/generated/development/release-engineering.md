---
title: "Release engineering"
description: "Release qualification is explicit and does not make live, Android, or long-duration checks part of every edit loop."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: d2c746aef06578690fde91eed58cee472bf9824cb8897cea21662a62a0f1fb12
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
