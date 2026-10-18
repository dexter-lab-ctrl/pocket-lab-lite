from __future__ import annotations

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException
from fastapi.testclient import TestClient

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir, load_fastapi_app


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/db/schema"


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _reason_code(response) -> str | None:
    body = response.json()
    detail = body.get("detail")
    if isinstance(detail, dict):
        return detail.get("reason_code") or body.get("reason_code")
    return body.get("reason_code")


def _assured(auth: dict, purpose: str) -> dict:
    now = datetime.now(timezone.utc)
    context = dict(auth)
    context["session"] = {
        **(auth.get("session") or {}),
        "assurance": [{
            "purpose": purpose,
            "credential_id": "test-passkey-only",
            "satisfied_at": now.isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
        }],
    }
    return context


@pytest.fixture()
def owner_operation_runtime(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import begin_immediate, connection, reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS
    from api_fastapi.services import lite_enterprise_identity, lite_identity_auth, lite_owner_operations

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_IDENTITY_SETUP_TOKEN", "owner-operation-test-token")
    monkeypatch.setenv("POCKETLAB_IDENTITY_COOKIE_SECURE", "0")
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()

    owner = lite_identity_auth.setup_owner(
        username="owner",
        display_name="Pocket Lab Owner",
        password="correct horse battery staple",
        setup_token="owner-operation-test-token",
    )
    login = lite_identity_auth.login(username="owner", password="correct horse battery staple")
    owner_auth = lite_enterprise_identity.enrich_auth_context(
        lite_identity_auth.authenticate_session_token(login["session_token"])
    )
    target = {
        "node_id": "secondary-phone",
        "label": "Secondary Phone",
        "identity_revision": 3,
        "binding": {
            "node_id": "secondary-phone",
            "identity_status": "verified",
            "identity_revision": 3,
            "identity_verified_at": "2026-10-18T08:00:00Z",
        },
        "binding_digest": "secondary-target-binding-v1",
    }
    monkeypatch.setattr(lite_owner_operations, "_target_binding", lambda _node_id: dict(target))
    return {
        "state": state,
        "owner": owner,
        "owner_auth": owner_auth,
        "approval_auth": _assured(owner_auth, lite_owner_operations.OWNER_APPROVAL_PURPOSE),
        "registration_auth": _assured(owner_auth, lite_owner_operations.CLIENT_REGISTRATION_PURPOSE),
        "target": target,
        "modules": (deps, lite_owner_operations),
        "db": (begin_immediate, connection),
    }


def _descriptor(client_id: str, *, reason: str = "Production Photo Backup acceptance", key: str = "acceptance-test-0001") -> dict:
    return {
        "contract_version": 1,
        "operation": "photo_backup.bounded_acceptance.v1",
        "requester_id": client_id,
        "target_node_id": "secondary-phone",
        "scope": {
            "fixture": "one_server_generated_jpeg",
            "collection": "pictures",
            "repeat": "same_fixture_once",
        },
        "reason": reason,
        "idempotency_key": key,
    }


def _register(runtime: dict, client_id: str = "registered-qualification-client"):
    _deps, operations = runtime["modules"]
    private = Ed25519PrivateKey.generate()
    public = _b64(private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    challenge = operations.issue_registration_challenge(
        runtime["owner_auth"], client_id=client_id, public_key=public
    )
    registered = operations.register_client(
        runtime["registration_auth"],
        client_id=client_id,
        display_name="Registered qualification client",
        public_key=public,
        challenge_id=challenge["challenge_id"],
        signature=_b64(private.sign(challenge["signing_payload"].encode("utf-8"))),
    )
    return private, public, registered


def _request(runtime: dict, private: Ed25519PrivateKey, client_id: str, descriptor: dict) -> dict:
    _deps, operations = runtime["modules"]
    challenge = operations.issue_request_challenge(client_id=client_id, descriptor=descriptor)
    return operations.request_operation(
        client_id=client_id,
        descriptor=descriptor,
        challenge_id=challenge["challenge_id"],
        signature=_b64(private.sign(challenge["signing_payload"].encode("utf-8"))),
    )


def test_schema_upgrade_adds_owner_operation_tables_and_is_restart_idempotent(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.db.connection import read_connection, reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations, latest_schema_version, migration_versions

    legacy = tmp_path / "schema-before-owner-operations"
    legacy.mkdir()
    for source in SCHEMA.glob("*.sql"):
        if int(source.name.split("_", 1)[0]) <= 40:
            shutil.copy2(source, legacy / source.name)
    database = tmp_path / "owner-operations.sqlite3"
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(database))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path))
    reset_sqlite_path_cache()
    assert apply_migrations(legacy) == list(range(1, 41))
    assert apply_migrations() == [41]
    assert apply_migrations() == []
    assert latest_schema_version() == 41
    with read_connection() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {
            "owner_operation_clients",
            "owner_operation_challenges",
            "owner_approved_operations",
            "owner_operation_events",
        } <= tables
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_descriptor_is_strict_and_cannot_carry_paths_urls_or_arbitrary_scope(owner_operation_runtime):
    _deps, operations = owner_operation_runtime["modules"]
    valid = _descriptor("registered-qualification-client")
    with pytest.raises(operations.OwnerOperationError) as extra:
        operations.normalize_descriptor({**valid, "source_path": "/photos"})
    assert extra.value.reason_code == "descriptor_fields_invalid"
    with pytest.raises(operations.OwnerOperationError) as path_reason:
        operations.normalize_descriptor({**valid, "reason": "/srv/photos"})
    assert path_reason.value.reason_code == "reason_invalid"
    with pytest.raises(operations.OwnerOperationError) as url_reason:
        operations.normalize_descriptor({**valid, "reason": "https://attacker.invalid"})
    assert url_reason.value.reason_code == "reason_invalid"
    with pytest.raises(operations.OwnerOperationError) as scope:
        operations.normalize_descriptor({**valid, "scope": {"fixture": "all_media", "collection": "pictures", "repeat": "same_fixture_once"}})
    assert scope.value.reason_code == "scope_invalid"
    with pytest.raises(operations.OwnerOperationError) as idem:
        operations.normalize_descriptor({**valid, "idempotency_key": "bad key"})
    assert idem.value.reason_code == "idempotency_key_invalid"


