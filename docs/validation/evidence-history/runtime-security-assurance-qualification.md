# Runtime Security Assurance Qualification Dossier

Status: `PRE-FIX EXACT-HEAD EVIDENCE` / `PARTIAL` for the explicit Deep result.
This dossier records the bounded qualification and supply-chain work performed
for PR #576. The latest exact-`bc1c080d` continuation section near the end is
the authoritative pre-fix runtime capture; it is retained as historical
evidence because the DEV-PC suite deadline was subsequently corrected from
900 to 1200 seconds after a 922-second phone Quick path. A final exact-head
qualification is run after that correction and this documentation projection
are published. It intentionally separates
`RUNTIME-VALIDATED` Android/Termux observations from `VALIDATED` DEV-PC/CI
tool evidence and from `UNVALIDATED`, `BLOCKED`, `UNSUPPORTED`, and
`DEFERRED` scope.

The Runtime Security Assurance Harness is not a generic remote shell. The
Server Phone is a consumer/qualification target, never the development
workspace. No destructive Recovery or production backup/restore operation was
performed.

## 1. Scope, authority, and sanitization

| Item | Evidence |
| --- | --- |
| Repository | `dexter-lab-ctrl/pocket-lab-lite` |
| Base main | `6d7e34920ceaecf773f8dbae36265cc282a199ed` (`VERIFIED`) |
| Feature branch | `feat/runtime-security-assurance-harness` (`VERIFIED`) |
| Feature source at the current authenticated phone qualification | `3ce5acf84675b666f47c6c16038afe54fae1671e` (`VERIFIED`) |
| Feature source at the isolated rollback rehearsal | `3f4f277de5fc8c99d01b0d07baa7376b608d1bd7` (`VERIFIED`; migration/runtime path unchanged by later client/test-only fixes) |
| Latest published DEV-PC supply-chain capture | C2 manager captures `devpc-20260915T003837Z-2003561` and `devpc-20260915T004140Z-2003561`, source `3ce5acf…` (`VERIFIED`) |
| PR | #576, open, draft, and mergeable at `3ce5acf84675b666f47c6c16038afe54fae1671e` (`VERIFIED`; `quick-and-docs` run `34904124568`, job `104176697071`, SUCCESS) |
| Provisioning token | `POCKETLAB_HARNESS_PROVISIONING_TOKEN` absent from the approved client environment (`VERIFIED` boolean-only check) |
| Qualification authentication | Key-bound operator bootstrap; no bearer provisioning token, test-auth bypass, qualification-owner, or human Owner identity (`RUNTIME-VALIDATED`) |
| Network target | Pocket Lab-owned local/loopback surfaces only (`VERIFIED`) |
| Destructive Recovery | Not run (`DEFERRED` by explicit task scope) |
| Raw evidence | Kept outside Git in ignored disposable run directories; canonical artifacts contain normalized/sanitized summaries only (`VERIFIED`) |

The following were never persisted or returned: private keys, raw signatures,
nonces, session tokens, provisioning authority, passwords, cookies, CSRF
values, Authorization headers, NATS credentials, Tailscale keys, recovery
encryption material, raw secret matches, user media, PhotoPrism media, and
backup payload contents. Removed material is represented as
`[REDACTED BY SECURITY ASSURANCE POLICY]` where relevant.

## 2. Final lifecycle being qualified

The implemented lifecycle is:

```text
operator-approved public key
    -> one-use five-minute bootstrap grant
    -> signed challenge proof
    -> disposable security-assurance-runner principal
    -> short-lived session A
    -> FastAPI admission and preflight
    -> durable run_id and fixed NATS/JetStream command
    -> pocket-worker and existing Security runner
    -> normalized SQLite/evidence/report state
    -> session renewal or client reauthentication
    -> same-run reattachment
    -> cleanup and default-off verification
```

The four lifetimes are independent:

| Lifetime | Implemented policy |
| --- | --- |
| Bootstrap grant | Process-ephemeral, five minutes, one use, bound to public key/fingerprint, runtime, revision, profile, purpose, and target (`IMPLEMENTED`, source/tests) |
| Synthetic principal | Bounded qualification principal; default 12 hours, safe bounds 1–24 hours (`IMPLEMENTED`, source/tests) |
| Authentication session | Short-lived current harness session; qualification evidence used a bounded 300-second TTL and renewed it five times (`RUNTIME-VALIDATED`) |
| Assurance run | Suite-owned durable lease; Smoke 1200s, Standard 1800s, Deep 7200s, Adversarial 600s (`IMPLEMENTED`, source/tests) |

Session expiry does not terminate an admitted run. Explicit principal
revocation is stronger: it prevents new sessions/runs, requests safe
cancellation of active assurance runs, and cannot convert incomplete work to
`PASS`.

## 3. Non-destructive schema 35/36 rollback rehearsal

Result: `RUNTIME-VALIDATED` — `VERIFIED SAFE` for the isolated Model A
rehearsal. This is not a production rollback test and does not authorize
restoring live state.

The rehearsal used a disposable sandbox outside the normal runtime state, a
separate local NATS port, alternate API ports, disposable SQLite copies, and
separate source copies of published `origin/main` and the feature revision.
It did not call Recovery APIs and did not touch the live database, Recovery
repository, media, or user data.

The rehearsal source revision predates the final client TTL-forwarding test,
the hermetic Trivy-cache test fix, and the final client workflow-phase fix.
Those later changes do not alter migration files, startup migration policy, or
the application runtime rollback path; the migration-path conclusion therefore
still applies to the final feature source (`INFERRED`, based on the final diff).
The final authenticated Smoke, Standard, Adversarial, and fixed restart
qualifications were consumed at `0cfe3978…`.

Sanitized rehearsal result:

```json
{
  "old_runtime_sha": "6d7e34920ceaecf773f8dbae36265cc282a199ed",
  "feature_runtime_sha": "3f4f277de5fc8c99d01b0d07baa7376b608d1bd7",
  "old_runtime_startup": true,
  "feature_runtime_startup": true,
  "migration_expectation": {"old_max": 34, "feature_added": [35, 36], "restored_max": 34},
  "pre_upgrade": {"migration_count": 34, "integrity_check": "ok", "quick_check": "ok", "foreign_key_errors": 0},
  "pre_upgrade_copy": {"migration_count": 34, "integrity_check": "ok", "quick_check": "ok", "foreign_key_errors": 0},
  "post_upgrade": {"migration_count": 36, "integrity_check": "ok", "quick_check": "ok", "foreign_key_errors": 0},
  "restored": {"migration_count": 34, "integrity_check": "ok", "quick_check": "ok", "foreign_key_errors": 0},
  "restored_old_runtime_startup": true,
  "health_ready_files_present": {
    "old-health.json": true,
    "old-ready.json": true,
    "feature-health.json": true,
    "feature-ready.json": true,
    "restored-health.json": true,
    "restored-ready.json": true
  },
  "sandbox_only": true,
  "production_state_touched": false
}
```

The supported contract is therefore forward-only application/database
migration plus restoration of a verified compatible pre-upgrade database copy
when an application rollback is required. The old runtime continues to reject
an unknown newer schema; that fail-closed check was preserved.

## 4. OPA Standard blocker and resolution

Historical result: `BLOCKED` (`VERIFIED` cause; no bypass used). The earlier
qualification observed a durable active OPA revision that did not match the
feature policy candidate, so the policy-integrity gate correctly returned
`policy_source_update_pending`.

Resolution: `RUNTIME-VALIDATED` — `PASS`. The approved key-bound
`security-assurance-runner` session used the supported fixed
`security.assurance.policy_sync` operation with no caller-supplied policy,
revision, role, target, or activation option. The supervisor-owned lifecycle
reconciled the repository Safety Rules; the sanitized response became
`status=current`, `source_update_required=false`, and the Standard preflight
became `ready` with OPA `ready`. The observed synchronized revision was
`plr-5cd9702f5cea80ae1813013f9c169169` (bounded operational metadata only).

No policy file was manually rewritten on the phone. `qualification-owner`,
test-auth bypass, and destructive gates remained disabled. This clears the
Standard admission blocker without weakening OPA or granting Owner authority.

## 5. Historical pre-C2 tool installation and execution evidence

The tables in this historical section document the earlier pre-promotion
snapshot. The exact C2 tool receipts and execution results are authoritative
in Section 17. In particular, the current registry no longer contains
`deferred`, `inventory_only`, or `unsupported` tool states for the required
assurance tools; Cosign is the sole explicit `NOT_APPLICABLE` result because
no signed artifact is registered for this revision.

### 5.1 DEV-PC/CI fixed toolchain

The existing operator-owned documentation-security installer and parity
installer were used. Binaries were outside Git, version-pinned where
practical, checksum/receipt-backed where the installer provides it, and run
sequentially with `max_parallel_scanners=1`. Caller-supplied executable paths,
targets, flags, templates, and environments are not accepted.

| Tool | Version observed | Origin/lane | Execution result |
| --- | --- | --- | --- |
| Bandit | 1.9.4 | `.venv`, Python/DEV PC | `VALIDATED` fixed Python SAST; 364 candidate warnings, no raw source snippets persisted |
| Gitleaks | 8.30.1 | pinned documentation-security binary, DEV PC | `VALIDATED` bounded current-tree and release scans; 3 fixed-protocol false-positive metadata hits, no raw match |
| pip-audit | 2.10.1 | `.venv`, DEV PC | `VALIDATED` `requirements-ci-openapi-constraints.txt` and docs requirements; 0 known vulnerabilities in the executed manifests |
| npm audit | 11.13.0 / package-lock mode | Node 24.16.0, DEV PC | `VALIDATED` production dependency audit; 0 vulnerabilities |
| OPA CLI | 1.19.0 | `/usr/local/bin/opa`, DEV PC | `VALIDATED` `opa check --strict` and `opa test --fail-on-empty`; both exit 0 |
| Schemathesis | 4.23.0 | pinned parity venv, DEV PC | `VALIDATED` installed/versioned compatibility lane; live phone execution requires the fixed tunnel procedure and is not claimed here |
| Syft | 1.50.0 | Anchore release binary, checksum receipt | `VALIDATED` bounded source/release CycloneDX capture; 54 normalized components in promoted DEV SBOM |
| Trivy | 0.73.0 | Aqua Security release binary, checksum receipt | `VALIDATED` source and SBOM scans; 0 vulnerability/misconfiguration/secret findings after the docs dependency update, 26 license observations |
| OSV-Scanner | 2.5.0 | Google release binary, checksum receipt | `VALIDATED` source and SBOM corroboration; SBOM path clean, source path returned 139 unranked dev-dependency candidates which remain visible |
| Grype | 0.116.1 | Anchore release binary, checksum receipt | `VALIDATED` against the fixed Syft SBOM; no matching vulnerabilities in the executed SBOM |
| Semgrep CE | 1.172.0 | pinned DEV-PC binary, fixed checked-in rules | `VALIDATED` curated architecture rules; 0 findings |
| Cosign | 3.1.3 | Sigstore release binary, checksum receipt | `VALIDATED` version/provenance lane; no applicable signed artifact was invented or claimed |
| Scorecard | 5.5.0 | OpenSSF release binary, checksum receipt | `VALIDATED` workflow posture; Dangerous-Workflow 10, Token-Permissions 0, Pinned-Dependencies 2 (review item) |
| ScanCode | 32.5.0 | pinned DEV-PC binary | `NOT_RUN` in the promoted capture; deep source-license analysis remains optional and unclaimed |
| testssl.sh | no qualified binary | no fixed parser/target contract | `UNSUPPORTED` for this increment |
| Nuclei | no qualified binary | no checked-in template allow-list/runtime parser | `UNSUPPORTED` / `DEFERRED` |
| nmap | no qualified binary on phone or DEV-PC assurance lane | fixed socket inventory remains authoritative | `UNSUPPORTED` for this increment |
| OWASP ZAP | no bounded approved profile | resource-heavy/manual Deep-only candidate | `DEFERRED` |

