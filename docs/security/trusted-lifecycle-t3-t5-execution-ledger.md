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