def test_registration_proof_binding_idempotency_replay_and_sanitized_observer(owner_operation_runtime):
    runtime = owner_operation_runtime
    _private, _public, registered = _register(runtime)
    _private_two, _public_two, registered_two = _register(runtime, "second-qualification-client")
    _deps, operations = runtime["modules"]
    assert registered["capabilities"] == [operations.OPERATION_TYPE]
    assert "public_key" not in registered
    assert "fingerprint" not in registered

    descriptor = _descriptor("registered-qualification-client")
    challenge = operations.issue_request_challenge(client_id=descriptor["requester_id"], descriptor=descriptor)
    signature = _b64(_private.sign(challenge["signing_payload"].encode("utf-8")))
    created = operations.request_operation(
        client_id=descriptor["requester_id"], descriptor=descriptor,
        challenge_id=challenge["challenge_id"], signature=signature,
    )
    assert created["status"] == "pending_approval"
    assert created["scope"] == descriptor["scope"]
    assert created["target_node_id"] == "secondary-phone"
    assert created["destination"] == "PhotoPrism on this server"
    assert "descriptor" not in created
    assert "signing_payload" not in created

    with pytest.raises(operations.OwnerOperationError) as replay:
        operations.request_operation(
            client_id=descriptor["requester_id"], descriptor=descriptor,
            challenge_id=challenge["challenge_id"], signature=signature,
        )
    assert replay.value.reason_code == "challenge_replayed"

    duplicate = _request(runtime, _private, descriptor["requester_id"], descriptor)
    assert duplicate["operation_id"] == created["operation_id"]
    assert duplicate["idempotent"] is True

    modified_challenge = operations.issue_request_challenge(client_id=descriptor["requester_id"], descriptor=descriptor)
    with pytest.raises(operations.OwnerOperationError) as modified:
        operations.request_operation(
            client_id=descriptor["requester_id"],
            descriptor={**descriptor, "reason": "Changed after approval request"},
            challenge_id=modified_challenge["challenge_id"],
            signature=_b64(_private.sign(modified_challenge["signing_payload"].encode("utf-8"))),
        )
    assert modified.value.reason_code == "request_binding_invalid"

    observer_challenge = operations.issue_observer_challenge(
        client_id=descriptor["requester_id"], operation_id=created["operation_id"]
    )
    observed = operations.observe_operation(
        client_id=descriptor["requester_id"], operation_id=created["operation_id"],
        challenge_id=observer_challenge["challenge_id"],
        signature=_b64(_private.sign(observer_challenge["signing_payload"].encode("utf-8"))),
    )
    assert observed["operation_id"] == created["operation_id"]
    assert observed["requester_id"] is None
    assert "public_key" not in observed and "credential" not in observed and "path" not in observed
    with pytest.raises(operations.OwnerOperationError) as cross_client:
        operations.issue_observer_challenge(
            client_id=registered_two["client_id"], operation_id=created["operation_id"]
        )
    assert cross_client.value.reason_code == "operation_not_found"


