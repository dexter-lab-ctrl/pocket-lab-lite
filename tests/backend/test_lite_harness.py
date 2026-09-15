from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir, load_fastapi_app


PROVISIONING_TOKEN = "synthetic-test-provisioning-token"
TARGET_SCOPE = "local_server_host_only"
HARNESS_HEADER = "X-Pocket-Lab-Harness-Session"
PROVISIONING_HEADERS = {
    "X-Pocket-Lab-Harness-Provisioning": "1",
    "X-Pocket-Lab-Harness-Provisioning-Token": PROVISIONING_TOKEN,
}


@pytest.fixture()
def harness_runtime(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_DEV_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_IDENTITY_COOKIE_SECURE", "0")
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "")
    monkeypatch.setenv("POCKETLAB_ALLOW_LOCAL_WRITE", "1")
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_HARNESS_ENABLED", "1")
    monkeypatch.setenv("POCKETLAB_HARNESS_DESTRUCTIVE", "0")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "0")
    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_HARNESS_PROVISIONING_TOKEN", PROVISIONING_TOKEN)
    monkeypatch.setenv("POCKETLAB_HARNESS_RUNTIME_ID", "runtime-test")
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()
    return state


def _client() -> TestClient:
    return TestClient(load_fastapi_app(), client=("127.0.0.1", 40123))


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_b64u(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return private, public


def _register(
    client: TestClient,
    private,
    public: bytes,
    *,
    principal_id: str = "machine-runner",
    profiles: tuple[str, ...] = ("recovery-qualifier",),
    extra: dict | None = None,
    expected_status: int = 201,
) -> dict:
    payload = {
        "principal_id": principal_id,
        "display_name": "Synthetic qualification runner",
        "public_key": _b64u(public),
        "profiles": list(profiles),
        "algorithm": "ed25519",
        "expires_in_seconds": 3600,
    }
    payload.update(extra or {})
    if "allowed_profiles" in (extra or {}):
        payload.pop("profiles", None)
    response = client.post("/api/lite/harness/principals", json=payload, headers=PROVISIONING_HEADERS)
    assert response.status_code == expected_status, response.text
    return response.json()


def _challenge(client: TestClient, *, principal_id: str = "machine-runner", profile: str = "recovery-qualifier", purpose: str = "recovery.verify", target_scope: str = TARGET_SCOPE, expected_status: int = 200) -> dict:
    response = client.post(
        "/api/lite/harness/challenge",
        json={"principal_id": principal_id, "purpose": purpose, "profile": profile, "target_scope": target_scope},
    )
    assert response.status_code == expected_status, response.text
    return response.json()


def _session_request(client: TestClient, challenge: dict, private, *, principal_id: str | None = None, profile: str | None = None, signing_payload: str | None = None, signature: str | None = None):
    payload = signing_payload or challenge["signing_payload"]
    response = client.post(
        "/api/lite/harness/session",
        json={
            "challenge_id": challenge["challenge_id"],
            "signing_payload": payload,
            "signature": signature or _b64u(private.sign(payload.encode("utf-8"))),
            **({"principal_id": principal_id} if principal_id is not None else {}),
            **({"profile": profile} if profile is not None else {}),
        },
    )
    return response


def _start_session(client: TestClient, private, *, principal_id: str = "machine-runner", profile: str = "recovery-qualifier", purpose: str = "recovery.verify") -> tuple[dict, dict]:
    challenge = _challenge(client, principal_id=principal_id, profile=profile, purpose=purpose)
    response = _session_request(client, challenge, private)
    assert response.status_code == 201, response.text
    return response.json(), challenge


def _request(headers: dict[str, str], *, host: str = "127.0.0.1") -> Request:
    encoded = [(key.lower().encode("latin-1"), value.encode("latin-1")) for key, value in headers.items()]
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/api/lite/status",
        "query_string": b"",
        "headers": encoded,
        "client": (host, 40123),
        "server": (host, 8080),
        "scheme": "http",
    })


def test_default_off_and_production_startup_are_fail_closed(harness_runtime, monkeypatch):
    from api_fastapi.services import lite_harness

    for name in (
        "POCKETLAB_HARNESS_ENABLED",
        "POCKETLAB_HARNESS_DESTRUCTIVE",
        "POCKETLAB_QUALIFICATION_OWNER",
        "POCKETLAB_TEST_AUTH_BYPASS",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("POCKETLAB_ENVIRONMENT", raising=False)
    state = lite_harness.verify_harness_disabled()
    assert state["enabled"] is False
    assert state["environment"] == "development"

    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "production")
    assert lite_harness.verify_harness_disabled()["environment"] == "production"

    monkeypatch.setenv("POCKETLAB_HARNESS_ENABLED", "1")
    with pytest.raises(lite_harness.HarnessConfigurationError) as error:
        lite_harness.validate_startup_configuration()
    assert error.value.reason_code == "harness_forbidden_in_production"

    monkeypatch.setenv("POCKETLAB_HARNESS_ENABLED", "0")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "1")
    with pytest.raises(lite_harness.HarnessConfigurationError) as error:
        lite_harness.validate_startup_configuration()
    assert error.value.reason_code == "harness_forbidden_in_production"


def test_app_lifespan_refuses_unsafe_production_flags(harness_runtime, monkeypatch):
    from api_fastapi.services import lite_harness

    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "production")
    monkeypatch.setenv("POCKETLAB_HARNESS_ENABLED", "1")
    with pytest.raises(lite_harness.HarnessConfigurationError):
        with TestClient(load_fastapi_app(), client=("127.0.0.1", 40123)):
            pass


