---
title: "Search & discovery"
description: "Static local search metadata, aliases, and weighted intent model."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Search & discovery

Search remains local/static. No hosted search, vector database, RAG service, or runtime indexer is required.

## Ranking model

`weighted-lexical-static` with deterministic title/alias/intent/domain/page-type/audience/canonical weighting.

## Alias groups

13 task-oriented alias groups are emitted into the machine contract and surfaced in hub content so MkDocs local search can discover operator/user entry points before deep implementation pages where practical.

Machine contract: `contracts/generated/documentation-enterprise/documentation-search.json`.
