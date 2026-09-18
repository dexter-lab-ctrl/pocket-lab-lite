---
title: "Security & Assurance"
description: "Threat model, assurance definition, exact qualification evidence, and uncertainty in one correlated static view."
generated: true
audience: development
page_type: overview
confidence: generated
---

# Security & Assurance

<div class="pl-page-lede"><strong>Model what could go wrong. Define how to test it safely. Preserve what actually happened.</strong><p>This hub correlates existing canonical security sources and sanitized qualification evidence. It does not create a second threat model or a live monitoring surface.</p></div>

## Latest Security Assurance

Published qualification artifacts: **5**. Historical artifacts outside the latest-per-suite set: **1**.

The latest suite set uses one runtime SHA.

| Suite | Result | Runtime SHA | Qualification | Completed UTC | Registry relationship |
| --- | --- | --- | --- | --- | --- |
| Smoke | PASS | 66ed279c01 | assurance-2a29076a8244411daed1b0a5ca0c1d1a | 2026-09-17T11:30:42Z | current registries |
| Standard | PASS | 66ed279c01 | assurance-b798f7e3a4c64b8b8c780a6c737b9e23 | 2026-09-17T11:37:52Z | current registries |
| Adversarial | PASS | 66ed279c01 | assurance-de72eb1604ed4b619c498bb2bc40e8b3 | 2026-09-17T11:39:34Z | current registries |
| Deep | PARTIAL | 66ed279c01 | assurance-3d7968589ce447f18454d1caf69a10e3 | 2026-09-17T11:51:07Z | current registries |

> **Truth boundary:** PASS means the registered invariant held for that exact qualification evidence. It is not a universal security guarantee. PARTIAL means valid evidence exists but coverage or the resulting condition is incomplete.

## Navigate by question

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">Security Assurance Reports</span><p>Per-qualification sanitized reports with exact runtime SHA and bounded verdicts.</p><a class="pl-intent-link" href="reports/">Open Security Assurance Reports</a></article>
<article class="pl-card"><span class="pl-card-kicker">How the Security Model and Assurance Evidence Fit Together</span><p>Threat model, assurance definition, and exact qualification evidence.</p><a class="pl-intent-link" href="model-and-evidence/">Open How the Security Model and Assurance Evidence Fit Together</a></article>
<article class="pl-card"><span class="pl-card-kicker">Scenario Walkthroughs</span><p>Trace AP-01, AP-02, AP-06, and AP-11 from model to evidence.</p><a class="pl-intent-link" href="scenario-walkthroughs/">Open Scenario Walkthroughs</a></article>
<article class="pl-card"><span class="pl-card-kicker">STRIDE: Model vs Qualification Evidence</span><p>STRIDE categories beside executed evidence; no security score.</p><a class="pl-intent-link" href="stride-evidence/">Open STRIDE: Model vs Qualification Evidence</a></article>
<article class="pl-card"><span class="pl-card-kicker">OWASP: Model vs Qualification Evidence</span><p>Secondary OWASP lens with explicit uncertainty.</p><a class="pl-intent-link" href="owasp-evidence/">Open OWASP: Model vs Qualification Evidence</a></article>
<article class="pl-card"><span class="pl-card-kicker">Model ↔ Assurance Evidence</span><p>AP, control, scenario, suite, finding, SHA, and human-review joins.</p><a class="pl-intent-link" href="model-assurance-evidence/">Open Model ↔ Assurance Evidence</a></article>
<article class="pl-card"><span class="pl-card-kicker">Scenario → Model</span><p>Registered scenarios and exact model relationships.</p><a class="pl-intent-link" href="scenario-model/">Open Scenario → Model</a></article>
<article class="pl-card"><span class="pl-card-kicker">How to Read Security Documentation</span><p>Question-to-destination guide and truth-boundary vocabulary.</p><a class="pl-intent-link" href="how-to-read/">Open How to Read Security Documentation</a></article>
<article class="pl-card"><span class="pl-card-kicker">Threat Model</span><p>Canonical threats, paths, controls, assets, and boundaries.</p><a class="pl-intent-link" href="../../threat-model/">Open Threat Model</a></article>
<article class="pl-card"><span class="pl-card-kicker">Security Atlas</span><p>Static model catalog; modeled, not live traffic.</p><a class="pl-intent-link" href="../../threat-model/catalog/">Open Security Atlas</a></article>
<article class="pl-card"><span class="pl-card-kicker">Trust Boundaries</span><p>Architecture-owned trust boundaries.</p><a class="pl-intent-link" href="../../../production/architecture/network-boundaries/">Open Trust Boundaries</a></article>
<article class="pl-card"><span class="pl-card-kicker">Security Controls</span><p>Canonical control posture and implementation references.</p><a class="pl-intent-link" href="../../reference/security-controls/">Open Security Controls</a></article>
<article class="pl-card"><span class="pl-card-kicker">Assets &amp; Guardrails</span><p>Protected assets and model guardrails.</p><a class="pl-intent-link" href="../../threat-model/assets-guardrails/">Open Assets &amp; Guardrails</a></article>
<article class="pl-card"><span class="pl-card-kicker">Evidence &amp; Provenance</span><p>Evidence provenance and residual uncertainty.</p><a class="pl-intent-link" href="../../threat-model/evidence/">Open Evidence &amp; Provenance</a></article>
<article class="pl-card"><span class="pl-card-kicker">Supply Chain</span><p>Normalized supply-chain evidence.</p><a class="pl-intent-link" href="../../reference/supply-chain/">Open Supply Chain</a></article>
<article class="pl-card"><span class="pl-card-kicker">Human Review</span><p>Residual risk and human-governed assurance decisions.</p><a class="pl-intent-link" href="../../threat-model/evidence/">Open Human Review</a></article>
</div>

## Authority

Canonical threat, scenario, suite, tool, architecture, and per-qualification report sources retain authority. This hub is a deterministic correlation/navigation projection.
