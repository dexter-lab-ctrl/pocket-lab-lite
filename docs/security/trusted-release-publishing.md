# Trusted release publishing (T1, source only)
The existing release-dist workflow now requires signed metadata and artifact
attestation for tagged/manual releases. Main source builds retain their normal
artifact flow. There is no fallback for missing signing configuration.

Before release readiness, configure independently approved public root JSON
(repository variable POCKETLAB_RELEASE_PUBLIC_ROOT), root version, strictly
increasing POCKETLAB_RELEASE_METADATA_VERSION (including repairs), and the
protected secret POCKETLAB_RELEASE_SIGNING_SEEDS (JSON array of base64 32-byte
Ed25519 seeds, enough distinct active keys to meet the root threshold). Restrict
repository secret access and release workflow execution to reviewed protected
refs. Prefer a separately protected signer/HSM in a future deployment. No
production secret has been created here. Do not merge into a release-enabled
environment before this configuration and workflow have been qualified.

The workflow attests both dist.zip and the signed envelope using GitHub's
artifact attestation action pinned to a full commit. A client must independently
verify both subjects and exact source digest/workflow. Signed metadata alone is
not proof of provenance. The schema range emitted by the publisher is deliberately
the exact current schema; broader migration claims require separate evidence.

References: https://github.com/actions/attest and
https://cli.github.com/manual/gh_attestation_verify.
