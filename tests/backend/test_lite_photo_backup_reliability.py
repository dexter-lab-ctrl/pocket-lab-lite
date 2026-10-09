from __future__ import annotations

from types import SimpleNamespace


def test_destination_classes_are_explicitly_disabled():
    from pocket_lab_test_utils import ensure_runtime_path
    ensure_runtime_path()
    from api_fastapi.services import lite_photo_backup_destinations as destinations
    capacity = {"status": "ready", "safe_upload_budget_bytes": 1024}
    result = destinations.destinations(capacity, operational=True)
    assert result[0]["eligible"] is True
    assert result[0]["transport"] == "https_webdav"
    assert all(not item["eligible"] and not item["supported"] for item in result[1:])
    try:
        destinations.require_eligible("managed-nas", capacity, operational=True)
    except ValueError as exc:
        assert str(exc) == "unsupported_destination"
    else:
        raise AssertionError("unimplemented destination was accepted")


def test_zero_planning_budget_is_not_admissible(monkeypatch):
    from pocket_lab_test_utils import ensure_runtime_path
    ensure_runtime_path()
    from api_fastapi.services import lite_photo_backup as backup
    monkeypatch.setattr(backup, "_safe_node_id", lambda x: x)
    monkeypatch.setattr(backup, "_agent", lambda node: {"node_id": node, "connection": "online"})
    monkeypatch.setattr(backup, "_photo_capability", lambda agent: {
        "rclone_available": True, "rclone_version": "rclone 1.75",
        "photo_storage_access": True, "collections": ["camera"]})
    monkeypatch.setattr(backup.lite_app_runtime, "probe_app_runtime",
                        lambda name: {"running": True, "reachable": True})
    monkeypatch.setattr(backup, "_secure_origin", lambda request=None: "https://safe.example")
    monkeypatch.setattr(backup, "_webdav_route_probe", lambda origin, force=False: None)
    monkeypatch.setattr(backup, "server_capacity", lambda: {
        "status": "ready", "safe_upload_budget_bytes": 0,
        "hard_upload_budget_bytes": 100, "sanitized": True})
    result = backup.readiness("secondary")
    assert result["ready"] is False
    assert result["destination_operational"] is True
    assert result["safe_capacity_available"] is False
    assert result["reason_code"] == "storage_below_planning_reserve"


def test_invalid_capacity_fails_closed(tmp_path, monkeypatch):
    from pocket_lab_test_utils import ensure_runtime_path
    ensure_runtime_path()
    from api_fastapi.services import lite_photo_backup as backup
    monkeypatch.setattr(backup, "_originals_path", lambda: tmp_path)
    monkeypatch.setattr(backup.os, "statvfs", lambda path: SimpleNamespace(
        f_blocks=100, f_bavail=110, f_frsize=4096))
    result = backup.server_capacity()
    assert result["status"] == "unavailable"
    assert result["safe_upload_budget_bytes"] == 0


def test_inventory_limit_is_bounded(monkeypatch, tmp_path):
    from pocket_lab_test_utils import ensure_runtime_path
    ensure_runtime_path()
    import importlib.util
    import sys
    from pathlib import Path
    runtime = Path(__file__).resolve().parents[2] / "pocket-lab-final-structure" / "runtime"
    agent_path = runtime / "agents" / "lite_photo_backup_agent.py"
    spec = importlib.util.spec_from_file_location("photo_backup_agent_reliability", agent_path)
    assert spec and spec.loader
    agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent)
    class FakeStat:
        st_size = 20
        st_mtime = 42.0
    root = tmp_path / "DCIM"
    root.mkdir()
    (root / "a.jpg").write_bytes(b"abc")
    monkeypatch.setattr(agent, "_collection_path", lambda name: root)
    monkeypatch.setattr(agent, "MAX_INVENTORY_ITEMS", 0)
    provider = agent.PhotoPrismWebDAVProvider(
        node_id="secondary", agent_token="test", control_origin="https://safe.example")
    import pytest
    with pytest.raises(RuntimeError, match="source_inventory_limit_reached"):
        provider._inventory(["camera"])


