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
| Runtime baseline binding | lite-2026.08.07.3 |
| Migration level | unobserved |
| SBOM digest | 42f6b79bf3bf0f55572b0c17145b3943f8dd2d576af217ebdc155524609fa461 |
| Security scan digest | 4c72fe899858b70b7757e6cada313f8c241fa42ee56a1329776d52cadbf7a6a2 |

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
