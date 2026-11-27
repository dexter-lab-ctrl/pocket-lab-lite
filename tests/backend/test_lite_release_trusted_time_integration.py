"""Disposable HTTPS signed-time integration qualification.

The service in this test is generated for one test process and uses an
ephemeral Ed25519 signer that is independent from release and recovery keys.
It exercises the actual client transport and ``renew`` path without
provisioning production trusted-time material.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import http.server
import ipaddress
import json
from pathlib import Path
import ssl
import threading

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat, PublicFormat
from cryptography.x509.oid import NameOID

from pocket_lab_test_utils import ensure_runtime_path

ensure_runtime_path()
from api_fastapi.services import lite_release_trusted_time as clock
from api_fastapi.services import lite_release_trust_configuration as config
from api_fastapi.services.lite_lifecycle_contract import canonical_bytes


class _SignedTimeHandler(http.server.BaseHTTPRequestHandler):
    signer: Ed25519PrivateKey
    pin: str

    def do_POST(self) -> None:  # noqa: N802 - stdlib protocol hook
        size = int(self.headers.get("Content-Length", "-1"))
        raw = self.rfile.read(size)
        request = json.loads(raw.decode("utf-8"))
        payload = {
            "schema_version": 1,
            "nonce": request["nonce"],
            "key_id": self.pin,
            "utc": "2026-11-27T12:00:00Z",
            "uncertainty_ms": 25,
        }
        body = canonical_bytes({
            "payload": payload,
            "signature": base64.b64encode(
                self.signer.sign(clock.DOMAIN + canonical_bytes(payload))
            ).decode("ascii"),
        })
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def _certificate(tmp_path: Path) -> tuple[Path, Path]:
    # Keep the TLS transport independent from the Ed25519 trusted-time signer.
    from cryptography.hazmat.primitives.asymmetric import rsa

    tls_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(tls_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(minutes=10))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(tls_key, hashes.SHA256())
    )
    cert_path = tmp_path / "time-service-cert.pem"
    key_path = tmp_path / "time-service-key.pem"
    cert_path.write_bytes(cert.public_bytes(Encoding.PEM))
    key_path.write_bytes(tls_key.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()))
    key_path.chmod(0o600)
    return cert_path, key_path


def test_signed_time_renew_exercises_disposable_https_service(tmp_path, monkeypatch):
    signer = Ed25519PrivateKey.generate()
    public = signer.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    pin = hashlib.sha256(public).hexdigest()
    cert_path, key_path = _certificate(tmp_path)

    handler = type("SignedTimeHandler", (_SignedTimeHandler,), {"signer": signer, "pin": pin})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    server.socket = tls.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    time_root = tmp_path / "time-root"
    time_root.mkdir(mode=0o700)
    key_file = time_root / "time-public-key.bin"
    key_file.write_bytes(public)
    key_file.chmod(0o400)
    samples = iter((1_000, 201_001_000))
    monkeypatch.setenv("POCKETLAB_RELEASE_TRUST_TIME_SOURCE", "signed_challenge")
    monkeypatch.setenv("POCKETLAB_RELEASE_TIME_URL", f"https://127.0.0.1:{server.server_port}/time")
    monkeypatch.setenv("POCKETLAB_RELEASE_TIME_KEY_SHA256", pin)
    monkeypatch.setenv("SSL_CERT_FILE", str(cert_path))
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(cert_path))
    monkeypatch.setattr(config, "BOOT_ID", "integration-boot")
    monkeypatch.setattr(config, "boot_time_ns", lambda: next(samples))

    try:
        now, receipt = clock.renew(time_root)
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()

    assert now.tzinfo == timezone.utc
    assert now >= datetime(2026, 11, 27, 12, 0, 0, 225000, tzinfo=timezone.utc)
    assert now < datetime(2026, 11, 27, 12, 0, 1, tzinfo=timezone.utc)
    assert receipt["clock_source"] == "signed_challenge"
    assert receipt["clock_basis"] == "boottime"
    assert receipt["clock_boot_id"] == "integration-boot"
    assert receipt["clock_source_revision"] == clock.source_revision()
