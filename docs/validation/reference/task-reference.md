# Security Assurance Taskfile reference

The commands in this page are copied from the source files
`tasks/Taskfile.lite.yml` and `tasks/Taskfile.docs.yml`. Run them from the
repository root on the environment stated by the playbook. Task variables are
fixed inputs to the supported wrapper; they are not a generic command
interface.

## Harness identity and qualification startup

| Task | Wrapper | Environment / authority | Side effect |
| --- | --- | --- | --- |
| `lite:harness:profiles` | bounded `task_runtime.py` → `harness.py profiles` | DEV PC/Server Phone loopback | read-only profile manifest; Termux resolves installed Python and scrubs DEV state |
| `lite:harness:status` | bounded `task_runtime.py` → `harness.py status` | DEV PC/Server Phone loopback | read-only bounded posture; Termux resolves installed Python and scrubs DEV state |
| `lite:harness:verify-off` | bounded `task_runtime.py` → `harness.py verify-off` | normal runtime loopback | read-only default-off assertion; no fake `.venv` required on Termux |
| `lite:harness:keygen` | `harness.py keygen --key-file` | approved client; `KEY_FILE` outside Git | creates local Ed25519 key, mode 0600 |
| `lite:harness:bootstrap` | `harness.py bootstrap --principal-id --key-file` | approved client; key-bound qualification grant | consumes one grant and creates session authority |
| `lite:harness:principal:create` | `harness.py principal-create ...` | manual operator provisioning | registers public principal; legacy compatibility path |
| `lite:harness:session:start` | `harness.py session-start ...` | approved client with registered principal/key | creates a short-lived signed session |
| `lite:qualification:start` | `start-qualification.sh` | operator-controlled qualification | legacy token-based startup; keep separate from normal startup |
| `lite:qualification:start:key-bound` | bounded `task_runtime.py` → `start-qualification.sh --bootstrap-*` | Server Phone operator + approved public key | scrubs DEV state then enables key-bound qualification, non-destructive |
| `lite:qualification:start:key-bound:faults` | bounded task runtime plus fixed fault-control enablement | explicit Server Phone qualification only | scrubs DEV state then enables registered non-destructive fault controls |

The private key is never a Taskfile value printed into output. The key-bound
launcher accepts only the public-key file for operator approval. On a Server
Phone, the bounded Task wrapper removes Taskfile development state/environment
before the production launcher derives its runtime state root and OPA active
policy path. See the Server Phone Task Runtime playbook.

The CLI also exposes `principal-revoke`, `session-status`, and `session-stop`;
they have no dedicated Taskfile wrappers in the current source. Use the exact
CLI forms in the command catalog when the supported cleanup flow calls for
them.

## Assurance admission and suites

| Task | Wrapper | Environment / authority | Duration/side effect |
| --- | --- | --- | --- |
| `lite:security:assurance:check` | `security_assurance.py check` | DEV PC/approved client | read-only registry check |
| `lite:security:assurance:preflight` | `security_assurance.py preflight <suite>` | authenticated approved client | bounded readiness/admission checks |
| `lite:security:assurance:policy-sync` | `security_assurance.py policy-sync --wait-seconds` | authenticated qualification session | requests supported policy-source synchronization |
| `lite:security:assurance:smoke` | `security_assurance.py run smoke` | authenticated assurance session | bounded normal Smoke run; worker-owned |
| `lite:security:assurance:standard` | `security_assurance.py run standard` | authenticated assurance session | normal Standard run; worker-owned |
| `lite:security:assurance:deep` | `security_assurance.py run deep` | explicit manual qualification session | resource-heavy Deep run; worker/static/live lanes |
| `lite:security:assurance:adversarial` | `security_assurance.py run adversarial` | explicit qualification-only session | fixed safe negative/adversarial checks |
| `lite:security:assurance:fault` | `security_assurance.py fault <id>` | explicit fault-control capability | one registered bounded service-fault control |
| `lite:security:assurance:scenario` | `security_assurance.py scenario <id>` | authenticated scenario capability | one registered Standard scenario |

