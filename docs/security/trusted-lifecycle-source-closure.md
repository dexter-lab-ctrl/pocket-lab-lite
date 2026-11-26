# Trusted Lifecycle — SC0–SC6 source closure ledger

**Disposition:** source remediation and focused qualification complete at the
code-bearing candidate `eea0d2fa5d81affc120a14459673b1b74db60f88`.
`main` baseline is `8fa96db378364891e645ed3e22f76218b3412da3`; branch
`feat/trusted-lifecycle-governance`, PR #662. The final documentation commit
may advance the PR head without changing this code-bearing identity. The
result is **qualified with explicit baseline-supported performance residuals**:
focused source, isolated runtime, mocked UI, exact-candidate physical System
qualification, restoration and documentation generation were executed. No
production release, merge, production key, or protected signing environment
was used.

## SC0 — requirement reconciliation

IDs map to the original T0–T2 brief sections 7–25; UI and qualification
rows map to sections 26–36 and 45–54. `PASS` below means the named focused
source or qualification evidence passed; it does not imply production release
signing, T3–T7 activation, or an unbounded security audit. Partial rows keep
independent runtime, publisher and live human-WebAuthn limits explicit.

| ID | Requirement / source | Disposition and qualification |
|---|---|---|
| TL-T0-001 | §7 dependencies and trust boundaries; foundations doc | **PASS (source):** edge-first ownership and trust boundaries reviewed; independent loaded-policy/backend-binary identity remains explicitly unknown in prepared reads. |
| TL-T0-002 | §8 decision architecture; lite_lifecycle_contract | **PASS:** `test_verified_signature_is_not_execution_or_provenance`, fail-closed cases, and candidate fixture checks preserve independent authenticity, provenance and execution dimensions. |
| TL-T0-003 | §9 registry; lifecycle contract and existing operation/protected action registries | **PASS:** descriptive registry test confirms references do not enroll executable adapters or dispatch. |
| TL-T0-004 | §10 impact; assess | **PASS:** scope expansion, unknown policy and restrictive impact cases are covered; unknown input does not widen authority. |
| TL-T0-005 | §11 layered authorization; lifecycle authority/delegation, existing OPA | **PASS:** delegation cannot override policy/runtime; PR #661 recovery activation fences remain intact and no activation path was added. |
| TL-T0-006 | §12 identities; summary and contracts | **PARTIAL / explicit unknown:** candidate manifest/header/meta identity is exact; independent current loaded OPA and backend-binary identity remains unavailable by contract. |
| TL-T1-001 | §13 trust architecture; release_runtime and release_trust_runtime | **PASS (focused):** lifecycle trust fixtures and release/process-isolation regression suites passed; no execution or extraction side effect was enabled. |
| TL-T1-002 | §14 metadata/root; trust, root_rotation, configuration | **PASS:** threshold, duplicate/untrusted/revoked key, root-rotation, durable-latch and missing-configuration cases passed in the lifecycle backend suite. |
| TL-T1-003 | §15 manifest; prepare_trusted_release_candidate and contracts | **PASS (focused):** canonical candidate identity, digest/manifest mismatch and sanitized exact-SHA candidate manifest cases passed. |
| TL-T1-004 | §16 workflow; release-dist.yml, publish_trusted_release | **PARTIAL:** workflow/source contracts were reviewed and no release was published; protected GitHub signing environment and real publication recovery were not exercised. |
| TL-T1-005 | §17 verification; release trust runtime/provenance | **PASS (synthetic focused):** artifact tamper, provenance separation, policy/registry mismatch, bounded candidate and private-fixture cases passed; external `gh`/attestation compatibility remains a production prerequisite. |
| TL-T1-006 | §18 rollback/expiry/offline; floor, CLOCK_BOOTTIME and cache | **PASS (focused):** durable floor replay, root/metadata expiry, no wall-clock fallback, trusted-time latch and restore-floor fencing passed; full TUF role hierarchy is not supplied. |
| TL-T2-001 | §19 profiles; authority, migrations | **PASS:** Notify, Security and Recommended preferences are review-only; managed/read-only and no-unattended-execution behavior passed in backend/UI fixtures. |
| TL-T2-002 | §20 boundary; authority epoch and scopes | **PASS (local boundary):** optional ceiling, restrictive impact, scope and revision fences passed; general enterprise boundary remains future scope. |
| TL-T2-003 | §21 standing authorization; grant and scope records | **PASS (review-only contract):** purpose-specific scope, supersession and revocation behavior is covered; live human WebAuthn confirmation was not used in Android qualification. |
| TL-T2-004 | §22 service authority; lifecycle delegation | **PASS:** delegation cannot impersonate a human or broaden its purpose; no reusable service credential or dispatch path was introduced. |
| TL-T2-005 | §23 Owner/step-up/revoke; authority and router | **PASS (focused):** Owner/revision/OPA narrowing and revocation fences passed; live protected passkey/OPA race coverage remains outside the synthetic browser fixture. |
| TL-T2-006 | §24 API and prepared state; summary, liteApi, revision sync | **PASS (focused):** prepared API/identity checks, exact candidate proxy safety, sanitized fixture summary, revision-safe UI behavior and no unsafe lifecycle writes passed. |
| TL-T2-007 | §25 persistence/evidence; migrations 0056–0063, staged restore | **PASS:** 56 regression tests, isolated schema migration/quick-check/FK/concurrency/rollback evidence, and restore epoch/floor/grant invalidation passed without touching the production phone database. |
| TL-UI-001 | §§26–36 System Manage Updates & protection | **PASS (focused):** 8 Vitest, 8 mocked desktop/mobile Playwright tests, four reviewed light/dark desktop/mobile snapshots, and 13 exact-candidate physical System interactions passed. |
| TL-Q-001 | §§45–51 tests/tasks | **PASS (focused, bounded):** backend 49, UI 8, mocked Playwright 8, regression 56, candidate-server 28; full seven-screen physical matrix was intentionally not run. |
| TL-DOC-001 | §§52–54 documentation/ledger | **PASS:** canonical docs/contracts were regenerated after qualification; this ledger records exact candidate, evidence classes and remaining prerequisites. |

