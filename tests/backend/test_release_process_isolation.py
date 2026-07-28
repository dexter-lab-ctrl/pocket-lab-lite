from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _prepare_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    database = tmp_path / "state" / "pocketlab-lite.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(database))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(database.parent))
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.runtime import SQLITE_READS
    from api_fastapi.services import release_runtime

    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    release_runtime._OPERATION_LOCK = None
    release_runtime.initialize_release_runtime()
    return release_runtime, database


def _release_payload(tag: str = "v2.0.0") -> dict:
    return {
        "phase": "available",
        "current_tag": "v1.0.0",
        "latest_tag": tag,
        "update_available": True,
        "auto_apply": False,
        "latest_release": {
            "tag_name": tag,
            "name": "Pocket Lab Lite",
            "html_url": "https://example.invalid/release",
            "published_at": "2026-07-28T00:00:00Z",
            "artifact": {
                "name": "dist.zip",
                "size": 1024,
                "digest": "sha256:" + "a" * 64,
                "verification_status": "digest_available",
            },
        },
        "last_known_good": True,
    }


def test_api_role_never_starts_legacy_release_thread(tmp_path, monkeypatch):
    ensure_runtime_path()
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "api")
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(tmp_path / "state" / "db.sqlite3"))
    from core.release_auto_update import ReleaseAutoUpdater

    updater = ReleaseAutoUpdater(
        state_dir=tmp_path,
        operation_service=object(),
        poll_interval=30,
    )
    assert updater.start() is False
    assert updater._thread is None
    assert not any(
        thread.name == "pocket-lab-release-auto-update"
        for thread in threading.enumerate()
    )
    with pytest.raises(RuntimeError, match="worker_scheduler_owned"):
        updater.check_once()


def test_release_projection_is_change_only_and_generation_fenced(tmp_path, monkeypatch):
    release_runtime, _database = _prepare_runtime(tmp_path, monkeypatch)

    first = release_runtime.claim_release_operation("check", "check-1")
    committed = release_runtime.commit_release_result(
        first,
        _release_payload(),
        subprocess_metrics={"pid": 101, "cpu_ms": 8.5, "wall_ms": 20.0},
    )
    assert committed["changed"] is True
    first_revision = committed["projection_revision"]

    second = release_runtime.claim_release_operation("check", "check-2")
    unchanged = release_runtime.commit_release_result(
        second,
        {**_release_payload(), "source": "automatic"},
        subprocess_metrics={"pid": 102, "cpu_ms": 7.5, "wall_ms": 18.0},
    )
    assert unchanged["changed"] is False
    assert unchanged["projection_revision"] == first_revision
    diagnostics = release_runtime.release_runtime_diagnostics()
    assert diagnostics["writes_committed"] == 1
    assert diagnostics["writes_skipped"] == 1
    assert diagnostics["unchanged_results"] == 1

    stale = release_runtime.claim_release_operation("check", "check-stale")
    from api_fastapi.db.connection import connection

    with connection() as conn:
        conn.execute(
            "UPDATE release_runtime_projection SET lease_expires_epoch_ms = 0 WHERE owner = 'release'"
        )
    current = release_runtime.claim_release_operation("check", "check-current")
    assert current.claimed is True
    with pytest.raises(release_runtime.ReleaseStaleResult):
        release_runtime.commit_release_result(stale, _release_payload("v3.0.0"))
    release_runtime.commit_release_result(current, _release_payload("v3.0.0"))
    diagnostics = release_runtime.release_runtime_diagnostics()
    assert diagnostics["stale_results_rejected"] == 1
    assert diagnostics["subprocess_restarts"] >= 1


def test_release_command_redelivery_is_deduplicated(tmp_path, monkeypatch):
    release_runtime, _database = _prepare_runtime(tmp_path, monkeypatch)
    lease = release_runtime.claim_release_operation("check", "same-command")
    release_runtime.commit_release_result(lease, _release_payload())

    duplicate = release_runtime.claim_release_operation("check", "same-command")
    assert duplicate.claimed is False
    assert duplicate.deduplicated is True
    assert duplicate.retry_after_seconds == 0
    assert release_runtime.release_runtime_diagnostics()["deduplicated_requests"] == 1


