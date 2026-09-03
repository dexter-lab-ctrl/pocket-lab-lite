from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir, load_fastapi_app


@pytest.fixture()
def policy_runtime(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS
    from api_fastapi.services import lite_enterprise_identity, lite_identity_auth

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_IDENTITY_SETUP_TOKEN", "one-time-setup-token")
    monkeypatch.setenv("POCKETLAB_IDENTITY_COOKIE_SECURE", "0")
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    applied = apply_migrations()
    assert 29 in applied
    lite_identity_auth.setup_owner(
        username="owner",
        display_name="Owner",
        password="correct horse battery staple",
        setup_token="one-time-setup-token",
    )
    signed_in = lite_identity_auth.login(
        username="owner",
        password="correct horse battery staple",
    )
    auth = lite_identity_auth.authenticate_session_token(signed_in["session_token"])
    lite_enterprise_identity.set_enterprise_enabled(auth_context=auth, enabled=True)
    signed_in = lite_identity_auth.login(
        username="owner",
        password="correct horse battery staple",
    )
    auth = lite_enterprise_identity.enrich_auth_context(
        lite_identity_auth.authenticate_session_token(signed_in["session_token"])
    )
    return state, auth


def _write_valid_stage(state: Path, revision: str) -> Path:
    stage = state / "opa" / "stage" / revision
    stage.mkdir(parents=True)
    policy = stage / "pocketlab.rego"
    policy.write_text("package pocketlab\n", encoding="utf-8")
    (stage / "revision.txt").write_text(revision + "\n", encoding="utf-8")
    files = [
        {
            "path": "pocketlab.rego",
            "sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
        }
    ]
    candidate_hash = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    (stage / "manifest.json").write_text(
        json.dumps(
            {
                "revision": revision,
                "candidate_hash": candidate_hash,
                "files": files,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return stage


def _make_uncertain(auth):
    from api_fastapi.db.connection import begin_immediate, connection
    from api_fastapi.services import lite_policy_lifecycle as rules

    candidate = rules.create_revision(
        auth_context=auth,
        template_id="baseline",
        parameters={},
        change_summary="candidate",
    )["revision"]
    operation = rules.request_activation(
        auth_context=auth,
        revision_id=candidate["revision_id"],
    )["operation"]
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """UPDATE policy_activation_operations
                   SET state='uncertain',reason_code='rollback_pointer_failed'
                   WHERE operation_id=?""",
                (operation["operation_id"],),
            )
    return candidate, operation["operation_id"]


def test_proved_manual_recovery_terminalizes_uncertain_and_preserves_incident(policy_runtime, monkeypatch):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_policy_lifecycle as rules

    state, auth = policy_runtime
    candidate, operation_id = _make_uncertain(auth)
    recovered = "plr-pre-lifecycle-known-good"
    stage = _write_valid_stage(state, recovered)
    (state / "opa" / "active").symlink_to(stage)
    (state / "opa" / "known-good").symlink_to(stage)
    monkeypatch.setattr(
        rules,
        "_fetch_local_json",
        lambda url: {} if url.endswith("/health") else {"result": recovered},
    )

    resolved = rules.resolve_uncertain_operation(
        auth_context=auth,
        operation_id=operation_id,
    )

    operation = resolved["operation"]
    resolution = resolved["resolution"]
    assert operation["state"] == "rolled_back"
    assert operation["reason_code"] == "rollback_pointer_failed"
    assert operation["observed_filesystem_revision"] == recovered
    assert operation["observed_opa_revision"] == recovered
    assert operation["evidence_ref"] == "policy:manual-recovery-proved"
    assert resolution["status"] == "proved"
    assert resolution["original_reason_code"] == "rollback_pointer_failed"
    assert resolution["recovered_revision_id"] == recovered
    assert resolution["evidence_ref"] == "policy:manual-recovery-proved"

    with connection() as conn:
        row = conn.execute(
            "SELECT original_reason_code,recovered_revision_id,status,evidence_ref FROM policy_recovery_resolutions WHERE operation_id=?",
            (operation_id,),
        ).fetchone()
    assert dict(row) == {
        "original_reason_code": "rollback_pointer_failed",
        "recovered_revision_id": recovered,
        "status": "proved",
        "evidence_ref": "policy:manual-recovery-proved",
    }

    # Terminalizing the quarantined incident releases the single-nonterminal
    # admission fence without inventing a lifecycle runtime row for the shipped
    # pre-P2.2 known-good revision.
    next_operation = rules.request_activation(
        auth_context=auth,
        revision_id=candidate["revision_id"],
    )["operation"]
    assert next_operation["state"] == "pending"


def test_manual_recovery_proof_fails_closed_and_keeps_uncertain(policy_runtime, monkeypatch):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_policy_lifecycle as rules

    _, auth = policy_runtime
    _, operation_id = _make_uncertain(auth)
    monkeypatch.setattr(
        rules,
        "_pointer_revision",
        lambda name: "plr-active" if name == "active" else "plr-known-good",
    )

    with pytest.raises(rules.PolicyLifecycleError) as exc:
        rules.resolve_uncertain_operation(
            auth_context=auth,
            operation_id=operation_id,
        )
    assert exc.value.reason_code == "policy_recovery_pointer_mismatch"

    with connection() as conn:
        operation = conn.execute(
            "SELECT state,reason_code,evidence_ref FROM policy_activation_operations WHERE operation_id=?",
            (operation_id,),
        ).fetchone()
        resolution_count = conn.execute(
            "SELECT COUNT(*) FROM policy_recovery_resolutions WHERE operation_id=?",
            (operation_id,),
        ).fetchone()[0]
    assert dict(operation) == {
        "state": "uncertain",
        "reason_code": "rollback_pointer_failed",
        "evidence_ref": None,
    }
    assert resolution_count == 0


def test_manual_recovery_rejects_opa_revision_mismatch(policy_runtime, monkeypatch):
    from api_fastapi.services import lite_policy_lifecycle as rules

    state, auth = policy_runtime
    _, operation_id = _make_uncertain(auth)
    recovered = "plr-pre-lifecycle-known-good"
    stage = _write_valid_stage(state, recovered)
    (state / "opa" / "active").symlink_to(stage)
    (state / "opa" / "known-good").symlink_to(stage)
    monkeypatch.setattr(
        rules,
        "_fetch_local_json",
        lambda url: {} if url.endswith("/health") else {"result": "plr-wrong"},
    )

    with pytest.raises(rules.PolicyLifecycleError) as exc:
        rules.resolve_uncertain_operation(
            auth_context=auth,
            operation_id=operation_id,
        )
    assert exc.value.reason_code == "policy_recovery_unproved"


def test_resolution_endpoint_requires_csrf_and_accepts_no_recovery_payload(policy_runtime, monkeypatch):
    from fastapi.testclient import TestClient
    from api_fastapi.services import lite_enterprise_governance, lite_policy_lifecycle as rules

    _, auth = policy_runtime
    _, operation_id = _make_uncertain(auth)
    monkeypatch.setattr(rules, "_manual_recovery_proof", lambda _operation: "plr-restored")

    client = TestClient(load_fastapi_app())
    signed_in = client.post(
        "/api/lite/identity/login",
        json={
            "username": "owner",
            "password": "correct horse battery staple",
        },
    )
    assert signed_in.status_code == 200
    csrf = signed_in.json()["csrf_token"]

    missing_csrf = client.post(
        f"/api/lite/enterprise/rules/activations/{operation_id}/resolve"
    )
    assert missing_csrf.status_code == 403

    step_up_required = client.post(
        f"/api/lite/enterprise/rules/activations/{operation_id}/resolve",
        headers={"x-pocket-lab-csrf": csrf},
    )
    assert step_up_required.status_code == 428
    assert step_up_required.json()["detail"]["reason_code"] == "owner_step_up_required"

    # The recovery-proof contract itself is tested below the WebAuthn boundary.
    # Keep the production passkey requirement intact while exercising the
    # endpoint's no-payload recovery semantics.
    monkeypatch.setattr(lite_enterprise_governance, "require_recent_assurance", lambda _auth, _purpose: None)
    resolved = client.post(
        f"/api/lite/enterprise/rules/activations/{operation_id}/resolve",
        headers={"x-pocket-lab-csrf": csrf},
    )
    assert resolved.status_code == 200
    assert resolved.json()["operation"]["state"] == "rolled_back"
    assert resolved.json()["resolution"]["evidence_ref"] == "policy:manual-recovery-proved"
