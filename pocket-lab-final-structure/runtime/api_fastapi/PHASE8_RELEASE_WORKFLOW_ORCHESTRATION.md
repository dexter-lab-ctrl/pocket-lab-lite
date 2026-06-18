# Phase 8 — Event-orchestrated Release Workflow

Phase 8 turns Pocket Lab release check/apply into a staged event-driven workflow.

## Runtime flow

```text
POST /api/release/self-update/check|apply
  -> action_queue.submit_domain_command()
  -> pocketlab.commands.release.check|apply
  -> worker/domain handler
  -> release_orchestrator.py
  -> pocketlab.events.release.*
  -> /ws/events and frontend LiveEventPanel
```

## Release apply stages

1. `metadata_fetch` — checks configured release metadata.
2. `prepare` — creates a rollback/backup snapshot via `release_prepare`.
3. `gitops_synced` — synchronizes local GitOps state via `release_sync`.
4. `catalog_refreshed` — refreshes Apps & Services catalog state.
5. `blueprint_deployed` — applies the release blueprint via `release_deploy`.
6. `drift_verified` — verifies desired state via `release_verify`.
7. `health_verified` — checks Health Engine, Fleet health, and telemetry.
8. `pwa_refresh_ready` — marks frontend refresh readiness.

## Event subjects

- `pocketlab.events.release.workflow.started`
- `pocketlab.events.release.stage.started`
- `pocketlab.events.release.stage.completed`
- `pocketlab.events.release.stage.failed`
- `pocketlab.events.release.gitops_synced`
- `pocketlab.events.release.catalog_refreshed`
- `pocketlab.events.release.blueprint_deployed`
- `pocketlab.events.release.drift_verified`
- `pocketlab.events.release.health_verified`
- `pocketlab.events.release.pwa_refresh_ready`
- `pocketlab.events.release.applied`
- `pocketlab.events.release.workflow.completed`
- `pocketlab.events.release.workflow.failed`
- `pocketlab.audit.release.applied`

## State

The latest orchestration state is persisted in:

```text
$POCKETLAB_STATE_DIR/release_orchestration.json
```

`GET /api/release/self-update/status` includes this state under `orchestration`.

## UX

Simple Mode receives plain progress updates like “Update step started” and “Update workflow completed”. Professional Mode sees stage IDs, command IDs, job IDs, and raw payloads in advanced details.