def test_key_bound_bootstrap_is_one_use_and_hash_only(harness_runtime, monkeypatch):
    client = _client()
    private, public = _key()
    principal_id = "codex-assurance-bootstrap"
    public_key = _b64u(public)
    fingerprint = "sha256:" + hashlib.sha256(public).hexdigest()
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_APPROVED", "1")
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID", principal_id)
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT", fingerprint)
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PROFILE", "security-assurance-runner")

    grant_response = client.post(
        "/api/lite/harness/bootstrap/grants",
        json={"principal_id": principal_id, "public_key": public_key},
    )
    assert grant_response.status_code == 201, grant_response.text
    grant = grant_response.json()
    assert grant["profile"] == "security-assurance-runner"
    assert grant["purpose"] == "security.assurance"
    assert grant["target_scope"] == TARGET_SCOPE
    assert grant["max_uses"] == 1
    assert "public_key" not in grant

    challenge_response = client.post(
        "/api/lite/harness/bootstrap/challenge",
        json={"grant_id": grant["grant_id"]},
    )
    assert challenge_response.status_code == 200, challenge_response.text
    challenge = challenge_response.json()
    complete_response = client.post(
        "/api/lite/harness/bootstrap/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "grant_id": grant["grant_id"],
            "principal_id": principal_id,
            "public_key": public_key,
            "signature": _b64u(private.sign(challenge["signing_payload"].encode("utf-8"))),
        },
    )
    assert complete_response.status_code == 201, complete_response.text
    session = complete_response.json()
    assert session["principal"]["default_profile"] == "security-assurance-runner"
    assert session["session"]["status"] == "active"
    assert session["session_token"]
    assert session["principal"]["principal_class"] == "qualification"
    assert "private" not in json.dumps(session).casefold()

    replay = client.post(
        "/api/lite/harness/bootstrap/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "grant_id": grant["grant_id"],
            "principal_id": principal_id,
            "public_key": public_key,
            "signature": _b64u(private.sign(challenge["signing_payload"].encode("utf-8"))),
        },
    )
    assert replay.status_code == 401
    assert replay.json()["reason_code"] == "bootstrap_grant_replayed"

    cleanup = client.post(
        "/api/lite/harness/principal/revoke",
        headers={HARNESS_HEADER: session["session_token"]},
    )
    assert cleanup.status_code == 200, cleanup.text
    assert cleanup.json()["active_assurance_runs_cancelled"] == 0
    after_cleanup = client.get("/api/lite/status", headers={HARNESS_HEADER: session["session_token"]})
    assert after_cleanup.status_code == 401
    assert after_cleanup.json()["reason_code"] == "harness_session_revoked"

    from api_fastapi.db.connection import connection

    with connection() as conn:
        row = conn.execute(
            "SELECT token_hash,public_key FROM harness_sessions s JOIN synthetic_principals p ON p.principal_id=s.principal_id WHERE s.principal_id=?",
            (principal_id,),
        ).fetchone()
        audit_types = {
            event["event_type"]
            for event in conn.execute(
                "SELECT event_type FROM harness_audit_events WHERE principal_id=? OR operation_id=?",
                (principal_id, grant["grant_id"]),
            )
        }
    assert row["token_hash"] != session["session_token"]
    assert row["public_key"] == public_key
    assert {
        "bootstrap_grant_created",
        "bootstrap_grant_consumed",
        "bootstrap_principal_created",
        "bootstrap_principal_revoked",
    }.issubset(audit_types)