The static lane is not native phone execution. The phone runtime registry still
selects only the existing worker-owned `pocketlab-security`, Trivy, Lynis, and
fixed OPA posture operations. Missing phone binaries were not mislabeled as
executed.

### 5.2 Server Phone inventory

Observed during the authenticated qualification sequence at
`0cfe3978aba4848934b85c4ff2cd124c611e5b11`:

| Component | Phone evidence |
| --- | --- |
| Pocket Lab Security runner | Existing worker-owned path executed; runtime version not exposed by the result (`RUNTIME-VALIDATED`, version `UNAVAILABLE`) |
| Lynis | Native `/data/data/com.termux/files/usr/bin/lynis`, 3.1.6 (`RUNTIME-VALIDATED`) |
| Trivy | Native and invoked through existing Security path; runtime reports `Version: dev` (`RUNTIME-VALIDATED`, exact release version `UNAVAILABLE`) |
| OPA | Native 1.19.0; direct version probe reported ARM64 build `1e32c796…-dirty`; policy status became ready/current after the fixed synchronization (`RUNTIME-VALIDATED`) |
| Python | 3.14.6 (`RUNTIME-VALIDATED`) |
| npm | 11.18.0 (`RUNTIME-VALIDATED`) |
| Bandit, Gitleaks, pip-audit, Schemathesis, Cosign, Semgrep, OSV-Scanner, Syft, Grype, testssl.sh, Nuclei, nmap, ZAP | Not installed/discovered on the phone (`RUNTIME-VALIDATED` `MISSING`/`UNSUPPORTED`; no installation was performed without a published bounded installer contract) |

The final assurance report intentionally reports a tool version only when the
worker-owned runtime result exposed one. The phone-side Pocket Lab Security
record did not expose a release version and Trivy reported `dev`; no DEV-PC
version was substituted (`VERIFIED`). Optional tools were not promoted into
the worker registry merely because DEV-PC binaries existed: their phone state
is `MISSING`/`UNSUPPORTED` or `DEFERRED` according to the fixed registry, and
no runtime execution is claimed for them.

### 5.3 Dependency remediation

The fixed DEV-PC Trivy SBOM scan found three development-only documentation
dependency advisories before the update: `CVE-2026-73295` for
`mkdocs-material`, `CVE-2026-67422` for `pymdown-extensions`, and
`CVE-2026-61632` for `pymdown-extensions`. The pinned requirements were
updated on the DEV PC from `mkdocs-material==9.7.6` and
`pymdown-extensions==10.21.3` to `9.7.7` and `11.0.1`. The post-update Trivy
SBOM scan reported zero vulnerabilities, and the docs-manifest pip-audit
reported zero known vulnerabilities (`VALIDATED`). This is a development
dependency remediation, not a phone runtime code fix.

OSV-Scanner still returned 139 single-source, unrated, unranked development
dependency candidates from recursive source discovery. They are retained in
the sanitized canonical correlation artifact and are not silently accepted as
exploitable runtime findings. Further triage is `DEFERRED`.

## 6. Historical pre-C2 runtime qualification results

The runs in this section predate the direct outage-window controls, the
worker/client recovery qualification, and the current exact-C2 promotion.
They remain useful as an audit trail, but are superseded by the exact-C2
results in Section 17.

### 6.1 Key-bound bootstrap and authenticated Smoke

Result: `RUNTIME-VALIDATED` — `PASS` at the final runtime source revision.

The approved client generated a disposable Ed25519 key outside the repository,
mode 0600, and exposed only the public fingerprint
`sha256:b759725931347b981183f435e7ec919f9035d68df8f021e93a9339cf56807852`.
The operator-approved launcher created a fixed security-assurance-runner
grant. The client signed the challenge, received a normal short-lived session,
and used the fixed assurance API. The provisioning token was absent and was
not requested, printed, logged, or substituted.

The same client workflow synchronized the fixed repository Safety Rules through
the qualification-only `security.assurance.policy_sync` operation. The
sanitized response was `status=current`, `source_update_required=false`, and
the Standard preflight became `ready`.

Final authenticated runs:

| Suite | Run ID | Result | Scenarios | Worker / operation | Checkpoints / events | Findings | Duration |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: |
| Smoke | `assurance-332d5d5f5c1c41caa502abb0e55e297d` | `PASS` | 8 | `pocketlab-worker-21332` / same run ID | 24 / 32 | 1 low | 708672 ms |
| Standard | `assurance-4feba106906246fcbdfa66811d59c2de` | `PASS` | 11 | `pocketlab-worker-21332` / same run ID | 30 / 41 | 1 low | 370209 ms |
| Adversarial | `assurance-2fc46c0dbc6e4277a96d31825f480d79` | `PASS` | 6 | `pocketlab-worker-21332` / same run ID | 14 / 20 | 0 | 37086 ms |

All three runs were bound to revision `0cfe3978aba4848934b85c4ff2cd124c611e5b11`
and runtime identity `runtime-408970a380f1bb14c7d0069eb2a8c453`. The Smoke
Security unit ran through the existing worker-owned path; its sanitized tool
duration was 676617 ms. Standard's corresponding Security unit was 297664 ms.
The reports were available and sanitized, with no raw scanner output or key
material persisted. The run operation ID matched the run ID; the client did
not choose the NATS subject.

The execution chain was FastAPI admission, fixed
`pocketlab.commands.lite.security.assurance` JetStream delivery, durable
worker consumption, the existing Security runner, and SQLite/report
materialization. This is `RUNTIME-VALIDATED` proof of the central path.

### 6.2 Client disconnect and reattachment

Result: `RUNTIME-VALIDATED` — `PASS` (earlier feature-head reattachment run;
the final `0cfe3978…` runs separately prove renewal through session expiry).

Run `assurance-d9ce31d17f044ce788ed41d7e5d1fb32` was started, the first
monitor was disconnected, and a new client process loaded only non-secret
continuity metadata from a mode-0600 file. It created a fresh signed session,
read the same run ID, and continued observation. The worker remained
`pocketlab-worker-20700`, the worker operation remained bound to the same run,
checkpoint generation remained 24, eight automatic renewals occurred, and the
run reached `PASS`. No duplicate run or second scanner admission was created.

### 6.3 Standard and Adversarial

| Suite | Result | Sanitized evidence |
| --- | --- | --- |
| Standard | `RUNTIME-VALIDATED` — `PASS` | Policy sync returned `current`; preflight had no blockers; run `assurance-4feba106906246fcbdfa66811d59c2de` completed all 11 registered scenarios |
| Adversarial | `RUNTIME-VALIDATED` — `PASS` | Run `assurance-2fc46c0dbc6e4277a96d31825f480d79` completed all 6 registered scenarios and 10 fixed negative probes; no valid authority material was accepted |
| Deep | `NOT_RUN` on the phone | Explicit manual Deep execution was not admitted; DEV-PC bounded Semgrep/Syft/Grype/static captures are recorded separately |

The fixed adversarial probe results were:

| Probe | HTTP result |
| --- | ---: |
| Invalid signature | 422 |
| Expired or unknown challenge | 422 |
| Wrong bootstrap key | 422 |
| Unknown bootstrap grant | 422 |
| Wrong bootstrap signature | 422 |
| Wrong purpose/profile/target | 422 |
| Unknown suite with forged session | 422 |
| Malformed JSON | 422 |
| Unauthorized report | 401 |
| Unauthorized cancel | 401 |

The six registered Adversarial scenarios also exercised fixed Caddy proof
stripping, readiness admission, evidence redaction, source ownership, and the
negative authentication path. Unknown values failed closed; no arbitrary
command, NATS subject, URL, target, or scanner option was accepted.

### 6.4 Fault/recovery scenarios

The current registry provides three fixed, one-use, SAFE_ACTIVE service
recovery controls. They restart only the named Pocket Lab PM2 service and wait
for the fixed health/recovery proof; they do not expose a caller-selected
service, PID, command, outage duration, or NATS subject.

| Scenario | Run ID | Result | Sanitized evidence |
| --- | --- | --- | --- |
| Worker restart/resume | `assurance-fb6ffcf0c87740dab7f00175c2dbd205` | `RUNTIME-VALIDATED` — `PASS` | `worker_restart_once` acted; worker changed from `pocketlab-worker-9272` to `pocketlab-worker-13710`; checkpoint advanced 1→32, event 46, same run/operation, terminal `PASS` |
| NATS restart/recovery | `assurance-65bfe64db677430daec243b788f0a3b9` | `RUNTIME-VALIDATED` — `PASS` | `nats_restart_once` acted; PM2 NATS identity changed; API/NATS/JetStream/worker recovered; checkpoint advanced 15→30, event 41, same run/operation, terminal `PASS` |
| OPA restart/recovery | `assurance-09145bd24cde40669909b33e8d97ca59` | `RUNTIME-VALIDATED` — `PASS` | `opa_restart_once` acted; OPA recovered to ready; checkpoint advanced 17→30, event 41, same run/operation, terminal `PASS` |

These runs prove bounded service restart, heartbeat/reconciliation, durable
correlation, and truthful terminal state. They do not prove an outage-window
request made while OPA or NATS is unavailable: the fixed controls wait for
recovery and do not expose an outage interval. Direct OPA-unavailable
fail-closed behavior is therefore `PARTIAL`/`UNVALIDATED` on the phone, with
source and unit-test coverage retained. No streams, consumers, policy
semantics, Recovery state, or production data were mutated.

FastAPI/client restart semantics remain `VALIDATED` in backend tests and
client reattachment evidence. A stale or incomplete run cannot be converted to
`PASS`.

## 7. Normalized findings

### Critical

None observed in the executed bounded evidence (`VALIDATED`).

### High

None normalized as a confirmed source/runtime defect (`VALIDATED`). Bandit
reported two high-severity candidate warnings in broad static analysis; they
are known safe-wrapper/test-pattern candidates and were not promoted to a
confirmed vulnerability without an attack path (`PARTIAL`, reviewable).

### Medium

No post-remediation Trivy SBOM vulnerability remained (`VALIDATED`). OSV’s 139
unrated single-source development candidates remain visible for dependency
triage (`DEFERRED`, not silently accepted). OpenSSF Scorecard reported
Pinned-Dependencies score 2 (`INFO/REVIEW`, not a confirmed runtime exploit).

### Low

One normalized runtime finding was observed by both the authenticated Smoke and
Standard Security paths:

