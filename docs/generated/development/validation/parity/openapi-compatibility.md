---
title: "OpenAPI Compatibility Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# OpenAPI Compatibility Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

`lite:api:breaking-changes` compares a caller-supplied or promoted OpenAPI baseline with the generated current Lite OpenAPI contract. It reports removed paths, required-field additions, enum/nullability changes, and response compatibility. No generated OpenAPI file is manually edited.

**Current result:** unvalidated until `oasdiff` is installed and a baseline is provided or promoted explicitly.
