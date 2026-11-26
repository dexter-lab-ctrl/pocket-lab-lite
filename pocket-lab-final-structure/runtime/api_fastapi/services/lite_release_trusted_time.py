"""Renewable independent signed-time evidence, release-child owned.

This is a small nonce-bound Ed25519 time-service contract, not an NTS or
Roughtime implementation. The time signer and its pin must be independently
provisioned, distinct from release and rotation authority. HTTPS is transport
defense only; the pinned signature is the time authentication boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
import re
import secrets
from urllib.parse import urlsplit
import urllib.request

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .lite_lifecycle_contract import canonical_bytes
from .lite_release_trust import TrustError, _decode, strict_json

DOMAIN = b"PocketLabLite signed time challenge v1\x00"
MAX_RESPONSE = 4096
MAX_RTT_NS = 3_000_000_000
MAX_UNCERTAINTY_MS = 1000
ANCHOR_NS = 600_000_000_000


def source_configuration():
    """Only local protected configuration can select a time service."""
    source = os.environ.get("POCKETLAB_RELEASE_TRUST_TIME_SOURCE", "operator_anchor")
    if source == "operator_anchor":
        return source, "", ""
    if source != "signed_challenge":
        raise TrustError("trusted_time_source_invalid")
    url = os.environ.get("POCKETLAB_RELEASE_TIME_URL", "")
    key_id = os.environ.get("POCKETLAB_RELEASE_TIME_KEY_SHA256", "")
    try:
        parsed = urlsplit(url)
        if (len(url) > 2048 or parsed.scheme != "https" or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or not parsed.path.startswith("/")
                or not re.fullmatch(r"[a-f0-9]{64}", key_id)):
            raise ValueError()
        _ = parsed.port
    except ValueError as exc:
        raise TrustError("trusted_time_configuration_invalid") from exc
    return source, url, key_id


def source_revision():
    source, url, pin = source_configuration()
    return hashlib.sha256(canonical_bytes({"source": source, "url": url, "pin": pin})).hexdigest()


def matches_current_source(receipt):
    """Prepared reads never renew time or contact a network service."""
    try:
        source, _, _ = source_configuration()
        if source == "operator_anchor":
            return receipt.get("clock_source", "operator_anchor") == source
        return (receipt.get("clock_source") == source
                and receipt.get("clock_source_revision") == source_revision())
    except (TrustError, ValueError):
        return False


def verify_response(raw: bytes, *, nonce: str, public_key: bytes, pinned_key: str,
                    start_ns: int, end_ns: int, boot_id: str):
    if (not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE
            or len(public_key) != 32 or hashlib.sha256(public_key).hexdigest() != pinned_key
            or not re.fullmatch(r"[0-9a-f]{64}", nonce)
            or type(start_ns) is not int or type(end_ns) is not int
            or not boot_id or not 0 <= end_ns - start_ns <= MAX_RTT_NS):
        raise TrustError("trusted_time_challenge_invalid")
    response = strict_json(raw)
    if (not isinstance(response, dict) or set(response) != {"payload", "signature"}
            or not isinstance(response["payload"], dict)
            or not isinstance(response["signature"], str)):
        raise TrustError("trusted_time_response_invalid")
    payload = response["payload"]
    if (set(payload) != {"schema_version", "nonce", "key_id", "utc", "uncertainty_ms"}
            or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
            or payload["nonce"] != nonce or payload["key_id"] != pinned_key
            or type(payload["uncertainty_ms"]) is not int
            or not 0 <= payload["uncertainty_ms"] <= MAX_UNCERTAINTY_MS
            or not isinstance(payload["utc"], str)
            or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", payload["utc"])):
        raise TrustError("trusted_time_response_invalid")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            _decode(response["signature"], 64), DOMAIN + canonical_bytes(payload))
        utc = datetime.fromisoformat(payload["utc"][:-1] + "+00:00").astimezone(timezone.utc)
        # Use the conservative upper bound, not an optimistic timestamp.
        # Full RTT includes suspend and bounds the response transit.
        rtt = end_ns - start_ns
        now = utc + timedelta(milliseconds=payload["uncertainty_ms"],
                              microseconds=(rtt + 999) // 1000)
    except (InvalidSignature, ValueError, OverflowError) as exc:
        raise TrustError("trusted_time_signature_or_timestamp_invalid") from exc
    return now, {"clock_boot_id": boot_id, "clock_sample_ns": end_ns,
                 "clock_basis": "boottime", "clock_remaining_ns": ANCHOR_NS - rtt,
                 "clock_source": "signed_challenge",
                 "clock_uncertainty_ms": payload["uncertainty_ms"] + (rtt + 999999) // 1000000}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise TrustError("trusted_time_redirect_rejected")


def renew(directory, *, excluded_key_ids=()):
    """One bounded challenge in the existing release child; no fallback."""
    from . import lite_release_trust_configuration as config
    from .lite_release_trust_runtime import _read

    source, url, pin = source_configuration()
    if source != "signed_challenge" or pin in excluded_key_ids or not config.BOOT_ID:
        raise TrustError("trusted_time_independent_key_required")
    key = _read(directory, "time-public-key.bin", 32)
    if len(key) != 32 or hashlib.sha256(key).hexdigest() != pin:
        raise TrustError("trusted_time_key_pin_mismatch")
    nonce = secrets.token_hex(32)
    request = urllib.request.Request(url, data=canonical_bytes({"schema_version": 1, "nonce": nonce}),
                                     headers={"Content-Type": "application/json", "Accept": "application/json"},
                                     method="POST")
    # No ambient proxy or redirect. TLS may fail on a badly set wall clock;
    # in that case hold verification. Never disable TLS checks or use wall time.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    start = config.boot_time_ns()
    if start is None:
        raise TrustError("trusted_time_boottime_unavailable")
    with opener.open(request, timeout=MAX_RTT_NS / 1e9) as response:
        if response.status != 200:
            raise TrustError("trusted_time_service_unavailable")
        raw = response.read(MAX_RESPONSE + 1)
    end = config.boot_time_ns()
    now, fields = verify_response(raw, nonce=nonce, public_key=key, pinned_key=pin,
                                  start_ns=start, end_ns=end, boot_id=config.BOOT_ID)
    return now, {**fields, "clock_source_revision": source_revision()}
