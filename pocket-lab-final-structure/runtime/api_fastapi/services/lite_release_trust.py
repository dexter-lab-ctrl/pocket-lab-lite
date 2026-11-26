"""Bounded offline verification primitives. No network, installation or activation.

Uses DSSE v1 pre-authentication encoding and cryptography's Ed25519 verifier.
This is not a full TUF implementation or a GitHub attestation verifier.
Trusted roots and trusted time must come from an independently qualified local
owner, not from candidate metadata or browser requests.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .lite_lifecycle_contract import Capability, inventory
from .lite_release_contract import DEFAULT_REPOSITORY, parse_lite_tag

PAYLOAD_TYPE = "application/vnd.pocketlab.release-trust.v1+json"
MAX_BYTES = 256 * 1024
DIGEST = r"^[0-9a-f]{64}$"


class TrustError(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TrustError("duplicate_json_key")
        result[key] = value
    return result


def _bad_constant(_):
    raise TrustError("invalid_json_constant")


def strict_json(raw: bytes):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise TrustError("metadata_size_invalid")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_bad_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise TrustError("metadata_invalid") from exc


def _decode(value: str, expected: int | None = None) -> bytes:
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise TrustError("encoding_invalid") from exc
    if base64.b64encode(raw).decode("ascii") != value or (expected is not None and len(raw) != expected):
        raise TrustError("encoding_invalid")
    return raw


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class PublicKey(Strict):
    keyid: str = Field(pattern=DIGEST)
    algorithm: Literal["ed25519"]
    public_key: str = Field(max_length=44)


class Root(Strict):
    schema_version: Literal[1]
    version: int = Field(ge=1, le=2147483647)
    repository: Literal["dexter-lab-ctrl/pocket-lab-lite"]
    workflow: Literal[".github/workflows/release-dist.yml"]
    role: Literal["release"]
    threshold: int = Field(ge=1, le=8)
    keys: list[PublicKey] = Field(min_length=1, max_length=8)
    revoked: list[str] = Field(max_length=32)
    expires: str = Field(max_length=32)
    rotation_keys: list[PublicKey] = Field(default_factory=list, max_length=8)
    rotation_threshold: int = Field(default=0, ge=0, le=8)


class Signature(Strict):
    keyid: str = Field(pattern=DIGEST)
    sig: str = Field(max_length=88)


class Envelope(Strict):
    payloadType: Literal["application/vnd.pocketlab.release-trust.v1+json"]
    payload: str = Field(max_length=MAX_BYTES)
    signatures: list[Signature] = Field(min_length=1, max_length=8)


class ReleaseMetadata(Strict):
    schema_version: Literal[1]
    version: int = Field(ge=1, le=99_991_231_999_999)
    root_version: int = Field(ge=1, le=2147483647)
    repository: Literal["dexter-lab-ctrl/pocket-lab-lite"]
    workflow: Literal[".github/workflows/release-dist.yml"]
    release_tag: str = Field(max_length=80)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    channel: Literal["stable", "preview"]
    expires: str = Field(max_length=32)
    artifact_sha256: str = Field(pattern=DIGEST)
    release_manifest_sha256: str = Field(pattern=DIGEST)
    capability_manifest_sha256: str = Field(pattern=DIGEST)
    policy_sha256: str = Field(pattern=DIGEST)
    migration_inventory_sha256: str = Field(pattern=DIGEST)
    schema_min: int = Field(ge=1)
    schema_max: int = Field(ge=1)


class CapabilityManifest(Strict):
    schema_version: Literal[1]
    release_tag: str = Field(max_length=80)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    artifact_sha256: str = Field(pattern=DIGEST)
    capabilities: list[Capability] = Field(max_length=256)


def _parse(model, raw):
    # Parse strictly twice so duplicate keys are rejected while JSON arrays can
    # be decoded into immutable tuple fields by Pydantic's JSON-mode validator.
    strict_json(raw)
    try:
        return model.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        raise TrustError("metadata_schema_invalid") from exc


def pae(payload: bytes) -> bytes:
    kind = PAYLOAD_TYPE.encode("ascii")
    return b"DSSEv1 " + str(len(kind)).encode() + b" " + kind + b" " + str(len(payload)).encode() + b" " + payload


def _expiry(value: str, now: datetime) -> None:
    try:
        if not value.endswith("Z"):
            raise ValueError()
        expiry = datetime.fromisoformat(value[:-1] + "+00:00")
        if expiry <= now:
            raise TrustError("metadata_expired")
    except (ValueError, TypeError) as exc:
        if isinstance(exc, TrustError):
            raise
        raise TrustError("metadata_time_invalid") from exc


def verify(envelope_bytes: bytes, *, pinned_root: Root, trusted_now: datetime | None,
           highest_version: int, highest_root: int, expected_tag: str,
           expected_commit: str, channel: str, observed_digests: dict[str, str],
           capability_manifest: bytes) -> dict:
    if trusted_now is None or trusted_now.tzinfo is None:
        raise TrustError("trusted_time_unavailable")
    now = trusted_now.astimezone(timezone.utc)
    _expiry(pinned_root.expires, now)
    if pinned_root.version < highest_root:
        raise TrustError("root_rollback")
    keys = {}
    if (pinned_root.rotation_threshold > len(pinned_root.rotation_keys)
        or bool(pinned_root.rotation_keys) != bool(pinned_root.rotation_threshold)
        or set(k.keyid for k in pinned_root.rotation_keys) & set(k.keyid for k in pinned_root.keys)):
        raise TrustError("root_role_separation_invalid")
    if len(set(pinned_root.revoked)) != len(pinned_root.revoked):
        raise TrustError("duplicate_revoked_key")
    for key in pinned_root.keys:
        raw = _decode(key.public_key, 32)
        if hashlib.sha256(raw).hexdigest() != key.keyid or key.keyid in keys:
            raise TrustError("root_key_invalid")
        keys[key.keyid] = raw
    envelope = _parse(Envelope, envelope_bytes)
    payload = _decode(envelope.payload)
    if len(payload) > MAX_BYTES:
        raise TrustError("metadata_size_invalid")
    valid = set()
    seen = set()
    for sig in envelope.signatures:
        if sig.keyid in seen:
            raise TrustError("duplicate_signature")
        seen.add(sig.keyid)
        if sig.keyid not in keys or sig.keyid in pinned_root.revoked:
            continue
        try:
            Ed25519PublicKey.from_public_bytes(keys[sig.keyid]).verify(_decode(sig.sig, 64), pae(payload))
            valid.add(sig.keyid)
        except InvalidSignature:
            continue
    if len(valid) < pinned_root.threshold:
        raise TrustError("signature_threshold_not_met")
    metadata = _parse(ReleaseMetadata, payload)
    _expiry(metadata.expires, now)
    if metadata.root_version != pinned_root.version or metadata.version <= highest_version:
        raise TrustError("metadata_replay_or_root_mismatch")
    parse_lite_tag(metadata.release_tag)
    if (metadata.repository != pinned_root.repository or metadata.workflow != pinned_root.workflow
        or metadata.release_tag != expected_tag or metadata.source_commit != expected_commit
        or metadata.channel != channel or metadata.schema_min > metadata.schema_max):
        raise TrustError("release_identity_mismatch")
    manifest = _parse(CapabilityManifest, capability_manifest)
    inventory(tuple(manifest.capabilities))
    if (manifest.release_tag != metadata.release_tag or manifest.source_commit != metadata.source_commit
        or manifest.artifact_sha256 != metadata.artifact_sha256):
        raise TrustError("capability_manifest_identity_mismatch")
    expected = {name: getattr(metadata, name) for name in (
        "artifact_sha256", "release_manifest_sha256", "policy_sha256", "migration_inventory_sha256")}
    if any(observed_digests.get(name) != value for name, value in expected.items()):
        raise TrustError("artifact_digest_mismatch")
    if hashlib.sha256(capability_manifest).hexdigest() != metadata.capability_manifest_sha256:
        raise TrustError("capability_manifest_digest_mismatch")
    return {
        "release_tag": metadata.release_tag, "source_commit": metadata.source_commit,
        "metadata_version": metadata.version, "root_version": pinned_root.version,
        "artifact_sha256": metadata.artifact_sha256, "metadata_sha256": hashlib.sha256(payload).hexdigest(),
        "expires": metadata.expires, "root_expires": pinned_root.expires, "checked_at": now.isoformat(),
        "channel": metadata.channel, "policy_sha256": metadata.policy_sha256,
        "migration_inventory_sha256": metadata.migration_inventory_sha256,
        "capability_manifest_sha256": metadata.capability_manifest_sha256,
        "schema_min": metadata.schema_min, "schema_max": metadata.schema_max,
        "authenticity": "verified", "integrity": "verified",
        "provenance": "unknown", "compatibility": "unknown", "impact": "UX",
        "execution_eligible": False, "reason_code": "independent_provenance_and_qualification_required",
    }