| Field | Sanitized value |
| --- | --- |
| Category | `protected_runtime_secret` |
| Stable finding identity | `assurance:15deb392776f0f7b27d15fb1f4e6bfb6f2dfaa7c9ec129dd` |
| Asset | `gitea/conf/app.runtime.ini` |
| Severity/confidence | Low / medium |
| STRIDE | Information Disclosure |
| OWASP | A02 Cryptographic Failures; A05 Security Misconfiguration |
| AP/control | AP-06; `CTRL-EVIDENCE-SANITIZE` |
| Baseline | `NEW` against unavailable run-local baseline |
| Status | Open for operator configuration review; `UNCHANGED` on the repeated compatible run |
| Evidence | Bounded path/metadata only; contents are `[REDACTED BY SECURITY ASSURANCE POLICY]` |

The DEV PC did not patch this because the path is not tracked source and the
qualification evidence did not establish an exposure through frontend,
reports, logs, or backup. On the final phone cleanup check the file was
untracked, mode `0600`, and its containing directory was mode `0700`; a bounded
source-reference search found no frontend/runtime reference. Ownership/mode
and rotation policy remain an operator-side configuration review. No secret
value was printed.

### Info / known-safe tooling observations

Gitleaks reported three `generic-api-key` metadata matches: the fixed
WebSocket handshake test material in source/tests. The values are fixed
protocol fixtures, not credentials; raw matches remain redacted. This is a
known-safe false positive (`VALIDATED`).

## 8. STRIDE coverage

The canonical framework remains STRIDE. Runtime and static coverage are
separated:

| Category | Runtime evidence | Static/automated evidence | Status |
| --- | --- | --- | --- |
| Spoofing | Signed bootstrap/session, invalid authority boundary, replay/key/runtime binding probes | Harness negative tests and source review | `RUNTIME-VALIDATED` for the registered adversarial path; human identity remains review-only |
| Tampering | Fixed envelope, target/revision binding, durable checkpoint identity, worker/NATS/OPA restart correlation | Migration/revision checks, registry tests | `RUNTIME-VALIDATED` scoped; message injection and Recovery mutation excluded |
| Repudiation | Run/audit correlation, worker operation, sanitized result state, restart evidence | Finding/report schema tests | `RUNTIME-VALIDATED` scoped |
| Information Disclosure | Caddy/header and redaction probes; protected-runtime-secret finding metadata | Bandit/Gitleaks/Trivy/OSV/Semgrep evidence | `RUNTIME-VALIDATED` scoped; one low operator-review finding remains |
| Denial of Service | Bounded timeout/resource admission semantics and fixed service restart/recovery | Timeout/cancellation/recovery tests | `RUNTIME-VALIDATED` for bounded restart; direct outage/load injection `UNVALIDATED` |
| Elevation of Privilege | Least-privilege profile, Owner/destructive rejection, direct-loopback harness path | Owner/capability/role negative tests | `RUNTIME-VALIDATED` scoped; human Owner paths require review |

No scenario automatically accepted risk or declared exploitability solely from
the threat-model mapping.

## 9. OWASP Top 10 2021 coverage

| Category | Surface/tool | Status |
| --- | --- | --- |
| A01 Broken Access Control | Harness capability/target/profile gates, Owner/destructive rejection, Caddy proof stripping | `RUNTIME-VALIDATED` scoped registered scenarios; no human Owner ceremony |
| A02 Cryptographic Failures | Key-bound bootstrap, signed session proof, secret-handling/redaction boundaries | `RUNTIME-VALIDATED` scoped; protected-runtime-secret metadata remains low/open |
| A03 Injection | Fixed argv and bounded parser tests; no arbitrary command interface | `VALIDATED` source/test evidence; broad runtime fuzzing `NOT_RUN` |
| A04 Insecure Design | Threat-model/AP registry, fixed server-owned execution architecture | `VALIDATED` static/source evidence; no dedicated runtime category |
| A05 Security Misconfiguration | OPA revision gate, Caddy boundary, Trivy misconfiguration mode | `RUNTIME-VALIDATED` scoped |
| A06 Vulnerable and Outdated Components | Trivy, OSV, Grype, pip-audit, npm audit, SBOM | `VALIDATED` DEV-PC lane; phone dependency tool coverage `MISSING` |
| A07 Identification and Authentication Failures | Bootstrap/session lifecycle and fixed replay/expiry/key/signature probes | `RUNTIME-VALIDATED` registered adversarial scope |
| A08 Software and Data Integrity Failures | Signed key possession, revision binding, durable worker correlation, schema rollback rehearsal, Cosign posture | `RUNTIME-VALIDATED` scoped; Recovery mutation excluded |
| A09 Security Logging and Monitoring Failures | Audit/evidence correlation, checkpoint/restart state, sanitized reports | `RUNTIME-VALIDATED` scoped |
| A10 SSRF | Fixed local target contract and no caller URL/host/port | `VALIDATED` source/tests; broad runtime probes `NOT_RUN` |

OWASP rows marked partial or not run are not asserted as full category passes.

## 10. Attack-path coverage

Every current `AP-*` path was classified by the runtime registry. Classification
is coverage bookkeeping, not automatic risk acceptance:

| Attack path | Classification | Executed evidence |
| --- | --- | --- |
| AP-01 | `PARTIALLY_EXECUTABLE` | Caddy proof stripping and harness admission executed; browser-to-NATS reachability remains source evidence |
| AP-02 | `EXECUTABLE_NOW` | Frontend shell boundary and fixed worker ownership executed; no shell API accepted |
| AP-03 | `STATIC_EVIDENCE_ONLY` | Source/identity binding evidence |
| AP-04 | `PARTIALLY_EXECUTABLE` | Fixed command envelope, same-run operation, NATS restart/recovery and replay tests; no arbitrary message injection |
| AP-05 | `STATIC_EVIDENCE_ONLY` | SBOM, provenance, dependency, and release-tool evidence |
| AP-06 | `EXECUTABLE_NOW` | Sanitized evidence/report checks, runtime finding metadata, and redaction probes |
| AP-07 | `PARTIALLY_EXECUTABLE` | Listener/target boundaries; no unrelated network scan |
| AP-08 | `STATIC_EVIDENCE_ONLY` | Non-destructive schema rehearsal only; Recovery mutation excluded |
| AP-09 | `HUMAN_REVIEW_REQUIRED` | No browser WebAuthn ceremony |
| AP-10 | `HUMAN_REVIEW_REQUIRED` | No Enterprise membership/final-Owner ceremony |
| AP-11 | `PARTIALLY_EXECUTABLE` | OPA policy sync/readiness and fixed OPA restart/recovery executed; direct outage-window fail-closed request `UNVALIDATED` |
| AP-12 | `STATIC_EVIDENCE_ONLY` | Current threat-model/source inventory |
| AP-13 | `HUMAN_REVIEW_REQUIRED` | Human identity boundary not automated |
| AP-14 | `HUMAN_REVIEW_REQUIRED` | Current repository classification; no safe automated ceremony |

## 11. Command-by-command assurance ledger

The following ledger records the security-testing and qualification commands
from this continuation. Commands are shown as fixed/sanitized argv shapes;
secret-bearing environment values and raw outputs are intentionally omitted.
`UNAVAILABLE` means the wrapper did not preserve a safe measurement, not zero.

