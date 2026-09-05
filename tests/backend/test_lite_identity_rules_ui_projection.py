from __future__ import annotations

from pathlib import Path

from pocket_lab_test_utils import ensure_runtime_path


ROOT = Path(__file__).resolve().parents[2]


def test_approval_projection_derives_safe_viewer_actions_without_human_ids():
    ensure_runtime_path()
    from api_fastapi.services import lite_policy_approvals as approvals

    row = {
        "approval_id": "apr-ui-polish",
        "originating_decision_id": "decision-ui-polish",
        "correlation_id": "correlation-ui-polish",
        "action_id": "device.remove",
        "target_type": "device",
        "target_id": "node-1",
        "initiating_human_id": "human-requester",
        "initiating_role": "Owner",
        "required_approver_roles_json": '["Admin","Owner"]',
        "required_assurance": approvals.APPROVAL_PURPOSE,
        "policy_revision": "revision-p3",
        "status": "pending",
        "created_at": "2026-08-24T10:00:00Z",
        "expires_at": "2099-08-24T10:15:00Z",
        "reason_code": "approval_required",
        "evidence_ref": "policy:decision-ui-polish",
        "approved_by_human_id": None,
        "rejected_by_human_id": None,
        "cancelled_by_human_id": None,
    }

    requester = approvals._public_approval(
        row,
        viewer_actor_id="human-requester",
        viewer_role="Owner",
        eligible_approver_count=0,
    )
    assert requester["viewer_relationship"] == "requester"
    # Owner-originated peer approvals are legacy policy inconsistencies. They
    # may be cancelled for reconciliation, but must never be approved/rejected.
    assert requester["policy_inconsistency"] is True
    assert requester["viewer_actions"] == {"approve": False, "reject": False, "cancel": True}
    assert requester["eligible_approver_count"] == 0
    assert "initiating_human_id" not in requester
    assert "approved_by_human_id" not in requester

    reviewer = approvals._public_approval(
        row,
        viewer_actor_id="human-admin",
        viewer_role="Admin",
        eligible_approver_count=1,
    )
    assert reviewer["viewer_relationship"] == "reviewer"
    assert reviewer["viewer_actions"] == {"approve": False, "reject": False, "cancel": False}
    assert reviewer["eligible_approver_count"] == 0
    assert "initiating_human_id" not in reviewer


def test_exception_projection_keeps_human_ids_out_of_public_exception_rows():
    ensure_runtime_path()
    from api_fastapi.services import lite_policy_approvals as approvals

    item = approvals._public_exception({
        "exception_id": "exc-ui-polish",
        "action_id": "catalog.install",
        "app_id": "photoprism",
        "device_id": "node-1",
        "human_id": "human-requester",
        "policy_revision": "revision-p3",
        "reason": "Maintenance",
        "created_by_human_id": "human-owner",
        "revoked_by_human_id": None,
        "status": "active",
        "created_at": "2026-08-24T10:00:00Z",
        "expires_at": "2026-08-24T10:15:00Z",
    })
    assert "human_id" not in item
    assert "created_by_human_id" not in item
    assert "revoked_by_human_id" not in item
    assert item["app_id"] == "photoprism"
    assert item["device_id"] == "node-1"


def test_identity_rules_ui_polish_keeps_sensitive_internals_progressively_disclosed():
    identity = (ROOT / "src/lite/LiteIdentity.jsx").read_text(encoding="utf-8")
    identity_enterprise = (ROOT / "src/lite/LiteIdentityEnterprise.jsx").read_text(encoding="utf-8")
    rules = (ROOT / "src/lite/LiteRules.jsx").read_text(encoding="utf-8")
    rules_enterprise = (ROOT / "src/lite/LiteRulesEnterprise.jsx").read_text(encoding="utf-8")
    css = (ROOT / "src/lite/identityRules.css").read_text(encoding="utf-8")

    assert "window.prompt" not in identity
    assert "window.confirm" not in identity
    assert "const identityReadOnly = savedStateOnly || !backendReachable;" in identity
    assert "buildLiteIdentityAccessOverview" in identity
    assert "LiteSheet" in identity
    assert "Enterprise people" in identity_enterprise
    assert "final-Owner protection" in identity_enterprise

    assert "Review the local policy engine" not in rules
    assert "free-form browser Rego" not in rules
    assert "Advanced diagnostics" in rules
    assert "This does not execute the action" in rules_enterprise
    for field in ("confirmed", "revision_validated", "protected_server_host", "assurance_recent"):
        assert field in rules_enterprise
    assert "viewer_actions?.approve" in rules_enterprise
    assert "Requesting identity ID" not in rules_enterprise
    assert "Select a person" in rules_enterprise
    assert "Not all conflicts are analyzable by this model" in rules_enterprise

    assert "min-height: 44px" in css
    assert "prefers-reduced-motion: reduce" in css
    assert ":focus-visible" in css
