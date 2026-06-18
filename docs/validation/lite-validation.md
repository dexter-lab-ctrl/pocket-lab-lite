# Lite Validation

Pocket Lab Lite keeps the core Pocket Lab control-plane model while reducing the default runtime footprint. Validation should prove that the Lite API, Lite UI, Lite bootstrap profile, and documentation build remain healthy without starting the heavyweight observability stack by default.

## What is validated

The Lite validation path checks:

- FastAPI imports and readiness routes;
- `/api/lite/*` read endpoints;
- fail-closed behavior for unsupported or risky Lite actions;
- `--profile lite` and `--lite` bootstrap selection;
- Lite bootstrap dry-run behavior;
- frontend production build;
- MkDocs strict build.

## Lite bootstrap checks

Run:

```bash
bash scripts/dev/check-lite-bootstrap.sh
```

Expected result:

```text
Bootstrap script syntax checks passed
Lite bootstrap profile checks passed
```

The check confirms that `install_proot_ubuntu` is skipped in Lite profile planning and that `--lite` selects `Profile: lite`.

## Lite API checks

Run:

```bash
bash scripts/dev/check-lite-api.sh
```

Expected result:

```text
Lite API checks passed
```

This uses the FastAPI test client. It does not require a live Android device or running NATS service.

## Full Lite local validation

Run:

```bash
task lite:check
```

or, without Taskfile:

```bash
bash scripts/dev/check-lite.sh
```

Expected result:

```text
Pocket Lab Lite validation passed
```

## Manual runtime validation on Android / Termux

After the Lite bootstrap profile is ready on a device, validate with:

```bash
cd ~/pocket-lab-lite/pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched
bash scripts/bootstrap.sh --profile lite --list
bash scripts/bootstrap.sh --profile lite
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/ready
curl -s http://127.0.0.1:8080/api/lite/status
pm2 status
```

In Lite mode, PM2 should not show the heavyweight observability services:

```text
pocket-gatus
loki-kms
promtail-agent
prometheus-db
grafana-ui
```

## Validation boundaries

These checks validate local source, contracts, frontend build, docs, and dry-run bootstrap behavior. They do not prove live Android service startup until run on an actual Termux device.
