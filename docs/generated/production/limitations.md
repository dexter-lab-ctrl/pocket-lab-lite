---
title: "Current limitations"
description: "Only source-implemented behavior is listed; live server-phone qualification remains separate."
status: unvalidated
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: b7a97038604d5fd6c3c4888b06e8ac22811c30be01fb0fa6f6d25cdcbb897ce2
schema_revision: 1
validation_status: generated
---

# Current limitations

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--unvalidated">Unvalidated</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Only source-implemented behavior is listed; live server-phone qualification remains separate.

- Passkeys/WebAuthn are implemented for local human registration/login/rename/revoke and purpose-bound step-up. External OIDC federation and service-identity provisioning or management remain deferred; the separate API-token actor/path is not a browser human session.
- Enterprise Mode is opt-in. Memberships and roles are server-owned, including final-Owner protection; it does not imply external federation.
- Rules protects only explicitly registered actions; broader authorization coverage is not implied. Approval is an independent, expiring gate and never executes an action automatically.
- Temporary exceptions apply only to exact `catalog.install` app/device/human/revision scope, are revocable, and last at most 60 minutes.
- The legacy generic secret store remains separate from the human Identity credential store and must not be treated as the owner password backend.
- Android performance and live OPA/process claims require server-phone evidence; desktop/source validation alone is insufficient.
- Live browser and long-duration qualification require a running isolated stack and explicit user action.
