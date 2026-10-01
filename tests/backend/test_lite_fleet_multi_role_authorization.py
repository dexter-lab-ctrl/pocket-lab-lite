from __future__ import annotations

import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, prepare_sqlite_test_database


@pytest.fixture()
def role_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    target = tmp_path / "state" / "pocketlab-lite.sqlite3"
    prepare_sqlite_test_database(target, monkeypatch)
    from api_fastapi.db.migrations import apply_migrations

    apply_migrations()
    from api_fastapi.services import lite_device_roles

    return target, lite_device_roles


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("compute", ["compute"]),
        ("storage", ["storage"]),
        (["compute"], ["compute"]),
        (["storage"], ["storage"]),
        (["storage", "compute"], ["compute", "storage"]),
        (["compute", "compute", "storage"], ["compute", "storage"]),
    ],
)
def test_canonical_device_role_normalization(role_runtime, value, expected):
    _, roles = role_runtime
    assert roles.normalize_device_roles(value, joinable_only=True) == expected


@pytest.mark.parametrize("value", [[], "", ["server_host"], ["unknown"], ["compute", "unknown"]])
def test_invalid_or_protected_role_sets_fail_closed(role_runtime, value):
    _, roles = role_runtime
    with pytest.raises(roles.DeviceRoleError):
        roles.normalize_device_roles(value, joinable_only=True)


def test_legacy_single_role_compatibility_projects_to_canonical_set(role_runtime):
    _, roles = role_runtime
    assert roles.assignment_state("legacy-compute", legacy_role="compute")["device_roles"] == ["compute"]
    assert roles.assignment_state("legacy-storage", legacy_role="storage")["device_roles"] == ["storage"]


def test_role_assignments_are_durable_and_generation_fenced(role_runtime):
    _, roles = role_runtime
    first = roles.record_desired_roles(
        "phone-two",
        ["compute"],
        status="accepted",
        actor_human_id="owner-1",
        actor_role="Owner",
        authorization_version=3,
        policy_revision="rules-v3",
        correlation_id="role-change-1",
    )
    second = roles.record_desired_roles(
        "phone-two",
        ["compute", "storage"],
        status="accepted",
        actor_human_id="owner-1",
        actor_role="Owner",
        authorization_version=3,
        policy_revision="rules-v3",
        correlation_id="role-change-2",
        expected_generation=first["generation"],
    )
    assert second["generation"] == first["generation"] + 1
    assert roles.assignment_state("phone-two")["desired_device_roles"] == ["compute", "storage"]

    with pytest.raises(roles.DeviceRoleError) as stale:
        roles.record_desired_roles(
            "phone-two",
            ["storage"],
            status="accepted",
            actor_human_id="owner-1",
            actor_role="Owner",
            authorization_version=3,
            policy_revision="rules-v3",
            correlation_id="stale-change",
            expected_generation=first["generation"],
        )
    assert stale.value.status_code == 409


def test_runtime_attestation_cannot_self_escalate_storage(role_runtime):
    _, roles = role_runtime
    assignment = roles.record_desired_roles(
        "compute-only",
        ["compute"],
        status="accepted",
        actor_human_id="owner-1",
        actor_role="Owner",
        correlation_id="compute-only",
    )
    state = roles.record_runtime_attestation(
        "compute-only",
        reported_roles=["compute", "storage"],
        advertised_capabilities=["compute", "host_apps", "media_storage", "backup_target"],
        online=True,
        identity_verified=True,
        generation=assignment["generation"],
    )
    assert state["active_device_roles"] != ["compute", "storage"]
    projected = roles.enrich_device_projection(
        {
            "id": "compute-only",
            "role": "compute",
            "connection": "online",
            "advertised_capabilities": ["compute", "host_apps", "media_storage", "backup_target"],
        }
    )
    storage = {item["id"]: item for item in projected["capability_states"]}["media_storage"]
    assert storage["authorization"] == "blocked"
    assert storage["effective"] is False


