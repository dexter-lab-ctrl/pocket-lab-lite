---
title: "Current limitations"
description: "Only source-implemented behavior is listed; live server-phone qualification remains separate."
status: unvalidated
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: e8f126c5205c0e3d902fd72cecfa7d2085539a23a187c70d9f4d8f49920f6ae6
schema_revision: 1
validation_status: generated
---

# Current limitations

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--unvalidated">Unvalidated</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Only source-implemented behavior is listed; live server-phone qualification remains separate.

- Passkeys/WebAuthn and OIDC federation are not enabled; Pocket Lab Lite remains self-contained with the local owner flow.
- Rules currently protects the explicitly registered `catalog.install` and `device.remove` actions; broader authorization coverage is not implied.
- The legacy generic secret store remains separate from the human Identity credential store and must not be treated as the owner password backend.
- Android performance and live OPA/process claims require server-phone evidence; desktop/source validation alone is insufficient.
- Live browser and long-duration qualification require a running isolated stack and explicit user action.
