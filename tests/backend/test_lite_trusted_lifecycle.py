"""Synthetic keys and isolated SQLite only; no server or production trust."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest
from pocket_lab_test_utils import ensure_runtime_path

ensure_runtime_path()
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from api_fastapi.services import lite_release_trust as trust
from api_fastapi.services import lite_release_trust_runtime as runtime
from api_fastapi.services.lite_lifecycle_contract import CAPABILITIES, Impact, assess, inventory, canonical_bytes, DecisionDimensions

NOW = datetime(2026, 11, 26, tzinfo=timezone.utc)
TAG = "lite-2026.11.26.1"
COMMIT = "a" * 40
D = "b" * 64


@pytest.fixture
def candidate():
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    kid = hashlib.sha256(public).hexdigest()
    root = trust.Root(schema_version=1, version=1, repository="dexter-lab-ctrl/pocket-lab-lite",
        workflow=".github/workflows/release-dist.yml", role="release", threshold=1,
        keys=[trust.PublicKey(keyid=kid, algorithm="ed25519", public_key=base64.b64encode(public).decode())],
        revoked=[], expires="2026-12-01T00:00:00Z")
    cap = canonical_bytes({"schema_version": 1, "release_tag": TAG, "source_commit": COMMIT,
                           "artifact_sha256": D, "capabilities": inventory()})
    observed = {k: D for k in runtime.FILES}
    metadata = {"schema_version": 1, "version": 1, "root_version": 1,
        "repository": root.repository, "workflow": root.workflow, "release_tag": TAG,
        "source_commit": COMMIT, "channel": "stable", "expires": "2026-11-30T00:00:00Z",
        **observed, "capability_manifest_sha256": hashlib.sha256(cap).hexdigest(),
        "schema_min": 55, "schema_max": 58}
    payload = canonical_bytes(metadata)
    envelope = {"payloadType": trust.PAYLOAD_TYPE, "payload": base64.b64encode(payload).decode(),
                "signatures": [{"keyid": kid, "sig": base64.b64encode(key.sign(trust.pae(payload))).decode()}]}
    kwargs = dict(pinned_root=root, trusted_now=NOW, highest_version=0, highest_root=0,
                  expected_tag=TAG, expected_commit=COMMIT, channel="stable",
                  observed_digests=observed, capability_manifest=cap)
    return envelope, kwargs


def test_verified_signature_is_not_execution_or_provenance(candidate):
    envelope, kwargs = candidate
    result = trust.verify(canonical_bytes(envelope), **kwargs)
    assert result["authenticity"] == result["integrity"] == "verified"
    assert result["provenance"] == result["compatibility"] == "unknown"
    assert result["execution_eligible"] is False


@pytest.mark.parametrize("field,value", [
    ("highest_version", 1), ("highest_root", 2), ("trusted_now", None),
    ("expected_commit", "c"*40), ("channel", "preview"),
    ("trusted_now", datetime(2026, 12, 2, tzinfo=timezone.utc)),
])
def test_fail_closed(candidate, field, value):
    envelope, kwargs = candidate
    kwargs[field] = value
    with pytest.raises(trust.TrustError):
        trust.verify(canonical_bytes(envelope), **kwargs)


def test_invalid_signature_and_duplicate_key(candidate):
    envelope, kwargs = candidate
    envelope["signatures"][0]["sig"] = base64.b64encode(bytes(64)).decode()
    with pytest.raises(trust.TrustError):
        trust.verify(canonical_bytes(envelope), **kwargs)
    with pytest.raises(trust.TrustError):
        trust.strict_json(b'{"version":1,"version":2}')


def test_revocation_and_manifest_mismatch(candidate):
    envelope, kwargs = candidate
    root = kwargs["pinned_root"]
    kwargs["pinned_root"] = root.model_copy(update={"revoked": [root.keys[0].keyid]})
    with pytest.raises(trust.TrustError):
        trust.verify(canonical_bytes(envelope), **kwargs)
    kwargs["pinned_root"] = root
    kwargs["capability_manifest"] += b" "
    with pytest.raises(trust.TrustError):
        trust.verify(canonical_bytes(envelope), **kwargs)


def test_scope_expansion_and_unknown_policy():
    old = CAPABILITIES[:1]
    expanded = (old[0].model_copy(update={"targets": ("new_target", old[0].targets[0])}),)
    result = assess(old, expanded, policy_changed=False, migration_changed=False, root_changed=False)
    assert result.impact == Impact.U4
    assert not result.execution_eligible
    assert assess(old, old, policy_changed=True, migration_changed=False, root_changed=False).impact == Impact.UX
    assert DecisionDimensions().execution == "not_enabled"
    with pytest.raises(ValueError):
        inventory(old + old)


def test_durable_floor_does_not_replace_receipt_on_replay(candidate, tmp_path, monkeypatch):
    from api_fastapi.services import lite_control_plane_store
    monkeypatch.setattr(lite_control_plane_store, "_bump_revision", lambda *args, **kwargs: None)
    envelope, kwargs = candidate
    receipt = trust.verify(canonical_bytes(envelope), **kwargs)
    configure_fixture(monkeypatch)
    receipt.update(provenance="verified", root_sha256=D, attestation_root_sha256="c"*64,
                   configuration_revision=1, clock_boot_id="test-boot", clock_basis="boottime",
                   clock_sample_ns=1000, clock_remaining_ns=600_000_000_000)
    schema = Path(__file__).parents[2] / "pocket-lab-final-structure/runtime/api_fastapi/db/schema"
    with sqlite3.connect(tmp_path / "isolated.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        for name in ("0056_trusted_lifecycle.sql", "0057_lifecycle_authority.sql", "0058_release_trust_observations.sql", "0059_lifecycle_review_state.sql", "0060_lifecycle_trusted_time.sql", "0061_lifecycle_trust_configuration.sql", "0062_lifecycle_independent_scopes.sql", "0063_lifecycle_audit_links.sql"):
            conn.executescript((schema / name).read_text())
        assert conn.execute("SELECT COUNT(*) FROM lite_lifecycle_preferences").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM lite_lifecycle_grants").fetchone()[0] == 0
        runtime.config.reconcile_configuration(conn)
        observation = {"state": "historical_evidence", "reason_code": receipt["reason_code"],
                       "root_sha256": D, "receipt": receipt}
        runtime.persist(conn, observation, TAG)
        runtime.persist(conn, observation, TAG)
        assert runtime.floor_request(conn)["highest_version"] == 1
        assert conn.execute("SELECT COUNT(*) FROM lite_release_trust_receipts").fetchone()[0] == 1
        runtime.persist(conn, {**observation, "receipt": {**receipt, "metadata_sha256": "c"*64}}, TAG)
        assert conn.execute("SELECT state FROM lite_release_trust_observation").fetchone()[0] == "verification_failed"
        assert runtime.floor_request(conn)["highest_digest"] == receipt["metadata_sha256"]


def test_local_optional_ceiling_and_restrictive_impact():
    old = CAPABILITIES[:1]
    opt = CAPABILITIES[1].model_copy(update={"optional": True})
    flags = dict(policy_changed=False, migration_changed=False, root_changed=False)
    assert assess(old, old + (opt,), **flags).impact == Impact.U4
    assert assess(old, old + (opt,), approved_optional=(opt,), **flags).impact == Impact.U3
    assert assess(old, (), **flags).impact == Impact.U2
    assert assess(old, old, presentation_only_proved=True, **flags).impact == Impact.U0


def test_delegation_cannot_override_policy_or_runtime():
    from api_fastapi.services.lite_lifecycle_delegation import scope_review
    cap = next(c for c in CAPABILITIES if c.id == "lifecycle.release.verify")
    args = dict(purpose="release-reconciler", internal_owner="release_runtime", ceiling=cap,
                proposed=cap, channel="stable", category="software",
                current_record="within_recorded_boundary", opa_allowed=True, runtime_ready=True)
    assert scope_review(**args).disposition == "within"
    assert not scope_review(**args).execution_eligible
    for change in ({"opa_allowed": False}, {"runtime_ready": False}, {"current_record": "revoked"},
                   {"purpose": "migration-executor"}, {"channel": "preview"}, {"internal_owner": "human"},
                   {"proposed": cap.model_copy(update={"secret_access": True})},
                   {"proposed": cap.model_copy(update={"version": 2})}):
        assert scope_review(**{**args, **change}).disposition != "within"


def test_root_rotation_requires_both_independent_thresholds(candidate):
    from api_fastapi.services.lite_release_root_rotation import verify_rotation, TYPE
    _, kwargs = candidate
    release_root = kwargs["pinned_root"]
    old_key, next_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    def public(key):
        raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        return trust.PublicKey(keyid=hashlib.sha256(raw).hexdigest(), algorithm="ed25519",
                               public_key=base64.b64encode(raw).decode())
    old = release_root.model_copy(update={"rotation_keys": [public(old_key)], "rotation_threshold": 1})
    new = release_root.model_copy(update={"version": 2, "rotation_keys": [public(next_key)], "rotation_threshold": 1})
    old_bytes, new_bytes = (canonical_bytes(item.model_dump(mode="json")) for item in (old, new))
    pins = dict(old_pin=hashlib.sha256(old_bytes).hexdigest(), new_pin=hashlib.sha256(new_bytes).hexdigest(), now=NOW)
    payload = canonical_bytes({"schema_version": 1, "old_sha256": pins["old_pin"], "new_sha256": pins["new_pin"],
                               "old_version": 1, "new_version": 2})
    message = b"DSSEv1 " + str(len(TYPE)).encode() + b" " + TYPE + b" " + str(len(payload)).encode() + b" " + payload
    transition = {"payloadType": TYPE.decode(), "payload": base64.b64encode(payload).decode(),
                  "signatures": [{"keyid": public(key).keyid, "sig": base64.b64encode(key.sign(message)).decode()}
                                 for key in (old_key, next_key)]}
    assert verify_rotation(old_bytes, new_bytes, canonical_bytes(transition), **pins)["previous_root_sha256"] == pins["old_pin"]
    transition["signatures"].pop()
    with pytest.raises(trust.TrustError):
        verify_rotation(old_bytes, new_bytes, canonical_bytes(transition), **pins)


def test_artifact_tampering_and_untrusted_key(candidate):
    envelope, kwargs = candidate
    kwargs["observed_digests"]["artifact_sha256"] = "d" * 64
    with pytest.raises(trust.TrustError):
        trust.verify(canonical_bytes(envelope), **kwargs)
    kwargs["observed_digests"]["artifact_sha256"] = D
    envelope["signatures"][0]["keyid"] = "c" * 64
    with pytest.raises(trust.TrustError):
        trust.verify(canonical_bytes(envelope), **kwargs)


def test_narrowing_and_revocation_require_owner_and_revision_not_opa(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from api_fastapi.services import lite_lifecycle_authority as lifecycle
    from api_fastapi.services import lite_control_plane_store
    from api_fastapi.services.lite_infrastructure_authority import require_owner
    schema = Path(__file__).parents[2] / "pocket-lab-final-structure/runtime/api_fastapi/db/schema"
    db = sqlite3.connect(tmp_path / "authority.sqlite3", isolation_level=None)
    db.row_factory = sqlite3.Row
    for name in ("0056_trusted_lifecycle.sql", "0057_lifecycle_authority.sql", "0058_release_trust_observations.sql",
                 "0059_lifecycle_review_state.sql", "0060_lifecycle_trusted_time.sql", "0061_lifecycle_trust_configuration.sql", "0062_lifecycle_independent_scopes.sql", "0063_lifecycle_audit_links.sql"):
        db.executescript((schema / name).read_text())
    @contextmanager
    def connection():
        yield db
    monkeypatch.setattr(lifecycle, "connection", connection)
    monkeypatch.setattr(lite_control_plane_store, "_bump_revision", lambda *args, **kwargs: None)
    monkeypatch.setattr(lifecycle.opa, "evaluate_authorization",
                        lambda **kwargs: pytest.fail("Safety narrowing must not call OPA"))
    with pytest.raises(PermissionError):
        require_owner(db, {"actor": {"type": "service"}, "session": {"authenticated": True}})
    monkeypatch.setattr(lifecycle, "_owner", lambda conn, context: ("fixture-owner", (1, 1, 1), False))
    db.execute("INSERT INTO lite_lifecycle_preferences VALUES(1,1,'recommended','2026-11-26T00:00:00Z','fixture-owner')")
    assert lifecycle.save_profile({}, lifecycle.PreferenceRequest(expected_revision=1, profile="notify", confirm=True))["revision"] == 2
    with pytest.raises(ValueError, match="preference_revision_changed"):
        lifecycle.save_profile({}, lifecycle.PreferenceRequest(expected_revision=1, profile="notify", confirm=True))
    assert lifecycle.revoke({}, lifecycle.RevokeRequest(expected_revision=1, confirm=True))["revision"] == 2
    with pytest.raises(ValueError, match="boundary_revision_changed"):
        lifecycle.revoke({}, lifecycle.RevokeRequest(expected_revision=1, confirm=True))
    assert db.execute("SELECT COUNT(*) FROM lite_lifecycle_audit").fetchone()[0] == 2
    db.close()


def configure_fixture(monkeypatch):
    from api_fastapi.services import lite_release_trust_configuration as config
    from api_fastapi.services import lite_control_plane_store
    monkeypatch.setenv("POCKETLAB_RELEASE_ROOT_SHA256", D)
    monkeypatch.setenv("POCKETLAB_RELEASE_ATTESTATION_ROOT_SHA256", "c"*64)
    monkeypatch.delenv("POCKETLAB_RELEASE_TRUST_SUSPENDED", raising=False)
    monkeypatch.setattr(config, "BOOT_ID", "test-boot")
    monkeypatch.setattr(config, "boot_time_ns", lambda: 1000)
    monkeypatch.setattr(lite_control_plane_store, "_bump_revision", lambda *args, **kwargs: None)
    return config


def fixture_db(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    schema = Path(__file__).parents[2] / "pocket-lab-final-structure/runtime/api_fastapi/db/schema"
    for file in sorted(schema.glob("*.sql")):
        if 56 <= int(file.name.split("_", 1)[0]) <= 63:
            db.executescript(file.read_text())
    return db


def test_configuration_latches_before_candidate_and_missing_config_suspends(tmp_path, monkeypatch):
    config = configure_fixture(monkeypatch)
    with fixture_db(tmp_path / "latch.sqlite3") as db:
        config.reconcile_configuration(db)
        assert config.latched(db)
        assert runtime.floor_request(db)["highest_version"] == 0
        monkeypatch.delenv("POCKETLAB_RELEASE_ROOT_SHA256")
        config.reconcile_configuration(db)
        assert config.latched(db)
        assert config.configuration(db)["state"] == "suspended"
        assert config.configuration(db)["root_sha256"] == D


def test_prepared_time_no_wall_clock_fallback(tmp_path, monkeypatch):
    config = configure_fixture(monkeypatch)
    with fixture_db(tmp_path / "clock.sqlite3") as db:
        config.reconcile_configuration(db)
        receipt = dict(configuration_revision=1, root_sha256=D, attestation_root_sha256="c"*64,
                       clock_basis="boottime", clock_boot_id="test-boot", clock_sample_ns=1000,
                       clock_remaining_ns=600_000_000_000, checked_at=NOW.isoformat())
        assert config.prepared_now(db, receipt) == NOW
        for sample in (999, 600_000_001_001, None):
            monkeypatch.setattr(config, "boot_time_ns", lambda: sample)
            assert config.prepared_now(db, receipt) is None
        monkeypatch.setattr(config, "boot_time_ns", lambda: 1000)
        monkeypatch.setattr(config, "BOOT_ID", "another-boot")
        assert config.prepared_now(db, receipt) is None


def test_restore_preserves_live_floor_and_advances_live_epochs(tmp_path, monkeypatch):
    from api_fastapi.services.lite_lifecycle_restore import fence_staged_restore
    config = configure_fixture(monkeypatch)
    staged, checkpoint = tmp_path / "staged.sqlite3", tmp_path / "checkpoint.sqlite3"
    db = fixture_db(checkpoint)
    config.reconcile_configuration(db)
    db.execute("INSERT INTO lite_release_trust_floor VALUES(1,12,2,?,?)", (D,TAG))
    db.execute("UPDATE lite_lifecycle_workspace SET authority_epoch=12,boundary_revision=13,delegation_revision=14")
    db.commit()
    db.close()
    db = fixture_db(staged)
    # The staged DB references the identity store via foreign keys, but no
    # synthetic human or grant is needed for this floor/epoch regression.
    db.close()
    fence_staged_restore(staged, checkpoint)
    with sqlite3.connect(staged) as db:
        assert db.execute("SELECT metadata_version,root_version FROM lite_release_trust_floor").fetchone() == (12,2)
        assert db.execute("SELECT state FROM lite_release_trust_configuration").fetchone() == ("suspended",)
        assert db.execute("SELECT authority_epoch,boundary_revision,delegation_revision FROM lite_lifecycle_workspace").fetchone() == (13,14,15)
        assert db.execute("SELECT COUNT(*) FROM lite_release_trust_observation").fetchone()[0] == 0


def test_restore_fails_closed_when_scoped_authority_has_no_identity_store(tmp_path):
    from api_fastapi.services.lite_lifecycle_restore import fence_staged_restore

    staged, checkpoint = tmp_path / "staged.sqlite3", tmp_path / "checkpoint.sqlite3"
    fixture_db(checkpoint).close()
    db = fixture_db(staged)
    db.execute(
        "INSERT INTO lite_lifecycle_boundary_scopes VALUES(?,?,?,?,?,?,?)",
        ("release-reconciler", 1, 1, "fixture-owner", "{}", "fixture-decision", NOW.isoformat()),
    )
    db.commit()
    db.close()

    with pytest.raises(ValueError, match="restore_identity_store_missing"):
        fence_staged_restore(staged, checkpoint)


def test_registry_is_descriptive_and_does_not_enable_execution():
    from api_fastapi.services.lite_infrastructure_operations import PRODUCTION_QUALIFIED_AUTOMATIC_OPERATIONS
    assert PRODUCTION_QUALIFIED_AUTOMATIC_OPERATIONS == {"projection.reconcile"}
    assert len({c.id for c in CAPABILITIES}) == len(CAPABILITIES)
    assert DecisionDimensions().execution == "not_enabled"
