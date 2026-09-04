from __future__ import annotations

import json

from pocket_lab_test_utils import ensure_runtime_path


def _stale_joined_device(**overrides):
    device = {
        "id": "pocket-node",
        "name": "Pocket Node",
        "role": "compute",
        "status": "offline",
        "connection": "offline",
        "last_heartbeat_at": "2026-07-02T08:00:00Z",
        "last_seen_at": "2026-07-02T08:00:00Z",
        "identity_status": "verified",
        "advertised_capabilities": ["receive_commands"],
    }
    device.update(overrides)
    return device


def _empty_context(**overrides):
    context = {
        "invites": [],
        "events": [],
        "hosted_apps": {},
        "backup_dependencies": {},
    }
    context.update(overrides)
    return context


def test_historical_blocked_join_does_not_block_joined_stale_device_removal():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    context = _empty_context(
        invites=[{
            "invite_id": "invite-old",
            "hostname": "Pocket Node",
            "node_id": "pocket-node",
            "status": "pending",
            "created_at": "2026-07-01T08:00:00Z",
            "updated_at": "2026-07-01T08:01:00Z",
            "expires_at_epoch": 4_102_444_800,
        }],
        events=[{
            "event_type": "pocketlab.events.fleet.bootstrap_blocked",
            "node_id": "pocket-node",
            "invite_id": "invite-old",
            "occurred_at": "2026-07-01T08:02:00Z",
            "reason_code": "invite_identity_mismatch",
            "summary": "A mismatched join attempt was blocked.",
            "token": "must-never-leak",
        }],
    )
    device = enrich_device(
        _stale_joined_device(
            identity_status="needs_review",
            repair_required=True,
            repair_reason_code="invite_identity_mismatch",
        ),
        context=context,
        commands=[],
    )

    assert device["identity_status"] == "verified"
    assert device["enrollment_status"] == "ready"
    assert device["identity"]["repair_required"] is False
    assessment = device["removal_assessment"]
    assert assessment["safe_to_remove"] is True
    assert assessment["allowed"] is True
    blocker_codes = {item["code"] for item in assessment["blockers"]}
    warning_codes = {item["code"] for item in assessment["warnings"]}
    assert "active_join_flow" not in blocker_codes
    assert "historical_join_blocked" in warning_codes
    assert "matching_invite_cleanup" in warning_codes
    serialized = json.dumps(device).lower()
    assert "must-never-leak" not in serialized
    assert "invite_identity_mismatch" in serialized


def test_accepted_invite_fallback_without_real_heartbeat_stays_fail_closed():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    device = enrich_device({
        "id": "waiting-phone",
        "name": "Waiting Phone",
        "role": "compute",
        "status": "waiting",
        "connection": "waiting",
        "source": "accepted-invite",
        # Accepted-invite compatibility rows synthesize this from accepted_at;
        # it must never be accepted as proof of a completed enrollment.
        "last_seen_at": "2026-08-01T08:00:00Z",
    }, context=_empty_context(invites=[{
        "invite_id": "invite-waiting",
        "node_id": "waiting-phone",
        "hostname": "Waiting Phone",
        "status": "accepted",
        "accepted_at": "2026-08-01T08:00:00Z",
        "created_at": "2026-08-01T07:55:00Z",
    }]), commands=[])

    assert device["identity_status"] == "pending"
    assert device["enrollment_status"] == "waiting_for_heartbeat"
    assert device["removal_assessment"]["safe_to_remove"] is False
    assert {item["code"] for item in device["removal_assessment"]["blockers"]} == {"active_join_flow"}


