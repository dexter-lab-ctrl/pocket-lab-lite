---
title: "Platforms and capabilities"
description: "Capability knowledge designed for Android/Termux, ARM64, WSL2, desktop, and mobile contexts."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
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

| Capability | Platform | Status | Components |
| --- | --- | --- | --- |
| App Host | Android/Termux ARM64 | unvalidated | — |
| App Host | ARM64 Ubuntu/proot | unvalidated | — |
| App Host | Ubuntu/WSL2 Dev | unvalidated | — |
| App Host | desktop browser | unvalidated | — |
| App Host | mobile browser | unvalidated | — |
| App Host | server phone | unvalidated | — |
| App Host | secondary device | unvalidated | — |
| Backup Target | Android/Termux ARM64 | unvalidated | — |
| Backup Target | ARM64 Ubuntu/proot | unvalidated | — |
| Backup Target | Ubuntu/WSL2 Dev | unvalidated | — |
| Backup Target | desktop browser | unvalidated | — |
| Backup Target | mobile browser | unvalidated | — |
| Backup Target | server phone | unvalidated | — |
| Backup Target | secondary device | unvalidated | — |
| Compute | Android/Termux ARM64 | unvalidated | — |
| Compute | ARM64 Ubuntu/proot | unvalidated | — |
| Compute | Ubuntu/WSL2 Dev | unvalidated | — |
| Compute | desktop browser | unvalidated | — |
| Compute | mobile browser | unvalidated | — |
| Compute | server phone | unvalidated | — |
| Compute | secondary device | unvalidated | — |
| Storage Node | Android/Termux ARM64 | unvalidated | — |
| Storage Node | ARM64 Ubuntu/proot | unvalidated | — |
| Storage Node | Ubuntu/WSL2 Dev | unvalidated | — |
| Storage Node | desktop browser | unvalidated | — |
| Storage Node | mobile browser | unvalidated | — |
| Storage Node | server phone | unvalidated | — |
| Storage Node | secondary device | unvalidated | — |
| Security Scanner | Android/Termux ARM64 | unvalidated | — |
| Security Scanner | ARM64 Ubuntu/proot | unvalidated | — |
| Security Scanner | Ubuntu/WSL2 Dev | unvalidated | — |
| Security Scanner | desktop browser | unvalidated | — |
| Security Scanner | mobile browser | unvalidated | — |
| Security Scanner | server phone | unvalidated | — |
| Security Scanner | secondary device | unvalidated | — |

Identity and Rules remain partial and are not promoted to supported/verified by this matrix.