## SC1–SC6 implementation map

| Increment | Source owners | Remaining qualification |
|---|---|---|
| SC1 | release trust runtime/configuration/provenance/rotation and migrations | **Closed for focused scope:** synthetic trust, latch, floor, time and rotation cases passed; full TUF/off-device rollback store and protected publisher remain out of scope. |
| SC2 | release runtime/update process, release-dist workflow and producer/publisher scripts | **Partially closed:** source/resource/lease/process-isolation regressions passed; no real signing environment, release publication or external attestation was triggered. |
| SC3 | lifecycle authority/delegation/restore, database recovery, migrations | **Closed for focused scope:** authority/restore/SQLite evidence passed; live human WebAuthn and independently loaded OPA identity remain explicit limits. |
| SC4 | contract registry, router, prepared summary and System Manage shared UI | **Closed for focused scope:** exact proxy identity, prepared fixture, responsive/theme UI and physical System lane passed. |
| SC5 | existing lifecycle backend/component/mocked E2E files, Storybook, Taskfile | **Closed for executed scope:** backend/UI/mocked/regression tasks and 13 physical interactions passed; Storybook and broad seven-screen physical matrix were not required for this PR. |
| SC6 | this document, foundations, publishing documentation, PR #662 | **Closed:** evidence and generated documentation are reconciled; exact-head CI and PR status remain finalization checks. |

## Reuse and provenance matrix

| Existing reference | Source reuse | Status |
|---|---|---|
| PR #606 shared components | src/lite/LiteUi.jsx: LiteActionRow, LiteButton, StateSurface, LiteTechnicalDetails | Reused and covered by focused UI/visual checks |
| PR #622 semantic tokens | existing shared component styles, no independent palette | Desktop/mobile light/dark mocked snapshots reviewed |
| PR #623 shell geometry | existing LiteSystemHealth Manage destination and section/detail classes | Mocked desktop/mobile and physical narrow viewport exercised |
| PR #636 spacing | existing Manage layout and shared row primitives | No unrelated Apps baseline changed; System snapshots reviewed |
| PR #640 feedback | existing LiteButton haptic and optional shared disclosure haptic | Source-preserved; physical lane used safe disclosures only |
| PR #661 recovery fences | existing recovery activation owner and production allowlist | No activation promotion introduced; isolated/runtime regression passed |
| Existing release path | release_runtime, release_update_process, dist.zip and checksum contract | Native-release/process-isolation regression bundle passed |
| Existing governance | current Owner/session, passkey assurance, OPA, prepared SQLite and revision events | Focused authority/SQLite checks passed; live human WebAuthn and independent loaded-policy observation remain explicit limits |

## Threats and operating decisions

The operator independently provisions the trust fingerprints and same-boot
clock anchor. Ten-minute CLOCK_BOOTTIME validity is deliberately conservative.
The review worker defaults to a 240-second total deadline, checks resource
admission and uses private bounded acquisition. The exact tagged version is
derived from the release tag, not an environment counter. Same-purpose
standing grants last 30 days; currently only two review-only purposes are
supported. Removing trust configuration suspends the latch. A controlled
restore preserves live high-water values and invalidates restored grants.
Arbitrary malicious same-UID code, external database replacement or
compromise of an old rotation threshold are not solved by SQLite alone.
No new installation, policy activation, app dispatch or unattended execution
is enabled. T3–T7 remain future, separately qualified increments.

## Qualification result

The exact feature candidate was qualified through the repository-owned
isolated backend/runtime path and the standard-user Windows Android Chrome CDP
path. The lifecycle backend and candidate-server suites passed 49 tests, the
component suite passed 8 Vitest tests, mocked desktop/mobile Playwright passed
8 tests, and the selected release/restore/migration/policy regression bundle
passed 56 tests. The candidate build passed with 2,272 modules. The API check
passed with the repository virtualenv. The physical System lane passed 13
safe interactions with exact manifest/response-header/page-meta identity and
no unsafe lifecycle writes.

The source-equivalent three-run System performance comparison retained the
existing thresholds and classifications: all nine interactions missed the
absolute target and hard gate on both feature and main samples, all were
`MIXED`, and no `APP_INCREMENTAL_COST` was established. The two isolated p95
delta observations did not establish a stable actionable PR-attributable
contribution. This is a baseline-supported residual, not an unconditional
performance pass. The broad seven-screen physical matrix was not executed.

The Server Phone was restored to main `8fa96db378364891e645ed3e22f76218b3412da3`.
Production SQLite quick-check and foreign-key checks passed, ten normal PM2
services were online, qualification processes were absent, and harness/test
auth/destructive flags were disabled. No production signing key, release,
merge, unattended install, policy activation or T3–T7 capability was used.
