---
title: "Documentation Platform Architecture"
description: "Static generation architecture and authority boundaries."
generated: true
audience: development
page_type: architecture
confidence: generated
---

# Documentation Platform Architecture

## Purpose

Turn repository-owned engineering truth into deterministic, local/static documentation without becoming a runtime control plane.

## Flow

`source → canonical contracts → explicit capture/promotion boundary → deterministic generators → generated contracts/pages → validation → MkDocs`

## Ownership

- Canonical source owns architecture, API, event, policy, and release semantics.
- Explicit capture/promotion tools own promoted evidence ingestion.
- Generators own deterministic derived projections.
- MkDocs owns static presentation/search/navigation only.

## Failure behavior

Generation fails closed on drift, dangling IA relations, invalid classification, unsafe path/secret exposure, or missing required canonical navigation targets.
