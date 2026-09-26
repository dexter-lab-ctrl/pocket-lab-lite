---
title: "Installation"
description: "Install through the repository-owned Lite bootstrap profile on the server phone. Do not install Development-PC documentation or browser tooling on Android/Termux."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: c36d3e48e3b8d6f30f2e35c3ee95ae21ee5d2c3fc91cc4848bc6f02980d6843d
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
