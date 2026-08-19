---
title: "Cross-link model"
description: "Deterministic bounded relationship joins for navigation and Feature Journeys."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Cross-link model

Cross-links are generated from canonical page targets and the Knowledge Graph cross-reference index. The current contract contains **755** stable relations.

## Algorithm

- build adjacency/reverse indexes once;
- use deterministic set joins;
- use bounded BFS only where contextual expansion adds value;
- max depth 2, strict result caps, cycle detection;
- never perform runtime traversal or network calls;
- never invent a missing relationship.

Machine contract: `contracts/generated/documentation-enterprise/documentation-cross-links.json`.
