---
title: "Maintenance Ownership Matrix"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Maintenance Ownership Matrix
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Artifact | Owner | Reviewers | Cadence | Status |
| --- | --- | --- | --- | --- |
| Recovery Storybook, Playwright, accessibility, and visual parity linkage | frontend-quality | frontend-platform, accessibility | each rendered Recovery state or interaction change | ready |
| contracts/parity/parity-model.json | architecture-and-quality | backend, frontend, security | each projection contract change | ready |
| recovery backend mappings | backend-platform | recovery, security | each recovery schema or endpoint change | ready |
| recovery selector and UI mappings | frontend-platform | quality, accessibility | each selector or UI state change | ready |
| live Termux parity | runtime-operations | security | release qualification or explicit runtime verification | unvalidated |
