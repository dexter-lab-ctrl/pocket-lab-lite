---
title: "Release"
description: "Release evidence, full multidimensional delta, supply-chain change, upgrade and provenance."
generated: true
audience: production
page_type: release
confidence: generated
---

# Release

## Summary

This page explains the current release evidence and change surface without conflating source HEAD, promoted runtime, GitHub publication, signatures or scanner evidence.

## Release evidence

Source/release/runtime identities remain separate. Current source commit: `uncommitted`; runtime binding: `lite-2026.08.12.2`.

## Release delta

Status: **initial-canonical-comparison-baseline**. From **not-comparable** to **lite-2026.08.12.2**. Repository HEAD is never substituted for a release.

| Dimension | Classification | From digest | To digest |
| --- | --- | --- | --- |
| git-source | not-comparable | — | — |
| openapi | not-comparable | — | — |
| asyncapi-events | not-comparable | — | — |
| sqlite-schema-migrations | not-comparable | — | — |
| architecture | not-comparable | — | — |
| trust-boundaries | not-comparable | — | — |
| capabilities | not-comparable | — | — |
| operational-health | not-comparable | — | — |
| runtime-topology | not-comparable | — | — |
| semantic-parity | not-comparable | — | — |
| platform-capability-evidence | not-comparable | — | — |
| reason-codes | not-comparable | — | — |
| task-inventory | not-comparable | — | — |
| security-controls | not-comparable | — | — |
| threat-model | not-comparable | — | — |
| sbom | not-comparable | — | — |
| dependency-versions | not-comparable | — | — |
| vulnerabilities | not-comparable | — | — |
| licenses | not-comparable | — | — |
| release-artifacts | not-comparable | — | — |
| documentation-coverage | not-comparable | — | — |
| validation-coverage | not-comparable | — | — |

## Compatibility

Supported targets: Android/Termux ARM64, ARM64 Ubuntu/proot, Ubuntu/WSL2 development. Upgrade compatibility remains evidence-bound and is generated only from a comparable release baseline.

## Validation outcomes

canonical validation evidence only; never polled live. No continuous CI/runtime polling occurs here.

## Supply-chain change

Supply-chain change is embedded in the Release Delta machine contract and rendered here from the same canonical comparison: dependencies, versions, vulnerabilities, licenses and upstream posture remain evidence-scoped and fail closed when historical scanner evidence is unavailable.

## Known limitations

