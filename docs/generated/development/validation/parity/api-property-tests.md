---
title: "API Property-Test Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# API Property-Test Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

`lite:api:schemathesis` exercises safe isolated endpoints from the generated OpenAPI contract. Live mode permits only GET/HEAD and excludes backup, restore, install, update, remove, restart, invite, and Security mutation paths. Unexpected 5xx responses and schema violations fail the gate.

**Current result:** unvalidated until the repository-local tool is installed.
