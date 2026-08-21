from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _cbor_head(major: int, value: int) -> bytes:
    if value < 24:
        return bytes([(major << 5) | value])
    if value < 256:
        return bytes([(major << 5) | 24, value])
    if value < 65536:
        return bytes([(major << 5) | 25]) + value.to_bytes(2, "big")
    return bytes([(major << 5) | 26]) + value.to_bytes(4, "big")


def _cbor(value) -> bytes:
    if value is None:
        return b"\xf6"
    if isinstance(value, bool):
        return b"\xf5" if value else b"\xf4"
    if isinstance(value, int):
        return _cbor_head(0, value) if value >= 0 else _cbor_head(1, -1 - value)
    if isinstance(value, bytes):
        return _cbor_head(2, len(value)) + value
    if isinstance(value, str):
        raw = value.encode()
        return _cbor_head(3, len(raw)) + raw
    if isinstance(value, list):
        return _cbor_head(4, len(value)) + b"".join(_cbor(item) for item in value)
    if isinstance(value, dict):
        return _cbor_head(5, len(value)) + b"".join(_cbor(key) + _cbor(item) for key, item in value.items())
    raise TypeError(type(value))


def _der_int(value: int) -> bytes:
    raw = value.to_bytes((value.bit_length() + 7) // 8 or 1, "big")
    if raw[0] & 0x80:
        raw = b"\x00" + raw
    return b"\x02" + bytes([len(raw)]) + raw


def _sign(webauthn, private_key: int, message: bytes, nonce: int) -> bytes:
    z = int.from_bytes(hashlib.sha256(message).digest(), "big")
    point = webauthn._point_mul(nonce, webauthn.P256_G)
    r = point[0] % webauthn.P256_N
    s = (pow(nonce, -1, webauthn.P256_N) * (z + r * private_key)) % webauthn.P256_N
    body = _der_int(r) + _der_int(s)
    return b"\x30" + bytes([len(body)]) + body


def _client_data(kind: str, challenge: str, origin: str) -> tuple[bytes, str]:
    raw = json.dumps({"type": kind, "challenge": challenge, "origin": origin, "crossOrigin": False}, separators=(",", ":")).encode()
    return raw, _b64(raw)


def _registration_payload(webauthn, *, challenge: str, origin: str, rp_id: str, private_key: int = 7, credential_id: bytes = b"credential-p1"):
    public = webauthn._point_mul(private_key, webauthn.P256_G)
    x = public[0].to_bytes(32, "big")
    y = public[1].to_bytes(32, "big")
    cose = {1: 2, 3: -7, -1: 1, -2: x, -3: y}
    auth_data = hashlib.sha256(rp_id.encode()).digest() + bytes([0x45]) + (0).to_bytes(4, "big") + (b"\x00" * 16) + len(credential_id).to_bytes(2, "big") + credential_id + _cbor(cose)
    attestation = _cbor({"fmt": "none", "attStmt": {}, "authData": auth_data})
    _, client = _client_data("webauthn.create", challenge, origin)
    return {
        "id": _b64(credential_id), "rawId": _b64(credential_id), "type": "public-key",
        "clientDataJSON": client, "attestationObject": _b64(attestation),
        "transports": ["internal"], "authenticatorAttachment": "platform",
    }, private_key, credential_id


def _assertion_payload(webauthn, *, challenge: str, origin: str, rp_id: str, private_key: int, credential_id: bytes, counter: int = 1, nonce: int = 11):
    auth_data = hashlib.sha256(rp_id.encode()).digest() + bytes([0x05]) + counter.to_bytes(4, "big")
    client_raw, client = _client_data("webauthn.get", challenge, origin)
    signature = _sign(webauthn, private_key, auth_data + hashlib.sha256(client_raw).digest(), nonce)
    return {
        "id": _b64(credential_id), "rawId": _b64(credential_id), "type": "public-key",
        "clientDataJSON": client, "authenticatorData": _b64(auth_data), "signature": _b64(signature),
    }


@pytest.fixture()
def p1_runtime(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_IDENTITY_COOKIE_SECURE", "0")
    monkeypatch.setenv("POCKETLAB_IDENTITY_SETUP_TOKEN", "one-time-setup-token")
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()
    return state


def test_owner_claim_is_hash_only_single_use_and_passkey_first(p1_runtime):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_webauthn

    issued = lite_webauthn.issue_owner_claim(origin="http://localhost:8443", ttl_seconds=120)
    with connection() as conn:
        stored = conn.execute("SELECT claim_hash,origin,rp_id FROM owner_claims WHERE claim_id=?", (issued["claim_id"],)).fetchone()
    assert issued["claim"] not in stored["claim_hash"]
    assert stored["origin"] == "http://localhost:8443"
    assert stored["rp_id"] == "localhost"

    consumed = lite_webauthn.consume_owner_claim(raw_claim=issued["claim"], origin="http://localhost:8443")
    with pytest.raises(lite_webauthn.WebAuthnError) as replay:
        lite_webauthn.consume_owner_claim(raw_claim=issued["claim"], origin="http://localhost:8443")
    assert replay.value.reason_code == "owner_claim_reused"

    options = lite_webauthn.owner_claim_registration_options(authority=consumed["authority"], origin="http://localhost:8443")
    credential, _, _ = _registration_payload(
        lite_webauthn, challenge=options["publicKey"]["challenge"], origin="http://localhost:8443", rp_id="localhost"
    )
    completed = lite_webauthn.complete_owner_claim_registration(
        authority=consumed["authority"], origin="http://localhost:8443", challenge=options["publicKey"]["challenge"],
        payload=credential, username="owner", display_name="Pocket Lab Owner", friendly_name="Phone passkey",
    )
    assert completed["session"]["auth_method"] == "passkey"
    assert len(completed["recovery_codes"]) == 10
    with connection() as conn:
        password = conn.execute("SELECT 1 FROM human_credentials WHERE human_id=? AND kind='password'", (completed["human_id"],)).fetchone()
        passkey = conn.execute("SELECT friendly_name,public_key_x FROM webauthn_credentials WHERE human_id=?", (completed["human_id"],)).fetchone()
        claim = conn.execute("SELECT completed_at,authority_hash FROM owner_claims WHERE claim_id=?", (issued["claim_id"],)).fetchone()
    assert password is None
    assert passkey["friendly_name"] == "Phone passkey"
    assert claim["completed_at"]
    assert claim["authority_hash"] is None


def test_owner_claim_wrong_origin_and_existing_owner_fail_closed(p1_runtime):
    from api_fastapi.services import lite_identity_auth, lite_webauthn

    issued = lite_webauthn.issue_owner_claim(origin="https://pocketlab.example")
    with pytest.raises(lite_webauthn.WebAuthnError) as wrong:
        lite_webauthn.consume_owner_claim(raw_claim=issued["claim"], origin="https://other.example")
    assert wrong.value.reason_code == "owner_claim_origin_mismatch"

    lite_identity_auth.setup_owner(username="owner", display_name="Owner", password="correct horse battery staple", setup_token="one-time-setup-token")
    with pytest.raises(lite_webauthn.WebAuthnError) as existing:
        lite_webauthn.issue_owner_claim(origin="https://pocketlab.example")
    assert existing.value.reason_code == "identity_owner_exists"


def test_passkey_login_replay_counter_and_step_up_are_server_recorded(p1_runtime):
    from api_fastapi.services import lite_identity_auth, lite_webauthn

    issued = lite_webauthn.issue_owner_claim(origin="http://localhost")
    consumed = lite_webauthn.consume_owner_claim(raw_claim=issued["claim"], origin="http://localhost")
    reg = lite_webauthn.owner_claim_registration_options(authority=consumed["authority"], origin="http://localhost")
    credential, private_key, raw_id = _registration_payload(lite_webauthn, challenge=reg["publicKey"]["challenge"], origin="http://localhost", rp_id="localhost")
    completed = lite_webauthn.complete_owner_claim_registration(authority=consumed["authority"], origin="http://localhost", challenge=reg["publicKey"]["challenge"], payload=credential, username="owner", display_name="Owner", friendly_name="Primary")

    login = lite_webauthn.login_options(origin="http://localhost")
    assertion = _assertion_payload(lite_webauthn, challenge=login["publicKey"]["challenge"], origin="http://localhost", rp_id="localhost", private_key=private_key, credential_id=raw_id, counter=1)
    signed = lite_webauthn.complete_login(origin="http://localhost", challenge=login["publicKey"]["challenge"], payload=assertion)
    assert signed["auth_method"] == "passkey"
    with pytest.raises(lite_webauthn.WebAuthnError) as replay:
        lite_webauthn.complete_login(origin="http://localhost", challenge=login["publicKey"]["challenge"], payload=assertion)
    assert replay.value.reason_code == "webauthn_challenge_replayed"

    auth = lite_identity_auth.authenticate_session_token(signed["session_token"])
    step = lite_webauthn.step_up_options(human_id=completed["human_id"], session_id=signed["session_id"], origin="http://localhost", purpose="identity.passkey.revoke")
    step_assertion = _assertion_payload(lite_webauthn, challenge=step["publicKey"]["challenge"], origin="http://localhost", rp_id="localhost", private_key=private_key, credential_id=raw_id, counter=2, nonce=13)
    elevated = lite_webauthn.complete_step_up(human_id=completed["human_id"], session_id=signed["session_id"], origin="http://localhost", purpose="identity.passkey.revoke", challenge=step["publicKey"]["challenge"], payload=step_assertion)
    assert elevated["purpose"] == "identity.passkey.revoke"
    refreshed = lite_identity_auth.authenticate_session_token(signed["session_token"])
    assert refreshed["session"]["assurance"][0]["purpose"] == "identity.passkey.revoke"
    assert not (auth["session"].get("assurance") or [])


def test_policy_uses_only_server_assurance_and_nonloopback_fails_closed(p1_runtime, monkeypatch):
    from api_fastapi.services import lite_policy_opa

    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setattr(lite_policy_opa, "OPA_BASE_URL", "http://192.0.2.44:8181")
    with pytest.raises(lite_policy_opa.PolicyDecisionError) as blocked:
        lite_policy_opa.evaluate_authorization(
            auth_context={"actor": {"identity_id": "human-test", "type": "human", "display_name": "Owner"}, "session": {"authenticated": True, "auth_method": "passkey", "assurance": []}},
            action_id="identity.passkey.revoke", target_type="passkey", target_id="cred", target_revision="r1",
            target={"requested_by_owner": True, "browser_assurance": True}, request_context={"assurance": "forged"}, correlation_id="corr-nonloopback",
        )
    assert blocked.value.reason_code == "policy_endpoint_not_loopback"
    assert blocked.value.decision["allow"] is False

    input_doc = lite_policy_opa.build_authorization_input(
        auth_context={"actor": {"identity_id": "human-test", "type": "human", "display_name": "Owner"}, "session": {"authenticated": True, "auth_method": "passkey", "assurance": []}},
        action_id="identity.passkey.revoke", target_type="passkey", target_id="cred", target_revision="r1",
        target={"browser_assurance": True}, request_context={"assurance": "forged"},
    )
    assert input_doc["session"]["assurance"] == []
    assert input_doc["target"]["state"].get("browser_assurance") is True  # bounded target metadata is visible to policy but not trusted as session assurance


def test_policy_decision_detail_is_bounded_and_templates_are_server_owned(p1_runtime, monkeypatch):
    from api_fastapi.services import lite_policy_opa

    monkeypatch.setattr(lite_policy_opa, "OPA_BASE_URL", "http://127.0.0.1:8181")
    monkeypatch.setattr(lite_policy_opa, "_http_json", lambda *args, **kwargs: (200, {"result": {"allow": False, "constraints": ["passkey_step_up"], "reason_code": "passkey_step_up_required", "policy_revision": "p1-test"}}))
    with pytest.raises(lite_policy_opa.PolicyDecisionError) as blocked:
        lite_policy_opa.evaluate_authorization(
            auth_context={"actor": {"identity_id": "human-test", "type": "human", "display_name": "Owner"}, "session": {"authenticated": True, "auth_method": "password", "assurance": []}},
            action_id="identity.passkey.revoke", target_type="passkey", target_id="cred-test", target_revision="rev-test", target={}, correlation_id="corr-stepup",
        )
    assert blocked.value.reason_code == "passkey_step_up_required"
    assert blocked.value.status_code == 428
    detail = lite_policy_opa.decision_detail(blocked.value.decision["decision_id"])
    assert detail["constraints"] == ["passkey_step_up"]
    assert detail["raw_input_exposed"] is False
    serialized = json.dumps(detail).casefold()
    assert "password" not in serialized
    assert "authenticator" not in serialized
    templates = lite_policy_opa.policy_templates()
    assert any(item["id"] == "passkey_step_up" and item["status"] == "active" for item in templates)


def test_identity_rules_p1_source_contracts():
    identity = Path("src/lite/LiteIdentity.jsx").read_text()
    app = Path("src/main.jsx").read_text()
    owner_claim = Path("src/lib/liteOwnerClaim.js").read_text()
    webauthn = Path("src/lib/liteWebAuthn.js").read_text()
    rules = Path("src/lite/LiteRules.jsx").read_text()
    api = Path("src/lib/liteApi.js").read_text()
    rego = Path("security/policies/opa/pocketlab/pocketlab.rego").read_text()

    assert "captureOwnerClaimFromUrl" in app
    assert "replaceState" in owner_claim
    assert "localStorage" not in owner_claim
    assert "sessionStorage" not in owner_claim
    assert "navigator.credentials.create" in webauthn
    assert "navigator.credentials.get" in webauthn
    assert "Sign In with Passkey" in identity
    assert "Advanced Setup" in identity
    assert "passkeyStepUpOptions" in api
    assert "policyDecision" in api
    assert "Safe templates" in rules
    assert "Raw policy input is not exposed" in rules
    assert 'input.action.id == "identity.passkey.revoke"' in rego
    assert "passkey_step_up_required" in rego
