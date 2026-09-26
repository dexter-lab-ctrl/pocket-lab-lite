# Security Assurance command catalog

This catalog records supported command forms and their ownership. Syntax is
derived from the current Taskfile, CLI parsers, FastAPI routers, launcher, and
tool manager. A placeholder such as `<run-id>` means a value returned by the
same server-owned workflow; it does not permit an arbitrary target or command.

The current CLI command inventory is: `keygen`, `principal-create`,
`principal-revoke`, `session-start`, `bootstrap`, `browser-bridge`, `session-status`,
`session-stop`, `status`, `profiles`, `verify-off`, `check`, `preflight`,
`policy-sync`, `fault`, `run`, `scenario`, `qualify`, `report`, and `compare`.

## Environment and registry

### SA-ENV-001
Status: **SUPPORTED**

- Purpose: record the candidate source revision and clean working-tree posture.
- Environment: `[DEV PC]` for source; `[SERVER PHONE]` for consumer evidence.
- Authority/prerequisites: repository access; no harness session.
- Mutating: no. Risk: PASSIVE. Safe for machine automation: yes.
- Exact commands: `git fetch origin --prune`, `git status --short --branch`,
  `git rev-parse HEAD`, `git rev-parse origin/main`, `git diff --check`.
- Expected output/exit: verified SHAs/status and exit `0`; a dirty or mismatched
  target blocks qualification.
- Evidence/failure/cleanup: record sanitized SHA/status; stop on mismatch;
  never repair a phone checkout from this command.
- Related playbook: [exact-head qualification](../security-assurance/18-exact-head-release-qualification.md).
- Implementation source: `AGENTS.md`

### SA-ENV-002
Status: **SUPPORTED**

- Purpose: inspect server-owned harness profiles and default-off posture.
- Environment: `[DEV PC]` or `[SERVER PHONE]` loopback.
- Authority/prerequisites: running Lite API; no session for the read checks.
- Mutating: no. Risk: PASSIVE. Safe for machine automation: yes.
- Exact commands: `task lite:harness:profiles`, `task lite:harness:status`,
  `task lite:harness:verify-off`.
- Expected output/exit: sanitized profile/status/verify-off result, exit `0`;
  unhealthy or enabled normal-runtime authority is a stop condition.
- Evidence/failure/cleanup: retain only bounded status; no cleanup beyond
  returning to the supported default-off launcher state.
- Related playbook: [cleanup/default-off](../security-assurance/16-cleanup-default-off.md).
- Implementation source: `tasks/Taskfile.lite.yml`

### SA-REG-001
Status: **SUPPORTED**

- Purpose: inspect fixed tools, suites, and capabilities without launching a run.
- Environment: `[DEV PC]` or approved client.
- Authority/prerequisites: repository and tool manager available.
- Mutating: no. Risk: PASSIVE. Safe for machine automation: yes.
- Exact command: `task lite:security:assurance:check`.
- Expected output/exit: registry summary, exit `0` when source registries are
  valid; malformed/unknown definitions fail closed.
- Evidence/failure/cleanup: record registry hashes and error; no runtime cleanup.
- Related playbook: [toolchain](../security-assurance/04-toolchain-installation.md).
- Implementation source: `scripts/dev/lite/security_assurance.py`

### SA-TOOLS-001
Status: **SUPPORTED**

- Purpose: install or promote the fixed DEV-PC toolchain outside Git.
- Environment: `[DEV PC]`; operator-owned managed directory.
- Authority/prerequisites: approved network/package/release workflow; no caller
  URL or package input.
- Mutating: yes, outside the repository. Risk: PASSIVE installer mutation.
  Safe for machine automation: only as the fixed task.
- Exact command: `task lite:security:assurance:tools:install`.
- Expected output/exit: bounded receipts and exit `0`; invalid receipt/install
  fails without accepting the tool.
- Evidence/failure/cleanup: preserve sanitized receipts; temporary archives are
  removed by the manager, but required caches may remain.
