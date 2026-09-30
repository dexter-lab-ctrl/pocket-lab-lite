from __future__ import annotations

import asyncio
import importlib.util
import subprocess
import sys
from pathlib import Path

from pocket_lab_test_utils import ensure_runtime_path


def _module():
    ensure_runtime_path()
    runtime = Path(__file__).resolve().parents[2] / "pocket-lab-final-structure" / "runtime"
    agents = runtime / "agents"
    if str(agents) not in sys.path:
        sys.path.insert(0, str(agents))
    path = agents / "lite_photo_backup_agent.py"
    spec = importlib.util.spec_from_file_location("lite_photo_backup_agent_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_transfer_contract_is_copy_only_and_atomic():
    module = _module()
    source = Path(module.__file__).read_text(encoding="utf-8")

    assert '"copyto"' in source
    assert '"moveto"' in source
    assert ".pocketlab-upload" in source
    assert '"sync"' not in source
    assert '"delete"' not in source
    assert '"purge"' not in source
    assert "--delete" not in source


def test_agent_inventory_is_media_only_and_skips_nomedia(tmp_path, monkeypatch):
    module = _module()
    camera = tmp_path / "DCIM"
    pictures = tmp_path / "Pictures"
    movies = tmp_path / "Movies"
    camera.mkdir()
    pictures.mkdir()
    movies.mkdir()

    (camera / "new.jpg").write_bytes(b"photo")
    (camera / "note.txt").write_text("not media", encoding="utf-8")
    excluded = camera / "Documents"
    excluded.mkdir()
    (excluded / "document.jpg").write_bytes(b"not eligible")
    hidden = pictures / "HiddenAlbum"
    hidden.mkdir()
    (hidden / ".nomedia").write_text("", encoding="utf-8")
    (hidden / "private.jpg").write_bytes(b"private")
    (movies / "clip.mp4").write_bytes(b"video")

    roots = {
        "camera": camera,
        "pictures": pictures,
        "videos": movies,
    }
    monkeypatch.setattr(module, "_collection_path", lambda collection: roots[collection])

    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="https://pocket.test.ts.net",
    )
    inventory = provider._inventory(["camera", "pictures", "videos"])

    keys = {(item["collection"], item["relative"]) for item in inventory}
    assert ("camera", "new.jpg") in keys
    assert ("videos", "clip.mp4") in keys
    assert not any("Documents" in relative for _, relative in keys)
    assert not any("HiddenAlbum" in relative for _, relative in keys)
    assert not any(relative.endswith(".txt") for _, relative in keys)


def test_same_name_conflict_gets_deterministic_version_suffix():
    module = _module()
    item = {"size": 1234, "mtime": 1788609600.0}
    first = module.PhotoPrismWebDAVProvider._conflict_relative("Camera/photo.jpg", item)
    second = module.PhotoPrismWebDAVProvider._conflict_relative("Camera/photo.jpg", item)

    assert first == second
    assert first.endswith(".jpg")
    assert ".pocketlab-v" in first
    assert first != "Camera/photo.jpg"


def test_rclone_password_is_obscured_over_stdin_not_argv(tmp_path, monkeypatch):
    module = _module()
    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="https://pocket.test.ts.net",
    )
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="obscured-value\n", stderr="")

    monkeypatch.setattr(provider, "_run", fake_run)
    config = provider._make_config(
        "/usr/bin/rclone",
        {
            "password": "raw-password",
            "username": "admin",
            "webdav_url": "https://pocket.test.ts.net/apps/photoprism/originals/",
        },
        tmp_path,
    )

    args, kwargs = calls[0]
    assert args == ["/usr/bin/rclone", "obscure", "-"]
    assert kwargs["input_text"] == "raw-password\n"
    assert "raw-password" not in " ".join(args)
    assert "raw-password" not in config.read_text(encoding="utf-8")
    assert oct(config.stat().st_mode & 0o777) == "0o600"


def test_missing_rclone_reports_degraded_without_arbitrary_install(monkeypatch):
    module = _module()
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    result = module.repair_rclone()
    assert result["status"] == "failed"
    assert result["rclone_available"] is False


def test_provider_rejects_non_https_control_origin():
    module = _module()
    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="http://192.0.2.1:8443",
    )
    try:
        provider._request_json("/api/lite/internal/photo-backup/test")
    except RuntimeError as exc:
        assert str(exc) == "secure_control_origin_required"
    else:
        raise AssertionError("HTTP control origin must fail closed")



def test_remote_listing_failure_is_fail_closed(monkeypatch, tmp_path):
    module = _module()
    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="https://pocket.test.ts.net",
    )
    monkeypatch.setattr(
        provider,
        "_run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=["rclone"], returncode=1, stdout="", stderr=""
        ),
    )
    try:
        provider._remote_listing(
            "/usr/bin/rclone",
            tmp_path / "rclone.conf",
            "PocketLab/Devices/storage-phone",
        )
    except RuntimeError as exc:
        assert str(exc) == "remote_listing_failed"
    else:
        raise AssertionError("Remote inventory errors must fail closed")


