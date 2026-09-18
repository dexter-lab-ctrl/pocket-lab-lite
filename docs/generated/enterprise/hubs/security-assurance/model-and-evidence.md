---
title: "How the Security Model and Assurance Evidence Fit Together"
description: "Three security truth layers and how they correlate."
generated: true
audience: development
page_type: reference
confidence: generated
---

# How the Security Model and Assurance Evidence Fit Together

<div class="pl-page-lede"><strong>One security story, three different authorities.</strong><p>The Threat Model says what could go wrong. Assurance definitions say how Pocket Lab can test an assumption safely. Qualification evidence records what actually happened for one exact SHA.</p></div>

## Layer 1 — Threat Model / Security Atlas
Authority: `security/threat-model-scenarios.json` plus canonical architecture. It defines AP-* paths, boundaries, consequences, and CTRL-* controls. It is a saved model, not live monitoring.

## Layer 2 — Assurance Definition
Authority: `security/assurance/scenarios.yaml`, `suites.yaml`, and `tools.yaml`. Scenarios such as `harness-auth-boundary`, `caddy-proof-strip`, `source-boundaries`, and `security-projection` define safe registered invariants; they are not scanner products.

## Layer 3 — Qualification Evidence
Authority: sanitized per-qualification reports under `generated/enterprise/hubs/security-assurance/reports/`. Each preserves qualification ID, suite, runtime SHA, findings, result, and uncertainty.

## Conceptual join key
`AP-*` joins model → scenarios → exact qualification evidence without creating another registry.

## Human review is a different axis
Threat-model `human-review-required` is a human security-model/residual-risk decision. Qualification execution classification (`EXECUTABLE_NOW`, `PARTIALLY_EXECUTABLE`, `STATIC_EVIDENCE_ONLY`, `HUMAN_REVIEW_REQUIRED`) describes automation reach. Automated PASS never upgrades the human decision to PASS.

## Latest-suite compatibility
| Suite | Result | Runtime SHA | Qualification | Completed UTC | Registry relationship |
| --- | --- | --- | --- | --- | --- |
| Smoke | PASS | 66ed279c01 | assurance-2a29076a8244411daed1b0a5ca0c1d1a | 2026-09-17T11:30:42Z | current registries |
| Standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | 2026-09-17T11:37:52Z | current registries |
| Adversarial | PASS | 66ed279c01 | assurance-de72eb1604ed4b619c498bb2bc40e8b3 | 2026-09-17T11:39:34Z | current registries |
| Deep | PARTIAL | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | 2026-09-17T11:51:07Z | current registries |

Latest suite evidence currently spans **one runtime SHA**.
