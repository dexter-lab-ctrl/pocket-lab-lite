---
title: "Generation lifecycle"
description: "Deterministic documentation generation and explicit evidence-promotion boundary."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Generation lifecycle

`repository source → canonical contracts → explicit runtime/security capture → sanitization → explicit promotion → deterministic generation → validation → MkDocs`

## Hard boundary

`task lite:docs:sync` regenerates/checks documentation. It does not capture runtime, promote evidence, run heavy scanners, or access secrets.

Generated output remains derived and reproducible; it never becomes source authority.
