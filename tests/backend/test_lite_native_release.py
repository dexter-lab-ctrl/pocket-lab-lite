from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import zipfile

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    database = tmp_path / "state" / "pocketlab-lite.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(database))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(database.parent))
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    monkeypatch.setenv("POCKETLAB_LITE_RELEASE_REPO", "dexter-lab-ctrl/pocket-lab-lite")
    monkeypatch.setenv(
        "POCKETLAB_LITE_VERIFIED_ORIGIN",
        "https://github.com/dexter-lab-ctrl/pocket-lab-lite.git",
    )
    monkeypatch.setenv("POCKETLAB_LITE_SOURCE_COMMIT", "a" * 40)
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.runtime import SQLITE_READS
    from api_fastapi.services import release_runtime

    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    release_runtime._OPERATION_LOCK = None
    release_runtime.initialize_release_runtime()
    return release_runtime


def _pwa_tree(
    root: Path, tag: str, commit: str = "b" * 40, *, install_mode: str = "release"
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(exist_ok=True)
    (root / "index.html").write_text("<title>Pocket Lab Lite</title>", encoding="utf-8")
    (root / "manifest.webmanifest").write_text(
        json.dumps({"name": "Pocket Lab Lite"}), encoding="utf-8"
    )
    (root / "sw.js").write_text("self.addEventListener('fetch', () => {});", encoding="utf-8")
    (root / "assets" / "app.js").write_text("console.log('lite')", encoding="utf-8")
    (root / "assets" / "app.css").write_text("body{}", encoding="utf-8")
    (root / "pocketlab-lite-build.json").write_text(
        json.dumps(
            {
                "product": "pocket-lab-lite",
                "install_mode": install_mode,
                "release_tag": tag,
                "source_commit": commit,
            }
        ),
        encoding="utf-8",
    )
    return root


def test_lite_tag_parser_is_calendar_aware_and_ordered():
    ensure_runtime_path()
    from api_fastapi.services.lite_release_contract import (
        LiteReleaseContractError,
        newest_valid_release,
        parse_lite_tag,
    )

    assert parse_lite_tag("lite-2026.07.28.2") > parse_lite_tag("lite-2026.07.28.1")
    assert parse_lite_tag("lite-2026.08.01.1") > parse_lite_tag("lite-2026.07.31.99")
    for invalid in (
        "v1.0.0",
        "release/2026.06.15.1",
        "2026.06.15.1",
        "main",
        "latest",
        "lite-2026.02.30.1",
        "lite-2026.07.28.0",
    ):
        with pytest.raises(LiteReleaseContractError):
            parse_lite_tag(invalid)
    selected = newest_valid_release(
        [
            {"tag_name": "v9.9.9", "draft": False, "prerelease": False},
            {"tag_name": "lite-2026.07.28.2", "draft": False, "prerelease": False},
            {"tag_name": "lite-2026.07.29.1", "draft": True, "prerelease": False},
            {"tag_name": "lite-2026.07.28.3", "draft": False, "prerelease": True},
        ],
        allow_prerelease=False,
    )
    assert selected["tag_name"] == "lite-2026.07.28.2"


def test_lite_repository_binding_normalizes_and_fails_closed(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services.lite_release_contract import normalize_repository, verify_repository

    assert normalize_repository("git@github.com:dexter-lab-ctrl/pocket-lab-lite.git") == (
        "dexter-lab-ctrl/pocket-lab-lite"
    )
    assert normalize_repository("https://github.com/dexter-lab-ctrl/pocket-lab-lite.git") == (
        "dexter-lab-ctrl/pocket-lab-lite"
    )
    verified = verify_repository(
        "dexter-lab-ctrl/pocket-lab-lite",
        "git@github.com:dexter-lab-ctrl/pocket-lab-lite.git",
    )
    assert verified["repository_match"] is True
    mismatch = verify_repository(
        "dexter-lab-ctrl/pocket-lab-lite",
        "https://github.com/dexter-lab-ctrl/pocket-lab.git",
    )
    assert mismatch["repository_match"] is False
    assert mismatch["failure_code"] == "release_product_mismatch"


def test_manifest_and_asset_contract_rejects_wrong_product_and_duplicates():
    ensure_runtime_path()
    from api_fastapi.services.lite_release_contract import (
        LiteReleaseContractError,
        select_assets,
        validate_manifest,
    )

    digest = "a" * 64
    valid = {
        "product": "pocket-lab-lite",
        "schema_version": 1,
        "release_tag": "lite-2026.07.28.1",
        "artifact": "dist.zip",
        "artifact_sha256": digest,
        "source_commit": "b" * 40,
        "target": "web-pwa",
        "created_at": "2026-07-28T00:00:00Z",
    }
    assert validate_manifest(
        valid, release_tag="lite-2026.07.28.1", checksum_sha256=digest
    )["product"] == "pocket-lab-lite"
    with pytest.raises(LiteReleaseContractError) as wrong:
        validate_manifest(
            {**valid, "product": "pocket-lab"},
            release_tag="lite-2026.07.28.1",
            checksum_sha256=digest,
        )
    assert wrong.value.code == "release_manifest_wrong_product"
    with pytest.raises(LiteReleaseContractError) as duplicate:
        select_assets(
            {
                "assets": [
                    {"name": "dist.zip", "size": 1, "browser_download_url": "https://a"},
                    {"name": "dist.zip", "size": 1, "browser_download_url": "https://b"},
                    {"name": "checksums.txt", "size": 1, "browser_download_url": "https://c"},
                    {
                        "name": "pocketlab-lite-release.json",
                        "size": 1,
                        "browser_download_url": "https://d",
                    },
                ]
            }
        )
    assert duplicate.value.code == "release_asset_duplicate"


def test_safe_zip_extraction_preserves_bytes_and_rejects_traversal(tmp_path):
    ensure_runtime_path()
    from api_fastapi.services.lite_release_contract import (
        LiteReleaseContractError,
        safe_extract_zip,
    )

    archive = tmp_path / "safe.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("index.html", b"Pocket Lab Lite")
        handle.writestr("manifest.webmanifest", b"{}")
    destination = tmp_path / "safe"
    safe_extract_zip(archive, destination)
    assert (destination / "index.html").read_bytes() == b"Pocket Lab Lite"

    malicious = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious, "w") as handle:
        handle.writestr("../escaped.txt", b"blocked")
    with pytest.raises(LiteReleaseContractError) as error:
        safe_extract_zip(malicious, tmp_path / "blocked")
    assert error.value.code == "release_archive_path_traversal"
    assert not (tmp_path / "escaped.txt").exists()


def test_pwa_archive_inspection_defaults_validate_lite_identity(tmp_path):
    ensure_runtime_path()
    from api_fastapi.services.lite_release_contract import inspect_pwa_archive

    archive = tmp_path / "dist.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        handle.writestr("index.html", "<title>Pocket Lab Lite</title>")
        handle.writestr("manifest.webmanifest", json.dumps({"name": "Pocket Lab Lite"}))
        handle.writestr("sw.js", "self.addEventListener('fetch', () => {})")
        handle.writestr("assets/app.js", "console.log('lite')")
        handle.writestr("assets/app.css", "body{}")
        handle.writestr(
            "pocketlab-lite-build.json",
            json.dumps(
                {
                    "product": "pocket-lab-lite",
                    "install_mode": "release",
                    "release_tag": "lite-2026.07.28.1",
                    "source_commit": "b" * 40,
                }
            ),
        )

    inspected = inspect_pwa_archive(archive)
    assert inspected["pwa_identity"] == "pocket-lab-lite"
    assert inspected["representative_js"] == ["assets/app.js"]
    assert inspected["representative_css"] == ["assets/app.css"]
    assert inspected["service_worker"] == ["sw.js"]


def test_installed_identity_migrates_legacy_to_source_and_is_change_only(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("POCKETLAB_RELEASE_TAG", "v1.0.0")
    release_runtime = _runtime(tmp_path, monkeypatch)
    identity = release_runtime.read_installed_identity()
    assert identity["install_mode"] == "source"
    assert identity["release_tag"] == ""
    assert identity["verified"] is True
    assert identity["migration_status"] == "legacy_identity_discarded"
    first_revision = identity["identity_revision"]
    same = release_runtime._write_installed_identity(
        {
            "install_mode": "source",
            "source_repository": "dexter-lab-ctrl/pocket-lab-lite",
            "source_commit": "a" * 40,
            "release_tag": "",
            "artifact_name": "",
            "artifact_sha256": "",
            "installed_at": None,
            "installer_schema": 1,
            "verified": True,
            "migration_status": "legacy_identity_discarded",
        }
    )
    assert same["identity_revision"] == first_revision
    installed = release_runtime._write_installed_identity(
        {
            "install_mode": "release",
            "source_repository": "dexter-lab-ctrl/pocket-lab-lite",
            "source_commit": "b" * 40,
            "release_tag": "lite-2026.07.28.1",
            "artifact_name": "dist.zip",
            "artifact_sha256": "c" * 64,
            "installed_at": "2026-07-28T00:00:00Z",
            "installer_schema": 1,
            "verified": True,
            "migration_status": "native_release_installed",
        }
    )
    assert installed["install_mode"] == "release"
    assert installed["release_tag"] == "lite-2026.07.28.1"
    assert installed["identity_revision"] == first_revision + 1


def test_stage_fails_closed_on_disk_pressure_and_cleans_partial_state(
    tmp_path, monkeypatch
):
    ensure_runtime_path()
    from api_fastapi.services import release_update_process

    tag = "lite-2026.07.28.1"
    artifact = tmp_path / "fixture-dist.zip"
    artifact.write_bytes(b"bounded-artifact")
    import hashlib

    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    checksums = tmp_path / "checksums.txt"
    checksums.write_text(f"{digest}  dist.zip\n", encoding="utf-8")
    manifest = tmp_path / "pocketlab-lite-release.json"
    manifest.write_text(json.dumps({
        "product": "pocket-lab-lite",
        "schema_version": 1,
        "release_tag": tag,
        "artifact": "dist.zip",
        "artifact_sha256": digest,
        "source_commit": "b" * 40,
        "target": "web-pwa",
        "created_at": "2026-07-28T00:00:00Z",
    }), encoding="utf-8")
    fixtures = {
        "fixture://dist": artifact,
        "fixture://checksums": checksums,
        "fixture://manifest": manifest,
    }

    def fake_download(url, target, *, timeout, max_bytes):
        source = fixtures[url]
        target.write_bytes(source.read_bytes())
        return hashlib.sha256(target.read_bytes()).hexdigest(), target.stat().st_size

    monkeypatch.setattr(release_update_process, "_download_to_file", fake_download)
    monkeypatch.setattr(
        release_update_process.shutil,
        "disk_usage",
        lambda _path: type("Usage", (), {"free": 0})(),
    )
    staging_root = tmp_path / "staging"
    target = staging_root / "generation-1-lite-2026.07.28.1"
    with pytest.raises(release_update_process.ReleaseProcessFailure) as error:
        release_update_process._stage({
            "release_tag": tag,
            "staging_root": str(staging_root),
            "target_dir": str(target),
            "assets": {
                "dist.zip": {"download_url": "fixture://dist", "size": artifact.stat().st_size},
                "checksums.txt": {"download_url": "fixture://checksums", "size": checksums.stat().st_size},
                "pocketlab-lite-release.json": {"download_url": "fixture://manifest", "size": manifest.stat().st_size},
            },
        })
    assert error.value.code == "release_disk_pressure"
    assert not target.exists()


def test_atomic_promotion_validation_and_rollback(tmp_path, monkeypatch):
    release_runtime = _runtime(tmp_path, monkeypatch)
    releases = tmp_path / "pwa" / "releases"
    old = _pwa_tree(
        releases / "source-existing", "source-existing", install_mode="source"
    )
    new_content = _pwa_tree(tmp_path / "staged" / "content", "lite-2026.07.28.1")
    current = tmp_path / "pwa" / "current"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.symlink_to(os.path.relpath(old, current.parent), target_is_directory=True)
    caddyfile = tmp_path / "Caddyfile"
    caddyfile.write_text(f":8443 {{\n  root * {current}\n  file_server\n}}\n", encoding="utf-8")

    promoted, _metrics = asyncio.run(
        release_runtime.execute_release_subprocess(
            "promote",
            {
                "release_tag": "lite-2026.07.28.1",
                "content_path": str(new_content),
                "current_link": str(current),
                "releases_dir": str(releases),
                "caddyfile": str(caddyfile),
            },
        )
    )
    assert promoted["rollback_available"] is True
    assert current.is_symlink()
    assert current.resolve().name == "lite-2026.07.28.1"
    validated, _metrics = asyncio.run(
        release_runtime.execute_release_subprocess(
            "validate",
            {
                "release_tag": "lite-2026.07.28.1",
                "current_link": str(current),
                "representative_assets": ["assets/app.js", "assets/app.css", "sw.js"],
            },
        )
    )
    assert validated["validation_status"] == "passed"
    rolled_back, _metrics = asyncio.run(
        release_runtime.execute_release_subprocess(
            "rollback",
            {"current_link": str(current), "releases_dir": str(releases)},
        )
    )
    assert rolled_back["rollback_status"] == "rolled_back"
    assert current.resolve().name == "source-existing"
    source_validated, _metrics = asyncio.run(
        release_runtime.execute_release_subprocess(
            "validate",
            {
                "release_tag": "source-existing",
                "install_mode": "source",
                "current_link": str(current),
                "representative_assets": ["assets/app.js", "assets/app.css", "sw.js"],
            },
        )
    )
    assert source_validated["validation_status"] == "passed"
    assert source_validated["install_mode"] == "source"


def test_worker_restart_recovery_rolls_back_and_cleans_abandoned_generation(
    tmp_path, monkeypatch
):
    release_runtime = _runtime(tmp_path, monkeypatch)
    pwa_root = tmp_path / "pwa"
    releases = pwa_root / "releases"
    previous_release = _pwa_tree(
        releases / "source-existing", "source-existing", install_mode="source"
    )
    promoted_release = _pwa_tree(
        releases / "lite-2026.07.28.1", "lite-2026.07.28.1"
    )
    current = pwa_root / "current"
    previous = pwa_root / "previous"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.symlink_to(
        os.path.relpath(promoted_release, current.parent), target_is_directory=True
    )
    previous.symlink_to(
        os.path.relpath(previous_release, previous.parent), target_is_directory=True
    )
    staging_root = tmp_path / "state" / "release-staging"
    monkeypatch.setenv("POCKETLAB_RELEASE_STAGING_DIR", str(staging_root))
    monkeypatch.setenv("POCKETLAB_LITE_PWA_CURRENT_LINK", str(current))
    monkeypatch.setenv("POCKETLAB_LITE_PWA_RELEASES_DIR", str(releases))

    lease = release_runtime.claim_release_operation(
        "apply", "apply-before-worker-restart", lease_seconds=30
    )
    release_runtime.update_release_stage(lease, phase="installing")
    abandoned = staging_root / f"generation-{lease.generation}-lite-2026.07.28.1"
    abandoned.mkdir(parents=True)
    (abandoned / "partial").write_text("partial", encoding="utf-8")
    from api_fastapi.db.connection import connection

    with connection() as conn:
        conn.execute(
            "UPDATE release_runtime_projection SET lease_expires_epoch_ms = 0 "
            "WHERE owner = 'release'"
        )

    recovered = asyncio.run(release_runtime.recover_abandoned_release_operation())
    assert recovered["recovered"] is True
    assert recovered["rollback_status"] == "rolled_back"
    assert recovered["failure_code"] == "release_worker_restart_recovered"
    assert current.resolve() == previous_release.resolve()
    assert not abandoned.exists()
    status = release_runtime.read_release_status()
    assert status["active_generation"] == 0
    assert status["last_failure_stage"] == "installing"
    assert status["last_rollback_status"] == "rolled_back"


def test_post_switch_validation_rejects_unexpected_pm2_restart(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import release_update_process

    release = _pwa_tree(
        tmp_path / "pwa" / "releases" / "lite-2026.07.28.1",
        "lite-2026.07.28.1",
    )
    current = tmp_path / "pwa" / "current"
    current.parent.mkdir(parents=True, exist_ok=True)
    current.symlink_to(os.path.relpath(release, current.parent), target_is_directory=True)
    monkeypatch.setattr(
        release_update_process,
        "_pm2_restart_snapshot",
        lambda: {"pocket-api": 2, "pocket-worker": 1, "caddy-proxy": 0},
    )

    with pytest.raises(release_update_process.ReleaseProcessFailure) as error:
        release_update_process._validate(
            {
                "release_tag": "lite-2026.07.28.1",
                "install_mode": "release",
                "current_link": str(current),
                "representative_assets": ["assets/app.js", "assets/app.css", "sw.js"],
                "pm2_restart_baseline": {
                    "pocket-api": 1,
                    "pocket-worker": 1,
                    "caddy-proxy": 0,
                },
            }
        )
    assert error.value.code == "release_unexpected_process_restart"


def test_promotion_fails_closed_when_caddy_root_is_not_current_pointer(
    tmp_path, monkeypatch
):
    release_runtime = _runtime(tmp_path, monkeypatch)
    releases = tmp_path / "pwa" / "releases"
    current = tmp_path / "pwa" / "current"
    content = _pwa_tree(tmp_path / "staged" / "content", "lite-2026.07.28.1")
    caddyfile = tmp_path / "Caddyfile"
    caddyfile.write_text(":8443 {\n  root * /wrong/static/root\n}\n", encoding="utf-8")
    with pytest.raises(release_runtime.ReleaseSubprocessError) as error:
        asyncio.run(
            release_runtime.execute_release_subprocess(
                "promote",
                {
                    "release_tag": "lite-2026.07.28.1",
                    "content_path": str(content),
                    "current_link": str(current),
                    "releases_dir": str(releases),
                    "caddyfile": str(caddyfile),
                },
            )
        )
    assert error.value.code == "release_caddy_static_root_mismatch"
    assert not current.exists()


def test_compatibility_dependency_uses_lite_identity_and_fail_closed_defaults(monkeypatch):
    ensure_runtime_path()
    monkeypatch.delenv("POCKETLAB_LITE_RELEASE_TAG", raising=False)
    monkeypatch.delenv("POCKETLAB_LITE_RELEASE_REPO", raising=False)
    monkeypatch.delenv("POCKETLAB_RELEASE_STABLE_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("POCKETLAB_AUTO_RELEASE_APPLY", raising=False)
    from api_fastapi import deps

    deps.core.AUTO_UPDATER = None
    updater = deps.ensure_release_updater()
    try:
        assert updater.current_tag_override == ""
        assert updater.github_repo == "dexter-lab-ctrl/pocket-lab-lite"
        assert updater.poll_interval == 12 * 3600
        assert updater.auto_apply is False
        assert updater.start() is False
    finally:
        deps.core.AUTO_UPDATER = None


def test_release_defaults_are_low_power_and_auto_apply_stays_off(monkeypatch):
    ensure_runtime_path()
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "worker")
    monkeypatch.delenv("POCKETLAB_RELEASE_STABLE_INTERVAL_SECONDS", raising=False)
    monkeypatch.delenv("POCKETLAB_AUTO_RELEASE_APPLY", raising=False)
    from api_fastapi.services import release_runtime

    assert release_runtime.stable_release_interval_seconds() == 12 * 3600
    request = release_runtime.build_check_request()
    assert request["configured_repository"] == "dexter-lab-ctrl/pocket-lab-lite"
    assert request["auto_apply"] is False
    assert "/releases?" in request["source_url"]
    assert "/releases/latest" not in request["source_url"]


def test_lite_release_frontend_uses_existing_safe_state_and_lifecycle_layers():
    root = Path(__file__).resolve().parents[2]
    card = (root / "src" / "lite" / "LiteReleaseUpdateCard.jsx").read_text(encoding="utf-8")
    home = (root / "src" / "lite" / "LiteHome.jsx").read_text(encoding="utf-8")
    api = (root / "src" / "lib" / "liteApi.js").read_text(encoding="utf-8")
    snapshots = (root / "src" / "lib" / "liteSafeSnapshots.js").read_text(encoding="utf-8")
    machine = (root / "src" / "machines" / "liteReleaseUpdateMachine.js").read_text(encoding="utf-8")
    router = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "routers"
        / "release.py"
    ).read_text(encoding="utf-8")
    worker = (
        root
        / "pocket-lab-final-structure"
        / "runtime"
        / "workers"
        / "pocketlab_worker.py"
    ).read_text(encoding="utf-8")
    combined = "\n".join((card, home, api, snapshots, machine))
    assert "useLiteResource" in card
    assert "useLiteMutation" in card
    assert "useMachine" in card
    assert "liteReleaseUpdateMachine" in machine
    assert "LiteReleaseUpdateCard" in home
    assert "safeGet('/api/lite/release')" in api
    assert "postJson('/api/lite/release/check'" in api
    assert "postJson('/api/lite/release/apply'" in api
    assert "'/api/lite/release'" in snapshots
    assert "BUS.publish_json" not in router
    assert "release_apply_failure_fence" in worker
    assert "POCKETLAB_RELEASE_STABLE_INTERVAL_SECONDS" in worker
    for label in (
        "Up to date",
        "Update available",
        "Checking for updates",
        "Downloading update",
        "Preparing update",
        "Installing update",
        "Checking the update",
        "Update failed",
        "Rolled back safely",
        "Update source not verified",
        "Installed from source",
    ):
        assert label in card
    for forbidden in ("pocket_lab_iac", "site.yml", "deploy_blueprint", "drift_scan", "Gitea", "Ansible"):
        assert forbidden not in combined
    assert "migrate_legacy_lite_pwa_root" in (
        root
        / "pocket-lab-final-structure"
        / "pocket-lab-bootstrap-production-scripts-patched"
        / "scripts"
        / "start-dashboard.sh"
    ).read_text(encoding="utf-8")