def test_empty_readable_gallery_completes_as_safe_noop(monkeypatch, tmp_path):
    module = _module()
    camera = tmp_path / "DCIM"
    camera.mkdir()
    monkeypatch.setattr(module, "_collection_path", lambda _name: camera)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/rclone" if name == "rclone" else None)

    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="https://pocket.test.ts.net",
    )
    monkeypatch.setattr(
        provider,
        "_credential",
        lambda *_args: {
            "capacity": {"safe_upload_budget_bytes": 10_000},
            "password": "one-time",
            "username": "admin",
            "webdav_url": "https://pocket.test.ts.net/apps/photoprism/originals/",
            "destination_prefix": "PocketLab/Devices/storage-phone",
        },
    )
    monkeypatch.setattr(provider, "_inventory", lambda _collections: [])
    reports = []
    monkeypatch.setattr(provider, "_post_progress", lambda _backup_id, payload: reports.append(payload))

    result = provider.backup(
        backup_id="photo-empty",
        credential_ref="cred-ref",
        collections=["camera"],
    )

    assert result["status"] == "completed"
    assert result["items_total"] == 0
    assert result["bytes_total_required"] == 0
    assert result["photo_processing_state"] == "not_needed"
    assert "nothing new" in result["progress"]["step"].lower()
    assert reports[-1]["status"] == "completed"


def test_destination_namespace_fallback_is_device_scoped():
    module = _module()
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "PocketLab/Devices/{self.node_id}" in source
    assert "PocketLab/{self.node_id}" not in source


def test_partial_progress_percent_uses_required_bytes_not_only_selected_bytes():
    module = _module()
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "bytes_transferred\n                                / required_bytes" in source
    assert "bytes_total_required" in source
    assert "bytes_remaining" in source



def test_missing_device_namespace_is_treated_as_empty_but_auth_failure_is_not(monkeypatch, tmp_path):
    module = _module()
    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="https://pocket.test.ts.net",
    )
    responses = iter([
        subprocess.CompletedProcess(args=["rclone"], returncode=3, stdout="", stderr="directory not found"),
        subprocess.CompletedProcess(args=["rclone"], returncode=1, stdout="", stderr="401 unauthorized"),
    ])
    monkeypatch.setattr(provider, "_run", lambda *_args, **_kwargs: next(responses))

    assert provider._remote_listing(
        "/usr/bin/rclone",
        tmp_path / "rclone.conf",
        "PocketLab/Devices/storage-phone",
    ) == {}

    try:
        provider._remote_listing(
            "/usr/bin/rclone",
            tmp_path / "rclone.conf",
            "PocketLab/Devices/storage-phone",
        )
    except RuntimeError as exc:
        assert str(exc) == "remote_listing_failed"
    else:
        raise AssertionError("Authentication failures must not look like an empty backup destination")


def test_remote_collection_names_are_human_friendly():
    module = _module()
    assert module.PhotoPrismWebDAVProvider._remote_key("camera", "2026/photo.jpg") == "DCIM/2026/photo.jpg"
    assert module.PhotoPrismWebDAVProvider._remote_key("pictures", "album/photo.jpg") == "Pictures/album/photo.jpg"
    assert module.PhotoPrismWebDAVProvider._remote_key("videos", "clip.mp4") == "Movies/clip.mp4"



def test_conflict_count_is_aggregate_only_and_versioning_is_non_destructive(monkeypatch, tmp_path):
    module = _module()
    camera = tmp_path / "DCIM"
    camera.mkdir()
    source = camera / "photo.jpg"
    source.write_bytes(b"new-content")
    monkeypatch.setattr(module, "_collection_path", lambda _name: camera)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/rclone" if name == "rclone" else None)

    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="https://pocket.test.ts.net",
    )
    monkeypatch.setattr(
        provider,
        "_credential",
        lambda *_args: {
            "capacity": {
                "safe_upload_budget_bytes": 10_000_000,
                "hard_upload_budget_bytes": 10_000_000,
            },
            "password": "one-time",
            "username": "admin",
            "webdav_url": "https://pocket.test.ts.net/apps/photoprism/originals/",
            "destination_prefix": "PocketLab/Devices/storage-phone",
        },
    )
    monkeypatch.setattr(
        provider,
        "_remote_listing",
        lambda *_args: {
            "DCIM/photo.jpg": {"size": 1, "mtime": 1.0},
        },
    )
    monkeypatch.setattr(
        provider,
        "_capacity",
        lambda *_args: {"hard_upload_budget_bytes": 10_000_000},
    )
    transfers = []
    monkeypatch.setattr(
        provider,
        "_make_config",
        lambda *_args: tmp_path / "rclone.conf",
    )
    monkeypatch.setattr(
        provider,
        "_transfer_one",
        lambda _rclone, _config, _item, remote_relative, _prefix: transfers.append(remote_relative),
    )
    reports = []
    monkeypatch.setattr(provider, "_post_progress", lambda _backup_id, payload: reports.append(payload))

    result = provider.backup(
        backup_id="photo-conflict",
        credential_ref="cred-ref",
        collections=["camera"],
    )

    assert result["status"] == "completed"
    assert result["conflicts"] == 1
    assert len(transfers) == 1
    assert transfers[0] != "DCIM/photo.jpg"
    assert ".pocketlab-v" in transfers[0]
    assert "photo.jpg" not in str({k: v for k, v in result.items() if k != "summary"})