- Related playbook: [toolchain installation](../security-assurance/04-toolchain-installation.md).
- Implementation source: `scripts/dev/lite/security_assurance_toolchain.py`

### SA-TOOLS-002
Status: **SUPPORTED**

- Purpose: check every registered tool's qualified discovery and receipt.
- Environment: `[DEV PC]`.
- Authority/prerequisites: tool manager registry.
- Mutating: no. Risk: PASSIVE. Safe for machine automation: yes.
- Exact command: `task lite:security:assurance:tools:check`.
- Expected output/exit: each tool is `READY`, `NOT_APPLICABLE`, or `FAILED`;
  exit is non-zero when a required tool cannot be trusted.
- Evidence/failure/cleanup: record version/lane/receipt state; do not substitute
  an unregistered PATH binary.
- Related playbook: [tool matrix](tool-matrix.md).
- Implementation source: `scripts/dev/lite/security_assurance_toolchain.py`

### SA-TOOLS-003
Status: **SUPPORTED**

- Purpose: run the fixed static/live DEV-PC assurance lane for one suite.
- Environment: `[DEV PC]`, with the approved Server Phone tunnel for live tools.
- Authority/prerequisites: `tools:check` and approved route/target; no arbitrary
  command, argv, URL, host, port, template, or ruleset.
- Mutating: no intended application mutation. Risk: tool-resource bounded.
  Safe for machine automation: yes, through the fixed task.
- Exact commands: `task lite:security:assurance:tools:run SUITE=standard` and
  `task lite:security:assurance:tools:run SUITE=deep`.
- Expected output/exit: normalized tool results and sanitized evidence; timeout,
  missing, or resource stop remains truthful.
- Evidence/failure/cleanup: preserve tool receipts/findings; manager handles
  process-group cleanup and temporary files.
- Related playbook: [tool-specific](../security-assurance/12-tool-specific-playbooks.md).
- Implementation source: `scripts/dev/lite/security_assurance_toolchain.py`

## Identity and authentication

### SA-AUTH-001
Status: **SUPPORTED**

- Purpose: create disposable Ed25519 key material outside Git.
- Environment: `[APPROVED CLIENT]` or `[DEV PC]`.
- Authority/prerequisites: private path outside repository; parent directory
  protected; no server access required.
- Mutating: yes, client-local only. Risk: PASSIVE. Safe for machine automation: yes.
- Exact command: `task lite:harness:keygen KEY_FILE=<outside-repository-key-path>`.
- Expected output/exit: public key/fingerprint/path/mode only, exit `0`.
- Evidence/failure/cleanup: private bytes are never printed or persisted in
  reports; remove the disposable key after revocation.
- Related playbook: [bootstrap authentication](../security-assurance/05-harness-bootstrap-auth.md).
- Implementation source: `scripts/dev/lite/harness.py`

### SA-AUTH-002
Status: **SUPPORTED**

- Purpose: complete the operator-approved one-use key-bound bootstrap.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]` against direct loopback.
- Authority/prerequisites: qualification launcher approved the matching public
  key; key file is mode 0600.
- Mutating: yes, server authority creation. Risk: SAFE_ACTIVE. Safe for machine
  automation: yes, only with the approved fixed profile.
- Exact command: `task lite:harness:bootstrap PRINCIPAL_ID=<id> KEY_FILE=<path>`.
- Expected output/exit: sanitized principal/session metadata, exit `0`; grant,
  challenge, signature, runtime, and revision mismatch fail closed.
- Evidence/failure/cleanup: record principal/fingerprint/profile/expiry only;
  consume/revoke authority through the supported cleanup flow.
- Related playbook: [bootstrap authentication](../security-assurance/05-harness-bootstrap-auth.md).
- Implementation source: `scripts/dev/lite/harness.py`

### SA-AUTH-003
Status: **SUPPORTED**

- Purpose: use the retained manual public-principal registration path.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]` direct loopback.
- Authority/prerequisites: existing operator provisioning authorization; public
  key only; bounded profile/expiry.