def test_owner_approval_requires_real_session_assurance_and_rejects_synthetic(owner_operation_runtime, monkeypatch):
    runtime = owner_operation_runtime
    private, _public, _registered = _register(runtime)
    descriptor = _descriptor("registered-qualification-client", key="approval-test-0001")
    operation = _request(runtime, private, descriptor["requester_id"], descriptor)
    _deps, operations = runtime["modules"]

    with pytest.raises(operations.OwnerOperationError) as no_step_up:
        operations.approve_operation(runtime["owner_auth"], operation["operation_id"])
    assert no_step_up.value.reason_code == "owner_step_up_required"

    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "1")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "1")
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    with pytest.raises(operations.OwnerOperationError) as synthetic:
        operations.approve_operation(_deps.qualification_owner_context(), operation["operation_id"])
    assert synthetic.value.reason_code == "synthetic_owner_forbidden"

    monkeypatch.delenv("POCKETLAB_TEST_AUTH_BYPASS")
    monkeypatch.delenv("POCKETLAB_QUALIFICATION_OWNER")
    monkeypatch.delenv("POCKETLAB_ENVIRONMENT")
    approved = operations.approve_operation(runtime["approval_auth"], operation["operation_id"])
    assert approved["status"] == "approved"
    assert approved["execution_stage"] == "awaiting_initial"
    with pytest.raises(operations.OwnerOperationError) as duplicate:
        operations.approve_operation(runtime["approval_auth"], operation["operation_id"])
    assert duplicate.value.reason_code == "approval_not_pending"


def test_concurrent_approval_has_one_winner_and_target_change_fails_closed(owner_operation_runtime, monkeypatch):
    runtime = owner_operation_runtime
    private, _public, _registered = _register(runtime)
    _deps, operations = runtime["modules"]
    operation = _request(runtime, private, "registered-qualification-client", _descriptor("registered-qualification-client", key="concurrent-0001"))

    def approve():
        try:
            return ("ok", operations.approve_operation(runtime["approval_auth"], operation["operation_id"]))
        except operations.OwnerOperationError as exc:
            return ("error", exc.reason_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _item: approve(), range(2)))
    assert [item[0] for item in outcomes].count("ok") == 1
    assert [item[0] for item in outcomes].count("error") == 1
    assert next(item[1]["status"] for item in outcomes if item[0] == "ok") == "approved"
    assert next(item[1] for item in outcomes if item[0] == "error") in {"approval_not_pending", "approval_race"}

    second = _request(runtime, private, "registered-qualification-client", _descriptor("registered-qualification-client", key="target-change-0001"))
    changed = {**runtime["target"], "identity_revision": 4, "binding_digest": "changed-target-binding"}
    monkeypatch.setattr(operations, "_target_binding", lambda _node_id: dict(changed))
    with pytest.raises(operations.OwnerOperationError) as target_change:
        operations.approve_operation(runtime["approval_auth"], second["operation_id"])
    assert target_change.value.reason_code == "target_identity_changed"
    monkeypatch.setattr(operations, "_target_binding", lambda _node_id: dict(runtime["target"]))
    with runtime["db"][1]() as conn:
        row = conn.execute("SELECT status,terminal_reason FROM owner_approved_operations WHERE operation_id=?", (second["operation_id"],)).fetchone()
    assert row["status"] == "blocked"
    assert row["terminal_reason"] == "target_identity_changed"


