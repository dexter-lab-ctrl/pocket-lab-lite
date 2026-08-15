---
title: "Security boundaries"
description: "Documentation Platform security invariants and prohibited behaviors."
generated: true
audience: development
page_type: architecture
confidence: generated
---

# Security boundaries

- MkDocs does not capture runtime, poll NATS, run scanners, promote evidence, execute shell commands, or access backend secrets.
- Generated IA/search/cross-link contracts reject private machine paths and secret-like values before writing.
- Knowledge Graph and Feature Journeys may only emit relationships backed by canonical repository contracts.
- Runtime/security evidence must be explicitly sanitized and promoted before documentation ingestion.
