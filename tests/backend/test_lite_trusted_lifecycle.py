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


def test_durable_floor_does_not_replace_receipt_on_replay(candidate, tmp_path):
    envelope, kwargs = candidate
    receipt = trust.verify(canonical_bytes(envelope), **kwargs)
    schema = Path(__file__).parents[2] / "pocket-lab-final-structure/runtime/api_fastapi/db/schema"
    with sqlite3.connect(tmp_path / "isolated.sqlite3") as conn:
        conn.row_factory = sqlite3.Row
        for name in ("0056_trusted_lifecycle.sql", "0057_lifecycle_authority.sql", "0058_release_trust_observations.sql"):
            conn.executescript((schema / name).read_text())
        assert conn.execute("SELECT COUNT(*) FROM lite_lifecycle_preferences").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM lite_lifecycle_grants").fetchone()[0] == 0
        observation = {"state": "historical_evidence", "reason_code": receipt["reason_code"],
                       "root_sha256": D, "receipt": receipt}
        runtime.persist(conn, observation, TAG)
        runtime.persist(conn, observation, TAG)
        assert runtime.floor_request(conn)["highest_version"] == 1
        assert conn.execute("SELECT COUNT(*) FROM lite_release_trust_receipts").fetchone()[0] == 1
        runtime.persist(conn, {**observation, "receipt": {**receipt, "metadata_sha256": "c"*64}}, TAG)
        assert conn.execute("SELECT state FROM lite_release_trust_observation").fetchone()[0] == "verification_failed"
        assert runtime.floor_request(conn)["highest_digest"] == receipt["metadata_sha256"]