[{'domain': 'apps', 'label': 'Apps', 'category': 'accepted_limitations', 'description': 'PhotoPrism is the currently cataloged runtime app; cross-app coverage grows from the same contract.', 'implementation_status': 'implemented', 'operational_health': 'healthy', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'apps', 'label': 'Apps', 'category': 'known_gaps', 'description': 'Application-owned media indexing is not a Pocket Lab parity authority.', 'implementation_status': 'implemented', 'operational_health': 'healthy', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'apps', 'label': 'Apps', 'category': 'unsupported_operations', 'description': 'Restore apply and update apply remain unavailable unless separately implemented and validated.', 'implementation_status': 'implemented', 'operational_health': 'healthy', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'devices', 'label': 'Devices', 'category': 'accepted_limitations', 'description': 'Heartbeat freshness can move during capture; comparison records the observed revision.', 'implementation_status': 'implemented', 'operational_health': 'healthy', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'devices', 'label': 'Devices', 'category': 'known_gaps', 'description': 'Per-device profile fields remain partial when the agent has not published them.', 'implementation_status': 'implemented', 'operational_health': 'healthy', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'devices', 'label': 'Devices', 'category': 'unsupported_operations', 'description': 'Healthy online devices are not removed without explicit confirmation.', 'implementation_status': 'implemented', 'operational_health': 'healthy', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'home', 'label': 'Home', 'category': 'accepted_limitations', 'description': 'CPU, memory, and storage presentation may be rounded or unit-formatted.', 'implementation_status': 'implemented', 'operational_health': 'degraded', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'home', 'label': 'Home', 'category': 'known_gaps', 'description': 'Live runtime semantic evidence remains explicit and release-bound.', 'implementation_status': 'implemented', 'operational_health': 'degraded', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'home', 'label': 'Home', 'category': 'unsupported_operations', 'description': 'Home never executes system operations directly.', 'implementation_status': 'implemented', 'operational_health': 'degraded', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'identity', 'label': 'Identity', 'category': 'accepted_limitations', 'description': 'Credential values are never observable parity fields.', 'implementation_status': 'partial', 'operational_health': 'unvalidated', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'identity', 'label': 'Identity', 'category': 'accepted_limitations', 'description': 'Identity guard and protected server-host authority fields are planned and may remain unavailable until identity bootstrap services are implemented.', 'implementation_status': 'partial', 'operational_health': 'unvalidated', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'identity', 'label': 'Identity', 'category': 'known_gaps', 'description': 'The current tab is direct-rendered and has no dedicated selector layer.', 'implementation_status': 'partial', 'operational_health': 'unvalidated', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'identity', 'label': 'Identity', 'category': 'known_gaps', 'description': 'Identity guard and protected server-host projections are not fully implemented.', 'implementation_status': 'partial', 'operational_health': 'unvalidated', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'identity', 'label': 'Identity', 'category': 'unsupported_operations', 'description': 'Identity mismatch repair/rejoin must remain explicit and fail closed.', 'implementation_status': 'partial', 'operational_health': 'unvalidated', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'recovery', 'label': 'Backup & Restore', 'category': 'accepted_limitations', 'description': 'Status labels intentionally use Lite-friendly wording instead of raw backend enums.', 'implementation_status': 'implemented', 'operational_health': 'degraded', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'recovery', 'label': 'Backup & Restore', 'category': 'accepted_limitations', 'description': 'App restore apply remains explicitly unsupported where the repository reports it unavailable.', 'implementation_status': 'implemented', 'operational_health': 'degraded', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'recovery', 'label': 'Backup & Restore', 'category': 'accepted_limitations', 'description': 'Historical restore previews are evidence only and never authorize a new restore.', 'implementation_status': 'implemented', 'operational_health': 'degraded', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'recovery', 'label': 'Backup & Restore', 'category': 'known_gaps', 'description': 'Live Termux and live browser semantic capture remain explicit; missing capture is not drift.', 'implementation_status': 'implemented', 'operational_health': 'degraded', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'recovery', 'label': 'Backup & Restore', 'category': 'unsupported_operations', 'description': 'Unsafe writes remain disabled while the recovery projection is stale.', 'implementation_status': 'implemented', 'operational_health': 'degraded', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'rules', 'label': 'Rules', 'category': 'accepted_limitations', 'description': 'The current product contract is a protection-mode policy surface, not a general arbitrary rule engine.', 'implementation_status': 'partial', 'operational_health': 'unvalidated', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'rules', 'label': 'Rules', 'category': 'known_gaps', 'description': 'Per-rule identity and execution history are planned, not present in the current API.', 'implementation_status': 'partial', 'operational_health': 'unvalidated', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'rules', 'label': 'Rules', 'category': 'unsupported_operations', 'description': 'Planned trigger/condition/action automation is not marked verified.', 'implementation_status': 'partial', 'operational_health': 'unvalidated', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'security', 'label': 'Security', 'category': 'accepted_limitations', 'description': 'Raw scanner output and sensitive paths are intentionally excluded.', 'implementation_status': 'implemented', 'operational_health': 'healthy', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'security', 'label': 'Security', 'category': 'known_gaps', 'description': 'A missing scanner is runtime-unavailable, not semantic drift.', 'implementation_status': 'implemented', 'operational_health': 'healthy', 'source': 'contracts/generated/parity/accepted-limitations.json'}, {'domain': 'security', 'label': 'Security', 'category': 'unsupported_operations', 'description': 'The browser never runs Lynis, Trivy, shell, PM2, or NATS commands.', 'implementation_status': 'implemented', 'operational_health': 'healthy', 'source': 'contracts/generated/parity/accepted-limitations.json'}]. Local or GitHub release assets remain unobserved unless explicitly verified.

## Provenance

Cosign signing is explicit. SLSA-style provenance is generated without claiming a formal SLSA level.
