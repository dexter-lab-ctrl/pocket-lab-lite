from __future__ import annotations

import base64
import hashlib
import importlib.util
import uuid
from pathlib import Path

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts/dev/lite/run-photo-backup-candidate-qualification.py"


def _module():
    spec = importlib.util.spec_from_file_location("photo_backup_candidate_qualification", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_isolated_environment_removes_production_credentials_and_uses_private_roots(tmp_path, monkeypatch):
    candidate = _module()
    monkeypatch.setenv("POCKETLAB_NATS_PASSWORD", "must-not-leak")
    monkeypatch.setenv("POCKETLAB_NATS_CREDENTIALS_FILE", "/production/credentials")
    monkeypatch.setenv("POCKETLAB_STATE_DIR", "/production/state")
    env = candidate._isolated_environment(tmp_path, "abcdef123456", 39191)

    candidate._assert_isolated_environment(env, tmp_path, "abcdef123456")
    assert env["POCKETLAB_TEST_AUTH_BYPASS"] == "0"
    assert env["POCKETLAB_HARNESS_DESTRUCTIVE"] == "0"
    assert env["POCKETLAB_NODE_ID"] == "qualification-photo-backup-abcdef123456"
    assert env["POCKETLAB_STATE_DIR"].startswith(str(tmp_path))
    assert "POCKETLAB_NATS_PASSWORD" not in env
    assert "POCKETLAB_NATS_CREDENTIALS_FILE" not in env
    assert "POCKETLAB_QUALIFICATION_RUN_ID" not in env
    assert "POCKETLAB_QUALIFICATION_CANDIDATE_SHA" not in env
    assert env["PM2_HOME"].startswith(str(tmp_path))


def test_manifest_explicitly_separates_candidate_and_device_gates(tmp_path):
    candidate = _module()
    env = candidate._isolated_environment(tmp_path, "123456abcdef", 39192)
    manifest = candidate.qualification_manifest("a" * 40, "123456abcdef", env)

    assert manifest["candidate_sha"] == "a" * 40
    assert manifest["source_tree"] == "temporary_git_worktree"
    assert manifest["pm2"] == "not_started"
    assert manifest["caddy"] == "not_started"
    assert manifest["nats"] == "not_started; no subjects published"
    assert manifest["phones_contacted"] is False


def test_runner_does_not_accept_short_or_zero_candidate_shas():
    candidate = _module()
    for value in ("not-a-sha", "a" * 39, "0" * 40):
        try:
            candidate._validate_sha(value)
        except candidate.QualificationError:
            pass
        else:
            raise AssertionError(f"accepted unsafe candidate SHA: {value}")


def test_harness_backed_photo_backup_api_contract(tmp_path, monkeypatch):
    """Exercise the candidate API with a real non-Owner harness proof."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir, load_fastapi_app

    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS
    from api_fastapi.routers import fleet

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_HARNESS_ENABLED", "1")
    monkeypatch.setenv("POCKETLAB_HARNESS_DESTRUCTIVE", "0")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "0")
    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_API_TOKEN", "")
    monkeypatch.setenv("POCKETLAB_ALLOW_LOCAL_WRITE", "0")

    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    monkeypatch.setattr(deps.core, "SETTINGS", deps.core.Settings(state_dir=state))
    apply_migrations()

    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    public_key = base64.urlsafe_b64encode(public).decode("ascii").rstrip("=")
    principal_id = "photo-backup-qual-" + uuid.uuid4().hex[:12]
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_APPROVED", "1")
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID", principal_id)
    monkeypatch.setenv(
        "POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT",
        "sha256:" + hashlib.sha256(public).hexdigest(),
    )
    monkeypatch.setenv("POCKETLAB_HARNESS_BOOTSTRAP_PROFILE", "security-assurance-runner")

    api = TestClient(load_fastapi_app(), client=("127.0.0.1", 40123))
    grant_response = api.post(
        "/api/lite/harness/bootstrap/grants",
        json={"principal_id": principal_id, "public_key": public_key},
    )
    assert grant_response.status_code == 201, grant_response.text
    grant = grant_response.json()
    challenge_response = api.post(
        "/api/lite/harness/bootstrap/challenge",
        json={"grant_id": grant["grant_id"]},
    )
    assert challenge_response.status_code == 200, challenge_response.text
    challenge = challenge_response.json()
    signature = base64.urlsafe_b64encode(
        private.sign(challenge["signing_payload"].encode("utf-8"))
    ).decode("ascii").rstrip("=")
    session_response = api.post(
        "/api/lite/harness/bootstrap/complete",
        json={
            "challenge_id": challenge["challenge_id"],
            "grant_id": grant["grant_id"],
            "principal_id": principal_id,
            "public_key": public_key,
            "signature": signature,
        },
    )
    assert session_response.status_code == 201, session_response.text
    session = session_response.json()
    assert session["principal"]["default_profile"] == "security-assurance-runner"
    assert session["session"]["destructive_allowed"] is False
    token = session["session_token"]
    headers = {"X-Pocket-Lab-Harness-Session": token}

    monkeypatch.setattr(
        fleet.lite_photo_backup,
        "fleet_status",
        lambda _request=None: {
            "status": "ok",
            "provider": "photoprism_webdav",
            "devices": [],
            "sanitized": True,
        },
    )
    monkeypatch.setattr(
        fleet.lite_photo_backup,
        "status",
        lambda node_id, _request=None: {
            "status": "ready",
            "ready": True,
            "node_id": node_id,
            "provider": "photoprism_webdav",
            "sanitized": True,
        },
    )
    monkeypatch.setattr(
        fleet.lite_photo_backup,
        "make_start_command",
        lambda *_args, **_kwargs: {
            "command_id": "photo-qualification",
            "backup_id": "photo-qualification",
            "node_id": "storage-phone",
            "collections": ["camera"],
            "provider": "photoprism_webdav",
        },
    )

    async def fake_submit(*_args, **_kwargs):
        return {"status": "queued"}

    monkeypatch.setattr(fleet, "submit_domain_command", fake_submit)

    fleet_response = api.get("/api/lite/media-backup", headers=headers)
    device_response = api.get(
        "/api/lite/devices/storage-phone/photo-backup", headers=headers
    )
    start_response = api.post(
        "/api/lite/devices/storage-phone/photo-backup",
        json={"collections": ["camera"]},
        headers=headers,
    )
    assert fleet_response.status_code == 200, fleet_response.text
    assert device_response.status_code == 200, device_response.text
    assert start_response.status_code == 202, start_response.text
    assert start_response.json()["sanitized"] is True
    assert start_response.json()["backup_id"] == "photo-qualification"

    revoke = api.post("/api/lite/harness/principal/revoke", headers=headers)
    assert revoke.status_code == 200, revoke.text
