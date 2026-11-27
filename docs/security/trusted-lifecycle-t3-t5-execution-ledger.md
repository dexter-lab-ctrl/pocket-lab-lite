# Trusted Lifecycle T3–T5 execution ledger

This is the bounded working ledger for the single-agent implementation and
qualification session. It records evidence observed in the current checkout;
an authored fixture, source inspection, or historical report is not a runtime
qualification result.

## Provenance at session start

| Item | Observed value | Status |
|---|---|---|
| Repository | `dexter-lab-ctrl/pocket-lab-lite` | VERIFIED |
| Base branch | `main` / `9bc53ce047c800be71cd76f1a37e79659af1ca4d` | VERIFIED |
| Feature branch | `feat/trusted-lifecycle-t3-t5` | VERIFIED |
| Starting feature HEAD | `a87a82cf619f390c5a22ac63e421416944b47165` | VERIFIED |
| PR | [#663](https://github.com/dexter-lab-ctrl/pocket-lab-lite/pull/663), draft, open, mergeable | VERIFIED |
| Starting worktree | Clean before implementation | VERIFIED |
| Production activation | Disabled and not authorized by this session | VERIFIED boundary |
| Server Phone | Not yet accessed in this session | NOT RUN |

## Current requirement ledger

| Requirement | Current implementation | Remaining gap | Planned qualification | Status |
|---|---|---|---|---|
| SC-R01 coordinated activation | Offline rehearsal remains available; a separately gated live owner now binds backend, PWA, OPA, SQLite, runtime health and committed terminal evidence | Live owner has not yet been exercised against an isolated running stack; newer-write/recovery execution remains pending | Q2/Q5/Q6 | IMPLEMENTED — NOT YET VALIDATED |
| SC-R02 independent identity | Migration 0067, `lite_runtime_identity`, and runtime-reconciler publication bind artifact/source inventory, process owners, loaded OPA module/data, frontend generation and migration ledger | Physical/runtime proof and residual same-UID limitations remain | Q1/Q2/Q5/Q6 | IMPLEMENTED — NOT YET VALIDATED |
| SC-R03 startup/recovery | Read-only journal reconciliation plus separately authorized live recovery owner and PWA/OPA pointer restoration path | Restart and recovery execution remain pending | Q2/Q5/Q6 | IMPLEMENTED — NOT YET VALIDATED |
| SC-R04 capability execution | Migration 0068 and `lite_lifecycle_capability_activation` add review, activation, expiry/revocation, exact binding, owner claim and scheduler enforcement | End-to-end Owner/passkey activation and worker claim execution remain pending | Q3/Q5 | IMPLEMENTED — NOT YET VALIDATED |
| SC-R05 executable qualification | Focused backend/package/identity/recovery tests, live-owner gate fixtures, UI unit tests and mocked desktop/mobile task execute | Full Q0–Q9 registry, live integrated driver and physical evidence remain | Q0–Q9 | PARTIALLY IMPLEMENTED |
| SC-R06 System Manage | Prepared identity/convergence/capability/recovery states and explicit completed-vs-rehearsal presentation are exposed from backend data | Physical System UI, complete visual matrix and live state exercise remain | Q4/Q6 | IMPLEMENTED — NOT YET VALIDATED |
| SC-R07 runtime packaging | Versioned `runtime-install-v1` profile and dependency manifest are bound and tested with archive limits and exact source inventory | Published exact candidate package and ARM64/Termux install execution remain | Q0/Q2/Q6 | IMPLEMENTED — NOT YET VALIDATED |
| SC-R08 policy compatibility | Unchanged, backup-location restrictive, and fresh-system-evidence restrictive classes compare full decision envelopes; loaded module/data hashes are projected | Full qualification corpus and physical policy activation remain | Q1/Q5 | IMPLEMENTED — NOT YET VALIDATED |

## SC1–SC7 source-closure matrix

| Requirement | Current source behavior and owner | Evidence / failure boundary | Status |
|---|---|---|---|
| SC1 T3 policy lifecycle | `lite_policy_candidate_differential`, OPA policy, `lite_policy_runtime_evidence`; compatibility remains registered and fail-closed | Exact differential result, loaded module/data identity, unknown semantics denied | IMPLEMENTED — NOT YET VALIDATED |
| SC2 trusted candidate/package | Release trust child and `runtime-install-v1` package profile bind source, manifest, dependencies and inventories | Archive bounds, path/special-file/credential exclusions and digest mismatch rejection | IMPLEMENTED — NOT YET VALIDATED |
| SC3 coordinated runtime | `coordinated_runtime_promotion` delegates to existing native/runtime owners under explicit qualification gate | Durable journal, SQLite checkpoint, PWA/OPA owner calls, health observations and committed terminal state | IMPLEMENTED — NOT YET VALIDATED |
| SC4 capability authority | `lite_lifecycle_capability_activation` and scheduler owner enforce exact capability/binding/claim | Candidate review cannot execute; missing identity, revocation, epoch or policy mismatch denies | IMPLEMENTED — NOT YET VALIDATED |
| SC5 recovery | Native journal reconciliation plus coordinated live recovery owner | Separate recovery signature, checkpoint digest, writer quiescence and newer-write denial | IMPLEMENTED — NOT YET VALIDATED |
| SC6 System Manage | `TrustedLifecyclePanel` renders prepared identity, capability, promotion, convergence and recovery distinctions | Mocked desktop/mobile interaction evidence; physical evidence not yet run | IMPLEMENTED — NOT YET VALIDATED |
| SC7 evidence/docs | This ledger and source handover preserve claim authority and category separation | Canonical generation intentionally deferred until device qualification | PARTIALLY IMPLEMENTED |

## Executed evidence

| Evidence | Result | Candidate | Notes |
|---|---|---|---|
| Focused lifecycle backend/package/promotion tests | 77 passed, 1 failed | `a87a82cf619f390c5a22ac63e421416944b47165` | Failure: replay assertion received `current backend pointer differs` before consumed-authority check. |
| Focused lifecycle after source closure edits | 158 passed, 1 warning | Working tree after `a87a82c` | Policy, candidate review, runtime identity, promotion, coordinated-owner gate, package and reconciler suites. |
| `task lite:lifecycle:qualification` | PASS: 21 backend, 81 package, 14 Vitest, 10 mocked Playwright | Current working tree | Mocked desktop/mobile only; no live/device claim. |
| `task lite:lifecycle:regression` | PASS: 56, 1 warning | Current working tree | Native release, process isolation, migrations, restore reconciliation and OPA readiness. |
| `npm run build` | PASS | Current working tree | Vite production build; existing chunk-size warning retained. |
| `opa check security/policies/opa/pocketlab` | PASS | Current working tree | Static OPA syntax/strict check. |
| PR CI `isolated-devpc-qualification` | PASS | PR merge SHA `b141f79779e567139a8c01e85496dc4ee19b4609` | CI merge ref, not feature-branch runtime proof. |
| PR CI `ui-performance-qualification` | PASS | PR merge SHA `b141f79779e567139a8c01e85496dc4ee19b4609` | Broad runner result; not System-only physical evidence. |
| PR CI `quick-and-docs` | FAIL | PR merge SHA `b141f79779e567139a8c01e85496dc4ee19b4609` | Docs check reports 19 undocumented reason codes. |
| Server Phone qualification | NOT RUN | — | Must consume a committed exact candidate and be restored to remote `main`. |
| DEV-PC isolated runtime | NOT RUN | — | Must consume a committed exact candidate; existing Photo Backup lane is runtime infrastructure evidence, not T3–T5 live cutover proof. |
| Server Phone qualification | NOT RUN | — | Must consume a committed exact candidate and be restored to remote `main`. |
| Windows Android CDP/System-only qualification | NOT RUN | — | Must use standard-user preflight and exact frontend/backend identity checks. |
| Canonical docs generation | DEFERRED | — | Run only after Q0–Q6 and final candidate freeze. |

## Session rules

- All source changes originate in this DEV-PC checkout.
- No subagents are used.
- No merge, release, production activation, or production deployment is
  authorized.
- Physical evidence is kept separate from source, mocked, CI, and offline
  rehearsal evidence.

## Final execution update — 2026-11-27

This section is the active disposition for the current candidate and
supersedes the earlier `NOT RUN` entries above. Historical entries are kept to
preserve provenance.

### Candidate and source closure

| Item | Evidence | Status |
|---|---|---|
| Starting main | `9bc53ce047c800be71cd76f1a37e79659af1ca4d` | VERIFIED |
| Starting feature head | `a87a82cf619f390c5a22ac63e421416944b47165` | VERIFIED |
| Code-bearing candidate | `1c9ee06818fb396e56ccd86ecfd99bab85c32a4d` | VERIFIED |
| Physical Android candidate | `1c9ee06818fb396e56ccd86ecfd99bab85c32a4d` | VERIFIED |
| Canonical documentation input | Current checkout at the code-bearing candidate plus generated-doc fixes | VERIFIED |
| Production activation/release/merge | Not performed or authorized | VERIFIED boundary |

SC-R01 through SC-R08 source paths are present and covered by focused tests,
but “implemented” is not promoted to “live production qualified.” The live
coordinated owner remains explicitly gated to an isolated qualification
environment and was not exercised against the ordinary Server Phone runtime.

| Requirement | Current closure evidence | Remaining limitation | Status |
|---|---|---|---|
| SC-R01 coordinated activation | `coordinated_runtime_promotion.py` binds candidate, grant, checkpoint, migration, PWA/OPA owners, health observations and terminal evidence; focused promotion and isolated runtime checks pass | Actual live multi-process cutover and recovery owner execution were not run | IMPLEMENTED — NOT YET VALIDATED |
| SC-R02 independent identity | Migration 0067, `lite_runtime_identity`, reconciler publication, process/source inventory and physical exact frontend markers | Ordinary installed backend identity was not changed; same-UID observation limits remain documented | IMPLEMENTED — NOT YET VALIDATED |
| SC-R03 startup/recovery | Journal bounds, interruption dispositions, explicit recovery authority, checkpoint/newer-write fences and focused recovery tests | Physical live restart/recovery was not run | IMPLEMENTED — NOT YET VALIDATED |
| SC-R04 capability activation | Migration 0068, review/activation/revoke/claim APIs, exact scope/owner/epoch/policy fencing and scheduler admission | No production capability was activated; real human Owner/passkey execution remains outside this run | IMPLEMENTED — NOT YET VALIDATED |
| SC-R05 executable qualification | Repository-owned lifecycle tasks, focused fixtures, isolated runtime runner and System-only Android runner executed | Full original detailed Q0–Q9 inventory was not recoverable; live coordinated fault matrix remains incomplete | PARTIALLY IMPLEMENTED |
| SC-R06 System Manage | Prepared backend state fields, truthful completed/rehearsal/recovery UI, mocked desktop/mobile, Storybook, accessibility and safe physical System interactions | Physical UI used an isolated candidate fixture, not a live production projection; full desktop/mobile visual matrix is not independently published | IMPLEMENTED — NOT YET VALIDATED |
| SC-R07 runtime packaging | Versioned `runtime-install-v1`, dependency profile, deterministic archive bounds/exclusions and package tests | No production release was published or installed; ARM64 install execution remains unvalidated | IMPLEMENTED — NOT YET VALIDATED |
| SC-R08 policy compatibility | Full-envelope differential comparison, registered restrictive classes, adversarial corpus and loaded module/data identity projection | Unknown semantic changes remain blocked; no production policy activation was performed | IMPLEMENTED — NOT YET VALIDATED |

### DEV-PC qualification

The exact-toolchain `task lite:check` completed successfully after selecting
the repository-required JDK 17.0.20.1 from the existing local cache. The
executed gate included: protected tool versions; Python and shell checks; 134
runtime tests; 171 backend tests; 652 Vitest tests in 103 files; OpenAPI and
contract checks; Storybook build with 20 representative renders; 52 mocked E2E
tests with 10 documented skips; accessibility; 74 documentation-browser
tests; redaction; Allure evidence generation; strict canonical documentation;
and the final repository evidence checks. Redocly reported 100 pre-existing
warnings while exiting successfully; they were not suppressed or relabeled.

Additional executed results:

- `task lite:lifecycle:qualification`: 21 backend, 81 package, 14 Vitest and
  10 mocked Playwright checks passed.
- `task lite:lifecycle:regression`: 56 checks passed.
- Focused promotion, release-execution and coordinated-owner tests: 36 passed.
- Isolated runtime candidate manifest `324e811a3a6744d4921f56d6`: PASS for
  candidate-bound FastAPI, worker, node-agent, supervisor, NATS/JetStream,
  synthetic auth/enrollment, SQLite, recovery and cleanup. This is isolated
  candidate evidence, not production runtime proof.
- `task lite:docs:generate`: PASS after physical qualification.
- `task lite:docs:check`: PASS with generated contracts, platform catalogs,
  runtime redaction, parity, knowledge, enterprise, architecture, SchemaSpy,
  diagrams, backend docs tests and strict MkDocs validation.

### Physical Android evidence

The sanitized evidence is committed under
`docs/security/evidence/trusted-lifecycle-t3-t5/1c9ee06818fb/`. The exact
qualifier output is `android-system-qualification.json`, run
`6712a817662a263ea9cfa4a9`, with three repetitions across nine System
interactions and 13 safe Trusted Lifecycle UI interactions. Candidate
manifest, page response and page meta source markers all matched the exact
candidate. The backend was an isolated candidate UI fixture and
`live_backend_summary` was false; this distinction is material.

The physical SQLite fixture advanced schema 42 to 69 with migrations 43–69,
`integrity_check=ok`, `quick_check=ok`, zero foreign-key errors, an empty
repeat application and no production database mutation. Qualification-owned
processes and temporary material were removed, and the synthetic session was
revoked.

The Android performance collector executed all three repetitions, but the
underlying performance contract did not pass: zero of nine interactions met
the absolute target or hard gate, with eight `MIXED`, one
`PLATFORM_DOMINATED`, zero `APP_INCREMENTAL_COST`, and zero `INCONCLUSIVE`
classifications. This is recorded as execution PASS with retained
`TARGET MISS`/`GATE MISS` residuals, not as performance compliance. No
unrelated screen optimization was performed.

### Q0–Q9 status

| Phase | Actual result | Evidence and disposition |
|---|---|---|
| Q0 | PARTIAL | Exact candidate, isolated artifact, synthetic authority and cleanup were exercised; independent human passkey/trusted-time service proof was not run. |
| Q1 | PASS — isolated | Differential corpus, full decision envelopes, loaded isolated OPA identity and fail-closed cases passed; production policy activation was not run. |
| Q2 | PARTIAL | Package, migration, checkpoint, journal and isolated runtime evidence passed; live coordinated backend/PWA/OPA/SQLite cutover was not run. |
| Q3 | PASS — isolated | Candidate-consent versus activation, scope, claim, revoke/expiry and replay fences passed in source/fixture qualification; no production capability was activated. |
| Q4 | PARTIAL | Mocked desktop/mobile, Storybook, accessibility and safe physical System interactions passed; complete visual matrix and live prepared projection remain limited. |
| Q5 | PASS — isolated | DEV-PC isolated NATS/worker/agent/supervisor/auth/runtime checks passed; physical Server Phone live runtime integration was not exercised. |
| Q6 | RESIDUAL | Standard-user Android CDP and System-only UI execution passed; performance target/gate misses remain, and full ARM64 Termux runtime/resource qualification is not claimed. |
| Q7 | PASS | Canonical generation, documentation check and exact-toolchain repository gate passed. |
| Q8 | NOT RUN | Requires the final pushed documentation/evidence candidate; prior run `45972277059` failed only on the then-undocumented reason-code set and is superseded. |
| Q9 | NOT RUN | Final remote HEAD, CI, phone restoration and PR report remain to be recorded after the final push. |

Q0–Q6 therefore do not receive an undifferentiated overall PASS. The active
qualification disposition is **PARTIAL with explicit residuals**: source and
isolated validation are strong, while live coordinated cutover and absolute
physical performance compliance remain unproven or failed.

### Exact-head CI and restoration update

The first documentation/evidence push was
`60633ad80e92e6ef2d89fb561111bfb600e1fd33` and triggered workflow run
[45980122454](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45980122454).
Its isolated DEV-PC job passed. Two failures were diagnosed precisely:

- `quick-and-docs` failed because the newly tracked SchemaSpy files expanded
  the CI-generated Codebase Map to 10,043,106 bytes, exceeding the existing
  10,000,000-byte contract. The local pre-push check had used the map before
  those generated files were tracked.
- `ui-performance-qualification` failed before qualification because
  Playwright dependency installation ran `apt` and the hosted runner received
  HTTP 403 from `packages.microsoft.com`; no repository test or performance
  assertion ran. This is an external CI image/repository availability
  blocker, not a source result and not a reason to weaken the dependency gate.

The Codebase Map generator was corrected from a 112-character bounded search
tail to 104 characters and regenerated against the now-tracked 5,801-file
tree. The map is now 9,994,340 bytes; its 12 focused tests and the full
`task lite:docs:check` pass locally. The correction is documentation-only and
does not alter the code-bearing candidate or physical evidence.

The Server Phone restoration then completed without source or ordinary
database edits:

- branch `main`, checkout and remote `main` both
  `9bc53ce047c800be71cd76f1a37e79659af1ca4d`, worktree status count `0`;
- guardian-led `task lite:runtime:resilience:phone:check` passed all topology,
  health, convergence, NATS, remote-access and recovery checks;
- after stabilization, all ten observed PM2 services were online with zero
  restarts in the snapshot; Caddy `/health`, `/ready` and
  `/api/lite/catalog` returned HTTP 200;
- the prepared runtime projection reported `state=stable`, `stable=true`,
  `summary=System running normally`, all services ready, remote access ready,
  and no runtime reason codes. The separate prepared `/api/lite/status`
  projection remained `degraded` with an empty degraded reason and two
  unknown device-summary rows; this pre-existing projection state is retained
  rather than relabeled as healthy.

Q8 is therefore `GATE MISS / EXTERNAL BLOCKER` for the first pushed SHA and
must be re-inspected on the corrected exact head. Q9 is `PARTIAL`: the phone
restoration is verified, while final corrected-head CI and PR presentation
remain pending.

### Corrected exact-head CI diagnosis and OpenAPI promotion — 2026-11-27

The corrected documentation head `39b5e9911e4e2ce30adf1e7fcc0787a0b7de71f2`
was inspected in [workflow 45988547157](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45988547157):

- [isolated-devpc-qualification](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45988547157/job/140470238651): PASS;
- [ui-performance-qualification](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45988547157/job/140470238016): PASS;
- [quick-and-docs](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45988547157/job/140470238396): GATE MISS in `tests/parity/test_api_contract_fences.py::test_openapi_baseline_promotion_is_explicit_and_hash_matched`.

The failure was a real explicit-promotion drift: the generated T3–T5 OpenAPI
contract had SHA-256 `582181f99288a3870935f77fa0289bf1a5cd6b91f63d92a8fc03f617ef6a6cf3`,
while the promoted baseline remained at `836ffc0f09712aede0ff821c8f18e47c6da3a03acd3e1bf2f2d05061045266e2`.
The required promotion was applied on DEV-PC: the baseline now exactly matches
the generated contract, the manifest records the old hash as `previous_sha256`,
the new hash as `promoted_sha256`, the exact `1c9ee068…` source revision, and
the T3–T5 rationale. `oasdiff` produced an empty breaking-change report;
`tests/parity/test_api_contract_fences.py` passed 16 tests and
`task lite:api:breaking-changes` passed. Canonical generation was rerun.

This corrective promotion is source/contract work and must be committed and
rechecked at a new exact head. Until that run completes, Q8 remains
`GATE MISS / CORRECTIVE PUSH PENDING` and Q9 remains `PARTIAL`.

### Final exact-head CI recheck — 2026-11-27

The promoted contract candidate
`9810349c455d50567692f6ce8ba326f377673dfe` was inspected in [workflow
45993578648](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45993578648):

- [isolated-devpc-qualification](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45993578648/job/140487253190): PASS;
- [quick-and-docs](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45993578648/job/140487253700): PASS;
- [ui-performance-qualification](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45993578648/job/140487253672): GATE MISS.

The UI job executed its complete performance contract: component tests and
build checks passed, while the existing broad mocked matrix retained one
failure in the Apps Manage interaction and one flaky Catalog sample (54
passed). The observed violations were `p95_frame_ms` at 33.3 ms, maximum
frame interval 33.4 ms, and gate smooth-frame ratio approximately 0.915–0.918.
The physical PR #663 qualification remains System-only; no System interaction
was omitted or threshold changed. The current failure is retained as a
renderer-sensitive broad-matrix `GATE MISS` outside the T3–T5 System-only
optimization scope, supported by the preceding exact-head UI pass and the
absence of runtime/performance-source changes in this contract-only commit.

Q8 is therefore `GATE MISS / PERFORMANCE RESIDUAL`, not PASS. Q9 remains
`PARTIAL`: exact-head source/documentation reconciliation and phone restoration
are verified, but the mandatory CI performance gate and live production
cutover/recovery proof remain unresolved. No threshold, assertion, or unrelated
screen was weakened to obtain a green result.

### Final documentation/evidence head and exact-head CI — 2026-11-27

The final documentation/evidence head at the time of this record is
`471d28c376f70259a60d0494e5be9f923a1429d7`. It contains no runtime-bearing
source change after the physically qualified candidate
`1c9ee06818fb396e56ccd86ecfd99bab85c32a4d`; the contract promotion and
documentation/evidence changes were checked for source-inventory equivalence.

The exact-head workflow
[45997861790](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45997861790)
for that head completed all required jobs successfully:

- [isolated-devpc-qualification](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45997861790/job/140501689508): PASS;
- [ui-performance-qualification](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45997861790/job/140501689880): PASS;
- [quick-and-docs](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45997861790/job/140501690062): PASS.

This rerun is CI evidence for the exact `471d28c…` head. It does not erase the
prior `45993578648` broad-matrix renderer-sensitive performance residual, and
it does not turn the physical System-only `TARGET MISS`/`GATE MISS` results
into compliance. No performance threshold, attribution rule, or assertion was
changed. Q8 is therefore `PASS` for exact-head CI, while Q9 remains `PARTIAL`
because live coordinated cutover/recovery and production activation were not
performed, and the physical performance residual remains disclosed.

### Consolidated T0–T5 qualification ledger — 2026-11-27

This section supersedes stale active dispositions above for the current PR
presentation. Historical entries remain preserved for provenance. It records
the consolidated work packages from the user-provided T0–T5 qualification
contract without treating source inspection or an offline rehearsal as live
runtime proof.

| Package | Original scope / owner | Existing evidence | Missing or limiting evidence | Status |
|---|---|---|---|---|
| C01 | TL-T0-006 / SC-R02; runtime reconciler, FastAPI identity projection, OPA observation | `lite_runtime_identity`, migration 0067, reconciler publication, isolated runtime and fail-closed identity fixtures | Ordinary installed backend artifact/process identity and same-UID observation limits are not independently established on the physical runtime | VALIDATED — ISOLATED |
| C02 | TL-T2 / SC-R01; human Owner WebAuthn and exact authority | Synthetic Owner boundary and rejection paths retained; no human ceremony or candidate-specific secure HTTPS ceremony was performed | Requires explicit human intervention and backend-confirmed human Owner state | BLOCKED |
| C03 | TL-T1 / trusted-time; independent signed-time owner | Signed nonce, pin, timestamp, monotonic RTT, expiry, replay and source-revision fixtures passed | No independently keyed disposable HTTPS service was exercised end to end; no production trust material provisioned | PARTIAL |
| C04 | TL-T1-003..005 / SC-R01, SC-R07; release/package owner | `runtime-install-v1` declaration, deterministic exact-commit archive, inventory, bounds, tamper and provenance fixtures passed | No real release publication or ARM64/Termux install was performed | VALIDATED — ISOLATED |
| C05 | SC-R01; coordinated promotion, native owner, release worker, PWA, OPA and SQLite | Default-disabled live-owner code path, offline rehearsal, focused controller tests and isolated runtime services | Actual multi-process backend/PWA/OPA/SQLite cutover and independently observed convergence were not run | NOT RUN — LIVE CUTOVER |
| C06 | PR #661 recovery / SC-R03; journal, supervisor and recovery owners | Bounded reconciliation, interruption dispositions, checkpoint and newer-write fences are covered by source and isolated fixtures | Live fault injection at cutover boundaries, restart ownership and separately authorized recovery were not run | NOT RUN — LIVE RECOVERY |
| C07 | SC-R04; registered capability owners and scheduler | Review-versus-activation, exact scope, owner, epoch, policy, lease, claim, expiry, revoke and replay fixtures passed | No production capability activation; broad T6 domains remain out of scope | VALIDATED — ISOLATED |
| C08 | SC-R07 / physical ARM64 and Termux; package/runtime owners | Server Phone consumer-only restoration and normal resilience checks passed; no source or ordinary DB mutation | Full exact-package install, ARM64 dependency closure, resource, battery and thermal matrix not run | PARTIAL |
| C09 | SC-R06; System Manage and prepared API projections | Desktop/mobile mocked UI, Storybook, accessibility and safe physical System interactions passed | Physical UI used an isolated fixture; actual candidate backend projections were not exercised | PARTIAL |
| C10 | PR #588/#589 / physical System performance | Three repetitions across nine System interactions; 0 absolute-target passes, 0 hard-gate passes, 8 MIXED, 1 PLATFORM_DOMINATED | Retained target/gate residual; no attributable PR #663 application regression established | RESIDUAL |
| C11 | SC-R05/SC7 / final regression, docs, CI and PR readiness | Existing focused suites, canonical docs/gates, phone restoration, and exact-head workflow 46002533515 passed | Consolidated live/human/device gates remain open; PR remains draft | PARTIAL |

#### Consolidated provenance

- Main/base: `9bc53ce047c800be71cd76f1a37e79659af1ca4d`.
- Starting feature reference: `a87a82cf619f390c5a22ac63e421416944b47165`.
- Physically qualified code-bearing candidate:
  `1c9ee06818fb396e56ccd86ecfd99bab85c32a4d`.
- Current documentation/evidence candidate at the time of this ledger:
  `e6e24fbb6876261fb0d251bbc7be75693acd5d25`.
- Exact-head workflow for the current candidate:
  [46002533515](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/46002533515);
  isolated DEV-PC, UI-performance and quick/docs jobs all passed.
- Server Phone was restored to remote `main` at the main SHA, with normal
  runtime resilience verified; no raw device serial is retained here.
- Production release, production activation, merge and auto-merge remain
  disabled and unauthorized.

#### Q0–Q9 consolidated disposition

| Phase | Disposition | Reason |
|---|---|---|
| Q0 | PARTIAL | Exact candidate, isolation and synthetic authority passed; human WebAuthn and independent trusted-time service were not run. |
| Q1 | PASS — ISOLATED | Policy differential, loaded isolated OPA identity and fail-closed cases passed. |
| Q2 | PARTIAL | Package, migration, journal and isolated runtime passed; live cutover was not run. |
| Q3 | PASS — ISOLATED | Capability consent/activation and claim fencing passed in isolated fixtures. |
| Q4 | PARTIAL | Mocked and safe physical System UI passed; live backend-projected visual evidence is incomplete. |
| Q5 | PASS — ISOLATED | Disposable FastAPI/worker/agent/supervisor/NATS/security checks passed. |
| Q6 | RESIDUAL | System-only Android execution completed; performance target/gate misses and full ARM64/resource coverage remain. |
| Q7 | PASS | Previously executed canonical generation, docs check and repository gate passed; no new generation is claimed for this incomplete consolidated run. |
| Q8 | PASS — CURRENT RECORDED HEAD | Workflow 46002533515 passed all required jobs for `e6e24fbb…`. |
| Q9 | PARTIAL | Evidence, PR presentation and phone restoration are recorded; mandatory live/human/device closures remain open. |

The consolidated session must not be marked merge-ready until C02, C03,
C05, C06, C08 and C09 are either executed successfully or explicitly
resolved by a separately authorized decision. The retained C10 performance
misses remain visible and are not relabeled as compliance.

### Consolidated qualification continuation — 2026-11-27, candidate `526df4643fd016afeab13c731342b222ca2f3b81`

This continuation started from the clean PR #663 head `f363b1f3c2f1de29e08ccb14e2a4148047e5f2bc` and added only a bounded trusted-time integration qualification asset plus task wiring. It did not alter production activation fences, release publication, ordinary device state, or the physical performance contract.

| Evidence item | Result | Exact evidence / limitation |
|---|---|---|
| Focused coordinator, promotion, identity, reconciler and trusted-time suites | PASS | 47 tests passed before the continuation change. |
| Disposable HTTPS signed-time client/server integration | PASS — ISOLATED | `tests/backend/test_lite_release_trusted_time_integration.py`; real loopback TLS, ephemeral independent Ed25519 signer, nonce-bound response, pinned key and boot-time RTT receipt. |
| T3–T5 package task after wiring | PASS — DEV-PC | `task lite:lifecycle:t3-t5-package`; 106 passed, 1 existing Starlette/httpx deprecation warning. |
| Trusted Lifecycle backend task | PASS — DEV-PC | `task lite:lifecycle:backend`; 21 passed, 1 existing Starlette/httpx deprecation warning. |
| Server Phone ordinary runtime baseline | PASS — READ ONLY | `main` and remote main `9bc53ce047c800be71cd76f1a37e79659af1ca4d`, clean worktree, ARM64, normal PM2 topology, FastAPI/OPA health, SQLite integrity `ok`. |
| Server Phone resilience check | PASS — READ ONLY | `task lite:runtime:resilience:phone:check`; guardian, PM2 ownership, service versions, runtime projections, NATS, remote access and PhotoPrism checks passed. |
| Repository Android read-only preflight | BLOCKED | The existing two-host lane reported the Server Phone baseline but could not establish its separately authorized private secondary transport; no candidate launch or production mutation was attempted. |
| Windows Android CDP preflight | PASS — PREREQUISITE ONLY | Standard-user PowerShell confirmed Chrome Protocol 1.3 on localhost; ADB showed two authorized transports for the same physical device and the existing `9222` forward. The open target was a new tab, not Pocket Lab Lite. No UAC elevation was used. |
| C02 human Owner WebAuthn | BLOCKED | No candidate-specific isolated HTTPS relying-party topology was available. Windows and phone Tailscale status did not expose a verified configured HTTPS FQDN; no human ceremony was requested, no credential was handled, and no main-runtime authentication was represented as candidate evidence. |
| C03 independent trusted-time service | VALIDATED — ISOLATED | The disposable HTTPS service proves the execution-relevant client/server path. Production trusted-time service provisioning remains deferred. |
| C05 live coordinated cutover | NOT RUN — LIVE OWNER PREREQUISITE | The live adapter remains default-disabled and requires an actual contained PM2/Caddy/OPA/NATS owner stack. The DEV-PC environment has no `pm2`, Caddy or `nats-server` binary, and the phone’s ordinary stack was not used as a candidate. Offline rehearsal remains explicitly non-live. |
| C06 live startup/recovery | NOT RUN — LIVE OWNER PREREQUISITE | No live cutover was run, so no live interruption/restart/recovery claim is made. Existing isolated journal, checkpoint and newer-write fixtures remain valid. |
| C08 ARM64 package/resource qualification | PARTIAL | Physical ordinary-runtime preservation and resilience passed; exact runtime-install package installation, candidate cutover, battery/thermal and full resource matrix remain unvalidated. |
| C09 backend-projected physical System UI | PARTIAL | Existing fixture-backed physical System evidence is retained; no new actual candidate backend projection was exercised. |
| C10 performance disposition | RESIDUAL | Existing nine-interaction, three-repetition System evidence remains 0/9 absolute-target passes, 0/9 hard-gate passes, 8 MIXED, 1 PLATFORM_DOMINATED, 0 APP_INCREMENTAL_COST. Thresholds and attribution rules were unchanged. |

The new source-bearing candidate is `526df4643fd016afeab13c731342b222ca2f3b81`; prior physical evidence for `1c9ee06818fb396e56ccd86ecfd99bab85c32a4d` is not transferred to this runtime-bearing candidate. Exact-head CI for `526df464…` must be inspected after GitHub completes. C02, C05, C06, C08 and C09 remain unresolved qualification gates; this continuation does not make PR #663 merge-ready.