| # | Timestamp / lane | Sanitized command | Target and purpose | Expected | Exit/result | Pocket Lab/tool evidence |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | 2026-09-13T22:40Z, DEV PC | `supply_chain_automation.py capture --run-dir <run>` with default source scan | DEV-PC source/SBOM/security capture | Complete bounded capture | `PARTIAL`; Gitleaks exceeded bounded practical runtime and was terminated with SIGTERM | Incomplete run not promoted |
| 2 | 2026-09-13T22:53Z, DEV PC | `semgrep --config security/static-analysis/pocketlab-architecture.yml --json` | Fixed architecture SAST | Valid JSON | `PASS`, 0 findings; first wrapper was diagnostic-only due malformed proxy environment | No raw output canonicalized |
| 3 | 2026-09-13T22:54Z, DEV PC | `bandit -r pocket-lab-final-structure/runtime scripts/dev/lite -f json -o <run>/bandit.json --exit-zero` | Python SAST | Bounded JSON | `PASS` command exit 0; 364 candidate findings | Candidate warnings normalized only as summary |
| 4 | 2026-09-13T22:54Z, DEV PC | `gitleaks dir --no-banner --no-color --redact=100 --max-target-megabytes 5 --report-format json --report-path <run>/gitleaks-runtime.json pocket-lab-final-structure/runtime` | Bounded source secret detection | Redacted JSON | Exit 1 with 1 fixed-protocol match | Rule/path/line metadata only; secret `[REDACTED BY SECURITY ASSURANCE POLICY]` |
| 5 | 2026-09-13T22:54Z, DEV PC | `pip-audit -r requirements-ci-openapi-constraints.txt --no-deps --disable-pip --format json --progress-spinner off` | Python dependency corroboration | JSON, no known vulnerabilities | `PASS`, 0 vulnerabilities | Safe manifest summary |
| 6 | 2026-09-13T22:54Z, DEV PC | `npm audit --package-lock-only --omit=dev --ignore-scripts --json` | Production frontend dependency audit | JSON, no known vulnerabilities | `PASS`, 0 vulnerabilities; 2,935 total package metadata entries | No credentials/network token persisted |
| 7 | 2026-09-13T22:54Z, DEV PC | `opa check --strict security/policies/opa` | Static policy validation | No errors | `PASS`, exit 0 | Fixed policy path |
| 8 | 2026-09-13T22:54Z, DEV PC | `opa test --fail-on-empty security/policies/opa` | Policy tests | Tests execute and pass | `PASS`, exit 0 | No empty test acceptance |
| 9 | 2026-09-13T23:11Z, DEV PC | `syft dir:. --exclude ./<fixed-generated-cache-dirs> -o cyclonedx-json` | Bounded source SBOM | Valid CycloneDX | `PASS`, fixed capture 1.774s | Source excludes prevent recursive local evidence scan |
| 10 | 2026-09-13T23:11Z, DEV PC | `syft dir:<release-staging> -o cyclonedx-json` | Release SBOM | Valid CycloneDX | `PASS`, 1.172s | Release staging is operator-created and bounded |
| 11 | 2026-09-13T23:11Z, DEV PC | `trivy fs --format json --scanners vuln,misconfig,secret,license --skip-dirs <fixed-dirs> .` | Source vulnerabilities/misconfig/secrets/licenses | Valid JSON | `PASS`, 23.487s; zero vuln/misconfig/secret findings, 26 license observations | Raw report not canonical |
| 12 | 2026-09-13T23:12Z, DEV PC | `trivy sbom --format json <fixed-syft-sbom>` | SBOM vulnerability check | Valid JSON | `PASS`, 0.068s; zero vulnerabilities after dependency update | Cache/database timestamp recorded in transient evidence |
| 13 | 2026-09-13T23:12Z, DEV PC | `osv-scanner scan source --format json --recursive --experimental-exclude <fixed-dirs> .` | Source dependency corroboration | Valid JSON | Exit 1 with findings; valid output, 139 unranked single-source candidates in sanitized correlation | Findings retained, not silently accepted |
| 14 | 2026-09-13T23:12Z, DEV PC | `osv-scanner scan source --format json --lockfile <fixed-syft-sbom>` | SBOM corroboration | Valid JSON | `PASS`, 0 results, 0.670s | No duplicate vulnerability asserted |
| 15 | 2026-09-13T23:12Z, DEV PC | `grype sbom:<fixed-syft-sbom> -o json` | SBOM corroboration | Valid JSON | `PASS`, 0 matches, 1.773s | Syft/Grype versions linked by receipt |
| 16 | 2026-09-13T23:12Z, DEV PC | `gitleaks dir --config security/static-analysis/gitleaks.toml --redact=100 --max-target-megabytes 5 ... .` | Fixed current-tree secret scan | Redacted JSON | Exit 1, valid JSON, 2.129s; 3 fixed-protocol false positives | Raw matches omitted |
| 17 | 2026-09-13T23:12Z, DEV PC | `gitleaks dir ... <release-staging>` | Release secret scan | Redacted JSON | `PASS`, 0 findings, 0.673s | No raw output promoted |
| 18 | 2026-09-13T23:12Z, DEV PC | `semgrep --config security/static-analysis/pocketlab-architecture.yml --json <fixed-source>` | Curated SAST | Valid JSON | `PASS`, 0 findings, 18.815s | Fixed rules only |
| 19 | 2026-09-13T23:12Z, DEV PC | `scorecard --repo=<fixed-repository> --format=json` | Workflow supply-chain posture | Valid JSON | `PASS`, 9.092s; Pinned-Dependencies score 2, Token-Permissions 0 | Review item retained |
| 20 | 2026-09-14, DEV PC | `pip install --upgrade --no-cache-dir mkdocs-material==9.7.7 pymdown-extensions==11.0.1` | Apply targeted docs dependency remediation | Exact pins installed | `PASS` | No secrets in command/output |
| 21 | 2026-09-14, DEV PC | `pip-audit -r requirements-docs.txt --no-deps --disable-pip --format json --progress-spinner off` | Retest docs dependencies | No known vulnerabilities | `PASS`, exit 0 | 0 vulnerabilities |
| 22 | 2026-09-14, DEV PC | `opa health` and revision query against fixed loopback endpoints | OPA health/current revision | Healthy and current | Health 200; revision served active old revision | `policy_source_update_pending` remains the governed blocker |
| 23 | 2026-09-14, Server Phone | `git rev-parse HEAD`; `git status --short --branch`; `pm2 status`; bounded `/health`/`/ready` | Consumer-only preflight | Exact published SHA, clean tree, healthy/ready services | `PASS` before and after prior qualification | PM2 online recorded separately from readiness |
| 24 | 2026-09-14, Server Phone | Existing operator launcher with public-key file and fixed `security-assurance-runner` profile | Key-bound qualification bootstrap | Grant accepted; no token | `PASS` | Public fingerprint only; private key not copied to repo/phone |
| 25 | 2026-09-14, approved client → Server Phone | Existing `security_assurance.py qualify` with in-memory session | Authenticated Smoke and cleanup | PASS or truthful terminal state | Historical `PASS` Smoke; Standard blocked | Historical run IDs retained; superseded by rows 34–37 |
| 26 | 2026-09-14, approved client → Server Phone | Client monitor termination followed by fresh signed session and `GET /runs/<same-id>` | Reattach without duplicate admission | Same run ID continues | `PASS` | Same worker operation/correlation; no duplicate scan |
| 27 | 2026-09-14, Server Phone sandbox | Bounded shell script using disposable source/DB/NATS copies, fixed local ports, SQLite backup API, health/readiness polling | Model A schema rollback rehearsal | Old/new/old runtime healthy with 34→36→34 schema states | `PASS` | No production state touched; exact sanitized JSON in section 3 |
| 28 | 2026-09-13T23:44Z, DEV PC | `supply_chain_automation.py capture --run-dir runtime-assurance-final-published-20260913T234446Z-813731` | Reproducible final supply-chain capture after publishing the exact source SHA | Complete valid capture | `PASS`; source commit `6d257ff9...`; 11 steps, max one scanner | Syft 1.573s; Trivy 27.342s; OSV source valid findings exit 1/25.778s; Grype 1.277s; Gitleaks 1.928s; Semgrep 9.845s; Scorecard 9.791s |
| 29 | 2026-09-13T23:44Z, DEV PC | `supply_chain_automation.py promote --run-dir <final-published-run>`; `supply_chain_automation.py check` | Promote only reviewed sanitized artifacts | Canonical CycloneDX/security/provenance evidence passes checks | `PASS`, both commands exit 0 | Scorecard observed Dangerous-Workflow 10, Pinned-Dependencies 2, Token-Permissions 0; no raw output canonicalized |
| 30 | 2026-09-14T01:25Z, DEV PC | `supply_chain_automation.py capture --run-dir runtime-assurance-final-cfe-20260914T0125Z --resume` with fixed disk-backed temp root and proxy variables removed from the child | Final source/SBOM/security capture at the published documentation/test head | Complete bounded capture | `PASS`; 11 steps, `max_parallel_scanners=1`; OSV/Gitleaks valid finding states retained | Semgrep recovered from the preserved checkpoint; raw output stayed transient; sanitized capture was promoted without runtime evidence |
| 31 | 2026-09-14T01:01–01:07Z, approved client → Server Phone | Operator-approved public-key launcher; signed bootstrap; `security_assurance.py qualify --session-ttl-seconds 60` | Historical exact-feature authenticated Smoke with automatic renewal | Smoke PASS; no duplicate run; sanitized report | `PASS` Smoke; Standard was blocked by OPA source drift | Historical run retained for the TTL-forwarding regression; superseded by rows 34–37 |
| 32 | 2026-09-14T01:16–01:18Z, Server Phone | Production-owned `start-dashboard.sh --profile lite` with explicit safe flags; bounded `/health`, `/ready`, harness status, NATS monitor, OPA revision, PM2 | Historical qualification cleanup | Disabled harness, healthy runtime, clean checkout | `PASS` | Historical default-off proof; final cleanup is recorded in row 44 |
| 33 | 2026-09-14T13:22–13:23Z, DEV PC → Server Phone | Key generation outside Git; operator launcher with public key and fixed `security-assurance-runner`; signed bootstrap challenge/complete | Key-bound one-use bootstrap and disposable principal | Grant consumed; principal/session created; no bearer provisioning token | `PASS`, all secret-bearing values remained in process memory or outside the report | Fingerprint only: `sha256:b759725931347b981183f435e7ec919f9035d68df8f021e93a9339cf56807852`; principal TTL 12h; bootstrap TTL 5m |
| 34 | 2026-09-14T13:23Z, approved client → Server Phone | `security_assurance.py qualify --session-ttl-seconds 300 --sync-policy --policy-sync-wait-seconds 180` | Authenticated preflight, policy convergence, and Smoke admission | Preflight ready; policy current; Smoke admitted | `PASS` | Revision `0cfe3978…`; runtime ID present; no blockers; 5 automatic renewals; session token was not persisted |
| 35 | 2026-09-14T13:23–13:35Z, FastAPI → NATS/JetStream → worker | Registered Smoke execution from row 34; fixed suite/scenario registry | Existing Security Quick path and critical boundaries | Same run/operation, durable checkpoints, sanitized report | `PASS` | `assurance-332d5d5f5c1c41caa502abb0e55e297d`; checkpoint 24; event 32; worker `pocketlab-worker-21332`; one low finding |
| 36 | 2026-09-14T13:36–13:42Z, FastAPI → NATS/JetStream → worker | Registered Standard execution from row 34; fixed suite/scenario registry | OPA-gated standard assurance and existing Security path | Standard preflight ready; all registered scenarios complete | `PASS` | `assurance-4feba106906246fcbdfa66811d59c2de`; checkpoint 30; event 41; same worker; one low finding |
| 37 | 2026-09-14T13:43–13:44Z, approved client → Server Phone | Registered Adversarial execution and fixed negative-probe set | Safe auth, Caddy, target, Owner/destructive, malformed-input, report/cancel boundaries | All registered probes denied as expected; sanitized report | `PASS` | `assurance-2fc46c0dbc6e4277a96d31825f480d79`; 10 fixed probes returned expected 401/422; 0 findings |
| 38 | 2026-09-14T13:49–13:55Z, fixed supervisor control | `POST /api/lite/harness/security-assurance/faults/worker_restart_once` with fixed confirmation | Worker restart, heartbeat reconciliation, checkpoint resume | Same run resumes without duplicate execution | `PASS` | `assurance-fb6ffcf0c87740dab7f00175c2dbd205`; worker identity changed; checkpoint 1→32; event 46; terminal `PASS` |
| 39 | 2026-09-14T13:59–14:05Z, fixed supervisor control | `POST /api/lite/harness/security-assurance/faults/nats_restart_once` with fixed confirmation | NATS/JetStream reconnect and durable worker recovery | No false PASS, duplicate, or storage mutation; service recovers | `PASS` | `assurance-65bfe64db677430daec243b788f0a3b9`; checkpoint 15→30; event 41; terminal `PASS` |
| 40 | 2026-09-14T14:09–14:15Z, fixed supervisor control | `POST /api/lite/harness/security-assurance/faults/opa_restart_once` with fixed confirmation | OPA restart and policy readiness recovery | OPA returns ready; run correlation remains intact | `PASS` | `assurance-09145bd24cde40669909b33e8d97ca59`; checkpoint 17→30; event 41; terminal `PASS` |
| 41 | 2026-09-14, Server Phone | `timeout 5s lynis --version`; `opa version`; `trivy --version` | Runtime tool identity and platform evidence | Version output is bounded and sanitized | `PASS` for Lynis/OPA/Trivy probes | Lynis `3.1.6`; OPA `1.19.0`, ARM64, build commit suffix `1e32c796…-dirty`; Trivy `dev`; Pocket Lab Security version `UNAVAILABLE` |
| 42 | 2026-09-14, Server Phone | Production-owned `start-dashboard.sh --profile lite` with explicit safe flags; direct loopback `/health`, `/ready`, harness status, NATS health, OPA health, PM2 JSON | Final cleanup and default-off proof | Qualification authority gone; normal runtime healthy | `PASS` | Harness disabled/production; active sessions/principals/runs 0; API health/ready 200; NATS monitor `ok`; OPA health 200; normal PM2 services online; checkout clean |

The earlier failed Syft attempt used invalid patterns without the required
`./` prefix and returned a validation error. It was corrected in the
server-owned capture code and covered by `tests/docs/test_supply_chain_runner_hardening.py`.
The first full Gitleaks attempt was stopped after its bounded practical limit;
the final fixed config excludes generated/dependency/cache paths and completed
in 2.129 seconds. Failed/incomplete attempts are retained here as truthful
evidence and were not promoted.

## 12. Automated harness coverage

At the exact runtime source head `0cfe3978…`, the focused backend command
completed:

```text
PYTHONPATH=tests:pocket-lab-final-structure/runtime \
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q \
  tests/backend/test_lite_security_assurance.py \
  tests/backend/test_lite_harness.py \
  tests/backend/test_lite_worker_recovery.py
65 passed, 1 warning
```

The tests cover bootstrap grant hash-only storage and one-use behavior, wrong
key/signature/runtime/revision/profile/target/forwarded transport, principal
and session lifetimes, renewal, old-session expiry/GC, run survival,
idempotent admission, worker heartbeat/stale reconciliation, checkpoint and
retry-safe resume, cancellation, principal revocation, fixed NATS envelope,
sanitization, Caddy/WS/SSE boundaries, readiness versus PM2, and registry
fail-closed behavior. The docs supply-chain hardening test suite passed 29
tests after the fixed exclusion/config changes (`VALIDATED`).

