---
title: "API Property-Test Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 0b555a4643cccbb5d48b5dd4e1492fc4487803cb12ab52681cdbd77e6e2bac27
generator: scripts/docs/parity/generate_parity.py
---

# API Property-Test Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

`lite:api:schemathesis` first compiles a deny-by-default local OpenAPI document containing only Recovery GET projections. The compiler rejects write methods, maintenance endpoints, streams, side-effectful compatibility GETs, non-loopback sources, and empty selections before Schemathesis starts. It discovers bounded safe resource identifiers through FastAPI reads, injects only sanitized examples, runs one deterministic worker with rate limits and retries, and writes sanitized JUnit, NDJSON, selection-manifest, and categorized summary evidence.

`lite:api:schemathesis:discovery` compiles a broader GET-only schema and records non-gating evidence without coverage-phase unsupported-method probes or destructive operations.

**Runtime result:** unvalidated until run against an explicitly configured loopback API or SSH loopback tunnel.