- Mutating: yes, server principal state. Risk: SAFE_ACTIVE. Safe for machine
  automation: no unless an operator explicitly uses the fixed workflow.
- Exact command: `python3 scripts/dev/lite/harness.py principal-create --principal-id <id> --display-name <name> --key-file <path> --profile <profile>`.
- Expected output/exit: sanitized principal metadata; invalid profile/key/expiry
  is rejected.
- Evidence/failure/cleanup: revoke the principal after use; never report private
  key bytes or a provisioning credential.
- Related playbook: [authentication](../security-assurance/05-harness-bootstrap-auth.md).
- Implementation source: `scripts/dev/lite/harness.py`

### SA-AUTH-004
Status: **SUPPORTED**

- Purpose: revoke a principal through the CLI cleanup path.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]` direct loopback.
- Authority/prerequisites: supported provisioning authorization or current
  authenticated cleanup flow as implemented by the server.
- Mutating: yes. Risk: SAFE_ACTIVE. Safe for machine automation: only for the
  disposable principal selected by the workflow.
- Exact command: `python3 scripts/dev/lite/harness.py principal-revoke --principal-id <id>`.
- Expected output/exit: bounded revocation, exit `0` on completion.
- Evidence/failure/cleanup: verify active sessions are invalidated; retain only
  sanitized IDs.
- Related playbook: [cleanup/default-off](../security-assurance/16-cleanup-default-off.md).
- Implementation source: `scripts/dev/lite/harness.py`

### SA-AUTH-005
Status: **SUPPORTED**

- Purpose: obtain a normal short-lived signed session after registration.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]` direct loopback.
- Authority/prerequisites: registered public principal and private key; exact
  challenge payload; purpose/profile/target are server-bound.
- Mutating: yes, session state. Risk: SAFE_ACTIVE. Safe for machine automation: yes.
- Exact command: `task lite:harness:session:start PRINCIPAL_ID=<id> PROFILE=security-assurance-runner PURPOSE=security.assurance KEY_FILE=<path>`.
- Expected output/exit: sanitized session metadata and process-only token; old
  expired sessions do not block a replacement.
- Evidence/failure/cleanup: never persist the token; renew with a new challenge
  and revoke/expire sessions after qualification.
- Related playbook: [authentication lifecycle](../security-assurance/05-harness-bootstrap-auth.md).
- Implementation source: `scripts/dev/lite/harness.py`

### SA-AUTH-006
Status: **SUPPORTED**

