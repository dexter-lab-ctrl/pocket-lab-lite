---
title: "Supported platforms"
description: "Platform-aware capability knowledge."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Supported platforms

Pocket Lab Lite remains designed for Android/Termux ARM64 and low-power edge operation, with Ubuntu/WSL2 used for development. Capability evidence is role-aware; verified, observed, implemented, not-applicable, and unvalidated are not collapsed into yes/no.

## Capability definitions

| Capability | Freshness | Degraded behavior |
| --- | --- | --- |
| App Host | 60 | app actions remain visible but blocked when delivery is unsafe |
| Backup Target | 60 | storage backup remains unavailable |
| Compute | 60 | commands remain undeliverable until the agent reconnects |
| Storage Node | 60 | media connection actions are blocked |
| Security Scanner | 300 | saved Security state remains read-only and new checks are blocked |

## Evidence-backed platform matrix

| Capability | Platform | Role | Status | Evidence |
| --- | --- | --- | --- | --- |
| App Host | ARM64 Ubuntu/proot | execution | verified | release-promoted |
| App Host | Android/Termux ARM64 | runtime-host | verified | release-promoted |
| App Host | Ubuntu/WSL2 Dev | development | not-applicable | not-applicable |
| App Host | desktop browser | control-client | not-applicable | not-applicable |
| App Host | mobile browser | control-client | not-applicable | not-applicable |
| App Host | secondary device | remote-node | implemented | source-derived |
| App Host | server phone | runtime-host | verified | release-promoted |
| Backup Target | ARM64 Ubuntu/proot | execution | unvalidated | unvalidated |
| Backup Target | Android/Termux ARM64 | storage | implemented | source-derived |
| Backup Target | Ubuntu/WSL2 Dev | development | not-applicable | not-applicable |
| Backup Target | desktop browser | control-client | not-applicable | not-applicable |
| Backup Target | mobile browser | control-client | not-applicable | not-applicable |
| Backup Target | secondary device | storage | implemented | source-derived |
| Backup Target | server phone | runtime-host | unvalidated | unvalidated |
| Compute | ARM64 Ubuntu/proot | execution | unvalidated | unvalidated |
| Compute | Android/Termux ARM64 | runtime-host | verified | release-promoted |
| Compute | Ubuntu/WSL2 Dev | development | not-applicable | not-applicable |
| Compute | desktop browser | control-client | not-applicable | not-applicable |
| Compute | mobile browser | control-client | not-applicable | not-applicable |
| Compute | secondary device | remote-node | implemented | source-derived |
| Compute | server phone | runtime-host | verified | release-promoted |
| Storage Node | ARM64 Ubuntu/proot | execution | unvalidated | unvalidated |
| Storage Node | Android/Termux ARM64 | storage | implemented | source-derived |
| Storage Node | Ubuntu/WSL2 Dev | development | not-applicable | not-applicable |
| Storage Node | desktop browser | control-client | not-applicable | not-applicable |
| Storage Node | mobile browser | control-client | not-applicable | not-applicable |
| Storage Node | secondary device | storage | implemented | source-derived |
| Storage Node | server phone | runtime-host | unvalidated | unvalidated |
| Security Scanner | ARM64 Ubuntu/proot | execution | unvalidated | unvalidated |
| Security Scanner | Android/Termux ARM64 | scanner-host | verified | release-promoted |
| Security Scanner | Ubuntu/WSL2 Dev | development | not-applicable | not-applicable |
| Security Scanner | desktop browser | control-client | not-applicable | not-applicable |
| Security Scanner | mobile browser | control-client | not-applicable | not-applicable |
| Security Scanner | secondary device | remote-node | unvalidated | unvalidated |
| Security Scanner | server phone | scanner-host | verified | release-promoted |
