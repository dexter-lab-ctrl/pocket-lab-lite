---
title: "Visual Regression Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 0b555a4643cccbb5d48b5dd4e1492fc4487803cb12ab52681cdbd77e6e2bac27
generator: scripts/docs/parity/generate_parity.py
---

# Visual Regression Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Existing Playwright visual checks remain separate from semantic parity. The all-tab live capture records bounded desktop and mobile observations, while visual approval continues to govern screenshot baselines independently. A pixel change can require baseline review even when semantic parity passes, and semantic parity can fail while screenshots remain visually similar.