- Purpose: inspect or stop a normal session through the CLI commands.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]` direct loopback.
- Authority/prerequisites: session ID and process-only session context where
  required.
- Mutating: status is no; stop is yes. Risk: SAFE_ACTIVE for stop. Safe for
  machine automation: only for owned disposable sessions.
- Exact commands: `python3 scripts/dev/lite/harness.py session-status --session-id <id>` and `python3 scripts/dev/lite/harness.py session-stop --session-id <id>`.
- Expected output/exit: sanitized lifecycle status or revocation; invalid/expired
  authority is denied.
- Evidence/failure/cleanup: record status only; do not put session tokens in
  continuity state or reports.
- Related playbook: [cleanup/default-off](../security-assurance/16-cleanup-default-off.md).
- Implementation source: `scripts/dev/lite/harness.py`

### SA-AUTH-007
Status: **SUPPORTED**

- Purpose: start key-bound qualification with explicit operator approval.
- Environment: `[SERVER PHONE]` consumer runtime, invoked by the operator.
- Authority/prerequisites: public key file only; fixed principal ID and profile
  `security-assurance-runner`; production/default-off gates intact.
- Mutating: yes, qualification runtime state. Risk: SAFE_ACTIVE. Safe for machine
  automation: no; operator approval is required.
- Exact task: `task lite:qualification:start:key-bound PRINCIPAL_ID=<id> PUBLIC_KEY_FILE=<public-key-path>`.
- Expected output/exit: launcher starts qualification and records bounded
  bootstrap approval; invalid flags fail closed.
- Evidence/failure/cleanup: verify no private key/token was passed; stop
  qualification and run `task lite:harness:verify-off` afterward.
- Related playbook: [getting started](../security-assurance/02-getting-started.md).
- Implementation source: `scripts/dev/lite/start-qualification.sh`

### SA-AUTH-008
Status: **SUPPORTED**

- Purpose: project a short-lived synthetic qualification-owner session into a
  constrained browser run for read-only UI performance qualification.
- Environment: `[DEV PC]` runner through the bounded Server Phone loopback
  tunnel; the backend must already be in explicit qualification mode.
- Authority/prerequisites: key-bound `qualification-owner` bootstrap, purpose
  `ui-performance-60fps`, target `local_server_host_only`, destructive and
  test-auth gates off; the bridge is created only after normal backend
  authorization.
- Mutating: yes, ephemeral bridge/session state only. Risk: SAFE_ACTIVE. Safe
  for machine automation: only through the fixed runner.
- Exact command: `python3 scripts/dev/lite/harness.py browser-bridge --session-token <process-only-session-token>`.
- Expected output/exit: sanitized bridge metadata; the reusable bridge value is
  held only by the runner process and is never written to browser storage,
  URLs, logs, or evidence.
- Evidence/failure/cleanup: browser requests remain same-origin and pass
  through Caddy/FastAPI; revoke the authenticated principal while the owned
  tunnel is still active, then verify the harness returns to default-off.
- Related playbook: [harness maintenance](../qualification-maintenance-harness.md).
- Implementation source: `scripts/dev/lite/harness.py`

## Preflight and suites

### SA-PREFLIGHT-001
Status: **SUPPORTED**

- Purpose: run deterministic admission/readiness checks for one fixed suite.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]` with authenticated session.
- Authority/prerequisites: exact runtime/revision, qualification/harness enabled,
  bypass/Owner/destructive disabled, API health/readiness, OPA/NATS/JetStream,
  worker, tools, and resource guard.
- Mutating: no. Risk: PASSIVE. Safe for machine automation: yes.
- Exact commands: `task lite:security:assurance:preflight SUITE=smoke`,
  `task lite:security:assurance:preflight SUITE=standard`,
  `task lite:security:assurance:preflight SUITE=deep`,
  `task lite:security:assurance:preflight SUITE=adversarial`.
- Expected output/exit: ready status and checks; failed prerequisites return
  BLOCKED, not a vulnerability finding.
- Evidence/failure/cleanup: preserve sanitized preflight; repair prerequisite
  through supported operator flow before rerun.
- Related playbook: [preflight](../security-assurance/06-preflight.md).
- Implementation source: `scripts/dev/lite/security_assurance.py`

### SA-POLICY-001
Status: **SUPPORTED**

- Purpose: request the supported qualification policy-source synchronization.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]`.
- Authority/prerequisites: active session with policy-sync capability; current
  source and qualification environment.
- Mutating: yes, bounded policy projection request. Risk: SAFE_ACTIVE. Safe for
  machine automation: only as fixed task.
- Exact command: `task lite:security:assurance:policy-sync WAIT_SECONDS=120`.
- Expected output/exit: accepted/converged sanitized status; pending/unavailable
  policy remains BLOCKED.
- Evidence/failure/cleanup: record source/revision state; do not rewrite policy
  on the phone.
- Related playbook: [preflight](../security-assurance/06-preflight.md).
- Implementation source: `pocket-lab-final-structure/runtime/api_fastapi/routers/security_assurance.py`

### SA-SMOKE-001
Status: **SUPPORTED**

- Purpose: run the bounded Smoke suite through the worker-owned execution path.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]` against the Server Phone.
- Authority/prerequisites: successful Smoke preflight and active assurance session.
- Mutating: registered passive/safe-active checks only. Risk: bounded. Safe for
  machine automation: yes.
- Exact commands: `task lite:security:assurance:smoke` or
  `task lite:security:assurance:qualify`.
- Expected output/exit: run `QUEUED` → `RUNNING` → terminal status, usually
  within the 1200-second maximum; worker execution is required.
