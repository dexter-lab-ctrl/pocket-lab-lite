---
title: "Release Assurance"
description: "Independent release/runtime/artifact/supply-chain authorities with explicit evidence gaps."
generated: true
audience: development
page_type: release
confidence: generated
---

# Release Assurance

## Summary

<div class="pl-page-lede"><strong>Release identity, runtime binding, artifact integrity and evidence gaps—kept as independent authorities.</strong><p>Local working-tree state is informational and cannot erase a verified release identity. MkDocs never polls GitHub or runtime.</p></div>

<div class="pl-kpi-grid pl-release-kpis"><div class="pl-fact"><span>Assurance status</span><strong>verified-with-evidence-gaps</strong></div><div class="pl-fact"><span>Release identity</span><strong>lite-2026.08.12.2</strong></div><div class="pl-fact"><span>Runtime binding</span><strong>lite-2026.08.12.2</strong></div><div class="pl-fact"><span>Historical comparison</span><strong>baseline-only</strong></div></div>

## Release evidence

Release, runtime, supply-chain and local generation state are independent authorities. Missing evidence stays unobserved.

## Evidence authorities

| Authority | Status | Confidence | Value | Source |
| --- | --- | --- | --- | --- |
| Release authority | verified | release-promoted | {'tag': 'lite-2026.08.12.2', 'commit': 'a6e4abc37ee9cca62c27286c556607ff3e740561', 'tree': '51fd1137e45dfe160a551c6a2cc7c0d99e22e560'} | contracts/generated/releases/promoted-release-evidence.json |
| Runtime authority | promoted | runtime-promoted | {'release_tag': 'lite-2026.08.12.2', 'source_commit': 'a6e4abc37ee9cca62c27286c556607ff3e740561'} | contracts/parity/runtime-verification-baseline.json |
| Supply-chain authority | promoted | release-promoted | normalized canonical evidence present | contracts/generated/supply-chain |
| Local repository authority | observed | local-observation | {'source_commit': 'uncommitted', 'tree': 'uncommitted'} | git/source environment |

## Assurance matrix

| Dimension | Status | Evidence |
| --- | --- | --- |
| source-identity | verified | release tag ↔ commit ↔ tree |
| artifact-integrity | verified | 3/3 promoted release assets have verified digest evidence |
| runtime-binding | verified | promoted runtime baseline ↔ release authority |
| operational-health | degraded | {'degraded': 2, 'healthy': 3, 'unvalidated': 2} |
| semantic-parity | observed | {'needs-review': 2, 'partial': 2, 'verified': 3} |
| security-evidence | promoted | normalized scanner/security evidence |
| sbom | verified | CycloneDX release SBOM |
| provenance | unobserved | unobserved |
| signatures | unobserved | unobserved-until-explicit-sign-command |
| migration-evidence | unobserved | repository migration inventory |
| historical-delta | observed | baseline-only |

## Artifact evidence

| Artifact | Release presence | Integrity | Verification detail | Binding | Local staging |
| --- | --- | --- | --- | --- | --- |
| dist.zip | verified | verified | SHA-256 verified against checksums.txt and GitHub asset digest where provided | verified | observed |
| checksums.txt | verified | verified | parsed and used to verify dist.zip; GitHub asset digest verified where provided | verified | observed |
| pocketlab-lite-release.json | verified | verified | JSON parsed and tag + source commit bound; GitHub asset digest verified where provided | verified | unobserved |

## Release delta

**Initial canonical comparison baseline.** Historical release-to-release comparison is intentionally unavailable until a second qualified release is promoted.

## Evidence gaps

| Dimension | Status | Why |
| --- | --- | --- |
| provenance | unobserved | unobserved |
| signatures | unobserved | unobserved-until-explicit-sign-command |
| migration-evidence | unobserved | repository migration inventory |

## Known limitations

