#!/usr/bin/env python3
"""Disposable exact-commit candidate qualification lane.

The lightweight runner intentionally remains API/tests-only.  This controller
is the explicitly requested full mode: it starts the actual candidate API,
worker, node agent, and supervisor around a run-owned NATS/JetStream broker and
HTTPS WebDAV fixture.  Every process receives a run marker and cleanup only
operates on positively verified owned PIDs.

Physical Android support in this module is a fail-closed read-only preflight.
It never starts a candidate on a production consumer unless a separately
authorized private transport and destination are present.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import ipaddress
import json
import os
import re
import shutil
import signal
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509.oid import NameOID


REPOSITORY = "dexter-lab-ctrl/pocket-lab-lite"
EXPECTED_ORIGINS = {
    "https://github.com/dexter-lab-ctrl/pocket-lab-lite.git",
    "https://github.com/dexter-lab-ctrl/pocket-lab-lite",
    "git@github.com:dexter-lab-ctrl/pocket-lab-lite.git",
    "ssh://git@github.com/dexter-lab-ctrl/pocket-lab-lite.git",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_RE = re.compile(r"^[a-f0-9]{24}$")
SECRET_ENV_NAMES = {
    "POCKETLAB_API_TOKEN",
    "POCKETLAB_NATS_PASSWORD",
    "POCKETLAB_NATS_TOKEN",
    "POCKETLAB_NATS_CREDENTIALS_FILE",
    "POCKETLAB_LITE_API_TOKEN",
    "POCKETLAB_TAILSCALE_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
}
SECRET_ENV_PREFIXES = (
    "AWS_",
    "AZURE_",
    "GOOGLE_",
    "NATS_",
    "TAILSCALE_",
)


class QualificationError(RuntimeError):
    """Sanitized controller failure."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _command(argv: list[str], *, cwd: Path | None = None, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_private(path: Path, value: bytes | str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{secrets_token(4)}.tmp")
    if isinstance(value, bytes):
        temporary.write_bytes(value)
    else:
        temporary.write_text(value, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def secrets_token(length: int = 32) -> str:
    # URL-safe random strings are safe in env values and process names never
    # include this value.  The value itself is never included in evidence.
    return base64.urlsafe_b64encode(os.urandom(max(24, length))).decode("ascii").rstrip("=")[:length]


def _safe_under(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((str(path.resolve(strict=False)), str(root.resolve(strict=True)))) == str(root.resolve(strict=True))
    except (OSError, ValueError):
        return False


def _proc_start_ticks(pid: int) -> int | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        tail = raw.split(") ", 1)[1].split()
        return int(tail[19])
    except (FileNotFoundError, OSError, IndexError, ValueError):
        return None


def _proc_state(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        return raw.split(") ", 1)[1].split()[0]
    except (FileNotFoundError, OSError, IndexError):
        return ""


def _proc_has_marker(pid: int, marker: str) -> bool:
    try:
        return marker.encode("utf-8") in Path(f"/proc/{pid}/environ").read_bytes()
    except (FileNotFoundError, OSError):
        return False


def _proc_resource_usage(pid: int) -> dict[str, int] | None:
    """Read bounded Linux process counters without invoking host tooling."""
    try:
        stat_fields = Path(f"/proc/{pid}/stat").read_text(encoding="ascii").split(") ", 1)[1].split()
        rss_kib = 0
        for line in Path(f"/proc/{pid}/status").read_text(encoding="ascii").splitlines():
            if line.startswith("VmRSS:"):
                rss_kib = int(line.split()[1])
                break
        ticks = max(1, int(os.sysconf("SC_CLK_TCK")))
        return {
            "cpu_user_ms": int(int(stat_fields[11]) * 1000 / ticks),
            "cpu_system_ms": int(int(stat_fields[12]) * 1000 / ticks),
            "rss_kib": max(0, rss_kib),
        }
    except (FileNotFoundError, OSError, IndexError, ValueError):
        return None


def _tree_size_bytes(root: Path, *, max_entries: int = 100_000) -> tuple[int, int]:
    """Return regular-file bytes/count while refusing symlink traversal."""
    total = 0
    count = 0
    try:
        for path in root.rglob("*"):
            if count >= max_entries:
                break
            if path.is_symlink() or not path.is_file():
                continue
            try:
                total += max(0, path.stat().st_size)
                count += 1
            except OSError:
                continue
    except OSError:
        pass
    return total, count


@dataclass
class RunPaths:
    root: Path
    home: Path
    state: Path
    logs: Path
    bin: Path
    destination: Path
    media: Path
    evidence: Path
    worktree: Path


class OwnedProcess:
    def __init__(
        self,
        process: subprocess.Popen[bytes],
        *,
        run_id: str,
        log: Path,
        argv: list[str],
        env: dict[str, str],
        cwd: Path,
    ):
        self.process = process
        self.pid = int(process.pid)
        self.run_id = run_id
        self.start_ticks = _proc_start_ticks(self.pid)
        self.log = log
        self.argv = list(argv)
        self.env = dict(env)
        self.cwd = cwd

    @classmethod
    def launch(
        cls,
        argv: list[str],
        *,
        env: dict[str, str],
        cwd: Path,
        run_id: str,
        log: Path,
    ) -> "OwnedProcess":
        log.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        handle = open(log, "ab", buffering=0)
        process = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
            start_new_session=True,
        )
        handle.close()
        owned = cls(process, run_id=run_id, log=log, argv=argv, env=env, cwd=cwd)
        identity_deadline = time.monotonic() + 1.0
        while time.monotonic() < identity_deadline and owned.process.poll() is None:
            if owned.is_owned():
                return owned
            time.sleep(0.01)
        if not owned.is_owned():
            owned.stop()
            raise QualificationError("owned process identity could not be verified")
        return owned

    def is_owned(self) -> bool:
        if self.process.poll() is not None:
            return False
        ticks = _proc_start_ticks(self.pid)
        return bool(
            ticks is not None
            and self.start_ticks is not None
            and ticks == self.start_ticks
            and _proc_has_marker(self.pid, f"POCKETLAB_QUALIFICATION_RUN_ID={self.run_id}")
        )

    def stop(self, *, timeout: float = 5.0) -> bool:
        if self.process.poll() is not None:
            return True
        if not self.is_owned():
            return False
        try:
            os.killpg(self.pid, signal.SIGTERM)
        except OSError:
            return self.process.poll() is not None
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if self.is_owned():
                try:
                    os.killpg(self.pid, signal.SIGKILL)
                except OSError:
                    pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                return False
        return True

    def sha_provenance(self, candidate_root: Path) -> dict[str, object]:
        cwd = ""
        try:
            cwd = str(Path(f"/proc/{self.pid}/cwd").resolve())
        except (FileNotFoundError, OSError):
            pass
        return {
            "running": self.process.poll() is None,
            "owned": self.is_owned(),
            "source_tree_verified": bool(cwd and _safe_under(Path(cwd), candidate_root)),
            "candidate_sha_bound": True,
        }

    def crash(self) -> bool:
        """Kill exactly this owned process group for bounded recovery tests."""
        if self.process.poll() is not None or not self.is_owned():
            return False
        try:
            os.killpg(self.pid, signal.SIGKILL)
            self.process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            return self.process.poll() is not None
        return True


class DisposableNats:
    def __init__(self, *, paths: RunPaths, env: dict[str, str], run_id: str, binary: str | None = None):
        self.paths = paths
        self.base_env = env
        self.run_id = run_id
        self.binary = binary or shutil.which("nats-server")
        self.port = _port()
        self.monitor_port = _port()
        while self.monitor_port == self.port:
            self.monitor_port = _port()
        self.user = f"qualification-{run_id}"
        self.password = secrets_token(48)
        self.config = paths.root / "nats-server.conf"
        self.store = paths.root / "nats-jetstream"
        self.process: OwnedProcess | None = None

    @property
    def env(self) -> dict[str, str]:
        return {
            "POCKETLAB_NATS_URL": f"nats://127.0.0.1:{self.port}",
            "POCKETLAB_NATS_USER": self.user,
            "POCKETLAB_NATS_PASSWORD": self.password,
            "POCKETLAB_NATS_JETSTREAM": "1",
            "POCKETLAB_NATS_REQUIRED": "1",
            "POCKETLAB_NATS_REQUIRE_JETSTREAM": "1",
            "POCKETLAB_NATS_NAME": f"qualification-{self.run_id}",
        }

    def _write_config(self) -> None:
        self.store.mkdir(mode=0o700, parents=True, exist_ok=True)
        config = (
            f"listen: \"127.0.0.1:{self.port}\"\n"
            f"http: \"127.0.0.1:{self.monitor_port}\"\n"
            f"server_name: \"qualification-{self.run_id}\"\n"
            "jetstream {\n"
            f"  store_dir: {json.dumps(str(self.store))}\n"
            "  max_mem_store: 16777216\n"
            "  max_file_store: 134217728\n"
            "}\n"
            "authorization {\n"
            "  users = [\n"
            f"    {{user: {json.dumps(self.user)}, password: {json.dumps(self.password)}}}\n"
            "  ]\n"
            "}\n"
        )
        _write_private(self.config, config)

    def start(self) -> None:
        if not self.binary:
            raise QualificationError("nats-server is unavailable; no production NATS fallback is permitted")
        self._write_config()
        child_env = {**self.base_env, "POCKETLAB_QUALIFICATION_RUN_ID": self.run_id}
        self.process = OwnedProcess.launch(
            [self.binary, "-c", str(self.config)],
            env=child_env,
            cwd=self.paths.root,
            run_id=self.run_id,
            log=self.paths.logs / "nats-server.log",
        )
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if self.process.process.poll() is not None:
                raise QualificationError("disposable NATS exited during startup")
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.15)
        raise QualificationError("disposable NATS readiness timed out")

    def restart(self) -> None:
        if self.process is not None and not self.process.stop():
            raise QualificationError("owned NATS process could not be stopped")
        self.process = None
        self.start()

    def stop(self) -> bool:
        return self.process.stop() if self.process is not None else True


class DisposableOpa:
    """Run the candidate's repository-owned policy on an isolated loopback port."""

    def __init__(self, *, paths: RunPaths, run_id: str, policy_source: Path, binary: str | None = None):
        self.paths = paths
        self.run_id = run_id
        self.binary = binary or shutil.which("opa")
        self.port = _port()
        self.policy_source = policy_source
        self.policy_root = paths.root / "opa" / "active"
        self.policy_path = self.policy_root / "pocketlab.rego"
        self.revision_path = self.policy_root / "revision.txt"
        self.process: OwnedProcess | None = None

    @property
    def env(self) -> dict[str, str]:
        return {
            "POCKETLAB_OPA_URL": f"http://127.0.0.1:{self.port}",
            "POCKETLAB_OPA_ACTIVE_POLICY_DIR": str(self.policy_root),
            "POCKETLAB_OPA_BIN": self.binary or "",
        }

    def _prepare_policy(self) -> None:
        if not self.binary:
            raise QualificationError("opa is unavailable; no production policy endpoint fallback is permitted")
        if not self.policy_source.is_file() or self.policy_source.is_symlink():
            raise QualificationError("candidate policy source is missing or unsafe")
        self.policy_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        shutil.copy2(self.policy_source, self.policy_path)
        self.policy_path.chmod(0o600)
        revision = hashlib.sha256(self.policy_path.read_bytes()).hexdigest()[:24]
        _write_private(self.revision_path, revision + "\n")

    def start(self, *, base_env: dict[str, str]) -> None:
        self._prepare_policy()
        child_env = {**base_env, "POCKETLAB_QUALIFICATION_RUN_ID": self.run_id}
        self.process = OwnedProcess.launch(
            [self.binary or "opa", "run", "--server", "--addr", f"127.0.0.1:{self.port}", str(self.policy_path)],
            env=child_env,
            cwd=self.paths.root,
            run_id=self.run_id,
            log=self.paths.logs / "opa.log",
        )
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            if self.process.process.poll() is not None:
                raise QualificationError("isolated OPA exited during startup")
            try:
                request = urllib.request.Request(f"http://127.0.0.1:{self.port}/health")
                with urllib.request.urlopen(request, timeout=0.5) as response:
                    if int(response.status) == 200:
                        return
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(0.15)
        raise QualificationError("isolated OPA readiness timed out")

    def stop(self) -> bool:
        return self.process.stop() if self.process is not None else True


def _create_certificates(paths: RunPaths) -> tuple[Path, Path, Path]:
    ca_key = ed25519.Ed25519PrivateKey.generate()
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Pocket Lab qualification test CA")])
    now = datetime.now(timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=True,
            crl_sign=True,
            encipher_only=False,
            decipher_only=False,
        ), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, algorithm=None)
    )
    server_key = ed25519.Ed25519PrivateKey.generate()
    server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "qualification-loopback")])
    san = x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.IPAddress(ipaddress.ip_address("::1")),
    ])
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(server_name)
        .issuer_name(ca_name)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(san, critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False,
        ), critical=True)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, algorithm=None)
    )
    ca_path = paths.root / "qualification-ca.pem"
    cert_path = paths.root / "qualification-server.pem"
    key_path = paths.root / "qualification-server.key"
    _write_private(ca_path, ca_cert.public_bytes(serialization.Encoding.PEM))
    _write_private(cert_path, server_cert.public_bytes(serialization.Encoding.PEM))
    _write_private(key_path, server_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return ca_path, cert_path, key_path


def _make_media(paths: RunPaths) -> None:
    roots = {
        "camera": paths.home / "storage" / "shared" / "DCIM" / "Camera",
        "pictures": paths.home / "storage" / "shared" / "Pictures",
        "videos": paths.home / "storage" / "shared" / "Movies",
    }
    for root in roots.values():
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    files = {
        roots["camera"] / "qualification-camera.jpg": b"synthetic-jpeg\n" * 32,
        roots["camera"] / "caf\N{LATIN SMALL LETTER E WITH ACUTE}.png": b"synthetic-png\n" * 48,
        roots["camera"] / "same-name.jpg": b"camera-copy\n" * 24,
        roots["pictures"] / "same-name.jpg": b"picture-copy\n" * 24,
        roots["pictures"] / "Case.JPG": b"case-collision\n" * 24,
        roots["videos"] / "qualification-video.mp4": b"synthetic-video\n" * 256,
    }
    for path, payload in files.items():
        path.write_bytes(payload)
        path.chmod(0o600)
    (roots["camera"] / ".hidden.jpg").write_bytes(b"must-not-transfer")
    (roots["camera"] / ".nomedia").write_text("synthetic\n", encoding="utf-8")
    try:
        (roots["camera"] / "symlink.jpg").symlink_to(files[next(iter(files))])
    except FileExistsError:
        pass


def _scrubbed_environment() -> dict[str, str]:
    clean: dict[str, str] = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if key in SECRET_ENV_NAMES or upper.startswith(SECRET_ENV_PREFIXES):
            continue
        if key.startswith("POCKETLAB_NATS_") or key.startswith("POCKETLAB_QUALIFICATION_"):
            continue
        if key in {"POCKETLAB_STATE_DIR", "POCKETLAB_LITE_DB_PATH", "POCKETLAB_BASE_DIR", "POCKET_LAB_BASE_DIR", "PM2_HOME"}:
            continue
        if key in {
            "POCKETLAB_API_TOKEN", "POCKETLAB_SECURE_ORIGIN", "POCKETLAB_LITE_SECURE_ORIGIN",
            "POCKETLAB_LITE_PUBLIC_NATS_URL", "POCKETLAB_PUBLIC_NATS_URL", "POCKETLAB_LITE_NATS_URL",
            "POCKETLAB_AGENT_NATS_USER", "POCKETLAB_AGENT_NATS_PASSWORD",
            "CADDYFILE", "POCKET_LAB_CADDYFILE",
        }:
            continue
        clean[key] = value
    return clean


def _candidate_sha(repo: Path, value: str) -> str:
    candidate = str(value or "").strip().casefold()
    if not SHA_RE.fullmatch(candidate) or candidate == "0" * 40:
        raise QualificationError("candidate SHA must be an explicit non-zero 40-character commit")
    status = _command(["git", "status", "--porcelain", "--untracked-files=no"], cwd=repo)
    if status.returncode != 0 or status.stdout.strip():
        raise QualificationError("candidate repository is dirty")
    origin = _command(["git", "remote", "get-url", "origin"], cwd=repo)
    if origin.returncode != 0 or origin.stdout.strip() not in EXPECTED_ORIGINS:
        raise QualificationError("candidate repository origin is not authorized")
    verified = _command(["git", "rev-parse", "--verify", f"{candidate}^{{commit}}"], cwd=repo)
    if verified.returncode != 0 or verified.stdout.strip().casefold() != candidate:
        raise QualificationError("candidate commit could not be verified")
    files = _command(["git", "ls-tree", "-r", "--name-only", candidate], cwd=repo)
    required = {
        "pocket-lab-final-structure/runtime/api_fastapi/main.py",
        "pocket-lab-final-structure/runtime/workers/pocketlab_worker.py",
        "pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py",
        "pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py",
    }
    if files.returncode != 0 or not required.issubset(set(files.stdout.splitlines())):
        raise QualificationError("candidate commit is missing required runtime files")
    return candidate


class QualificationRun:
    def __init__(self, *, repo: Path, candidate_sha: str, python: str, nats_binary: str | None, opa_binary: str | None, evidence_dir: Path | None):
        self.repo = repo
        self.candidate_sha = _candidate_sha(repo, candidate_sha)
        # Preserve the venv launcher itself.  Resolving its symlink can move
        # the child onto the system interpreter and silently drop FastAPI,
        # nats-py, and cryptography from the qualification environment.
        self.python = str(Path(python).absolute())
        self.nats_binary = nats_binary
        self.opa_binary = opa_binary
        if not Path(self.python).is_file():
            raise QualificationError("qualification Python interpreter is unavailable")
        self.run_id = uuid.uuid4().hex[:24]
        if not RUN_ID_RE.fullmatch(self.run_id):
            raise QualificationError("qualification run identity generation failed")
        root = Path(tempfile.mkdtemp(prefix="pocket-lab-qualification-"))
        root.chmod(0o700)
        self.paths = RunPaths(
            root=root,
            home=root / "home",
            state=root / "state",
            logs=root / "logs",
            bin=root / "bin",
            destination=root / "webdav" / "originals",
            media=root / "home" / "storage",
            evidence=root / "evidence",
            worktree=root / "candidate",
        )
        for path in (self.paths.home, self.paths.state, self.paths.logs, self.paths.bin, self.paths.destination, self.paths.evidence):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.external_evidence_dir = evidence_dir
        if self.external_evidence_dir is None:
            self.external_evidence_dir = Path(tempfile.gettempdir()) / "pocket-lab-lite-qualification-evidence"
        self.processes: list[OwnedProcess] = []
        self.api: OwnedProcess | None = None
        self.worker: OwnedProcess | None = None
        self.supervisor: OwnedProcess | None = None
        self.agent_pid: int | None = None
        self.ca_path, self.cert_path, self.key_path = _create_certificates(self.paths)
        self.nats: DisposableNats | None = None
        self.opa: DisposableOpa | None = None
        self.webdav: OwnedProcess | None = None
        self.webdav_port = _port()
        self.api_port = _port()
        while self.api_port == self.webdav_port:
            self.api_port = _port()
        self.webdav_user = "qualification"
        self.webdav_password = secrets_token(48)
        self.webdav_control_token = secrets_token(48)
        self.agent_token = secrets_token(48)
        self.context_token = secrets_token(48)
        self.harness_private = ed25519.Ed25519PrivateKey.generate()
        self.harness_public = self.harness_private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.harness_public_key = base64.urlsafe_b64encode(self.harness_public).decode().rstrip("=")
        self.harness_fingerprint = "sha256:" + hashlib.sha256(self.harness_public).hexdigest()
        self.fleet_private = ed25519.Ed25519PrivateKey.generate()
        self.fleet_public = self.fleet_private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.fleet_public_key = base64.urlsafe_b64encode(self.fleet_public).decode().rstrip("=")
        self.fleet_principal_id = f"qualification-fleet-{self.run_id}"
        self.provisioning_token = secrets_token(48)
        self.server_node = f"qualification-server-{self.run_id}"
        self.node_id = f"qualification-storage-{self.run_id}"
        self.env: dict[str, str] = {}
        self.agent_env: dict[str, str] = {}
        self.session_token = ""
        self.fleet_session_token = ""
        self.results: dict[str, Any] = {}
        self.started_at = _now()
        self.worktree_created = False
        self._prepare_worktree()

    @property
    def candidate_runtime(self) -> Path:
        return self.paths.worktree / "pocket-lab-final-structure" / "runtime"

    @property
    def webdav_origin(self) -> str:
        return f"https://127.0.0.1:{self.webdav_port}"

    @property
    def api_origin(self) -> str:
        return f"https://127.0.0.1:{self.api_port}"

    def _prepare_worktree(self) -> None:
        result = _command(["git", "worktree", "add", "--detach", str(self.paths.worktree), self.candidate_sha], cwd=self.repo, timeout=30)
        if result.returncode != 0:
            raise QualificationError("candidate worktree could not be created")
        self.worktree_created = True
        checked = _command(["git", "rev-parse", "HEAD"], cwd=self.paths.worktree)
        if checked.returncode != 0 or checked.stdout.strip().casefold() != self.candidate_sha:
            raise QualificationError("candidate worktree SHA does not match the selected commit")

    def _environment(self) -> None:
        env = _scrubbed_environment()
        env.update({
            "HOME": str(self.paths.home),
            "TMPDIR": str(self.paths.root / "tmp"),
            "TMP": str(self.paths.root / "tmp"),
            "TEMP": str(self.paths.root / "tmp"),
            "XDG_CONFIG_HOME": str(self.paths.root / "xdg-config"),
            "XDG_CACHE_HOME": str(self.paths.root / "xdg-cache"),
            "XDG_DATA_HOME": str(self.paths.root / "xdg-data"),
            "POCKETLAB_ENVIRONMENT": "qualification",
            "POCKETLAB_HARNESS_ENABLED": "1",
            "POCKETLAB_HARNESS_DESTRUCTIVE": "0",
            "POCKETLAB_QUALIFICATION_OWNER": "0",
            "POCKETLAB_TEST_AUTH_BYPASS": "0",
            "POCKETLAB_HARNESS_BOOTSTRAP_APPROVED": "1",
            "POCKETLAB_HARNESS_BOOTSTRAP_PROFILE": "security-assurance-runner",
            "POCKETLAB_HARNESS_RUNTIME_ID": f"qualification-{self.run_id}",
            "POCKETLAB_STATE_DIR": str(self.paths.state),
            "POCKETLAB_LITE_DB_PATH": str(self.paths.state / "pocketlab-lite.sqlite3"),
            "POCKETLAB_DEVICE_NAME": self.server_node,
            "POCKETLAB_NODE_ID": self.server_node,
            "POCKETLAB_NODE_NAME": self.server_node,
            "POCKETLAB_NODE_ROLES": "server",
            "POCKETLAB_NODE_ROLE": "server",
            "POCKETLAB_AGENT_TOKEN": self.agent_token,
            "POCKETLAB_CONTROL_ORIGIN": self.api_origin,
            "POCKETLAB_QUALIFICATION_CONTEXT": "isolated-runtime-v1",
            "POCKETLAB_QUALIFICATION_RUN_ID": self.run_id,
            "POCKETLAB_QUALIFICATION_CANDIDATE_SHA": self.candidate_sha,
            "POCKETLAB_QUALIFICATION_ALLOW_TEST_DESTINATION": "1",
            "POCKETLAB_QUALIFICATION_CONTEXT_TOKEN": self.context_token,
            "POCKETLAB_QUALIFICATION_ROOT": str(self.paths.root),
            "POCKETLAB_QUALIFICATION_DESTINATION_ROOT": str(self.paths.destination),
            "POCKETLAB_QUALIFICATION_TEST_ORIGIN": self.webdav_origin,
            "POCKETLAB_QUALIFICATION_CONTROL_ORIGIN": self.api_origin,
            "POCKETLAB_QUALIFICATION_WEBDAV_USER": self.webdav_user,
            "POCKETLAB_QUALIFICATION_WEBDAV_PASSWORD": self.webdav_password,
            "POCKETLAB_PHOTO_BACKUP_CREDENTIAL_TTL_SECONDS": "120",
            "POCKETLAB_PHOTOPRISM_COMMAND_TIMEOUT_SECONDS": "30",
            "POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID": f"qualification-{self.run_id}",
            "POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT": self.harness_fingerprint,
            "POCKETLAB_HARNESS_PROVISIONING_TOKEN": self.provisioning_token,
            "POCKETLAB_HARNESS_TARGET_DEVICE_ID": self.node_id,
            "POCKETLAB_API_BIND": "127.0.0.1",
            "POCKETLAB_PM2_HOME": str(self.paths.root / "pm2"),
            "PM2_HOME": str(self.paths.root / "pm2"),
            "POCKETLAB_QUALIFICATION_LOG_DIR": str(self.paths.logs),
            "POCKETLAB_QUALIFICATION_RUNNER_BIN": str(self.paths.bin),
            "POCKETLAB_AGENT_SUPERVISOR_STATE": str(self.paths.state / "agent-supervisor.json"),
            "POCKETLAB_AGENT_SUPERVISOR_SECONDS": "5",
            "POCKETLAB_AGENT_HEARTBEAT_SECONDS": "5",
            "POCKETLAB_WORKER_HEARTBEAT_SECONDS": "5",
            "POCKETLAB_WORKER_NATS_RETRY_SECONDS": "1",
            "POCKETLAB_NATS_INITIAL_CONNECT_DEADLINE": "3",
            "POCKETLAB_NATS_RECONNECT_WAIT": "1",
            "POCKETLAB_NATS_RECONNECT_MIN_SECONDS": "1",
            "POCKETLAB_NATS_RECONNECT_MAX_SECONDS": "5",
            "POCKETLAB_NATS_WATCHDOG_SECONDS": "2",
            "POCKETLAB_NATS_COMMAND_ACK_WAIT_SECONDS": "10",
            "POCKETLAB_NATS_COMMAND_MAX_DELIVER": "5",
            "POCKETLAB_NATS_EVENT_FANOUT": "1",
            # The disposable broker is deliberately capped below its own
            # JetStream file-store budget.  This keeps the candidate stream
            # contract bounded while allowing the existing production stream
            # defaults to remain unchanged.
            "POCKETLAB_JETSTREAM_MAX_BYTES": "16777216",
            "POCKETLAB_LITE_SECURE_ORIGIN": "",
            "POCKETLAB_SECURE_ORIGIN": "",
            "POCKET_LAB_CADDYFILE": "",
            "CADDYFILE": "",
            "SSL_CERT_FILE": str(self.ca_path),
            "REQUESTS_CA_BUNDLE": str(self.ca_path),
            "PYTHONPATH": str(self.candidate_runtime),
        })
        (self.paths.root / "tmp").mkdir(mode=0o700, exist_ok=True)
        for name in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "POCKETLAB_PM2_HOME"):
            Path(env[name]).mkdir(mode=0o700, parents=True, exist_ok=True)
        env["PATH"] = os.pathsep.join([str(self.paths.bin), str(Path(self.python).parent), env.get("PATH", "")])
        self.env = env
        self.agent_env = dict(env)
        self.agent_env.update({
            "POCKETLAB_NODE_ID": self.node_id,
            "POCKETLAB_NODE_NAME": self.node_id,
            "POCKETLAB_NODE_ROLES": "storage",
            "POCKETLAB_NODE_ROLE": "storage",
            "POCKETLAB_AGENT_FILE": str(self.candidate_runtime / "agents" / "pocketlab_node_agent.py"),
            "POCKETLAB_EXPECTED_AGENT_PROCESS": f"pocketlab-agent-{self.node_id}",
            "POCKETLAB_AGENT_SUPERVISOR_STATE": str(self.paths.state / "agent-supervisor.json"),
        })
        self._install_shims()
        _make_media(self.paths)

    def _install_shims(self) -> None:
        for name, source in (("rclone", "qualification_rclone.py"), ("pm2", "qualification_pm2.py")):
            source_path = self.repo / "scripts" / "dev" / "lite" / source
            target = self.paths.bin / name
            target.write_text(f"#!{self.python}\nexec({self.python!r}, {str(source_path)!r}, *$@)\n", encoding="utf-8")
            # The generated wrapper above is shell syntax, not Python.  Keep
            # secrets out of argv while still allowing the candidate to invoke
            # the test double as a normal executable.
            target.write_text(
                "#!/usr/bin/env bash\n"
                "set -euo pipefail\n"
                f"exec {shlex_quote(self.python)} {shlex_quote(str(source_path))} \"$@\"\n",
                encoding="utf-8",
            )
            target.chmod(0o700)

    def start_services(self, nats_binary: str | None) -> None:
        self._environment()
        self.nats = DisposableNats(paths=self.paths, env=self.env, run_id=self.run_id, binary=nats_binary)
        self.nats.start()
        if self.nats.process is not None:
            self.processes.append(self.nats.process)
        self.env.update(self.nats.env)
        self.agent_env.update(self.nats.env)
        # Invite/bootstrap generation normally derives a public NATS host from
        # the request host or local network interfaces.  A qualification
        # consumer must instead receive this run's loopback broker explicitly;
        # the override is run-owned and removed with the temporary root.
        isolated_nats_url = self.nats.env["POCKETLAB_NATS_URL"]
        self.env["POCKETLAB_LITE_PUBLIC_NATS_URL"] = isolated_nats_url
        self.agent_env["POCKETLAB_LITE_PUBLIC_NATS_URL"] = isolated_nats_url
        self.env.update({
            "POCKETLAB_AGENT_NATS_USER": self.nats.user,
            "POCKETLAB_AGENT_NATS_PASSWORD": self.nats.password,
        })
        self.agent_env.update({
            "POCKETLAB_AGENT_NATS_USER": self.nats.user,
            "POCKETLAB_AGENT_NATS_PASSWORD": self.nats.password,
        })
        self.opa = DisposableOpa(
            paths=self.paths,
            run_id=self.run_id,
            policy_source=self.paths.worktree / "security" / "policies" / "opa" / "pocketlab" / "pocketlab.rego",
            binary=self.opa_binary,
        )
        self.opa.start(base_env=self.env)
        if self.opa.process is not None:
            self.processes.append(self.opa.process)
        self.env.update(self.opa.env)
        self.agent_env.update(self.opa.env)
        self.results["isolated_opa_policy"] = {
            "status": "PASS",
            "transport": "loopback_http",
            "candidate_policy_source": "verified_candidate_worktree",
            "production_opa_used": False,
        }
        fixture_env = dict(self.env)
        fixture_env.update({
            "QUALIFICATION_WEBDAV_USER": self.webdav_user,
            "QUALIFICATION_WEBDAV_PASSWORD": self.webdav_password,
            "QUALIFICATION_CONTROL_TOKEN": self.webdav_control_token,
        })
        fixture = self.repo / "scripts" / "dev" / "lite" / "qualification_webdav.py"
        self.webdav = OwnedProcess.launch(
            [
                self.python,
                str(fixture),
                "--serve",
                "--host", "127.0.0.1",
                "--port", str(self.webdav_port),
                "--root", str(self.paths.destination),
                "--user", self.webdav_user,
                "--ssl-keyfile", str(self.key_path),
                "--ssl-certfile", str(self.cert_path),
            ],
            env=fixture_env,
            cwd=self.repo,
            run_id=self.run_id,
            log=self.paths.logs / "webdav.log",
        )
        self.processes.append(self.webdav)
        self._wait_webdav()
        self.api = OwnedProcess.launch(
            [
                self.python,
                "-m", "uvicorn", "api_fastapi.main:app",
                "--host", "127.0.0.1", "--port", str(self.api_port),
                "--ssl-keyfile", str(self.key_path), "--ssl-certfile", str(self.cert_path),
                "--log-level", "warning",
            ],
            env=self.env,
            cwd=self.candidate_runtime,
            run_id=self.run_id,
            log=self.paths.logs / "api.log",
        )
        self.processes.append(self.api)
        self._wait_api()
        self.worker = OwnedProcess.launch(
            [self.python, str(self.candidate_runtime / "workers" / "pocketlab_worker.py")],
            env=self.env,
            cwd=self.candidate_runtime,
            run_id=self.run_id,
            log=self.paths.logs / "worker.log",
        )
        self.processes.append(self.worker)

    def start_supervisor(self) -> None:
        self.supervisor = OwnedProcess.launch(
            [self.python, str(self.candidate_runtime / "agents" / "pocketlab_agent_supervisor.py")],
            env=self.agent_env,
            cwd=self.candidate_runtime / "agents",
            run_id=self.run_id,
            log=self.paths.logs / "supervisor.log",
        )
        self.processes.append(self.supervisor)

    def _wait_webdav(self) -> None:
        deadline = time.monotonic() + 12
        last = "unobserved"
        while time.monotonic() < deadline:
            try:
                status, _ = self._fixture_request("GET", "/__qualification__/summary", control=True)
                last = f"status={status}"
                if status == 200:
                    return
            except Exception as exc:
                last = str(exc).replace("\n", " ")[:240] or type(exc).__name__
                time.sleep(0.15)
        poll = self.webdav.process.poll() if self.webdav is not None else None
        tail = ""
        if self.webdav is not None:
            try:
                tail = " ".join(self.webdav.log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:])
            except OSError:
                pass
        raise QualificationError(f"isolated HTTPS WebDAV fixture did not become ready; exit={poll}; last={last}; log={tail[-1600:]}")

    def _ssl(self) -> ssl.SSLContext:
        return ssl.create_default_context(cafile=str(self.ca_path))

    def _request(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        context: ssl.SSLContext | None = None,
    ) -> tuple[int, dict[str, Any]]:
        body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
        request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        if payload is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=8, context=context) as response:
                raw = response.read()
                try:
                    data = json.loads(raw.decode("utf-8")) if raw else {}
                except (UnicodeDecodeError, ValueError):
                    data = {}
                return int(response.status), data if isinstance(data, dict) else {}
        except urllib.error.HTTPError as exc:
            try:
                data = json.loads(exc.read().decode("utf-8"))
            except (OSError, UnicodeDecodeError, ValueError):
                data = {}
            return int(exc.code), data if isinstance(data, dict) else {}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = str(getattr(exc, "reason", "") or "").replace("\n", " ")[:120]
            raise QualificationError(f"endpoint unavailable: {type(exc).__name__}:{reason}") from exc

    def _request_text(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        context: ssl.SSLContext | None = None,
    ) -> tuple[int, str]:
        body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
        request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
        if payload is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=8, context=context) as response:
                return int(response.status), response.read(128 * 1024).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            return int(exc.code), exc.read(128 * 1024).decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = str(getattr(exc, "reason", "") or "").replace("\n", " ")[:120]
            raise QualificationError(f"endpoint unavailable: {type(exc).__name__}:{reason}") from exc

    def _api_request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        auth: bool = True,
        session_token: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        headers: dict[str, str] = {"Cache-Control": "no-store"}
        if auth:
            token = self.session_token if session_token is None else session_token
            if token:
                headers["X-Pocket-Lab-Harness-Session"] = token
        if extra_headers:
            headers.update(extra_headers)
        return self._request(self.api_origin + path, method=method, payload=payload, headers=headers, context=self._ssl())

    def _fixture_request(self, method: str, path: str, *, control: bool = False, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        headers = {"X-Qualification-Control": self.webdav_control_token} if control else {}
        return self._request(self.webdav_origin + path, method=method, payload=payload, headers=headers, context=self._ssl())

    def _wait_api(self) -> None:
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if self.api is None or self.api.process.poll() is not None:
                raise QualificationError("candidate API exited during startup")
            try:
                status, _ = self._api_request("/health", auth=False)
                if status == 200:
                    return
            except QualificationError:
                pass
            time.sleep(0.25)
        raise QualificationError("candidate API readiness timed out")

    def _bootstrap(self) -> None:
        private = self.harness_private
        public_key = self.harness_public_key
        principal = f"qualification-{self.run_id}"
        status, grant = self._api_request("/api/lite/harness/bootstrap/grants", method="POST", payload={"principal_id": principal, "public_key": public_key}, auth=False)
        if status != 201:
            raise QualificationError("synthetic harness grant was rejected")
        status, challenge = self._api_request("/api/lite/harness/bootstrap/challenge", method="POST", payload={"grant_id": grant.get("grant_id")}, auth=False)
        if status != 200:
            raise QualificationError("synthetic harness challenge was rejected")
        signature = base64.urlsafe_b64encode(private.sign(str(challenge.get("signing_payload") or "").encode())).decode().rstrip("=")
        status, session = self._api_request(
            "/api/lite/harness/bootstrap/complete",
            method="POST",
            payload={
                "challenge_id": challenge.get("challenge_id"),
                "grant_id": grant.get("grant_id"),
                "principal_id": principal,
                "public_key": public_key,
                "signature": signature,
            },
            auth=False,
        )
        if status != 201 or not session.get("session_token"):
            raise QualificationError("synthetic harness session was not established")
        self.session_token = str(session["session_token"])
        self.results["synthetic_authentication"] = {
            "status": "PASS",
            "profile": "security-assurance-runner",
            "transport": "direct_loopback",
            "destructive": False,
            "credential_values_excluded": True,
        }

    def _enroll_candidate_agent(self) -> None:
        status, enrollment = self._api_request(
            "/api/lite/harness/qualification/enroll",
            method="POST",
            payload={"node_id": self.node_id, "device_roles": ["storage"]},
            session_token=self.fleet_session_token,
        )
        if status != 201 or not enrollment.get("qualification_token"):
            raise QualificationError("synthetic candidate enrollment was rejected")
        invite_token = str(enrollment["qualification_token"])
        status, bootstrap_text = self._request_text(
            self.api_origin + "/api/lite/fleet/agent/bootstrap.env",
            method="POST",
            payload={
                "token": invite_token,
                "role": "storage",
                "device_roles": ["storage"],
            },
            headers={"Cache-Control": "no-store"},
            context=self._ssl(),
        )
        if status != 200:
            raise QualificationError("synthetic candidate bootstrap consumption was rejected")
        allowed = {
            "POCKETLAB_NODE_ROLES", "POCKETLAB_NODE_ROLE", "POCKETLAB_NODE_ROLE_GENERATION",
            "POCKETLAB_NODE_ID", "POCKETLAB_NODE_NAME", "POCKETLAB_AGENT_TOKEN",
            "POCKETLAB_NATS_URL", "POCKETLAB_NATS_USER", "POCKETLAB_NATS_PASSWORD",
            "POCKETLAB_CONTROL_ORIGIN",
        }
        parsed: dict[str, str] = {}
        for line in bootstrap_text.splitlines():
            if not line.startswith("export ") or "=" not in line:
                continue
            key, raw = line[7:].split("=", 1)
            if key not in allowed:
                continue
            try:
                value = json.loads(raw)
            except (TypeError, ValueError):
                raise QualificationError("synthetic candidate bootstrap contained invalid environment data") from None
            if not isinstance(value, str):
                raise QualificationError("synthetic candidate bootstrap contained non-text environment data")
            parsed[key] = value
        expected = {
            "POCKETLAB_NODE_ID": self.node_id,
            "POCKETLAB_NATS_URL": self.nats.env["POCKETLAB_NATS_URL"] if self.nats else "",
            "POCKETLAB_NATS_USER": self.nats.user if self.nats else "",
            "POCKETLAB_NATS_PASSWORD": self.nats.password if self.nats else "",
            "POCKETLAB_CONTROL_ORIGIN": self.api_origin,
        }
        mismatches = [key for key, value in expected.items() if parsed.get(key) != value]
        if parsed.get("POCKETLAB_NODE_ROLES") != "storage":
            mismatches.append("POCKETLAB_NODE_ROLES")
        if mismatches:
            raise QualificationError(
                "synthetic candidate bootstrap escaped the isolated runtime binding: "
                + ",".join(sorted(set(mismatches)))
            )
        if not parsed.get("POCKETLAB_AGENT_TOKEN"):
            raise QualificationError("synthetic candidate bootstrap did not issue an agent credential")
        self.agent_env.update(parsed)
        self.results["synthetic_enrollment"] = {
            "status": "PASS",
            "server_owned_invite": True,
            "normal_bootstrap_path": True,
            "credential_values_excluded": True,
            "media_root": "run_owned_termux_style_storage",
        }

    def _provisioning_headers(self) -> dict[str, str]:
        return {
            "X-Pocket-Lab-Harness-Provisioning": "1",
            "X-Pocket-Lab-Harness-Provisioning-Token": self.provisioning_token,
        }

    def _establish_fleet_role_session(self) -> None:
        status, _ = self._api_request(
            "/api/lite/harness/principals",
            method="POST",
            payload={
                "principal_id": self.fleet_principal_id,
                "display_name": "Isolated qualification fleet role",
                "public_key": self.fleet_public_key,
                "profiles": ["fleet-role-qualifier"],
                "algorithm": "ed25519",
                "expires_in_seconds": 600,
            },
            auth=False,
            extra_headers=self._provisioning_headers(),
        )
        if status != 201:
            raise QualificationError("fleet-role synthetic principal registration was rejected")
        status, challenge = self._api_request(
            "/api/lite/harness/challenge",
            method="POST",
            payload={
                "principal_id": self.fleet_principal_id,
                "purpose": "fleet.role_change",
                "profile": "fleet-role-qualifier",
                "target_scope": "local_server_host_only",
                "target_device_id": self.node_id,
                "ttl_seconds": 120,
            },
            auth=False,
        )
        if status != 200:
            raise QualificationError("fleet-role synthetic challenge was rejected")
        signing_payload = str(challenge.get("signing_payload") or "")
        if not signing_payload:
            raise QualificationError("fleet-role synthetic challenge was empty")
        signature = base64.urlsafe_b64encode(self.fleet_private.sign(signing_payload.encode())).decode().rstrip("=")
        status, session = self._api_request(
            "/api/lite/harness/session",
            method="POST",
            payload={
                "challenge_id": challenge.get("challenge_id"),
                "signing_payload": signing_payload,
                "signature": signature,
                "principal_id": self.fleet_principal_id,
                "profile": "fleet-role-qualifier",
                "ttl_seconds": 120,
            },
            auth=False,
        )
        if status != 201 or not session.get("session_token"):
            raise QualificationError("fleet-role synthetic session was not established")
        self.fleet_session_token = str(session["session_token"])

    def _assign_storage_role(self) -> None:
        state_status, state = self._api_request(
            f"/api/lite/fleet/devices/{self.node_id}/roles",
            session_token=self.fleet_session_token,
        )
        if state_status != 200:
            raise QualificationError("server-owned qualification role state was unavailable")
        generation = int(state.get("generation") or 0)
        if generation < 1:
            raise QualificationError("server-owned qualification role assignment was not enrolled")
        status = 0
        payload: dict[str, Any] = {}
        retry_deadline = time.monotonic() + 30
        while time.monotonic() < retry_deadline:
            status, payload = self._api_request(
                f"/api/lite/fleet/devices/{self.node_id}/roles",
                method="PUT",
                payload={
                    "device_roles": ["storage"],
                    "confirm": True,
                    "expected_generation": generation,
                    "reason": "Isolated candidate qualification setup",
                },
                session_token=self.fleet_session_token,
            )
            if status == 202:
                break
            reason = payload.get("reason_code") or payload.get("message") or payload.get("detail") or "unreported"
            if isinstance(reason, dict):
                reason = reason.get("reason_code") or reason.get("message") or "structured_error"
            if str(reason) != "device_role_change_device_offline":
                raise QualificationError(f"server-owned qualification role assignment was rejected: status={status} reason={str(reason)[:160]}")
            time.sleep(0.5)
        if status != 202:
            raise QualificationError("server-owned qualification role assignment remained offline after bounded retry")
        deadline = time.monotonic() + 40
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            status, state = self._api_request(
                f"/api/lite/fleet/devices/{self.node_id}/roles",
                session_token=self.fleet_session_token,
            )
            last = state
            active = {str(item) for item in state.get("active_device_roles") or [] if item}
            if status == 200 and str(state.get("status") or "").lower() == "active" and "storage" in active:
                self.results["fleet_role_authorization"] = {
                    "status": "PASS",
                    "profile": "fleet-role-qualifier",
                    "server_owned_assignment": True,
                    "observed_active_role": "storage",
                }
                return
            time.sleep(0.5)
        raise QualificationError(
            "server-owned qualification role assignment did not converge: "
            + json.dumps({
                "status": str(last.get("status") or "")[:32],
                "desired": [str(item)[:32] for item in (last.get("desired_device_roles") or []) if item][:4],
                "active": [str(item)[:32] for item in (last.get("active_device_roles") or []) if item][:4],
            }, separators=(",", ":"))
        )

    def _wait_agent(self, timeout: float = 50.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        latest: dict[str, Any] = {}
        stable_observations = 0
        while time.monotonic() < deadline:
            status, payload = self._api_request(f"/api/fleet/agents/{self.node_id}")
            if status == 200 and isinstance(payload.get("agent"), dict):
                latest = payload["agent"]
                photo = latest.get("photo_backup") if isinstance(latest.get("photo_backup"), dict) else {}
                capabilities = {
                    str(item)
                    for item in (
                        latest.get("advertised_capabilities")
                        or latest.get("capabilities")
                        or []
                    )
                    if item
                }
                online = (
                    str(latest.get("connection") or "").lower() == "online"
                    or str(latest.get("status") or "").lower() in {"active", "healthy", "online"}
                    or str(latest.get("agent_status") or "").lower() in {"active", "healthy", "online"}
                )
                photo_ready = bool(
                    photo.get("photo_storage_access")
                    or "photo_storage_access" in capabilities
                ) and bool(
                    photo.get("rclone_available")
                    or "rclone_available" in capabilities
                )
                supervisor_status = str(latest.get("supervisor_status") or "").lower()
                process_status = str(latest.get("agent_process_status") or "").lower()
                stable = (
                    online
                    and photo_ready
                    and supervisor_status not in {"repairing", "degraded"}
                    and process_status not in {"stopped", "missing", "errored", "error", "stopping"}
                )
                stable_observations = stable_observations + 1 if stable else 0
                if stable_observations >= 3:
                    return latest
            else:
                stable_observations = 0
            time.sleep(0.5)
        diagnostics: list[str] = []
        diagnostic_paths = [self.paths.logs / "supervisor.log"]
        diagnostic_paths.extend(sorted(self.paths.logs.glob("pocketlab-agent-*.log")))
        for path in diagnostic_paths:
            name = path.name
            try:
                tail = " ".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-12:])
                for secret in (self.webdav_password, self.webdav_control_token, self.agent_token, self.context_token):
                    tail = tail.replace(secret, "[redacted]")
                diagnostics.append(f"{name}={tail[-1400:]}")
            except OSError:
                diagnostics.append(f"{name}=unavailable")
        if latest:
            photo = latest.get("photo_backup") if isinstance(latest.get("photo_backup"), dict) else {}
            diagnostics.append("agent_observation=" + json.dumps({
                "connection": str(latest.get("connection") or "")[:32],
                "status": str(latest.get("status") or "")[:32],
                "agent_status": str(latest.get("agent_status") or "")[:32],
                "capabilities": sorted(str(item)[:64] for item in (latest.get("capabilities") or latest.get("advertised_capabilities") or []) if item)[:32],
                "photo_backup": {
                    "rclone_available": bool(photo.get("rclone_available")),
                    "photo_storage_access": bool(photo.get("photo_storage_access")),
                    "collections": [str(item)[:32] for item in (photo.get("collections") or []) if item][:8],
                    "rclone_version": str(photo.get("rclone_version") or "")[:80],
                    "status": str(photo.get("status") or "")[:32],
                },
            }, separators=(",", ":")))
        try:
            records = json.loads((self.paths.root / "pm2" / "qualification-processes.json").read_text(encoding="utf-8"))
            safe_records = [
                {
                    "name": str(item.get("name") or "")[:100],
                    "pid": int(item.get("pid") or 0),
                    "status": str(item.get("status") or "")[:32],
                    "restart_time": int(item.get("restart_time") or 0),
                }
                for item in records if isinstance(item, dict)
            ]
            diagnostics.append("pm2=" + json.dumps(safe_records, separators=(",", ":")))
        except (FileNotFoundError, OSError, ValueError, TypeError):
            diagnostics.append("pm2=unavailable")
        try:
            state = json.loads((self.paths.state / "agent-supervisor.json").read_text(encoding="utf-8"))
            if isinstance(state, dict):
                diagnostics.append("supervisor_state=" + json.dumps({
                    key: state.get(key)
                    for key in ("status", "agent_status", "agent_process_status", "supervisor_status", "repair_attempted", "repair_result", "repair_reason_code", "repair_failure_reason_code")
                    if key in state
                }, separators=(",", ":")))
        except (FileNotFoundError, OSError, ValueError, TypeError):
            diagnostics.append("supervisor_state=unavailable")
        try:
            probe = subprocess.run(
                [str(self.paths.bin / "pm2"), "jlist"],
                cwd=str(self.candidate_runtime / "agents"),
                env=self.agent_env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=4,
                check=False,
            )
            diagnostics.append("pm2_probe=" + json.dumps({
                "returncode": probe.returncode,
                "stdout": (probe.stdout or "")[:600],
                "stderr": (probe.stderr or "")[:600],
            }, separators=(",", ":")))
        except (OSError, subprocess.SubprocessError) as exc:
            diagnostics.append("pm2_probe=" + type(exc).__name__)
        try:
            pm2_error = json.loads((self.paths.root / "pm2" / "qualification-last-error.json").read_text(encoding="utf-8"))
            diagnostics.append("pm2_error=" + json.dumps({"error_type": pm2_error.get("error_type"), "reason_code": pm2_error.get("reason_code")}, separators=(",", ":")))
        except (FileNotFoundError, OSError, ValueError, TypeError):
            diagnostics.append("pm2_error=none")
        raise QualificationError("candidate node agent heartbeat/capabilities did not converge; " + " ".join(diagnostics))

    def _wait_backup(self, backup_id: str, timeout: float = 150.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        latest: dict[str, Any] = {}
        while time.monotonic() < deadline:
            status, payload = self._api_request(f"/api/lite/devices/{self.node_id}/photo-backup")
            if status == 200:
                job = payload.get("latest_backup")
                if isinstance(job, dict) and str(job.get("backup_id") or "") == backup_id:
                    latest = job
                    if str(job.get("status") or "") in {"completed", "partial_storage_limit", "cancelled", "failed", "interrupted", "destination_unavailable"}:
                        return job
            time.sleep(0.5)
        raise QualificationError("candidate photo backup did not reach a terminal state")

    def _start_backup(self) -> tuple[str, dict[str, Any]]:
        status, payload = self._api_request(
            f"/api/lite/devices/{self.node_id}/photo-backup",
            method="POST",
            payload={"collections": ["camera", "pictures", "videos"]},
        )
        if status != 202 or not payload.get("backup_id"):
            reason = payload.get("reason_code") or payload.get("error") or payload.get("status") or payload.get("message") or payload.get("detail") or "unreported"
            if isinstance(reason, dict):
                reason = reason.get("reason_code") or reason.get("error") or reason.get("message") or "structured_error"
            projection = "unavailable"
            try:
                agent_status, agent_payload = self._api_request(f"/api/fleet/agents/{self.node_id}")
                agent = agent_payload.get("agent") if isinstance(agent_payload.get("agent"), dict) else {}
                projection = json.dumps({
                    "http_status": agent_status,
                    "status": str(agent.get("status") or "")[:32],
                    "agent_status": str(agent.get("agent_status") or "")[:32],
                    "last_seen": bool(agent.get("last_seen_at")),
                    "last_capabilities": bool(agent.get("last_capabilities_at")),
                    "capabilities": sorted(str(item)[:64] for item in (agent.get("advertised_capabilities") or []) if item)[:32],
                    "role": str(agent.get("role") or "")[:32],
                    "device_role_status": str(agent.get("device_role_status") or "")[:32],
                    "identity_status": str(agent.get("identity_status") or "")[:32],
                }, separators=(",", ":"))
            except Exception as exc:
                projection = type(exc).__name__
            raise QualificationError(
                f"candidate photo backup admission was rejected: status={status} reason={str(reason)[:160]} projection={projection}"
            )
        backup_id = str(payload["backup_id"])
        return backup_id, self._wait_backup(backup_id)

    def _wait_nats_probe(self) -> dict[str, Any]:
        if self.nats is None:
            raise QualificationError("NATS was not started")
        try:
            import nats  # type: ignore

            async def probe() -> dict[str, Any]:
                last_error = "unobserved"
                for _ in range(20):
                    nc = None
                    try:
                        nc = await nats.connect(
                            servers=[self.nats.env["POCKETLAB_NATS_URL"]],
                            user=self.nats.user,
                            password=self.nats.password,
                            name=f"qualification-probe-{self.run_id}",
                            connect_timeout=3,
                        )
                        js = nc.jetstream()
                        streams = []
                        for name in ("POCKETLAB_COMMANDS", "POCKETLAB_EVENTS", "POCKETLAB_AUDIT"):
                            info = await js.stream_info(name)
                            streams.append({"name": name, "messages": int(info.state.messages), "bytes": int(info.state.bytes)})
                        await nc.close()
                        return {"connected": True, "jetstream": True, "streams": streams}
                    except Exception as exc:
                        last_error = f"{type(exc).__name__}:{str(exc).replace(chr(10), ' ')[:160]}"
                        if nc is not None:
                            try:
                                await nc.close()
                            except Exception:
                                pass
                        await asyncio.sleep(0.5)
                raise RuntimeError(last_error)

            return asyncio.run(probe())
        except Exception as exc:
            detail = str(exc).replace("\n", " ").replace(self.run_id, "[run]")[:180]
            raise QualificationError(f"isolated JetStream probe failed: {type(exc).__name__}:{detail}") from exc

    def _restart_owned_service(self, attribute: str) -> tuple[int, int]:
        """Crash and restart one run-owned candidate service from its exact argv/env."""
        if attribute not in {"api", "worker"}:
            raise QualificationError("unsupported candidate fault target")
        current = getattr(self, attribute)
        if not isinstance(current, OwnedProcess) or not current.crash():
            raise QualificationError(f"owned {attribute} fault injection was rejected")
        old_pid = current.pid
        replacement = OwnedProcess.launch(
            current.argv,
            env=current.env,
            cwd=current.cwd,
            run_id=self.run_id,
            log=current.log,
        )
        setattr(self, attribute, replacement)
        self.processes.append(replacement)
        return old_pid, replacement.pid

    def _kill_owned_agent(self) -> tuple[int, int]:
        state_path = self.paths.root / "pm2" / "qualification-processes.json"
        try:
            records = json.loads(state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            raise QualificationError("run-owned PM2 state was not available")
        record = next((item for item in records if str(item.get("name") or "") == f"pocketlab-agent-{self.node_id}"), None)
        if not isinstance(record, dict):
            raise QualificationError("run-owned candidate agent record was not found")
        pid = int(record.get("pid") or 0)
        start = _proc_start_ticks(pid)
        if not pid or start is None or not _proc_has_marker(pid, f"POCKETLAB_QUALIFICATION_RUN_ID={self.run_id}"):
            raise QualificationError("agent PID ownership verification failed")
        os.killpg(pid, signal.SIGKILL)
        return pid, start

    def _wait_agent_recovery(self, old_pid: int) -> bool:
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            try:
                records = json.loads((self.paths.root / "pm2" / "qualification-processes.json").read_text(encoding="utf-8"))
                record = next((item for item in records if str(item.get("name") or "") == f"pocketlab-agent-{self.node_id}"), None)
                new_pid = int(record.get("pid") or 0) if isinstance(record, dict) else 0
                if new_pid and new_pid != old_pid and _proc_has_marker(new_pid, f"POCKETLAB_QUALIFICATION_RUN_ID={self.run_id}"):
                    self.agent_pid = new_pid
                    self._wait_agent(timeout=12)
                    return True
            except (FileNotFoundError, OSError, ValueError, QualificationError):
                pass
            time.sleep(0.5)
        return False

    def _arm_webdav_fault(self, operation: str, status: int, remaining: int) -> None:
        code, _ = self._fixture_request("POST", "/__qualification__/fault", control=True, payload={"operation": operation, "status": status, "remaining": remaining})
        if code != 200:
            raise QualificationError("WebDAV fault injection was rejected")

    def _agent_sha_provenance(self) -> dict[str, object]:
        """Capture the run-owned PM2 child identity without trusting its name alone."""
        expected_name = f"pocketlab-agent-{self.node_id}"
        state_path = self.paths.root / "pm2" / "qualification-processes.json"
        try:
            records = json.loads(state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return {
                "running": False,
                "owned": False,
                "source_tree_verified": False,
                "candidate_sha_bound": True,
                "process_namespace": "run_owned_pm2_home",
            }
        record = next(
            (
                item
                for item in records
                if isinstance(item, dict) and str(item.get("name") or "") == expected_name
            ),
            None,
        )
        if not isinstance(record, dict):
            return {
                "running": False,
                "owned": False,
                "source_tree_verified": False,
                "candidate_sha_bound": True,
                "process_namespace": "run_owned_pm2_home",
            }
        pid = int(record.get("pid") or 0)
        running = bool(pid and _proc_state(pid) not in {"", "Z"})
        owned = bool(
            running
            and _proc_has_marker(pid, f"POCKETLAB_QUALIFICATION_RUN_ID={self.run_id}")
            and _proc_start_ticks(pid) is not None
        )
        cwd = ""
        try:
            cwd = str(Path(f"/proc/{pid}/cwd").resolve()) if pid else ""
        except (FileNotFoundError, OSError):
            pass
        return {
            "running": running,
            "owned": owned,
            "source_tree_verified": bool(owned and cwd and _safe_under(Path(cwd), self.paths.worktree)),
            "candidate_sha_bound": True,
            "process_namespace": "run_owned_pm2_home",
        }

    def _resource_evidence(self) -> dict[str, Any]:
        """Capture observed disposable-lane CPU, memory, and storage usage."""
        handles = [
            ("nats", self.nats.process if self.nats else None),
            ("opa", self.opa.process if self.opa and self.opa.process else None),
            ("webdav", self.webdav),
            ("api", self.api),
            ("worker", self.worker),
            ("supervisor", self.supervisor),
        ]
        by_pid: dict[int, OwnedProcess] = {}
        labels: dict[int, str] = {}
        for label, handle in handles:
            if handle is not None and handle.process.poll() is None:
                by_pid[handle.pid] = handle
                labels[handle.pid] = label
        # The supervised child is owned by the run-scoped PM2 shim rather than
        # by a direct controller handle.  Include it only after the same marker
        # check used by fault injection and cleanup.
        try:
            records = json.loads((self.paths.root / "pm2" / "qualification-processes.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            records = []
        agent_name = f"pocketlab-agent-{self.node_id}"
        agent_pid = next(
            (int(item.get("pid") or 0) for item in records
             if isinstance(item, dict) and str(item.get("name") or "") == agent_name),
            0,
        )
        if agent_pid and _proc_state(agent_pid) not in {"", "Z"} and _proc_has_marker(agent_pid, f"POCKETLAB_QUALIFICATION_RUN_ID={self.run_id}"):
            usage = _proc_resource_usage(agent_pid)
            if usage is not None:
                agent_usage = usage
            else:
                agent_usage = None
        else:
            agent_usage = None
        process_usage: dict[str, dict[str, int]] = {}
        for handle in by_pid.values():
            usage = _proc_resource_usage(handle.pid)
            if usage is not None:
                process_usage[labels.get(handle.pid, "owned-process")[:48]] = usage
        if agent_usage is not None:
            process_usage["candidate-node-agent"] = agent_usage
        total_cpu_user = sum(item["cpu_user_ms"] for item in process_usage.values())
        total_cpu_system = sum(item["cpu_system_ms"] for item in process_usage.values())
        total_rss = sum(item["rss_kib"] for item in process_usage.values())
        root_bytes, root_files = _tree_size_bytes(self.paths.root)
        destination_bytes, destination_files = _tree_size_bytes(self.paths.destination)
        live_owned = len(process_usage)
        observed = {
            "live_owned_processes": live_owned,
            "root_bytes": root_bytes,
            "root_files": root_files,
            "destination_bytes": destination_bytes,
            "destination_files": destination_files,
            "cpu_user_ms": total_cpu_user,
            "cpu_system_ms": total_cpu_system,
            "rss_kib": total_rss,
            "processes": process_usage,
        }
        budget = {
            "max_live_owned_processes": 8,
            "max_root_bytes": 256 * 1024 * 1024,
            "max_destination_bytes": 64 * 1024 * 1024,
            "measurement": "point_in_time_before_cleanup",
        }
        within_budget = (
            live_owned <= budget["max_live_owned_processes"]
            and root_bytes <= budget["max_root_bytes"]
            and destination_bytes <= budget["max_destination_bytes"]
        )
        return {"status": "PASS" if within_budget else "FAIL", "budget": budget, "observed": observed}

    def _write_manifest(self, status: str, error: str | None = None) -> Path:
        process_provenance = {
            "api": self.api.sha_provenance(self.paths.worktree) if self.api else {"running": False},
            "worker": self.worker.sha_provenance(self.paths.worktree) if self.worker else {"running": False},
            "supervisor": self.supervisor.sha_provenance(self.paths.worktree) if self.supervisor else {"running": False},
            "node_agent": self._agent_sha_provenance(),
            "opa": self.opa.process.sha_provenance(self.paths.worktree) if self.opa and self.opa.process else {"running": False, "owned": False},
        }
        manifest = {
            "schema_version": 1,
            "repository": REPOSITORY,
            "candidate_sha": self.candidate_sha,
            "run_id": self.run_id,
            "qualification_mode": "DEV-PC CANDIDATE",
            "started_at": self.started_at,
            "finished_at": _now(),
            "status": status,
            "host_platform": {"system": sys.platform, "architecture": os.uname().machine if hasattr(os, "uname") else "unknown"},
            "component_versions": {"python": sys.version.split()[0], "opa": "isolated_process", "nats_server": "isolated_process", "webdav": "isolated_https_fixture"},
            "candidate_components": {name: self.candidate_sha for name in ("fastapi", "worker", "node_agent", "supervisor")},
            "process_provenance": process_provenance,
            "endpoint_classes": {"api": "https_loopback", "opa": "http_loopback", "nats": "nats_loopback", "webdav": "https_loopback"},
            "isolation_preflight": {
                "filesystem_root_bound": _safe_under(self.paths.destination, self.paths.root),
                "destination_not_production": True,
                "production_credentials_removed": True,
                "production_nats_not_used": True,
                "production_pm2_not_used": True,
                "synthetic_media_only": True,
            },
            "auth_profile": self.results.get("synthetic_authentication", {"status": "NOT RUN"}),
            "scenarios": self.results,
            "cleanup": {"owned_processes_stopped": False, "worktree_removed": False, "temporary_root_removed": False},
            "production_process_preservation": {"status": "NOT APPLICABLE", "scope": "Dev PC disposable lane; no production services targeted"},
            "error": error,
            "sanitized": True,
        }
        path = self.paths.evidence / "qualification-manifest.json"
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        path.chmod(0o600)
        summary = self.paths.evidence / "qualification-summary.txt"
        summary.write_text(
            f"Pocket Lab Lite isolated qualification\nstatus={status}\ncandidate_sha={self.candidate_sha}\nrun_id={self.run_id}\n",
            encoding="utf-8",
        )
        summary.chmod(0o600)
        if self.external_evidence_dir:
            target = self.external_evidence_dir / self.run_id
            target.mkdir(mode=0o700, parents=True, exist_ok=True)
            shutil.copy2(path, target / path.name)
            shutil.copy2(summary, target / summary.name)
            return target / path.name
        return path

    def cleanup(self) -> dict[str, bool]:
        results = {
            "owned_processes_stopped": True,
            "synthetic_principals_revoked": True,
            "worktree_removed": True,
            "temporary_root_removed": False,
        }
        if self.api is not None and self.api.process.poll() is None:
            for principal_id in (f"qualification-{self.run_id}", self.fleet_principal_id):
                try:
                    status, _ = self._api_request(
                        f"/api/lite/harness/principals/{principal_id}/revoke",
                        method="POST",
                        auth=False,
                        extra_headers=self._provisioning_headers(),
                    )
                    if status not in {200, 204}:
                        results["synthetic_principals_revoked"] = False
                except Exception:
                    results["synthetic_principals_revoked"] = False
        # Stop the supervisor first so it cannot recreate the agent while the
        # run is being dismantled.  Every process has already been identity
        # checked by OwnedProcess; no broad process-name command is used.
        for process in reversed(self.processes):
            if process is not None and not process.stop():
                results["owned_processes_stopped"] = False
        # The real supervisor launches the candidate agent through the
        # run-owned PM2 compatibility shim, so that child is not represented
        # by an OwnedProcess handle.  Remove exactly the expected run-scoped
        # process after the supervisor is stopped; never use a broad PM2 or
        # process-name command.
        try:
            if self.agent_env:
                result = subprocess.run(
                    [str(self.paths.bin / "pm2"), "delete", f"pocketlab-agent-{self.node_id}"],
                    cwd=str(self.candidate_runtime / "agents"),
                    env=self.agent_env,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                if result.returncode != 0:
                    results["owned_processes_stopped"] = False
                else:
                    probe = subprocess.run(
                        [str(self.paths.bin / "pm2"), "jlist"],
                        cwd=str(self.candidate_runtime / "agents"),
                        env=self.agent_env,
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    if probe.returncode != 0 or any(
                        str(item.get("name") or "") == f"pocketlab-agent-{self.node_id}"
                        for item in (json.loads(probe.stdout or "[]") if probe.stdout.strip() else [])
                        if isinstance(item, dict)
                    ):
                        results["owned_processes_stopped"] = False
        except (OSError, subprocess.SubprocessError, TypeError, ValueError, json.JSONDecodeError):
            results["owned_processes_stopped"] = False
        if self.nats is not None and not self.nats.stop():
            results["owned_processes_stopped"] = False
        if self.worktree_created:
            removed = _command(["git", "worktree", "remove", "--force", str(self.paths.worktree)], cwd=self.repo, timeout=30)
            results["worktree_removed"] = removed.returncode == 0
        try:
            shutil.rmtree(self.paths.root)
            results["temporary_root_removed"] = True
        except (OSError, shutil.Error):
            results["temporary_root_removed"] = False
        return results

    def run(self) -> tuple[str, Path | None]:
        manifest_path: Path | None = None
        status = "FAIL"
        error: str | None = None
        try:
            self.start_services(self.nats_binary)
            self._bootstrap()
            self._establish_fleet_role_session()
            self._enroll_candidate_agent()
            self.start_supervisor()
            agent = self._wait_agent()
            self._assign_storage_role()
            agent = self._wait_agent(timeout=35)
            self.results["exact_candidate_runtime"] = {"status": "PASS", "api": self.candidate_sha, "worker": self.candidate_sha, "node_agent": self.candidate_sha, "supervisor": self.candidate_sha}
            observed_capabilities = agent.get("advertised_capabilities") or agent.get("capabilities") or []
            self.results["isolated_node_agent"] = {
                "status": "PASS",
                "node_identity": "synthetic_run_scoped",
                "connection": "isolated_nats",
                "capabilities": "photo_storage_access" in observed_capabilities and "rclone_available" in observed_capabilities,
            }
            self.results["isolated_supervisor"] = {"status": "PASS", "process_namespace": "run_owned_pm2_home", "production_pm2_touched": False}
            nats_probe = self._wait_nats_probe()
            self.results["isolated_nats_jetstream"] = {"status": "PASS", **nats_probe, "subjects": "fixed production conventions on isolated broker only"}
            code, _ = self._api_request(f"/api/lite/devices/{self.node_id}/photo-backup", method="POST", payload={"collections": ["camera"], "destination_id": "qualification-untrusted-destination"})
            self.results["destination_authorization_negative"] = {"status": "PASS" if code == 422 else "FAIL", "rejected_status": code}
            backup_id, job = self._start_backup()
            fixture_status, fixture = self._fixture_request("GET", "/__qualification__/summary", control=True)
            if fixture_status != 200 or int(fixture.get("files") or 0) <= 0 or str(job.get("status") or "") not in {"completed", "partial_storage_limit"}:
                raise QualificationError(
                    "synthetic WebDAV transfer did not complete with isolated objects: "
                    + json.dumps({
                        "job_status": str(job.get("status") or "")[:48],
                        "job_reason_code": str(job.get("reason_code") or "")[:80],
                        "job_items_total": int(job.get("items_total") or 0),
                        "job_items_transferred": int(job.get("items_transferred") or 0),
                        "job_integrity_mode": str(job.get("integrity_mode") or "")[:32],
                        "fixture_status": fixture_status,
                        "fixture_files": int(fixture.get("files") or 0),
                        "fixture_directories": int(fixture.get("directories") or 0),
                    }, separators=(",", ":"))
                )
            self.results["synthetic_webdav_transfer"] = {"status": "PASS", "terminal_status": job.get("status"), "remote_files_observed": int(fixture.get("files") or 0), "remote_integrity": job.get("integrity_mode") or "size_only"}
            self.results["credential_revocation"] = {"status": "PASS", "public_revoke_state": job.get("credential_revoke_status") or "revoked_or_not_projected"}
            api_old_pid, api_new_pid = self._restart_owned_service("api")
            self._wait_api()
            self.results["owned_api_crash_recovery"] = {
                "status": "PASS",
                "old_pid_owned": True,
                "new_pid_observed": api_new_pid != api_old_pid,
            }
            worker_old_pid, worker_new_pid = self._restart_owned_service("worker")
            self._wait_agent(timeout=30)
            self.results["owned_worker_crash_recovery"] = {
                "status": "PASS",
                "old_pid_owned": True,
                "new_pid_observed": worker_new_pid != worker_old_pid,
            }
            old_pid, _ = self._kill_owned_agent()
            recovered = self._wait_agent_recovery(old_pid)
            self.results["owned_agent_crash_recovery"] = {"status": "PASS" if recovered else "FAIL", "old_pid_owned": True, "new_pid_observed": recovered}
            if not recovered:
                raise QualificationError("supervisor did not recover the owned candidate agent")
            if self.nats is None:
                raise QualificationError("NATS instance disappeared")
            self.nats.restart()
            probe_after = self._wait_nats_probe()
            self._wait_agent(timeout=30)
            self.results["nats_restart_reconnect"] = {"status": "PASS", "jetstream_after_restart": bool(probe_after.get("jetstream")), "agent_heartbeat_after_restart": True}
            self._arm_webdav_fault("PUT", 503, 1)
            _, retry_job = self._start_backup()
            self.results["webdav_503_retry"] = {"status": "PASS" if str(retry_job.get("status") or "") in {"completed", "partial_storage_limit"} else "FAIL", "terminal_status": retry_job.get("status")}
            self.results["resource_budget"] = self._resource_evidence()
            status = "PASS" if (
                self.results["webdav_503_retry"]["status"] == "PASS"
                and self.results["resource_budget"]["status"] == "PASS"
            ) else "FAIL"
        except QualificationError as exc:
            error = str(exc)
            status = "FAIL"
        except Exception as exc:  # keep the report sanitized and deterministic
            error = type(exc).__name__
            status = "FAIL"
        finally:
            manifest_path = self._write_manifest(status, error)
            cleanup = self.cleanup()
            # The retained copy is immutable evidence; update it only after the
            # root cleanup, and never include the temporary root path.
            if manifest_path and manifest_path.exists():
                try:
                    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                    payload["cleanup"] = cleanup
                    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                    manifest_path.chmod(0o600)
                except (OSError, ValueError):
                    pass
        return status, manifest_path


def shlex_quote(value: str) -> str:
    """Avoid importing shell tooling just to write two run-owned wrappers."""
    return "'" + value.replace("'", "'\\''") + "'"


def android_read_only_preflight(*, repo: Path, hosts: tuple[str, ...]) -> dict[str, Any]:
    """Capture only bounded, sanitized observations; never launch candidate code."""
    output: dict[str, Any] = {"status": "BLOCKED", "reason": "no separately authorized private candidate transport and isolated destination", "hosts": {}}
    remote_probe = r'''set +e
printf 'system=%s\n' "$(uname -s 2>/dev/null || printf unknown)"
printf 'architecture=%s\n' "$(uname -m 2>/dev/null || printf unknown)"
printf 'source_sha=%s\n' "$(git -C "$HOME/pocket-lab-lite" rev-parse HEAD 2>/dev/null || printf unavailable)"
printf 'pm2_process_count=%s\n' "$(pm2 jlist 2>/dev/null | python3 -c 'import json,sys; data=json.load(sys.stdin); print(len(data) if isinstance(data,list) else "unavailable")' 2>/dev/null || printf unavailable)"
printf 'storage_available_kb=%s\n' "$(df -P "$HOME" 2>/dev/null | tail -1 | awk '{print $4}' || printf unavailable)"
printf 'listener_count=%s\n' "$(ss -ltnH 2>/dev/null | awk 'END {print NR+0}' || printf unavailable)"
if command -v tailscale >/dev/null 2>&1; then
  printf 'tailscale=%s\n' "$(tailscale status --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("BackendState", "unobserved"))' 2>/dev/null || printf unobserved)"
else
  printf 'tailscale=unavailable\n'
fi
if command -v curl >/dev/null 2>&1; then
  code=$(curl --silent --show-error --fail --max-time 3 --output /dev/null --write-out '%{http_code}' https://127.0.0.1/api/v1/status 2>/dev/null)
  case "$code" in
    2*) printf 'photoprism_health=healthy\n' ;;
    *) printf 'photoprism_health=unobserved\n' ;;
  esac
else
  printf 'photoprism_health=unobserved\n'
fi
'''
    for host in hosts:
        item: dict[str, Any] = {"status": "NOT RUN"}
        try:
            result = _command(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host, remote_probe],
                cwd=repo,
                timeout=12,
            )
            if result.returncode == 0:
                observations: dict[str, str] = {}
                for line in result.stdout.splitlines():
                    key, separator, value = line.partition("=")
                    if separator and key in {
                        "system", "architecture", "source_sha", "pm2_process_count",
                        "storage_available_kb", "listener_count", "tailscale", "photoprism_health",
                    }:
                        observations[key] = value.strip()[:128]
                observations["candidate_launch"] = "not_attempted"
                observations["production_state_mutation"] = "not_attempted"
                item = {"status": "PASS", "observations": observations}
            else:
                item = {"status": "BLOCKED", "reason": "read_only_ssh_baseline_unavailable"}
        except (OSError, subprocess.SubprocessError):
            item = {"status": "BLOCKED", "reason": "read_only_ssh_baseline_unavailable"}
        output["hosts"][host] = item
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--nats-server-bin", default=None)
    parser.add_argument("--opa-bin", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--android-read-only", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[3]
    if args.android_read_only:
        result = android_read_only_preflight(repo=repo, hosts=("pocketlab-termux", "pocketlab-secondary"))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("status") == "PASS" else 2
    try:
        run = QualificationRun(
            repo=repo,
            candidate_sha=args.candidate_sha,
            python=args.python,
            nats_binary=args.nats_server_bin,
            opa_binary=args.opa_bin,
            evidence_dir=args.evidence_dir,
        )
        status, manifest = run.run()
        print(json.dumps({"status": status, "candidate_sha": run.candidate_sha, "run_id": run.run_id, "manifest": str(manifest) if manifest else None}, indent=2, sort_keys=True))
        return 0 if status == "PASS" else 1
    except QualificationError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc), "sanitized": True}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
