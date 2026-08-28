---
title: "Identity and Rules implementation boundaries"
description: "Identity implements local human authentication, passkeys, step-up, and opt-in Enterprise memberships. Rules provides bounded policy governance without moving execution authority from FastAPI."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: f550711dc74aee58192a2de538c36f44f39585a42364cb9b53930ee3c78398d2
schema_revision: 1
validation_status: generated
---

# Identity and Rules implementation boundaries

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Identity implements local human authentication, passkeys, step-up, and opt-in Enterprise memberships. Rules provides bounded policy governance without moving execution authority from FastAPI.

## Identity

The local human flow covers setup, sign-in, password change, logout/session revocation, one-time recovery codes, and passkey registration, sign-in, rename, and revoke. WebAuthn validates origin, RP ID, and one-use challenges; purpose-bound passkey step-up expires. Personal Mode is the default. Opt-in Enterprise Mode uses server-owned memberships and roles, with final-Owner protection. Device identities remain owned by Devices. The separate API-token actor/path is not a browser human session. External OIDC federation and service-identity provisioning or management remain deferred.

## Rules

FastAPI builds server-owned authorization input, preserves non-bypassable domain invariants, asks loopback OPA only for registered protected actions, records bounded sanitized decisions, and fails closed on unavailable or invalid policy responses. Rules supports immutable typed revisions, validation, activation/readiness, known-good rollback, uncertain-recovery resolution, deterministic analysis, and non-executing simulation. Independent approval is a bounded gate: an eligible Owner or Admin other than the initiator completes passkey step-up for the exact action, target, and revision; the initiator retries with a one-use continuation. Approval never executes the action. Temporary exceptions are limited to exact `catalog.install` app/device/human/revision scope, are revocable, and last no more than 60 minutes.
