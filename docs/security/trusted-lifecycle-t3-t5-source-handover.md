# Trusted Lifecycle T3–T5 — source closure continuation

The SC1–SC7 continuation ledger at the end of this document supersedes earlier progress descriptions. Earlier sections remain as historical implementation context.

**Disposition: SOURCE INCOMPLETE / UNVALIDATED.** Draft PR #663. No tests, checks, builds, scans, qualification, canonical generation, CI inspection/remediation, production provisioning, release, deployment, merge or Server Phone actions were performed in the implementation session. GitHub may independently trigger its configured workflows; no results are claimed. Do not transfer baseline qualification to these changes.

## Baseline and ownership

- Repository: dexter-lab-ctrl/pocket-lab-lite
- Base: PR #662 merge, main 9bc53ce047c800be71cd76f1a37e79659af1ca4d
- Branch: feat/trusted-lifecycle-t3-t5
- Prior implementation head: f97b5fa70655c8870b62dc0ec2a842a382af5438
- Continuation source head before this handover: 2e46489d9f31ca51e221659238eb485f88bd6ff6
- Baseline migration 0063; new migrations 0064 and 0065 are authored, not applied.
- Existing release worker, FastAPI authorization, OPA, policy lifecycle and core supervisor remain owners. PR #661 recovery authority and PR #662 review-only standing grants must remain distinct from execution.
- T6/T7 remain deferred.

## Implemented source (not runtime-validated)

| Area | Source | Status and limit |
|---|---|---|
| Authenticated coordinated package | lite_release_package, release publishing workflow, release trust runtime/provenance | Optional exact signed manifest-bound source archive and independent attestation; no production installation. |
| Independent trusted time | lite_release_trusted_time | Pinned Ed25519 signed challenge client, monotonic RTT/uncertainty, durable floor; independent endpoint not implemented/provisioned; not NTS or Roughtime compliance. |
| T3 compatibility | lite_policy_compatibility, lite_policy_candidate_differential | Locally recognized unchanged bytes or strictly appended ASCII note-comment lines; bounded synthetic offline decision corpus. Arbitrary semantic changes remain unknown. |
| T3 runtime observation | lite_policy_runtime_evidence | Independent OPA raw module hashes, revision, registered template data and parameters; not independent native backend identity or proof of all loaded data. |
| T3 exact activation | lite_lifecycle_policy_execution, policy rules, policy source sync, core supervisor | Separate one-shot Owner passkey authorization, fixed local policy-reconciler service decision, exact candidate/source/revision/expiry/epoch binding, claim/recheck, stage/prove/switch/restart/finalize or rollback. Only the narrow note-evolution class and isolated qualification lane; production remains disabled. |
| T4 coordinated preflight | lite_release_coordinated_preflight | Authenticated source and dist.zip staged in private temporary location; rehash open descriptors, size limits, source/native/frontend digests; temporary online SQLite checkpoint and quick_check. Neither a durable recovery checkpoint nor a promotion authorization. |
| T4 migration ledger | lite_release_package | Recorded applied names/version/checksums compared against local and candidate inventories, append-only checks. |
| T4 synthetic rehearsal | lite_release_migration_rehearsal | Isolated in-memory schema construction and restricted candidate SQL with bounded pages/statements/deadline, integrity and ledger checks; no user data and no production compatibility claim. |
| T5 candidate review/consent | lite_capability_review, lite_lifecycle_candidate_consent, lifecycle authority, migration 0064 | Exact typed scope, signed metadata, accept-for-review/decline/defer/revoke, Owner passkey, expiry and scope/epoch fences. No executable rights from candidate review. |
| T5 specific execution authority | migration 0065, policy execution service | Independent one-shot policy operation grant, service claim and revocation. Not a general app/recovery/maintenance/software execution grant. |
| UI | TrustedLifecyclePanel, liteApi | Existing System Manage components, haptics and exact passkey workflow; distinct recorded evidence, candidate consent, isolated operation and revocation. No production activation button. |

## Explicit opt-ins

- GitHub variable POCKETLAB_COORDINATED_RELEASE_PUBLISHING=1 for optional coordinated source publishing.
- POCKETLAB_RELEASE_POLICY_DIFFERENTIAL=1 for bounded offline differential work during trusted review.
- POCKETLAB_RELEASE_COORDINATED_PREFLIGHT=1 for manual trusted coordinated preflight.
- POCKETLAB_RELEASE_MIGRATION_REHEARSAL=1 plus complete qualification context for synthetic migration rehearsal.
- POCKETLAB_RELEASE_POLICY_EXECUTION=1 plus complete qualification context and state, SQLite database and PM2_HOME contained under the isolated run root. An environment label alone is insufficient.
- Signed time configuration is separate from release/rotation roles, requires independent locally pinned public key and HTTPS challenge endpoint. No production values were provisioned.
- All new execution opt-ins remain off by default. They are not a production qualification decision.