def test_requester_revocation_cancels_pending_operation_and_records_event(owner_operation_runtime):
    runtime = owner_operation_runtime
    private, _public, registered = _register(runtime)
    _operation = _request(runtime, private, registered["client_id"], _descriptor(registered["client_id"], key="revocation-0001"))
    _deps, operations = runtime["modules"]
    result = operations.revoke_client(runtime["registration_auth"], client_id=registered["client_id"])
    assert result["status"] == "revoked"
    with runtime["db"][1]() as conn:
        row = conn.execute("SELECT status,terminal_reason FROM owner_approved_operations WHERE idempotency_key='revocation-0001'").fetchone()
        event = conn.execute("SELECT event_type,reason_code FROM owner_operation_events WHERE operation_id=(SELECT operation_id FROM owner_approved_operations WHERE idempotency_key='revocation-0001') ORDER BY event_id DESC LIMIT 1").fetchone()
    assert row["status"] == "cancelled"
    assert row["terminal_reason"] == "requester_revoked"
    assert event["event_type"] == "cancel_requested"
    assert event["reason_code"] == "requester_revoked"
    with pytest.raises(operations.OwnerOperationError) as revoked:
        operations.issue_request_challenge(client_id=registered["client_id"], descriptor=_descriptor(registered["client_id"], key="revocation-0002"))
    assert revoked.value.reason_code == "client_revoked"


def test_approved_dispatch_reuses_existing_photo_backup_handler_and_fixed_scope(owner_operation_runtime, monkeypatch):
    runtime = owner_operation_runtime
    private, _public, _registered = _register(runtime)
    _deps, operations = runtime["modules"]
    operation = _request(runtime, private, "registered-qualification-client", _descriptor("registered-qualification-client", key="dispatch-0001"))
    operations.approve_operation(runtime["approval_auth"], operation["operation_id"])

    from api_fastapi.services import action_queue, lite_photo_backup

    calls = []
    monkeypatch.setattr(lite_photo_backup, "prepare_acceptance_fixture", lambda _node: {"fixture_id": "fixture-0123456789abcdef0123"})
    monkeypatch.setattr(lite_photo_backup, "acceptance_fixture_descriptor", lambda _node, fixture: {"fixture_id": fixture, "collection": "pictures", "scope": "bounded_acceptance_fixture"})
    def fake_start(_node, collections, **kwargs):
        assert collections == ["pictures"]
        assert kwargs["destination_id"] == lite_photo_backup_destinations.CURRENT_DESTINATION_ID
        assert kwargs["acceptance_fixture_id"] == "fixture-0123456789abcdef0123"
        return {"backup_id": "photo-0123456789abcdef0123", "node_id": "secondary-phone", "collections": collections}

    from api_fastapi.services import lite_photo_backup_destinations
    monkeypatch.setattr(lite_photo_backup, "make_start_command", fake_start)

    async def fake_submit(subject, event_type, command, *, trace_id):
        calls.append((subject, event_type, command, trace_id))
        return {"status": "queued"}

    monkeypatch.setattr(action_queue, "submit_domain_command", fake_submit)
    dispatched = asyncio.run(operations.dispatch_approved_operation(operation["operation_id"]))
    assert dispatched["execution_stage"] == "initial_dispatched"
    assert dispatched["backup_id"] == "photo-0123456789abcdef0123"
    assert len(calls) == 1
    assert calls[0][0] == lite_photo_backup.PHOTO_BACKUP_START_SUBJECT
    assert calls[0][2]["source_fixture"]["scope"] == "bounded_acceptance_fixture"
    assert calls[0][2]["collections"] == ["pictures"]


