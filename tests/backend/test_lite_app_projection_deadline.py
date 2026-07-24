from __future__ import annotations

import time

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _module():
    ensure_runtime_path()
    from api_fastapi.services import lite_app_lifecycle

    return lite_app_lifecycle


def test_app_stage_collection_uses_one_absolute_deadline(monkeypatch: pytest.MonkeyPatch):
    lifecycle = _module()
    monkeypatch.setenv("POCKETLAB_LITE_APP_STAGE_DEADLINE_SECONDS", "0.25")
    monkeypatch.setattr(lifecycle.CONTROL_PLANE, "app_current_subprojections", lambda *args, **kwargs: None)

    def slow_mapping(*args, **kwargs):
        time.sleep(0.8)
        return {"status": "ready"}

    monkeypatch.setattr(lifecycle, "_catalog_app", slow_mapping)
    monkeypatch.setattr(lifecycle, "_media_payload", slow_mapping)
    monkeypatch.setattr(lifecycle.lite_app_operations, "app_operation_status", slow_mapping)
    monkeypatch.setattr(lifecycle.lite_app_update, "update_status", slow_mapping)
    monkeypatch.setattr(lifecycle, "app_backup_subprojection", slow_mapping)
    monkeypatch.setattr(lifecycle, "app_security_subprojection", slow_mapping)
    monkeypatch.setattr(lifecycle.lite_recovery_subprojections, "app_backup_targets", slow_mapping)
    reconciliations: list[object] = []
    monkeypatch.setattr(
        lifecycle,
        "_schedule_saved_stage_reconciliation",
        lambda callbacks: reconciliations.append(callbacks),
    )

    timings: dict[str, float] = {}
    started = time.monotonic()
    result = lifecycle._collect_app_stages(timings)
    elapsed = time.monotonic() - started

    assert elapsed < 0.65
    assert reconciliations
    assert set(result) == {
        "catalog", "media", "operations", "update", "backup", "security", "backup_targets"
    }
    assert any(value.get("refresh_pending") is True for value in result.values())
    assert all(value.get("read_degraded") is True for value in result.values())
    assert max(timings.values()) < 700.0


def test_app_stage_saved_values_return_without_waiting(monkeypatch: pytest.MonkeyPatch):
    lifecycle = _module()
    monkeypatch.setenv("POCKETLAB_LITE_APP_STAGE_DEADLINE_SECONDS", "0.25")
    saved = {
        "projection_age_ms": 42,
        "catalog": {"status": "ready"},
        "media": {"status": "ready"},
        "operations": {"status": "ready"},
        "update": {"status": "ready"},
        "backup": {"kind": "raw", "payload": {"status": "ready"}},
        "security": {"kind": "raw", "payload": {"status": "ready"}},
        "backup_targets": {"status": "ready"},
    }
    monkeypatch.setattr(lifecycle.CONTROL_PLANE, "app_current_subprojections", lambda *args, **kwargs: saved)
    reconciliations: list[object] = []
    monkeypatch.setattr(
        lifecycle,
        "_schedule_saved_stage_reconciliation",
        lambda callbacks: reconciliations.append(callbacks),
    )

    started = time.monotonic()
    result = lifecycle._collect_app_stages({})
    elapsed = time.monotonic() - started

    assert elapsed < 0.1
    assert reconciliations
    assert all(value.get("projection_only") is True for value in result.values())
    assert all(value.get("projection_age_ms") == 42 for value in result.values())


def test_app_stage_deadline_configuration_is_bounded(monkeypatch: pytest.MonkeyPatch):
    lifecycle = _module()

    monkeypatch.setenv("POCKETLAB_LITE_APP_STAGE_DEADLINE_SECONDS", "0")
    assert lifecycle._app_stage_deadline_seconds() == 0.25
    monkeypatch.setenv("POCKETLAB_LITE_APP_STAGE_DEADLINE_SECONDS", "999")
    assert lifecycle._app_stage_deadline_seconds() == 4.0
    monkeypatch.setenv("POCKETLAB_LITE_APP_STAGE_DEADLINE_SECONDS", "invalid")
    assert lifecycle._app_stage_deadline_seconds() == 1.5


def test_reconciliation_deadline_configuration_is_bounded(monkeypatch: pytest.MonkeyPatch):
    lifecycle = _module()

    monkeypatch.setenv("POCKETLAB_LITE_APP_RECONCILE_DEADLINE_SECONDS", "0")
    assert lifecycle._reconcile_deadline_seconds() == 1.0
    monkeypatch.setenv("POCKETLAB_LITE_APP_RECONCILE_DEADLINE_SECONDS", "999")
    assert lifecycle._reconcile_deadline_seconds() == 15.0
    monkeypatch.setenv("POCKETLAB_LITE_APP_RECONCILE_DEADLINE_SECONDS", "invalid")
    assert lifecycle._reconcile_deadline_seconds() == 4.0
