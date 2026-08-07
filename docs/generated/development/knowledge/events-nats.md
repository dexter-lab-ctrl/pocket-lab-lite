---
title: "NATS and event encyclopedia"
description: "Sanitized subject/event knowledge from the generated AsyncAPI contract."
generated: true
audience: knowledgebase
confidence: generated
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 1
---

# NATS and event encyclopedia

Credentials are never included. Incomplete delivery semantics remain explicitly incomplete.

| Subject | Domain | Publishers | Consumers | Delivery | Durability | Retry |
| --- | --- | --- | --- | --- | --- | --- |
| `pocketlab.commands` | unknown | workflow_engine.py | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.catalog.refresh` | apps | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.drift.apply` | drift | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.drift.approve` | drift | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.drift.ignore` | drift | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.drift.preview` | drift | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.drift.rescan` | drift | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.drift.scan` | drift | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.drift.{action}` | drift | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.fleet.join` | devices | lite_invites.py | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.fleet.save_tailscale_key` | devices | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.health.check` | health | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.app.backup.create` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.app.backup.transfer` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.app.media` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.app.repair` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.app.restore.preview` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.app.safety` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.app.update.check` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.backup.create` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.backup.verify` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.catalog.install` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.database.backup` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.database.backup.verify` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.database.restore` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.database.restore.preview` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.device.restart` | devices | FastAPI | node agent | JetStream durable command | — | bounded command lifecycle |
| `pocketlab.commands.lite.maintenance.checkpoint` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.maintenance.retention` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.restore.apply` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.restore.preview` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.security.app_scan` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.lite.security.scan` | security | FastAPI | pocket-worker | JetStream durable pull | pocketlab_command_worker_v1 | bounded max-deliver and stale-run recovery |
| `pocketlab.commands.node` | node | pocketlab_worker.py | pocketlab_worker.py | incomplete | incomplete | incomplete |
| `pocketlab.commands.node.all` | node | — | pocketlab_node_agent.py | incomplete | incomplete | incomplete |
| `pocketlab.commands.node.all.{command.replace` | node | fleet.py | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.node.{node_id}` | node | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.node.{node_id}.{command.replace` | node | fleet.py | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.node.{normalized_node_id}.agent.restart` | node | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.node.{self.node_id}` | node | — | pocketlab_node_agent.py | incomplete | incomplete | incomplete |
| `pocketlab.commands.operation.execute` | operation | action_queue.py, pocketlab_worker.py, reliability.py | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.release.apply` | release | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.release.check` | release | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.runbook.approve` | runbook | action_queue.py, pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.runbook.execute` | runbook | action_queue.py | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.runbook.reject` | runbook | action_queue.py, pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.security.configure_opa` | security | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.security.scan` | security | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.unknown` | unknown | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.vault.dynamic_secret` | vault | — | — | incomplete | incomplete | incomplete |
| `pocketlab.commands.vault.rotate` | vault | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events` | unknown | — | nats_bus.py | incomplete | incomplete | incomplete |
| `pocketlab.events.api.started` | api | main.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.api.stopped` | api | main.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.catalog.refresh_started` | apps | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.catalog.refreshed` | apps | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.command.dead_lettered` | command | nats_bus.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.command.deferred` | command | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.command.failed` | command | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.command.queued` | command | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.command.received` | command | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.command.retry_scheduled` | command | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.command.running` | command | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.command.succeeded` | command | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.command.worker_claimed` | command | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.drift.detected` | drift | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.drift.previewed` | drift | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.drift.scan_completed` | drift | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.drift.scan_started` | drift | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.drift.{action}` | drift | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.drift.{action}_started` | drift | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.bootstrap_blocked` | devices | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.config_updated` | devices | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.device_health_sampled` | devices | live_status.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.device_removed` | devices | fleet_registry.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.health_changed` | devices | live_status.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.health_sampled` | devices | live_status.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.invite_accepted` | devices | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.invite_created` | devices | domain_commands.py, lite_invites.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.invite_revoked` | devices | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.invite_started` | devices | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.node_` | devices | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.node_capabilities` | devices | pocketlab_node_agent.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.node_command_queued` | devices | fleet.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.node_command_result` | devices | pocketlab_node_agent.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.node_health` | devices | pocketlab_node_agent.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.node_heartbeat` | devices | pocketlab_node_agent.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.node_left` | devices | pocketlab_node_agent.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.node_profile` | devices | pocketlab_node_agent.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.node_seen` | devices | pocketlab_node_agent.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.node_supervisor` | devices | pocketlab_agent_supervisor.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.fleet.node_telemetry` | devices | pocketlab_node_agent.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.health.changed` | health | live_status.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.health.check_completed` | health | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.health.checked` | health | live_status.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.health.service_changed` | health | live_status.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.backup.completed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.backup.failed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.backup.started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.media.completed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.media.failed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.media.started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.media.updated` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.restore.preview_created` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.restore.preview_failed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.restore.preview_started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.update.check_completed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.update.check_failed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.update.check_started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.{event_prefix}.completed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.{event_prefix}.failed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.{event_prefix}.started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.app.{event_prefix}.updated` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.backup.failed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.backup.snapshot_created` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.backup.started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.backup.verified` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.backup.verify_failed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.backup.verify_started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.catalog.install_completed` | lite | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.catalog.install_failed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.catalog.install_started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.database.backup.started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.database.backup.verified` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.database.restore.preview_ready` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.database.restore.started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.database.restore.{event_suffix}` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.database.restore.{rollback_status}` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.restore.checkpoint_created` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.restore.completed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.restore.failed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.restore.health_validated` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.restore.preview_created` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.restore.preview_failed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.restore.preview_started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.restore.service_restart_checked` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.restore.started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.security.critical_found` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.security.scan.completed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.security.scan.started` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.security.tool_missing` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.lite.security.{tool}.completed` | lite | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.live_status.started` | live_status | live_status.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.live_status.stopped` | live_status | live_status.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.live_status.{name}_error` | live_status | live_status.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.manual` | manual | events.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.operation.created` | operation | action_queue.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.operation.failed` | operation | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.operation.log` | operation | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.operation.log.error` | operation | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.operation.log.warning` | operation | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.operation.previewed` | operation | operations.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.operation.snapshot` | operation | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.operation.status` | operation | websocket.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.operation.succeeded` | operation | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.operation.worker_claimed` | operation | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.release.applied` | release | release_orchestrator.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.release.available` | release | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.release.check_degraded` | release | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.release.current` | release | pocketlab_worker.py, release_orchestrator.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.release.stage.completed` | release | release_orchestrator.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.release.stage.failed` | release | release_orchestrator.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.release.stage.started` | release | release_orchestrator.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.release.workflow.completed` | release | release_orchestrator.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.release.workflow.failed` | release | release_orchestrator.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.release.workflow.started` | release | release_orchestrator.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.approval_queued` | runbook | action_queue.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.approval_required` | runbook | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.approved` | runbook | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.auto_approved` | runbook | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.failed` | runbook | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.queued` | runbook | action_queue.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.rejected` | runbook | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.rejection_queued` | runbook | action_queue.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.resumed` | runbook | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.started` | runbook | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.step_failed` | runbook | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.step_started` | runbook | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.step_succeeded` | runbook | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.runbook.succeeded` | runbook | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.security.evaluated` | security | security.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.security.finding` | security | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.security.log_query` | security | security.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.security.policy_updated` | security | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.security.scan_completed` | security | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.security.scan_started` | security | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.telemetry` | telemetry | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.telemetry.changed` | telemetry | live_status.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.telemetry.sampled` | telemetry | live_status.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.vault.lease_created` | vault | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.vault.secret_rotated` | vault | domain_commands.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.websocket.heartbeat` | websocket | — | — | incomplete | incomplete | incomplete |
| `pocketlab.events.worker.error` | worker | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.worker.heartbeat` | worker | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.worker.ignored` | worker | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.worker.maintenance_deferred` | worker | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.worker.started` | worker | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.worker.stopped` | worker | pocketlab_worker.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.workflow.dead_letter_replayed` | workflow | reliability.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.workflow.recovery_completed` | workflow | reliability.py | — | incomplete | incomplete | incomplete |
| `pocketlab.events.workflow.replay_requested` | workflow | workflow_engine.py | — | incomplete | incomplete | incomplete |
