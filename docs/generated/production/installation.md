---
title: "Installation"
description: "Install through the repository-owned Lite bootstrap profile on the server phone. Do not install Development-PC documentation or browser tooling on Android/Termux."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 9085e81a12fd1d6805333b96f1baac6009db2c4e4473d38484618ad81d0e0b82
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