def test_repair_records_only_sanitized_phases(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    agent_path = (Path(__file__).resolve().parents[2] /
                  "pocket-lab-final-structure/runtime/agents/lite_photo_backup_agent.py")
    spec = importlib.util.spec_from_file_location("photo_backup_repair_isolation", agent_path)
    assert spec and spec.loader
    agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent)
    monkeypatch.setattr(agent.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(agent.shutil, "which",
                        lambda name: "/usr/bin/pkg" if name == "pkg" else None)
    monkeypatch.setattr(agent, "collect_photo_backup_capabilities", lambda: {
        "rclone_available": False, "rclone_version": "Unavailable",
        "photo_storage_access": True, "sanitized": True,
    })
    import subprocess
    monkeypatch.setattr(agent.subprocess, "run", lambda args, **kwargs:
                        subprocess.CompletedProcess(args, 1))
    result = agent.repair_rclone()
    assert result["status"] == "failed"
    assert result["reason_code"] == "rclone_install_failed"
    import json
    record = json.loads((tmp_path / ".pocketlab-lite/photo-backup-repair.json").read_text())
    assert record["status"] == "failed"
    assert record["reason_code"] == "rclone_install_failed"
    assert "stdout" not in record and "stderr" not in record
    assert (tmp_path / ".pocketlab-lite/photo-backup-repair.json").stat().st_mode & 0o777 == 0o600


def test_repair_does_not_launch_second_package_manager(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    import fcntl
    agent_path = (Path(__file__).resolve().parents[2] /
                  "pocket-lab-final-structure/runtime/agents/lite_photo_backup_agent.py")
    spec = importlib.util.spec_from_file_location("photo_backup_repair_lock", agent_path)
    assert spec and spec.loader
    agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent)
    monkeypatch.setattr(agent.Path, "home", lambda: tmp_path)
    directory = tmp_path / ".pocketlab-lite"
    directory.mkdir()
    with (directory / "photo-backup-repair.lock").open("w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        monkeypatch.setattr(agent.subprocess, "run", lambda *_args, **_kwargs:
                            (_ for _ in ()).throw(AssertionError("installer was called")))
        result = agent.repair_rclone()
        assert result["status"] == "already_running"
        assert result["reason_code"] == "rclone_repair_in_progress"


def test_p0_route_probe_caches_auth_challenge_as_reachable(monkeypatch):
    from pocket_lab_test_utils import ensure_runtime_path
    ensure_runtime_path()
    from api_fastapi.services import lite_photo_backup as backup
    import urllib.error
    backup._PREFLIGHT_CACHE.clear()
    observed = []
    def fake_open(request, timeout):
        observed.append((request.full_url, request.get_method(), timeout))
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)
    monkeypatch.setattr(backup.urllib.request, "urlopen", fake_open)
    assert backup._webdav_route_probe("https://safe.example", force=True) is None
    assert backup._webdav_route_probe("https://safe.example") is None
    assert observed == [("https://safe.example/apps/photoprism/originals/", "OPTIONS", 3)]


