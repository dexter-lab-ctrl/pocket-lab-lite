from __future__ import annotations

import json
import importlib.util
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir, load_fastapi_app


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/db/schema"
PREPARE = ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/prepare-opa-policy.sh"
SUPERVISOR = ROOT / "pocket-lab-final-structure/runtime/supervisors/pocketlab_core_supervisor.py"


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
    reset_sqlite_path_cache(); SQLITE_READS.invalidate(); deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()
    lite_identity_auth.setup_owner(username="owner", display_name="Owner", password="correct horse battery staple", setup_token="one-time-setup-token")
    signed_in = lite_identity_auth.login(username="owner", password="correct horse battery staple")
    auth = lite_identity_auth.authenticate_session_token(signed_in["session_token"])
    lite_enterprise_identity.set_enterprise_enabled(auth_context=auth, enabled=True)
    auth = lite_enterprise_identity.enrich_auth_context(lite_identity_auth.authenticate_session_token(lite_identity_auth.login(username="owner", password="correct horse battery staple")["session_token"]))
    return state, auth


def test_migration_fresh_upgrade_idempotence_and_p21_tables(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.db.connection import read_connection, reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations

    db = tmp_path / "state" / "rules.sqlite3"; monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(db)); reset_sqlite_path_cache()
    assert 27 in apply_migrations()
    assert apply_migrations() == []
    legacy = tmp_path / "legacy-schema"; legacy.mkdir()
    for source in SCHEMA.glob("*.sql"):
        if source.name != "0027_policy_revision_activation_p2.sql":
            shutil.copy2(source, legacy / source.name)
    upgraded = tmp_path / "state" / "upgrade.sqlite3"; monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(upgraded)); reset_sqlite_path_cache()
    assert 26 in apply_migrations(legacy)
    assert apply_migrations()[-1] == 27
    with read_connection() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert {"enterprise_configuration", "enterprise_memberships", "policy_revisions", "policy_runtime_state", "policy_activation_operations"} <= tables
    assert "idx_policy_activation_single_nonterminal" in indexes


def test_typed_revisions_reject_raw_input_and_serialize_activation(policy_runtime):
    from api_fastapi.services import lite_policy_lifecycle as rules

    _, auth = policy_runtime
    created = rules.create_revision(auth_context=auth, template_id="passkey_step_up", parameters={"max_age_seconds": 900}, change_summary="Tighten step-up interval")
    revision = created["revision"]
    assert revision["template_id"] == "passkey_step_up"
    assert all("contents" not in entry for entry in revision["manifest"]["files"])
    with pytest.raises(rules.PolicyLifecycleError, match="approved"):
        rules.create_revision(auth_context=auth, template_id="package evil", parameters={}, change_summary="bad")
    with pytest.raises(rules.PolicyLifecycleError, match="unsupported"):
        rules.create_revision(auth_context=auth, template_id="baseline", parameters={"rego": "package evil"}, change_summary="bad")
    first = rules.request_activation(auth_context=auth, revision_id=revision["revision_id"])
    assert first["operation"]["state"] == "pending"
    with pytest.raises(rules.PolicyLifecycleError) as blocked:
        rules.request_activation(auth_context=auth, revision_id=revision["revision_id"])
    assert blocked.value.reason_code == "policy_activation_in_progress"


def test_rules_api_requires_csrf_enterprise_mode_and_authorized_role(policy_runtime, monkeypatch):
    from fastapi.testclient import TestClient
    from api_fastapi.services import lite_enterprise_governance

    client = TestClient(load_fastapi_app())
    signed_in_response = client.post("/api/lite/identity/login", json={"username": "owner", "password": "correct horse battery staple"})
    assert signed_in_response.status_code == 200
    signed_in = signed_in_response.json()
    personal = client.post("/api/lite/enterprise/rules/revisions", json={"template_id": "baseline", "parameters": {}, "change_summary": "baseline"})
    assert personal.status_code == 403  # CSRF is evaluated before durable mutation.
    missing = client.post("/api/lite/enterprise/rules/revisions", json={"template_id": "baseline", "parameters": {}, "change_summary": "baseline"}, headers={"x-pocket-lab-csrf": signed_in["csrf_token"]})
    assert missing.status_code == 201
    revision_id = missing.json()["revision"]["revision_id"]

    # Root-level Rules activation is fail-closed until the Owner performs a
    # recent passkey step-up. The test then isolates the lifecycle admission
    # boundary without faking browser WebAuthn cryptography.
    step_up_required = client.post("/api/lite/enterprise/rules/activations", json={"revision_id": revision_id}, headers={"x-pocket-lab-csrf": signed_in["csrf_token"]})
    assert step_up_required.status_code == 428
    assert "owner_step_up_required" in step_up_required.text
    monkeypatch.setattr(lite_enterprise_governance, "require_recent_assurance", lambda _auth, _purpose: None)

    activation = client.post("/api/lite/enterprise/rules/activations", json={"revision_id": revision_id}, headers={"x-pocket-lab-csrf": signed_in["csrf_token"]})
    assert activation.status_code == 202
    # The API admitted durable intent only; it did not run a process or switch a pointer.
    assert activation.json()["operation"]["state"] == "pending"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0)); return int(sock.getsockname()[1])


