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

Status: **comparable**. From **lite-2026.08.19.2** to **lite-2026.08.29.1**. Repository HEAD is never substituted for a release.

| Dimension | Classification | From digest | To digest |
| --- | --- | --- | --- |
| git-source | changed | e443d1cb54228f77f0b509318613ce5e04a5f68b1fbf3748e033ba099f54419e | 2944163f0cc2e3cf66bddbfdcceff51b986bbc436b2cf786387fabcc0a72491a |
| openapi | non-breaking | 2a227b325ebecd2c420e49b26d0951a09ca3a4105b114661be0340f5e8f6cbd2 | 91a2bb77ed9f4946a549cb39c1ba35280365ac3be1a81ba0e7534ad6962aee5d |
| asyncapi-events | changed | 0be55ad04175cd1c464f9a0807cda20a754bbd00b2f71ef08a2adab29c5bda0b | 00da212b6e6d96bf330ce736d869128e7d82463072941dbc409593a180dde3f5 |
| sqlite-schema-migrations | not-comparable | — | — |
| architecture | architecture-drift | d98afd995a4cc5f0c1537cc43261cf454fc76fa1919d8cd1520ca37e597703ce | c2ebe92f92f3f84a648205a5f732d946aa0bcc6fb2c199392b3f2fac3b04725b |
| trust-boundaries | architecture-drift | 26562b8a411e389ef004af273f095839fe91069dcdbe482f8424bc247bad7fbd | 0f5f526dab5ad22248bf9f19c6b9bfedda72dd2598750c69c833bc34fb4e5875 |
| capabilities | changed | e9ffb05ac6f4e2ed99ffa2e79744732afe87eafaea353e9669acfeb70c2a66d7 | dd67ee359435915488a2d4217ec630ddffcf033aca75b4fe09d4a5406ee320bd |
| operational-health | changed | 5432235467fc118fab21a5a02aaa902ba28b32a4176d1fb8df82ece791cecfd0 | fdb3241b95bdc1b5451221bf24b8cff72a9ac7a44009c62972cdf6ae9fb4afe5 |
| runtime-topology | changed | 6326d529ba0afaa830b353fd42597d7a3fd107c23e18e74f29a847d4f14c1c0e | c9128ff8ec66a475616fa98cedbe5baf6dc4604defbf851619962192010803f4 |
| semantic-parity | unchanged | 3388e580dd9216d8ba60f23caf7560567cfc1f8335cbd740de3b04ead12ca477 | 3388e580dd9216d8ba60f23caf7560567cfc1f8335cbd740de3b04ead12ca477 |
| platform-capability-evidence | changed | 33b8a8565525949e576151eb733c402f9ce825b21bbbb35d5015608e16da6542 | 0e495cd87750d6ca91fcf06a2eb472a027b9fd25e9710904d5ba68498f95f71f |
| reason-codes | changed | 8902ad00e878b270a0428a800de82579468ba3e8ff15db384977f4cc6a3f985c | e174705eb6f0e213c4319d88b02392d66824b6280d76b4cbd3b463f180158445 |
| task-inventory | changed | 221d112d95c8a938edd3ec233bd5555e244723733769dd5d32d189752ae74620 | c10ac9e36add5a45f112d93faadd98fe345168828bdf5b5fe3d8806049f9112d |
| security-controls | changed | b7c3648058436ba82bac5b08fa672bb212c86c5219d349d71ed089bb33181929 | c4366040e9e680803c3dff44d217df0da32a6bdf7fb698e1d68b4129fc6dc8a7 |
| threat-model | changed | d82a41f26174ff07ac07fd713148bb42dbf01d81ca9e521d9c50ba1ae85f6093 | d2e0171409ef897940883c427a528206fcc4454a5a44845d878a864619235f65 |
| sbom | unchanged | 914cce33367e0d6811bd84bdde3a784d729ee452d97c2d21cf5355f15b97a65b | 914cce33367e0d6811bd84bdde3a784d729ee452d97c2d21cf5355f15b97a65b |
| dependency-versions | unchanged | 846fb5ec48aae6845ae59498a6e8b2ac94e6ed2d84503f261abcf0ff1737092e | 846fb5ec48aae6845ae59498a6e8b2ac94e6ed2d84503f261abcf0ff1737092e |
| vulnerabilities | unchanged | 828704f68e7a2522ffd4cc9e979bb1a5c910d8c679c64069aee087b3cc733355 | 828704f68e7a2522ffd4cc9e979bb1a5c910d8c679c64069aee087b3cc733355 |
| licenses | unchanged | 3420cefa32d0a8c0591e1f776c319570db2588d92c81f829618df4a22e014a7a | 3420cefa32d0a8c0591e1f776c319570db2588d92c81f829618df4a22e014a7a |
| release-artifacts | unchanged | 29d63d2302114690d98d76776e0012ee51ed3fe7cdfaba1d5bbf4fe89baf8384 | 29d63d2302114690d98d76776e0012ee51ed3fe7cdfaba1d5bbf4fe89baf8384 |
| documentation-coverage | changed | 8a3776528d59dd5a261833860e93003f5c6429622c9e5c81eb41bb863d93e615 | 663a4d8e805cd1086277aa9b459c84f98efb7eb2eadb0d5d38e07afd540d3305 |
| validation-coverage | changed | f17b6a8201fb6171190ec0bd0ef6a0bdc510cda3b7967665f6c45f69e0fa1600 | 7a93d18e849477fbdc2e046d45dff0e66d0b755c08d069135e30ec75375e08cd |

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
