"""Qualification provenance is independent from production GitHub attestation."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pocket_lab_test_utils import ensure_runtime_path

ensure_runtime_path()
from api_fastapi.services import lite_release_provenance as provenance
from api_fastapi.services import qualification_context
from api_fastapi.services.lite_lifecycle_contract import canonical_bytes


def _fixture(tmp_path: Path):
    root = tmp_path / "release-trust"
    candidate = root / "candidate"
    root.mkdir(mode=0o700)
    candidate.mkdir(mode=0o700)
    signer = Ed25519PrivateKey.generate()
    public = signer.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    key_id = hashlib.sha256(public).hexdigest()
    root_record = {
        "schema": provenance.QUALIFICATION_ROOT_SCHEMA,
        "repository": "dexter-lab-ctrl/pocket-lab-lite",
        "workflow": ".github/workflows/release-dist.yml",
        "key_id": key_id,
        "algorithm": "ed25519",
        "public_key": base64.b64encode(public).decode("ascii"),
        "expires": "2026-12-01T00:00:00Z",
    }
    root_bytes = canonical_bytes(root_record)
    root_file = root / provenance.QUALIFICATION_ROOT
    root_file.write_bytes(root_bytes)
    root_file.chmod(0o400)
    files = {name: (candidate / name) for name in ("dist.zip", "pocketlab-lite-trust.dsse.json")}
    for path in files.values():
        path.write_bytes(path.name.encode("ascii"))
        path.chmod(0o400)
    lines = []
    for name, path in files.items():
        signed = {
            "schema": provenance.QUALIFICATION_SCHEMA,
            "subject": name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "source_commit": "a" * 40,
            "release_tag": "lite-2026.11.28.663",
            "repository": "dexter-lab-ctrl/pocket-lab-lite",
            "workflow": ".github/workflows/release-dist.yml",
            "key_id": key_id,
        }
        lines.append({**signed, "signature": base64.b64encode(signer.sign(provenance.QUALIFICATION_DOMAIN + canonical_bytes(signed))).decode("ascii")})
    bundle = candidate / "pocketlab-lite-provenance.jsonl"
    bundle.write_bytes(b"\n".join(canonical_bytes(line) for line in lines) + b"\n")
    bundle.chmod(0o400)
    return root, candidate, hashlib.sha256(root_bytes).hexdigest()


def test_qualification_provenance_is_independently_verified(tmp_path, monkeypatch):
    root, candidate, pin = _fixture(tmp_path)
    monkeypatch.setenv("POCKETLAB_RELEASE_PROVENANCE_SOURCE", "qualification")
    monkeypatch.setenv("POCKETLAB_RELEASE_ATTESTATION_ROOT_SHA256", pin)
    monkeypatch.setattr(qualification_context, "enabled", lambda: True)
    state, reason = provenance.provenance(
        candidate,
        root,
        commit="a" * 40,
        tag="lite-2026.11.28.663",
        trusted_now=datetime(2026, 11, 28, tzinfo=timezone.utc),
    )
    assert (state, reason) == ("verified", "qualification_provenance_verified")


def test_qualification_provenance_rejects_tampered_subject(tmp_path, monkeypatch):
    root, candidate, pin = _fixture(tmp_path)
    monkeypatch.setenv("POCKETLAB_RELEASE_PROVENANCE_SOURCE", "qualification")
    monkeypatch.setenv("POCKETLAB_RELEASE_ATTESTATION_ROOT_SHA256", pin)
    monkeypatch.setattr(qualification_context, "enabled", lambda: True)
    (candidate / "dist.zip").chmod(0o600)
    (candidate / "dist.zip").write_bytes(b"tampered")
    state, reason = provenance.provenance(
        candidate,
        root,
        commit="a" * 40,
        tag="lite-2026.11.28.663",
        trusted_now=datetime(2026, 11, 28, tzinfo=timezone.utc),
    )
    assert state == "failed"
    assert reason == "qualification_provenance_subject_digest_mismatch"
