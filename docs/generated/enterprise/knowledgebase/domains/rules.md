---
title: "Rules"
description: "Operational domain page for Rules."
generated: true
audience: production
page_type: domain
confidence: generated
---

# Rules

## Summary

Canonical domain documentation projection.

## Current state

Operational health: **unvalidated**. Semantic parity remains independent.

## Capabilities

No canonical per-domain capability list is present; see Platform Capability Matrix.

## Dependencies

| Dependency | State | Evidence |
| --- | --- | --- |
| FastAPI | healthy | verified-runtime-baseline |
| SQLite | healthy | verified-runtime-baseline |
| OPA policy engine | unvalidated | source-derived |
| Policy lifecycle | unvalidated | source-derived |
| Independent approvals | unvalidated | source-derived |
| Temporary exceptions | unvalidated | source-derived |

## Evidence

Release/promoted evidence status: **release-promoted**.

## Known limitations

See generated Known Limitations; none inferred here.

## Recovery

Use canonical Recovery/Incident Runbooks; this page does not infer repair commands.

## Provenance

`contracts/generated/runtime/domain-operational-health.json` and canonical Documentation Platform metadata.

## Rules relationships

[Rules Feature Journey](../../journeys/rules.md) links protected-action admission, lifecycle, analysis, approval, continuation, and narrow exceptions. [API-to-UI Trace](../../reference/api-ui-trace.md) does not infer NATS or worker execution for these governance operations.
