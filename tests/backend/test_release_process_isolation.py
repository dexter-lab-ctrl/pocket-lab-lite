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


def _release_payload(tag: str = "lite-2026.07.28.2") -> dict:
    return {
        "product": "pocket-lab-lite",
        "phase": "available",
        "current_tag": "lite-2026.07.27.1",
        "latest_tag": tag,
        "comparison": "older",
        "update_available": True,
        "auto_apply": False,
        "configured_repository": "dexter-lab-ctrl/pocket-lab-lite",
        "verified_repository": "dexter-lab-ctrl/pocket-lab-lite",
        "repository_match": True,
        "install_mode": "release",
        "installed_release_tag": "lite-2026.07.27.1",
        "manifest_verified": True,
        "artifact_verified": False,
        "latest_release": {
            "tag_name": tag,
            "name": "Pocket Lab Lite",
            "html_url": "https://example.invalid/release",
            "published_at": "2026-07-28T00:00:00Z",
            "manifest": {
                "product": "pocket-lab-lite",
                "schema_version": 1,
                "release_tag": tag,
                "artifact": "dist.zip",
                "artifact_sha256": "a" * 64,
                "source_commit": "b" * 40,
                "target": "web-pwa",
                "created_at": "2026-07-28T00:00:00Z",
            },
            "artifact": {
                "name": "dist.zip",
                "size": 1024,
                "digest": "sha256:" + "a" * 64,
                "verification_status": "manifest_and_checksum_verified",
            },
        },
        "last_known_good": True,
    }


def _build_release_assets(tmp_path: Path, tag: str, *, traversal: bool = False) -> dict[str, bytes]:
    import hashlib

    archive = tmp_path / f"{tag}.zip"
    source_commit = "b" * 40
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("index.html", "<!doctype html><title>Pocket Lab Lite</title><div>Pocket Lab Lite</div>")
        handle.writestr("manifest.webmanifest", json.dumps({"name": "Pocket Lab Lite"}))
        handle.writestr("sw.js", "self.addEventListener('fetch', () => {});")
        handle.writestr("assets/app.js", "console.log('Pocket Lab Lite');")
        handle.writestr("assets/app.css", "body { min-height: 100vh; }")
        handle.writestr(
            "pocketlab-lite-build.json",
            json.dumps({"product": "pocket-lab-lite", "release_tag": tag, "source_commit": source_commit}),
        )
        if traversal:
            handle.writestr("../escape.txt", "blocked")
    archive_bytes = archive.read_bytes()
    digest = hashlib.sha256(archive_bytes).hexdigest()
    manifest = {
        "product": "pocket-lab-lite",
        "schema_version": 1,
        "release_tag": tag,
        "artifact": "dist.zip",
        "artifact_sha256": digest,
        "source_commit": source_commit,
        "target": "web-pwa",
        "minimum_runtime_version": "1",
        "created_at": "2026-07-28T00:00:00Z",
    }
    return {
        "dist.zip": archive_bytes,
        "checksums.txt": f"{digest}  dist.zip\n".encode(),
        "pocketlab-lite-release.json": json.dumps(manifest).encode(),
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
        release_runtime.commit_release_result(stale, _release_payload("lite-2026.07.28.3"))
    release_runtime.commit_release_result(current, _release_payload("lite-2026.07.28.3"))
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
    responses: dict[str, tuple[str, bytes]] = {}

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        content_type, body = type(self).responses.get(
            path, ("application/json", b'{"error":"not found"}')
        )
        status = 200 if path in type(self).responses else 404
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        return None


def _serve_release(tmp_path: Path, tag: str, *, traversal: bool = False):
    assets = _build_release_assets(tmp_path, tag, traversal=traversal)
    server = HTTPServer(("127.0.0.1", 0), _ReleaseHandler)
    base = f"http://127.0.0.1:{server.server_port}"
    release = {
        "tag_name": tag,
        "name": f"Pocket Lab Lite {tag}",
        "html_url": f"{base}/release",
        "published_at": "2026-07-28T00:00:00Z",
        "draft": False,
        "prerelease": False,
        "assets": [
            {
                "name": name,
                "size": len(body),
                "browser_download_url": f"{base}/assets/{name}",
            }
            for name, body in assets.items()
        ],
    }
    _ReleaseHandler.responses = {
        "/releases": (
            "application/json",
            json.dumps([
                {**release, "tag_name": "v9.9.9"},
                release,
                {**release, "tag_name": "lite-2026.02.30.1"},
            ]).encode(),
        ),
        **{f"/assets/{name}": ("application/octet-stream", body) for name, body in assets.items()},
    }
    thread = threading.Thread(target=server.serve_forever, name="release-test-http", daemon=True)
    thread.start()
    return server, base, release

def test_release_check_runs_in_bounded_subprocess(tmp_path, monkeypatch):
    monkeypatch.setenv("POCKETLAB_LITE_RELEASE_REPO", "dexter-lab-ctrl/pocket-lab-lite")
    monkeypatch.setenv(
        "POCKETLAB_LITE_VERIFIED_ORIGIN",
        "git@github.com:dexter-lab-ctrl/pocket-lab-lite.git",
    )
    release_runtime, _database = _prepare_runtime(tmp_path, monkeypatch)
    release_runtime.record_release_install(
        release_tag="lite-2026.07.27.1",
        source_repository="dexter-lab-ctrl/pocket-lab-lite",
        source_commit="a" * 40,
        artifact_sha256="c" * 64,
    )
    server, base, _release = _serve_release(tmp_path, "lite-2026.07.28.2")
    monkeypatch.setenv("POCKETLAB_RELEASE_ALLOW_INSECURE_SOURCE", "1")
    monkeypatch.setenv("POCKETLAB_RELEASE_ALLOWED_HOSTS", "127.0.0.1")
    monkeypatch.setenv("POCKETLAB_GITHUB_RELEASES_API", f"{base}/releases")
    try:
        result = asyncio.run(release_runtime.run_release_check("subprocess-check"))
    finally:
        server.shutdown()
        server.server_close()
    assert result["status"] == "healthy"
    assert result["update_available"] is True
    assert result["latest_tag"] == "lite-2026.07.28.2"
    assert result["manifest_verified"] is True
    assert result["repository_match"] is True
    assert result["latest_release"]["artifact"]["name"] == "dist.zip"
    assert "download_url" not in json.dumps(result["latest_release"])
    diagnostics = release_runtime.release_runtime_diagnostics()
    assert diagnostics["last_cpu_ms"] >= 0
    assert diagnostics["last_wall_ms"] > 0
    assert diagnostics["last_peak_rss_bytes"] >= 0
    assert diagnostics["api_thread_started"] is False
    assert diagnostics["execution_owner"] == "pocket-worker/release-subprocess"

def test_release_stage_rejects_archive_traversal(tmp_path, monkeypatch):
    release_runtime, _database = _prepare_runtime(tmp_path, monkeypatch)
    server, base, release = _serve_release(
        tmp_path, "lite-2026.07.28.2", traversal=True
    )
    monkeypatch.setenv("POCKETLAB_RELEASE_ALLOW_INSECURE_SOURCE", "1")
    monkeypatch.setenv("POCKETLAB_RELEASE_ALLOWED_HOSTS", "127.0.0.1")
    staging = tmp_path / "release-staging"
    try:
        with pytest.raises(release_runtime.ReleaseSubprocessError) as exc_info:
            asyncio.run(
                release_runtime.execute_release_subprocess(
                    "stage",
                    {
                        "release_tag": "lite-2026.07.28.2",
                        "assets": {
                            item["name"]: {
                                "name": item["name"],
                                "size": item["size"],
                                "download_url": item["browser_download_url"],
                            }
                            for item in release["assets"]
                        },
                        "staging_root": str(staging),
                        "target_dir": str(staging / "generation-1"),
                    },
                )
            )
    finally:
        server.shutdown()
        server.server_close()
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
                    "installed_release_tag": "lite-2026.07.27.1",
                },
            )
        )
    assert exc_info.value.code == "release_source_host_rejected"


