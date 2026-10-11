from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tarfile

import pytest

from pocket_lab_test_utils import ensure_runtime_path


ROOT = Path(__file__).resolve().parents[2]
CONTEXT = ROOT / "pocket-lab-final-structure" / "runtime" / "api_fastapi" / "services" / "qualification_context.py"
CONTROLLER = ROOT / "scripts" / "dev" / "lite" / "run-isolated-runtime-qualification.py"
RCLONE = ROOT / "scripts" / "dev" / "lite" / "qualification_rclone.py"
TASKFILE = ROOT / "tasks" / "Taskfile.lite.yml"


def _context():
    ensure_runtime_path()
    from api_fastapi.services import qualification_context

    return qualification_context


def _arm(monkeypatch: pytest.MonkeyPatch, root: Path, *, origin: str = "https://127.0.0.1:43123") -> Path:
    destination = root / "webdav" / "originals"
    destination.mkdir(mode=0o700, parents=True)
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_CONTEXT", "isolated-runtime-v1")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_RUN_ID", "a" * 24)
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_CANDIDATE_SHA", "b" * 40)
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_ALLOW_TEST_DESTINATION", "1")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_CONTEXT_TOKEN", "c" * 48)
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_WEBDAV_PASSWORD", "d" * 48)
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_ROOT", str(root))
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_DESTINATION_ROOT", str(destination))
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_TEST_ORIGIN", origin)
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_CONTROL_ORIGIN", "https://127.0.0.1:43124")
    return destination


