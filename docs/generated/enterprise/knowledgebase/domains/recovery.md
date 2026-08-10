---
title: "Backup & Restore"
description: "Operational domain page for Backup & Restore."
generated: true
audience: production
page_type: domain
confidence: generated
---

# Backup & Restore

## Summary

Canonical domain documentation projection.

## Current state

Operational health: **degraded**. Semantic parity remains independent.

## Capabilities

No canonical per-domain capability list is present; see Platform Capability Matrix.

## Dependencies

| Dependency | State | Evidence |
| --- | --- | --- |
| FastAPI | healthy | verified-runtime-baseline |
| NATS/JetStream | healthy | verified-runtime-baseline |
| worker | healthy | verified-runtime-baseline |
| SQLite | healthy | verified-runtime-baseline |
| restic | unvalidated | source-derived |

## Evidence

Release/promoted evidence status: **release-promoted**.

## Known limitations

projection_too_old

## Recovery

Use canonical Recovery/Incident Runbooks; this page does not infer repair commands.

## Provenance

`contracts/generated/runtime/domain-operational-health.json` and canonical Documentation Platform metadata.