def test_apply_orchestrator_uses_only_native_lite_stages(monkeypatch):
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
    subprocess_stages: list[str] = []

    async def noop_async(*_args, **_kwargs):
        return None

    async def fake_begin(_command_id):
        return lease

    async def fake_check(_lease):
        return _release_payload(), {"pid": 700, "cpu_ms": 5.0, "wall_ms": 10.0}

    async def fake_subprocess(operation, _payload):
        subprocess_stages.append(operation)
        if operation == "stage":
            return {
                "release_tag": "lite-2026.07.28.2",
                "content_path": "/private/staging/content",
                "artifact_sha256": "a" * 64,
                "manifest_verified": True,
                "artifact_verified": True,
                "archive": {
                    "representative_js": ["assets/app.js"],
                    "representative_css": ["assets/app.css"],
                    "service_worker": ["sw.js"],
                },
            }, {"pid": 701}
        if operation == "promote":
            return {
                "release_tag": "lite-2026.07.28.2",
                "rollback_available": True,
            }, {"pid": 702}
        if operation == "validate":
            return {
                "release_tag": "lite-2026.07.28.2",
                "validation_status": "passed",
            }, {"pid": 703}
        raise AssertionError(operation)

    monkeypatch.setattr(release_orchestrator, "_update_run", lambda *_a, **_k: {})
    monkeypatch.setattr(release_orchestrator, "_publish", noop_async)
    monkeypatch.setattr(release_orchestrator, "_stage_started", noop_async)
    monkeypatch.setattr(release_orchestrator, "_stage_completed", noop_async)
    monkeypatch.setattr(release_runtime, "begin_release_apply", fake_begin)
    monkeypatch.setattr(release_runtime, "check_for_apply", fake_check)
    monkeypatch.setattr(release_runtime, "execute_release_subprocess", fake_subprocess)
    monkeypatch.setattr(release_runtime, "build_stage_request", lambda *_a: {})
    monkeypatch.setattr(release_runtime, "build_promote_request", lambda *_a: {})
    monkeypatch.setattr(release_runtime, "build_validate_request", lambda *_a: {})
    monkeypatch.setattr(
        release_runtime,
        "record_release_install",
        lambda **_kwargs: {
            "source_commit": "b" * 40,
            "artifact_sha256": "a" * 64,
            "installed_at": "2026-07-28T00:00:00Z",
        },
    )
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

    result = asyncio.run(
        release_orchestrator.apply_release({"command_id": "apply-7", "force": True})
    )
    assert result["status"] == "success"
    assert result["runtime_status"] == "healthy"
    assert phases == ["downloading", "installing", "validating"]
    assert subprocess_stages == ["stage", "promote", "validate"]
    assert [item["operation"] for item in result["operations"]] == [
        "lite_release_check",
        "lite_artifact_stage",
        "lite_pwa_promote",
        "lite_release_validate",
    ]
    assert result["update_available"] is False
    source = Path(release_orchestrator.__file__).read_text(encoding="utf-8")
    for legacy in (
        "release_prepare",
        "release_sync",
        "release_deploy",
        "release_verify",
        "deploy_blueprint",
        "drift_scan",
        "pocket_lab_iac",
        "site.yml",
    ):
        assert legacy not in source

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
            "current_tag": "",
            "latest_tag": "",
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


