from __future__ import annotations

import sys
from pathlib import Path

RUNTIME_DIR = (
    Path(__file__).resolve().parents[2]
    / "pocket-lab-final-structure"
    / "runtime"
)
if str(RUNTIME_DIR) not in sys.path:
    sys.path.insert(0, str(RUNTIME_DIR))

from api_fastapi.services import lite_app_lifecycle


def test_operation_action_treats_none_projection_as_unavailable() -> None:
    result = lite_app_lifecycle._operation_action(
        "check_app",
        True,
        {"actions": {"check_app": None}},
    )

    assert result["enabled"] is True
    assert result["status"] == "ready"
    assert result["progress"] is None
    assert result["run_count"] == 0
    assert result["checks"] == []
    assert result["details"] == {}
    assert result["technical_details"] == {}


def test_operation_action_treats_non_mapping_actions_as_empty() -> None:
    result = lite_app_lifecycle._operation_action(
        "repair_app",
        True,
        {"actions": None},
    )

    assert result["enabled"] is True
    assert result["status"] == "ready"
