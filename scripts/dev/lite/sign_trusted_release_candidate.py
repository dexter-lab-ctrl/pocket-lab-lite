#!/usr/bin/env python3
"""Sign a prepared release in an explicitly protected release environment.

Private Ed25519 keys are supplied only through the environment; never written
to disk or printed. The independently configured public root is not published
as a source of initial client trust.
"""
from __future__ import annotations
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "pocket-lab-final-structure/runtime"))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from api_fastapi.services.lite_release_trust import (
    Root, ReleaseMetadata, PAYLOAD_TYPE, _parse, _expiry, pae, verify,
)
from api_fastapi.services.lite_lifecycle_contract import canonical_bytes
from api_fastapi.services import lite_release_package as source_package


def sign(directory: Path, assets: Path, root: Root, seeds: list[str]):
    if not isinstance(seeds, list) or not 1 <= len(seeds) <= 8:
        raise ValueError("invalid_signer_configuration")
    payload = (directory / "unsigned-release-metadata.json").read_bytes()
    metadata = _parse(ReleaseMetadata, payload)
    now = datetime.now(timezone.utc)
    _expiry(root.expires, now)
    _expiry(metadata.expires, now)
    if metadata.root_version != root.version:
        raise ValueError("signer_root_mismatch")
    signatures = []
    seen = set()
    for seed in seeds:
        key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(seed, validate=True))
        public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        kid = hashlib.sha256(public).hexdigest()
        if kid in seen or kid in root.revoked or not any(k.keyid == kid for k in root.keys):
            raise ValueError("unauthorized_or_duplicate_signer")
        seen.add(kid)
        signatures.append({"keyid": kid, "sig": base64.b64encode(key.sign(pae(payload))).decode("ascii")})
    envelope = canonical_bytes({"payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode("ascii"), "signatures": signatures})
    observed = {}
    for field, path in {
        "artifact_sha256": assets / "dist.zip",
        "release_manifest_sha256": assets / "pocketlab-lite-release.json",
        "policy_sha256": directory / "pocketlab-lite-policy-inventory.json",
        "migration_inventory_sha256": directory / "pocketlab-lite-migration-inventory.json",
    }.items():
        with path.open("rb") as handle:
            observed[field] = hashlib.file_digest(handle, "sha256").hexdigest()
    verify(envelope, pinned_root=root, trusted_now=now, highest_version=0, highest_root=root.version,
           expected_tag=metadata.release_tag, expected_commit=metadata.source_commit,
           channel=metadata.channel, observed_digests=observed,
           capability_manifest=(directory / "pocketlab-lite-capabilities.json").read_bytes())
    declaration = source_package.source_declaration(
        (assets / "pocketlab-lite-release.json").read_bytes(),
        source_commit=metadata.source_commit, release_tag=metadata.release_tag)
    if declaration is not None:
        with (assets / source_package.SOURCE_ASSET).open("rb") as stream:
            source_package.inspect_source(stream, declaration=declaration,
                policy_inventory=(directory / "pocketlab-lite-policy-inventory.json").read_bytes(),
                migration_inventory=(directory / "pocketlab-lite-migration-inventory.json").read_bytes())
    (directory / "pocketlab-lite-trust.dsse.json").write_bytes(envelope)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("arguments_invalid")
        root = _parse(Root, os.environ["POCKETLAB_RELEASE_PUBLIC_ROOT"].encode())
        seeds = json.loads(os.environ.pop("POCKETLAB_RELEASE_SIGNING_SEEDS"))
        sign(Path(sys.argv[1]), Path(sys.argv[2]), root, seeds)
    except Exception:
        # Never emit input values or private material in exceptions.
        raise SystemExit("trusted release signing failed; publishing prohibited") from None
