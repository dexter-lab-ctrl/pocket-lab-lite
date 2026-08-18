---
title: "OpenAPI Compatibility Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 0b555a4643cccbb5d48b5dd4e1492fc4487803cb12ab52681cdbd77e6e2bac27
generator: scripts/docs/parity/generate_parity.py
---

# OpenAPI Compatibility Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

`lite:api:breaking-changes` verifies the promoted baseline hash before comparing it with the generated Lite OpenAPI contract. The wrapper disables external references, writes JSON through an atomic temporary file, rejects malformed reports, and fails on unapproved breaking errors. Baseline replacement requires an explicit promotion manifest containing the previous hash, promoted hash, rationale, validation commands, and secret-safety review. No generated OpenAPI file is manually edited.

**Runtime result:** unvalidated until the repository-local `oasdiff` binary is available and the gate is run.
