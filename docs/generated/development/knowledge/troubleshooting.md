---
title: "Troubleshooting decision trees"
description: "Generated safe troubleshooting paths from structured knowledge metadata."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Troubleshooting decision trees

## Node agent stopped

**Check**
- GET /api/lite/fleet
- Inspect supervisor state before manual intervention

**Recovery**
- Allow supervisor recovery when present
- Use explicit repair guidance when the supervisor is unavailable

## FastAPI unavailable

**Check**
- GET /api/lite/status
- Inspect pocket-api in the PM2 runtime view

**Recovery**
- Recover the API process through the documented server-host process manager

## App installation failure

**Check**
- Check App Catalog action state, worker result, and sanitized troubleshooting summary.
- Check same-origin route readiness only after install execution reaches a terminal state.

**Recovery**
- Retry only through the FastAPI-owned app action after the backend reports it safe; do not run install commands from the UI.

## Backup failure

**Check**
- GET /api/lite/recovery/summary

**Recovery**
- Verify repository readiness and backup state before retrying

## Caddy unavailable

**Check**
- Check the Caddy process state through the approved service status path.
- Validate the tracked Caddy configuration before any restart.

**Recovery**
- Use the existing Caddy restart helper only after configuration validation; keep same-origin routing intact.

## Device joining, waiting, or repairing

**Check**
- Check invite lifecycle, last heartbeat, command progress, and supervisor status.
- Distinguish joining/waiting from an enrolled offline device.

**Recovery**
- Allow guarded enrollment/recovery to converge; use explicit repair/rejoin only for verified identity or enrollment failure.

## Device offline or reconnecting

**Check**
- GET /api/lite/fleet
- Check Tailnet and NATS reachability through documented diagnostics

**Recovery**
- Distinguish disconnected from stopped before restarting anything

## Documentation drift

**Check**
- Run the deterministic documentation check tasks
- Run strict MkDocs build

**Recovery**
- Regenerate from canonical sources; do not hand-edit generated truth

## Release tag missing locally

**Check**
- Compare the promoted release binding with local Git tag availability.
- Confirm the tag exists in verified remote/session metadata before fetching it.

**Recovery**
- Use the existing promotion preflight safe remediation to fetch only the verified missing tag; do not fabricate a tag.

## NATS or JetStream unavailable

**Check**
- Inspect NATS readiness through backend diagnostics
- Confirm the worker reports messaging connectivity

**Recovery**
- Restore NATS reachability before retrying backend-owned commands

## Parity or browser capture failure

**Check**
- Run parity evidence checks and inspect the failing evidence lane

**Recovery**
- Recapture only the failed bounded lane; do not promote incomplete evidence

## PhotoPrism unavailable

**Check**
- GET /api/lite/catalog
- Inspect same-origin app route readiness

**Recovery**
- Use backend-owned Check app or Repair actions; do not run app process control in the browser

## Recovery projection stale

**Check**
- Check Recovery freshness and the authoritative database recovery projection.
- Confirm whether the degradation reason is projection_too_old.

**Recovery**
- Refresh/reconcile through the existing backend projection path; require a fresh restore preview before destructive restore.

## Release or rollback issue

**Check**
- GET /api/lite/release
- Verify release binding and post-switch health

**Recovery**
- Use the last-known-good rollback path only after release verification fails

## Remote access not ready

**Check**
- GET /api/lite/fleet
- Inspect sanitized remote-access readiness

**Recovery**
- Restore tailscaled, Tailnet address, and NATS reachability in that order

## Restore blocked or preview stale

**Check**
- GET /api/lite/recovery/summary

**Recovery**
- Refresh Recovery state and create a fresh preview before destructive restore

## Runtime evidence or release binding mismatch

**Check**
- Run lite:evidence:runtime:preflight with the explicit release tag

**Recovery**
- Resolve the real source/release/evidence mismatch; do not rewrite tags or hide semantic drift

## Security scan failure

**Check**
- GET /api/lite/security/summary
- GET /api/lite/security/progress

**Recovery**
- Use the saved backend troubleshooting state and explicit retry after terminal failure

## Stale runtime evidence

**Check**
- Check promoted evidence timestamp, source commit, and release binding.
- Check whether semantic parity and operational health are being reported independently.

**Recovery**
- Capture a new sanitized runtime projection and explicitly promote it only after validation; never track transient raw capture.

## Supervisor stopped

**Check**
- Check supervisor and node-agent PM2 status separately.
- Confirm the device is not merely disconnected while the agent process is running.

**Recovery**
- Restore the supervisor through the approved PM2/runtime startup path, then verify a fresh heartbeat.

## Tailscale unavailable

**Check**
- Check tailscaled status and whether a Tailnet IPv4 is available.
- Check NATS reachability over the configured secondary/Tailnet URL.

**Recovery**
- Start tailscaled only through the existing safe startup helper and re-check remote-access readiness.

## Pocket Lab UI unavailable

**Check**
- GET /api/lite/status through the configured Pocket Lab origin
- Inspect Caddy service state through the documented runtime topology

**Recovery**
- Restore Caddy/PWA serving before attempting write actions

## Worker stopped

**Check**
- Check PM2 worker status and sanitized worker/NATS health.
- Confirm the durable command consumer is healthy before retrying a write.

**Recovery**
- Use the existing supervisor/PM2 recovery path; do not queue commands from the browser.
