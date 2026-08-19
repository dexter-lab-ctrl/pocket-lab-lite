---
title: "CI Workflow-to-Gate Map"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 8a90a66c46a250cebfd7e62993f9c541fa1c293fd7e4dd880cc399353b42bff4
generator: scripts/docs/parity/generate_parity.py
---

# CI Workflow-to-Gate Map
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Workflow | Job | Task | Suite | Evidence | Blocking | Status |
| --- | --- | --- | --- | --- | --- | --- |
| .github/workflows/lite-quality.yml | quick-and-docs | lite:parity:check | contracts/backend/selectors/docs | pocket-lab-lite-validation | True | patch-provided |