The focused tests are source-level/backend evidence. They do not replace the
phone results or prove the direct OPA outage-window procedure that the fixed
restart control intentionally does not expose.

## 13. Resource evidence

Measured phone values from the final authenticated Smoke, Standard, and
Adversarial evidence:

| Metric | Observation |
| --- | --- |
| Smoke memory | 2,605,641,728 bytes / 35.13% at start; 2,886,537,216 bytes / 38.92% at finish (`RUNTIME-VALIDATED`) |
| Standard memory | 2,888,507,392 bytes / 38.95% at start; 2,902,405,120 bytes / 39.14% at finish (`RUNTIME-VALIDATED`) |
| Adversarial memory | 2,902,597,632 bytes at start; 2,911,846,400 bytes at finish (`RUNTIME-VALIDATED`) |
| Free storage | Smoke 136,874,553,344→136,862,150,656 bytes; Standard 136,851,677,184→136,852,791,296; Adversarial 136,845,893,632→136,839,057,408 (`RUNTIME-VALIDATED`) |
| Battery / charging | 94% / charging throughout the current q runs (`RUNTIME-VALIDATED`) |
| Temperature | 33.0 °C throughout the current q runs (`RUNTIME-VALIDATED`) |
| Worker RSS | Approximately 245–255 MB (`RUNTIME-VALIDATED`) |
| Aggregate CPU/load | `UNAVAILABLE`; Android `/proc` fallback was not represented as measured data |
| Heavy scanner admission | One-heavy-scanner policy accepted (`RUNTIME-VALIDATED`) |
| Per-tool phone CPU, disk delta, thermal delta | `UNAVAILABLE` in the safe report; current totals Smoke 708672 ms, Standard 370209 ms, Adversarial 37086 ms |

DEV-PC fixed capture durations are recorded per step in the command ledger.
Syft’s earlier unbounded root scan reached approximately 1.4 GiB RSS and was
not promoted; fixed exclusions reduced the final source capture to 1.774s.

## 14. Cleanup and consumer-only proof

Final phone qualification cleanup was `RUNTIME-VALIDATED`:

- the short-lived sessions were expired or revoked and active sessions reported
  zero;
- the disposable principal was revoked/cleaned through the supported flow;
- the bootstrap public-key staging files and client temporary qualification
  directory were removed; private key bytes never entered the phone checkout;
- qualification-only runtime state was stopped by rerunning the repository-owned
  production Lite launcher after qualification; the final harness status was
  `disabled` in `production`;
- `POCKETLAB_HARNESS_ENABLED=0`, `POCKETLAB_HARNESS_DESTRUCTIVE=0`,
  `POCKETLAB_QUALIFICATION_OWNER=0`, and `POCKETLAB_TEST_AUTH_BYPASS=0` (or
  equivalent disabled status) were verified without printing environment
  values;
- API health/readiness, NATS/JetStream, durable consumer, worker, OPA, and
  normal PM2 state were healthy; NATS monitor health was `ok`, JetStream was
  enabled, and OPA served the durable known-good revision;
- the phone checkout was detached at the published feature SHA `0cfe3978…`
  and clean both before and after qualification;
- the exact disposable client keys and phone-side public-key staging files were
  removed after the final run; the fixed `.harness-demo.sh` untracked file on
  the DEV PC was preserved as pre-existing user-owned state.

No source, tracked file, branch, commit, tag, reset, patch, or development Git
operation occurred on the Server Phone. All implementation changes and Git
operations were performed on the DEV PC.

## 15. Remediation record

| Finding/change | DEV-PC patch | Validation and retest | Result |
| --- | --- | --- | --- |
| Documentation dependency CVEs (CVE-2026-73295, CVE-2026-67422, CVE-2026-61632) | Pinned `requirements-docs.txt` to mkdocs-material 9.7.7 and pymdown-extensions 11.0.1 | Trivy SBOM retest: 0 vulnerabilities; docs pip-audit: 0 vulnerabilities; docs generation/check required at final head | `VALIDATED` for DEV-PC documentation lane |
| Recursive local evidence/cache contamination of source SBOM/OSV/Gitleaks | Added fixed source exclusions, OSV exact-dir exclusions, checked-in Gitleaks allowlist, and regression tests | Fixed Syft/OSV/Gitleaks capture and 29 hardening tests | `IMPLEMENTED` / `VALIDATED`; no phone source change |
| Trivy cache-identity regression fixture | Isolated the unknown-database test from any locally installed Trivy cache by stubbing both database identity and status | Focused security-assurance/security tests and final full-gate rerun | `IMPLEMENTED` / `VALIDATED`; test-only correction |
| Qualification client discarded the requested renewal TTL on the session request | Forwarded the bounded `ttl_seconds` value to both the signed challenge and normal session endpoints | Harness client regression test; current phone qualification used a 300-second session TTL and completed with 5 renewals | `IMPLEMENTED` / `RUNTIME-VALIDATED` |
| Assurance client attributed transport failure to Smoke after later phases | Preserved the active workflow phase/suite when a client transport failure is observed | Focused client/harness tests; current Smoke/Standard/Adversarial workflow completed with truthful phase state | `IMPLEMENTED` / `VALIDATED` |
| Assurance tool metadata lost bounded version/duration fields | Preserved sanitized tool version and derived duration in the SQLite/report projection | Focused Security/assurance tests; current phone report exposed Trivy `dev` and Lynis `3.1.6` | `IMPLEMENTED` / `RUNTIME-VALIDATED` |
| Runtime `gitea/conf/app.runtime.ini` low finding | No source patch: tracked-source and runtime exposure were not established; content remains redacted | Requires operator ownership/mode/exposure review; no secret printed | `PARTIAL` / `UNVALIDATED` configuration follow-up |
| OPA `policy_source_update_pending` | No bypass; used the fixed qualification-only current-Safety-Rules synchronization path | OPA became `ready`, source became `current`, Standard completed 11 scenarios | `RUNTIME-VALIDATED` / `PASS` |

No genuine Critical or High source/runtime defect was fixed in this
continuation. A Server Phone finding would have been patched only on the DEV
PC and republished before retest.

## 16. Remaining limitations and release decision

`RUNTIME-VALIDATED`: key-bound bootstrap, authenticated Smoke, session
renewal, run survival, client reattachment, fixed worker-owned Security path,
sanitized result/report flow, consumer-only cleanup, and isolated schema
rollback rehearsal.

`RUNTIME-VALIDATED`: Standard now passes after the fixed qualification-only
policy-source synchronization. Live worker restart/resume, NATS restart/
recovery, and OPA restart/recovery also pass with the same run/operation
correlation and preserved checkpoints. The current runs used a 300-second
session TTL and five automatic renewals; authentication expiry did not stop an
admitted run.

`PARTIAL`/`UNVALIDATED`: a direct request made during an OPA outage and a
direct NATS outage-window assertion were not exposed by the fixed restart
controls. Source/unit tests cover fail-closed and interruption semantics, but
this phone evidence proves restart/recovery, not an outage interval.

`DEFERRED`/`UNSUPPORTED`: native phone execution of Bandit, Gitleaks,
pip-audit, Schemathesis, Cosign, Semgrep, OSV-Scanner, Syft, Grype, testssl.sh,
Nuclei, nmap, and ZAP; broad API fuzzing; history-wide secret scans; browser
WebAuthn; Enterprise/final-Owner ceremonies; destructive Recovery; unrelated
network scanning; and heavy ZAP/deep attack profiles.

Final qualification verdict at this evidence point: `PARTIAL`.

PR #576 recommendation: `KEEP DRAFT`. Authenticated Smoke, Standard,
Adversarial, worker restart/resume, NATS restart/recovery, OPA restart/recovery,
policy convergence, cleanup, and the central FastAPI→NATS→worker→Security
path are runtime-proven. The recommendation remains draft because optional
tools are not promoted into the phone worker path, Deep is not run, direct
outage-window fail-closed probes remain unvalidated, and human/Recovery paths
remain outside this non-destructive qualification.

The latest complete static/supply-chain evidence in this dossier is bound to
`cfe3168e05f25483410217bb21bf711f80db596e`; it is a complete local/CI
diagnostic capture with sanitized artifacts promoted and is not substituted for
the final phone runtime report, which is bound to `0cfe3978…`. Any later
documentation-only commit must keep those evidence identities separate and
must not be presented as a new phone runtime execution without an exact-SHA
retest.

## 17. Current C2 continuation addendum (authoritative)

This section supersedes the historical qualification statements above for the
current continuation. It records the current implementation and the bounded
runtime evidence captured against the exact published C2 revision.

### 17.1 Identity and scope

| Item | Evidence |
| --- | --- |
| Status | `CURRENT C2 EVIDENCE`; harness execution blockers closed, with a truthful `PARTIAL` Deep phone result and existing static baseline findings |
| Base `origin/main` | `6d7e34920ceaecf773f8dbae36265cc282a199ed` |
| Feature revision tested | `3ce5acf84675b666f47c6c16038afe54fae1671e` |
| PR | #576, open, draft at the time of this capture |
| Primary framework | STRIDE |
| OWASP reference | Top 10 2021 |
| Runtime target | Server Phone, `local_server_host_only` |
| Runtime identity | `runtime-408970a380f1bb14c7d0069eb2a8c453` |
| Tool registry hash | `sha256:38755b7f13c94ff9a37a0eccf4324455d7f05fcddc9c7dfa1b85f3fb8c657687` |
| Suite registry hash | `sha256:f1a63f73e1b086a24eec1b1f041948b7c17d3e30318d30ae858c89005cdc4bcb` |
| Scenario registry hash | `sha256:a84205ac580f1ac3fab9e5e2d329b4b488f5d511e687f393e9d2d4a7cc232af5` |
| Fault registry hash | `sha256:6a18652671ed48330c44f94f6d9e53d993c6831ec2f3dbd95f9be8b98ae35820` |
| Provisioning token | `UNAVAILABLE` in the approved environment; no token path was weakened or bypassed |
| Qualification identity | Key-bound, operator-approved bootstrap; disposable Ed25519 private keys stayed outside Git and reports |

`VERIFIED`: the C2 client used the key-bound bootstrap path and did not need a
long-lived `POCKETLAB_HARNESS_PROVISIONING_TOKEN`. The bootstrap grant is
server-owned, fixed to `security-assurance-runner`, `security.assurance`,
`local_server_host_only`, qualification runtime, non-destructive operation,
one use, and a five-minute lifetime. The bootstrap-created principal is bounded
to a qualification window, and normal sessions are short-lived and renewable.

`VERIFIED`: an admitted assurance run has its own durable deadline, heartbeat,
worker operation, checkpoint generation and cancellation state. Session expiry
does not terminate an already admitted run.

### 17.2 Authenticated run results

The following are sanitized result identities. Run IDs, worker operation IDs,
and correlation IDs are not credentials and are included only to establish
same-run execution and recovery. Session tokens, signatures, challenges and
private key material are intentionally absent.

