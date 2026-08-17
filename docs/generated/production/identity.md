---
title: "Identity"
description: "Identity owns the local human owner credential, browser session lifecycle, recovery codes, and safe identity-class visibility. It does not replace device enrollment identity or service credentials."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 65a74e4abf0c0da3178307346cab000076511caf826cf3cad30fa9634abf0faa
schema_revision: 1
validation_status: generated
---

# Identity

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Identity owns the local human owner credential, browser session lifecycle, recovery codes, and safe identity-class visibility. It does not replace device enrollment identity or service credentials.

## Local owner

- One local owner is created only through the explicit setup flow and one-time setup token (or explicit environment bootstrap).
- Password verifiers use `scrypt`; raw passwords are never stored in the Identity tables.
- Browser sessions use opaque random credentials whose hashes are stored in SQLite; session cookies are HttpOnly and Secure by default.
- Browser writes require a separate same-site CSRF token. API-token service identity remains a distinct non-browser path.

## Recovery and sessions

- Recovery codes are high-entropy, shown once, stored hash-only, generation-scoped, and consumed once. Regeneration invalidates the prior batch.
- Password change and recovery increment the owner auth version and revoke stale sessions. Sessions can be revoked explicitly.
- Identity audit rows contain bounded reason codes and summaries, not credentials or recovery material.

## Boundaries

Device enrollment identity remains owned by Devices. Passkeys/WebAuthn and OIDC are optional and not enabled by this implementation. The local-owner implementation is intentionally bounded; advanced roles are not claimed. The frontend does not persist session credentials in localStorage, Dexie, Zustand, XState, or TanStack Query.
