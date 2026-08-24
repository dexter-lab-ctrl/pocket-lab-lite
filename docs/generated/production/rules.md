---
title: "Rules"
description: "Rules is the operator view of a loopback-only Open Policy Agent authorization layer. FastAPI remains authoritative and preserves hard domain invariants before any policy call."
status: verified
generated: true
audience: production
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 2c00a172d3837d03655330db878706b3c00cba2028169da9c596a847dcdc4e5e
schema_revision: 1
validation_status: generated
---

# Rules

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Production guidance</span>
</div>

Rules is the operator view of a loopback-only Open Policy Agent authorization layer. FastAPI remains authoritative and preserves hard domain invariants before any policy call.

## Runtime model

- OPA is installed as a pinned ARM64 runtime dependency and is not packaged in `dist.zip`.
- Startup validates repository Rego with `opa fmt`, `opa check --strict`, and `opa test --fail-on-empty` before atomically activating a revision and starting `pocket-opa` on `127.0.0.1:8181`.
- OPA is not routed through Caddy and is not called by the browser or NATS.
- FastAPI constructs bounded authorization input from server-owned actor/session and target state, asks OPA, reuses existing domain invariants/revision checks, and only then reaches the existing execution path.

## Current enforcement scope

- `catalog.install`
- `device.remove`

Unknown registered-action gaps, OPA unavailability, timeouts, and malformed decisions fail closed. Decision evidence stores bounded identifiers, allow/block state, stable reason code, policy revision, and evaluation duration; raw policy input, credentials, command payloads, and secrets are excluded. The current action set is deliberately narrow; advanced execution is not claimed. This authorization layer is not an Approval Model.
