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

Status: **comparable**. From **lite-2026.08.12.2** to **lite-2026.08.19.2**. Repository HEAD is never substituted for a release.

| Dimension | Classification | From digest | To digest |
| --- | --- | --- | --- |
| git-source | changed | 9eb5181b543cd86feef2045749141e6f56a4228fb78ba32b2b1583943fd7deb1 | e443d1cb54228f77f0b509318613ce5e04a5f68b1fbf3748e033ba099f54419e |
| openapi | non-breaking | ca46065e6f046019e9141b5134306525d375b6f9d675a678e21b3c8697714c8a | 2a227b325ebecd2c420e49b26d0951a09ca3a4105b114661be0340f5e8f6cbd2 |
| asyncapi-events | changed | 8a51bc94d741a923406fede9abef161821c06d4094ebf0c4de6bc8b8db157020 | 0be55ad04175cd1c464f9a0807cda20a754bbd00b2f71ef08a2adab29c5bda0b |
| sqlite-schema-migrations | not-comparable | — | — |
| architecture | architecture-drift | 4ab392c6d2b5e56adfce730a97bdceed8a1b882b9800aceb0f1415a929c8e0cc | d98afd995a4cc5f0c1537cc43261cf454fc76fa1919d8cd1520ca37e597703ce |
| trust-boundaries | architecture-drift | 3fa8d34f8ac8a8cf7881ed8b57ca19dc697c0c26fc6af0dde1de779e7fb83562 | 26562b8a411e389ef004af273f095839fe91069dcdbe482f8424bc247bad7fbd |
| capabilities | changed | a8402a2158e5933f0500bc6dde5b94fd6465de37265afb03668cd84005e55f6e | e9ffb05ac6f4e2ed99ffa2e79744732afe87eafaea353e9669acfeb70c2a66d7 |
| operational-health | changed | 4d1dbd6e336307cd772390e57ff72fea503f0330e2c7af7967b9831c7fe58f70 | 5432235467fc118fab21a5a02aaa902ba28b32a4176d1fb8df82ece791cecfd0 |
| runtime-topology | changed | 886ac403a924c53922beb6d4d4f138b3713f1bc6d8420762d568171ac36e9401 | 6326d529ba0afaa830b353fd42597d7a3fd107c23e18e74f29a847d4f14c1c0e |
| semantic-parity | changed | d0f15a8863af1c95e1fc011e8cf6d829d5f2aa5d3b416a38a750f6eadebeec8f | 3388e580dd9216d8ba60f23caf7560567cfc1f8335cbd740de3b04ead12ca477 |
| platform-capability-evidence | changed | bccb11f395cba51d248eea1852527ff04cd55b6290e9c93c0bd6dcc125c3ecf8 | 33b8a8565525949e576151eb733c402f9ce825b21bbbb35d5015608e16da6542 |
| reason-codes | changed | 252758a61fe828243776b889665cbbdacbe8314b84ab1b7f6c498a4cbe882ae4 | 8902ad00e878b270a0428a800de82579468ba3e8ff15db384977f4cc6a3f985c |
| task-inventory | changed | 7d228a36df349d8e7af2ff828af0f479bf868ee3c4c0ed36cc4498666a7cfcd7 | 221d112d95c8a938edd3ec233bd5555e244723733769dd5d32d189752ae74620 |
| security-controls | changed | e7b549c4d13ce2e11b2c43b08a7fc740d92240183d82082b6edb541532125f4f | b7c3648058436ba82bac5b08fa672bb212c86c5219d349d71ed089bb33181929 |
| threat-model | changed | c94973c98de476ea5296efc458be2db24f85cf6d361d4859a53f024a107381c4 | d82a41f26174ff07ac07fd713148bb42dbf01d81ca9e521d9c50ba1ae85f6093 |
| sbom | unchanged | 914cce33367e0d6811bd84bdde3a784d729ee452d97c2d21cf5355f15b97a65b | 914cce33367e0d6811bd84bdde3a784d729ee452d97c2d21cf5355f15b97a65b |
| dependency-versions | changed | 85f1690746e36929098cd5a5a8a9e43eab670d52ab9188fce8b4cca26361db0c | 846fb5ec48aae6845ae59498a6e8b2ac94e6ed2d84503f261abcf0ff1737092e |
| vulnerabilities | unchanged | 828704f68e7a2522ffd4cc9e979bb1a5c910d8c679c64069aee087b3cc733355 | 828704f68e7a2522ffd4cc9e979bb1a5c910d8c679c64069aee087b3cc733355 |
| licenses | unchanged | 3420cefa32d0a8c0591e1f776c319570db2588d92c81f829618df4a22e014a7a | 3420cefa32d0a8c0591e1f776c319570db2588d92c81f829618df4a22e014a7a |
| release-artifacts | unchanged | 29d63d2302114690d98d76776e0012ee51ed3fe7cdfaba1d5bbf4fe89baf8384 | 29d63d2302114690d98d76776e0012ee51ed3fe7cdfaba1d5bbf4fe89baf8384 |
| documentation-coverage | changed | 036be93d188847b32d3056f550b49c969d5342d170635674b7ed7980d6e102a5 | 8a3776528d59dd5a261833860e93003f5c6429622c9e5c81eb41bb863d93e615 |
| validation-coverage | changed | 428bc1d6bc4425adf0fa9b87592ebea9547681c5bae3bfdefc70fdd9ceef9732 | f17b6a8201fb6171190ec0bd0ef6a0bdc510cda3b7967665f6c45f69e0fa1600 |

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
