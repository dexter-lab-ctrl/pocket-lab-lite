---
title: "Identity and Rules implementation boundaries"
description: "Identity now implements one local human owner, hash-only credentials/sessions/recovery records, CSRF-protected browser writes, and explicit session lifecycle. Rules now reports a loopback OPA engine and enforces the first bounded policy set for app install and old-device removal."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 8b7e457bdeb6cbdf9bf6dc80faa75c6bbcbe4b1a448ea3d2c75c39d81a65f0a0
schema_revision: 1
validation_status: generated
---

# Identity and Rules implementation boundaries

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Identity now implements one local human owner, hash-only credentials/sessions/recovery records, CSRF-protected browser writes, and explicit session lifecycle. Rules now reports a loopback OPA engine and enforces the first bounded policy set for app install and old-device removal.

## Identity

The implemented local-owner flow covers setup, sign-in, password change, logout/session revocation, and one-time recovery codes. Passkeys/WebAuthn and OIDC federation remain optional and are not presented as enabled. Device identities remain owned by Devices; API-token service identity remains separate from the human session.

## Rules

FastAPI builds the authorization input, preserves non-bypassable domain invariants, asks loopback OPA only for registered protected actions, records bounded sanitized decision metadata, and fails closed on unavailable/invalid policy responses. The first registered actions are `catalog.install` and `device.remove`; this is not an Approval Model.
