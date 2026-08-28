---
title: "Installation"
description: "Install through the repository-owned Lite bootstrap profile on the server phone. Do not install Development-PC documentation or browser tooling on Android/Termux."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: ae852e970e2385b9f84509e4a446d978365eb0e16ee80c312f96ab8f18ee8983
schema_revision: 1
validation_status: generated
---

# Installation

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Install through the repository-owned Lite bootstrap profile on the server phone. Do not install Development-PC documentation or browser tooling on Android/Termux.

Use the current release artifact and bootstrap scripts from the verified repository/release. Validate `/health`, `/ready`, Caddy same-origin access, NATS/JetStream, worker, node agent, and supervisor after install.
