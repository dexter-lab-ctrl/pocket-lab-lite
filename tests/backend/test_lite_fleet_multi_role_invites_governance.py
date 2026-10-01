from __future__ import annotations

import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, prepare_sqlite_test_database


@pytest.fixture()
def fleet_join_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    database = state / "pocketlab-lite.sqlite3"
    prepare_sqlite_test_database(database, monkeypatch)

    from api_fastapi import deps
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.services import lite_invites

    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()
    return state, lite_invites


def _seed_invite(lite_invites, *, roles: list[str], token: str = "invite-token") -> dict:
    expires_at, expires_epoch = lite_invites._expires_at()
    record = {
        "invite_id": "invite-1",
        "command_id": "command-1",
        "node_id": "phone-two",
        "hostname": "Phone Two",
        "role": "compute" if "compute" in roles else roles[0],
        "role_label": " + ".join(role.title() for role in roles),
        "device_roles": roles,
        "device_role_labels": [role.title() for role in roles],
        "device_role_generation": 1,
        "capabilities": [],
        "token_hash": lite_invites._hash_token(token),
        "token_hint": lite_invites._token_hint(token),
        "expires_at": expires_at,
        "expires_at_epoch": expires_epoch,
        "uses_remaining": 1,
        "status": "pending",
        "created_at": lite_invites._now_iso(),
        "updated_at": lite_invites._now_iso(),
    }
    lite_invites._write_state("fleet_invites.json", {"invites": [record], "updated_at": lite_invites._now_iso()})
    return record


@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        (["compute"], ["compute"]),
        (["storage"], ["storage"]),
        (["storage", "compute"], ["compute", "storage"]),
    ],
)
def test_invite_role_set_is_canonical(fleet_join_runtime, roles, expected):
    _, lite_invites = fleet_join_runtime
    assert lite_invites.normalize_device_roles(roles) == expected


def test_invite_token_is_bound_to_exact_role_set(fleet_join_runtime):
    _, lite_invites = fleet_join_runtime
    _seed_invite(lite_invites, roles=["compute", "storage"])

    status, _ = lite_invites.invite_token_status(
        "invite-token",
        device_roles=["compute", "storage"],
    )
    assert status == "valid"

    tampered_status, _ = lite_invites.invite_token_status(
        "invite-token",
        device_roles=["compute"],
    )
    assert tampered_status == "role_set_mismatch"


def test_server_host_cannot_be_obtained_by_bootstrap_role_tampering(fleet_join_runtime):
    _, lite_invites = fleet_join_runtime
    _seed_invite(lite_invites, roles=["compute"])

    status, _ = lite_invites.invite_token_status(
        "invite-token",
        device_roles=["server_host"],
    )
    assert status == "invalid_role"


def test_invite_role_mismatch_evidence_is_sanitized(fleet_join_runtime):
    state, lite_invites = fleet_join_runtime
    invite = _seed_invite(lite_invites, roles=["compute", "storage"])

    event = lite_invites.append_bootstrap_blocked_evidence(
        invite,
        intended_node_id="phone-two",
        intended_node_name="Phone Two",
        reason_code="invite_role_set_mismatch",
        reason="Tampered request",
    )
    assert event["reason_code"] == "invite_role_set_mismatch"
    assert "token" not in json.dumps(event).lower()
    assert event["device_roles"] == ["compute", "storage"]
    audit = json.loads((state / "fleet_invite_audit.json").read_text(encoding="utf-8"))
    assert audit["events"][0]["reason_code"] == "invite_role_set_mismatch"


def test_duplicate_name_protection_is_independent_of_role_selection(fleet_join_runtime):
    _, lite_invites = fleet_join_runtime
    _seed_invite(lite_invites, roles=["compute"])
    conflict = lite_invites.find_invite_identity_conflict("Phone__Two")
    assert conflict is not None
    assert conflict["device_id"] == "phone-two"


def test_role_change_fingerprint_invalidates_stale_authorization_version(fleet_join_runtime):
    _, _ = fleet_join_runtime
    from api_fastapi.services import lite_device_roles

    old = lite_device_roles.request_fingerprint(
        action_id="device.roles.change",
        device_id="phone-two",
        requested_roles=["compute", "storage"],
        authorization_version=4,
        generation=3,
    )
    new = lite_device_roles.request_fingerprint(
        action_id="device.roles.change",
        device_id="phone-two",
        requested_roles=["compute", "storage"],
        authorization_version=5,
        generation=3,
    )
    assert old != new


def test_approval_purpose_is_action_specific(fleet_join_runtime):
    _, _ = fleet_join_runtime
    from api_fastapi.services import lite_policy_approvals

    assert lite_policy_approvals.APPROVAL_PURPOSES["device.invite"] == "policy.approval.device.invite"
    assert lite_policy_approvals.APPROVAL_PURPOSES["device.roles.change"] == "policy.approval.device.roles.change"
    assert lite_policy_approvals.APPROVAL_PURPOSES["device.remove"] == "policy.approval.device.remove"


def test_step_up_is_bound_to_the_requested_approval_purpose(fleet_join_runtime):
    _, _ = fleet_join_runtime
    from api_fastapi.services import lite_policy_approvals

    context = {
        "session": {
            "assurance": [
                {
                    "purpose": "policy.approval.device.remove",
                    "expires_at": "2999-01-01T00:00:00Z",
                }
            ]
        }
    }
    assert lite_policy_approvals._approved_assurance(context, "policy.approval.device.remove") is True
    assert lite_policy_approvals._approved_assurance(context, "policy.approval.device.roles.change") is False


@pytest.mark.parametrize(
    ("human_role", "action", "expected"),
    [
        ("Owner", "device.invite.compute", "allow"),
        ("Owner", "device.invite.storage", "allow"),
        ("Admin", "device.invite.compute", "allow"),
        ("Admin", "device.invite.storage", "approval"),
        ("Operator", "device.invite.compute", "allow"),
        ("Operator", "device.invite.storage", "approval"),
        ("Auditor", "device.invite.compute", "deny"),
        ("Viewer", "device.invite.compute", "deny"),
    ],
)
def test_fleet_authority_matrix_defaults(fleet_join_runtime, human_role, action, expected):
    _, _ = fleet_join_runtime
    from api_fastapi.services import lite_enterprise_governance as governance

    assert governance._mode_for(action, human_role, governance.POLICY_DEFAULTS) == expected
