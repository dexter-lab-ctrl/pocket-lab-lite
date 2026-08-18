---
title: "Maintenance Ownership Matrix"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 0b555a4643cccbb5d48b5dd4e1492fc4487803cb12ab52681cdbd77e6e2bac27
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
