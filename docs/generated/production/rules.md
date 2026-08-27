---
title: "Rules"
description: "Rules is the operator view of loopback-only Open Policy Agent admission and bounded policy governance. FastAPI remains authoritative and preserves hard domain invariants before any policy call or continuation."
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

# Rules

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Rules is the operator view of loopback-only Open Policy Agent admission and bounded policy governance. FastAPI remains authoritative and preserves hard domain invariants before any policy call or continuation.

## Runtime model

- OPA is installed as a pinned ARM64 runtime dependency and is not packaged in `dist.zip`.
- Startup validates repository Rego with `opa fmt`, `opa check --strict`, and `opa test --fail-on-empty` before atomically activating a revision and starting `pocket-opa` on `127.0.0.1:8181`. OPA is not routed through Caddy and is not called by the browser or NATS.
- FastAPI constructs bounded authorization input from server-owned actor/session and target state, asks loopback OPA, reuses existing domain invariants/revision checks, and only then reaches the existing execution path. Unavailable, timed-out, malformed, or unknown decisions fail closed.

## Policy lifecycle and evaluation

- Typed policy candidates become immutable revisions. Validation, activation/readiness, active and known-good state, rollback, and uncertain-recovery resolution remain explicit and auditable.
- Analysis reports only direct registered-action coverage that current templates can prove. Simulation uses bounded real-derived or synthetic input and never executes an action.
- Decision evidence stores bounded identifiers, allow/block state, stable reason code, policy revision, and evaluation duration; raw policy input, credentials, command payloads, and secrets are excluded.

## Approval and exception bounds

- A policy may require independent approval. An eligible Owner or Admin other than the initiator must complete purpose-bound passkey step-up for the exact action, target, and policy revision before an expiring approval is recorded. The initiator must retry; the matching continuation is atomic, one-use, and refuses replay. Approval never auto-executes an action.
- Temporary exceptions are limited to exact `catalog.install` app/device/human/revision scope, must be revoked or expire within 60 minutes, and do not bypass hard domain invariants.

The registered enforcement surface remains deliberately bounded; broader authorization coverage is not implied.