def test_key_bound_bootstrap_applies_bounded_requested_session_ttl(harness_runtime, monkeypatch):
    client = _client()
    private, public = _key()
    principal_id = "codex-assurance-bootstrap-ttl"
    fingerprint = "sha256:" + hashlib.sha256(public).hexdigest()
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_APPROVED", "1")
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID", principal_id)
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT", fingerprint)
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PROFILE", "security-assurance-runner")

    grant = client.post(
        "/api/lite/harness/bootstrap/grants",
        json={"principal_id": principal_id, "public_key": _b64u(public)},
    ).json()
    challenge = client.post(
        "/api/lite/harness/bootstrap/challenge",
        json={"grant_id": grant["grant_id"]},
    ).json()
    response = client.post(
        "/api/lite/harness/bootstrap/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "grant_id": grant["grant_id"],
            "principal_id": principal_id,
            "public_key": _b64u(public),
            "signature": _b64u(private.sign(challenge["signing_payload"].encode("utf-8"))),
            "ttl_seconds": 60,
        },
    )
    assert response.status_code == 201, response.text
    session = response.json()["session"]
    started = datetime.fromisoformat(session["started_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
    assert 59 <= (expires - started).total_seconds() <= 61

    cleanup = client.post(
        "/api/lite/harness/principal/revoke",
        headers={HARNESS_HEADER: response.json()["session_token"]},
    )
    assert cleanup.status_code == 200, cleanup.text


def test_bootstrap_rejects_wrong_key_and_forwarded_transport(harness_runtime, monkeypatch):
    client = _client()
    private, public = _key()
    wrong_private, wrong_public = _key()
    principal_id = "codex-assurance-wrong-key"
    fingerprint = "sha256:" + hashlib.sha256(public).hexdigest()
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_APPROVED", "1")
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID", principal_id)
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT", fingerprint)
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PROFILE", "security-assurance-runner")
    grant = client.post(
        "/api/lite/harness/bootstrap/grants",
        json={"principal_id": principal_id, "public_key": _b64u(public)},
    ).json()
    challenge = client.post(
        "/api/lite/harness/bootstrap/challenge",
        json={"grant_id": grant["grant_id"]},
    ).json()
    wrong = client.post(
        "/api/lite/harness/bootstrap/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "grant_id": grant["grant_id"],
            "principal_id": principal_id,
            "public_key": _b64u(wrong_public),
            "signature": _b64u(wrong_private.sign(challenge["signing_payload"].encode("utf-8"))),
        },
    )
    assert wrong.status_code == 401
    assert wrong.json()["reason_code"] == "bootstrap_binding_mismatch"
    forwarded = client.post(
        "/api/lite/harness/bootstrap/challenge",
        json={"grant_id": grant["grant_id"]},
        headers={"X-Forwarded-For": "127.0.0.1"},
    )
    assert forwarded.status_code == 401
    assert forwarded.json()["reason_code"] == "harness_transport_rejected"


def test_bootstrap_retries_are_bounded_and_exact_grant_creation_is_idempotent(harness_runtime, monkeypatch):
    client = _client()
    private, public = _key()
    principal_id = "codex-assurance-attempts"
    fingerprint = "sha256:" + hashlib.sha256(public).hexdigest()
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_APPROVED", "1")
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID", principal_id)
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT", fingerprint)
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PROFILE", "security-assurance-runner")

    payload = {"principal_id": principal_id, "public_key": _b64u(public)}
    first_response = client.post("/api/lite/harness/bootstrap/grants", json=payload)
    assert first_response.status_code == 201, first_response.text
    first = first_response.json()
    retry = client.post("/api/lite/harness/bootstrap/grants", json=payload)
    assert retry.status_code == 201, retry.text
    assert retry.json()["grant_id"] == first["grant_id"]
    assert retry.json()["idempotent_reuse"] is True

    challenge = client.post(
        "/api/lite/harness/bootstrap/challenge", json={"grant_id": first["grant_id"]}
    ).json()
    # Keep the invalid proof deterministic without putting private material in
    # the request's public fields or test output.
    wrong_private, _ = _key()
    for attempt in range(1, 6):
        rejected = client.post(
            "/api/lite/harness/bootstrap/complete",
            json={
                "challenge_id": challenge["challenge_id"],
                "grant_id": first["grant_id"],
                "principal_id": principal_id,
                "public_key": _b64u(public),
                "signature": _b64u(wrong_private.sign(challenge["signing_payload"].encode("utf-8"))),
            },
        )
        assert rejected.status_code == 401, rejected.text
        expected = "bootstrap_attempt_limit" if attempt == 5 else "bootstrap_signature_invalid"
        assert rejected.json()["reason_code"] == expected

    replay = client.post(
        "/api/lite/harness/bootstrap/challenge", json={"grant_id": first["grant_id"]}
    )
    assert replay.status_code == 401
    assert replay.json()["reason_code"] == "bootstrap_grant_replayed"


def test_assurance_client_continuity_is_bounded_and_does_not_persist_tokens(harness_runtime, tmp_path):
    script = Path("scripts/dev/lite/security_assurance.py").resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_security_assurance_client", script)
    assert spec and spec.loader
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    continuity = tmp_path / "continuity.json"
    client._write_continuity(
        continuity,
        {
            "principal_id": "codex-assurance",
            "public_key_fingerprint": "sha256:" + "a" * 64,
            "private_key_file_path": "/tmp/codex-assurance.key",
            "active_run_id": "assurance-" + "b" * 32,
            "session_token": "must-not-persist",
            "signing_payload": "must-not-persist",
            "signature": "must-not-persist",
        },
    )
    content = continuity.read_text(encoding="utf-8")
    assert "must-not-persist" not in content
    assert "session_token" not in content
    assert stat.S_IMODE(continuity.stat().st_mode) == 0o600
    assert client._should_reauthenticate(RuntimeError("assurance_transport_unavailable: OSError")) is True
    assert client._should_reauthenticate(RuntimeError("run_not_found: rejected")) is False


def test_assurance_client_discards_stale_run_when_identity_changes(tmp_path):
    script = Path("scripts/dev/lite/security_assurance.py").resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_security_assurance_identity_continuity", script)
    assert spec and spec.loader
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)

    state = {
        "principal_id": "old-assurance-runner",
        "public_key_fingerprint": "sha256:" + "a" * 64,
        "active_run_id": "assurance-" + "b" * 32,
        "suite_id": "standard",
        "scenario_id": "security-projection",
        "last_event_sequence": 12,
        "runtime_id": "runtime-old",
        "revision_sha": "c" * 40,
    }
    client._reset_continuity_for_identity_change(
        state,
        principal_id="new-assurance-runner",
        fingerprint="sha256:" + "d" * 64,
    )

    assert "active_run_id" not in state
    assert "suite_id" not in state
    assert "scenario_id" not in state
    assert "last_event_sequence" not in state
    assert "runtime_id" not in state
    assert "revision_sha" not in state


def test_assurance_client_keeps_matching_identity_continuity(tmp_path):
    script = Path("scripts/dev/lite/security_assurance.py").resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_security_assurance_matching_continuity", script)
    assert spec and spec.loader
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)

    state = {
        "principal_id": "assurance-runner",
        "public_key_fingerprint": "sha256:" + "a" * 64,
        "active_run_id": "assurance-" + "b" * 32,
        "suite_id": "standard",
    }
    client._reset_continuity_for_identity_change(
        state,
        principal_id="ASSURANCE-RUNNER",
        fingerprint="SHA256:" + "A" * 64,
    )

    assert state["active_run_id"] == "assurance-" + "b" * 32
    assert state["suite_id"] == "standard"


def test_assurance_client_ensure_lease_renews_with_keyword_arguments(tmp_path, monkeypatch):
    script = Path("scripts/dev/lite/security_assurance.py").resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_security_assurance_ensure_lease", script)
    assert spec and spec.loader
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)
    lease = {
        "session_token": "memory-only-token",
        "session": {
            "started_at": "2026-09-14T12:00:00Z",
            "expires_at": "2026-09-14T12:00:10Z",
        },
        "session_ids": ["hs-old"],
        "renewal_count": 0,
    }
    calls = []

    def fake_renew(current, *, principal_id, key_file, ttl_seconds):
        calls.append((current, principal_id, key_file, ttl_seconds))

    monkeypatch.setattr(client, "_renew_lease", fake_renew)
    client._ensure_lease(
        lease,
        principal_id="assurance-runner",
        key_file=str(tmp_path / "runner.key"),
        ttl_seconds=60,
    )
    assert len(calls) == 1
    assert calls[0][1:] == ("assurance-runner", str(tmp_path / "runner.key"), 60)


