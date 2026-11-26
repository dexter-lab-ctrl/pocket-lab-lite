"""Explicit sequential root transition; old and new threshold must approve.

This is a DSSE-based bounded subset, not a TUF root role implementation.
An expired or compromised old threshold requires independently governed
out-of-band recovery; it cannot be bypassed by a candidate release.
"""
import hashlib
import base64
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from .lite_release_trust import Root, TrustError, _parse, _decode, _expiry, strict_json
from .lite_lifecycle_contract import canonical_bytes

TYPE = b"application/vnd.pocketlab.root-transition.v1+json"


def verify_rotation(old_bytes, new_bytes, transition, *, old_pin, new_pin, now):
    if now is None:
        raise TrustError("trusted_time_unavailable")
    if hashlib.sha256(old_bytes).hexdigest() != old_pin or hashlib.sha256(new_bytes).hexdigest() != new_pin:
        raise TrustError("root_pin_mismatch")
    old, new = _parse(Root, old_bytes), _parse(Root, new_bytes)
    _expiry(old.expires, now)
    _expiry(new.expires, now)
    if new.version != old.version + 1 or old.repository != new.repository or old.workflow != new.workflow:
        raise TrustError("root_transition_invalid")
    if not set(old.revoked).issubset(new.revoked):
        raise TrustError("revocation_rollback")
    release_keys = {k.keyid for root in (old,new) for k in root.keys}
    rotation_keys = {k.keyid for root in (old,new) for k in root.rotation_keys}
    if release_keys & rotation_keys:
        raise TrustError("root_role_separation_invalid")
    envelope = strict_json(transition)
    if not isinstance(envelope, dict) or set(envelope) != {"payloadType", "payload", "signatures"} or envelope["payloadType"] != TYPE.decode():
        raise TrustError("root_transition_invalid")
    payload = canonical_bytes({"schema_version": 1, "old_sha256": old_pin, "new_sha256": new_pin,
                               "old_version": old.version, "new_version": new.version})
    if _decode(envelope["payload"]) != payload:
        raise TrustError("root_transition_binding_mismatch")
    message = b"DSSEv1 " + str(len(TYPE)).encode() + b" " + TYPE + b" " + str(len(payload)).encode() + b" " + payload
    signatures = envelope["signatures"]
    if not isinstance(signatures, list) or not 1 <= len(signatures) <= 16:
        raise TrustError("root_transition_signatures_invalid")
    by_id = {}
    for sig in signatures:
        if not isinstance(sig, dict) or set(sig) != {"keyid", "sig"} or sig["keyid"] in by_id:
            raise TrustError("root_transition_signatures_invalid")
        by_id[sig["keyid"]] = _decode(sig["sig"], 64)
    for root in (old, new):
        if not root.rotation_keys or not root.rotation_threshold or root.rotation_threshold > len(root.rotation_keys):
            raise TrustError("root_rotation_role_unprovisioned")
        if set(k.keyid for k in root.rotation_keys) & set(k.keyid for k in root.keys):
            raise TrustError("root_role_separation_invalid")
        if len(set(k.keyid for k in root.rotation_keys)) != len(root.rotation_keys):
            raise TrustError("duplicate_rotation_key")
        valid = set()
        for key in root.rotation_keys:
            raw = _decode(key.public_key, 32)
            if hashlib.sha256(raw).hexdigest() != key.keyid:
                raise TrustError("root_key_invalid")
            if key.keyid in root.revoked or key.keyid not in by_id:
                continue
            try:
                Ed25519PublicKey.from_public_bytes(raw).verify(by_id[key.keyid], message)
                valid.add(key.keyid)
            except InvalidSignature:
                continue
        if len(valid) < root.rotation_threshold:
            raise TrustError("root_transition_threshold_not_met")
    return {"previous_root_sha256": old_pin, "root_transition_sha256": hashlib.sha256(transition).hexdigest()}
