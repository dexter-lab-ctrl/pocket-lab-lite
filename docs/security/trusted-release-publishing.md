# Trusted release publishing (T1, source plus focused qualification)

The source and focused synthetic trust qualification for PR #662 are complete
at code-bearing candidate `eea0d2fa5d81affc120a14459673b1b74db60f88`.
Qualification did not publish a GitHub release or provision production signing
material. Protected publisher configuration, external attestation service
compatibility and real draft recovery remain explicit operational prerequisites.
The existing release-dist workflow now requires signed metadata and artifact
attestation for tagged/manual releases. Main source builds retain their normal
artifact flow. There is no fallback for missing signing configuration.

Before release readiness, configure independently approved public root JSON
(protected environment variable POCKETLAB_RELEASE_PUBLIC_ROOT), root version, and the
protected secret POCKETLAB_RELEASE_SIGNING_SEEDS (JSON array of base64 32-byte
Ed25519 seeds, enough distinct active keys to meet the root threshold). Configure the pocketlab-release-signing GitHub environment with required
reviewers, approved main/release-tag deployment restrictions, and environment-scoped
secrets (not repository-level signing secrets). This is a mandatory configuration
prerequisite; build jobs have read-only contents permission and scoped OIDC/attestation write permission to attest the archive, but no release signing secret. Prefer a separately protected signer/HSM in a future deployment. No
production secret has been created here. Do not merge into a release-enabled
environment before this configuration and workflow have been qualified.

The build job attests dist.zip; the protected publishing job verifies that build attestation before signing, then attests the signed envelope. Both use GitHub's artifact attestation action pinned to a full commit. A client must independently
verify both subjects and exact source digest/workflow. Signed metadata alone is
not proof of provenance. The schema range emitted by the publisher is deliberately
the exact current schema; broader migration claims require separate evidence.

References: https://github.com/actions/attest and
https://cli.github.com/manual/gh_attestation_verify.

The rotation role is separately provisioned: rotation_keys and rotation_threshold
must be disjoint from the release signing keys. To rotate, the administrator
independently authorizes the new root fingerprint and provides previous-root.json
and root-transition.dsse.json, signed by both the previous and next rotation
thresholds. Rotation without these independent role keys is blocked. A compromised
or expired old root threshold requires a separate Owner-governed offline recovery
procedure; it cannot be overridden by candidate metadata. Retained time high-water
also rejects a backward clock anchor after successful verification.

## Immutable publication and recovery

Metadata version is derived from the date-based release tag:
YYYYMMDD * 1000000 + sequence (sequence 1–999999). It is deterministic,
monotonic for ordered tags and fits a safe integer. Do not maintain an
independent metadata version variable. The workflow serializes publishing
across refs. It creates a draft, compares any existing assets byte-for-byte,
uploads missing assets only, and publishes after all expected assets match.
A newer already published signed tag blocks a downgrade. Published assets
are never replaced using clobber. Interrupted publication recovery requires
the exact original archived signed assets, not a newly rebuilt envelope; a
conflicting draft must be independently reviewed. Source review and the
selected native release/process-isolation regression bundle passed, but no
recovery or publication was executed in this session.

## Focused qualification disposition

The lifecycle backend and candidate-server suites passed 49 tests covering
signature separation, duplicate/untrusted/revoked keys, manifest and artifact
tampering, root rotation, durable floor replay, configuration latching,
trusted-time fallback rejection, restore fencing, exact candidate identity and
sanitized review-only UI fixtures. The selected release/process-isolation,
migration, restore and policy regression bundle passed 56 tests. These results
qualify the source contracts and deterministic isolated behavior; they do not
qualify a protected GitHub environment, real publisher credentials, external
attestation service compatibility, or an actual immutable release.

## Local trusted-time contract

The independently provisioned anchor file contains boot_id, boottime_ns and
utc (timezone-aware UTC). The nanosecond sample must come from CLOCK_BOOTTIME
on the same host and boot, not Python monotonic_ns. Old-format anchors fail
closed. No automatic trust/time bootstrap is performed. The default ten-minute
anchor window is intentionally conservative and must be qualified on supported
platforms. Use private state storage (0700 directory, owner-controlled regular
files). A missing or invalid configuration suspends the durable trust latch.
A new candidate must satisfy the configured trust roots and durable floors;
neither a browser nor a candidate can replace the initial root. Recovery from
a compromised or unavailable old rotation threshold remains out of band.