def test_reconcile_target_change_blocks_active_operation(owner_operation_runtime, monkeypatch):
    runtime = owner_operation_runtime
    private, _public, _registered = _register(runtime, "reconcile-target-client")
    _deps, operations = runtime["modules"]
    operation = _request(
        runtime,
        private,
        "reconcile-target-client",
        _descriptor("reconcile-target-client", key="reconcile-target-0001"),
    )
    operations.approve_operation(runtime["approval_auth"], operation["operation_id"])
    with runtime["db"][1]() as conn:
        with runtime["db"][0](conn) as tx:
            tx.execute(
                "UPDATE owner_approved_operations SET status='executing',execution_stage='initial_dispatched' WHERE operation_id=?",
                (operation["operation_id"],),
            )
    changed = {**runtime["target"], "identity_revision": 4, "binding_digest": "changed-after-dispatch"}
    monkeypatch.setattr(operations, "_target_binding", lambda _node_id: dict(changed))
    monkeypatch.setattr(
        operations,
        "_request_existing_job_cancellation",
        lambda *_args, **_kwargs: asyncio.sleep(0, result={"status": "not_bound"}),
    )
    result = asyncio.run(operations._reconcile_execution(operation["operation_id"]))
    assert result["status"] == "blocked"
    assert result["terminal_reason"] == "target_identity_changed"


def test_dispatch_binds_one_fixture_before_admission_retry(owner_operation_runtime, monkeypatch):
    runtime = owner_operation_runtime
    private, _public, _registered = _register(runtime, "registered-fixture-retry-client")
    _deps, operations = runtime["modules"]
    operation = _request(
        runtime,
        private,
        "registered-fixture-retry-client",
        _descriptor("registered-fixture-retry-client", key="fixture-retry-0001"),
    )
    operations.approve_operation(runtime["approval_auth"], operation["operation_id"])

    from api_fastapi.services import action_queue, lite_photo_backup

    fixture_id = "fixture-0123456789abcdef0123"
    prepared = {"count": 0}

    def prepare(_node):
        prepared["count"] += 1
        return {"fixture_id": fixture_id}

    monkeypatch.setattr(lite_photo_backup, "prepare_acceptance_fixture", prepare)
    monkeypatch.setattr(lite_photo_backup, "acceptance_fixture_descriptor", lambda _node, fixture: {"fixture_id": fixture, "collection": "pictures", "scope": "bounded_acceptance_fixture"})
    monkeypatch.setattr(lite_photo_backup, "make_start_command", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("admission temporarily unavailable")))
    first = asyncio.run(operations.dispatch_approved_operation(operation["operation_id"]))
    assert first["status"] == "approved"
    assert first["execution_stage"] == "awaiting_initial"
    assert prepared["count"] == 1

    with runtime["db"][1]() as conn:
        row = conn.execute("SELECT fixture_id FROM owner_approved_operations WHERE operation_id=?", (operation["operation_id"],)).fetchone()
    assert row["fixture_id"] == fixture_id

    monkeypatch.setattr(lite_photo_backup, "prepare_acceptance_fixture", lambda _node: (_ for _ in ()).throw(AssertionError("retry must reuse the bound fixture")))
    monkeypatch.setattr(lite_photo_backup, "make_start_command", lambda _node, collections, **kwargs: {"backup_id": "photo-0123456789abcdef0123", "node_id": "secondary-phone", "collections": collections, "acceptance_fixture_id": kwargs["acceptance_fixture_id"]})
    submitted = []

    async def submit(subject, event_type, command, *, trace_id):
        submitted.append((subject, event_type, command, trace_id))
        return {"status": "queued"}

    monkeypatch.setattr(action_queue, "submit_domain_command", submit)
    second = asyncio.run(operations.dispatch_approved_operation(operation["operation_id"]))
    assert second["execution_stage"] == "initial_dispatched"
    assert prepared["count"] == 1
    assert submitted[0][2]["acceptance_fixture_id"] == fixture_id