def test_runtime_attestation_cannot_self_escalate_compute(role_runtime):
    _, roles = role_runtime
    assignment = roles.record_desired_roles(
        "storage-only",
        ["storage"],
        status="accepted",
        actor_human_id="owner-1",
        actor_role="Owner",
        correlation_id="storage-only",
    )
    roles.record_runtime_attestation(
        "storage-only",
        reported_roles=["storage", "compute"],
        advertised_capabilities=["compute", "host_apps", "media_storage", "backup_target"],
        online=True,
        identity_verified=True,
        generation=assignment["generation"],
    )
    projected = roles.enrich_device_projection(
        {
            "id": "storage-only",
            "role": "storage",
            "connection": "online",
            "advertised_capabilities": ["compute", "host_apps", "media_storage", "backup_target"],
        }
    )
    compute = {item["id"]: item for item in projected["capability_states"]}["compute"]
    assert compute["authorization"] == "blocked"
    assert compute["effective"] is False


def test_multi_role_requires_fresh_verified_runtime_evidence(role_runtime):
    _, roles = role_runtime
    assignment = roles.record_desired_roles(
        "dual-role",
        ["compute", "storage"],
        status="accepted",
        actor_human_id="owner-1",
        actor_role="Owner",
        correlation_id="dual-role",
    )
    active = roles.record_runtime_attestation(
        "dual-role",
        reported_roles=["compute", "storage"],
        advertised_capabilities=["compute", "host_apps", "media_storage", "backup_target"],
        online=True,
        identity_verified=True,
        generation=assignment["generation"],
    )
    assert active["active_device_roles"] == ["compute", "storage"]

    stale = roles.record_runtime_attestation(
        "dual-role",
        reported_roles=["compute", "storage"],
        advertised_capabilities=["compute", "host_apps", "media_storage", "backup_target"],
        online=False,
        identity_verified=True,
        generation=assignment["generation"],
    )
    assert stale["status"] == "verifying"
    projection = roles.enrich_device_projection(
        {
            "id": "dual-role",
            "role": "compute",
            "connection": "offline",
            "advertised_capabilities": ["compute", "host_apps", "media_storage", "backup_target"],
        }
    )
    assert any(item["status"] == "stale" for item in projection["capability_states"])


def test_photo_backup_source_remains_independent_from_storage_role(role_runtime):
    _, roles = role_runtime
    roles.record_desired_roles(
        "photo-source",
        ["compute"],
        status="accepted",
        actor_human_id="owner-1",
        actor_role="Owner",
        correlation_id="photo-source",
    )
    projection = roles.enrich_device_projection(
        {
            "id": "photo-source",
            "role": "compute",
            "connection": "online",
            "advertised_capabilities": ["compute", "host_apps", "media_backup_source", "photo_storage_access"],
        }
    )
    by_id = {item["id"]: item for item in projection["capability_states"]}
    assert by_id["media_backup_source"]["authorization"] == "independent_runtime_policy"
    assert by_id["media_backup_source"]["effective"] is True
    assert "storage" not in projection["device_role_ids"]


def test_storage_role_removal_is_dependency_aware(role_runtime):
    _, roles = role_runtime
    blocked = roles.role_change_dependency_assessment(
        {
            "dependencies": {"backup_set_count": 2},
            "removal_assessment": {
                "blockers": [
                    {"summary": "Two verified backup sets still use this device."},
                ]
            },
        },
        ["compute", "storage"],
        ["compute"],
    )
    assert blocked["safe"] is False
    assert blocked["storage_role_removed"] is True
    assert blocked["blockers"][0]["reason_code"] == "device_role_change_blocked_by_dependency"

    allowed = roles.role_change_dependency_assessment(
        {"dependencies": {"backup_set_count": 0}, "removal_assessment": {"blockers": []}},
        ["compute", "storage"],
        ["compute"],
    )
    assert allowed["safe"] is True


