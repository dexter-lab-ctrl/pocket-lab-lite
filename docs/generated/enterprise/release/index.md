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

Status: **no-comparable-verified-prior-release**. From **not-comparable** to **HEAD**.

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

derive from canonical limitations catalog. Local or GitHub release assets remain unobserved unless explicitly verified.

## Provenance

Cosign signing is explicit. SLSA-style provenance is generated without claiming a formal SLSA level.