| Operation | Qualification result | Run result | Checkpoints/events | Evidence |
| --- | --- | --- | --- | --- |
| Authenticated Smoke | `PASS` | `assurance-3c4b4fb1ff3f461bb61167e975a9253e` | 24 / 32 | worker-owned Security path, sanitized report, exact C2 revision |
| Authenticated Standard | `PASS` | `assurance-6c166dbfd4b94bd38d0a305fb9a2334f` | 30 / 41 | fixed NATS subject, JetStream delivery, worker result, sanitized report |
| Safe Adversarial | `PASS` | `assurance-432681b19c5f403ea3c62217c354bb07` | 14 / 20 | negative authentication and authorization probes denied as expected |
| Direct OPA outage window | `PASS` | fixed fault `opa_pause_probe_restore` | bounded fault evidence | unavailable policy denied; OPA restored and policy rechecked |
| Direct NATS outage window | `PASS` for recovery control | injected Standard was `FAIL` during the intentional outage | preserved run/correlation | outage was observed, no false PASS or duplicate, NATS/JetStream/worker recovered |
| Worker restart/resume | `PASS` | fixed fault `worker_restart_once` | completed checkpoints retained | new worker resumed the same run without suite duplication |
| Physical client crash/reattach | `PASS` | `assurance-1179d31089294c64bf00115c38eff408` | same run and worker operation | monitor terminated and restarted; same run reattached and completed |
| Phone Deep | `PARTIAL` | `assurance-19a5bd9588324f7d87ea4acf736b2e71` | 30 / 41 | all registered phone tools returned; existing Security Full result was partial, with no medium/high/critical finding |
| DEV-PC external Standard | truthful tool result `FAIL` | `devpc-20260915T003837Z-2003561` | managed tool receipts | 512 existing normalized baseline findings |
| DEV-PC external Deep | truthful tool result `FAIL` | `devpc-20260915T004140Z-2003561` | managed tool receipts | 517 findings: 512 existing and 5 new ZAP observations |

`RUNTIME-VALIDATED`: the successful Smoke and Standard runs followed the
normal control-plane path:

```text
key-bound signed client
  -> FastAPI admission and preflight
  -> fixed subject pocketlab.commands.lite.security.assurance
  -> NATS / JetStream durable delivery
  -> pocket-worker
  -> registered worker-owned Security runner
  -> Trivy/Lynis where discovered by the existing Security lifecycle
  -> normalized/redacted evidence
  -> SQLite assurance lifecycle
  -> report and checksums
```

No caller-selected command, executable, working directory, target, URL, port,
NATS subject, scanner flag, template, ruleset or environment override was
accepted.

### 17.3 Preflight, renewal and continuity

Each C2 qualification first checked the exact deployed revision, a clean phone
worktree, explicit qualification mode, harness enabled, test-auth bypass off,
qualification-owner off, destructive gate off, API health, API readiness,
Caddy, NATS, JetStream, worker, scanner capability, resource admission and
absence of a conflicting heavyweight Security run. The preflight explicitly
records that PM2 `online` is not equivalent to FastAPI readiness.

`RUNTIME-VALIDATED`: the C2 client renewed short-lived sessions automatically
(the qualification runs recorded multiple renewals, including five during the
longer Smoke/Standard workflows) and continued to observe the same admitted
run. The old session was allowed to expire logically; it was not extended in
place and no raw token was persisted.

`RUNTIME-VALIDATED`: the physical client-crash test terminated only the
qualification client monitor on the DEV PC. While the client was absent, the
phone retained the same `RUNNING` run and advancing worker heartbeat. A new
client process loaded bounded continuity metadata, obtained a fresh session,
reattached to the same run ID and observed terminal `PASS`. No duplicate run
or scanner operation was admitted. Continuity state was absent after cleanup.

### 17.4 Fault-window and recovery evidence

The fixed fault registry contains only registered qualification actions. It
does not expose a generic service-control API.

* `opa_pause_probe_restore` stopped only the registered OPA service, executed
  one fixed governed probe during the unavailable window, and restored OPA in a
  bounded `finally` path. During the window the response was unavailable,
  `fail_closed=true`, `decision_allow=false`, and policy revision was not
  accepted as current. After restoration OPA was healthy/current and the same
  probe was denied by current policy. `RUNTIME-VALIDATED: PASS`.
* `nats_pause_probe_restore` stopped only the registered Pocket Lab NATS
  service, observed the bounded outage, restored it promptly, and verified
  TCP/API reconnect, JetStream availability, fixed-subject ownership, same
  run/operation correlation, no duplicate execution and terminal-state
  truthfulness. The injected assurance run returned `FAIL` while NATS was
  intentionally unavailable, which is the required truthful result; the fault
  control and recovery assertion returned `PASS`. No stream, consumer or
  storage was deleted or modified.
* `worker_restart_once` restarted only the registered worker through the
  supported supervisor path. The old heartbeat became stale, the new worker
  identity took over, completed checkpoints remained durable, and the same
  run/operation reached terminal `PASS`. `RUNTIME-VALIDATED: PASS`.

`VERIFIED`: these controls cannot turn an interrupted or unavailable execution
into `PASS`. An injected outage result may therefore be `FAIL`/`PARTIAL` while
the recovery assertion itself passes.

### 17.5 Current registered toolchain

The C2 registry promotes all 18 requested tools to first-class fixed contracts.
The manager check reported 17 `READY` managed tools and one truthful
`NOT_APPLICABLE` result for Cosign because this revision has no registered
signed artifact. No registry entry remains `DEFERRED`, `INVENTORY_ONLY`, or
`UNSUPPORTED`.

| Tool | Version evidence | Lane | Harness status / execution |
| --- | --- | --- | --- |
| Pocket Lab Security | runtime-reported existing Security result; exact component version not exposed | Server Phone worker | `ACTIVE` / Smoke, Standard, Deep phone path |
| Lynis | `3.1.6` runtime-reported | Server Phone worker | `ACTIVE` / worker-owned lifecycle |
| Trivy | runtime-reported (`dev` in sanitized projection) | Server Phone worker | `ACTIVE` / worker-owned optimized lifecycle |
| Bandit | `1.9.4` | DEV-PC static | `ACTIVE` / Standard and Deep executed |
| Gitleaks | `8.30.1` | DEV-PC static | `ACTIVE` / Smoke, Standard and Deep executed |
| pip-audit | `2.10.1` | DEV-PC static | `ACTIVE` / Standard and Deep executed |
| npm audit | `11.13.0` | DEV-PC static | `ACTIVE` / Standard and Deep executed |
| OPA | runtime readiness/current-policy evidence; CLI version not required by service path | Server Phone worker | `ACTIVE` / preflight, policy sync, outage window |
| Schemathesis | `4.23.0` | DEV-PC → actual phone runtime | `ACTIVE` / fixed OpenAPI safe routes executed |
| Cosign | `3.1.3` installed and checked | DEV-PC static | `ACTIVE` / `NOT_APPLICABLE`, no signed artifact |
| Semgrep CE | `1.172.0` | DEV-PC static | `ACTIVE` / Standard and Deep executed |
| OSV-Scanner | `2.5.0` | DEV-PC static | `ACTIVE` / Standard and Deep executed |
| Syft | `1.50.0` | DEV-PC static | `ACTIVE` / Deep executed |
| Grype | `0.116.1` | DEV-PC static | `ACTIVE` / Deep executed against managed Syft SBOM |
| testssl.sh | `3.2.2` | DEV-PC → actual phone runtime | `ACTIVE` / Standard and Deep executed against fixed Caddy endpoint |
| Nuclei | `3.8.0` | DEV-PC → actual phone runtime | `ACTIVE` / curated safe templates executed |
| nmap | `7.98` | DEV-PC → actual phone runtime | `ACTIVE` / fixed local Pocket Lab listener list |
| OWASP ZAP | `2.17.0` | DEV-PC → actual phone runtime | `ACTIVE` / bounded Deep API/baseline execution |

Installation receipts were created by the fixed DEV-PC manager under the
operator-owned tool directory, with pinned versions, source receipts,
qualified absolute paths, bounded environments and checksums where the source
supports them. Temporary download/extraction paths were not included in Git.
The external manager Standard and Deep runs executed every applicable managed
tool. The phone tool entries remain worker-owned and were attached to phone
assurance reports rather than run by the client.

`VERIFIED`: the toolchain is orchestrated through fixed server-owned contracts;
the caller cannot change tool argv, target, template, ruleset or environment.
`UNAVAILABLE`: the existing phone Security projection intentionally does not
expose a Pocket Lab Security binary version, so no version is inferred here.

### 17.6 Finding and delta summary

Phone Smoke/Standard/Adversarial reports contained no Critical, High or Medium
finding. The recurring one Low finding is the protected backend runtime-secret
posture for `gitea/conf/app.runtime.ini`; the evidence records only the bounded
path and sanitized metadata. Existing checks continue to show mode `0600`, a
mode `0700` parent, no frontend exposure and no raw secret in logs/reports.
It remains `REVIEW REQUIRED — NON-BLOCKING FOR SECURITY ASSURANCE HARNESS`.

The DEV-PC managed Deep result contains 517 normalized findings: 512 existing
baseline findings and five new ZAP observations (one Medium, one Low and three
Info). The new ZAP observations are retained as normalized review findings,
not hidden by the suite result. OSV critical/high dependency rows are existing
baseline package findings and are not represented as new C2 harness defects;
Trivy/OSV/pip-audit/npm-audit/Grype corroboration is correlated by stable
package/advisory identity. The current production dependency-only npm audit
result was clean.

Bandit findings are existing bounded subprocess/agent patterns; the current
harness's internal SQL and fixed loopback probe patterns were reviewed as
bounded implementation behavior, not accepted as demonstrated exploitability.
Gitleaks matches are fixed test/protocol fixtures; raw matches are never
persisted. This is a classification of the observed result, not automatic risk
acceptance.

### 17.7 STRIDE and attack-path coverage

`RUNTIME-VALIDATED`: authenticated admission, Caddy proof stripping, runtime
readiness, worker ownership, evidence redaction, OPA outage fail-closed,
NATS outage recovery, worker restart/resume, adversarial authentication
negative tests and Security projection were executed. The canonical model
still classifies every current AP entry. Current classifications are:

| Attack path | Classification | Current evidence |
| --- | --- | --- |
| AP-01 Browser control-plane bypass | `PARTIALLY_EXECUTABLE` | Caddy/FastAPI boundary runtime-tested; direct browser-to-NATS remains source evidence |
| AP-02 Browser shell execution | `EXECUTABLE_NOW` | frontend/backend shell boundary assertions and runtime ownership tested |
| AP-03 Forged managed-device identity | `PARTIALLY_EXECUTABLE` | harness identity binding tested; enrolled-device forgery is not injected |
| AP-04 Messaging command tampering/replay | `PARTIALLY_EXECUTABLE` | fixed subject, durable delivery and duplicate protection tested; arbitrary tampering is not injected |
| AP-05 Supply-chain artifact compromise | `STATIC_EVIDENCE_ONLY` | managed tool receipts, SCA/SBOM/signature applicability and source evidence |
| AP-06 Evidence poisoning | `EXECUTABLE_NOW` | redaction, normalized evidence and bounded persistence tested |
| AP-07 Tailnet/private-network exposure | `PARTIALLY_EXECUTABLE` | local listener/Caddy/TLS checks; unrelated network scanning excluded |
| AP-08 Recovery state tampering | `OUT_OF_SCOPE_FOR_PR_576` | destructive Recovery and production restore explicitly excluded |
| AP-09 Human identity/WebAuthn misuse | `HUMAN_REVIEW_REQUIRED` | physical ceremony is not automated |
| AP-10 Enterprise membership/final-Owner escalation | `HUMAN_REVIEW_REQUIRED` | governance ceremony remains human-owned |
| AP-11 OPA authorization integrity failure | `EXECUTABLE_NOW` | policy sync, current revision and unavailable-window fail-closed proof |
| AP-12 Runtime availability/worker recovery | `PARTIALLY_EXECUTABLE` | worker, NATS and bounded resource/restart recovery tested; uncontrolled load excluded |
| AP-13 Backup/recovery media exposure | `HUMAN_REVIEW_REQUIRED` | no backup payload or user media was scanned |
| AP-14 Protected runtime-secret handling | `HUMAN_REVIEW_REQUIRED` | ownership/rotation review remains operator-owned; exposure controls were checked |

