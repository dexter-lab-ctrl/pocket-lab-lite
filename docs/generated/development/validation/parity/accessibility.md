---
title: "Accessibility Conformance Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Accessibility Conformance Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

The repository already uses `@axe-core/playwright` and Storybook a11y. Recovery coverage includes the main tab and links to Manage, history, confirmation, progress, error, desktop, and mobile states. Serious and critical violations block the mocked gate; color contrast remains tracked separately by the existing test policy.
