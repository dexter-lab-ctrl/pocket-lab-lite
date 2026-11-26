from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

RUNTIME_DIR = Path(__file__).resolve().parents[1]
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

os.environ.setdefault("POCKETLAB_API_TOKEN", "pocketlab-test-token")
os.environ.setdefault("POCKETLAB_TEST_AUTH_BYPASS", "1")

from api_fastapi.main import app  # noqa: E402


def test_legacy_observability_route_is_retired_without_probe_execution() -> None:
    response = TestClient(
        app,
        headers={
            "Authorization": "Bearer pocketlab-test-token",
            "X-Pocket-Lab-Token": "pocketlab-test-token",
            "X-Pocket-Lab-Test": "1",
        },
    ).get("/api/observability/status")
    assert response.status_code == 410
    detail = response.json()
    assert detail["reason_code"] == "legacy_observability_stack_retired"
    assert detail["replacement"].startswith("/api/lite/")


def test_legacy_observability_probe_is_not_a_workload() -> None:
    service_path = RUNTIME_DIR / "api_fastapi/services/observability_status.py"
    workload_path = RUNTIME_DIR / "api_fastapi/services/workload_admission.py"
    assert not service_path.exists()
    assert "system.observability_probe" not in workload_path.read_text(encoding="utf-8")