def test_role_change_redelivery_is_idempotent_at_agent_semantic_boundary(tmp_path, monkeypatch):
    ensure_runtime_path()
    from agents.pocketlab_node_agent import LiteNodeAgent

    env_file = tmp_path / "agent.env"
    env_file.write_text(
        "export POCKETLAB_NODE_ID=phone-two\n"
        "export POCKETLAB_NODE_NAME=Phone Two\n"
        "export POCKETLAB_NODE_ROLES=compute\n"
        "export POCKETLAB_NODE_ROLE=compute\n"
        "export POCKETLAB_NODE_ROLE_GENERATION=4\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("POCKETLAB_NODE_ID", "phone-two")
    monkeypatch.setenv("POCKETLAB_NODE_NAME", "Phone Two")
    monkeypatch.setenv("POCKETLAB_NODE_ROLES", "compute")
    monkeypatch.setenv("POCKETLAB_NODE_ROLE_GENERATION", "4")
    monkeypatch.setenv("POCKETLAB_AGENT_ENV_FILE", str(env_file))

    agent = LiteNodeAgent()
    first = agent._apply_device_roles({"node_id": "phone-two", "device_roles": ["compute", "storage"], "generation": 5})
    before = env_file.read_text(encoding="utf-8")
    second = agent._apply_device_roles({"node_id": "phone-two", "device_roles": ["compute", "storage"], "generation": 5})
    after = env_file.read_text(encoding="utf-8")

    assert first["accepted"] is True
    assert second["accepted"] is True
    assert second["unchanged"] is True
    assert before == after


def test_role_change_identity_mismatch_fails_closed(role_runtime):
    _, roles = role_runtime
    assignment = roles.record_desired_roles(
        "phone-two",
        ["compute", "storage"],
        status="accepted",
        actor_human_id="owner-1",
        actor_role="Owner",
        correlation_id="identity-mismatch",
    )
    state = roles.record_runtime_attestation(
        "phone-two",
        reported_roles=["compute", "storage"],
        advertised_capabilities=["compute", "media_storage"],
        online=True,
        identity_verified=False,
        generation=assignment["generation"],
    )
    assert state["status"] == "blocked"
    assert state["reason_code"] == "device_role_change_identity_mismatch"
    assert state["active_device_roles"] == []


def test_device_removal_retires_role_authority_without_deleting_history(role_runtime):
    _, roles = role_runtime
    roles.record_desired_roles(
        "retired-phone",
        ["compute", "storage"],
        status="accepted",
        actor_human_id="owner-1",
        actor_role="Owner",
        correlation_id="retire-role-state",
    )
    retired = roles.retire_device_roles("retired-phone")
    assert retired["status"] == "retired"
    state = roles.assignment_state("retired-phone")
    assert state["desired_device_roles"] == []
    assert state["active_device_roles"] == []


def test_governance_matrix_separates_human_roles_from_device_roles(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_enterprise_governance as governance

    params = governance.POLICY_DEFAULTS
    assert governance._mode_for("device.invite.compute", "Owner", params) == "allow"
    assert governance._mode_for("device.invite.storage", "Owner", params) == "allow"
    assert governance._mode_for("device.invite.compute", "Admin", params) == "allow"
    assert governance._mode_for("device.invite.storage", "Admin", params) == "approval"
    assert governance._mode_for("device.invite.compute", "Operator", params) == "allow"
    assert governance._mode_for("device.invite.storage", "Operator", params) == "approval"
    assert governance._mode_for("device.invite.compute", "Auditor", params) == "deny"
    assert governance._mode_for("device.invite.storage", "Viewer", params) == "deny"


def test_request_fingerprint_binds_role_set_and_authorization_version(role_runtime):
    _, roles = role_runtime
    compute = roles.request_fingerprint(
        action_id="device.roles.change",
        device_id="phone-two",
        requested_roles=["compute"],
        authorization_version=3,
        generation=7,
    )
    dual = roles.request_fingerprint(
        action_id="device.roles.change",
        device_id="phone-two",
        requested_roles=["compute", "storage"],
        authorization_version=3,
        generation=7,
    )
    stale_auth = roles.request_fingerprint(
        action_id="device.roles.change",
        device_id="phone-two",
        requested_roles=["compute"],
        authorization_version=2,
        generation=7,
    )
    assert compute != dual
    assert compute != stale_auth
