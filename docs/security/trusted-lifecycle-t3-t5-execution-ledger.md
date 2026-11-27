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
