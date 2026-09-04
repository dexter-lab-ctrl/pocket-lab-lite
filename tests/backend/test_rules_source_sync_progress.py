from __future__ import annotations

from fastapi import Response

from pocket_lab_test_utils import ensure_runtime_path


def test_source_sync_status_projects_only_bounded_progress(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.routers import lite_enterprise_rules

    monkeypatch.setattr(
        lite_enterprise_rules.lite_policy_source_sync,
        "source_state",
        lambda: {
            "durable": True,
            "active_revision": "plr-active",
            "known_good_revision": "plr-known-good",
            "repository_revision": "plr-candidate",
            "source_update_required": True,
            "activation_in_progress": True,
            "activation_operation": {
                "operation_id": "plo-progress",
                "candidate_revision_id": "plr-candidate",
                "state": "verifying",
                "created_at": "2026-09-04T17:30:00Z",
                "updated_at": "2026-09-04T17:30:03Z",
                "reason_code": "must-not-leak",
                "observed_filesystem_revision": "must-not-leak",
                "evidence_ref": "must-not-leak",
            },
            "candidate": {
                "manifest": [{"path": "private.rego", "sha256": "must-not-leak"}],
                "parameters": {"secret_like_value": "must-not-leak"},
            },
        },
    )

    payload = lite_enterprise_rules._source_sync_status()

    assert payload == {
        "source": {
            "durable": True,
            "active_revision": "plr-active",
            "known_good_revision": "plr-known-good",
            "repository_revision": "plr-candidate",
            "source_update_required": True,
            "activation_in_progress": True,
            "activation_operation": {
                "operation_id": "plo-progress",
                "candidate_revision_id": "plr-candidate",
                "state": "verifying",
                "created_at": "2026-09-04T17:30:00Z",
                "updated_at": "2026-09-04T17:30:03Z",
            },
        },
        "sanitized": True,
        "policy_source_exposed": False,
        "runtime_command_exposed": False,
    }
    serialized = repr(payload)
    assert "must-not-leak" not in serialized
    assert "manifest" not in serialized
    assert "parameters" not in serialized


def test_source_sync_status_requires_authenticated_read(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.routers import lite_enterprise_rules

    calls = []

    def require_auth(request, *, write):
        calls.append((request, write))
        return {"actor": {"type": "human", "identity_id": "owner"}}

    monkeypatch.setattr(lite_enterprise_rules.deps, "require_auth", require_auth)
    monkeypatch.setattr(
        lite_enterprise_rules,
        "_source_sync_status",
        lambda: {
            "source": {"activation_in_progress": False, "activation_operation": None},
            "sanitized": True,
            "policy_source_exposed": False,
            "runtime_command_exposed": False,
        },
    )

    request = object()
    response = Response()
    payload = lite_enterprise_rules.source_sync_status(request=request, response=response)

    assert calls == [(request, False)]
    assert payload["sanitized"] is True
    assert response.headers["Cache-Control"] == "no-store"
