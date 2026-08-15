---
title: "Sources of Truth"
description: "Explicit authority ordering and what may not override what."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Sources of Truth

| Area | Authority | What may not override it |
| --- | --- | --- |
| Architecture | Canonical architecture metadata | Generated architecture can project it; it cannot redefine it. |
| API | FastAPI/OpenAPI contracts | Generated docs cannot invent endpoints or compatibility. |
| Events | AsyncAPI/canonical event metadata | Generated docs cannot invent publishers, subscribers, durability, or ordering. |
| Runtime | Explicitly promoted sanitized runtime evidence | Repository HEAD never substitutes for promoted runtime. |
| Security | Canonical threat/control models + promoted normalized evidence | Modeled threat is not a confirmed exploit; residual risk remains human review. |
| Release | Verified release records and release evidence | Source HEAD is not a verified release baseline. |
| Generated documentation | Derived projection only | Generated Markdown/JSON does not become source authority. |
| Human risk acceptance | Human review only | Automation may surface evidence; it may not accept risk. |

## What may not override what

Generated output cannot override canonical source. Documentation Intelligence cannot mutate source/runtime. Threat Model overlays cannot redefine architecture topology. Knowledge Graph relations cannot be invented when source relations are missing. MkDocs cannot capture or promote evidence.
