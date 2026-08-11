---
title: "User"
description: "Uses Pocket Lab Lite through the browser."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# User

Uses Pocket Lab Lite through the browser.

## Why it exists

Uses Pocket Lab Lite through the browser.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:user` |
| Owner | User |
| Execution owner | Browser |
| Data owner | None |
| Recovery owner | User |
| Runtime owner | Browser |
| Runtime process | Browser |
| Runtime platform | Human user device |
| Security boundary | browser |
| Confidence | verified |

## Responsibilities

- Uses Pocket Lab Lite through the browser.

## Inputs

- Pocket Lab Lite status and actions

## Outputs

- Intent and confirmation

## Supported platforms

- Browser

## Depends on / uses

- depends_on: `Browser`
- protected_by: `Browser trust boundary`
- protected_by: `Browser trust boundary`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_premium_tab_polish.py`
- verified_by: `tests/backend/test_lite_security_f3_summary_contract.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

No verified backlinks.

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/user.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `src/lite/LiteApp.jsx`