def test_fixture_expiry_after_binding_is_terminal_and_does_not_issue_another_fixture(owner_operation_runtime, monkeypatch):
    runtime = owner_operation_runtime
    private, _public, _registered = _register(runtime, "expired-fixture-client")
    _deps, operations = runtime["modules"]
    operation = _request(
        runtime,
        private,
        "expired-fixture-client",
        _descriptor("expired-fixture-client", key="expired-fixture-0001"),
    )
    operations.approve_operation(runtime["approval_auth"], operation["operation_id"])
    from api_fastapi.services import lite_photo_backup

    fixture_id = "fixture-0123456789abcdef0123"
    prepared = {"count": 0}

    def prepare(_node):
        prepared["count"] += 1
        return {"fixture_id": fixture_id}

    monkeypatch.setattr(lite_photo_backup, "prepare_acceptance_fixture", prepare)
    monkeypatch.setattr(
        lite_photo_backup,
        "make_start_command",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            HTTPException(
                status_code=409,
                detail={"reason_code": "source_fixture_expired", "sanitized": True},
            )
        ),
    )
    result = asyncio.run(operations.dispatch_approved_operation(operation["operation_id"]))
    assert result["status"] == "failed"
    assert result["terminal_reason"] == "source_fixture_expired"
    assert prepared["count"] == 1

    with runtime["db"][1]() as conn:
        row = conn.execute(
            "SELECT status,fixture_id FROM owner_approved_operations WHERE operation_id=?",
            (operation["operation_id"],),
        ).fetchone()
    assert row["status"] == "failed"
    assert row["fixture_id"] == fixture_id


def test_dispatch_reuses_durable_backup_binding_after_publish_loss(owner_operation_runtime, monkeypatch):
    runtime = owner_operation_runtime
    private, _public, _registered = _register(runtime, "registered-backup-retry-client")
    _deps, operations = runtime["modules"]
    operation = _request(
        runtime,
        private,
        "registered-backup-retry-client",
        _descriptor("registered-backup-retry-client", key="backup-retry-0001"),
    )
    operations.approve_operation(runtime["approval_auth"], operation["operation_id"])

    from api_fastapi.services import action_queue, lite_photo_backup

    fixture_id = "fixture-0123456789abcdef0123"
    backup_id = "photo-0123456789abcdef0123"
    monkeypatch.setattr(lite_photo_backup, "prepare_acceptance_fixture", lambda _node: {"fixture_id": fixture_id})
    monkeypatch.setattr(
        lite_photo_backup,
        "acceptance_fixture_descriptor",
        lambda _node, fixture: {"fixture_id": fixture, "collection": "pictures", "scope": "bounded_acceptance_fixture"},
    )
    calls = []

    def start(_node, collections, **kwargs):
        calls.append(kwargs)
        assert collections == ["pictures"]
        return {"backup_id": backup_id, "node_id": "secondary-phone", "collections": collections}

    monkeypatch.setattr(lite_photo_backup, "make_start_command", start)
    monkeypatch.setattr(
        lite_photo_backup,
        "job_status",
        lambda _backup_id: {
            "backup_id": backup_id,
            "node_id": "secondary-phone",
            "destination_id": "server-photoprism-originals",
            "destination_contract_version": 2,
            "source_fixture_id": fixture_id,
            "source_scope": "bounded_acceptance_fixture",
            "collections": ["pictures"],
            "status": "queued",
        },
    )
    submissions = []

    async def submit(subject, event_type, command, *, trace_id):
        submissions.append((subject, event_type, command, trace_id))
        if len(submissions) == 1:
            raise RuntimeError("acknowledgment lost")
        return {"status": "queued"}

    monkeypatch.setattr(action_queue, "submit_domain_command", submit)

    first = asyncio.run(operations.dispatch_approved_operation(operation["operation_id"]))
    assert first["execution_stage"] == "awaiting_initial"
    assert first["backup_id"] == backup_id

    second = asyncio.run(operations.dispatch_approved_operation(operation["operation_id"]))
    assert second["execution_stage"] == "initial_dispatched"
    assert [call.get("backup_id") for call in calls] == [None, backup_id]
    assert len(submissions) == 2