## Outstanding source blockers (do not mark T3–T5 complete)

1. T3: extend the local compatibility contract beyond note-only evolution, with independently justified supported semantic change classes; complete all protected-action decision-envelope differential scenarios, race/fault/rollback qualification assets, full loaded data and native/backend identity convergence, and production enablement contract. The qualification-only activation path is not a production-ready general policy updater.
2. T4: retain the existing trust latch (trusted_promotion_not_qualified). The existing standalone backend_runtime_promotion.py uses separate signed promotion and recovery authorities and is bound to an older migration range. Connect the actual trusted release admission/claim to its external runtime owner without replacing or bypassing either authority, coordinate backend/PWA/policy/schema generations, durable checkpoint and transition journal, startup reconciliation, independently observed runtime identity, and preserve newer writes on recovery. No coordinated native/software cutover has been added. The preflight temporary checkpoint is not a rollback point.
3. T5: implement real local capability activation/decline/defer semantics and admission+claim enforcement for additional supported capabilities on their existing owners, including installation/activation separation and independently revocable scoped grants. A candidate consent record cannot authorize a worker. Preserve PR #661 assisted/automatic recovery fences; no automatic broadening based on package authenticity.
4. Complete remaining Q0–Q9 source scenario/fixture coverage and qualification scripts. Existing tests authored in this branch cover fragments of these paths; they do not establish full qualification.
5. The real publisher, independent time service, live Owner WebAuthn, actual policy activation/rollback, ARM64/Termux resource budgets, package size, UI behavior, migrations and runtime convergence are all unvalidated.

## Authored qualification entry points

Run only in a separate approved qualification session, after remaining source blockers are implemented. Use the repository-owned task names and exact candidate SHA. No task was executed here.

- task lite:lifecycle:t3-t5-package (includes source/package, time, candidate review and policy execution/migration safety fixtures)
- task lite:lifecycle:backend
- task lite:lifecycle:ui
- task lite:lifecycle:mocked
- task lite:lifecycle:qualification
- task lite:lifecycle:regression

New fixtures include tests/backend/test_lite_lifecycle_policy_execution.py and extensions to tests/backend/test_lite_lifecycle_candidate_review.py and src/lite/components/TrustedLifecyclePanel.test.jsx. Existing mock/Storybook/Playwright fixtures remain in the draft. In a separately authorized qualification session, review real service OPA claim, stale/revoked grants, source and policy drift, SQLite migration and restore fences, interruption and rollback, same-UID residual, offline trusted-time failure, mocked desktop/mobile and physical Android resource gates. Never regenerate evidence or mark gates passing without actual outputs.

## Review before qualification

This continuation intentionally chooses a narrow note-only local policy change contract, no publisher-declared arbitrary semantics, strict independent grant scopes, no synthetic production human identity, and fail-closed rather than speculative native cutover. These are conservative implementation decisions, not evidence that the original full requirement has been met.


## SC1–SC7 continuation ledger (source only)

- Starting head: `4e71cd52cb33fdfceaf0900e65fd8077a2e1a8cd`.
- Code-bearing head before this ledger: `4cbcd07a6003c76fd88b8863ed71e3dbba3c1d24`.
- Branch and draft PR unchanged; no main changes or merge.
- New migration: 0066, in addition to authored 0064–0065. Not applied here.
- No validation commands, runtime actions, CI inspection, release, provisioning or canonical regeneration were performed.