class _ReleaseHandler(BaseHTTPRequestHandler):
    response: dict = {}

    def do_GET(self):  # noqa: N802
        body = json.dumps(type(self).response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return None


def test_release_check_runs_in_bounded_subprocess(tmp_path, monkeypatch):
    release_runtime, _database = _prepare_runtime(tmp_path, monkeypatch)
    _ReleaseHandler.response = {
        "tag_name": "v2.0.0",
        "name": "Pocket Lab Lite v2",
        "html_url": "https://example.invalid/v2",
        "published_at": "2026-07-28T00:00:00Z",
        "body": "Release notes",
        "assets": [
            {
                "name": "dist.zip",
                "size": 4096,
                "digest": "sha256:" + "b" * 64,
                "browser_download_url": "https://objects.githubusercontent.com/private/signed",
            }
        ],
    }
    server = HTTPServer(("127.0.0.1", 0), _ReleaseHandler)
    server_thread = threading.Thread(
        target=server.serve_forever,
        name="release-test-http",
        daemon=True,
    )
    server_thread.start()
    monkeypatch.setenv("POCKETLAB_RELEASE_ALLOW_INSECURE_SOURCE", "1")
    monkeypatch.setenv(
        "POCKETLAB_GITHUB_RELEASES_API",
        f"http://127.0.0.1:{server.server_port}/latest",
    )
    monkeypatch.setenv("POCKETLAB_RELEASE_TAG", "v1.0.0")
    try:
        result = asyncio.run(release_runtime.run_release_check("subprocess-check"))
    finally:
        server.shutdown()
        server.server_close()
    assert result["status"] == "healthy"
    assert result["update_available"] is True
    assert result["latest_release"]["artifact"]["name"] == "dist.zip"
    assert "download_url" not in result["latest_release"]["artifact"]
    diagnostics = release_runtime.release_runtime_diagnostics()
    assert diagnostics["last_cpu_ms"] >= 0
    assert diagnostics["last_wall_ms"] > 0
    assert diagnostics["last_peak_rss_bytes"] >= 0
    assert diagnostics["api_thread_started"] is False
    assert diagnostics["execution_owner"] == "pocket-worker/release-subprocess"


def test_release_verify_rejects_archive_traversal(tmp_path, monkeypatch):
    release_runtime, _database = _prepare_runtime(tmp_path, monkeypatch)
    staging = tmp_path / "release-staging"
    staging.mkdir(parents=True)
    archive = staging / "bad.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../escape.txt", "blocked")
    monkeypatch.setenv("POCKETLAB_RELEASE_STAGING_DIR", str(staging))

    with pytest.raises(release_runtime.ReleaseSubprocessError) as exc_info:
        asyncio.run(
            release_runtime.execute_release_subprocess(
                "verify",
                {"path": str(archive)},
            )
        )
    assert exc_info.value.code == "release_archive_path_traversal"
    assert not (tmp_path / "escape.txt").exists()


def test_release_source_host_is_fail_closed(tmp_path, monkeypatch):
    release_runtime, _database = _prepare_runtime(tmp_path, monkeypatch)
    monkeypatch.delenv("POCKETLAB_GITHUB_RELEASES_API", raising=False)
    monkeypatch.setenv("POCKETLAB_RELEASE_ALLOWED_HOSTS", "api.github.com")

    with pytest.raises(release_runtime.ReleaseSubprocessError) as exc_info:
        asyncio.run(
            release_runtime.execute_release_subprocess(
                "check",
                {
                    "source_url": "https://untrusted.invalid/releases/latest",
                    "current_tag": "v1.0.0",
                },
            )
        )
    assert exc_info.value.code == "release_source_host_rejected"