def test_approval_expiry_is_terminal_and_does_not_execute(owner_operation_runtime):
    runtime = owner_operation_runtime
    private, _public, _registered = _register(runtime)
    _deps, operations = runtime["modules"]
    operation = _request(runtime, private, "registered-qualification-client", _descriptor("registered-qualification-client", key="expiry-0001"))
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    with runtime["db"][1]() as conn:
        with runtime["db"][0](conn) as tx:
            tx.execute("UPDATE owner_approved_operations SET approval_deadline=? WHERE operation_id=?", (past, operation["operation_id"]))
    assert operations._mark_expired_operations() == 1
    with runtime["db"][1]() as conn:
        row = conn.execute("SELECT status,execution_stage FROM owner_approved_operations WHERE operation_id=?", (operation["operation_id"],)).fetchone()
    assert row["status"] == "expired"
    assert row["execution_stage"] == "terminal"


def test_http_surface_requires_identity_csrf_and_never_creates_anonymous_request(owner_operation_runtime):
    runtime = owner_operation_runtime
    api = TestClient(load_fastapi_app())
    descriptor = _descriptor("unregistered-client", key="http-anonymous-0001")
    anonymous = api.post(
        "/api/lite/owner-operations/request-challenge",
        json={"client_id": descriptor["requester_id"], "descriptor": descriptor},
    )
    assert anonymous.status_code == 401
    assert _reason_code(anonymous) == "client_unknown", anonymous.text

    public = _b64(Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))
    missing_csrf = api.post(
        "/api/lite/owner-operations/clients/challenge",
        json={"client_id": "registered-http-client", "public_key": public},
    )
    assert missing_csrf.status_code == 401

    login = api.post("/api/lite/identity/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    missing_csrf = api.post(
        "/api/lite/owner-operations/clients/challenge",
        json={"client_id": "registered-http-client", "public_key": public},
    )
    assert missing_csrf.status_code == 403
    assert _reason_code(missing_csrf) == "csrf_required", missing_csrf.text

    owner_read_without_auth = TestClient(load_fastapi_app()).get("/api/lite/owner-operations/pending")
    assert owner_read_without_auth.status_code == 401


def test_http_approval_write_is_csrf_gated_before_operation_authority(owner_operation_runtime):
    runtime = owner_operation_runtime
    private, _public, _registered = _register(runtime, "registered-http-approval-client")
    operation = _request(
        runtime,
        private,
        "registered-http-approval-client",
        _descriptor("registered-http-approval-client", key="http-approval-0001"),
    )
    api = TestClient(load_fastapi_app())
    login = api.post("/api/lite/identity/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert login.status_code == 200
    response = api.post(f"/api/lite/owner-operations/pending/{operation['operation_id']}/approve", json={})
    assert response.status_code == 403
    assert _reason_code(response) == "csrf_required", response.text
    with runtime["db"][1]() as conn:
        row = conn.execute("SELECT status FROM owner_approved_operations WHERE operation_id=?", (operation["operation_id"],)).fetchone()
    assert row["status"] == "pending_approval"