| Package | Source delivered | Disposition / remaining source |
|---|---|---|
| SC1 | Locally registered restrictive backup-location policy evolution, exact differential matching, reconstructed signed policy inventory, isolated OPA endpoint and registered stage-data proof | Partial: other compatible semantic classes, complete base-data and independent installed backend identity, complete execution corpus and production eligibility remain. |
| SC2 | Exact one-shot Owner release preparation, service claim and durable authenticated handoff; existing native controller commands; separately pinned promotion and recovery authority | Partial: runtime-oriented package refinement and live coordinated promotion owner integration remain. |
| SC3 | Dynamic contiguous migration contract, durable checkpoint/journal, WAL and interruption fences, private offline generation transaction, manual-recovery-required disposition on failure | Partial: actual live backend/PWA/OPA/SQLite generation switch, startup recovery and separately authorized runtime recovery transaction remain. Offline rehearsal is not live convergence. |
| SC4 | Versioned independently scoped policy activation and release preparation contracts, Owner consent, current grant/lease checks and revocation | Partial: optional candidate capability activation and broader app/maintenance owner admission/claim remain. Existing PR #661 fences and PR #662 review-only consent are not replaced. Unsupported actions remain non-delegable. |
| SC5 | Existing System Manage shared components and API wrappers expose preparation, pending, prepared, cutover claim, rehearsal and revocation; policy data and restrictive result presentation | Partial: live promotion/recovery and broader capability activation UI are not implemented. Component fixtures authored; responsive behavior unvalidated. |
| SC6 | Existing policy/clock/package/native migration fixtures extended, release preparation scope/tamper/role fixtures added, aggregate qualification task includes T3–T5 package tests | Partial: full Q0–Q9 coverage, real integrated owner and runtime fault injection, desktop/mobile E2E and physical resource qualification remain. |
| SC7 | This ledger and PR description reconcile delivered source, decisions and blockers | Handover recorded, NOT a source-complete or qualification-ready signoff. |

### Execution limits

The explicit `POCKETLAB_RELEASE_COORDINATED_EXECUTION=1` flag is default off and requires an isolated qualification context, contained state/database/PWA paths and explicit isolated loopback OPA endpoint. Existing `POCKETLAB_RELEASE_POLICY_EXECUTION` also remains default off. Neither is permission to execute against the Server Phone. A release preparation grant cannot authorize native cutover by itself. Native controller `prepare-coordinated` and `activate-coordinated` operate on an offline qualification workspace and require current grant binding, the authenticated handoff, and separately pinned signed promotion and recovery authority. The offline generation records `runtime_convergence=not_exercised`. Do not interpret it as installed software, a production rollback point, or independently observed runtime identity. Do not use legacy native promotion on a trust-latched installation.

### Qualification assets (authored, not executed)

In the future authorized qualification environment, use `task lite:lifecycle:t3-t5-package`, `task lite:lifecycle:qualification` and the existing lifecycle regression tasks. These are not comprehensive Q0–Q9 signoff and should not be run against live data. Before formal qualification, complete the remaining source items above and reconcile the original Q0–Q9 requirements with executable scenarios. Do not promote or activate solely from these source changes.

### Residual implementation risks

The new migrations, API/worker/supervisor integration, exact grant lifecycle, differential corpus, OPA manifest data observation, signed handoff, native controller, and UI have not been compiled or exercised. Integration and compatibility defects may remain, including migration, policy-format, lease, rollback and platform differences. The optional source archive still uses the existing tracked-tree packaging approach. Independent trusted-time service provisioning and live human WebAuthn remain unexercised. No new autonomous application or maintenance execution was enabled. These are intentional fail-closed limits, not completed requirements.


## Source closure continuation — independent follow-up (2026-11-27)

**SOURCE INCOMPLETE / UNVALIDATED.** This section supersedes the earlier ledger where indicated. Draft PR #663 remains the only target. No test, build, check, qualification, performance run, generated-doc regeneration, deployment, release, merge, Server Phone access or production activation was performed by this follow-up. GitHub may independently trigger configured workflows on commits.

Starting remote head: `c5969b82bf89cc240de5a23fb5d8cf3eee3ae752`.

### Authored source increments

- `b36c7572634a8b4cd8cf7e2fd87754f79712876a`: terminal offline grant authority rechecked within its write transaction; controller must honor failed disposition, retains blocked journal on claim/finalization failure; staged source file fsync; native promotion test file included in lifecycle package qualification.
- `912affbcd1c90b8d72e02c9dddf1f2b5c2a1f3be`: versioned `runtime-review-v1` scoped exact-Git-commit archive contract, optional release workflow, verifier and fixture coverage; inconsistent, Boolean, decreasing or out-of-range schema scopes rejected.
- `6daefbe62264c21fd9dbee1a351c5722db48ccf0`: publisher/verifier share a dependency-free profile, avoiding backend dependency imports in the PWA build job.
- `4322b603b13462ab2bdf1f6d15154e4d093fb8c4`: read-only restart journal inspection with bounds, missing/symlink/invalid journal refusal, explicit phase/status agreement and distinct offline rehearsal convergence.
- This ledger's commit: exact differential corpus completeness and real-human Owner preservation, synthetic and false-Owner-authority cases; safer failure/reconciliation language in System Manage and corresponding component fixture; additional malformed-journal fences.

### SC1–SC7 disposition after follow-up