def test_qualification_context_is_disabled_without_complete_binding(monkeypatch):
    context = _context()
    for name in tuple(os.environ):
        if name.startswith("POCKETLAB_QUALIFICATION_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("POCKETLAB_ENVIRONMENT", raising=False)
    assert context.enabled() is False


def test_existing_qualification_harness_state_path_does_not_arm_destination_context(monkeypatch):
    context = _context()
    for name in tuple(os.environ):
        if name.startswith("POCKETLAB_QUALIFICATION_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_STATE_DIR", "/run-owned/qualification-state")
    assert context.enabled() is False


def test_qualification_context_requires_loopback_https_and_private_destination(tmp_path, monkeypatch):
    context = _context()
    destination = _arm(monkeypatch, tmp_path)
    assert context.enabled() is True
    assert context.destination_root() == destination.resolve()
    assert context.control_origin() == "https://127.0.0.1:43124"
    assert context.public_summary() == {
        "enabled": True,
        "context": "isolated-runtime-v1",
        "run_id": "a" * 24,
        "candidate_sha": "b" * 40,
        "destination_id": "server-photoprism-originals",
        "origin_class": "https_loopback",
        "credential_scope": "synthetic_run_node_backup",
    }

    monkeypatch.setenv("POCKETLAB_QUALIFICATION_TEST_ORIGIN", "https://example.invalid:443")
    with pytest.raises(context.QualificationContextError):
        context.assert_safe()


def test_qualification_context_rejects_symlink_destination(tmp_path, monkeypatch):
    context = _context()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "webdav"
    link.symlink_to(outside, target_is_directory=True)
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_DESTINATION_ROOT", str(link / "originals"))
    _arm(monkeypatch, tmp_path)
    # _arm creates the intended child after the symlink setup; restore the
    # symlink because the helper intentionally provisions a normal fixture.
    link.unlink()
    link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(context.QualificationContextError):
        context.assert_safe()


def test_partial_context_cannot_fall_back_to_production_origin(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_catalog

    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_CONTEXT", "isolated-runtime-v1")
    monkeypatch.setenv("POCKETLAB_LITE_SECURE_ORIGIN", "https://production.example.ts.net")
    monkeypatch.delenv("POCKETLAB_QUALIFICATION_ROOT", raising=False)
    assert lite_catalog._detect_secure_origin_from_request(None) is None


def test_controller_scrubs_production_nats_and_cloud_credentials(monkeypatch):
    spec = importlib.util.spec_from_file_location("isolated_qualification_controller", CONTROLLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setenv("POCKETLAB_NATS_PASSWORD", "production-secret")
    monkeypatch.setenv("POCKETLAB_LITE_PUBLIC_NATS_URL", "nats://production.example:4222")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "production-secret")
    monkeypatch.setenv("POCKETLAB_STATE_DIR", "/production/state")
    clean = module._scrubbed_environment()
    assert "POCKETLAB_NATS_PASSWORD" not in clean
    assert "POCKETLAB_LITE_PUBLIC_NATS_URL" not in clean
    assert "AWS_SECRET_ACCESS_KEY" not in clean
    assert "POCKETLAB_STATE_DIR" not in clean


def test_controller_namespaces_are_run_bound():
    spec = importlib.util.spec_from_file_location("isolated_qualification_controller_2", CONTROLLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    first = module.uuid.uuid4().hex[:24]
    second = module.uuid.uuid4().hex[:24]
    assert first != second
    assert module.RUN_ID_RE.fullmatch(first)
    assert module.RUN_ID_RE.fullmatch(second)


def test_full_task_exposes_explicit_isolated_dependency_paths():
    taskfile = TASKFILE.read_text(encoding="utf-8")
    assert 'NATS_SERVER_BIN: \'{{default "" .NATS_SERVER_BIN}}\'' in taskfile
    assert 'OPA_BIN: \'{{default "" .OPA_BIN}}\'' in taskfile
    assert "--nats-server-bin" in taskfile
    assert "--opa-bin" in taskfile


def test_android_candidate_task_is_explicit_and_preserves_read_only_mode():
    taskfile = TASKFILE.read_text(encoding="utf-8")
    assert "lite:photo-backup:candidate:android:qualify:" in taskfile
    assert "--android-qualify" in taskfile
    assert "--android-read-only" in taskfile
    assert "EVIDENCE_DIR" in taskfile


def test_android_media_fixture_keeps_camera_files_with_nested_nomedia_marker(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("isolated_android_media_fixture_test", CONTROLLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    archive, expected = module._android_media_archive(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    with tarfile.open(archive, "r") as bundle:
        bundle.extractall(home)

    ensure_runtime_path()
    from agents import lite_photo_backup_agent

    roots = {
        "camera": home / "storage" / "shared" / "DCIM" / "Camera",
        "pictures": home / "storage" / "shared" / "Pictures",
        "videos": home / "storage" / "shared" / "Movies",
    }
    monkeypatch.setattr(lite_photo_backup_agent, "_collection_path", lambda name: roots[name])
    provider = lite_photo_backup_agent.PhotoPrismWebDAVProvider(
        node_id="qualification-test",
        agent_token="qualification-token",
        control_origin="https://127.0.0.1:43123",
    )

    records = list(provider._inventory(["camera", "pictures", "videos"]))
    assert len(records) == 6
    assert {record["collection"] for record in records} == {"camera", "pictures", "videos"}
    assert not any("ignored" in str(record["path"]) for record in records)
    assert not any(Path(record["path"]).name.startswith(".") for record in records)
    assert len([
        item for item in expected
        if not Path(str(item["path"])).name.startswith(".")
    ]) == 6


def test_android_production_projection_ignores_ephemeral_pm2_pids():
    spec = importlib.util.spec_from_file_location("isolated_android_projection_test", CONTROLLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    before = {
        "system": "Linux",
        "architecture": "aarch64",
        "home_class": "termux_private_home",
        "prefix_class": "termux_prefix",
        "source_sha": "a" * 40,
        "git_clean": True,
        "pm2": [{"name": "pocket-api", "pid": 101, "status": "online", "version": "1.0", "cwd_class": "other"}],
        "listeners": {"count": 0, "addresses": [], "loopback_only": True},
        "tailscale": "unobserved",
        "photoprism_health": "unobserved",
    }
    after = {**before, "pm2": [{**before["pm2"][0], "pid": 202}]}

    assert module.AndroidQualificationRun._production_projection(before) == module.AndroidQualificationRun._production_projection(after)


def test_android_transport_is_loopback_only_and_not_a_reverse_shell():
    spec = importlib.util.spec_from_file_location("isolated_android_transport_test", CONTROLLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    tunnel = module.AndroidTunnel(
        host="pocketlab-secondary",
        run_id="a" * 24,
        kind="test",
        log=Path("/tmp/qualification-test.log"),
        direction="reverse",
        local_port=12345,
        target_port=23456,
    )
    assert tunnel.mapping["bind_address"] == "127.0.0.1"
    assert tunnel.direction == "reverse"
    source = CONTROLLER.read_text(encoding="utf-8")
    assert "ClearAllForwardings=no" in source
    assert "GatewayPorts=no" in source
    assert "\"ssh\", \"-v\", \"-N\", \"-T\"" in source
    assert "--no-check-certificate" not in source


def test_android_python_probes_preserve_argument_boundaries(monkeypatch):
    spec = importlib.util.spec_from_file_location("isolated_android_argument_test", CONTROLLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    calls = []

    def fake_ssh_run(host, args, *, input_data=None, timeout=20):
        calls.append((host, args, input_data, timeout))
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps({"missing": [], "python": args[0], "version": "3.14.6"}),
            stderr="",
        )

    monkeypatch.setattr(module, "_android_ssh_run", fake_ssh_run)
    assert module._android_import_check(
        "pocketlab-termux",
        "/data/data/com.termux/files/usr/bin/python",
        ["nats"],
        extra_paths=["/data/data/com.termux/files/home/.local/lib/python3.13/site-packages"],
    )["missing"] == []
    assert calls[0][1][3:] == [
        '["/data/data/com.termux/files/home/.local/lib/python3.13/site-packages"]',
        "nats",
    ]


def test_android_ssh_input_does_not_duplicate_stdin(monkeypatch):
    spec = importlib.util.spec_from_file_location("isolated_android_stdin_test", CONTROLLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        return subprocess.CompletedProcess(args, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    module._android_ssh_run("pocketlab-secondary", ["sh", "-c", "cat"], input_data=b"fixture")
    assert captured["input"] == b"fixture"
    assert captured["stdin"] is None


def test_android_cleanup_unlocks_read_only_roots_and_avoids_unstarted_pm2():
    spec = importlib.util.spec_from_file_location("isolated_android_cleanup_test", CONTROLLER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert "path.chmod(0o600)" in module._ANDROID_REMOVE_ROOT_CODE
    assert "path.unlink()" in module._ANDROID_REMOVE_ROOT_CODE
    assert "already_stopped" in module._ANDROID_STOP_CODE
    assert "self.secondary_env_path and self.supervisor_started" in CONTROLLER.read_text(encoding="utf-8")


def test_android_supervisor_uses_explicit_run_scoped_pm2_binary():
    supervisor = (ROOT / "pocket-lab-final-structure" / "runtime" / "agents" / "pocketlab_agent_supervisor.py").read_text(encoding="utf-8")
    controller = CONTROLLER.read_text(encoding="utf-8")
    assert "POCKETLAB_PM2_BIN" in supervisor
    assert "def _run_pm2(" in supervisor
    assert "shlex.join([executable, *args])" in supervisor
    assert '"--interpreter",' in supervisor
    assert '"none",' in supervisor
    assert '_run_pm2(pm2, ["jlist"]' in supervisor
    assert '"error_stage": self.error_stage' in supervisor
    assert '"repair_failure_detail": self.last_repair_failure_detail or None' in supervisor
    assert '"LD_PRELOAD": str(remote.baseline.get("termux_exec_ld_preload") or "")' in controller
    assert '"termux_exec_ld_preload"' in controller
    assert 'shlex.join([pm2, "jlist"])' in controller
    assert 'agent_error_log' in controller
    assert '"POCKETLAB_PM2_BIN": remote.pm2 or ""' in controller


def test_qualification_rclone_accepts_candidate_flag_surface():
    spec = importlib.util.spec_from_file_location("qualification_rclone_test", RCLONE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    args, rest = module._parse_args([
        "lsjson",
        "photoprism:PocketLab/Devices/test",
        "--recursive",
        "--files-only",
        "--hash",
        "--hash-type",
        "SHA-256",
        "--config",
        "/run-owned/config",
    ])
    assert args.command == "lsjson"
    assert rest[0] == "photoprism:PocketLab/Devices/test"
    assert "--recursive" in rest
    assert "--config" in rest


def test_fleet_projection_retains_only_sanitized_photo_observation():
    ensure_runtime_path()
    from api_fastapi.services import fleet_registry

    projected = fleet_registry._normalize_photo_backup({
        "rclone_available": True,
        "photo_storage_access": True,
        "collections": ["camera", "pictures", "unexpected"],
        "rclone_version": "rclone v1.0.0",
        "repair": {
            "status": "completed",
            "reason_code": "rclone_install_failed",
            "password": "must-not-project",
        },
        "password": "must-not-project",
    })
    assert projected["collections"] == ["camera", "pictures"]
    assert projected["repair"]["status"] == "completed"
    assert "password" not in repr(projected)


def test_pending_bootstrap_token_rotation_is_server_owned(monkeypatch, tmp_path):
    ensure_runtime_path()
    from api_fastapi.services import fleet_registry

    node_id = "qualification-token-rotation"
    state = {
        "agents": {
            node_id: {
                "node_id": node_id,
                "identity_status": "pending",
                "enrollment_status": "waiting_for_heartbeat",
                "auth_token_hash": "a" * 16,
            }
        }
    }
    writes = []
    monkeypatch.setattr(fleet_registry, "_agents_payload", lambda: state)
    monkeypatch.setattr(fleet_registry, "_write", lambda path, payload: writes.append((path, payload)))
    monkeypatch.setattr(fleet_registry, "_state_path", lambda name: tmp_path / name)

    rotated = fleet_registry.rotate_pending_agent_token_hash(node_id, "b" * 16)
    assert rotated["auth_token_hash"] == "b" * 16
    assert rotated["enrollment_status"] == "waiting_for_heartbeat"
    assert writes

    state["agents"][node_id]["identity_status"] = "verified"
    with pytest.raises(ValueError, match="rotation_forbidden"):
        fleet_registry.rotate_pending_agent_token_hash(node_id, "c" * 16)
