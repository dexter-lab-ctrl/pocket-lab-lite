---
title: "Release Evidence"
description: "Source/release/runtime/SBOM/provenance evidence without unsupported claims."
generated: true
audience: development
page_type: release
confidence: generated
---

# Release Evidence

## Summary

Release evidence keeps source, release artifacts, promoted runtime evidence, SBOM/security evidence and signatures as separate authorities. Missing evidence remains unobserved.

## Release evidence

### Identity

| Field | Value |
| --- | --- |
| Source commit | uncommitted |
| Tree | uncommitted |
| Exact tag | unobserved |
| Runtime baseline binding | lite-2026.08.12.2 |
| Migration level | unobserved |
| SBOM digest | a2b32890679e4e900936e44b764cefc49d54dab64a5a4861829ee40e3e6ceb33 |
| Security scan digest | 896d0046be0362258195ee5f44436c764ef1752bf62d5c99bd5edf74fc03fe0f |

### Artifacts

| Artifact | Status | SHA-256 |
| --- | --- | --- |
| dist.zip | observed-local-release-staging | a33d470458a2d4d394af644f652597f0d2e15773bc70b33b08d89bf3c6c4f24f |
| checksums.txt | unobserved | — |
| release_manifest | unobserved | — |

## Release delta

**no-comparable-verified-prior-release**. The multidimensional engine compares only a verified canonical prior release; otherwise every dimension fails closed as not-comparable.

## Compatibility

Android/Termux ARM64, ARM64 Ubuntu/proot, Ubuntu/WSL2 development. Runtime/agent/config compatibility is further constrained by the Upgrade & Migration projection when a comparable release exists.

## Validation outcomes

Canonical recorded validation only; this page does not poll GitHub Actions or runtime.

## Known limitations

derive from canonical limitations catalog. GitHub asset presence is never claimed without verified release evidence.

## Provenance

Cosign signing and SLSA-style provenance workflows are implemented but remain unobserved until explicitly run. No formal SLSA level is claimed.