def test_apply_validation_failure_rolls_back_before_reporting_failure(monkeypatch):
    ensure_runtime_path()
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    from api_fastapi.services import release_orchestrator, release_runtime

    lease = release_runtime.ReleaseLease(
        claimed=True,
        generation=8,
        operation="apply",
        command_id="apply-rollback",
        worker_generation="worker-8",
    )
    calls: list[str] = []
    validation_count = 0

    async def noop_async(*_args, **_kwargs):
        return None

    async def fake_begin(_command_id):
        return lease

    async def fake_check(_lease):
        return _release_payload(), {"pid": 800}

    async def fake_subprocess(operation, _payload):
        nonlocal validation_count
        calls.append(operation)
        if operation == "stage":
            return {
                "release_tag": "lite-2026.07.28.2",
                "content_path": "/private/staging/content",
                "artifact_sha256": "a" * 64,
                "manifest_verified": True,
                "artifact_verified": True,
                "archive": {},
            }, {"pid": 801}
        if operation == "promote":
            return {"release_tag": "lite-2026.07.28.2", "rollback_available": True}, {"pid": 802}
        if operation == "validate":
            validation_count += 1
            if validation_count == 1:
                raise release_runtime.ReleaseSubprocessError("release_post_switch_asset_missing")
            return {"release_tag": "lite-2026.07.27.1", "validation_status": "passed"}, {"pid": 804}
        if operation == "rollback":
            return {
                "rollback_status": "rolled_back",
                "restored_release_tag": "lite-2026.07.27.1",
            }, {"pid": 803}
        raise AssertionError(operation)

    monkeypatch.setattr(release_orchestrator, "_update_run", lambda *_a, **_k: {})
    monkeypatch.setattr(release_orchestrator, "_publish", noop_async)
    monkeypatch.setattr(release_orchestrator, "_stage_started", noop_async)
    monkeypatch.setattr(release_orchestrator, "_stage_completed", noop_async)
    monkeypatch.setattr(release_runtime, "begin_release_apply", fake_begin)
    monkeypatch.setattr(release_runtime, "check_for_apply", fake_check)
    monkeypatch.setattr(release_runtime, "execute_release_subprocess", fake_subprocess)
    monkeypatch.setattr(release_runtime, "build_stage_request", lambda *_a: {})
    monkeypatch.setattr(release_runtime, "build_promote_request", lambda *_a: {})
    monkeypatch.setattr(release_runtime, "build_validate_request", lambda *_a: {})
    monkeypatch.setattr(release_runtime, "build_rollback_request", lambda: {})
    monkeypatch.setattr(release_runtime, "renew_release_lease", lambda *_a, **_k: True)
    monkeypatch.setattr(release_runtime, "update_release_stage", lambda *_a, **_k: {})
    monkeypatch.setattr(
        release_runtime,
        "fail_release_apply",
        lambda _lease, failure_code, **kwargs: {
            "status": "degraded",
            "phase": "error",
            "last_failure_code": failure_code,
            "last_failure_stage": kwargs.get("failure_stage"),
            "last_rollback_status": kwargs.get("rollback_status"),
            "last_known_good": True,
        },
    )

    result = asyncio.run(
        release_orchestrator.apply_release(
            {"command_id": "apply-rollback", "force": True}
        )
    )
    assert result["status"] == "failed"
    assert result["failure_stage"] == "validation"
    assert result["rollback_status"] == "rolled_back"
    assert result["last_known_good"] is True
    assert calls == ["stage", "promote", "validate", "rollback", "validate"]
