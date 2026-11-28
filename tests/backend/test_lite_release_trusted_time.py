"""Synthetic time signer fixtures; no external time service or production keys."""
import base64
from datetime import datetime, timezone
import hashlib

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from pocket_lab_test_utils import ensure_runtime_path

ensure_runtime_path()
from api_fastapi.services import lite_release_trusted_time as clock
from api_fastapi.services.lite_lifecycle_contract import canonical_bytes
from api_fastapi.services.lite_release_trust import TrustError


@pytest.fixture
def signed_sample():
    signer = Ed25519PrivateKey.generate()
    key = signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    pin = hashlib.sha256(key).hexdigest()
    nonce = "a" * 64
    payload = {"schema_version": 1, "nonce": nonce, "key_id": pin,
               "utc": "2026-11-27T00:00:00Z", "uncertainty_ms": 100}
    raw = canonical_bytes({"payload": payload,
        "signature": base64.b64encode(signer.sign(clock.DOMAIN + canonical_bytes(payload))).decode()})
    return raw, dict(nonce=nonce, public_key=key, pinned_key=pin,
                     start_ns=1000, end_ns=200001000, boot_id="fixture-boot")


def test_nonce_bound_sample_conservative_upper_bound(signed_sample):
    raw, kwargs = signed_sample
    now, receipt = clock.verify_response(raw, **kwargs)
    assert now == datetime(2026, 11, 27, 0, 0, 0, 300000, tzinfo=timezone.utc)
    assert receipt["clock_basis"] == "boottime"
    assert receipt["clock_remaining_ns"] == clock.ANCHOR_NS - 200000000


@pytest.mark.parametrize("field,value", [
    ("nonce", "b" * 64), ("pinned_key", "c" * 64),
    ("end_ns", 0), ("end_ns", 4000000000), ("boot_id", ""),
])
def test_wrong_pin_replay_suspend_or_clock_rollback(signed_sample, field, value):
    raw, kwargs = signed_sample
    kwargs[field] = value
    with pytest.raises(TrustError):
        clock.verify_response(raw, **kwargs)


def test_tampered_signed_time(signed_sample):
    raw, kwargs = signed_sample
    raw = raw.replace(b"2026-11-27", b"2026-11-28")
    with pytest.raises(TrustError):
        clock.verify_response(raw, **kwargs)


def test_time_source_changes_invalidate_prepared_receipt(monkeypatch):
    monkeypatch.setenv("POCKETLAB_RELEASE_TRUST_TIME_SOURCE", "signed_challenge")
    monkeypatch.setenv("POCKETLAB_RELEASE_TIME_URL", "https://time.invalid/nonce")
    monkeypatch.setenv("POCKETLAB_RELEASE_TIME_KEY_SHA256", "a" * 64)
    receipt = {"clock_source": "signed_challenge", "clock_source_revision": clock.source_revision()}
    assert clock.matches_current_source(receipt)
    monkeypatch.setenv("POCKETLAB_RELEASE_TIME_KEY_SHA256", "b" * 64)
    assert not clock.matches_current_source(receipt)
    assert not clock.matches_current_source({})
    monkeypatch.setenv("POCKETLAB_RELEASE_TRUST_TIME_SOURCE", "operator_anchor")
    assert not clock.matches_current_source(receipt)
    assert clock.matches_current_source({})