| Package | Additional source | Remaining source blocker |
|---|---|---|
| SC1 | Restrictive differential refuses incomplete corpus, real Owner access loss, non-registered deny envelopes; more adversarial inputs | Independent installed and loaded backend identity, complete registered/base policy data proof and additional justified semantic classes (SC-R02/R08). |
| SC2 | Exact runtime-review package profile and schema scope fences | Live coordinated generation switch across backend/PWA/OPA/SQLite, independently verified installation inventory (SC-R01). The new profile is review-only, not a dependency-closed production install image (SC-R07). |
| SC3 | Recheck terminal authority, distinguish failed versus rehearsed result, hardened read-only journal reconciliation | Actual startup owner integration, writer quiescence, recoverable live switch and separately authorized runtime recovery preserving newer writes (SC-R03). |
| SC4 | Exact existing release-grant scope/expiry/revocation completion fences reinforced | No new app or maintenance execution capability. Local optional activation and actual domain-owner admission and claim enforcement remain source work (SC-R04). |
| SC5 | Historical rehearsal and failure/reconciliation copy based on prepared grant disposition | Live runtime convergence/recovery and broader capability controls require real source owners first (SC-R06). |
| SC6 | Native promotion suite connected; authored policy, package, grant, journal and UI fixtures | End-to-end and fault scenario harness coverage still incomplete (SC-R05). |
| SC7 | Updated this ledger and PR handover | No source-complete, qualification-ready or merge signoff. |

### Codex qualification sequence (original phase-level sequence recovered; exact original detailed scenario inventory unavailable)

Every phase is NOT RUN. Do not convert a fixture into a passing result, and do not start full qualification until P0 source blockers are resolved. Use exact remote head and isolated workspaces, not production state.

| Phase | Scope and required evidence | Available source / remaining work |
|---|---|---|
| Q0 | Resolve exact candidate, clean worktree, immutable artifact/input identities and isolation; independent signing/time authorities | Existing candidate prep and package contract; require reproducibility, profile dependency inventory, signature/provenance and size verification. |
| Q1 | T3 policy differential, real OPA modules/data, deny and allow envelope comparison, unauthorized/stale/revoked and rollback cases | `test_lite_lifecycle_candidate_review.py`, `test_lite_lifecycle_policy_execution.py`; missing complete loaded identity and real OPA activation/rollback qualification. |
| Q2 | T4 artifact integrity, migration ledger, checkpoint, coordinated cutover, failure at every journal boundary, no overwrite of newer writes | `test_lite_coordinated_release_package.py`, `test_lite_lifecycle_release_execution.py`, `test_lite_backend_runtime_promotion.py`; live coordinated owner missing. |
| Q3 | T5 optional scope, candidate consent vs activation, exact admission/claim and revocation; preserve existing recovery owners | Candidate review and release/policy execution tests; new domain owner paths still missing. |
| Q4 | Frontend desktop/mobile, light/dark, keyboard/accessibility, stale/degraded/role fences, no fake completion | `TrustedLifecyclePanel.test.jsx`, stories, `lite-trusted-lifecycle.spec.ts`; extend after actual live controls exist. |
| Q5 | Isolated runtime/security: current human passkey and separate executor, NATS worker claim, trusted time, restart/fault injection, tamper/replay denial | Existing focused lifecycle tasks and signed time fixtures; implement complete integrated scenario drivers before signoff. |
| Q6 | Android/Termux ARM64 qualification: realistic CPU/RAM/disk/battery/thermal bounds, timeouts, interruption, idle regression | Requires separately authorized isolated device environment and measured evidence; not executed against Server Phone. |
| Q7 | Canonical contracts, docs generation, repository gates, full regression as appropriate | Existing repo-owned tasks; execute only in later qualification session. |
| Q8 | Inspect exact-head CI, remediate actual failures, rerun applicable checks | No CI inspection or reruns performed. |
| Q9 | Reconcile requirement ledger to artifacts and actual evidence; review-ready decision | Keep draft until source and qualification gates are satisfied. No merge or deployment authorization. |

### Specific residual risks and decisions

The runtime-review archive deliberately excludes unrelated roots, uses Git archive of an exact commit and declares a new signed profile. It is not a complete native installer; v1 full-tree declarations remain reviewable, while clients without schema v2 support must fail closed. Archive contents, dependencies, byte reproducibility and budgets are unvalidated. The read-only restart journal inspector cannot independently establish runtime health, nor authorize recovery. Restrictive policy changes still use the pre-existing exact locally registered backup-location transformation; no speculative additional semantic rule was enabled. The failure UI is based only on recorded disposition and is not a live runtime recovery control. Do not treat any of these source edits as formal qualification.