- Evidence/failure/cleanup: report artifacts, findings, checkpoints, and
  correlation; continue/revoke using the cleanup playbook.
- Related playbook: [Smoke](../security-assurance/07-smoke-playbook.md).
- Implementation source: `pocket-lab-final-structure/runtime/api_fastapi/routers/security_assurance.py`

### SA-STANDARD-001
Status: **SUPPORTED**

- Purpose: run the normal Standard assurance profile.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]` against the Server Phone.
- Authority/prerequisites: Standard preflight, current OPA policy, tools and
  resource guard; active renewable session.
- Mutating: passive/safe-active registered checks only. Risk: bounded. Safe for
  machine automation: yes.
- Exact commands: `task lite:security:assurance:standard` or
  `task lite:security:assurance:qualify:full`.
- Expected output/exit: durable run and normalized static/runtime evidence; the
  maximum suite lease is 1800 seconds.
- Evidence/failure/cleanup: preserve findings/delta/coverage; session renewal
  must not create a second run.
- Related playbook: [Standard](../security-assurance/08-standard-playbook.md).
- Implementation source: `security/assurance/suites.yaml`

### SA-ADV-001
Status: **SUPPORTED**

- Purpose: run fixed qualification-only negative/auth-boundary scenarios.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]` with explicit qualification mode.
- Authority/prerequisites: Adversarial preflight, fault/destructive gates off,
  active `security-assurance-runner` authority.
- Mutating: safe active only. Risk: qualification-only. Safe for machine
  automation: only with operator-approved qualification.
- Exact command: `task lite:security:assurance:adversarial`.
- Expected output/exit: denials and boundary invariants are recorded; maximum
  suite lease is 600 seconds.
- Evidence/failure/cleanup: preserve reason codes/audit and revoke authority;
  no brute force, load, unrelated network, or Recovery mutation.
- Related playbook: [Adversarial](../security-assurance/09-adversarial-playbook.md).
- Implementation source: `security/assurance/suites.yaml`

### SA-DEEP-001
Status: **SUPPORTED**

- Purpose: run explicit manual-only extended assurance.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]` plus fixed phone worker/live lanes.
- Authority/prerequisites: explicit intent, Deep preflight, full tool receipts,
  renewable sessions, resource admission, and one-heavy-tool scheduling.
- Mutating: passive/safe-active registered checks only. Risk: resource-heavy.
  Safe for machine automation: no, manual intent required.
- Exact commands: `task lite:security:assurance:deep` or
  `task lite:security:assurance:qualify:full`.
- Expected output/exit: checkpointed tool/scenario results within the 7200-second
  maximum; a resource stop is PARTIAL/BLOCKED as appropriate.
- Evidence/failure/cleanup: report every executed/deferred/unsupported tool and
  perform complete authority/default-off cleanup.
- Related playbook: [Deep](../security-assurance/10-deep-playbook.md).
- Implementation source: `security/assurance/suites.yaml`

### SA-RUN-001
Status: **SUPPORTED**

- Purpose: invoke the CLI suite admission command directly.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]`.
- Authority/prerequisites: active session, registered suite, preflight.
- Mutating: yes, creates/publishes a durable run. Risk: SAFE_ACTIVE. Safe for
  machine automation: yes, fixed suite only.
- Exact CLI commands: `python3 scripts/dev/lite/security_assurance.py run smoke`,
  `python3 scripts/dev/lite/security_assurance.py run standard`,
  `python3 scripts/dev/lite/security_assurance.py run deep`,
  `python3 scripts/dev/lite/security_assurance.py run adversarial`.
- Expected output/exit: existing active equivalent run may be reused; otherwise
  one worker-owned run reaches a truthful terminal status.
- Evidence/failure/cleanup: run ID/correlation/report; use resume/cancel and
  cleanup only through registered APIs/tasks.
- Related playbook: suite pages 07–10.
- Implementation source: `scripts/dev/lite/security_assurance.py`

### SA-RUN-002
Status: **SUPPORTED**

