from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir, load_fastapi_app


@pytest.fixture()
def qualification_runtime(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_IDENTITY_COOKIE_SECURE", "0")
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "")
    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "0")
    monkeypatch.delenv("POCKETLAB_ENVIRONMENT", raising=False)
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()
    return state


def _headers(*, qualification: bool = True, test: bool = True, role: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if test:
        headers["X-Pocket-Lab-Test"] = "1"
    if qualification:
        headers["X-Pocket-Lab-Qualification"] = "1"
    if role is not None:
        headers["X-Role"] = role
    return headers


def _qualification_client(*, headers: dict[str, str] | None = None, local: bool = True) -> TestClient:
    from api_fastapi import deps

    return TestClient(
        load_fastapi_app(),
        headers=headers or _headers(),
        client=("127.0.0.1", 40000) if local else ("testclient", 50000),
    )


def _enable_qualification(monkeypatch) -> None:
    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "1")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "1")
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")


def _fake_policy_transport(monkeypatch, captured: list[dict]):
    from api_fastapi.services import lite_policy_opa

    def fake_http(method, path, payload=None, **kwargs):
        if method == "POST":
            captured.append(payload or {})
            return 200, {
                "result": {
                    "allow": True,
                    "constraints": ["qualification-test"],
                    "reason_code": "owner_authority_restore" if (payload or {}).get("input", {}).get("action", {}).get("id") == "restore.apply" else "authenticated_recovery_operation",
                    "policy_revision": "qualification-policy-rev",
                }
            }
        return 200, {"result": "qualification-policy-rev"}

    monkeypatch.setattr(lite_policy_opa, "_http_json", fake_http)


def test_qualification_owner_is_disabled_by_default_and_in_production(qualification_runtime, monkeypatch):
    client = _qualification_client()

    default_response = client.post("/api/lite/recovery/backup", json={"dry_run": True})
    assert default_response.status_code == 401
    assert default_response.json()["reason_code"] == "qualification_authentication_required"

    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "1")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "1")
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "production")
    production_response = client.post("/api/lite/recovery/backup", json={"dry_run": True})
    assert production_response.status_code == 401
    assert production_response.json()["reason_code"] == "qualification_authentication_required"


def test_qualification_owner_requires_complete_direct_local_proof(qualification_runtime, monkeypatch):
    _enable_qualification(monkeypatch)

    missing_header = _qualification_client(headers=_headers(qualification=False))
    assert missing_header.post("/api/lite/recovery/backup", json={"dry_run": True}).status_code == 401

    browser_client = _qualification_client(local=False)
    assert browser_client.post("/api/lite/recovery/backup", json={"dry_run": True}).status_code == 401

    forwarded = _qualification_client(headers={**_headers(), "X-Forwarded-For": "127.0.0.1"})
    assert forwarded.post("/api/lite/recovery/backup", json={"dry_run": True}).status_code == 401

    caller_role = _qualification_client(headers=_headers(role="Admin"))
    assert caller_role.post("/api/lite/recovery/backup", json={"dry_run": True}).status_code == 401

    no_test_marker = _qualification_client(headers=_headers(test=False))
    assert no_test_marker.post("/api/lite/recovery/backup", json={"dry_run": True}).status_code == 401


def test_qualification_owner_is_ephemeral_and_projects_owner_authority(qualification_runtime, monkeypatch):
    _enable_qualification(monkeypatch)
    response = _qualification_client().get("/api/lite/enterprise/access")
    assert response.status_code == 200
    payload = response.json()
    assert payload["current_role"] == "Owner"
    assert payload["owner_authority"] is True
    assert payload["principal"] == {
        "type": "qualification",
        "synthetic": True,
        "auth_method": "qualification_owner",
    }

    from api_fastapi.db.connection import connection

    with connection() as conn:
        human = conn.execute(
            "SELECT COUNT(*) AS count FROM human_identities WHERE human_id=?",
            ("qualification-owner",),
        ).fetchone()
        membership = conn.execute(
            "SELECT COUNT(*) AS count FROM enterprise_memberships WHERE human_id=?",
            ("qualification-owner",),
        ).fetchone()
    assert human["count"] == 0
    assert membership["count"] == 0

    from api_fastapi import deps

    context = deps.qualification_owner_context()
    assert context["actor"] == {
        "identity_id": "qualification-owner",
        "type": "qualification",
        "display_name": "Qualification Owner",
    }
    assert context["session"]["assurance"][0]["purpose"] == "policy.rules.activate"
    assert context["session"]["assurance"][0]["credential_id"] == "qualification-owner-step-up"
    assert "human_id" not in json.dumps(context)
    assert deps.is_qualification_owner_context(context) is True
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "0")
    assert deps.is_qualification_owner_context(context) is False


