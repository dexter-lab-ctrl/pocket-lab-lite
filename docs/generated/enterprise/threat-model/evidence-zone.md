---
title: "Promoted evidence → documentation"
description: "Projection-zone detail for promoted evidence flowing into static documentation without creating a new canonical trust boundary."
generated: true
audience: production
page_type: reference
confidence: generated
---

# Promoted evidence → documentation

<nav class="pl-threat-subnav" aria-label="Threat Model sections"><a class="pl-intent-link" href="../">Overview</a><a class="pl-intent-link" href="../architecture/">Architecture &amp; trust zones</a><a class="pl-intent-link" href="../stride/">STRIDE</a><a class="pl-intent-link" href="../attack-paths/">Attack paths</a><a class="pl-intent-link" href="../controls/">Controls</a><a class="pl-intent-link" href="../assets-guardrails/">Assets &amp; guardrails</a><a class="pl-intent-link" href="../evidence/">Evidence &amp; provenance</a><a class="pl-intent-link" href="../evidence-zone/">Promoted evidence → documentation</a><a class="pl-intent-link" href="../catalog/">Security Atlas catalog</a></nav>

<div class="pl-page-lede pl-threat-boundary-lede"><strong>Saved evidence enters documentation through an explicit projection zone.</strong><p>This lane uses the same review anatomy as canonical boundaries while remaining a presentation/evidence projection. It does not create a tenth canonical threat boundary or imply live monitoring.</p></div>

<div class="pl-threat-boundary-summary" aria-label="Threat Model detail summary"><article><span>Type</span><strong>Evidence projection zone</strong></article><article><span>Assets</span><strong>3</strong></article><article><span>Controls</span><strong>2</strong></article><article><span>Review</span><strong>Human review required</strong></article></div>

## Boundary

<div class="pl-threat-boundary-callout"><strong>Promoted evidence → documentation</strong><span>Presentation/evidence zone · canonical threat-boundary ownership unchanged</span></div>

## Assets

- SQLite state
- audit evidence
- backup metadata

## Actors

| Component | Role | Architecture component | Canonical boundary |
| --- | --- | --- | --- |
| Documentation | static evidence projection | completion-evidence | durable-state |
| Promoted evidence | sanitized canonical evidence | completion-evidence | durable-state |

## Entry points

- scanner-evidence → promoted-evidence — sanitize + promote
- server-host → promoted-evidence — sanitized runtime evidence

## Data flows

| Flow | From | To | Meaning |
| --- | --- | --- | --- |
| flow-16 | scanner-evidence | promoted-evidence | sanitize + promote |
| flow-17 | server-host | promoted-evidence | sanitized runtime evidence |
| flow-18 | promoted-evidence | documentation | deterministic projection |

## Allowed flows

- scanner-evidence → promoted-evidence — sanitize + promote
- server-host → promoted-evidence — sanitized runtime evidence
- promoted-evidence → documentation — deterministic projection

## Forbidden flows

- documentation generator → live runtime (documentation → server-host)
- raw scanner output → MkDocs (scanner-evidence → documentation)

## Threats

No canonical STRIDE threat is assigned directly to this projection zone because it is not a canonical threat boundary. Relevant threats remain owned by the canonical boundaries and controls that produce, sanitize, promote or consume the evidence.

## Controls

| Control | Description | Status |
| --- | --- | --- |
| CTRL-EVIDENCE-SANITIZE | Runtime/scanner evidence is sanitized before canonical documentation ingestion. | control-observed |
| CTRL-EXPLICIT-PROMOTION | Runtime and scanner evidence promotion is explicit; MkDocs does not capture or promote. | control-observed |

## Runtime evidence & provenance

Promoted runtime evidence and canonical provenance are shown together here because this page explains how saved evidence reaches documentation. The table is lineage information, not a live feed.

| Stage | Canonical/promoted source |
| --- | --- |
| Promoted runtime baseline | contracts/parity/runtime-verification-baseline.json |
| Domain operational health | contracts/generated/runtime/domain-operational-health.json |
| Dependency health | contracts/generated/documentation-intelligence/dependency-health.json |
| Normalized scanner/SBOM evidence | contracts/generated/supply-chain |
| Threat posture projection | contracts/generated/documentation-enterprise/threat-posture.json |
| Threat model diagram | docs/generated/assets/enterprise/threat-model.svg |

## Residual risk

No independent residual-risk score is assigned to this projection zone. Evidence adequacy, stale or missing observations, control effectiveness and acceptance remain human-review decisions owned by the canonical model.

## Guardrails

- Documentation does not capture or poll live runtime.
- Raw scanner output does not become documentation truth.
- Runtime/scanner evidence must be sanitized and explicitly promoted before canonical documentation ingestion.

## Review status

Human review remains required for evidence adequacy, exploitability, residual risk and acceptance.
