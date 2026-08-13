---
title: "Browser"
description: "Hosts the installed or web PWA and enforces browser-origin boundaries."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 2
---

# Browser

Hosts the installed or web PWA and enforces browser-origin boundaries.

## Why it exists

Hosts the installed or web PWA and enforces browser-origin boundaries.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:browser` |
| Owner | Browser |
| Execution owner | Browser |
| Data owner | None |
| Recovery owner | Browser reload / service-worker update |
| Runtime owner | Browser |
| Runtime process | Browser |
| Runtime platform | User device |
| Security boundary | browser |
| Confidence | verified |

## Responsibilities

- Hosts the installed or web PWA and enforces browser-origin boundaries.

## Inputs

- HTML, CSS, JavaScript, SVG

## Outputs

- Same-origin HTTP requests

## Health signals

- page load
- service worker readiness

## Supported platforms

- Browser
- Android
- Desktop

## Depends on / uses

- depends_on: `React / Vite PWA`
- protected_by: `Browser trust boundary`
- protected_by: `Browser trust boundary`
- recovers_with: `Pocket Lab UI unavailable`
- verified_by: `tests/backend/test_lite_api.py`
- verified_by: `tests/backend/test_lite_development_documentation_platform.py`
- verified_by: `tests/backend/test_lite_n6b_install_surface.py`
- verified_by: `tests/backend/test_lite_native_release.py`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/backend/test_release_process_isolation.py`
- verified_by: `tests/dev/test_frontend_resource_policy.py`
- verified_by: `tests/docs/test_docs_runtime_network_fence.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `User`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/browser.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
- `index.html`
- `vite.config.js`
