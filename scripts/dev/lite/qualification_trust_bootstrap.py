#!/usr/bin/env python3
"""Disposable trust bootstrap and owner runner for lifecycle qualification.

This module composes the existing release preparation, signing, release
worker and trusted-time clients.  It never provisions production roots,
publishes a release, or writes lifecycle rows directly.  The local HTTP
servers are loopback-only, run-owned, and intended only for an explicitly
armed ``POCKETLAB_ENVIRONMENT=qualification`` context.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import http.server
import ipaddress
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "pocket-lab-final-structure" / "runtime"
PREPARE = ROOT / "scripts" / "dev" / "lite" / "prepare_trusted_release_candidate.py"
SIGN = ROOT / "scripts" / "dev" / "lite" / "sign_trusted_release_candidate.py"
sys.path.insert(0, str(RUNTIME))

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from api_fastapi.services.lite_lifecycle_contract import canonical_bytes
from api_fastapi.services.lite_release_trusted_time import DOMAIN as TRUSTED_TIME_DOMAIN


# Used only for generating a short-lived local TLS certificate.
_RSA_PRIVATE_KEY = rsa
QUALIFICATION_WORKFLOW = ".github/workflows/release-dist.yml"
PROVENANCE_SCHEMA = "pocketlab.qualification-provenance/v1"
PROVENANCE_ROOT_SCHEMA = "pocketlab.qualification-provenance-root/v1"
PROVENANCE_DOMAIN = b"PocketLab qualification provenance v1\n"
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _utc_after(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write(path: Path, raw: bytes, *, mode: int = 0o600) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.unlink(missing_ok=True)
    with temporary.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.chmod(mode)
    os.replace(temporary, path)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _public(private: Ed25519PrivateKey) -> bytes:
    return private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _schema_max() -> int:
    versions = []
    for path in (ROOT / "pocket-lab-final-structure" / "runtime" / "api_fastapi" / "db" / "schema").glob("[0-9][0-9][0-9][0-9]_*.sql"):
        try:
            versions.append(int(path.name[:4]))
        except ValueError:
            continue
    if not versions:
        raise RuntimeError("qualification_schema_inventory_empty")
    return max(versions)


def _root_record(private: Ed25519PrivateKey, *, expires: str) -> dict[str, Any]:
    public = _public(private)
    return {
        "schema_version": 1,
        "version": 1,
        "repository": "dexter-lab-ctrl/pocket-lab-lite",
        "workflow": QUALIFICATION_WORKFLOW,
        "role": "release",
        "threshold": 1,
        "keys": [{"keyid": hashlib.sha256(public).hexdigest(), "algorithm": "ed25519", "public_key": _b64(public)}],
        "revoked": [],
        "expires": expires,
        "rotation_keys": [],
        "rotation_threshold": 0,
    }


def _provenance_root(private: Ed25519PrivateKey, *, expires: str) -> dict[str, Any]:
    public = _public(private)
    return {
        "schema": PROVENANCE_ROOT_SCHEMA,
        "repository": "dexter-lab-ctrl/pocket-lab-lite",
        "workflow": QUALIFICATION_WORKFLOW,
        "key_id": hashlib.sha256(public).hexdigest(),
        "algorithm": "ed25519",
        "public_key": _b64(public),
        "expires": expires,
    }


def _certificate(directory: Path) -> tuple[Path, Path]:
    key = _RSA_PRIVATE_KEY.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(minutes=45))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert = directory / "trusted-time-cert.pem"
    key_path = directory / "trusted-time-key.pem"
    _write(cert, certificate.public_bytes(serialization.Encoding.PEM), mode=0o400)
    _write(key_path, key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()), mode=0o600)
    return cert, key_path


def _provenance_bundle(directory: Path, signer: Ed25519PrivateKey, *, commit: str, tag: str) -> None:
    subjects = ["dist.zip", "pocketlab-lite-trust.dsse.json"]
    if (directory / "pocketlab-lite-source.zip").is_file():
        subjects.append("pocketlab-lite-source.zip")
    lines = []
    key_id = hashlib.sha256(_public(signer)).hexdigest()
    for subject in subjects:
        path = directory / subject
        if not path.is_file():
            raise RuntimeError("qualification_provenance_subject_missing")
        signed = {
            "schema": PROVENANCE_SCHEMA,
            "subject": subject,
            "sha256": _sha256(path),
            "source_commit": commit,
            "release_tag": tag,
            "repository": "dexter-lab-ctrl/pocket-lab-lite",
            "workflow": QUALIFICATION_WORKFLOW,
            "key_id": key_id,
        }
        lines.append({**signed, "signature": _b64(signer.sign(PROVENANCE_DOMAIN + canonical_bytes(signed)))})
    _write(directory / "pocketlab-lite-provenance.jsonl", b"\n".join(canonical_bytes(item) for item in lines) + b"\n", mode=0o400)


def bootstrap(*, run_root: Path, assets: Path, tag: str, commit: str, release_port: int, time_port: int) -> dict[str, Any]:
    """Create the exact run-owned trust inputs before service startup."""
    root = (run_root / "state" / "release-trust").resolve()
    candidate = root / "candidate"
    secrets = (run_root / "secrets").resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    candidate.mkdir(mode=0o700)
    secrets.mkdir(mode=0o700)
    expiry = _utc_after(30)

    release_signer = Ed25519PrivateKey.generate()
    provenance_signer = Ed25519PrivateKey.generate()
    time_signer = Ed25519PrivateKey.generate()
    root_record = _root_record(release_signer, expires=expiry)
    provenance_record = _provenance_root(provenance_signer, expires=expiry)
    root_path = root / "root.json"
    attestation_path = root / "qualification-provenance-root.json"
    _write(root_path, canonical_bytes(root_record), mode=0o400)
    _write(attestation_path, canonical_bytes(provenance_record), mode=0o400)
    _write(root / "time-public-key.bin", _public(time_signer), mode=0o400)
    time_private = secrets / "trusted-time-signing.key"
    _write(time_private, time_signer.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()), mode=0o600)
    cert, tls_private = _certificate(secrets)

    names = ["dist.zip", "pocketlab-lite-release.json", "checksums.txt"]
    if (assets / "pocketlab-lite-source.zip").is_file():
        names.append("pocketlab-lite-source.zip")
    for name in names:
        source = assets / name
        if not source.is_file() or source.is_symlink():
            raise RuntimeError("qualification_release_asset_missing")
        _write(candidate / name, source.read_bytes(), mode=0o400)

    metadata = run_root / "trust-metadata"
    expires = _utc_after(20)
    prepared = subprocess.run([
        sys.executable, str(PREPARE), "--assets", str(assets), "--output", str(metadata),
        "--tag", tag, "--commit", commit, "--channel", "stable", "--root-version", "1",
        "--expires", expires, "--schema-min", "1", "--schema-max", str(_schema_max()),
    ], cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180, check=False)
    if prepared.returncode != 0:
        raise RuntimeError("qualification_release_metadata_prepare_failed")
    signing_env = dict(os.environ)
    signing_env["POCKETLAB_RELEASE_PUBLIC_ROOT"] = json.dumps(root_record, sort_keys=True, separators=(",", ":"))
    signing_env["POCKETLAB_RELEASE_SIGNING_SEEDS"] = json.dumps([_b64(release_signer.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))])
    signed = subprocess.run([sys.executable, str(SIGN), str(metadata), str(assets)], cwd=str(ROOT), env=signing_env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180, check=False)
    if signed.returncode != 0:
        raise RuntimeError("qualification_release_metadata_sign_failed")
    for path in metadata.iterdir():
        if path.name in {"pocketlab-lite-capabilities.json", "pocketlab-lite-policy-inventory.json", "pocketlab-lite-migration-inventory.json", "pocketlab-lite-trust.dsse.json"}:
            _write(candidate / path.name, path.read_bytes(), mode=0o400)
    _provenance_bundle(candidate, provenance_signer, commit=commit, tag=tag)
    return {
        "status": "PASS",
        "source": "qualification",
        "root_sha256": _sha256(root_path),
        "attestation_root_sha256": _sha256(attestation_path),
        "time_key_sha256": _sha256(root / "time-public-key.bin"),
        "release_port": int(release_port),
        "time_port": int(time_port),
        "candidate_relative": "state/release-trust/candidate",
        "certificate_relative": "secrets/trusted-time-cert.pem",
        "production_execution": False,
        "sanitized": True,
    }


class _TimeHandler(http.server.BaseHTTPRequestHandler):
    signer: Ed25519PrivateKey
    pin: str

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/time":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "-1"))
            if size <= 0 or size > 4096:
                raise ValueError()
            request = json.loads(self.rfile.read(size).decode("utf-8"))
            nonce = str(request["nonce"])
            if not re.fullmatch(r"[0-9a-f]{64}", nonce):
                raise ValueError()
            payload = {"schema_version": 1, "nonce": nonce, "key_id": self.pin,
                       "utc": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
                       "uncertainty_ms": 25}
            body = canonical_bytes({"payload": payload, "signature": _b64(self.signer.sign(TRUSTED_TIME_DOMAIN + canonical_bytes(payload)))})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ValueError, KeyError, json.JSONDecodeError):
            self.send_error(400)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class _ReleaseHandler(http.server.BaseHTTPRequestHandler):
    assets: Path
    tag: str
    commit: str
    port: int

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/releases":
            entries = []
            for name in ("dist.zip", "checksums.txt", "pocketlab-lite-release.json"):
                path = self.assets / name
                entries.append({"name": name, "size": path.stat().st_size, "browser_download_url": f"http://127.0.0.1:{self.port}/assets/{name}"})
            body = json.dumps([{"tag_name": self.tag, "name": self.tag, "html_url": "", "published_at": datetime.now(timezone.utc).isoformat(), "draft": False, "prerelease": False, "assets": entries}], separators=(",", ":")).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        prefix = "/assets/"
        if not self.path.startswith(prefix) or "/" in self.path[len(prefix):]:
            self.send_error(404)
            return
        name = self.path[len(prefix):]
        if name not in {"dist.zip", "checksums.txt", "pocketlab-lite-release.json"}:
            self.send_error(404)
            return
        path = self.assets / name
        raw = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def serve_time(*, port: int, private_key: Path, cert: Path, tls_key: Path) -> None:
    signer = Ed25519PrivateKey.from_private_bytes(private_key.read_bytes())
    handler = type("QualificationTimeHandler", (_TimeHandler,), {"signer": signer, "pin": hashlib.sha256(_public(signer)).hexdigest()})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", int(port)), handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert), keyfile=str(tls_key))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever()


def serve_release(*, port: int, assets: Path, tag: str, commit: str) -> None:
    handler = type("QualificationReleaseHandler", (_ReleaseHandler,), {"assets": assets.resolve(), "tag": tag, "commit": commit, "port": int(port)})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", int(port)), handler)
    server.serve_forever()


def run_release_check(command_id: str) -> int:
    # The qualification entry point invokes the real release-worker service
    # contract directly.  Keep the role explicit so the worker-only admission
    # fence cannot accidentally inherit the API role from the controller.
    os.environ["POCKETLAB_PROCESS_ROLE"] = "worker"
    from api_fastapi.db.connection import read_connection
    from api_fastapi.services import release_runtime
    result = asyncio.run(release_runtime.run_release_check(command_id, source="manual"))
    with read_connection() as conn:
        observation_row = conn.execute("SELECT state,reason_code,checked_at,release_tag,review_json FROM lite_release_trust_observation WHERE singleton_id=1").fetchone()
        time_row = conn.execute("SELECT trusted_at FROM lite_release_trusted_time WHERE singleton_id=1").fetchone()
    review = {}
    if observation_row and observation_row["review_json"]:
        try:
            review = json.loads(observation_row["review_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            review = {}
    state = str(observation_row["state"] if observation_row else "missing")
    passed = bool(result.get("last_terminal_status") == "succeeded" and state == "historical_evidence" and review.get("provenance") == "verified" and review.get("authenticity") == "verified" and review.get("integrity") == "verified" and time_row)
    payload = {
        "status": "PASS" if passed else "BLOCKED",
        "release_worker": {key: result.get(key) for key in ("status", "phase", "last_terminal_status", "latest_tag", "installed_source_commit", "last_failure_code")},
        "trust_observation": {"state": state, "reason_code": observation_row["reason_code"] if observation_row else "observation_missing", "checked_at": observation_row["checked_at"] if observation_row else None, "release_tag": observation_row["release_tag"] if observation_row else None, "provenance": review.get("provenance"), "authenticity": review.get("authenticity"), "integrity": review.get("integrity"), "clock_source": review.get("clock_source"), "clock_source_revision": review.get("clock_source_revision"), "metadata_sha256": review.get("metadata_sha256"), "source_commit": review.get("source_commit"), "artifact_sha256": review.get("artifact_sha256")},
        "trusted_time": {"trusted_at": time_row["trusted_at"] if time_row else None, "receipt_present": bool(time_row)},
        "production_execution": False,
        "sanitized": True,
    }
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))
    return 0 if passed else 4


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    boot = commands.add_parser("bootstrap")
    boot.add_argument("--run-root", type=Path, required=True)
    boot.add_argument("--assets", type=Path, required=True)
    boot.add_argument("--tag", required=True)
    boot.add_argument("--commit", required=True)
    boot.add_argument("--release-port", type=int, required=True)
    boot.add_argument("--time-port", type=int, required=True)
    time_parser = commands.add_parser("serve-time")
    time_parser.add_argument("--port", type=int, required=True)
    time_parser.add_argument("--private-key", type=Path, required=True)
    time_parser.add_argument("--cert", type=Path, required=True)
    time_parser.add_argument("--tls-key", type=Path, required=True)
    release = commands.add_parser("serve-release")
    release.add_argument("--port", type=int, required=True)
    release.add_argument("--assets", type=Path, required=True)
    release.add_argument("--tag", required=True)
    release.add_argument("--commit", required=True)
    check = commands.add_parser("release-check")
    check.add_argument("--command-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "bootstrap":
            print(json.dumps(bootstrap(run_root=args.run_root.resolve(), assets=args.assets.resolve(), tag=args.tag, commit=args.commit, release_port=args.release_port, time_port=args.time_port), sort_keys=True))
            return 0
        if args.command == "serve-time":
            serve_time(port=args.port, private_key=args.private_key.resolve(), cert=args.cert.resolve(), tls_key=args.tls_key.resolve())
            return 0
        if args.command == "serve-release":
            serve_release(port=args.port, assets=args.assets.resolve(), tag=args.tag, commit=args.commit)
            return 0
        if args.command == "release-check":
            return run_release_check(args.command_id)
    except Exception:
        print(json.dumps({"status": "BLOCKED", "reason_code": "qualification_trust_bootstrap_failed", "sanitized": True}, sort_keys=True))
        return 4
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
