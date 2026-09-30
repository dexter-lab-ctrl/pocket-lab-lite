from __future__ import annotations

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
