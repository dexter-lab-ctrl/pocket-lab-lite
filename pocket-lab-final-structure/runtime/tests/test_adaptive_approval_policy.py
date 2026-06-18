# ruff: noqa: E402
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path(__file__).resolve().parents[1]
CORE_DIR = RUNTIME_DIR / "core"
for item in (str(RUNTIME_DIR), str(CORE_DIR)):
    if item not in sys.path:
        sys.path.insert(0, item)

from api_fastapi.services.approval_policy import resolve_runbook_approval_decision


@dataclass
class Step:
    requires_approval: bool = False


@dataclass
class Runbook:
    name: str = "demo"
    requires_approval: bool = True
    steps: list[Any] = field(default_factory=lambda: [Step(requires_approval=True)])


def test_personal_mode_auto_approves_governed_runbooks() -> None:
    decision = resolve_runbook_approval_decision(
        runbook=Runbook(),
        command={"runbook": "demo", "dry_run": True},
        governance_settings={
            "governanceMode": "personal",
            "approvalPolicy": {
                "personal": {
                    "autoApproveRunbooks": True,
                    "approvedBy": "local-policy",
                    "approvalRole": "local-owner",
                    "reason": "test auto approval",
                }
            },
        },
    )
    assert decision["decision"] == "auto_approved"
    assert decision["approved"] is True
    assert decision["approval_mode"] == "automatic"
    assert decision["approved_by"] == "local-policy"


def test_enterprise_mode_requires_human_approval() -> None:
    decision = resolve_runbook_approval_decision(
        runbook=Runbook(),
        command={"runbook": "demo"},
        governance_settings={"governanceMode": "enterprise", "approvalPolicy": {"enterprise": {}}},
    )
    assert decision["decision"] == "human_required"
    assert decision["approved"] is False
    assert decision["approval_mode"] == "enterprise"


def test_explicit_approval_still_wins() -> None:
    decision = resolve_runbook_approval_decision(
        runbook=Runbook(),
        command={"runbook": "demo", "approved": True, "approved_by": "alice", "approval_role": "release_manager"},
        governance_settings={"governanceMode": "enterprise", "approvalPolicy": {"enterprise": {}}},
    )
    assert decision["decision"] == "explicit_approval"
    assert decision["approved"] is True
    assert decision["approved_by"] == "alice"
    assert decision["approval_role"] == "release_manager"