def test_assurance_client_recovers_lost_admission_response_without_duplicate_run(tmp_path, monkeypatch):
    script = Path("scripts/dev/lite/security_assurance.py").resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_security_assurance_admission_recovery", script)
    assert spec and spec.loader
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)

    calls = []

    def fake_request(method, path, payload=None, **kwargs):
        calls.append((method, path, payload, kwargs))
        if method == "POST":
            raise RuntimeError("assurance_transport_unavailable: TimeoutError")
        return {
            "runs": [{
                "run_id": "assurance-" + "c" * 32,
                "suite_id": "standard",
                "status": "QUEUED",
                "runtime_id": "runtime-test",
                "revision_sha": "a" * 40,
            }],
            "sanitized": True,
        }

    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr(client, "_ensure_lease", lambda *args, **kwargs: None)
    result = client._admit_qualified_run(
        suite_id="standard",
        lease={"session_token": "memory-only-token"},
        principal_id="assurance-runner",
        key_file=str(tmp_path / "runner.key"),
        preflight={"runtime_id": "runtime-test", "revision": "a" * 40},
        session_ttl_seconds=180,
    )

    assert result["run_id"] == "assurance-" + "c" * 32
    assert result["transport_recovered"] is True
    assert [call[0] for call in calls] == ["POST", "POST", "GET"]
    assert calls[0][1].endswith("/runs")
    assert calls[2][1].endswith("/runs?limit=100")
    assert all(call[3].get("timeout_seconds") in {30.0, 60.0} for call in calls)


def test_harness_client_forwards_bounded_session_ttl_without_persisting_token(tmp_path, monkeypatch):
    script = Path("scripts/dev/lite/harness.py").resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_harness_client_ttl", script)
    assert spec and spec.loader
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)

    class FakeKey:
        def sign(self, payload):
            assert payload == b"canonical-challenge"
            return b"s" * 64

    requests = []

    def fake_request(method, path, payload=None, headers=None):
        requests.append((method, path, payload, headers))
        if path.endswith("/challenge"):
            return {"challenge_id": "hch-" + "a" * 32, "signing_payload": "canonical-challenge"}
        return {"session_token": "memory-only-test-token", "session": {"harness_session_id": "hs-test"}}

    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr(client, "_private_key", lambda _path: FakeKey())
    client.start_session(
        principal_id="ttl-runner",
        profile="security-assurance-runner",
        purpose="security.assurance",
        key_file=str(tmp_path / "machine.key"),
        ttl_seconds=60,
    )

    assert requests[0][2]["ttl_seconds"] == 60
    assert requests[1][2]["ttl_seconds"] == 60


def test_qualification_keeps_safe_adversarial_lane_independent_of_standard(tmp_path):
    script = Path("scripts/dev/lite/security_assurance.py").resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_security_assurance_adversarial_gate", script)
    assert spec and spec.loader
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)

    assert client._safe_adversarial_admitted(
        {"smoke": {"status": "PASS"}, "standard": {"status": "BLOCKED"}},
        skipped=False,
    ) is True
    assert client._safe_adversarial_admitted(
        {"smoke": {"status": "PASS"}, "standard": {"status": "FAIL"}},
        skipped=False,
    ) is True
    assert client._safe_adversarial_admitted(
        {"smoke": {"status": "PARTIAL"}, "standard": {"status": "PASS"}},
        skipped=False,
    ) is False
    assert client._safe_adversarial_admitted(
        {"smoke": {"status": "PASS"}},
        skipped=True,
    ) is False


def test_assurance_fault_requests_use_a_bounded_recovery_timeout(tmp_path, monkeypatch):
    script = Path("scripts/dev/lite/security_assurance.py").resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_security_assurance_fault_timeout", script)
    assert spec and spec.loader
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)

    observed = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return b'{"status":"PASS"}'

    def fake_urlopen(_request, timeout):
        observed["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)
    result = client._request(
        "POST",
        "/api/lite/harness/security-assurance/faults/opa_pause_probe_restore",
        {"confirm": True},
        authenticated=True,
        session_token="memory-only-session",
        timeout_seconds=150.0,
    )
    assert result["status"] == "PASS"
    assert observed["timeout"] == 150.0


def test_harness_client_forwards_bounded_bootstrap_session_ttl(tmp_path, monkeypatch):
    script = Path("scripts/dev/lite/harness.py").resolve()
    spec = importlib.util.spec_from_file_location("pocketlab_harness_client_bootstrap_ttl", script)
    assert spec and spec.loader
    client = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(client)

    class FakeKey:
        def sign(self, payload):
            assert payload == b"canonical-bootstrap-challenge"
            return b"s" * 64

        def public_key(self):
            return self

        def public_bytes(self, *_args):
            return b"p" * 32

    requests = []

    def fake_request(method, path, payload=None, headers=None):
        requests.append((method, path, payload, headers))
        if path.endswith("/grants"):
            return {"grant_id": "hbg-" + "a" * 32}
        if path.endswith("/bootstrap/challenge"):
            return {"challenge_id": "hbc-" + "b" * 32, "signing_payload": "canonical-bootstrap-challenge"}
        return {"session_token": "memory-only-bootstrap-token", "session": {"harness_session_id": "hs-test"}}

    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr(client, "_private_key", lambda _path: FakeKey())
    client.bootstrap_session(
        principal_id="ttl-bootstrap-runner",
        key_file=str(tmp_path / "machine.key"),
        ttl_seconds=60,
    )

    assert requests[2][2]["ttl_seconds"] == 60


def test_bootstrap_configuration_cannot_be_enabled_in_production(harness_runtime, monkeypatch):
    from api_fastapi.services import lite_harness

    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "production")
    monkeypatch.setenv("POCKETLAB_HARNESS_ENABLED", "0")
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_APPROVED", "1")
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID", "codex-assurance-bootstrap")
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT", "sha256:" + "a" * 64)
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PROFILE", "security-assurance-runner")
    with pytest.raises(lite_harness.HarnessConfigurationError) as error:
        lite_harness.validate_startup_configuration()
    assert error.value.reason_code == "harness_forbidden_in_production"