The STRIDE report retains the six categories and maps each executed scenario
to its threat, asset, trust boundary, control, expected invariant, observed
evidence and residual risk. Human-review classifications are complete coverage
classifications, not missing implementation, when the model documents reviewer
role and pass/fail evidence requirements.

OWASP Top 10 2021 mappings remain reference mappings rather than a replacement
for STRIDE. Runtime-tested categories include A01 Broken Access Control, A02
Cryptographic Failures where applicable, A05 Security Misconfiguration, A07
Identification and Authentication Failures, A08 Software and Data Integrity
Failures, and A09 Security Logging and Monitoring Failures. Injection and
other categories without a relevant safe scenario remain explicitly
`NOT_APPLICABLE`, `HUMAN_REVIEW_REQUIRED`, or static-only in the report; they
are not called runtime `PASS` without an executed scenario.

### 17.8 Current command/output ledger

The command ledger below is intentionally bounded and sanitized. Exact raw
stdout/stderr is not reproduced when it could contain secrets, private paths,
or scanner matches; the linked machine-readable receipts contain normalized
summaries and checksums.

| Seq. | Environment/lane | Sanitized command or operation | Result |
| ---: | --- | --- | --- |
| 43 | DEV PC | `security_assurance_toolchain.py install` | `PASS`; receipts for all managed tools |
| 44 | DEV PC | `security_assurance_toolchain.py check` | `PASS`; 17 `READY`, Cosign `NOT_APPLICABLE` |
| 45 | DEV PC | managed fixed Standard suite | `FAIL` from existing baseline findings; all applicable tools executed |
| 46 | DEV PC | managed fixed Deep suite | `FAIL` from baseline/new normalized findings; all applicable tools executed |
| 47 | Server Phone via fixed local tunnel | key-bound qualification bootstrap and signed client setup | `PASS`; no provisioning bearer token used |
| 48 | Server Phone worker | fixed authenticated Smoke suite | `PASS`; FastAPI → NATS/JetStream → worker → Security |
| 49 | Server Phone worker | fixed authenticated Standard suite | `PASS`; same architecture, renewable short sessions |
| 50 | Server Phone worker | fixed safe Adversarial suite | `PASS`; bounded negative probes denied |
| 51 | Server Phone worker | `opa_pause_probe_restore` | `PASS`; unavailable-window deny and restoration |
| 52 | Server Phone worker | `nats_pause_probe_restore` | `PASS` recovery assertion; injected run failed truthfully during outage |
| 53 | Server Phone worker | `worker_restart_once` | `PASS`; same run, retained checkpoints, new worker |
| 54 | DEV PC client / Server Phone worker | terminate monitor, then rerun fixed client with same identity | `PASS`; same run reattached, no duplicate |
| 55 | Server Phone | bounded Deep/full orchestration | `PARTIAL`; phone Security Full result partial, external Deep receipts complete |
| 56 | Server Phone | sanitized evidence/checksum/continuity inspection | `PASS`; no raw credential material persisted |
| 57 | Server Phone | supported qualification cleanup and default-off verification | `PASS` in C2 reports; final exact-head cleanup is repeated after the final promotion |

Every entry had a fixed target and bounded timeout. No command in this ledger
was a generic shell request or caller-defined scanner invocation. The full
per-tool receipts record version, execution lane, fixed target, duration,
exit/result classification, finding count, normalized output summary,
STRIDE/OWASP/AP mapping, and evidence reference.

### 17.9 Resource and sanitization evidence

Measured phone values are reported only where the runtime exposed them:

| Run | Duration | Battery | Temperature | Memory/free storage | CPU/RSS |
| --- | ---: | --- | --- | --- | --- |
| Smoke | approximately 708,672 ms | 72% → 59%, not charging across captures | 33.9–34.4 C | available memory approximately 2.99–3.13 GiB; free storage approximately 136.7 GiB | CPU and per-process RSS `UNAVAILABLE` |
| Standard | approximately 370,209 ms | captured in sanitized resource snapshots | captured in sanitized resource snapshots | captured in sanitized resource snapshots | CPU/RSS `UNAVAILABLE` |
| Adversarial | approximately 37,086 ms | captured in sanitized resource snapshot | captured in sanitized resource snapshot | captured in sanitized resource snapshot | CPU/RSS `UNAVAILABLE` |
| Deep phone | approximately 610 s | captured start/finish | captured start/finish | captured start/finish | CPU/RSS `UNAVAILABLE` |

`VERIFIED`: resource admission remained enabled, output was bounded, and the
one-heavy-scanner guard remained true. Missing Android `/proc` metrics are not
reported as zero. Security scans excluded PhotoPrism media, Android shared
storage, backup payload contents, runtime state exclusions, generated/cache
paths and other repository-defined user-data paths. Reports contain normalized
findings only; raw secret matches, credentials, authorization headers, private
keys, user media and recovery material are absent or replaced with
`[REDACTED BY SECURITY ASSURANCE POLICY]`.

### 17.10 Release and rollback conclusion

`VERIFIED SAFE — NON-DESTRUCTIVE ISOLATED ROLLBACK REHEARSAL`: the existing
Model A release contract was proven earlier in an isolated disposable sandbox:
compatible pre-upgrade SQLite state, integrity check, feature migrations
0035/0036, disposable pre-upgrade copy restoration, prior-runtime startup,
health/readiness and schema/integrity checks. No live Server Phone database,
Recovery repository, backup payload, user media or production state was
restored or downgraded. The forward-only migration rejection safeguard remains
enabled. This conclusion does not authorize destructive Recovery qualification.

### 17.11 Non-blocking review classifications

The following are intentionally outside the Runtime Security Assurance Harness
readiness gate:

* protected Gitea runtime-secret ownership/rotation: `REVIEW REQUIRED —
  NON-BLOCKING FOR SECURITY ASSURANCE HARNESS`;
* physical WebAuthn, human approval, Enterprise membership and final-Owner
  ceremonies: `HUMAN_REVIEW_REQUIRED — NON-BLOCKING FOR PR #576`;
* destructive Recovery and production backup/restore: `OUT_OF_SCOPE_FOR_PR_576
  — NON-BLOCKING`;
* general production maintenance activation and unrelated release-management
  improvements: `OUT_OF_SCOPE — NON-BLOCKING`.

These classifications do not accept risk automatically. They preserve human
ownership and identify the evidence and reviewer responsibilities for later
work.

### 17.12 C2 qualification verdict

`VALIDATED`: the C2 implementation closes the authenticated admission,
renewal, durable run, idempotent admission, checkpoint/reconciliation,
worker-heartbeat, worker restart, client reattachment, direct OPA outage,
direct NATS recovery, toolchain orchestration, sanitization and reporting gaps
that were open in the pre-C2 report.

`PARTIAL`: the phone Deep result truthfully contains the existing Security Full
partial outcome, and DEV-PC static Deep contains baseline and newly observed
normalized tool findings. These are reported for review and are not converted
to `PASS`.

The C2 evidence is not the final head after this documentation update. A final
exact-head qualification is required after the documentation and any remaining
tracked changes are committed and published. No later phone result may be
described as testing an earlier SHA.

## 18. Latest pre-fix exact-head continuation evidence

This section supersedes the older C2 identities for the exact published
`bc1c080d1e5d5ef9568d32b74dce6e70d9fa0f33` pre-fix candidate. It is a
sanitized pre-projection capture; the final documentation/source candidate is
qualified again so the final PR head and runtime-tested head remain identical.

### 18.1 Repository and authentication

| Item | Result |
| --- | --- |
| Base `origin/main` | `6d7e34920ceaecf773f8dbae36265cc282a199ed` (`VERIFIED`) |
| Candidate feature head | `bc1c080d1e5d5ef9568d32b74dce6e70d9fa0f33` (`VERIFIED`) |
| PR | #576 open, draft, mergeable; exact-head `quick-and-docs` SUCCESS (`VERIFIED`) |
| Provisioning token | absent by boolean-only check; no bearer path used (`VERIFIED`) |
| Bootstrap | operator-approved, key-bound, five-minute, one-use grant (`RUNTIME-VALIDATED`) |
| Principal | disposable `security-assurance-runner`, qualification class, local-server-only target, non-destructive (`RUNTIME-VALIDATED`) |
| Session | short-lived session renewed automatically; 11 renewals in the full run (`RUNTIME-VALIDATED`) |
| Cleanup | principal disabled/revoked and 12 session records invalidated by supported cleanup (`RUNTIME-VALIDATED`) |

No private key, raw signature, challenge, session token, provisioning secret,
authorization header, NATS credential, user media, or backup payload was
persisted or returned. The client key remained outside Git and only the public
key was staged on the phone (`VERIFIED`).

### 18.2 Exact candidate runtime suites

The full fixed workflow was `qualification-20260915T052042Z-2285924`.
Preflight and policy synchronization were both `PASS`; the phone worktree was
clean, API health/readiness were HTTP 200, Caddy/NATS/JetStream/worker were
available, OPA was ready where required, scanner capability was known, the
resource guard admitted the run, and no conflicting Security scan was present.
PM2 `online` was not used as a readiness substitute (`RUNTIME-VALIDATED`).

| Suite or control | Status | Run/fault identity | Sanitized result |
| --- | --- | --- | --- |
| Smoke | `PASS` | `assurance-3035de3c3ca947d2a719f431e7848719` | 8 scenarios, 5 registered phone tools, checkpoint 24/32, one low protected-secret review finding |
| Standard | `PASS` | `assurance-0ef4fafef87f474584fd9a524c929604` | 11 scenarios, 15 tool records, checkpoint 30/41, no medium/high/critical findings |
| Safe Adversarial | `PASS` | `assurance-06a8d5abbe1c444ea88092ad83175b31` | 6 scenarios, 14/20 checkpoints; fixed negative-auth and boundary probes rejected |
| Deep phone path | `PARTIAL` | `assurance-3a272766a1bc4e908e9881c3ce7c5a0d` | 11 scenarios, 18 tool records, checkpoint 30/41; existing full Security reported protected runtime-config target partial, no deadline overrun |
| DEV-PC managed Standard | `FAIL` as a finding-bearing tool report | `devpc-20260915T054600Z-2285924` | every applicable managed tool executed; 514 normalized findings, existing dependency/SAST baseline retained |
| DEV-PC managed Deep | `FAIL` as a finding-bearing tool report | `devpc-20260915T054855Z-2285924` | every applicable managed tool executed; 520 normalized findings, existing baseline plus bounded ZAP observations |
| OPA pause/probe/restore | `PASS` | `qualification-20260915T041119Z-2257044` | OPA unavailable → fixed governed deny with `fail_closed=true` → healthy/current restore → policy deny |
| Worker restart/resume | `PASS` | `qualification-20260915T044156Z-2270309` | worker identity changed; same run/correlation and durable checkpoints retained |
| NATS pause/probe/restore | `PASS` fault control | `qualification-20260915T050840Z-2280627` | fixed `pocket-nats` outage observed and restored; injected run failed truthfully, no duplicate or false PASS |

