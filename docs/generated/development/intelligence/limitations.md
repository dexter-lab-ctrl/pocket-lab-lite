---
title: "Known limitations"
description: "Accepted constraints, open gaps, and unsupported operations without hiding uncertainty."
generated: true
audience: development
confidence: generated
---

# Known limitations and unsupported states

| Area | Type | Status | What it means | Implementation | Health |
| --- | --- | --- | --- | --- | --- |
| Apps | accepted-limitation | accepted | PhotoPrism is the currently cataloged runtime app; cross-app coverage grows from the same contract. | implemented | healthy |
| Apps | known-gap | open | Application-owned media indexing is not a Pocket Lab parity authority. | implemented | healthy |
| Apps | unsupported-operation | unsupported | Restore apply and update apply remain unavailable unless separately implemented and validated. | implemented | healthy |
| Devices | accepted-limitation | accepted | Heartbeat freshness can move during capture; comparison records the observed revision. | implemented | healthy |
| Devices | known-gap | open | Per-device profile fields remain partial when the agent has not published them. | implemented | healthy |
| Devices | unsupported-operation | unsupported | Healthy online devices are not removed without explicit confirmation. | implemented | healthy |
| Home | accepted-limitation | accepted | CPU, memory, and storage presentation may be rounded or unit-formatted. | implemented | degraded |
| Home | known-gap | open | Live runtime semantic evidence remains explicit and release-bound. | implemented | degraded |
| Home | unsupported-operation | unsupported | Home never executes system operations directly. | implemented | degraded |
| Identity | accepted-limitation | accepted | Credential values are never observable parity fields. | partial | unvalidated |
| Identity | accepted-limitation | accepted | Identity guard and protected server-host authority fields are planned and may remain unavailable until identity bootstrap services are implemented. | partial | unvalidated |
| Identity | known-gap | open | The current tab is direct-rendered and has no dedicated selector layer. | partial | unvalidated |
| Identity | known-gap | open | Identity guard and protected server-host projections are not fully implemented. | partial | unvalidated |
| Identity | unsupported-operation | unsupported | Identity mismatch repair/rejoin must remain explicit and fail closed. | partial | unvalidated |
| Backup & Restore | accepted-limitation | accepted | Status labels intentionally use Lite-friendly wording instead of raw backend enums. | implemented | degraded |
| Backup & Restore | accepted-limitation | accepted | App restore apply remains explicitly unsupported where the repository reports it unavailable. | implemented | degraded |
| Backup & Restore | accepted-limitation | accepted | Historical restore previews are evidence only and never authorize a new restore. | implemented | degraded |
| Backup & Restore | known-gap | open | Live Termux and live browser semantic capture remain explicit; missing capture is not drift. | implemented | degraded |
| Backup & Restore | unsupported-operation | unsupported | Unsafe writes remain disabled while the recovery projection is stale. | implemented | degraded |
| Rules | accepted-limitation | accepted | The current product contract is a protection-mode policy surface, not a general arbitrary rule engine. | partial | unvalidated |
| Rules | known-gap | open | Per-rule identity and execution history are planned, not present in the current API. | partial | unvalidated |
| Rules | unsupported-operation | unsupported | Planned trigger/condition/action automation is not marked verified. | partial | unvalidated |
| Security | accepted-limitation | accepted | Raw scanner output and sensitive paths are intentionally excluded. | implemented | healthy |
| Security | known-gap | open | A missing scanner is runtime-unavailable, not semantic drift. | implemented | healthy |
| Security | unsupported-operation | unsupported | The browser never runs Lynis, Trivy, shell, PM2, or NATS commands. | implemented | healthy |
