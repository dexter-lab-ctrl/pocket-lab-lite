# Trusted Lifecycle T3–T5: partial implementation and completion handover

**Disposition: SOURCE IMPLEMENTATION INCOMPLETE / UNVALIDATED.** This is a draft source increment, not end-to-end T3–T5, not a qualified update mechanism, and not a production activation request. No qualification commands, CI remediation, publisher credential setup, signed release, deployment, or merge have been performed by this implementation session.

## Source baseline

- Repository: dexter-lab-ctrl/pocket-lab-lite
- Base main / PR #662 merge: `9bc53ce047c800be71cd76f1a37e79659af1ca4d`
- PR #662 qualified feature head: `e47d03d7fa57337048f8981d162e47f47bb6d86c`
- PR #662 code-bearing candidate: `eea0d2fa5d81affc120a14459673b1b74db60f88`
- Feature branch: `feat/trusted-lifecycle-t3-t5`
- Current baseline schema: migration 0063; this increment adds no migration.

The existing foundation, source-closure, trusted publishing and production activation documents remain authoritative for their respective claims. Do not transfer earlier qualification evidence to this candidate.

## Implemented source increment

### T3 — policy candidate review

- `lite_release_package.inspect_source` binds exact policy module and migration bytes to signed inventories and the archive hash bound by the signed release-manifest digest. Non-Rego policy data in the source package is rejected because no authenticated data inventory exists yet.
- `lite_policy_compatibility.compare_source` uses the existing four registered repository modules. Identical inventory is only source equality. Changed bytes or unknown module sets require review.
- `differential_evidence` compares complete supplied decision objects; equality of finite samples is not arbitrary Rego equivalence. A real differential corpus/runner is not implemented.
- `lite_policy_runtime_evidence.observe` samples existing durable active/known-good revision, pointers and OPA's loopback metadata and policy list. It compares exact raw Rego hashes as a multiset, checks the durable snapshot again, and reports only historical module evidence. Loaded data, backend identity, race-free activation and runtime generation are not proved. A malformed, oversized or unavailable response is unknown.
- Existing policy-source guard, OPA authorization path, policy lifecycle and core supervisor activation ownership are unchanged.

### T4 — source delivery and trusted time

The existing DSSE/Ed25519 metadata format is retained. Optional manifest field `coordinated_source` contains schema_version 1, fixed artifact `pocketlab-lite-source.zip`, exact SHA-256 and source commit. The existing signed manifest digest binds this field. The optional archive is built by GitHub Actions using git archive of the exact source commit, and independently attested as another subject. Signing/publication and release review cross-check inventory and archive bytes. Legacy publications do not receive this asset automatically. Publishing opt-in is the repository variable `POCKETLAB_COORDINATED_RELEASE_PUBLISHING=1` and has not been configured.

The source archive is review-only, never extracted or installed. Limits: compressed 256 MiB, expanded 512 MiB, 12,000 entries, 64 MiB per member, 256 KiB per reviewed inventory member, existing release child deadline and minimum free-space check. Full tracked tree is large, so real archive fit, device storage/latency and a narrower future source-owned package need qualification. No claim of production performance or package suitability is made.

`migration_inventory_comparison` requires contiguous registered filenames and unchanged prior source entries, holds any appended migration for qualification and rejects altered applied-source entries. It does not independently prove actual applied SQLite migration digests or backward-compatible data behavior. No migration is executed.

`lite_release_trusted_time` adds an independent signed challenge mode, using a locally provisioned raw 32-byte Ed25519 public key at `release-trust/time-public-key.bin`, pinned SHA-256, explicit HTTPS URL, separate key from release and rotation roles, 256-bit fresh nonce, <=3 s CLOCK_BOOTTIME round trip and bounded uncertainty. It reuses the existing ten-minute same-boot anchor, trust configuration and durable time floor. The verifier accepts only a signed canonical response with schema_version, nonce, key_id, UTC timestamp and uncertainty_ms. Signature domain is the source-owned DOMAIN constant. Signed time is inspired by nonce-based trusted-time patterns; it is not NTS or Roughtime compliance. The independent service must be separately operated and qualified; HTTPS does not substitute for pinned signature. TLS failure, reboot without fresh evidence, stale or changed config, invalid response or offline state hold trusted admission. No wall-clock fallback is introduced. Default operator-anchor mode remains unchanged. No production endpoint/key is configured.

The existing release runtime still denies trusted promotion through its existing latch. No coordinated release transition or unattended installer has been implemented.

### T5 — capability review

`lite_capability_review.compare_capabilities` compares stable IDs, owner/domain, scope, constraints, risk, mutation, network, secret access, approval/qualification and contract versions using the existing Capability ceiling comparator. New capabilities require review, owner/domain changes require trust/ownership review, changed contract versions without expansion are unknown, narrower scopes are still only review evidence. Results are bounded to twenty rows, prioritized by impact; truncation is explicit. No new consent, grant, worker admission or capability activation route exists. The existing T0–T2 review grants cannot execute anything.

### UI and evidence

