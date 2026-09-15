# Historical command completeness mapping

This appendix prevents the documentation restructuring from silently dropping
an invocation from the original validation dossiers. The original files were
read in full and are preserved or linked as follows:

| Original dossier | Current location/status |
| --- | --- |
| `lite-validation.md` | current operating validation page; legacy commands below remain mapped |
| `qualification-maintenance-harness.md` | current harness overview; historical examples are mapped to the current key-bound flow |
| `runtime-security-assurance-harness.md` | current assurance architecture overview; current commands are in the catalog |
| `runtime-security-assurance-qualification.md` | stable pointer; full historical dossier is under `evidence-history/` |

## Extracted command mapping

| Source dossier | Extracted form | Canonical command ID | Status | Replacement/playbook |
| --- | --- | --- | --- | --- |
| `lite-validation.md` | `bash scripts/dev/check-lite-bootstrap.sh` | SA-LEGACY-001 | ACTIVE | [Getting started](../security-assurance/02-getting-started.md) |
| `lite-validation.md` | `bash scripts/dev/check-lite-api.sh` | SA-LEGACY-002 | ACTIVE | [Getting started](../security-assurance/02-getting-started.md) |
| `lite-validation.md` | `task lite:check` | SA-LEGACY-003 | ACTIVE | [Exact-head qualification](../security-assurance/18-exact-head-release-qualification.md) |
| `lite-validation.md` | `bash scripts/dev/check-lite.sh` | SA-LEGACY-004 | ACTIVE | [Getting started](../security-assurance/02-getting-started.md) |
| `lite-validation.md` | `npm run build-storybook` | SA-LEGACY-005 | ACTIVE | repository Lite validation |
| `lite-validation.md` | `npm run test:phase9:qualification` | SA-LEGACY-006 | ACTIVE | repository Lite validation |
| `lite-validation.md` | `npm run test:a11y` | SA-LEGACY-007 | ACTIVE | repository Lite validation |
| `lite-validation.md` | `npm run test:a11y:states` | SA-LEGACY-008 | ACTIVE | repository Lite validation |
| `lite-validation.md` | `npm run test:content-stress` | SA-LEGACY-009 | ACTIVE | repository Lite validation |
| `lite-validation.md` | `npm run test:visual` | SA-LEGACY-010 | ACTIVE | repository Lite validation |
| `lite-validation.md` | `npm run test:visual:states` | SA-LEGACY-011 | ACTIVE | repository Lite validation |
| `lite-validation.md` | `npm run test:visual:overlays` | SA-LEGACY-012 | ACTIVE | repository Lite validation |
| `lite-validation.md` | `npm run test:mock-regression` | SA-LEGACY-013 | ACTIVE | repository Lite validation |
| `lite-validation.md` | `npm run test:visual:states -- --update-snapshots` | SA-LEGACY-014 | SUPERSEDED | use the current package-script snapshot workflow; never update snapshots in qualification evidence |
| `lite-validation.md` | `npm run test:visual:overlays -- --update-snapshots` | SA-LEGACY-015 | SUPERSEDED | use the current package-script snapshot workflow; never update snapshots in qualification evidence |
| `lite-validation.md` | `cd ~/pocket-lab-lite/pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched` | SA-LEGACY-016 | HISTORICAL | current checkout/task working-directory instructions |
| `lite-validation.md` | `bash scripts/bootstrap.sh --profile lite --list` | SA-LEGACY-017 | HISTORICAL | current supported Lite launcher and [prerequisites](../security-assurance/03-environment-prerequisites.md) |
| `lite-validation.md` | `bash scripts/bootstrap.sh --profile lite` | SA-LEGACY-018 | HISTORICAL | current supported Lite launcher; do not use an obsolete checkout path |
| `lite-validation.md` | `curl -s http://127.0.0.1:8080/health` | SA-LEGACY-019 | ACTIVE | [Preflight](../security-assurance/06-preflight.md); readiness is separately required |
| `lite-validation.md` | `curl -s http://127.0.0.1:8080/ready` | SA-LEGACY-020 | ACTIVE | [Preflight](../security-assurance/06-preflight.md) |
| `lite-validation.md` | `curl -s http://127.0.0.1:8080/api/lite/status` | SA-LEGACY-021 | ACTIVE | normal Lite status/readiness inspection |
| `lite-validation.md` | `pm2 status` | SA-LEGACY-022 | ACTIVE | bounded service inspection; PM2 online is not readiness |
| `qualification-maintenance-harness.md` | `python3 scripts/dev/lite/harness.py keygen` | SA-AUTH-001 | SUPERSEDED | use `task lite:harness:keygen KEY_FILE=<outside-repository-path>` with an explicit key path |
| `qualification-maintenance-harness.md` | historical provisioning-token environment assignment (value omitted) | SA-AUTH-007 | PROHIBITED | use operator-approved key-bound startup; legacy compatibility remains server-owned and secrets stay outside documentation |
| `qualification-maintenance-harness.md` | `task lite:harness:principal:create` | SA-AUTH-003 | ACTIVE | [Authentication](../security-assurance/05-harness-bootstrap-auth.md) |
| `qualification-maintenance-harness.md` | `POST /api/lite/harness/principals` | SA-API-001 | ACTIVE | [API reference](api-reference.md) |
| `qualification-maintenance-harness.md` | `POST /api/lite/harness/challenge` | SA-API-002 | ACTIVE | [API reference](api-reference.md) |
| `qualification-maintenance-harness.md` | `sign(exact signing_payload)` | SA-AUTH-005 | ACTIVE | client signs only the server-returned canonical payload |
| `qualification-maintenance-harness.md` | `POST /api/lite/harness/session` | SA-API-003 | ACTIVE | [API reference](api-reference.md) |
| `qualification-maintenance-harness.md` | `GET /api/lite/status` | SA-LEGACY-021 | ACTIVE | normal Lite status; not harness authority |
| `qualification-maintenance-harness.md` | `DELETE /api/lite/harness/session/{id}` | SA-API-004 | SUPERSEDED | current route is `DELETE /api/lite/harness/session/{session_id}` |
| `qualification-maintenance-harness.md` | `task lite:harness:profiles` | SA-ENV-002 | ACTIVE | [Task reference](task-reference.md) |
| `qualification-maintenance-harness.md` | `task lite:harness:status` | SA-ENV-002 | ACTIVE | [Task reference](task-reference.md) |
| `qualification-maintenance-harness.md` | `task lite:harness:verify-off` | SA-CLEANUP-001 | ACTIVE | [Cleanup](../security-assurance/16-cleanup-default-off.md) |
| `qualification-maintenance-harness.md` | historical shell flag cleanup assignments | SA-CLEANUP-002 | SUPERSEDED | use `task lite:harness:verify-off` and sanitized runtime status |
| `qualification-maintenance-harness.md` | `python3 scripts/dev/lite/harness.py verify-off` | SA-CLEANUP-003 | SUPERSEDED | use `task lite:harness:verify-off` |
| `runtime-security-assurance-harness.md` | `GET /api/lite/harness/security-assurance/capabilities` | SA-API-010 | ACTIVE | [API reference](api-reference.md) |
| `runtime-security-assurance-harness.md` | `GET /api/lite/harness/security-assurance/suites` | SA-API-011 | ACTIVE | [API reference](api-reference.md) |
| `runtime-security-assurance-harness.md` | `GET /api/lite/harness/security-assurance/preflight?suite_id=smoke` | SA-API-012 | ACTIVE | [Preflight](../security-assurance/06-preflight.md) |
| `runtime-security-assurance-harness.md` | `POST /api/lite/harness/security-assurance/runs` | SA-API-013 | ACTIVE | [Run lifecycle](../security-assurance/07-smoke-playbook.md) |
| `runtime-security-assurance-harness.md` | `GET /api/lite/harness/security-assurance/runs` | SA-API-014 | ACTIVE | [API reference](api-reference.md) |
| `runtime-security-assurance-harness.md` | `GET /api/lite/harness/security-assurance/runs/{run_id}` | SA-API-015 | ACTIVE | [Evidence/reporting](../security-assurance/15-evidence-reporting.md) |
| `runtime-security-assurance-harness.md` | `GET /api/lite/harness/security-assurance/runs/{run_id}/findings` | SA-API-016 | ACTIVE | [Findings](../security-assurance/14-findings-remediation.md) |
| `runtime-security-assurance-harness.md` | `GET /api/lite/harness/security-assurance/runs/{run_id}/events?after=0` | SA-API-017 | ACTIVE | [API reference](api-reference.md) |
| `runtime-security-assurance-harness.md` | `POST /api/lite/harness/security-assurance/runs/{run_id}/resume` | SA-API-018 | ACTIVE | [Fault recovery](../security-assurance/11-fault-recovery-playbook.md) |
| `runtime-security-assurance-harness.md` | `GET /api/lite/harness/security-assurance/runs/{run_id}/report` | SA-API-019 | ACTIVE | [Evidence/reporting](../security-assurance/15-evidence-reporting.md) |
| `runtime-security-assurance-harness.md` | `POST /api/lite/harness/security-assurance/runs/{run_id}/cancel` | SA-API-020 | ACTIVE | [Fault recovery](../security-assurance/11-fault-recovery-playbook.md) |
| `runtime-security-assurance-harness.md` | `task lite:security:assurance:check` | SA-REG-001 | ACTIVE | [Toolchain](../security-assurance/04-toolchain-installation.md) |
| `runtime-security-assurance-harness.md` | `python3 -m py_compile pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_assurance.py` | SA-VALIDATE-001 | ACTIVE | local focused validation |
| `runtime-security-assurance-harness.md` | `task lite:docs:check` | SA-DOCS-001 | ACTIVE | [Exact-head qualification](../security-assurance/18-exact-head-release-qualification.md) |
| `runtime-security-assurance-qualification.md` | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/backend/test_lite_security_assurance.py tests/backend/test_lite_harness.py tests/backend/test_lite_worker_recovery.py` | SA-VALIDATE-002 | ACTIVE | current focused backend validation |

## Mapping policy

Every original form is mapped. `HISTORICAL` means the form is retained for
audit lineage but is not a current operating instruction;
`SUPERSEDED` identifies the current supported replacement; `PROHIBITED` means
the historical form must not be copied because it would expose or mishandle
authority. The current command catalog and playbooks contain the supported
syntax and implementation source.