def test_apply_orchestrator_separates_download_apply_and_verify(monkeypatch):
    ensure_runtime_path()
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    from api_fastapi.services import release_orchestrator, release_runtime

    lease = release_runtime.ReleaseLease(
        claimed=True,
        generation=7,
        operation="apply",
        command_id="apply-7",
        worker_generation="worker-7",
    )
    phases: list[str] = []
    operation_stages: list[str] = []

    async def noop_async(*_args, **_kwargs):
        return None

    async def fake_begin(_command_id):
        return lease

    async def fake_check(_lease):
        return _release_payload(), {"pid": 700, "cpu_ms": 5.0, "wall_ms": 10.0}

    async def fake_operation(
        _command_id,
        stage_id,
        _title,
        operation,
        _target_type,
        _target_ref,
        _params=None,
    ):
        operation_stages.append(stage_id)
        return {"operation": operation, "job_id": stage_id, "status": "succeeded"}

    monkeypatch.setattr(release_orchestrator, "_update_run", lambda *_a, **_k: {})
    monkeypatch.setattr(release_orchestrator, "_publish", noop_async)
    monkeypatch.setattr(release_orchestrator, "_stage_started", noop_async)
    monkeypatch.setattr(release_orchestrator, "_stage_completed", noop_async)
    monkeypatch.setattr(release_orchestrator, "_run_release_operation", fake_operation)
    monkeypatch.setattr(release_runtime, "begin_release_apply", fake_begin)
    monkeypatch.setattr(release_runtime, "check_for_apply", fake_check)
    monkeypatch.setattr(
        release_runtime,
        "update_release_stage",
        lambda _lease, *, phase, status="running": phases.append(phase) or {},
    )
    monkeypatch.setattr(release_runtime, "renew_release_lease", lambda *_a, **_k: True)
    monkeypatch.setattr(
        release_runtime,
        "finalize_release_apply",
        lambda _lease, payload, **_kwargs: {
            **payload,
            "status": "healthy",
            "projection_revision": 8,
        },
    )
    monkeypatch.setattr(
        release_orchestrator.deps.core, "build_catalog_view", lambda: []
    )
    monkeypatch.setattr(
        release_orchestrator.deps.core, "build_catalog_cache", lambda _items: None
    )
    monkeypatch.setattr(
        release_orchestrator.deps.core, "build_health_engine_snapshot", lambda: {"status": "healthy"}
    )
    monkeypatch.setattr(
        release_orchestrator.deps.core, "load_fleet_nodes", lambda: []
    )
    monkeypatch.setattr(
        release_orchestrator.deps.core,
        "build_fleet_health_snapshot",
        lambda _nodes: {"status": "healthy"},
    )
    monkeypatch.setattr(
        release_orchestrator.deps.core, "telemetry_snapshot", lambda: {"ready": True}
    )

    result = asyncio.run(
        release_orchestrator.apply_release(
            {"command_id": "apply-7", "force": True}
        )
    )
    assert result["status"] == "success"
    assert result["runtime_status"] == "healthy"
    assert phases == ["preparing", "downloading", "applying", "verifying"]
    assert operation_stages == ["prepare", "download", "apply", "verify"]
    assert result["update_available"] is False


def test_worker_publishes_truthful_terminal_failure_for_release_result(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import domain_commands
    from workers import pocketlab_worker

    published: list[tuple[str, str, dict]] = []

    async def fake_domain(_subject, _command):
        return {
            "status": "failed",
            "failure_code": "release_checksum_mismatch",
            "last_known_good": True,
        }

    async def fake_publish(subject, event_type, data, **_kwargs):
        published.append((subject, event_type, data))

    monkeypatch.setattr(domain_commands, "execute_domain_command", fake_domain)
    monkeypatch.setattr(pocketlab_worker, "publish", fake_publish)

    asyncio.run(
        pocketlab_worker.execute_domain_command(
            "pocketlab.commands.release.apply",
            {"command_id": "release-failed-1"},
        )
    )
    terminal = published[-1]
    assert terminal[0] == "pocketlab.events.command.failed"
    assert terminal[1] == "command.failed"
    assert terminal[2]["terminal"] is True
    assert terminal[2]["error_type"] == "release_checksum_mismatch"
    assert terminal[2]["last_known_good"] is True


def test_release_check_returns_truthful_degraded_state(monkeypatch):
    ensure_runtime_path()
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    from api_fastapi.services import release_orchestrator, release_runtime

    async def noop_async(*_args, **_kwargs):
        return None

    async def degraded(_command_id, *, source="manual"):
        return {
            "status": "degraded",
            "phase": "error",
            "last_failure_code": "release_source_unreachable",
            "last_known_good": True,
            "current_tag": "v1.0.0",
            "latest_tag": "v1.0.0",
            "update_available": False,
        }

    monkeypatch.setattr(release_orchestrator, "_update_run", lambda *_a, **_k: {})
    monkeypatch.setattr(release_orchestrator, "_publish", noop_async)
    monkeypatch.setattr(release_orchestrator, "_stage_started", noop_async)
    monkeypatch.setattr(release_orchestrator, "_stage_completed", noop_async)
    monkeypatch.setattr(release_orchestrator, "_stage_failed", noop_async)
    monkeypatch.setattr(release_runtime, "run_release_check", degraded)

    result = asyncio.run(
        release_orchestrator.check_release({"command_id": "check-degraded"})
    )
    assert result["status"] == "failed"
    assert result["runtime_status"] == "degraded"
    assert result["last_failure_code"] == "release_source_unreachable"
    assert result["last_known_good"] is True