def test_pending_invite_without_joined_evidence_stays_fail_closed():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    device = enrich_device({
        "id": "new-phone",
        "name": "New Phone",
        "role": "compute",
        "status": "waiting",
        "connection": "waiting",
    }, context=_empty_context(invites=[{
        "invite_id": "invite-new",
        "node_id": "new-phone",
        "hostname": "New Phone",
        "status": "pending",
        "created_at": "2026-09-01T07:55:00Z",
        "expires_at_epoch": 4_102_444_800,
    }]), commands=[])

    assert device["enrollment_status"] == "invite_pending"
    assert device["removal_assessment"]["safe_to_remove"] is False
    assert "active_join_flow" in {item["code"] for item in device["removal_assessment"]["blockers"]}


def test_terminal_historical_invites_never_reopen_join_blocker_for_joined_device():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    for invite_status in ("revoked", "expired", "removed", "failed", "used", "joined"):
        device = enrich_device(
            _stale_joined_device(),
            context=_empty_context(invites=[{
                "invite_id": f"invite-{invite_status}",
                "node_id": "pocket-node",
                "hostname": "Pocket Node",
                "status": invite_status,
                "created_at": "2024-12-01T00:00:00Z",
                "updated_at": "2025-01-02T00:00:00Z",
            }]),
            commands=[],
        )
        assert device["enrollment_status"] == "ready"
        assert device["removal_assessment"]["safe_to_remove"] is True
        warning_codes = {item["code"] for item in device["removal_assessment"]["warnings"]}
        assert "matching_invite_cleanup" not in warning_codes


def test_expired_pending_invite_is_not_a_live_join_dependency():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    device = enrich_device(
        _stale_joined_device(),
        context=_empty_context(invites=[{
            "invite_id": "invite-expired-by-time",
            "node_id": "pocket-node",
            "hostname": "Pocket Node",
            "status": "pending",
            "created_at": "2024-12-01T00:00:00Z",
            "expires_at_epoch": 1,
        }]),
        commands=[],
    )
    assert device["removal_assessment"]["safe_to_remove"] is True
    assert "matching_invite_cleanup" not in {item["code"] for item in device["removal_assessment"]["warnings"]}


def test_non_identity_repair_still_blocks_joined_device_removal():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    device = enrich_device(
        _stale_joined_device(
            repair_required=True,
            repair_reason_code="enrollment_state_inconsistent",
        ),
        context=_empty_context(),
        commands=[],
    )

    assert device["enrollment_status"] == "repair_required"
    assert device["removal_assessment"]["safe_to_remove"] is False
    assert "device_repair_required" in {item["code"] for item in device["removal_assessment"]["blockers"]}


def test_existing_dependency_and_recovery_blockers_remain_authoritative():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    context = _empty_context(
        hosted_apps={"pocket-node": [{"app_id": "photos", "label": "Photos", "status": "running"}]},
        backup_dependencies={"pocket-node": {
            "backup_set_count": 1,
            "backup_repository_count": 1,
            "stores_only_verified_copy": True,
        }},
    )
    device = enrich_device(
        _stale_joined_device(status="repairing", supervisor_status="repairing"),
        context=context,
        commands=[{"node_id": "pocket-node", "command_id": "cmd-1", "status": "running"}],
    )

    blocker_codes = {item["code"] for item in device["removal_assessment"]["blockers"]}
    assert {
        "hosts_active_app",
        "only_verified_backup_copy",
        "pending_commands",
        "active_recovery",
    }.issubset(blocker_codes)
    assert device["removal_assessment"]["safe_to_remove"] is False


def test_protected_server_host_remains_non_removable_even_with_historical_invite_state():
    ensure_runtime_path()
    from api_fastapi.services.lite_device_awareness import enrich_device

    device = enrich_device({
        **_stale_joined_device(),
        "id": "server-phone",
        "name": "Pocket Lab Lite Server",
        "role": "server_host",
        "is_current": True,
    }, context=_empty_context(invites=[{
        "invite_id": "old-server-invite",
        "node_id": "server-phone",
        "status": "revoked",
    }]), commands=[])

    assert device["removal_assessment"]["safe_to_remove"] is False
    assert "protected_server_host" in {item["code"] for item in device["removal_assessment"]["blockers"]}
