---
title: "Projection Parity Architecture"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Projection Parity Architecture
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

## Flow

```text
backend durable authority
→ prepared projection
→ FastAPI /api/lite/*
→ TanStack Query
→ frontend selector/view model
→ React rendering
→ sanitized evidence
```

| Boundary | Left | Right | Comparison | Owner |
| --- | --- | --- | --- | --- |
| backend-api | backend durable authority | FastAPI API projection | semantic | backend-platform |
| api-selector | FastAPI API payload | frontend selector/view model | semantic | frontend-platform |
| selector-render | frontend selector/view model | rendered React UI | meaning-and-visible-state | frontend-quality |

## Method

Stable identifiers correlate authority, API, selector, and UI evidence. Comparisons normalize enums, formatting, ordering, timestamps, and intentional user-facing labels. Byte equality is reserved for generated artifacts. Last-good and stale states must remain visibly truthful. Runtime evidence and fixture evidence are recorded separately.