def _supervisor_module():
    spec = importlib.util.spec_from_file_location("pocketlab_core_supervisor_p22", SUPERVISOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def test_supervisor_activation_and_proved_rollback(policy_runtime, monkeypatch):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_policy_lifecycle as rules

    state, auth = policy_runtime
    good = rules.create_revision(auth_context=auth, template_id="baseline", parameters={}, change_summary="known good")["revision"]
    candidate = rules.create_revision(auth_context=auth, template_id="passkey_step_up", parameters={"max_age_seconds": 600}, change_summary="candidate")["revision"]
    rules.request_activation(auth_context=auth, revision_id=good["revision_id"])["operation"]
    module = _supervisor_module(); supervisor = module.LiteCoreSupervisor()
    monkeypatch.setattr(supervisor, "restart_pm2", lambda *_args, **_kwargs: {"acted": True})
    monkeypatch.setattr(module, "fetch_json", lambda url, **_kwargs: {} if url.endswith("/health") else {"result": good["revision_id"]})
    activated = supervisor.reconcile_policy_activation()
    assert activated and activated["event"] == "policy_activation_active"
    with connection() as conn:
        state_row = conn.execute("SELECT active_revision_id,known_good_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
    assert dict(state_row) == {"active_revision_id": good["revision_id"], "known_good_revision_id": good["revision_id"]}

    # A candidate staging failure restores the previously proved revision and
    # reports rolled_back only after health + observed metadata agree.
    second = rules.request_activation(auth_context=auth, revision_id=candidate["revision_id"])["operation"]
    original_prepare = supervisor._prepare_policy
    monkeypatch.setattr(supervisor, "_prepare_policy", lambda action, revision, template_json="": False if action == "stage" and revision == candidate["revision_id"] else original_prepare(action, revision, template_json))
    monkeypatch.setattr(module, "fetch_json", lambda url, **_kwargs: {} if url.endswith("/health") else {"result": good["revision_id"]})
    rolled = supervisor.reconcile_policy_activation()
    assert rolled and rolled["event"] == "policy_activation_rolled_back"
    with connection() as conn:
        final = conn.execute("SELECT state,reason_code FROM policy_activation_operations WHERE operation_id=?", (second["operation_id"],)).fetchone()
    assert dict(final) == {"state": "rolled_back", "reason_code": "candidate_invalid"}


def test_stage_does_not_switch_active_and_real_opa_metadata_is_exact(tmp_path):
    ensure_runtime_path()
    from api_fastapi.services import lite_policy_lifecycle as rules
    opa = shutil.which("opa")
    if not opa:
        pytest.skip("OPA unavailable")
    state = tmp_path / "state"
    revision, tree = rules.policy_source_tree("baseline", "1", {})
    _, candidate_hash = rules.manifest_for_tree(tree)
    env = os.environ | {"POCKETLAB_STATE_DIR": str(state), "POCKETLAB_OPA_BIN": opa, "POCKETLAB_POLICY_REVISION": revision}
    staged = subprocess.run(["bash", str(PREPARE), "stage"], cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    assert staged.returncode == 0, staged.stderr
    revision = staged.stdout.strip().split("revision=")[-1]
    assert not (state / "opa" / "active").exists()
    activated = subprocess.run(["bash", str(PREPARE), "activate", revision], cwd=ROOT, env=env, text=True, capture_output=True, check=False)
    assert activated.returncode == 0, activated.stderr
    stage = state / "opa" / "stage" / revision
    manifest = json.loads((stage / "manifest.json").read_text())
    assert {entry["path"] for entry in manifest["files"]} >= {"pocketlab.rego", "revision.rego", "template.json"}
    assert manifest["candidate_hash"] == candidate_hash
    port = _free_port()
    process = subprocess.Popen([opa, "run", "--server", f"--addr=127.0.0.1:{port}", str(state / "opa" / "active")], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = f"http://127.0.0.1:{port}/v1/data/pocketlab/meta/revision"
        deadline = time.monotonic() + 8
        while True:
            try:
                with urllib.request.urlopen(url, timeout=0.5) as response:
                    payload = json.loads(response.read().decode())
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.1)
        assert payload == {"result": revision}
    finally:
        process.terminate(); process.wait(timeout=5)
