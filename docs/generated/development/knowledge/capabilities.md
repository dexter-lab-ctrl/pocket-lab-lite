---
title: "Platforms and capabilities"
description: "Capability knowledge designed for Android/Termux, ARM64, WSL2, desktop, and mobile contexts."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Platforms and capabilities

| Capability | Freshness | Expiry | Degraded behavior | Runtime evidence |
| --- | --- | --- | --- | --- |
| App Host | 60 | stale | app actions remain visible but blocked when delivery is unsafe | fleet prepared projection |
| Backup Target | 60 | stale | storage backup remains unavailable | Recovery and fleet prepared projections |
| Compute | 60 | stale | commands remain undeliverable until the agent reconnects | fleet prepared projection |
| Storage Node | 60 | stale | media connection actions are blocked | fleet prepared projection |
| Security Scanner | 300 | stale | saved Security state remains read-only and new checks are blocked | Security compact summary |

## Platform matrix

| Capability | Platform | Role | Status | Evidence | Rationale |
| --- | --- | --- | --- | --- | --- |
| App Host | ARM64 Ubuntu/proot | execution | verified | release-promoted | PhotoPrism executes in the ARM64 Ubuntu/proot runtime owned by the server phone. |
| App Host | Android/Termux ARM64 | runtime-host | verified | release-promoted | The server-host role advertises app_host and the promoted Apps lane observes the managed app runtime. |
| App Host | Ubuntu/WSL2 Dev | development | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| App Host | desktop browser | control-client | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| App Host | mobile browser | control-client | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| App Host | secondary device | remote-node | implemented | source-derived | The compute device role advertises app_host, but the promoted baseline does not prove a currently ready secondary app host. |
| App Host | server phone | runtime-host | verified | release-promoted | The protected server-host role owns the current App Host runtime. |
| Backup Target | ARM64 Ubuntu/proot | execution | unvalidated | unvalidated | No canonical repository binding currently claims this capability on this platform. |
| Backup Target | Android/Termux ARM64 | storage | implemented | source-derived | The storage role advertises backup_target, while readiness still depends on a current qualifying storage node. |
| Backup Target | Ubuntu/WSL2 Dev | development | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Backup Target | desktop browser | control-client | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Backup Target | mobile browser | control-client | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Backup Target | secondary device | storage | implemented | source-derived | Secondary storage nodes are the canonical remote backup-target role. |
| Backup Target | server phone | runtime-host | unvalidated | unvalidated | No canonical repository binding currently claims this capability on this platform. |
| Compute | ARM64 Ubuntu/proot | execution | unvalidated | unvalidated | No canonical repository binding currently claims this capability on this platform. |
| Compute | Android/Termux ARM64 | runtime-host | verified | release-promoted | The server-host and compute roles advertise compute on Android/Termux ARM64. |
| Compute | Ubuntu/WSL2 Dev | development | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Compute | desktop browser | control-client | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Compute | mobile browser | control-client | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Compute | secondary device | remote-node | implemented | source-derived | The compute device role advertises compute, but current readiness must still come from fresh device evidence. |
| Compute | server phone | runtime-host | verified | release-promoted | The protected server phone is the canonical control-plane compute host. |
| Storage Node | ARM64 Ubuntu/proot | execution | unvalidated | unvalidated | No canonical repository binding currently claims this capability on this platform. |
| Storage Node | Android/Termux ARM64 | storage | implemented | source-derived | The storage role advertises media_storage on enrolled Android/Termux nodes; no current ready storage node is promoted. |
| Storage Node | Ubuntu/WSL2 Dev | development | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Storage Node | desktop browser | control-client | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Storage Node | mobile browser | control-client | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Storage Node | secondary device | storage | implemented | source-derived | The storage device role owns media_storage capability on secondary nodes. |
| Storage Node | server phone | runtime-host | unvalidated | unvalidated | No canonical repository binding currently claims this capability on this platform. |
| Security Scanner | ARM64 Ubuntu/proot | execution | unvalidated | unvalidated | No canonical repository binding currently claims this capability on this platform. |
| Security Scanner | Android/Termux ARM64 | scanner-host | verified | release-promoted | Lynis and Trivy execute behind FastAPI/worker boundaries on the Android/Termux server runtime. |
| Security Scanner | Ubuntu/WSL2 Dev | development | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Security Scanner | desktop browser | control-client | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Security Scanner | mobile browser | control-client | not-applicable | not-applicable | This platform is a control/development surface; Pocket Lab capabilities remain backend/runtime-owned and are not executed here. |
| Security Scanner | secondary device | remote-node | unvalidated | unvalidated | No canonical repository binding currently claims this capability on this platform. |
| Security Scanner | server phone | scanner-host | verified | release-promoted | The protected server-host role advertises security_scanner and promoted Security evidence observes it healthy. |

Identity and Rules remain partial and are not promoted to supported/verified by this matrix. Browser and development surfaces remain control/development roles rather than execution hosts.