def test_p0_route_probe_fails_closed_without_network_on_insecure_origin(monkeypatch):
    from pocket_lab_test_utils import ensure_runtime_path
    ensure_runtime_path()
    from api_fastapi.services import lite_photo_backup as backup
    monkeypatch.setattr(backup.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network")))
    assert backup._webdav_route_probe("http://unsafe.example", force=True) == "secure_route_unavailable"
    assert backup._webdav_route_probe("https://user:pass@safe.example", force=True) == "secure_route_unavailable"


def test_p0_reason_classification_and_independent_readiness(monkeypatch):
    from pocket_lab_test_utils import ensure_runtime_path
    ensure_runtime_path()
    from api_fastapi.services import lite_photo_backup as backup
    monkeypatch.setattr(backup, "_safe_node_id", lambda x: x)
    monkeypatch.setattr(backup, "_agent", lambda node: {"node_id": node, "connection": "online"})
    monkeypatch.setattr(backup, "_photo_capability", lambda agent: {
        "rclone_available": True, "rclone_version": "rclone 1.75",
        "photo_storage_access": True, "collections": ["camera"]})
    monkeypatch.setattr(backup.lite_app_runtime, "probe_app_runtime",
                        lambda name, force=False: {"running": True, "reachable": True})
    monkeypatch.setattr(backup, "_secure_origin", lambda request=None: "https://safe.example")
    monkeypatch.setattr(backup, "_webdav_route_probe",
                        lambda origin, force=False: "webdav_probe_failed")
    monkeypatch.setattr(backup, "server_capacity", lambda: {
        "status": "ready", "safe_upload_budget_bytes": 2000,
        "hard_upload_budget_bytes": 3000, "sanitized": True})
    view = backup.readiness("secondary", force=True)
    assert view["source_ready"] is True
    assert view["safe_capacity_available"] is True
    assert view["destination_operational"] is False
    assert view["backup_admissible"] is False
    assert view["reason_code"] == "webdav_probe_failed"
    assert view["webdav_authenticated"] is None
    assert view["diagnostics"][0]["remediation_category"] == "destination"


def test_p0_worker_capacity_reason_is_independent_of_route():
    from pocket_lab_test_utils import ensure_runtime_path
    ensure_runtime_path()
    from api_fastapi.services import lite_photo_backup as backup
    assert backup._capacity_diagnostic({"status": "unavailable"}) == "destination_storage_unavailable"
    assert backup._capacity_diagnostic({"status": "ready", "read_only": True}) == "destination_read_only"
    assert backup._capacity_diagnostic({"status": "ready", "hard_upload_budget_bytes": 10,
                                        "safe_upload_budget_bytes": 0}) == "storage_below_planning_reserve"


def test_p0_missing_or_old_fleet_heartbeat_fails_closed(monkeypatch):
    from pocket_lab_test_utils import ensure_runtime_path
    ensure_runtime_path()
    from api_fastapi.services import lite_photo_backup as backup
    assert backup._source_fresh({"connection": "online"}) is False
    monkeypatch.setattr(backup, "_epoch", lambda: 1000.0)
    assert backup._source_fresh({"last_seen_epoch": 995}) is True
    assert backup._source_fresh({"last_seen_epoch": 700}) is False
    assert backup._source_fresh({"last_seen_epoch": 1018}) is False


def test_p0_destination_identity_binding_requires_explicit_repair(monkeypatch, tmp_path):
    from pocket_lab_test_utils import ensure_runtime_path
    ensure_runtime_path()
    from api_fastapi.services import lite_photo_backup as backup
    from types import SimpleNamespace
    root = tmp_path / "originals"
    root.mkdir()
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(backup.deps, "settings", lambda: SimpleNamespace(state_dir=state))
    result = backup._destination_identity(root, __import__("os").statvfs(root))
    assert result is None
    identity_file = state / "lite_photo_backup_destination_identity.json"
    record = backup._read_json(identity_file, {})
    assert record["schema_version"] == 1
    assert record["destination_id"] == backup.lite_photo_backup_destinations.CURRENT_DESTINATION_ID
    record["fingerprint"] = "0" * 64
    backup._write_json(identity_file, record)
    assert backup._destination_identity(root, __import__("os").statvfs(root)) == "destination_identity_mismatch"
    assert backup._read_json(identity_file, {})["fingerprint"] == "0" * 64


def test_p0_specific_capacity_reason_and_public_credential_revocation():
    from pocket_lab_test_utils import ensure_runtime_path
    ensure_runtime_path()
    from api_fastapi.services import lite_photo_backup as backup
    assert backup._capacity_diagnostic({
        "status": "unavailable", "identity_mismatch": True
    }) == "destination_identity_mismatch"
    assert backup._public_job({
        "backup_id": "photo-example", "status": "cancelled",
        "credential_revoke_status_internal": "pending",
        "credential_ref_internal": "secret-ref",
    })["credential_revoke_status"] == "pending"
    assert "credential_ref_internal" not in backup._public_job({
        "credential_ref_internal": "secret-ref"})