| Area | Type | Limitation | Implementation | Health |
| --- | --- | --- | --- | --- |
| Apps | accepted_limitations | PhotoPrism is the currently cataloged runtime app; cross-app coverage grows from the same contract. | implemented | healthy |
| Apps | known_gaps | Application-owned media indexing is not a Pocket Lab parity authority. | implemented | healthy |
| Apps | unsupported_operations | Restore apply and update apply remain unavailable unless separately implemented and validated. | implemented | healthy |
| Devices | accepted_limitations | Heartbeat freshness can move during capture; comparison records the observed revision. | implemented | healthy |
| Devices | known_gaps | Per-device profile fields remain partial when the agent has not published them. | implemented | healthy |
| Devices | unsupported_operations | Healthy online devices are not removed without explicit confirmation. | implemented | healthy |
| Home | accepted_limitations | CPU, memory, and storage presentation may be rounded or unit-formatted. | implemented | degraded |
| Home | known_gaps | Live runtime semantic evidence remains explicit and release-bound. | implemented | degraded |
| Home | unsupported_operations | Home never executes system operations directly. | implemented | degraded |
| Identity | accepted_limitations | Credential values are never observable parity fields. | partial | unvalidated |
| Identity | accepted_limitations | Identity guard and protected server-host authority fields are planned and may remain unavailable until identity bootstrap services are implemented. | partial | unvalidated |
| Identity | known_gaps | The current tab is direct-rendered and has no dedicated selector layer. | partial | unvalidated |
| Identity | known_gaps | Identity guard and protected server-host projections are not fully implemented. | partial | unvalidated |
| Identity | unsupported_operations | Identity mismatch repair/rejoin must remain explicit and fail closed. | partial | unvalidated |
| Backup & Restore | accepted_limitations | Status labels intentionally use Lite-friendly wording instead of raw backend enums. | implemented | degraded |
| Backup & Restore | accepted_limitations | App restore apply remains explicitly unsupported where the repository reports it unavailable. | implemented | degraded |
| Backup & Restore | accepted_limitations | Historical restore previews are evidence only and never authorize a new restore. | implemented | degraded |
| Backup & Restore | known_gaps | Live Termux and live browser semantic capture remain explicit; missing capture is not drift. | implemented | degraded |
| Backup & Restore | unsupported_operations | Unsafe writes remain disabled while the recovery projection is stale. | implemented | degraded |
| Rules | accepted_limitations | The current product contract is a protection-mode policy surface, not a general arbitrary rule engine. | partial | unvalidated |
| Rules | known_gaps | Per-rule identity and execution history are planned, not present in the current API. | partial | unvalidated |
| Rules | unsupported_operations | Planned trigger/condition/action automation is not marked verified. | partial | unvalidated |
| Security | accepted_limitations | Raw scanner output and sensitive paths are intentionally excluded. | implemented | healthy |
| Security | known_gaps | A missing scanner is runtime-unavailable, not semantic drift. | implemented | healthy |
| Security | unsupported_operations | The browser never runs Lynis, Trivy, shell, PM2, or NATS commands. | implemented | healthy |

## Evidence lineage

<div class="pl-lineage"><div><strong>release authority → runtime baseline</strong><span><code>contracts/generated/releases/promoted-release-evidence.json</code></span></div><span aria-hidden="true">→</span><div><strong>runtime baseline → domain operational health</strong><span><code>contracts/parity/runtime-verification-baseline.json</code></span></div><span aria-hidden="true">→</span><div><strong>domain operational health → release impact/assurance</strong><span><code>contracts/generated/runtime/domain-operational-health.json</code></span></div><span aria-hidden="true">→</span><div><strong>release impact/assurance → MkDocs</strong><span><code>contracts/generated/documentation-enterprise/release-evidence.json</code></span></div></div>

## Compatibility

Android/Termux ARM64, ARM64 Ubuntu/proot, Ubuntu/WSL2 development.

## Validation outcomes

canonical validation evidence only; never polled live. This page does not poll GitHub Actions or runtime.

## Provenance

Cosign/signature and SLSA-style provenance remain evidence dimensions. No formal SLSA level is claimed unless separately promoted evidence supports it.