def test_normal_release_headers_never_activate_synthetic_authority(harness_runtime, monkeypatch):
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "production")
    monkeypatch.setenv("POCKETLAB_HARNESS_ENABLED", "0")
    monkeypatch.setenv("POCKETLAB_HARNESS_DESTRUCTIVE", "0")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "0")
    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    headers = {
        "X-Pocket-Lab-Test": "1",
        "X-Pocket-Lab-Qualification": "1",
        "X-Pocket-Lab-Harness-Session": "not-a-session",
        "X-Pocket-Lab-Harness-Profile": "qualification-owner",
        "X-Role": "Owner",
    }
    response = _client().get("/api/lite/status", headers=headers)
    assert response.status_code == 401
    assert response.json()["reason_code"] == "harness_disabled"


def test_capability_manifest_and_maintenance_deferral(harness_runtime):
    manifest = _client().get("/api/lite/harness/capabilities")
    assert manifest.status_code == 200
    payload = manifest.json()
    assert set(payload["profiles"]) == {
        "debug-observer", "test-runner", "security-qualifier", "recovery-qualifier",
        "release-qualifier", "maintenance-runner", "qualification-owner",
        "security-assurance-runner",
    }
    assert payload["profiles"]["recovery-qualifier"]["capabilities"] == [
        "recovery.read", "backup.create", "backup.verify", "restore.preview",
    ]
    assert payload["profiles"]["maintenance-runner"]["availability"] == "deferred"
    assert payload["production_maintenance"] == "deferred"


def test_registration_uses_public_key_and_preserves_human_isolation(harness_runtime):
    client = _client()
    private, public = _key()
    result = _register(client, private, public, extra={"allowed_profiles": ["recovery-qualifier"]})
    assert result["principal_id"] == "machine-runner"
    assert result["principal_type"] == "synthetic_machine"
    assert result["principal_class"] == "qualification"
    assert "public_key" not in result
    assert "private" not in json.dumps(result).casefold()

    from api_fastapi.db.connection import connection

    with connection() as conn:
        principal = conn.execute("SELECT * FROM synthetic_principals WHERE principal_id=?", ("machine-runner",)).fetchone()
        tables = (
            "human_identities", "enterprise_memberships", "human_credentials",
            "webauthn_credentials", "auth_sessions", "auth_session_assurance",
        )
        counts = {table: conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"] for table in tables}
        audit = [dict(row) for row in conn.execute("SELECT * FROM harness_audit_events ORDER BY event_id")]
    assert principal["public_key"] == _b64u(public)
    assert principal["public_key_fingerprint"] == "sha256:" + hashlib.sha256(public).hexdigest()
    assert principal["principal_type"] == "synthetic_machine"
    assert all(count == 0 for count in counts.values())
    assert audit[-1]["event_type"] == "principal_registered"
    assert audit[-1]["principal_id"] == "machine-runner"

    duplicate = _register(client, private, public, expected_status=409)
    assert duplicate["reason_code"] == "principal_exists"


@pytest.mark.parametrize(
    ("extra", "expected_status"),
    [
        ({"principal_id": "Bad ID"}, 422),
        ({"public_key": "not-a-valid-key"}, 422),
        ({"algorithm": "rsa"}, 422),
    ],
)
def test_registration_rejects_invalid_material(harness_runtime, extra, expected_status):
    client = _client()
    private, public = _key()
    result = _register(client, private, public, principal_id="invalid-runner", extra=extra, expected_status=expected_status)
    if expected_status == 422 and extra.get("algorithm") == "rsa":
        assert result["reason_code"] == "principal_algorithm_unsupported"


def test_registration_rejects_unknown_deferred_and_disabled_profiles(harness_runtime, monkeypatch):
    client = _client()
    private, public = _key()
    unknown = _register(client, private, public, principal_id="unknown-profile", profiles=("unknown-profile",), expected_status=403)
    assert unknown["reason_code"] == "harness_profile_unknown"

    private, public = _key()
    deferred = _register(client, private, public, principal_id="maintenance-profile", profiles=("maintenance-runner",), expected_status=403)
    assert deferred["reason_code"] == "maintenance_activation_deferred"

    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "0")
    private, public = _key()
    disabled = _register(client, private, public, principal_id="owner-profile", profiles=("qualification-owner",), expected_status=403)
    assert disabled["reason_code"] == "qualification_owner_profile_disabled"


