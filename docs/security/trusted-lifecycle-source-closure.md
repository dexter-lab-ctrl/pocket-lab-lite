# Trusted Lifecycle — SC0–SC6 source closure ledger

**Disposition:** source authored, not qualified. Starting candidate
`0587872810b63ebc76e26452e9bcbb2de1bb492d`; main baseline
`8fa96db378364891e645ed3e22f76218b3412da3` (PR #661).
Branch `feat/trusted-lifecycle-governance`, PR #662. The PR head is the
authoritative final candidate. No validation command, scan, release, merge,
runtime mutation, production key or environment provisioning was performed.

## SC0 — requirement reconciliation

IDs map to the original T0–T2 brief sections 7–25; UI and qualification
rows map to sections 26–36 and 45–54. All implemented rows are **unvalidated**.
Partial rows identify remaining coverage explicitly, not as passed gates.

| ID | Requirement / source | Disposition and qualification |
|---|---|---|
| TL-T0-001 | §7 dependencies and trust boundaries; foundations doc | Partial: domain references present; full dependency inventory and independent artifact observations remain to qualify. |
| TL-T0-002 | §8 decision architecture; lite_lifecycle_contract | Authored independent dimensions; no execution; qualify unknown/mixed inputs. |
| TL-T0-003 | §9 registry; lifecycle contract and existing operation/protected action registries | Authored descriptive references, not executable adapter enrollment; validate complete owner mapping. |
| TL-T0-004 | §10 impact; assess | Authored U0–U5/UX; prove no widening on unknown input. |
| TL-T0-005 | §11 layered authorization; lifecycle authority/delegation, existing OPA | Authored platform/Owner/policy/runtime constraints; full governed activation deferred. |
| TL-T0-006 | §12 identities; summary and contracts | Partial: prepared revision facts, explicit unknown for independent current loaded OPA/backend binary identity. |
| TL-T1-001 | §13 trust architecture; release_runtime and release_trust_runtime | Authored existing worker/lease, configured latch, private review; qualify failure isolation. |
| TL-T1-002 | §14 metadata/root; trust, root_rotation, configuration | Authored threshold and dual-root transition, durable latch; compromised old threshold recovery out of band. |
| TL-T1-003 | §15 manifest; prepare_trusted_release_candidate and contracts | Authored deterministic inventories and signed scope; qualify canonical bytes and completeness. |
| TL-T1-004 | §16 workflow; release-dist.yml, publish_trusted_release | Authored build attestation, protected signing, deterministic version, immutable draft publication. No external release was made. |
| TL-T1-005 | §17 verification; release trust runtime/provenance | Authored strict acquisition/digests/attestation, deadline, resource admission and private files; actual gh compatibility unvalidated. |
| TL-T1-006 | §18 rollback/expiry/offline; floor, CLOCK_BOOTTIME and cache | Authored durable floor, short same-boot anchor, historical-only offline evidence, restore fence; full TUF and independently rollback-resistant store not supplied. |
| TL-T2-001 | §19 profiles; authority, migrations | Authored Notify default, Security and Recommended preferences, managed read-only; no unattended execution. |
| TL-T2-002 | §20 boundary; authority epoch and scopes | Authored independent local purpose ceilings; general enterprise boundary deferred. |
| TL-T2-003 | §21 standing authorization; grant and scope records | Authored two independent stable review-only purposes, 30-day expiry and per-purpose supersession. |
| TL-T2-004 | §22 service authority; lifecycle delegation | Authored purpose contracts, no service credentials/dispatch. Qualify no human impersonation. |
| TL-T2-005 | §23 Owner/step-up/revoke; authority and router | Authored exact review digest, current policy/assurance fences, narrow revocation; full live passkey/OPA race coverage remains. |
| TL-T2-006 | §24 API and prepared state; summary, liteApi, revision sync | Authored SQLite prepared reads and revision invalidation; qualify auth, offline, lifecycle event races. |
| TL-T2-007 | §25 persistence/evidence; migrations 0056–0063, staged restore | Authored forward migrations, bounded audit and decision linkage; qualify full database upgrade/restore/concurrency. |
| TL-UI-001 | §§26–36 System Manage Updates & protection | Authored shared components, individual/all revoke, exact scope, historical/current trust, haptic disclosures; visual parity and accessibility remain unvalidated. |
| TL-Q-001 | §§45–51 tests/tasks | Authored focused backend/component/Storybook/mocked Playwright and aggregate task sources; full matrix, live platform and CI evidence incomplete. |
| TL-DOC-001 | §§52–54 documentation/ledger | Source docs and this ledger; detailed cross-PR token/geometry provenance not independently reconstructed. |

## SC1–SC6 implementation map

| Increment | Source owners | Remaining qualification |
|---|---|---|
| SC1 | release trust runtime/configuration/provenance/rotation and migrations | Symlink and replacement races, clock/reboot, revocation, gh versions, operator bootstrap |
| SC2 | release runtime/update process, release-dist workflow and producer/publisher scripts | Lease expiry, subprocess cleanup, public redirects, publication conflicts, archived asset recovery, resource budgets |
| SC3 | lifecycle authority/delegation/restore, database recovery, migrations | Current Owner and loaded policy races, independent grants, revocation, controlled restore |
| SC4 | contract registry, router, prepared summary and System Manage shared UI | Complete independent identity observations, query invalidation, responsive/theme/haptic parity |
| SC5 | existing lifecycle backend/component/mocked E2E files, Storybook, Taskfile | No tests run; expand uncovered adversarial and end-to-end cases during qualification |
| SC6 | this document, foundations, publishing documentation, PR #662 | Exact-head qualification evidence and final review |

## Reuse and provenance matrix

| Existing reference | Source reuse | Status |
|---|---|---|
| PR #606 shared components | src/lite/LiteUi.jsx: LiteActionRow, LiteButton, StateSurface, LiteTechnicalDetails | Source reuse; exact historical provenance not revalidated |
| PR #622 semantic tokens | existing shared component styles, no independent palette | Visual light/dark parity not measured |
| PR #623 shell geometry | existing LiteSystemHealth Manage destination and section/detail classes | Desktop/mobile geometry not measured |
| PR #636 spacing | existing Manage layout and shared row primitives | Apps spacing comparison pending |
| PR #640 feedback | existing LiteButton haptic and optional shared disclosure haptic | Device behavior pending |
| PR #661 recovery fences | existing recovery activation owner and production allowlist | No activation promotion introduced; regression pending |
| Existing release path | release_runtime, release_update_process, dist.zip and checksum contract | Existing regression suite authored previously; not run |
| Existing governance | current Owner/session, passkey assurance, OPA, prepared SQLite and revision events | Integrated in source; runtime parity pending |

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

## Qualification entry

Resolve the actual PR head before qualification. Review source and run
focused isolated tasks before broader gates:

- task lite:lifecycle:backend
- task lite:lifecycle:ui
- task lite:lifecycle:mocked
- task lite:lifecycle:qualification
- task lite:lifecycle:regression

Cover real passkey and OPA authorization, prepared reads, full migration
and restore with synthetic state, publisher test-only keys, provenance
tool availability, network and clock failure, bounded resource behavior,
responsive and accessibility parity, and existing PR #661 recovery
behavior. Do not provision production trust pins or secrets, publish a
release, or activate trusted promotion during synthetic qualification.
No qualification result is claimed here.
