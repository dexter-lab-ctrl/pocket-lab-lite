---
title: "Documentation Platform"
description: "How Pocket Lab Lite documentation is generated, governed, validated, and secured."
generated: true
audience: development
page_type: overview
confidence: generated
---

# Documentation Platform

Pocket Lab Lite documentation is a deterministic engineering knowledge projection, not a control plane.

## Start with the system manual

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">Architecture</span><p>Understand sources, contracts, generators, promotion, validation, and MkDocs boundaries.</p><a class="pl-intent-link" href="architecture/">Open architecture</a></article>
<article class="pl-card"><span class="pl-card-kicker">Information Architecture</span><p>See audience, intent, primary navigation ownership, contextual links, and feature journeys.</p><a class="pl-intent-link" href="information-architecture/">Open IA</a></article>
<article class="pl-card"><span class="pl-card-kicker">Sources of truth</span><p>Know which authority wins when source, generated docs, runtime evidence, and human review differ.</p><a class="pl-intent-link" href="sources-of-truth/">Open sources</a></article>
<article class="pl-card"><span class="pl-card-kicker">Validation</span><p>Understand determinism, drift, navigation, redaction, browser, and security fences.</p><a class="pl-intent-link" href="validation-testing/">Open validation</a></article>
</div>

## Security boundary

MkDocs does not capture runtime, poll NATS, run scanners, promote evidence, execute shell commands, or access backend secrets.

## Generation lifecycle

`repository-owned source → canonical contracts → explicit capture → sanitization → explicit promotion → deterministic generators → knowledge/intelligence/architecture/enterprise projections → validation → MkDocs`
