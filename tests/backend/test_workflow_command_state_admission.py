"""Regression coverage for command-state event admission.

The workflow event journal and liveness paths are separate from persisted
command-state identity. These tests never operate on a production database.
"""
from __future__ import annotations

import json
import sqlite3

import pytest

from pocket_lab_test_utils import ensure_runtime_path

ensure_runtime_path()


@pytest.fixture
def command_writer():
    from api_fastapi.services.workflow_projection_process import WorkflowProjectionProcess

    writer = object.__new__(WorkflowProjectionProcess)
    writer.serialized_bytes_max = 65536
    writer.generation = 1
    writer.database_instance = "unit-test"
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE workflow_command_state (
            command_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            subject TEXT NOT NULL,
            event_type TEXT NOT NULL,
            command_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_at_epoch_ms INTEGER NOT NULL,
            process_generation INTEGER NOT NULL,
            database_instance TEXT NOT NULL
        )
        """
    )
    yield writer, conn
    conn.close()


def event(kind, *, data=None, subject="pocketlab.events.worker", event_id="event-1"):
    return {
        "id": event_id,
        "type": kind,
        "subject": subject,
        "trace_id": "trace-1",
        "time": "2026-11-14T00:00:00Z",
        "workflow_id": "wf-1",
        "data": data or {},
    }


@pytest.mark.parametrize("kind", ["worker.heartbeat", "worker.started"])
def test_worker_liveness_never_creates_command_even_with_misleading_subject(command_writer, kind):
    writer, conn = command_writer
    writer._record_command(conn, event(kind, data={
        "subject": "pocketlab.commands.test", "command_id": "misleading",
    }))
    assert conn.execute("SELECT COUNT(*) FROM workflow_command_state").fetchone()[0] == 0


@pytest.mark.parametrize("kind", ["worker.error", "worker.ignored", "worker.maintenance_deferred"])
def test_uncorrelated_worker_event_is_not_a_command(command_writer, kind):
    writer, conn = command_writer
    writer._record_command(conn, event(kind, data={"subject": "pocketlab.commands.test"}))
    assert conn.execute("SELECT COUNT(*) FROM workflow_command_state").fetchone()[0] == 0


def test_correlated_worker_error_retains_explicit_command_identity(command_writer):
    writer, conn = command_writer
    writer._record_command(conn, event("worker.error", data={
        "command_id": "cmd-1", "subject": "pocketlab.commands.test", "error": "safe-test-error",
    }))
    assert conn.execute("SELECT command_id FROM workflow_command_state").fetchone()[0] == "cmd-1"


@pytest.mark.parametrize("kind", ["command.queued", "command.succeeded", "command.failed", "command.dead_lettered"])
def test_command_transitions_remain_persisted(command_writer, kind):
    writer, conn = command_writer
    writer._record_command(conn, event(kind, subject="pocketlab.commands.test",
                                       data={"command_id": "cmd-1"}))
    assert conn.execute("SELECT event_type FROM workflow_command_state").fetchone()[0] == kind


def test_fleet_request_remains_command_state(command_writer):
    writer, conn = command_writer
    writer._record_command(conn, event("fleet.node_command_requested", data={
        "command_id": "fleet-cmd-1", "subject": "pocketlab.commands.device",
    }))
    assert conn.execute("SELECT command_id FROM workflow_command_state").fetchone()[0] == "fleet-cmd-1"


def test_generic_error_event_id_cannot_be_promoted_to_command_id(command_writer):
    writer, conn = command_writer
    writer._record_command(conn, event("worker.error", event_id="event-that-is-not-a-command",
                                       data={"subject": "pocketlab.commands.test"}))
    assert conn.execute("SELECT COUNT(*) FROM workflow_command_state").fetchone()[0] == 0