The NATS fault’s injected run was intentionally `FAIL` because the active
Smoke execution encountered the controlled outage. The fault result itself is
the recovery assertion and is `PASS`; it must not be conflated with the clean
baseline Smoke result (`VERIFIED`).

### 18.3 End-to-end and resilience proof

`RUNTIME-VALIDATED`: the clean Smoke and Standard runs established:

```text
signed key-bound client
  -> FastAPI admission/preflight
  -> pocketlab.commands.lite.security.assurance
  -> NATS / JetStream durable delivery
  -> pocket-worker
  -> existing worker-owned Quick/Full Security lifecycle
  -> native Trivy/Lynis where discovered
  -> sanitized normalized evidence
  -> SQLite assurance checkpoints and terminal row
  -> report/checksums
```

The client renewed short sessions while the durable run lease continued. The
physical client-monitor test terminated only the DEV-PC monitor; the phone
retained the same run and heartbeat, and the restarted client reauthenticated
and reattached without a duplicate run (`RUNTIME-VALIDATED` in the preceding
C2 capture; final-head repetition remains required after this projection).

The worker fault changed the worker identity while preserving run ID,
operation correlation and completed checkpoints. The NATS fault preserved the
same run ID and worker operation, observed no duplicate command, restored
JetStream/worker connectivity, and kept the interrupted run truthful. The OPA
fault denied a fixed governed probe during the unavailable window and did not
fall back to Owner or test-auth authority (`RUNTIME-VALIDATED`).

### 18.4 Toolchain receipts and finding triage

The fixed tool manager reported 17 `READY` tools and Cosign
`NOT_APPLICABLE` because no signed artifact is registered for this revision.
All required entries are active fixed contracts; no tool registry entry is
`DEFERRED`, `INVENTORY_ONLY`, or `UNSUPPORTED` (`VERIFIED`).

| Tool | Version | Lane | Execution |
| --- | --- | --- | --- |
| Pocket Lab Security | runtime-reported; binary version intentionally not exposed | Server Phone worker | Smoke/Standard/Deep existing lifecycle (`RUNTIME-VALIDATED`) |
| Lynis | `3.1.6` | Server Phone worker | Smoke/Standard/Deep (`RUNTIME-VALIDATED`) |
| Trivy | runtime projection `dev`; exact upstream binary version not exposed | Server Phone worker | Smoke/Standard/Deep (`RUNTIME-VALIDATED`) |
| Bandit | `1.9.4` | DEV-PC static | Standard/Deep (`VALIDATED`) |
| Gitleaks | `8.30.1` | DEV-PC static | Standard/Deep (`VALIDATED`; fixed fixtures reviewed) |
| pip-audit | `2.10.1` | DEV-PC static | Standard/Deep (`VALIDATED`) |
| npm audit | `11.13.0` | DEV-PC static | Standard/Deep (`VALIDATED`; production dependency-only result clean) |
| OPA | runtime policy readiness/current revision | Server Phone worker | preflight, sync, outage window (`RUNTIME-VALIDATED`) |
| Schemathesis | `4.23.0` | DEV-PC → actual phone runtime | Standard/Deep bounded route set (`VALIDATED`) |
| Cosign | `3.1.3` | DEV-PC static | `NOT_APPLICABLE`; no signed artifact (`VALIDATED`) |
| Semgrep CE | `1.172.0` | DEV-PC static | Standard/Deep (`VALIDATED`) |
| OSV-Scanner | `2.5.0` | DEV-PC static | Standard/Deep (`VALIDATED`; existing baseline advisories) |
| Syft | `1.50.0` | DEV-PC static | Deep (`VALIDATED`) |
| Grype | `0.116.1` | DEV-PC static | Deep against managed Syft SBOM (`VALIDATED`) |
| testssl.sh | `3.2.2` | DEV-PC → actual phone runtime | Standard/Deep fixed Caddy TLS target (`VALIDATED`) |
| Nuclei | `3.8.0` | DEV-PC → actual phone runtime | Standard/Deep curated safe template (`VALIDATED`) |
| nmap | `7.98` | DEV-PC → actual phone runtime | Standard/Deep fixed local Pocket Lab port list (`VALIDATED`) |
| OWASP ZAP | `2.17.0` | DEV-PC → actual phone runtime | Deep bounded API baseline (`VALIDATED`) |

The managed Standard/Deep receipts reported every applicable external tool as
executed. They intentionally preserve findings rather than treating a zero
exit code as security success. The normalized Deep count was 520: five
critical and 56 high rows are existing dependency/SAST baseline material; the
bounded ZAP run added one medium, one low and four informational observations.
The ZAP medium is alert `10055`, CSP directive fallback, against the direct
loopback JSON API target; the direct API is not a browser HTML origin and the
Caddy same-origin boundary supplies the relevant response headers. It remains
a bounded review/triage observation, not a demonstrated harness exploit. ZAP
alert `10021` (X-Content-Type-Options) is absent on the direct FastAPI hop but
present through Caddy. Raw ZAP traffic was not retained (`PARTIAL` review,
not a secret disclosure).

### 18.5 STRIDE, OWASP, and attack-path status

`RUNTIME-VALIDATED`: the latest clean phone runs exercised Spoofing, Tampering,
Repudiation, Information Disclosure, Denial of Service and Elevation of
Privilege controls through the signed-boundary, Caddy, redaction, OPA, NATS,
worker-restart and negative-auth scenarios. Static and tool lanes add source,
dependency, SBOM and fixed listener/TLS evidence. The canonical registry
classified all current AP entries (`VERIFIED`).

| Coverage class | Attack paths |
| --- | --- |
| `EXECUTABLE_NOW` | AP-02, AP-06, AP-11 (including direct OPA fail-closed) |
| `PARTIALLY_EXECUTABLE` | AP-01, AP-03, AP-04, AP-07, AP-12 |
| `STATIC_EVIDENCE_ONLY` | AP-05; AP-08 is static/non-destructive only and remains excluded from destructive Recovery |
| `HUMAN_REVIEW_REQUIRED` | AP-09, AP-10, AP-13, AP-14; modeled reviewer procedures are complete coverage, not implementation blockers |

OWASP Top 10 2021 remains a reference lens: A01, A02, A05, A07, A08 and A09
are tested or mapped where applicable; A03 and A10 have no relevant safe
runtime scenario and remain explicitly not applicable/static rather than
being called PASS. Human WebAuthn, Enterprise/final-Owner and protected
secret ownership ceremonies are `HUMAN_REVIEW_REQUIRED — NON-BLOCKING FOR PR
#576`.

### 18.6 Schema, resource, sanitization, and cleanup

`VERIFIED SAFE`: the isolated Model A rehearsal constructed a migration-34
database, preserved an immutable disposable copy, applied migrations 0035 and
0036 to the disposable upgrade copy, restored only that copy, and started the
prior runtime against the restored migration-34 database. Integrity, foreign
keys, health/readiness and bounded startup checks passed. No live database,
Recovery repository, backup payload, user media or production state was
modified. The old runtime’s unknown-schema rejection remains fail-closed.

The exact candidate full run measured phone available memory about 2.80–2.99
GiB (approximately 39.8–40.5%), free storage about 136.7 GiB, battery 19–21%
at the captured late run, not charging, and temperature 34.2–34.3 C. System
load and per-process CPU/RSS were `UNAVAILABLE`; they are not represented as
zero. The one-heavy-scanner guard was true and the phone’s Trivy execution
retained exclusions for PhotoPrism media, Android shared storage, backup and
Recovery payloads, runtime state, generated/cache directories and other
repository-defined private data (`RUNTIME-VALIDATED`).

The candidate full cleanup was `PASS`: the synthetic principal was disabled
and revoked, all session IDs were invalidated, no active assurance run remained,
temporary continuity state was cleared, and the qualification runtime was
left under the explicit qualification flags pending the final cleanup after
the final exact-head run. The final exact-head cleanup is a required next
step, not inferred from this candidate capture (`UNVALIDATED`).

### 18.7 Command/output dossier index

The sanitized machine-readable evidence is outside Git under the operator-owned
paths recorded by the workflow, including:

* `/home/dj/.pocketlab-lite/evidence/runtime-security-assurance/qualification-20260915T052042Z-2285924/manifest.json`;
* `/home/dj/.pocketlab-lite/evidence/runtime-security-assurance/devpc-20260915T054600Z-2285924/standard/`;
* `/home/dj/.pocketlab-lite/evidence/runtime-security-assurance/devpc-20260915T054855Z-2285924/deep/`;
* `/tmp/pr576-bc1-nats2-fault.json`;
* `/tmp/pr576-bc1-full.json`.

The command ledger includes the operator bootstrap, tool install/check,
policy sync, authenticated preflight, Smoke, Standard, Adversarial, Deep,
fixed OPA/NATS/worker faults, client continuity, every external tool receipt,
and cleanup. Each entry records fixed/sanitized argv, execution lane, target,
version, exit/duration, bounded stdout/stderr summaries, finding/result
classification, and checksums. Raw scanner output and credentials are never
copied into this dossier (`VERIFIED`).

### 18.8 Readiness state before final projection

The Runtime Security Assurance implementation and its active tool contracts
are `IMPLEMENTED` and focused automated tests were `VALIDATED`. The candidate
runtime evidence closes authenticated Smoke/Standard/Adversarial admission,
OPA direct outage, NATS direct recovery, worker restart/resume, policy sync,
tool execution, normalized reporting, and the isolated schema rollback
contract. Deep is complete as an executed, truthful `PARTIAL` phone result;
its partial target is existing protected runtime-config posture rather than a
new harness execution error (`RUNTIME-VALIDATED`, `PARTIAL`).

The final documentation/source correction must now be published, consumed by
the phone, and qualified at its exact SHA. Only that final capture can support
the final PR recommendation (`UNVALIDATED`).

## 19. Follow-up deadline correction before final qualification

The exact `bc1c080d` requalification after the projection commit completed
the worker-owned Quick Security path in 922 seconds, but the Smoke lease was
900 seconds. The run therefore ended `PARTIAL` with `run_deadline_exceeded`
and correctly did not admit Standard. This was a bounded runtime-budget
observation, not a scanner finding or authorization failure (`RUNTIME-VALIDATED`).

The DEV-PC correction keeps the Smoke target at 180 seconds and changes only
the hard maximum to 1200 seconds. Standard remains 1800 seconds, Deep remains
7200 seconds, and Adversarial remains 600 seconds. A regression test asserts
the new Smoke contract. The worker still terminates and records `PARTIAL` on
an actual deadline, so the change adds evidence-backed execution margin and
does not weaken truthful timeout semantics (`IMPLEMENTED`, final exact-head
runtime qualification pending).
