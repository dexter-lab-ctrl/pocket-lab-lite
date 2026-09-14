# Runtime Security Assurance Qualification Dossier

Status: `PARTIAL` / `KEEP DRAFT` at the final continuation evidence point. This
dossier records the bounded qualification and supply-chain work performed for
PR #576. It intentionally separates `RUNTIME-VALIDATED` Android/Termux
observations from `VALIDATED` DEV-PC/CI tool evidence and from
`UNVALIDATED`, `BLOCKED`, `UNSUPPORTED`, and `DEFERRED` scope.

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
| Feature source at the final authenticated phone qualification | `0cfe3978aba4848934b85c4ff2cd124c611e5b11` (`VERIFIED`) |
| Feature source at the isolated rollback rehearsal | `3f4f277de5fc8c99d01b0d07baa7376b608d1bd7` (`VERIFIED`; migration/runtime path unchanged by later client/test-only fixes) |
| Latest published DEV-PC supply-chain capture | `cfe3168e05f25483410217bb21bf711f80db596e` (`VERIFIED`; complete capture later promoted from this source revision) |
| PR | #576, open, draft, and mergeable at `0cfe3978aba4848934b85c4ff2cd124c611e5b11` (`VERIFIED`; exact-head CI rechecked before publication) |
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
| Assurance run | Suite-owned durable lease; Smoke 900s, Standard 1800s, Deep 7200s, Adversarial 600s (`IMPLEMENTED`, source/tests) |

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

## 5. Tool installation and execution evidence

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

## 6. Runtime qualification results

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
