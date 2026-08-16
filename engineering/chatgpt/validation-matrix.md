# Pocket Lab Lite Validation Matrix

Use the smallest relevant validation first, then broaden according to change risk. Validation evidence must come from actual command output; do not infer PASS from the absence of a reported error.

## Universal hygiene

Run for every code/documentation change:

```bash
git diff --check
git status --short
```

Before commit, inspect the staged set:

```bash
git diff --cached --check
git diff --cached --stat
```

## Python changes

Focused syntax/import validation:

```bash
python3 -m py_compile <changed-python-files>
```

Focused tests:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q <relevant-tests>
```

Broaden to the owning task/suite when the focused test passes.

## Shell/bootstrap changes

```bash
bash -n <changed-shell-files>
```

Then run the repository-owned bootstrap/task checks relevant to the changed path. For production/bootstrap behavior, preserve Android/Termux and ARM64 assumptions and do not treat WSL2-only success as production proof.

## Frontend/UI/state changes

Minimum expected checks usually include:

```bash
npm run build
```

Then run relevant unit/state/browser tests from the repository. When the change affects rendered behavior, use the repo-owned Playwright configuration/tasks for desktop and mobile where applicable.

Validate truthful state semantics, safe error boundaries and no unexpected horizontal overflow/blank UI.

## FastAPI/API changes

Prefer focused backend tests first, then:

```bash
task lite:api:check
```

When API contracts change, also validate the applicable OpenAPI/parity/breaking-change/Schemathesis gates defined by current Taskfiles/CI.

Check:

- response/failure reason semantics;
- sanitization;
- no hidden execution in read APIs;
- UI/API parity where presentation uses the field;
- event/command evidence when actions are asynchronous.

## Node agent / supervisor / device recovery changes

Static/local checks should cover the changed Python/shell and backend contract tests. Runtime validation, when explicitly requested and safe, should inspect:

```bash
pm2 status
pm2 logs <process> --lines 80
```

Also validate, as relevant:

- node-agent NATS connectivity;
- supervisor PM2 state;
- fresh heartbeat after reconnect;
- secondary-device NATS connectivity;
- Tailscale/tailscaled status;
- Tailnet IPv4 readiness;
- NATS reachable over the intended Tailnet path.

Do not print env secrets or invite material.

## Device onboarding / identity changes

Test at minimum:

| Scenario | Expected behavior |
| --- | --- |
| unique valid device | allowed according to current approval model |
| case-only duplicate | blocked |
| separator-only duplicate | blocked |
| protected server host name | blocked |
| stale matching identity/record | handled explicitly, not silently duplicated |
| pending/accepted invite collision | blocked or explicitly resolved by source contract |
| another device's invite on enrolled device | blocked |
| identity mismatch | fail closed |
| identity mismatch env write | must not occur |
| identity mismatch PM2 restart | must not occur |
| blocked invite consumption | sanitized audit evidence produced |

## Documentation / generated artifacts

Never hand-edit generated output as the source fix. Change canonical inputs/generator, then:

```bash
task lite:docs:generate
task lite:docs:check
```

The Codebase Map must be the final repository projection after generators that mutate tracked outputs. When changing Codebase Map behavior, also run its focused generator/check/tests.

Useful focused pattern:

```bash
python3 scripts/docs/knowledge/generate_codebase_map.py generate
python3 scripts/docs/knowledge/generate_codebase_map.py check
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q tests/docs/test_codebase_map.py
```

For MkDocs/browser changes, also run the current strict MkDocs and Playwright documentation gates defined by the repository.

## Taskfile / CI ordering changes

When changing generator/task ordering:

1. run the focused regression test that encodes the ordering invariant;
2. run the full generation sequence;
3. immediately run the corresponding check sequence;
4. run generation twice when determinism is in question and compare working-tree state;
5. reproduce the CI command order as closely as practical.

For docs fixed-point checks:

```bash
task lite:docs:generate
git status --short > /tmp/pocketlab-status-before.txt
task lite:docs:generate
git status --short > /tmp/pocketlab-status-after.txt
diff -u /tmp/pocketlab-status-before.txt /tmp/pocketlab-status-after.txt
```

Expected for deterministic generation: no status difference caused by the second generation.

## Broad local gates

Use the repository's current Taskfile as authority. Common gates include:

```bash
task lite:check:quick
task lite:docs:check
task lite:check
```

Do not run the heaviest gate after every single edit; use focused tests during iteration and broad gates before PR/merge according to risk.

## Release/live qualification

Live/release checks require explicit user intent and current repo instructions. They may involve an isolated running stack and real Android/Termux verification. Do not claim desktop-only evidence proves Android runtime behavior.

Verify expected release artifacts using the current release workflow, including `dist.zip` when required.

## Evidence reporting

For every validation summary record:

```text
command
affected scope
result: PASS / FAIL / NOT RUN
important counts/output
known warnings
what the command does NOT prove
```

Warnings should be classified rather than ignored. A known benign warning is different from an uninvestigated warning.

## Failure workflow

When a validation fails:

1. stop claiming completion;
2. capture the first meaningful error;
3. identify the owning layer;
4. use Work specialists when multiple hypotheses/layers are plausible;
5. use Chat for the smallest fix/retest loop;
6. add a regression test when the failure reveals an invariant;
7. rerun the focused failing gate before broad suites.
