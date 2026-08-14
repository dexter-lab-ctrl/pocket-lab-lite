---
title: "Promoted evidence → documentation"
description: "Projection-zone detail for promoted evidence flowing into static documentation without creating a new canonical trust boundary."
generated: true
audience: production
page_type: reference
confidence: generated
---

# Promoted evidence → documentation

<nav class="pl-threat-subnav" aria-label="Threat Model sections"><a class="pl-intent-link" href="../">Overview</a><a class="pl-intent-link" href="../architecture/">Architecture &amp; trust zones</a><a class="pl-intent-link" href="../stride/">STRIDE</a><a class="pl-intent-link" href="../attack-paths/">Attack paths</a><a class="pl-intent-link" href="../controls/">Controls</a><a class="pl-intent-link" href="../assets-guardrails/">Assets &amp; guardrails</a><a class="pl-intent-link" href="../evidence/">Evidence &amp; provenance</a><a class="pl-intent-link" href="../catalog/">Security Atlas catalog</a></nav>

<div class="pl-page-lede"><strong>Saved evidence enters documentation through an explicit projection zone.</strong><p>This page explains the visual evidence lane in the Security Architecture Poster. It is a presentation/evidence zone backed by canonical and promoted inputs; it is not promoted into a new canonical threat boundary.</p></div>

## Boundary

**Projection zone:** Promoted evidence → documentation. Canonical threat-boundary ownership remains unchanged.

## Assets

- SQLite state
- audit evidence
- backup metadata

## Actors & components

| Component | Role | Architecture component | Canonical boundary |
| --- | --- | --- | --- |
| Documentation | static evidence projection | completion-evidence | durable-state |
| Promoted evidence | sanitized canonical evidence | completion-evidence | durable-state |

## Controls

| Control | Description | Status |
| --- | --- | --- |
| CTRL-EVIDENCE-SANITIZE | Runtime/scanner evidence is sanitized before canonical documentation ingestion. | control-observed |
| CTRL-EXPLICIT-PROMOTION | Runtime and scanner evidence promotion is explicit; MkDocs does not capture or promote. | control-observed |

## Data flows

| Flow | From | To | Meaning |
| --- | --- | --- | --- |
| flow-16 | scanner-evidence | promoted-evidence | sanitize + promote |
| flow-17 | server-host | promoted-evidence | sanitized runtime evidence |
| flow-18 | promoted-evidence | documentation | deterministic projection |

## Evidence lineage

| Stage | Canonical/promoted source |
| --- | --- |
| Promoted runtime baseline | contracts/parity/runtime-verification-baseline.json |
| Domain operational health | contracts/generated/runtime/domain-operational-health.json |
| Dependency health | contracts/generated/documentation-intelligence/dependency-health.json |
| Normalized scanner/SBOM evidence | contracts/generated/supply-chain |
| Threat posture projection | contracts/generated/documentation-enterprise/threat-posture.json |
| Threat model diagram | docs/generated/assets/enterprise/threat-model.svg |

## Guardrails

- Documentation does not capture or poll live runtime.
- Raw scanner output does not become documentation truth.
- Runtime/scanner evidence must be sanitized and explicitly promoted before canonical documentation ingestion.

## Review status

Human review remains required for evidence adequacy, exploitability, residual risk and acceptance.