Defaults are source-defined: `SUITE=smoke` for preflight,
`WAIT_SECONDS=120` for policy sync, and `SUITE=deep` for the DEV-PC tool lane.
Use only IDs listed in the current registries.

## Reports and tool lanes

| Task | Wrapper | Environment / authority | Result |
| --- | --- | --- | --- |
| `lite:security:assurance:report` | `security_assurance.py report <run-id>` | authenticated report capability | read one sanitized runtime report bundle |
| `lite:security:assurance:report:generate` | `security_assurance_report.py generate --qualification-id` | approved DEV PC/client with report capability | validates terminal normalized/sanitized evidence and builds deterministic report identity; no publication |
| `lite:security:assurance:report:check` | `security_assurance_report.py check --qualification-id` | DEV PC/CI | validates one published Markdown/JSON/index set, redaction, link and count reconciliation |
| `lite:security:assurance:report:publish` | `security_assurance_report.py publish --qualification-id` | approved DEV PC/client with report capability | stages, redaction-checks and atomically publishes Markdown + sanitized companion JSON + index |
| `lite:security:assurance:reports:index` | `security_assurance_report.py index` | DEV PC/CI | deterministically rebuilds only the generated report index from sanitized companion JSON |
| `lite:security:assurance:compare` | `security_assurance.py compare <run-id>` | authenticated report/baseline capability | read normalized baseline delta |
| `lite:security:assurance:tunnel:check` | `security_assurance_runtime_tunnel.py check` | DEV PC using managed SSH alias | validates fixed runtime-derived Server Phone and Tailnet tunnel facts |
| `lite:security:assurance:tunnel:hold` | `security_assurance_runtime_tunnel.py hold` | DEV PC using managed SSH alias | holds fixed assurance forwards using runtime-derived addresses |
| `lite:security:assurance:tools:install` | `security_assurance_toolchain.py install` | DEV PC operator | installs/checks fixed managed tools outside Git |
| `lite:security:assurance:tools:check` | `security_assurance_toolchain.py check` | DEV PC | reports each tool as READY, NOT_APPLICABLE, or FAILED |
| `lite:security:assurance:tools:run` | `security_assurance_toolchain.py run <suite>` | DEV PC and approved phone tunnel | runs fixed static/live tool lane; no arbitrary args |
| `lite:security:assurance:qualify` | `security_assurance.py qualify ... --sync-policy ...` | approved client with key-bound startup | coordinated phone Smoke/Standard/Adversarial workflow with renewal/cleanup |
| `lite:security:assurance:qualify:full` | same workflow plus `--full` | approved client; explicit full intent | adds fixed DEV-PC Standard/Adversarial/Deep lanes |

Report publication is repository-owned and must not be used to edit tracked
source on the Server Phone. The report publisher consumes the existing
normalized/sanitized report API only; it does not parse raw scanner output.

## Documentation gate

| Task | Wrapper | Environment | Side effect |
| --- | --- | --- | --- |
| `lite:docs:security-assurance:check` | `scripts/docs/check_security_assurance_playbooks.py` and its focused test | DEV PC/CI | static registry/source/link drift check only |
| `lite:docs:check` | repository documentation gates, including the assurance check | DEV PC/CI | validation; generated docs remain source-owned |

`lite:check` is the broader Lite validation gate and may be used at final
exact-head qualification. It does not replace the authenticated runtime
assurance suites.

## Return semantics

The assurance CLI preserves distinct terminal meanings: success returns `0`, a
security/suite failure returns the implementation's FAIL code, partial work
returns its PARTIAL code, and blocked admission returns its BLOCKED code.
Client argument errors remain validation failures. Use the
[result-status reference](result-status-reference.md) and the actual sanitized
CLI output rather than guessing from duration or process state.
