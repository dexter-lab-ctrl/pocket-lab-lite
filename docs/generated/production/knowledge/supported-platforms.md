---
title: "Supported platforms"
description: "Platform-aware capability knowledge."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# Supported platforms

Pocket Lab Lite remains designed for Android/Termux ARM64 and low-power edge operation, with Ubuntu/WSL2 used for development. Capability evidence is nuanced; implemented, observed, verified, partial, and unvalidated are not collapsed into yes/no.

| Capability | Freshness | Degraded behavior |
| --- | --- | --- |
| App Host | 60 | app actions remain visible but blocked when delivery is unsafe |
| Backup Target | 60 | storage backup remains unavailable |
| Compute | 60 | commands remain undeliverable until the agent reconnects |
| Storage Node | 60 | media connection actions are blocked |
| Security Scanner | 300 | saved Security state remains read-only and new checks are blocked |
