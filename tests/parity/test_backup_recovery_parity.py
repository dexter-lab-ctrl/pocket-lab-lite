from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

from scripts.test.parity.parity_common import FIXTURE_ROOT, ROOT, compare_subset, load_json

RUNTIME = ROOT / "pocket-lab-final-structure" / "runtime"


def _runtime_import(module: str):
    import sys

    for value in (str(ROOT), str(RUNTIME)):
        if value not in sys.path:
            sys.path.insert(0, value)
    return importlib.import_module(module)


def test_backend_manifest_to_api_projection_is_allowlisted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path / "state"))
    manifest_module = _runtime_import("api_fastapi.services.lite_backup_manifest")
    internal = {
        "backup_id": "backup-safe",
        "created_at": "2026-01-01T00:00:00Z",
        "engine": "restic",
        "repository": {"ready": True, "engine": "restic"},
        "snapshot_id": "snapshot-safe",
        "included_sets": ["configuration"],
        "included_files": ["safe-a", "safe-b"],
        "excluded_sensitive_items": ["credentials"],
        "verification_status": "verified",
        "manifest_checksum": "abcdef1234567890",
        "summary": "Backup verified.",
        "password": "must-never-project",
        "raw_paths": ["must-never-project"],
        "restic_environment": {"RESTIC_PASSWORD": "must-never-project"},
    }
    projected = manifest_module.api_manifest(internal)
    assert projected["backup_id"] == internal["backup_id"]
    assert projected["included_file_count"] == 2
    assert "password" not in projected
    assert "raw_paths" not in projected
    assert "restic_environment" not in projected


def test_receipt_projection_excludes_backend_only_fields() -> None:
    manifest_module = _runtime_import("api_fastapi.services.lite_backup_manifest")
    receipt = manifest_module.api_receipt({
        "backup_id": "backup-safe",
        "status": "succeeded",
        "summary": "Saved.",
        "token": "must-never-project",
        "raw_log": "must-never-project",
        "private_path": "must-never-project",
    })
    assert receipt == {"backup_id": "backup-safe", "status": "succeeded", "summary": "Saved."}


def test_cursor_pagination_is_opaque_and_invalid_cursor_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path / "state"))
    policy = _runtime_import("api_fastapi.services.lite_backup_policy")
    manifests = _runtime_import("api_fastapi.services.lite_backup_manifest")
    for index in range(3):
        manifests.write_manifest({
            "backup_id": f"backup-{index}",
            "created_at": f"2026-01-0{index + 1}T00:00:00Z",
            "engine": "restic",
        })
    first = manifests.list_manifests_page(limit=2)
    assert len(first["items"]) == 2
    assert first["has_more"] is True
    assert first["next_cursor"] and "backup" not in first["next_cursor"]
    second = manifests.list_manifests_page(limit=2, cursor=first["next_cursor"])
    assert len(second["items"]) == 1
    invalid = manifests.list_manifests_page(limit=2, cursor="not-a-valid-cursor")
    assert invalid["cursor_found"] is False
    assert invalid["items"] == []


def test_api_to_selector_fixtures_cover_ready_stale_offline_and_failure() -> None:
    scenario_ids = {path.stem for path in FIXTURE_ROOT.glob("*.json")}
    assert {
        "recovery-verified",
        "recovery-projection-stale",
        "recovery-offline-snapshot",
        "recovery-backend-unavailable",
        "recovery-backup-failed",
        "recovery-restore-failed",
    }.issubset(scenario_ids)
    for scenario_id in scenario_ids:
        fixture = load_json(FIXTURE_ROOT / f"{scenario_id}.json")
        assert fixture["authority"]["raw_sqlite_rows_included"] is False
        assert fixture["authority"]["raw_manifest_included"] is False
        assert fixture["traceability"]["selector"] == "selectRecoveryScreenView"


def test_formatter_transformations_and_enum_normalization_are_explicit() -> None:
    model = load_json(ROOT / "contracts" / "parity" / "parity-model.json")
    transformations = {item["transformation"] for item in model["field_mappings"]}
    assert any("enum" in value.lower() for value in transformations)
    assert any("allowlist" in value.lower() for value in transformations)
    assert any("Restore preview ready" in value for value in transformations)
