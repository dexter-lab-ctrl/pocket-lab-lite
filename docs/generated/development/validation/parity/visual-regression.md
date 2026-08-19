---
title: "Visual Regression Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 8a90a66c46a250cebfd7e62993f9c541fa1c293fd7e4dd880cc399353b42bff4
generator: scripts/docs/parity/generate_parity.py
---

# Visual Regression Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Existing Playwright visual checks remain separate from semantic parity. The all-tab live capture records bounded desktop and mobile observations, while visual approval continues to govern screenshot baselines independently. A pixel change can require baseline review even when semantic parity passes, and semantic parity can fail while screenshots remain visually similar.