- Purpose: run one registered scenario or inspect one registered fault.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]` in the allowed qualification mode.
- Authority/prerequisites: exact ID from the current registry and matching
  capability; fault controls require explicit operator qualification.
- Mutating: scenario depends on registry; fault is bounded service mutation.
  Risk: SAFE_ACTIVE. Safe for machine automation: only fixed IDs.
- Exact commands: `task lite:security:assurance:scenario ID=<scenario-id>` and
  `task lite:security:assurance:fault FAULT_ID=<fault-id>`.
- Expected output/exit: registered result/reason code and sanitized evidence;
  unknown IDs fail closed.
- Evidence/failure/cleanup: restore service through the fixed control, preserve
  checkpoint/health evidence, and return default-off.
- Related playbook: [Adversarial](../security-assurance/09-adversarial-playbook.md)
  and [fault recovery](../security-assurance/11-fault-recovery-playbook.md).
- Implementation source: `scripts/dev/lite/security_assurance.py`

## Reports and documentation

### SA-REPORT-001
Status: **SUPPORTED**

- Purpose: read a run's sanitized report or normalized baseline delta.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]`.
- Authority/prerequisites: active session with report/read/baseline capability;
  run belongs to the principal.
- Mutating: no. Risk: PASSIVE. Safe for machine automation: yes.
- Exact commands: `task lite:security:assurance:report RUN_ID=<run-id>` and
  `task lite:security:assurance:compare RUN_ID=<run-id>`.
- Expected output/exit: bounded report artifacts/status; unauthorized or
  incomplete reports fail closed.
- Evidence/failure/cleanup: validate checksums and sanitization; never publish
  raw scanner output or secret values.
- Related playbook: [evidence/reporting](../security-assurance/15-evidence-reporting.md).
- Implementation source: `pocket-lab-final-structure/runtime/api_fastapi/routers/security_assurance.py`

### SA-CLEANUP-001
Status: **SUPPORTED**

- Purpose: revoke temporary authority and prove safe normal-runtime posture.
- Environment: `[APPROVED CLIENT]`/`[DEV PC]`, then `[SERVER PHONE]`.
- Authority/prerequisites: IDs from the qualification workflow and supported
  runtime access.
- Mutating: yes, revokes/stops temporary qualification state. Risk: SAFE_ACTIVE.
  Safe for machine automation: yes for owned disposable authority.
- Exact commands: `python3 scripts/dev/lite/harness.py session-stop --session-id <id>`,
  `python3 scripts/dev/lite/harness.py principal-revoke --principal-id <id>`,
  `task lite:harness:status`, and `task lite:harness:verify-off`.
- Expected output/exit: sessions/principal are revoked or expired and default-off
  status passes; health/readiness/PM2 are checked separately.
- Evidence/failure/cleanup: remove client key/continuity state after server
  revocation; retry supported cleanup on failure, never edit phone source.
- Related playbook: [cleanup/default-off](../security-assurance/16-cleanup-default-off.md).
- Implementation source: `scripts/dev/lite/harness.py`

### SA-DOCS-001
Status: **SUPPORTED**

- Purpose: validate that playbooks, registries, routes, CLI commands, and task
  references do not silently drift.
- Environment: `[DEV PC]` or CI.
- Authority/prerequisites: repository checkout and documentation dependencies.
- Mutating: no. Risk: PASSIVE. Safe for machine automation: yes.
- Exact command: `task lite:docs:security-assurance:check`.
- Expected output/exit: source-owned check summary and focused test, exit `0`;
  missing IDs, paths, routes, or unsafe documentation fails.
- Evidence/failure/cleanup: fix canonical source/docs on DEV PC; no runtime
  cleanup is needed.
- Related playbook: [Start here](../security-assurance/README.md).
- Implementation source: `scripts/docs/check_security_assurance_playbooks.py`

## Historical command migration

Historical commands from the former dossier are mapped in
[command completeness](command-completeness.md). `SUPPORTED` current commands
are the records above. Historical source-only validation commands may remain
useful, but they do not grant harness authority or replace authenticated
runtime proof.