def test_qualification_source_sync_records_principal_without_human_identity(qualification_runtime, monkeypatch):
    _enable_qualification(monkeypatch)

    from api_fastapi import deps
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_source_sync

    stale_revision = "plr-qualification-stale-revision"
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO policy_revisions(
                       revision_id,parent_revision_id,template_id,template_version,
                       canonical_parameters_json,manifest_json,content_hash,created_by_human_id,
                       created_by_principal_type,created_by_principal_id,created_at,validation_status,
                       validated_at,validation_reason_code,lifecycle_status,activated_at,change_summary
                   ) VALUES (?,?,?, ?,?,?,?,?,?,?,?,?,?,?,'active',?,?)""",
                (
                    stale_revision,
                    None,
                    "baseline",
                    "1",
                    "{}",
                    '{"files":[],"candidate_hash":"stale"}',
                    "0" * 64,
                    None,
                    "qualification",
                    "qualification-owner",
                    "2026-09-01T00:00:00Z",
                    "valid",
                    "2026-09-01T00:00:00Z",
                    "",
                    "2026-09-01T00:00:00Z",
                    "Qualification source-sync fixture",
                ),
            )
            tx.execute(
                """INSERT INTO policy_runtime_state(
                       state_id,active_revision_id,known_good_revision_id,updated_at,updated_by_operation_id
                   ) VALUES (1,?,?,?,NULL)""",
                (stale_revision, stale_revision, "2026-09-01T00:00:00Z"),
            )

    result = lite_policy_source_sync.request_source_sync(
        auth_context=deps.qualification_owner_context(),
        correlation_id="qualification-source-sync",
    )
    assert result["status"] == "queued"

    with connection() as conn:
        operation = conn.execute(
            """SELECT requested_by_human_id,requested_by_principal_type,requested_by_principal_id
               FROM policy_activation_operations WHERE operation_id=?""",
            (result["operation"]["operation_id"],),
        ).fetchone()
        candidate = conn.execute(
            """SELECT created_by_human_id,created_by_principal_type,created_by_principal_id
               FROM policy_revisions WHERE revision_id=?""",
            (result["operation"]["candidate_revision_id"],),
        ).fetchone()
        identity_count = conn.execute(
            "SELECT COUNT(*) AS count FROM human_identities WHERE human_id=?",
            ("qualification-owner",),
        ).fetchone()["count"]
    assert operation["requested_by_human_id"] is None
    assert operation["requested_by_principal_type"] == "qualification"
    assert operation["requested_by_principal_id"] == "qualification-owner"
    assert candidate["created_by_human_id"] is None
    assert candidate["created_by_principal_type"] == "qualification"
    assert candidate["created_by_principal_id"] == "qualification-owner"
    assert identity_count == 0


def test_recovery_writes_use_opa_and_preserve_hard_restore_guards(qualification_runtime, monkeypatch):
    _enable_qualification(monkeypatch)
    captured: list[dict] = []
    _fake_policy_transport(monkeypatch, captured)

    from api_fastapi.routers import lite

    async def accepted(*args, **kwargs):
        return {"accepted": True, "status": "queued", "command_id": kwargs.get("command", {}).get("command_id")}

    monkeypatch.setattr(lite, "submit_domain_command", accepted)
    backup = _qualification_client().post(
        "/api/lite/recovery/backup",
        json={
            "include_event_journal": True,
            "include_app_data": True,
            "dry_run": False,
            "reason": "qualification-owner-test",
        },
    )
    assert backup.status_code == 202
    assert backup.json()["authorization"]["reason_code"] == "authenticated_recovery_operation"
    assert captured[-1]["input"]["actor"]["type"] == "qualification"
    assert captured[-1]["input"]["actor"]["role"] == "Owner"
    assert captured[-1]["input"]["session"]["auth_method"] == "qualification_owner"

    from api_fastapi.services import lite_backup

    monkeypatch.setattr(
        lite_backup,
        "get_restore_preview",
        lambda preview_id: {
            "preview_id": preview_id,
            "backup_id": "selected-backup",
            "status": "ready",
            "restore_allowed": True,
            "verification_status": "verified",
        },
    )
    monkeypatch.setattr(lite_backup, "validate_restore_preview_binding", lambda preview: {"backup_id": "selected-backup"})
    restore = _qualification_client().post(
        "/api/lite/recovery/restore",
        json={"backup_id": "selected-backup", "preview_id": "selected-preview", "confirm": True},
    )
    assert restore.status_code == 202
    assert restore.json()["authorization"]["reason_code"] == "owner_authority_restore"
    assert captured[-1]["input"]["action"]["id"] == "restore.apply"
    assert captured[-1]["input"]["actor"]["identity_class"] == "qualification_principal"

    captured.clear()
    missing_confirmation = _qualification_client().post(
        "/api/lite/recovery/restore",
        json={"backup_id": "selected-backup", "preview_id": "selected-preview", "confirm": False},
    )
    assert missing_confirmation.status_code == 409
    assert captured == []


def test_qualification_audit_classification_is_sanitized(qualification_runtime, monkeypatch):
    from api_fastapi import deps
    from api_fastapi.services import domain_commands

    _enable_qualification(monkeypatch)
    safe = {
        "requested_by_actor": {
            "actor_type": "qualification",
            "actor_label": "Qualification Owner",
            "auth_method": "qualification_owner",
            "synthetic": True,
            "token": "must-not-cross-boundary",
        }
    }
    audit = domain_commands._audit_actor(safe)
    serialized = json.dumps(audit)
    assert audit == {
        "actor_type": "qualification",
        "actor_label": "Qualification Owner",
        "auth_method": "qualification_owner",
        "synthetic": True,
    }
    assert "token" not in serialized
    assert deps.QUALIFICATION_OWNER_ID not in serialized


@pytest.mark.parametrize("route", [
    "/health", "/ready", "/healthz", "/api/lite/security/events",
    "/api/*", "/openapi.json", "/docs*", "/redoc*", "/ws/*",
])
def test_caddy_strips_qualification_proof_headers(route):
    source = Path(
        "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh"
    ).read_text(encoding="utf-8")
    handler = source.split(f"  handle {route} {{", 1)[1].split("\n  }", 1)[0]
    assert "header_up -X-Pocket-Lab-Test" in handler
    assert "header_up -X-Pocket-Lab-Qualification" in handler
    if route == "/api/lite/security/events":
        assert "flush_interval -1" in handler
