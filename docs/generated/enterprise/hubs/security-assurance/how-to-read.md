---
title: "How to Read Security Documentation"
description: "Question-to-destination navigation and security truth-boundary vocabulary."
generated: true
audience: development
page_type: reference
confidence: generated
---

# How to Read Security Documentation

Use the question you are trying to answer; no page is a universal security verdict.

| Question | Go here | Path |
| --- | --- | --- |
| What asset are we protecting? | Threat Model → Assets & Guardrails | ../../threat-model/assets-guardrails.md |
| Which trust boundary is crossed? | Architecture → Trust Boundaries | ../../../production/architecture/network-boundaries.md |
| What can go wrong? | Threat Model / Security Atlas | ../../threat-model/index.md |
| Which control should mitigate it? | Security Controls | ../../reference/security-controls.md |
| How do we test that assumption? | Scenario → Model | scenario-model.md |
| What happened in the latest qualification? | Security Assurance Reports | reports/index.md |
| Where do model and evidence meet? | Model ↔ Assurance Evidence | model-assurance-evidence.md |
| What remains uncertain or human-owned? | Evidence & Provenance / Human Review | ../../threat-model/evidence.md |

## Vocabulary

| Term | Meaning |
| --- | --- |
| Threat Model | Saved modeled threats and controls; not live monitoring. |
| Scenario | Registered invariant and safe execution definition; not a scanner product. |
| Qualification | Bounded evidence for one exact qualification and runtime SHA; not a universal security claim. |
| Pass | The registered invariant held for the observed qualification evidence; not proof it can never fail. |
| Partial | Valid evidence exists but coverage or resulting condition is incomplete. |
| Coverage | Evidence coverage ratio; never a security score. |
| Human Review | Human-governed review remains separate from automated checks and cannot be auto-promoted to PASS. |
