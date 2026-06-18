#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "contracts/asyncapi/pocketlab-nats-jetstream.yaml"

COMMAND_SUBJECTS = [
    "pocketlab.commands.operation.execute",
    "pocketlab.commands.catalog.refresh",
    "pocketlab.commands.drift.scan",
    "pocketlab.commands.fleet.join",
    "pocketlab.commands.release.check",
    "pocketlab.commands.release.apply",
    "pocketlab.commands.health.check",
    "pocketlab.commands.security.scan",
    "pocketlab.commands.vault.rotate",
    "pocketlab.commands.vault.dynamic_secret",
    "pocketlab.commands.runbook.execute",
    "pocketlab.commands.runbook.approve",
    "pocketlab.commands.runbook.reject",
]

EVENT_SUBJECTS = [
    "pocketlab.events.operation.created",
    "pocketlab.events.operation.worker_claimed",
    "pocketlab.events.operation.log",
    "pocketlab.events.operation.succeeded",
    "pocketlab.events.operation.failed",
    "pocketlab.events.command.queued",
    "pocketlab.events.command.succeeded",
    "pocketlab.events.command.failed",
    "pocketlab.events.command.retry_scheduled",
    "pocketlab.events.command.dead_lettered",
    "pocketlab.events.catalog.refreshed",
    "pocketlab.events.drift.detected",
    "pocketlab.events.fleet.node_heartbeat",
    "pocketlab.events.fleet.node_telemetry",
    "pocketlab.events.health.checked",
    "pocketlab.events.telemetry.sampled",
    "pocketlab.events.security.finding",
    "pocketlab.events.vault.secret_rotated",
    "pocketlab.events.release.workflow.started",
    "pocketlab.events.release.stage.completed",
    "pocketlab.events.release.workflow.completed",
    "pocketlab.events.worker.heartbeat",
    "pocketlab.events.workflow.recovery_completed",
    "pocketlab.events.runbook.queued",
    "pocketlab.events.runbook.started",
    "pocketlab.events.runbook.approval_required",
    "pocketlab.events.runbook.approval_queued",
    "pocketlab.events.runbook.approved",
    "pocketlab.events.runbook.rejection_queued",
    "pocketlab.events.runbook.rejected",
    "pocketlab.events.runbook.resumed",
    "pocketlab.events.runbook.step_started",
    "pocketlab.events.runbook.step_succeeded",
    "pocketlab.events.runbook.step_failed",
    "pocketlab.events.runbook.succeeded",
    "pocketlab.events.runbook.failed",
]

AUDIT_SUBJECTS = [
    "pocketlab.audit.release.applied",
    "pocketlab.audit.security.policy_updated",
    "pocketlab.audit.vault.secret_rotated",
    "pocketlab.audit.runbook.executed",
    "pocketlab.audit.runbook.approved",
    "pocketlab.audit.runbook.rejected",
]

DLQ_SUBJECTS = [
    "pocketlab.dlq.original_subject",
]


def safe_name(subject: str) -> str:
    return subject.replace(".", "_").replace(">", "all").replace("{", "").replace("}", "")


def channel(subject: str, message_name: str) -> dict:
    return {
        "address": subject,
        "messages": {
            message_name: {
                "$ref": f"#/components/messages/{message_name}"
            }
        },
    }


def message(name: str, title: str, schema_ref: str) -> dict:
    return {
        "name": name,
        "title": title,
        "summary": title,
        "payload": {
            "$ref": schema_ref
        },
    }


def build_contract() -> dict:
    channels = {}
    messages = {}

    for subject in COMMAND_SUBJECTS:
        name = safe_name(subject)
        channels[subject] = channel(subject, name)
        messages[name] = message(name, f"Command: {subject}", "#/components/schemas/CommandEnvelope")

    for subject in EVENT_SUBJECTS:
        name = safe_name(subject)
        channels[subject] = channel(subject, name)
        messages[name] = message(name, f"Event: {subject}", "#/components/schemas/EventEnvelope")

    for subject in AUDIT_SUBJECTS:
        name = safe_name(subject)
        channels[subject] = channel(subject, name)
        messages[name] = message(name, f"Audit: {subject}", "#/components/schemas/EventEnvelope")

    for subject in DLQ_SUBJECTS:
        name = safe_name(subject)
        channels[subject] = channel(subject, name)
        messages[name] = message(name, f"DLQ: {subject}", "#/components/schemas/DeadLetterEnvelope")

    return {
        "asyncapi": "3.1.0",
        "info": {
            "title": "Pocket Lab NATS / JetStream Event Contract",
            "version": "2.3.0-phase12",
            "description": (
                "Pocket Lab uses NATS and JetStream as its durable command and event backbone. "
                "FastAPI publishes typed commands, workers consume them, and events are emitted "
                "for UI state, auditability, workflow recovery, retries, and dead-letter handling."
            ),
        },
        "defaultContentType": "application/json",
        "servers": {
            "pocketlabNats": {
                "host": "127.0.0.1:4222",
                "protocol": "nats",
                "description": "Local Pocket Lab NATS / JetStream runtime",
            }
        },
        "channels": channels,
        "components": {
            "messages": messages,
            "schemas": {
                "CommandEnvelope": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["operation_id"],
                    "properties": {
                        "operation_id": {"type": "string"},
                        "operation": {"type": "string"},
                        "target": {"type": "object", "additionalProperties": True},
                        "params": {"type": "object", "additionalProperties": True},
                        "correlation_id": {"type": "string"},
                    },
                },
                "EventEnvelope": {
                    "type": "object",
                    "additionalProperties": True,
                    "required": ["subject", "time"],
                    "properties": {
                        "event_id": {"type": "string"},
                        "operation_id": {"type": "string"},
                        "correlation_id": {"type": "string"},
                        "subject": {"type": "string"},
                        "status": {"type": "string"},
                        "time": {"type": "string", "format": "date-time"},
                        "message": {"type": "string"},
                        "payload": {"type": "object", "additionalProperties": True},
                    },
                },
                "DeadLetterEnvelope": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "original_subject": {"type": "string"},
                        "reason": {"type": "string"},
                        "attempts": {"type": "integer"},
                        "last_error": {"type": "string"},
                        "payload": {"type": "object", "additionalProperties": True},
                    },
                },
            },
        },
        "x-pocketlab-streams": {
            "POCKETLAB_COMMANDS": ["pocketlab.commands.>"],
            "POCKETLAB_EVENTS": ["pocketlab.events.>"],
            "POCKETLAB_AUDIT": ["pocketlab.audit.>"],
            "POCKETLAB_DLQ": ["pocketlab.dlq.>"],
        },
        "x-pocketlab-retry-policy": {
            "max_deliver": 5,
            "ack_wait_seconds": 60,
            "retry_base_seconds": 5,
            "retry_max_seconds": 300,
        },
        "x-pocketlab-redaction": {
            "sensitive_keys": ["token", "password", "secret", "api_key", "authorization", "private_key", "value"]
        },
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build_contract(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote AsyncAPI contract: {OUT}")


if __name__ == "__main__":
    main()