def test_progress_post_preserves_safe_aggregate_fields(monkeypatch):
    module = _module()
    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="https://pocket.test.ts.net",
    )
    captured = {}
    monkeypatch.setattr(
        provider,
        "_request_json",
        lambda path, **kwargs: captured.update(path=path, **kwargs) or {"ok": True},
    )
    delivered = provider._post_progress(
        "photo-aggregate",
        {
            "status": "completed",
            "conflicts": 2,
            "bytes_total": 5000,
            "bytes_total_planned": 5000,
            "bytes_total_required": 5000,
            "bytes_transferred": 5000,
            "bytes_remaining": 0,
            "photo_processing_state": "processing",
        },
    )
    assert delivered is True
    body = captured["body"]
    assert body["conflicts"] == 2
    assert body["bytes_total_required"] == 5000
    assert body["bytes_total_planned"] == 5000
    assert body["bytes_remaining"] == 0
    assert body["photo_processing_state"] == "processing"
    assert "password" not in str(body).lower()
    assert "path" not in str(body).lower()


def test_node_agent_restart_marker_contains_only_non_secret_job_identity():
    ensure_runtime_path()
    path = (
        Path(__file__).resolve().parents[2]
        / "pocket-lab-final-structure"
        / "runtime"
        / "agents"
        / "pocketlab_node_agent.py"
    )
    source = path.read_text(encoding="utf-8")
    marker_writer = source.split(
        "def _write_photo_backup_marker", 1
    )[1].split(
        "def _clear_photo_backup_marker", 1
    )[0]
    assert "backup_id" in marker_writer
    assert "node_id" in marker_writer
    assert "started_at" in marker_writer
    assert "credential_ref" not in marker_writer
    assert "webdav_url" not in marker_writer
    assert "password" not in marker_writer



def test_capacity_drop_mid_transfer_stops_before_next_file(monkeypatch, tmp_path):
    module = _module()
    camera = tmp_path / "DCIM"
    camera.mkdir()
    first = camera / "one.jpg"
    second = camera / "two.jpg"
    first.write_bytes(b"a" * 10)
    second.write_bytes(b"b" * 10)
    monkeypatch.setattr(module, "_collection_path", lambda _name: camera)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/rclone" if name == "rclone" else None)

    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="https://pocket.test.ts.net",
    )
    monkeypatch.setattr(
        provider,
        "_credential",
        lambda *_args: {
            "capacity": {
                "safe_upload_budget_bytes": 1000,
                "hard_upload_budget_bytes": 1000,
            },
            "password": "one-time",
            "username": "admin",
            "webdav_url": "https://pocket.test.ts.net/apps/photoprism/originals/",
            "destination_prefix": "PocketLab/Devices/storage-phone",
        },
    )
    monkeypatch.setattr(provider, "_remote_listing", lambda *_args: {})
    monkeypatch.setattr(provider, "_make_config", lambda *_args: tmp_path / "rclone.conf")
    budgets = iter([
        {"hard_upload_budget_bytes": 1000},
        {"hard_upload_budget_bytes": 0},
    ])
    monkeypatch.setattr(provider, "_capacity", lambda *_args: next(budgets))
    transfers = []
    monkeypatch.setattr(
        provider,
        "_transfer_one",
        lambda _rclone, _config, item, _remote, _prefix: transfers.append(item["relative"]),
    )
    monkeypatch.setattr(provider, "_post_progress", lambda *_args, **_kwargs: True)

    result = provider.backup(
        backup_id="photo-capacity-drop",
        credential_ref="cred-ref",
        collections=["camera"],
    )
    assert result["status"] == "partial_storage_limit"
    assert result["items_transferred"] == 1
    assert result["items_remaining"] == 1
    assert len(transfers) == 1


