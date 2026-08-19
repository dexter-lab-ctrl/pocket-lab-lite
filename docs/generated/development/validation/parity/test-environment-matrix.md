---
title: "Test Environment Matrix"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 8a90a66c46a250cebfd7e62993f9c541fa1c293fd7e4dd880cc399353b42bff4
generator: scripts/docs/parity/generate_parity.py
---

# Test Environment Matrix
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Environment | Proves | Does not prove | Status |
| --- | --- | --- | --- |
| WSL2 + VS Code | source generation, Python/Node tests, external Chrome browser tests, tool setup | phone runtime state | verified |
| GitHub Actions | clean checkout determinism, blocking gates, artifact retention | private phone reachability | verified |
| Temporary SQLite and backup root | backend persistence, projection mapping, failure attribution | production data | verified |
| MSW + Storybook | deterministic UI state, component accessibility, viewport behavior | backend persistence | verified |
| External Chrome mocked | integrated rendered meaning, offline/stale/error behavior, a11y and visual evidence | live backend authority | verified |
| External Chrome live | Caddy/FastAPI/browser integration | raw SQLite equality | unvalidated |
| Android/Termux ARM64 | sanitized runtime authority and process topology, read-only backend verifier | browser library correctness, Storybook behavior | runtime-source-verified |
