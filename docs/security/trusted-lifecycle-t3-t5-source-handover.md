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