Existing release-worker lease and trust receipt/observation transaction remain the evidence owner. The existing authenticated lifecycle summary returns bounded owner-only candidate review facts from the latest verified observation, not a fresh live probe. The new CandidateReview component is inside the existing Updates & protection detail panel, using LiteActionRow, LiteTechnicalDetails and the existing detail-block geometry/semantic CSS. No new overlay, breakpoint, shell, theme color or motion dependency. It explicitly labels recorded evidence and unknown states. No activate/install/consent action is added. Storybook, component tests and a mocked desktop/mobile Playwright scenario are authored.

## Requirement and ownership ledger

| Phase | Source authored | Existing owner | Disposition |
|---|---|---|---|
| T3 authenticated candidate and inventory | lite_release_package, trust runtime | release review child | Source implemented / unvalidated; no executable staging |
| T3 structured compatibility | lite_policy_compatibility | existing policy contracts | Partial; no safe typed evolution/semantic proof |
| T3 differential decisions | differential_evidence | future existing policy analysis owner | Comparator only; no corpus execution |
| T3 independent observation | lite_policy_runtime_evidence | release review child, read-only OPA | Partial; modules only |
| T3 delegated activation, admission, revalidation and rollback | none | lite_policy_lifecycle, source sync, supervisor | Missing |
| T4 package delivery | workflow, publisher, source review | existing protected release publishing and review lease | Source implemented / unvalidated, default off |
| T4 secure time | lite_release_trusted_time | existing trust runtime/floor | Client source only; independent service qualification/provisioning missing |
| T4 migration comparison | lite_release_package | release review child | Source comparison only |
| T4 transition, installation, checkpoint, reconciliation, rollback | none | existing release worker, runtime supervisors, Recovery | Missing |
| T5 capability review | lite_capability_review | lifecycle authority projection | Source implemented / unvalidated |
| T5 consent, revocation and actual admission/claim enforcement | none | existing identity, OPA and execution owners | Missing |
| UI review | TrustedLifecyclePanel and mocks | existing System Manage / FastAPI | Partial; read-only |
| T6/T7 | no implementation | existing future governance contracts | Deferred |

## Security and remaining implementation gates

1. T3: define versioned locally enforced typed policy evolution and complete compatibility evidence (protected actions, requirements, approval, explicit deny, nondelegable actions, resource and target scope). Do not remove current repository-source consistency gate. Derive exact staged bytes and independently verify loaded module **and data** identities, backend identity, generation, active/known-good pointers, and rollback state.
2. Add purpose-specific executable delegation with real service actor provenance rather than fake humans. Existing policy revision and activation operation schema has required human FK fields. Introduce explicit service actor persistence, independent Owner grant references, exact revisions, epoch, expiry, revocation and single-flight fencing, and wire the actual supervisor and worker claim. Old review grants must remain review-only. Revalidate existing PR #661 authority without broadening it. Do not infer activation authority from an update preference.
3. T4: implement a durable coordinated transition using the existing release lease/worker. Authenticate each staged byte used for installation, checkpoint installed state and data, prove compatibility of real applied migrations, prevent concurrent mutation, retain installed state on deferral, implement restart-safe transition reconciliation and verified recovery without restoring over newer user writes. Independent native/backend/frontend/OPA/SQLite readiness proof must precede committed installed identity. No arbitrary script execution.
4. T5: implement exact per-capability review/consent and passkey step-up; independent scope and expiry; revocation, decline/defer, durable audit and backend enforcement at admission and claim across existing owners. A release cannot widen local authority, even if verified. Unknown impact remains held.
5. Complete desktop/mobile state UX, purposeful consent controls, recovery history and accessible guidance only when actual backend states exist. Add focused source, mocked and physical qualification assets for real transitions.
6. Preserve same-UID threat residual, publisher compromise threat, clock/attestation root trust, and PR #661/#662 authority and restore safeguards. Full TUF compliance is not claimed.

No additional activation flag is exposed because the executable paths are not present. Existing legacy trusted-promotion latch is intentionally unchanged. Do not merge or activate this increment.

## Qualification handover (not executed)

After missing source work is implemented on this branch, review the whole branch, update the exact-head ledger and author all missing adversarial/isolated transition tests before Q0–Q9. Follow the original qualification gates and existing repository-owned tasks; no gate may be skipped, weakened or recorded as passing without evidence.

Authored targeted assets:
- `tests/backend/test_lite_coordinated_release_package.py`
- `tests/backend/test_lite_release_trusted_time.py`
- `tests/backend/test_lite_lifecycle_candidate_review.py`
- `src/lite/components/TrustedLifecyclePanel.test.jsx`
- `src/lite/components/TrustedLifecyclePanel.stories.jsx`
- `src/mocks/handlers.js` candidate scenario
- `tests/e2e/lite-trusted-lifecycle.spec.ts` candidate scenario and Axe assertion

Existing Taskfile targets to use only during later qualification:
- `task lite:lifecycle:t3-t5-package` (new)
- `task lite:lifecycle:backend`
- `task lite:lifecycle:ui`
- `task lite:lifecycle:mocked`
- `task lite:lifecycle:qualification`
- `task lite:lifecycle:regression`

The focused tests do not cover complete T3/T4/T5 execution. Real publisher, independent trusted time, real WebAuthn, migration, interrupted install, revocation races, rollback, performance and physical Android qualification remain outstanding. Do not generate canonical artifacts or remediate CI in the source-only session. Later qualification must resolve source defects, regenerate canonical artifacts through their existing generators and record exact SHA and outputs. Separate owner approval is required for any production activation.
