---
title: "Documentation Platform"
description: "How Pocket Lab Lite generates evidence-backed documentation."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Documentation Platform

Pocket Lab Lite documentation is a generated knowledge/evidence projection, not a control plane.

## Generation pipeline

`source + canonical contracts → promoted sanitized evidence → generators → validation → MkDocs`

## Security boundary

MkDocs does not capture runtime, poll NATS, run scanners, promote evidence, or access secrets.

## Sections

- Information architecture and UX contract
- Evidence model and runtime promotion
- Living Knowledge and Documentation Intelligence
- Architecture generation
- Validation gates and contributing
