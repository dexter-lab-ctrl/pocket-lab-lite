---
title: "Accepted Parity Limitations"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Accepted Parity Limitations
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Domain | Type | Description |
| --- | --- | --- |
| Home | accepted-limitation | CPU, memory, and storage presentation may be rounded or unit-formatted. |
| Home | unsupported | Home never executes system operations directly. |
| Apps | accepted-limitation | PhotoPrism is the currently cataloged runtime app; cross-app coverage grows from the same contract. |
| Apps | unsupported | Restore apply and update apply remain unavailable unless separately implemented and validated. |
| Devices | accepted-limitation | Heartbeat freshness can move during capture; comparison records the observed revision. |
| Devices | unsupported | Healthy online devices are not removed without explicit confirmation. |
| Security | accepted-limitation | Raw scanner output and sensitive paths are intentionally excluded. |
| Security | unsupported | The browser never runs Lynis, Trivy, shell, PM2, or NATS commands. |
| Identity | accepted-limitation | Credential values are never observable parity fields. |
| Identity | unsupported | Identity mismatch repair/rejoin must remain explicit and fail closed. |
| Rules | accepted-limitation | The current product contract is a protection-mode policy surface, not a general arbitrary rule engine. |
| Rules | unsupported | Planned trigger/condition/action automation is not marked verified. |
| Backup & Restore | accepted-limitation | Status labels intentionally use Lite-friendly wording instead of raw backend enums. |
| Backup & Restore | accepted-limitation | App restore apply remains explicitly unsupported where the repository reports it unavailable. |
| Backup & Restore | unsupported | Unsafe writes remain disabled while the recovery projection is stale. |
