---
title: "Identity"
description: "Identity owns local human credentials, browser session lifecycle, recovery codes, passkeys, step-up, and safe identity-class visibility. It does not replace device enrollment identity or the separate API-token actor/path."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 3bd1846004fa5a873680d41dd98c02813d700c3d91507c781e5de3b5baa151ca
schema_revision: 1
validation_status: generated
---

# Identity

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Identity owns local human credentials, browser session lifecycle, recovery codes, passkeys, step-up, and safe identity-class visibility. It does not replace device enrollment identity or the separate API-token actor/path.

## Local human authentication

- A local owner is created through the explicit setup flow and one-time setup token, or through the explicit passkey owner-claim flow.
- Password verifiers use `scrypt`; raw passwords are never stored in the Identity tables.
- Browser sessions use opaque random credentials whose hashes are stored in SQLite; session cookies are HttpOnly and Secure by default. Browser writes require a separate same-site CSRF token.

## Passkeys and step-up

- Passkeys support registration, sign-in, friendly-name updates, and revoke. WebAuthn validates the HTTPS origin (with localhost development support), RP ID, and one-use challenge; credential public keys and counters are server-recorded without exposing authenticator material.
- Purpose-bound passkey step-up provides short-lived server-recorded assurance for protected actions. It does not make browser-provided assurance authoritative.

## Recovery, sessions, and Enterprise Mode

- Recovery codes are high-entropy, shown once, stored hash-only, generation-scoped, and consumed once. Regeneration invalidates the prior batch. Password change and recovery increment the owner auth version and revoke stale sessions; sessions can also be revoked explicitly.
- Personal Mode is the default. Opt-in Enterprise Mode uses server-owned memberships and roles, and prevents removal or demotion of the final active Owner.
- Identity audit rows contain bounded reason codes and summaries, not credentials, recovery material, challenges, or credential identifiers.

## Boundaries

Device enrollment identity remains owned by Devices. The separate API-token actor/path is non-browser and does not grant a human session. External OIDC federation and service-identity provisioning or management are deferred. The frontend does not persist session credentials in localStorage, Dexie, Zustand, XState, or TanStack Query.