def test_challenge_is_bounded_random_and_server_stores_only_hashes(harness_runtime):
    client = _client()
    private, public = _key()
    _register(client, private, public)
    challenge = _challenge(client)
    nonce = _decode_b64u(challenge["nonce"])
    assert len(nonce) == 32
    issued = datetime.fromisoformat(challenge["issued_at"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(challenge["expires_at"].replace("Z", "+00:00"))
    assert timedelta(seconds=30) <= expires - issued <= timedelta(seconds=300)

    from api_fastapi.db.connection import connection

    with connection() as conn:
        row = conn.execute("SELECT nonce_hash,signing_payload_hash FROM harness_challenges WHERE challenge_id=?", (challenge["challenge_id"],)).fetchone()
    assert row["nonce_hash"] == hashlib.sha256(challenge["nonce"].encode()).hexdigest()
    assert row["signing_payload_hash"] == hashlib.sha256(challenge["signing_payload"].encode()).hexdigest()
    assert challenge["nonce"] not in row["nonce_hash"]
    assert challenge["signing_payload"] not in row["signing_payload_hash"]


def test_signed_session_replay_and_secret_redaction(harness_runtime):
    client = _client()
    private, public = _key()
    _register(client, private, public)
    session, challenge = _start_session(client, private)
    token = session["session_token"]
    session_data = session["session"]
    assert session_data["status"] == "active"
    assert session_data["destructive_allowed"] is False

    from api_fastapi.db.connection import connection

    with connection() as conn:
        stored = conn.execute("SELECT token_hash FROM harness_sessions WHERE harness_session_id=?", (session_data["harness_session_id"],)).fetchone()
        challenge_row = conn.execute("SELECT consumed_at FROM harness_challenges WHERE challenge_id=?", (challenge["challenge_id"],)).fetchone()
        events = [dict(row) for row in conn.execute("SELECT * FROM harness_audit_events ORDER BY event_id")]
    assert stored["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert stored["token_hash"] != token
    assert challenge_row["consumed_at"] is not None
    serialized = json.dumps(events)
    assert token not in serialized
    assert challenge["nonce"] not in serialized
    assert challenge["signing_payload"] not in serialized
    assert {event["event_type"] for event in events} >= {"principal_registered", "challenge_issued", "authentication_succeeded", "session_created"}

    replay = _session_request(client, challenge, private)
    assert replay.status_code == 401
    assert replay.json()["reason_code"] == "challenge_replayed"


def test_wrong_signature_does_not_consume_challenge_until_limit(harness_runtime):
    client = _client()
    private, public = _key()
    wrong_private, _ = _key()
    _register(client, private, public)
    challenge = _challenge(client)
    rejected = _session_request(client, challenge, wrong_private)
    assert rejected.status_code == 401
    assert rejected.json()["reason_code"] == "signature_invalid"

    from api_fastapi.db.connection import connection

    with connection() as conn:
        row = conn.execute(
            "SELECT failed_attempts,consumed_at FROM harness_challenges WHERE challenge_id=?",
            (challenge["challenge_id"],),
        ).fetchone()
    assert row["failed_attempts"] == 1
    assert row["consumed_at"] is None

    accepted = _session_request(client, challenge, private)
    assert accepted.status_code == 201, accepted.text


def test_modified_challenge_context_and_request_claims_fail_closed(harness_runtime):
    client = _client()
    private, public = _key()
    _register(client, private, public)
    challenge = _challenge(client)

    wrong_principal = _session_request(client, challenge, private, principal_id="other-runner")
    assert wrong_principal.status_code == 401
    assert wrong_principal.json()["reason_code"] == "challenge_principal_mismatch"

    wrong_profile = _session_request(client, challenge, private, profile="debug-observer")
    assert wrong_profile.status_code == 401
    assert wrong_profile.json()["reason_code"] == "challenge_profile_mismatch"

    modified = json.loads(challenge["signing_payload"])
    modified["purpose"] = "security.read"
    modified_payload = _canonical(modified)
    altered = _session_request(client, challenge, private, signing_payload=modified_payload)
    assert altered.status_code == 401
    assert altered.json()["reason_code"] == "challenge_context_mismatch"


def test_expired_challenge_is_rejected_without_becoming_a_valid_session(harness_runtime):
    client = _client()
    private, public = _key()
    _register(client, private, public)
    challenge = _challenge(client)

    from api_fastapi.db.connection import connection

    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    with connection() as conn:
        conn.execute("UPDATE harness_challenges SET expires_at=? WHERE challenge_id=?", (expired, challenge["challenge_id"]))

    rejected = _session_request(client, challenge, private)
    assert rejected.status_code == 401
    assert rejected.json()["reason_code"] == "challenge_expired"


def test_authenticated_context_is_synthetic_and_caller_role_fields_are_rejected(harness_runtime):
    client = _client()
    private, public = _key()
    _register(client, private, public)
    session, _challenge_data = _start_session(client, private)
    token = session["session_token"]

    from api_fastapi import deps
    from api_fastapi.services import lite_policy_opa

    context = deps.resolve_auth_context(_request({HARNESS_HEADER: token}))
    assert context["actor"]["type"] == "synthetic_machine"
    assert context["authorization"]["role"] is None
    assert context["authorization"]["membership_active"] is False
    assert context["authorization"]["identity_class"] == "synthetic_machine"
    assert context["harness"]["principal_id"] == "machine-runner"
    assert context["harness"]["target_scope"] == TARGET_SCOPE

    opa_input = lite_policy_opa.build_authorization_input(
        auth_context=context,
        action_id="backup.verify",
        target_type="recovery",
        target_id="backup-1",
        target_revision="revision-1",
        target={"status": "verified"},
    )
    assert opa_input["actor"]["type"] == "synthetic_machine"
    assert opa_input["session"]["auth_method"] == "harness_session"
    assert opa_input["harness"]["capabilities"] == [
        "recovery.read", "backup.create", "backup.verify", "restore.preview",
    ]
    assert opa_input["target"]["scope"] == TARGET_SCOPE

    role_claim = client.get("/api/lite/status", headers={HARNESS_HEADER: token, "X-Role": "Owner"})
    assert role_claim.status_code == 403
    assert role_claim.json()["reason_code"] == "harness_role_field_rejected"

    proof_claim = client.get(
        "/api/lite/status",
        headers={HARNESS_HEADER: token, "X-Pocket-Lab-Harness-Profile": "qualification-owner"},
    )
    assert proof_claim.status_code == 403
    assert proof_claim.json()["reason_code"] == "harness_proof_fields_rejected"

    forwarded = client.get(
        "/api/lite/status",
        headers={HARNESS_HEADER: token, "X-Forwarded-For": "127.0.0.1"},
    )
    assert forwarded.status_code == 401
    assert forwarded.json()["reason_code"] == "harness_transport_rejected"


def test_capability_resolution_denies_escalation_and_secondary_targets(harness_runtime):
    client = _client()
    private, public = _key()
    _register(client, private, public)
    session, _ = _start_session(client, private)
    token = session["session_token"]

    from api_fastapi import deps
    from api_fastapi.services import lite_harness

    context = deps.resolve_auth_context(_request({HARNESS_HEADER: token}))
    lite_harness.enforce_capability(
        context,
        action_id="backup.create",
        target_type="recovery",
        target_id="local-backup",
        operation_id="op-safe",
    )
    for action_id, target_type, target_id, expected in (
        ("restore.apply", "recovery", "local-backup", "harness_capability_denied"),
        ("not.registered", "recovery", "local-backup", "harness_action_unregistered"),
        ("backup.create", "device", "secondary-phone", "harness_target_mismatch"),
    ):
        with pytest.raises(lite_harness.HarnessError) as error:
            lite_harness.enforce_capability(
                context,
                action_id=action_id,
                target_type=target_type,
                target_id=target_id,
                operation_id="op-denied",
            )
        assert error.value.reason_code == expected

    debug_private, debug_public = _key()
    _register(client, debug_private, debug_public, principal_id="debug-runner", profiles=("debug-observer",))
    debug_session, _ = _start_session(client, debug_private, principal_id="debug-runner", profile="debug-observer", purpose="diagnostics.read")
    debug_context = deps.resolve_auth_context(_request({HARNESS_HEADER: debug_session["session_token"]}))
    with pytest.raises(lite_harness.HarnessError) as error:
        lite_harness.enforce_capability(
            debug_context,
            action_id="backup.create",
            target_type="recovery",
            target_id="local-backup",
        )
    assert error.value.reason_code == "harness_capability_denied"


def test_security_qualifier_is_enforced_at_lite_security_routes(harness_runtime, monkeypatch):
    client = _client()
    private, public = _key()
    _register(
        client,
        private,
        public,
        principal_id="security-runner",
        profiles=("security-qualifier",),
    )
    session, _ = _start_session(
        client,
        private,
        principal_id="security-runner",
        profile="security-qualifier",
        purpose="security.scan.quick",
    )
    security_headers = {HARNESS_HEADER: session["session_token"]}

    from api_fastapi import deps
    from api_fastapi.services import lite_harness

    context = deps.resolve_auth_context(_request(security_headers))
    for action_id in (
        "security.read",
        "security.scan.quick",
        "security.scan.full",
        "security.scan.app",
        "security.evidence.read",
    ):
        lite_harness.enforce_capability(
            context,
            action_id=action_id,
            target_type="security",
            target_id="qualification-target",
        )

    summary = client.get("/api/lite/security/summary", headers=security_headers)
    assert summary.status_code == 200, summary.text

    from api_fastapi.services.nats_bus import BUS

    monkeypatch.setattr(BUS, "connected", True)
    monkeypatch.setattr(BUS, "js", object())

    async def publish_json(*_args, **_kwargs):
        return None

    monkeypatch.setattr(BUS, "publish_json", publish_json)
    queued = client.post(
        "/api/lite/security/check",
        headers=security_headers,
        json={"profile": "quick"},
    )
    assert queued.status_code == 202, queued.text

    debug_private, debug_public = _key()
    _register(
        client,
        debug_private,
        debug_public,
        principal_id="debug-security-runner",
        profiles=("debug-observer",),
    )
    debug_session, _ = _start_session(
        client,
        debug_private,
        principal_id="debug-security-runner",
        profile="debug-observer",
        purpose="security.scan.quick",
    )
    denied = client.post(
        "/api/lite/security/check",
        headers={HARNESS_HEADER: debug_session["session_token"]},
        json={"profile": "quick"},
    )
    assert denied.status_code == 403, denied.text
    assert denied.json().get("reason_code") == "harness_capability_denied", denied.text


def test_qualification_owner_is_an_explicit_profile_with_no_membership(harness_runtime, monkeypatch):
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "1")
    client = _client()
    private, public = _key()
    _register(client, private, public, principal_id="owner-runner", profiles=("qualification-owner",))
    session, _ = _start_session(client, private, principal_id="owner-runner", profile="qualification-owner", purpose="policy.rules.activate")
    token = session["session_token"]

    from api_fastapi import deps
    from api_fastapi.services import lite_enterprise_governance

    context = deps.resolve_auth_context(_request({HARNESS_HEADER: token}))
    assert deps.is_qualification_owner_context(context) is True
    assert context["actor"]["type"] == "qualification"
    assert context["authorization"] == {
        "role": "Owner",
        "owner_authority": True,
        "membership_active": False,
        "identity_class": "synthetic_machine",
        "enterprise_enabled": False,
        "authorization_version": 1,
        "principal_class": "qualification",
    }
    assert lite_enterprise_governance.require_root_owner(context)[1] == "owner-runner"

    access = client.get("/api/lite/enterprise/access", headers={HARNESS_HEADER: token})
    assert access.status_code == 200, access.text
    assert access.json()["current_role"] == "Owner"
    assert access.json()["principal"] == {
        "type": "qualification",
        "synthetic": True,
        "auth_method": "harness_session",
    }


def test_destructive_gate_and_single_destructive_session(harness_runtime, monkeypatch):
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "1")
    client = _client()
    private, public = _key()
    _register(client, private, public, principal_id="destructive-runner", profiles=("qualification-owner",))
    first, _ = _start_session(client, private, principal_id="destructive-runner", profile="qualification-owner", purpose="recovery.restore")

    from api_fastapi import deps
    from api_fastapi.services import lite_harness

    first_context = deps.resolve_auth_context(_request({HARNESS_HEADER: first["session_token"]}))
    with pytest.raises(lite_harness.HarnessError) as error:
        lite_harness.enforce_capability(
            first_context,
            action_id="restore.apply",
            target_type="recovery",
            target_id="backup-1",
        )
    assert error.value.reason_code == "destructive_harness_disabled"

    monkeypatch.setenv("POCKETLAB_HARNESS_DESTRUCTIVE", "1")
    second, _ = _start_session(client, private, principal_id="destructive-runner", profile="qualification-owner", purpose="recovery.restore")
    assert second["session"]["destructive_allowed"] is True
    second_context = deps.resolve_auth_context(_request({HARNESS_HEADER: second["session_token"]}))
    lite_harness.enforce_capability(
        second_context,
        action_id="restore.apply",
        target_type="recovery",
        target_id="backup-1",
        operation_id="op-destructive",
    )

    third_challenge = _challenge(client, principal_id="destructive-runner", profile="qualification-owner", purpose="recovery.restore")
    third = _session_request(client, third_challenge, private)
    assert third.status_code == 429
    assert third.json()["reason_code"] == "harness_destructive_session_limit"

    from api_fastapi.db.connection import connection

    with connection() as conn:
        audit = [dict(row) for row in conn.execute("SELECT * FROM harness_audit_events ORDER BY event_id")]
    assert any(event["reason_code"] == "destructive_admitted" and event["result"] == "accepted" for event in audit)
    assert any(event["reason_code"] == "destructive_harness_disabled" for event in audit)


def test_session_expiry_revocation_and_principal_revocation_are_immediate(harness_runtime):
    client = _client()
    private, public = _key()
    _register(client, private, public)
    expired_session, _ = _start_session(client, private)

    from api_fastapi.db.connection import connection

    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    with connection() as conn:
        conn.execute("UPDATE harness_sessions SET expires_at=? WHERE harness_session_id=?", (expired, expired_session["session"]["harness_session_id"]))
    expired_response = client.get("/api/lite/status", headers={HARNESS_HEADER: expired_session["session_token"]})
    assert expired_response.status_code == 401
    assert expired_response.json()["reason_code"] == "harness_session_expired"

    revoked_session, _ = _start_session(client, private)
    stop = client.delete(
        f"/api/lite/harness/session/{revoked_session['session']['harness_session_id']}",
        headers={HARNESS_HEADER: revoked_session["session_token"]},
    )
    assert stop.status_code == 200
    revoked_response = client.get("/api/lite/status", headers={HARNESS_HEADER: revoked_session["session_token"]})
    assert revoked_response.status_code == 401
    assert revoked_response.json()["reason_code"] == "harness_session_revoked"

    principal_session, _ = _start_session(client, private)
    principal_revoke = client.post(
        "/api/lite/harness/principals/machine-runner/revoke",
        headers=PROVISIONING_HEADERS,
    )
    assert principal_revoke.status_code == 200
    principal_response = client.get("/api/lite/status", headers={HARNESS_HEADER: principal_session["session_token"]})
    assert principal_response.status_code == 401
    assert principal_response.json()["reason_code"] == "harness_session_revoked"
    after_revoke = _challenge(client, expected_status=403)
    assert after_revoke["reason_code"] == "principal_revoked"

    with connection() as conn:
        event_types = {row["event_type"] for row in conn.execute("SELECT event_type FROM harness_audit_events")}
    assert {"session_expired", "session_revoked", "principal_revoked"}.issubset(event_types)


def test_expired_and_disabled_principals_cannot_issue_challenges(harness_runtime):
    client = _client()
    private, public = _key()
    _register(client, private, public, principal_id="expired-runner")

    from api_fastapi.db.connection import connection

    expired = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
    with connection() as conn:
        conn.execute("UPDATE synthetic_principals SET expires_at=? WHERE principal_id=?", (expired, "expired-runner"))
    expired_response = _challenge(client, principal_id="expired-runner", expected_status=403)
    assert expired_response["reason_code"] == "principal_expired"

    private, public = _key()
    _register(client, private, public, principal_id="disabled-runner")
    with connection() as conn:
        conn.execute("UPDATE synthetic_principals SET enabled=0 WHERE principal_id=?", ("disabled-runner",))
    disabled_response = _challenge(client, principal_id="disabled-runner", expected_status=403)
    assert disabled_response["reason_code"] == "principal_revoked"


def test_cli_generates_restrictive_key_without_printing_private_material(harness_runtime, tmp_path):
    with tempfile.TemporaryDirectory(prefix="pocketlab-harness-") as temporary:
        key_path = Path(temporary) / "machine.key"
        result = subprocess.run(
            [sys.executable, "scripts/dev/lite/harness.py", "keygen", "--key-file", str(key_path)],
            check=False,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        assert result.returncode == 0, result.stderr
        output = json.loads(result.stdout)
        assert output["algorithm"] == "ed25519"
        assert output["private_key_returned"] is False
        assert output["private_key_mode"] == "0o600"
        assert len(key_path.read_bytes()) == 32
        assert "BEGIN" not in result.stdout
        assert output["private_key_path"].endswith("machine.key")
        assert output["public_key_path"].endswith("machine.key.pub")
        assert output["public_key_mode"] == "0o644"


def test_cli_refuses_key_material_inside_repository(harness_runtime):
    result = subprocess.run(
        [sys.executable, "scripts/dev/lite/harness.py", "keygen", "--key-file", "scripts/dev/lite/unsafe.key"],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 2
    assert "outside the repository" in result.stderr


def test_qualification_launcher_owns_lite_profile(harness_runtime):
    result = subprocess.run(
        ["bash", "scripts/dev/lite/start-qualification.sh", "--profile", "full"],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 2
    assert "owns the --profile lite selection" in result.stderr


def test_no_frontend_projection_or_harness_mcp_extension(harness_runtime):
    forbidden = (
        "/api/lite/harness",
        "POCKETLAB_HARNESS",
        "qualification-owner",
        "maintenance-runner",
        "synthetic machine",
    )
    for root_name in ("src", "public"):
        root = Path(root_name)
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".woff", ".woff2"}:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore").casefold()
            assert not any(term.casefold() in content for term in forbidden), path

    mcp_root = Path("tools/mcp/pocketlab_dev")
    for path in mcp_root.rglob("*.py"):
        content = path.read_text(encoding="utf-8", errors="ignore").casefold()
        assert "/api/lite/harness" not in content
        assert "harness_session_start" not in content
