# Server Phone Task Runtime

Pocket Lab Lite keeps two intentionally different Task environments:

```text
DEV PC / CI
  Python: repository .venv/bin/python
  state: .pocketlab-dev/state
  POCKETLAB_ENV: dev

Server Phone / Android-Termux
  Python: installed python3 (python fallback only when required)
  state: production launcher-owned $POCKETLAB_BASE_DIR/state
  normal environment: production, harness default-off
  explicit qualification environment: qualification
```

The root Taskfile remains a development Task environment. Only the bounded phone-side tasks below are routed through `scripts/dev/lite/task_runtime.py`, which detects Termux, resolves the installed runtime Python, and removes development-only Task variables before launching the runtime command.

## Supported Server Phone tasks

These commands no longer require `PYTHON=python3`:

```bash
task lite:harness:status
task lite:harness:profiles
task lite:harness:verify-off

task lite:qualification:start:key-bound \
  PRINCIPAL_ID=codex-security-assurance \
  PUBLIC_KEY_FILE=~/.pocketlab-qualification/codex-security-assurance.pub

task lite:qualification:start:key-bound:faults \
  PRINCIPAL_ID=codex-security-assurance \
  PUBLIC_KEY_FILE=~/.pocketlab-qualification/codex-security-assurance.pub
```

The `:faults` form remains an explicit opt-in for the checked-in non-destructive service-fault controls. It is not normal qualification startup.

## What the phone wrapper removes

On Termux only, the bounded wrapper removes development scratch/env variables before invoking a supported runtime command:

```text
STATE_DIR
VALIDATION_DIR
POCKETLAB_STATE_DIR
POCKETLAB_ENV
POCKETLAB_DEV_PYTHON
POCKETLAB_DEV_TMPDIR
POCKETLAB_ENVIRONMENT
```

This is deliberate. `start-dashboard.sh` must be allowed to derive:

```text
POCKETLAB_BASE_DIR = existing runtime base
POCKETLAB_STATE_DIR = $POCKETLAB_BASE_DIR/state
POCKETLAB_OPA_ACTIVE_POLICY_DIR = $POCKETLAB_STATE_DIR/opa/active
```

Normal Lite startup defaults `POCKETLAB_ENVIRONMENT=production` and `POCKETLAB_HARNESS_ENABLED=0`. The separate `start-qualification.sh` explicitly sets `POCKETLAB_ENVIRONMENT=qualification` and enables only the approved harness profile before delegating to the existing production launcher.

The wrapper never hard-codes an Android home directory, account name, IP address, FQDN, runtime secret, or fake `.venv`.

## Why the wrapper is bounded

Most Task commands are DEV-PC/CI development tasks and should continue using the repository virtual environment and `.pocketlab-dev` scratch tree. Making every task phone-aware would blur the production/development boundary. Only the commands explicitly documented above are supported as Server Phone Task entry points.

The approved client/DEV PC still owns key generation, signed bootstrap/session handling, tool-manager execution, sanitized report publication, MkDocs generation, and repository mutations.

## Verification

On the DEV PC:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q \
  tests/backend/test_lite_security_assurance_portability.py
```

On a published Server Phone candidate:

```bash
task lite:harness:status
task lite:harness:profiles
task lite:harness:verify-off

git status --short --branch
pm2 status
```

When qualification is explicitly launched, its startup output must show the runtime-owned state directory and must **not** show `.pocketlab-dev/state`. OPA must resolve under that runtime-owned state root, never `.pocketlab-dev/state/opa/active`.
