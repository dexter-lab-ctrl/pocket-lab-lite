---
title: "Operations & troubleshooting"
description: "Documentation generation/drift troubleshooting without runtime side effects."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Operations & troubleshooting

## Generated drift

Run the owning generator in check mode, then regenerate from canonical source. Do not patch generated Markdown by hand.

## Broken navigation or relation

Use the IA validation error to identify the missing path/entity or duplicate owner. Fix source metadata/navigation and regenerate.

## Evidence mismatch

Verify capture/promotion inputs outside MkDocs. Documentation generation must never compensate by reading live runtime or substituting repository HEAD.