def test_incremental_run_skips_matching_remote_and_copies_only_new_media(monkeypatch, tmp_path):
    module = _module()
    camera = tmp_path / "DCIM"
    camera.mkdir()
    old = camera / "old.jpg"
    new = camera / "new.jpg"
    old.write_bytes(b"old")
    new.write_bytes(b"new")
    old_stat = old.stat()
    monkeypatch.setattr(module, "_collection_path", lambda _name: camera)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/rclone" if name == "rclone" else None)

    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="https://pocket.test.ts.net",
    )
    monkeypatch.setattr(
        provider,
        "_credential",
        lambda *_args: {
            "capacity": {
                "safe_upload_budget_bytes": 1000,
                "hard_upload_budget_bytes": 1000,
            },
            "password": "one-time",
            "username": "admin",
            "webdav_url": "https://pocket.test.ts.net/apps/photoprism/originals/",
            "destination_prefix": "PocketLab/Devices/storage-phone",
        },
    )
    monkeypatch.setattr(
        provider,
        "_remote_listing",
        lambda *_args: {
            "DCIM/old.jpg": {
                "size": old_stat.st_size,
                "mtime": old_stat.st_mtime,
            },
        },
    )
    monkeypatch.setattr(provider, "_make_config", lambda *_args: tmp_path / "rclone.conf")
    monkeypatch.setattr(provider, "_capacity", lambda *_args: {"hard_upload_budget_bytes": 1000})
    transfers = []
    monkeypatch.setattr(
        provider,
        "_transfer_one",
        lambda _rclone, _config, item, _remote, _prefix: transfers.append(item["relative"]),
    )
    monkeypatch.setattr(provider, "_post_progress", lambda *_args, **_kwargs: True)

    result = provider.backup(
        backup_id="photo-incremental",
        credential_ref="cred-ref",
        collections=["camera"],
    )
    assert result["status"] == "completed"
    assert result["items_skipped"] == 1
    assert result["items_transferred"] == 1
    assert transfers == ["new.jpg"]



def test_cancel_targets_only_matching_active_backup_child():
    module = _module()
    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="https://pocket.test.ts.net",
    )

    class FakeProcess:
        def __init__(self):
            self.terminated = 0
        def poll(self):
            return None
        def terminate(self):
            self.terminated += 1

    process = FakeProcess()
    provider._active_backup_id = "photo-active"
    provider._process = process

    provider.cancel("photo-other")
    assert process.terminated == 0
    assert provider.cancel_event.is_set() is False

    provider.cancel("photo-active")
    assert provider.cancel_event.is_set() is True
    assert process.terminated == 1


def test_temp_rclone_state_is_removed_when_transfer_setup_fails(monkeypatch, tmp_path):
    module = _module()
    camera = tmp_path / "DCIM"
    camera.mkdir()
    (camera / "photo.jpg").write_bytes(b"photo")

    temp_root = tmp_path / "ephemeral-rclone"
    monkeypatch.setattr(module, "_collection_path", lambda _name: camera)
    monkeypatch.setattr(module.shutil, "which", lambda name: "/usr/bin/rclone" if name == "rclone" else None)

    def fake_mkdtemp(**_kwargs):
        temp_root.mkdir(parents=True, exist_ok=False)
        return str(temp_root)

    monkeypatch.setattr(module.tempfile, "mkdtemp", fake_mkdtemp)

    provider = module.PhotoPrismWebDAVProvider(
        node_id="storage-phone",
        agent_token="token",
        control_origin="https://pocket.test.ts.net",
    )
    monkeypatch.setattr(
        provider,
        "_credential",
        lambda *_args: {
            "capacity": {
                "safe_upload_budget_bytes": 1000,
                "hard_upload_budget_bytes": 1000,
            },
            "password": "one-time-secret",
            "username": "admin",
            "webdav_url": "https://pocket.test.ts.net/apps/photoprism/originals/",
            "destination_prefix": "PocketLab/Devices/storage-phone",
        },
    )

    def fake_make_config(_rclone, _credential, root):
        root.mkdir(parents=True, exist_ok=True)
        config = root / "rclone.conf"
        config.write_text("temporary-config", encoding="utf-8")
        config.chmod(0o600)
        return config

    monkeypatch.setattr(provider, "_make_config", fake_make_config)
    monkeypatch.setattr(
        provider,
        "_remote_listing",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("remote_listing_failed")),
    )
    monkeypatch.setattr(provider, "_post_progress", lambda *_args, **_kwargs: True)

    result = provider.backup(
        backup_id="photo-cleanup",
        credential_ref="cred-ref",
        collections=["camera"],
    )

    assert result["status"] == "interrupted"
    assert not temp_root.exists()


def test_rclone_subprocess_policy_never_enables_shell_execution():
    module = _module()
    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "subprocess.Popen(" in source
    assert "shell=True" not in source
    assert '"sync"' not in source
    assert '"delete"' not in source
    assert '"purge"' not in source
