# Security Assurance Taskfile reference

The commands in this page are copied from the source files
`tasks/Taskfile.lite.yml` and `tasks/Taskfile.docs.yml`. Run them from
`/home/dj/pocket-lab-lite` on the environment stated by the playbook. Task
variables are fixed inputs to the supported wrapper; they are not a generic
command interface.

## Harness identity and qualification startup

| Task | Wrapper | Environment / authority | Side effect |
| --- | --- | --- | --- |
| `lite:harness:profiles` | `harness.py profiles` | DEV PC/approved client; direct loopback | read-only profile manifest |
| `lite:harness:status` | `harness.py status` | DEV PC/phone loopback | read-only bounded posture |
| `lite:harness:verify-off` | `harness.py verify-off` | normal runtime loopback | read-only default-off assertion |
| `lite:harness:keygen` | `harness.py keygen --key-file` | approved client; `KEY_FILE` outside Git | creates local Ed25519 key, mode 0600 |
| `lite:harness:bootstrap` | `harness.py bootstrap --principal-id --key-file` | approved client; key-bound qualification grant | consumes one grant and creates session authority |
| `lite:harness:principal:create` | `harness.py principal-create ...` | manual operator provisioning | registers public principal; legacy compatibility path |
| `lite:harness:session:start` | `harness.py session-start ...` | approved client with registered principal/key | creates a short-lived signed session |
| `lite:qualification:start` | `start-qualification.sh` | operator-controlled qualification | legacy token-based startup; keep separate from normal startup |
| `lite:qualification:start:key-bound` | `start-qualification.sh --bootstrap-*` | operator + approved public key | enables key-bound qualification, non-destructive |
| `lite:qualification:start:key-bound:faults` | key-bound launcher plus fixed fault-control enablement | explicit qualification only | enables the registered non-destructive fault controls |

The private key is never a Taskfile value printed into output. The key-bound
launcher accepts only the public-key file for operator approval.

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
| `lite:security:assurance:report` | `security_assurance.py report <run-id>` | authenticated report capability | read one sanitized report |
| `lite:security:assurance:compare` | `security_assurance.py compare <run-id>` | authenticated report/baseline capability | read normalized baseline delta |
| `lite:security:assurance:tools:install` | `security_assurance_toolchain.py install` | DEV PC operator | installs/checks fixed managed tools outside Git |
| `lite:security:assurance:tools:check` | `security_assurance_toolchain.py check` | DEV PC | reports each tool as READY, NOT_APPLICABLE, or FAILED |
| `lite:security:assurance:tools:run` | `security_assurance_toolchain.py run <suite>` | DEV PC and approved phone tunnel | runs fixed static/live tool lane; no arbitrary args |
| `lite:security:assurance:qualify` | `security_assurance.py qualify ... --sync-policy ...` | approved client with key-bound startup | coordinated phone Smoke/Standard/Adversarial workflow with renewal/cleanup |
| `lite:security:assurance:qualify:full` | same workflow plus `--full` | approved client; explicit full intent | adds fixed DEV-PC Standard/Deep lanes |

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
