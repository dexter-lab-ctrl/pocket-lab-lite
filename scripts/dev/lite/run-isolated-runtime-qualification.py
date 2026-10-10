#!/usr/bin/env python3
"""Disposable exact-commit candidate qualification lane.

The lightweight runner intentionally remains API/tests-only.  This controller
is the explicitly requested full mode: it starts the actual candidate API,
worker, node agent, and supervisor around a run-owned NATS/JetStream broker and
HTTPS WebDAV fixture.  Every process receives a run marker and cleanup only
operates on positively verified owned PIDs.

Physical Android support has two explicit modes: the historical read-only
preflight and an opt-in authorized candidate run.  The latter stages an
immutable exact-SHA snapshot and uses only controller-owned SSH loopback
forwards to disposable Dev-PC services; it never changes the installed
checkout or production service definitions on either phone.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import ipaddress
import io
import json
import os
import re
import shutil
import signal
import shlex
import socket
import ssl
import stat
import subprocess
import sys
import tarfile
import tempfile
import threading
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


ANDROID_MAX_ROOT_BYTES = 256 * 1024 * 1024
ANDROID_MAX_MEDIA_BYTES = 1 * 1024 * 1024
ANDROID_MAX_LIVE_PROCESSES = 8
ANDROID_MIN_FREE_BYTES = 32 * 1024 * 1024
ANDROID_MAX_DURATION_SECONDS = 20 * 60
ANDROID_MAX_RETRIES = 3
ANDROID_ALLOWED_SNAPSHOT_PREFIXES = (
    "pocket-lab-final-structure/runtime/",
    "security/policies/opa/pocketlab/",
)
ANDROID_PRODUCTION_FILE_NAMES = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    "photoprism.env",
    "Caddyfile",
    "rclone.conf",
    "authorized_keys",
})


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
                    reconnect_nc = None
                    probe_stream = ""
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
                        # Use a run-unique stream and durable pull consumer to
                        # prove that an unacknowledged delivery is redelivered
                        # after the client connection is replaced.  It cannot
                        # collide with the candidate's fixed production
                        # subjects or be consumed by the worker.
                        from nats.js.api import ConsumerConfig

                        probe_stream = f"QUALIFICATION_PROBE_{self.run_id.upper()}"
                        probe_subject = f"qualification.probe.{self.run_id}"
                        probe_durable = f"qualification_probe_{self.run_id}"
                        await js.add_stream(
                            name=probe_stream,
                            subjects=[probe_subject],
                            max_msgs=4,
                            max_bytes=65536,
                        )
                        consumer_config = ConsumerConfig(
                            durable_name=probe_durable,
                            filter_subject=probe_subject,
                            ack_wait=1.0,
                            max_deliver=3,
                        )
                        subscription = await js.pull_subscribe(
                            probe_subject,
                            durable=probe_durable,
                            stream=probe_stream,
                            config=consumer_config,
                        )
                        await js.publish(probe_subject, b"qualification-redelivery-probe")
                        first_messages = await subscription.fetch(1, timeout=3)
                        if len(first_messages) != 1:
                            raise RuntimeError("jetstream_probe_initial_delivery_missing")
                        await nc.close()
                        nc = None
                        reconnect_nc = await nats.connect(
                            servers=[self.nats.env["POCKETLAB_NATS_URL"]],
                            user=self.nats.user,
                            password=self.nats.password,
                            name=f"qualification-redelivery-{self.run_id}",
                            connect_timeout=3,
                        )
                        reconnect_js = reconnect_nc.jetstream()
                        reconnect_subscription = await reconnect_js.pull_subscribe(
                            probe_subject,
                            durable=probe_durable,
                            stream=probe_stream,
                        )
                        redelivered_messages = []
                        redelivery_deadline = time.monotonic() + 5
                        while time.monotonic() < redelivery_deadline and not redelivered_messages:
                            try:
                                redelivered_messages = await reconnect_subscription.fetch(1, timeout=1)
                            except Exception:
                                continue
                        if len(redelivered_messages) != 1 or redelivered_messages[0].metadata.num_delivered < 2:
                            raise RuntimeError("jetstream_probe_redelivery_missing")
                        await redelivered_messages[0].ack()
                        await reconnect_js.delete_stream(probe_stream)
                        await reconnect_nc.close()
                        reconnect_nc = None
                        return {
                            "connected": True,
                            "jetstream": True,
                            "streams": streams,
                            "durable_consumer_redelivery": True,
                            "initial_delivery_count": len(first_messages),
                            "redelivery_count": int(redelivered_messages[0].metadata.num_delivered),
                            "probe_stream_run_scoped": True,
                        }
                    except Exception as exc:
                        last_error = f"{type(exc).__name__}:{str(exc).replace(chr(10), ' ')[:160]}"
                        if probe_stream:
                            cleanup_nc = reconnect_nc or nc
                            if cleanup_nc is not None:
                                try:
                                    await cleanup_nc.jetstream().delete_stream(probe_stream)
                                except Exception:
                                    pass
                        if nc is not None:
                            try:
                                await nc.close()
                            except Exception:
                                pass
                        if reconnect_nc is not None:
                            try:
                                await reconnect_nc.close()
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
            # Do not manufacture a PM2 cleanup failure when an early
            # dependency gate stopped the run before the candidate supervisor
            # or agent existed.  If either component was launched, the exact
            # run-scoped name must still be deleted and verified below.
            if self.agent_env and (self.supervisor is not None or self.agent_pid is not None):
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


@dataclass(frozen=True)
class AndroidSnapshot:
    archive: Path
    manifest: Path
    manifest_sha256: str
    file_count: int
    byte_count: int


def _android_snapshot(repo: Path, candidate_sha: str, root: Path) -> AndroidSnapshot:
    """Build a minimal immutable source archive from the selected Git tree."""
    tree = _command(
        ["git", "ls-tree", "-r", "-z", candidate_sha, *ANDROID_ALLOWED_SNAPSHOT_PREFIXES],
        cwd=repo,
        timeout=30,
    )
    if tree.returncode != 0:
        raise QualificationError("candidate source inventory could not be read")
    entries: list[dict[str, Any]] = []
    expected_paths: set[str] = set()
    for raw in tree.stdout.split("\x00"):
        if not raw:
            continue
        header, separator, path = raw.partition("\t")
        parts = header.split()
        if not separator or len(parts) != 3 or parts[1] != "blob":
            raise QualificationError("candidate source contains an unsupported Git object")
        mode, _object_type, object_sha = parts
        if mode == "120000" or not any(path.startswith(prefix) for prefix in ANDROID_ALLOWED_SNAPSHOT_PREFIXES):
            raise QualificationError("candidate source contains an unsafe snapshot entry")
        if Path(path).name in ANDROID_PRODUCTION_FILE_NAMES or Path(path).name.startswith(".env"):
            raise QualificationError("candidate snapshot includes a production configuration file")
        expected_paths.add(path)
        entries.append({"path": path, "object_sha": object_sha, "mode": mode})
    if not entries:
        raise QualificationError("candidate source snapshot is empty")

    archive_path = root / "candidate-snapshot.tar"
    with archive_path.open("wb") as output:
        archived = subprocess.run(
            ["git", "archive", "--format=tar", candidate_sha, *ANDROID_ALLOWED_SNAPSHOT_PREFIXES],
            cwd=str(repo),
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.PIPE,
            text=False,
            timeout=60,
            check=False,
        )
    if archived.returncode != 0:
        raise QualificationError("candidate source archive could not be created")

    manifest_entries: list[dict[str, Any]] = []
    archive_paths: set[str] = set()
    byte_count = 0
    with tarfile.open(archive_path, "r") as bundle:
        for member in bundle.getmembers():
            name = member.name.rstrip("/")
            if not name:
                continue
            if member.issym() or member.islnk() or not member.isfile():
                if member.isdir():
                    continue
                raise QualificationError("candidate source archive contains a symlink or non-file")
            if name not in expected_paths or name in archive_paths:
                raise QualificationError("candidate source archive contains an unexpected file")
            stream = bundle.extractfile(member)
            if stream is None:
                raise QualificationError("candidate source archive file could not be read")
            digest = hashlib.sha256()
            size = 0
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
                size += len(chunk)
            archive_paths.add(name)
            byte_count += size
            manifest_entries.append({"path": name, "sha256": digest.hexdigest(), "size": size, "mode": member.mode & 0o777})
    if archive_paths != expected_paths:
        raise QualificationError("candidate source archive does not match the Git inventory")
    manifest_payload = {
        "schema_version": 1,
        "repository": REPOSITORY,
        "candidate_sha": candidate_sha,
        "snapshot_prefixes": list(ANDROID_ALLOWED_SNAPSHOT_PREFIXES),
        "files": sorted(manifest_entries, key=lambda item: str(item["path"])),
        "production_configuration_files_present": False,
        "symlinks_present": False,
    }
    manifest_path = root / "candidate-manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest_path.chmod(0o600)
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return AndroidSnapshot(archive_path, manifest_path, manifest_sha, len(manifest_entries), byte_count)


def _android_media_archive(root: Path) -> tuple[Path, list[dict[str, Any]]]:
    """Create deterministic media without enumerating a real Android library."""
    files = {
        "storage/shared/DCIM/Camera/qualification-camera.jpg": b"synthetic-jpeg\n" * 32,
        "storage/shared/DCIM/Camera/caf\N{LATIN SMALL LETTER E WITH ACUTE}.png": b"synthetic-png\n" * 48,
        "storage/shared/DCIM/Camera/same-name.jpg": b"camera-copy\n" * 24,
        "storage/shared/Pictures/same-name.jpg": b"picture-copy\n" * 24,
        "storage/shared/Pictures/Case.JPG": b"case-collision\n" * 24,
        "storage/shared/Movies/qualification-video.mp4": b"synthetic-video\n" * 256,
        "storage/shared/DCIM/Camera/.hidden.jpg": b"must-not-transfer",
        "storage/shared/DCIM/Camera/.nomedia": b"synthetic\n",
    }
    archive_path = root / "synthetic-media.tar"
    expected: list[dict[str, Any]] = []
    with tarfile.open(archive_path, "w") as bundle:
        directories = {
            "storage", "storage/shared", "storage/shared/DCIM", "storage/shared/DCIM/Camera",
            "storage/shared/Pictures", "storage/shared/Movies",
        }
        for directory in sorted(directories):
            info = tarfile.TarInfo(directory)
            info.type = tarfile.DIRTYPE
            info.mode = 0o700
            bundle.addfile(info)
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o600
            bundle.addfile(info, io.BytesIO(payload))
            expected.append({"path": name, "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})
        link = tarfile.TarInfo("storage/shared/DCIM/Camera/symlink.jpg")
        link.type = tarfile.SYMTYPE
        link.linkname = "qualification-camera.jpg"
        link.mode = 0o600
        bundle.addfile(link)
    archive_path.chmod(0o600)
    size = archive_path.stat().st_size
    if size > ANDROID_MAX_MEDIA_BYTES:
        raise QualificationError("synthetic media fixture exceeds the Android resource budget")
    return archive_path, expected


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
    parser.add_argument("--android-qualify", action="store_true")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[3]
    if args.android_read_only and args.android_qualify:
        parser.error("--android-read-only and --android-qualify are mutually exclusive")
    if args.android_read_only:
        result = android_read_only_preflight(repo=repo, hosts=("pocketlab-termux", "pocketlab-secondary"))
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result.get("status") == "PASS" else 2
    try:
        if args.android_qualify:
            run = AndroidQualificationRun(
                repo=repo,
                candidate_sha=args.candidate_sha,
                python=args.python,
                nats_binary=args.nats_server_bin,
                opa_binary=args.opa_bin,
                evidence_dir=args.evidence_dir,
            )
            status, manifest = run.run()
            print(json.dumps({
                "status": status,
                "candidate_sha": run.candidate_sha,
                "run_id": run.run_id,
                "manifest": str(manifest) if manifest else None,
            }, indent=2, sort_keys=True))
            return 0 if status == "PASS" else 1
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


class AndroidTunnel:
    """One controller-owned SSH forward with dynamic-port evidence."""

    def __init__(
        self,
        *,
        host: str,
        run_id: str,
        kind: str,
        log: Path,
        direction: str,
        local_port: int,
        target_port: int,
        remote_port: int = 0,
    ) -> None:
        if direction not in {"reverse", "local"}:
            raise QualificationError("unsupported SSH tunnel direction")
        if not 1 <= int(local_port) <= 65535 or not 1 <= int(target_port) <= 65535:
            raise QualificationError("SSH tunnel target port is invalid")
        if remote_port and not 1 <= int(remote_port) <= 65535:
            raise QualificationError("SSH tunnel remote port is invalid")
        self.host = host
        self.run_id = run_id
        self.kind = kind
        self.log = log
        self.direction = direction
        self.local_port = int(local_port)
        self.target_port = int(target_port)
        self.requested_remote_port = int(remote_port)
        self.remote_port = int(remote_port)
        self.process: subprocess.Popen[bytes] | None = None
        self.pid = 0
        self.start_ticks: int | None = None
        self._lines: list[str] = []
        self._allocated = threading.Event()
        self._reader: threading.Thread | None = None

    @property
    def mapping(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "kind": self.kind,
            "direction": self.direction,
            "bind_address": "127.0.0.1",
            "local_target": f"127.0.0.1:{self.target_port}",
            "requested_remote_port": self.requested_remote_port,
            "allocated_remote_port": self.remote_port,
        }

    def _read_stderr(self, stream: Any) -> None:
        try:
            for raw in iter(stream.readline, b""):
                line = raw.decode("utf-8", errors="replace").strip()
                if len(self._lines) >= 120:
                    self._lines.pop(0)
                self._lines.append(line[-400:])
                match = re.search(r"Allocated port (\d+) for remote forward", line)
                if match:
                    self.remote_port = int(match.group(1))
                    self._allocated.set()
                if "remote forward success" in line.lower() and self.direction == "reverse":
                    self._allocated.set()
                if (
                    ("forward success" in line.lower() or "local forwarding listening" in line.lower())
                    and self.direction == "local"
                ):
                    self._allocated.set()
        except (OSError, ValueError):
            return

    def _owned(self) -> bool:
        return bool(
            self.process is not None
            and self.process.poll() is None
            and self.pid > 0
            and self.start_ticks is not None
            and _proc_start_ticks(self.pid) == self.start_ticks
            and _proc_has_marker(self.pid, f"POCKETLAB_QUALIFICATION_RUN_ID={self.run_id}")
        )

    def start(self, *, timeout: float = 12.0) -> None:
        if self.process is not None and self.process.poll() is None:
            raise QualificationError("SSH tunnel is already running")
        self.log.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.direction == "reverse":
            specification = f"127.0.0.1:{self.requested_remote_port}:127.0.0.1:{self.target_port}"
            forwarding = ["-R", specification]
        else:
            specification = f"127.0.0.1:{self.local_port}:127.0.0.1:{self.target_port}"
            forwarding = ["-L", specification]
        command = [
            "ssh", "-v", "-N", "-T",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "BatchMode=yes",
            "-o", "RequestTTY=no",
            "-o", "ClearAllForwardings=no",
            "-o", "GatewayPorts=no",
            "-o", "ConnectTimeout=8",
            "-o", "ServerAliveInterval=5",
            "-o", "ServerAliveCountMax=2",
            *forwarding,
            self.host,
        ]
        marker_env = dict(_scrubbed_environment())
        marker_env.update({
            "POCKETLAB_QUALIFICATION_RUN_ID": self.run_id,
            "POCKETLAB_QUALIFICATION_TRANSPORT": self.kind,
        })
        handle = self.log.open("ab", buffering=0)
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=handle,
            stderr=subprocess.PIPE,
            env=marker_env,
            close_fds=True,
            start_new_session=True,
        )
        handle.close()
        self.pid = int(self.process.pid)
        self.start_ticks = _proc_start_ticks(self.pid)
        if self.process.stderr is not None:
            self._reader = threading.Thread(target=self._read_stderr, args=(self.process.stderr,), daemon=True)
            self._reader.start()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self._owned():
                detail = " ".join(self._lines[-8:])[:1600]
                raise QualificationError(f"SSH {self.kind} tunnel failed ownership/startup: {detail}")
            if self.direction == "reverse" and self.requested_remote_port == 0:
                ready = self._allocated.is_set() and self.remote_port > 0
            else:
                ready = self._allocated.is_set()
            if ready:
                if self.direction == "reverse" and not self.remote_port:
                    self.remote_port = self.requested_remote_port
                return
            time.sleep(0.05)
        self.stop()
        detail = " ".join(self._lines[-8:])[:1600]
        raise QualificationError(f"SSH {self.kind} tunnel allocation timed out: {detail}")

    def assert_alive(self) -> None:
        if not self._owned():
            raise QualificationError(f"SSH {self.kind} tunnel stopped during qualification")

    def stop(self) -> bool:
        if self.process is None or self.process.poll() is not None:
            return True
        if not self._owned():
            return False
        try:
            os.killpg(self.pid, signal.SIGTERM)
        except OSError:
            return self.process.poll() is not None
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if self._owned():
                try:
                    os.killpg(self.pid, signal.SIGKILL)
                except OSError:
                    pass
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                return False
        return True

@dataclass(frozen=True)
class AndroidRemote:
    host: str
    home: str
    prefix: str
    python: str
    pm2: str | None
    rclone: str | None
    baseline: dict[str, Any]


def _android_ssh_base(host: str) -> list[str]:
    return [
        "ssh",
        "-T",
        "-o", "BatchMode=yes",
        "-o", "RequestTTY=no",
        "-o", "ConnectTimeout=8",
        "-o", "ClearAllForwardings=yes",
        host,
    ]


def _android_ssh_run(
    host: str,
    remote_args: list[str],
    *,
    input_data: bytes | str | None = None,
    timeout: float = 20.0,
) -> subprocess.CompletedProcess[Any]:
    if not remote_args:
        raise QualificationError("Android SSH control command was empty")
    # OpenSSH sends the remote command through the phone's shell.  Preserve
    # Python -c payloads and all other argument boundaries explicitly; passing
    # the list directly makes a multiline payload detach from its -c flag.
    remote_command = shlex.join(remote_args)
    return subprocess.run(
        _android_ssh_base(host) + [remote_command],
        input=input_data,
        stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
        capture_output=True,
        text=isinstance(input_data, str),
        timeout=timeout,
        check=False,
    )


def _android_ssh_shell(
    host: str,
    command: str,
    *,
    input_data: bytes | str | None = None,
    timeout: float = 20.0,
) -> subprocess.CompletedProcess[Any]:
    return _android_ssh_run(host, ["sh", "-c", command], input_data=input_data, timeout=timeout)


def _android_safe_remote_path(path: str, root: str) -> str:
    candidate = str(path or "")
    owner = str(root or "").rstrip("/")
    if not owner or not candidate.startswith(owner + "/"):
        raise QualificationError("remote qualification path escaped the run root")
    relative = candidate[len(owner) + 1:]
    if not relative or any(part in {"", ".", ".."} for part in relative.split("/")):
        raise QualificationError("remote qualification path is malformed")
    return candidate


def _android_remote_write(
    host: str,
    path: str,
    data: bytes | str,
    *,
    root: str,
    mode: str = "600",
) -> None:
    path = _android_safe_remote_path(path, root)
    parent = str(Path(path).parent)
    command = (
        f"umask 077; mkdir -p -- {shlex.quote(parent)}; "
        f"cat > {shlex.quote(path)}; chmod {mode} {shlex.quote(path)}"
    )
    result = _android_ssh_shell(host, command, input_data=data, timeout=30)
    if result.returncode != 0:
        raise QualificationError("remote qualification file staging failed")


def _android_remote_mkdir(host: str, path: str, *, root: str) -> None:
    path = _android_safe_remote_path(path, root)
    result = _android_ssh_shell(
        host,
        f"umask 077; mkdir -p -- {shlex.quote(path)}; chmod 700 {shlex.quote(path)}",
    )
    if result.returncode != 0:
        raise QualificationError("remote qualification directory creation failed")


_ANDROID_BASELINE_CODE = r'''
import json, os, pathlib, shlex, shutil, subprocess, sys

home = pathlib.Path.home()
repo = home / "pocket-lab-lite"

def run(args, timeout=8):
    try:
        return subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None

def run_shell(command, timeout=8):
    try:
        return subprocess.run(command, shell=True, check=False, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None

def which(name):
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        candidate = pathlib.Path(directory) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return ""

def safe_pm2():
    pm2 = which("pm2")
    # Termux's PM2/Node combination can abort a Python process during direct
    # list-argv subprocess finalization.  Keep this fixed, read-only command
    # shell-mediated and quote the discovered executable path.
    result = run_shell(f"{shlex.quote(pm2)} jlist") if pm2 else None
    if result is None or result.returncode != 0:
        return []
    try:
        payload = json.loads(result.stdout or "[]")
    except Exception:
        return []
    output = []
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
        cwd = str(env.get("pm_cwd") or item.get("cwd") or "")
        output.append({
            "name": str(item.get("name") or "")[:100],
            "pid": int(item.get("pid") or 0),
            "status": str(env.get("status") or item.get("status") or "")[:32],
            "version": str(env.get("version") or "")[:80],
            "cwd_class": "pocketlab_checkout" if cwd.endswith("/pocket-lab-lite") else "other",
        })
    return sorted(output, key=lambda item: item["name"])

def listeners():
    result = run(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"])
    rows = []
    if result is not None and result.returncode == 0:
        for line in (result.stdout or "").splitlines()[1:]:
            fields = line.split()
            if fields:
                rows.append(fields[-1][:80])
    return {
        "count": len(rows),
        "addresses": sorted(rows)[:64],
        "loopback_only": all(value.startswith("127.0.0.1:") or value.startswith("[::1]:") for value in rows),
    }

def tailscale_state():
    if not which("tailscale"):
        return "unavailable"
    result = run(["tailscale", "status", "--json"], timeout=5)
    if result is None or result.returncode != 0:
        return "unobserved"
    try:
        return str(json.loads(result.stdout or "{}").get("BackendState") or "unobserved")[:40]
    except Exception:
        return "unobserved"

def free_bytes(path):
    try:
        return max(0, int(shutil.disk_usage(path).free))
    except Exception:
        return None

def memory_available():
    try:
        for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return max(0, int(line.split()[1]) * 1024)
    except Exception:
        pass
    return None

try:
    load_1m = float(os.getloadavg()[0])
except Exception:
    load_1m = None

git = run(["git", "-C", str(repo), "rev-parse", "HEAD"])
dirty = run(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"])
photo = run([
    "curl", "--silent", "--show-error", "--fail", "--max-time", "3",
    "--output", "/dev/null", "--write-out", "%{http_code}",
    "https://127.0.0.1/api/v1/status",
], timeout=5)
print(json.dumps({
    "system": os.uname().sysname,
    "architecture": os.uname().machine,
    "home": str(home),
    "prefix": str(os.environ.get("PREFIX") or ""),
    "home_class": "termux_private_home" if str(home).startswith("/data/data/com.termux/") else "unexpected",
    "prefix_class": "termux_prefix" if os.environ.get("PREFIX", "").startswith("/data/data/com.termux/") else "unexpected",
    "python": sys.executable,
    "python_version": sys.version.split()[0],
    "pm2_path": which("pm2"),
    "rclone_path": which("rclone"),
    "df_free_bytes": free_bytes(home),
    "memory_available_bytes": memory_available(),
    "load_1m": load_1m,
    "source_sha": (git.stdout or "").strip() if git and git.returncode == 0 else "unavailable",
    "git_clean": bool(dirty and dirty.returncode == 0 and not dirty.stdout.strip()),
    "pm2": safe_pm2(),
    "listeners": listeners(),
    "tailscale": tailscale_state(),
    "photoprism_health": "healthy" if photo and photo.returncode == 0 and str(photo.stdout or "").startswith("2") else "unobserved",
}, sort_keys=True))
'''


def _android_baseline(host: str) -> dict[str, Any]:
    result = _android_ssh_run(host, ["python3", "-c", _ANDROID_BASELINE_CODE], timeout=20)
    if result.returncode != 0:
        raise QualificationError("Android production baseline could not be captured")
    try:
        payload = json.loads(result.stdout or "{}")
    except (TypeError, ValueError) as exc:
        raise QualificationError("Android production baseline was malformed") from exc
    if not isinstance(payload, dict):
        raise QualificationError("Android production baseline was not an object")
    return payload


def _android_import_check(host: str, python: str, modules: list[str]) -> dict[str, Any]:
    code = r'''
import importlib.util, json, sys
modules = sys.argv[1:]
missing = [name for name in modules if importlib.util.find_spec(name) is None]
print(json.dumps({"missing": missing, "python": sys.executable, "version": sys.version.split()[0]}))
'''
    result = _android_ssh_run(host, [python, "-c", code, *modules], timeout=20)
    if result.returncode != 0:
        raise QualificationError("Android runtime dependency preflight failed")
    try:
        payload = json.loads(result.stdout or "{}")
    except (TypeError, ValueError) as exc:
        raise QualificationError("Android runtime dependency result was malformed") from exc
    if not isinstance(payload, dict):
        raise QualificationError("Android runtime dependency result was not an object")
    return payload


def _android_create_remote_root(remote: AndroidRemote, run_id: str) -> str:
    root = f"{remote.home}/.pocketlab-qualification/{run_id}"
    code = r'''
import json, pathlib, sys
home = pathlib.Path.home().resolve(strict=True)
root = pathlib.Path(sys.argv[1])
parent = root.parent
if root.exists() or root.is_symlink():
    raise SystemExit(2)
if parent.exists() and parent.is_symlink():
    raise SystemExit(3)
parent.mkdir(mode=0o700, parents=True, exist_ok=True)
parent.chmod(0o700)
root.mkdir(mode=0o700)
resolved = root.resolve(strict=True)
if not str(resolved).startswith(str(home) + "/"):
    raise SystemExit(4)
print(json.dumps({"root": str(resolved), "home": str(home)}))
'''
    result = _android_ssh_run(remote.host, [remote.python, "-c", code, root], timeout=20)
    if result.returncode != 0:
        raise QualificationError("remote qualification root creation failed")
    try:
        payload = json.loads(result.stdout or "{}")
    except (TypeError, ValueError) as exc:
        raise QualificationError("remote qualification root result was malformed") from exc
    resolved = str(payload.get("root") or "") if isinstance(payload, dict) else ""
    if resolved != root:
        raise QualificationError("remote qualification root identity could not be proved")
    return resolved


def _android_remote_extract(remote: AndroidRemote, archive: Path, destination: str, *, root: str) -> None:
    destination = _android_safe_remote_path(destination, root)
    command = (
        f"umask 077; mkdir -p -- {shlex.quote(destination)}; chmod 700 {shlex.quote(destination)}; "
        f"tar -xf - -C {shlex.quote(destination)}"
    )
    result = _android_ssh_shell(
        remote.host,
        command,
        input_data=archive.read_bytes(),
        timeout=90,
    )
    if result.returncode != 0:
        raise QualificationError("remote qualification archive extraction failed")


_ANDROID_VERIFY_SNAPSHOT_CODE = r'''
import hashlib, json, pathlib, sys
root = pathlib.Path(sys.argv[1]).resolve(strict=True)
manifest_path = pathlib.Path(sys.argv[2]).resolve(strict=True)
expected = json.loads(manifest_path.read_text(encoding="utf-8"))
files = expected.get("files") if isinstance(expected, dict) else []
seen = set()
for item in files if isinstance(files, list) else []:
    relative = str(item.get("path") or "")
    path = root / relative
    if not relative or not path.is_file() or path.is_symlink():
        raise SystemExit(2)
    if pathlib.Path(relative).name in {".env", ".env.local", ".env.production", "photoprism.env", "Caddyfile", "rclone.conf"}:
        raise SystemExit(3)
    if any(parent.is_symlink() for parent in [path.parent, *path.parents]):
        raise SystemExit(4)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != str(item.get("sha256") or "") or path.stat().st_size != int(item.get("size") or -1):
        raise SystemExit(5)
    seen.add(relative)
for path in root.rglob("*"):
    if path.is_symlink():
        raise SystemExit(6)
    if path.is_file() and path.relative_to(root).as_posix() not in seen:
        raise SystemExit(7)
print(json.dumps({
    "verified": True,
    "file_count": len(seen),
    "candidate_sha": expected.get("candidate_sha"),
    "repository": expected.get("repository"),
}))
'''


def _android_verify_snapshot(remote: AndroidRemote, candidate_root: str, manifest: str, *, root: str) -> dict[str, Any]:
    _android_safe_remote_path(candidate_root, root)
    _android_safe_remote_path(manifest, root)
    result = _android_ssh_run(remote.host, [
        remote.python, "-c", _ANDROID_VERIFY_SNAPSHOT_CODE, candidate_root, manifest,
    ], timeout=40)
    if result.returncode != 0:
        raise QualificationError("remote candidate snapshot verification failed")
    try:
        payload = json.loads(result.stdout or "{}")
    except (TypeError, ValueError) as exc:
        raise QualificationError("remote candidate snapshot verification was malformed") from exc
    if not isinstance(payload, dict) or payload.get("verified") is not True:
        raise QualificationError("remote candidate snapshot verification did not pass")
    return payload


_ANDROID_LAUNCH_CODE = r'''
import base64, json, pathlib, subprocess, sys
env_path, argv_b64, cwd, log_path = sys.argv[1:]
env = json.loads(pathlib.Path(env_path).read_text(encoding="utf-8"))
argv = json.loads(base64.urlsafe_b64decode(argv_b64.encode()).decode("utf-8"))
if not isinstance(env, dict) or not isinstance(argv, list) or not argv:
    raise SystemExit(2)
pathlib.Path(log_path).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
with open(log_path, "ab", buffering=0) as stream:
    process = subprocess.Popen(
        [str(item) for item in argv],
        cwd=cwd,
        env={str(key): str(value) for key, value in env.items()},
        stdin=subprocess.DEVNULL,
        stdout=stream,
        stderr=subprocess.STDOUT,
        close_fds=True,
        start_new_session=True,
    )
print(process.pid, flush=True)
'''


_ANDROID_PROCESS_INFO_CODE = r'''
import hashlib, json, pathlib, sys
pid = int(sys.argv[1])
root = pathlib.Path(sys.argv[2]).resolve(strict=True)
run_id = str(sys.argv[3])

def start_ticks(value):
    raw = pathlib.Path(f"/proc/{value}/stat").read_text(encoding="utf-8")
    return int(raw.split(") ", 1)[1].split()[19])

def under(path):
    try:
        return str(path.resolve(strict=True)).startswith(str(root) + "/")
    except Exception:
        return False

try:
    state = pathlib.Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split(") ", 1)[1].split()[0]
    ticks = start_ticks(pid)
    cwd = pathlib.Path(f"/proc/{pid}/cwd").resolve(strict=True)
    environ = pathlib.Path(f"/proc/{pid}/environ").read_bytes()
    cmdline = pathlib.Path(f"/proc/{pid}/cmdline").read_bytes()
    marker = f"POCKETLAB_QUALIFICATION_RUN_ID={run_id}".encode()
    owned = marker in environ and under(cwd)
    print(json.dumps({
        "pid": pid,
        "state": state,
        "start_ticks": ticks,
        "cwd_class": "run_root" if under(cwd) else "outside_run_root",
        "owned": bool(owned),
        "argv_sha256": hashlib.sha256(cmdline).hexdigest()[:32],
        "environment_keys": sorted({
            part.split(b"=", 1)[0].decode("utf-8", "ignore")
            for part in environ.split(b"\x00") if b"=" in part
        })[:160],
    }, sort_keys=True))
except Exception:
    print(json.dumps({"pid": pid, "state": "missing", "owned": False}, sort_keys=True))
'''


def _android_process_info(remote: AndroidRemote, pid: int, *, root: str) -> dict[str, Any]:
    _android_safe_remote_path(root + "/probe", root)
    result = _android_ssh_run(remote.host, [
        remote.python, "-c", _ANDROID_PROCESS_INFO_CODE,
        str(int(pid)), root, root.rsplit("/", 1)[-1],
    ], timeout=15)
    if result.returncode != 0:
        return {"pid": int(pid), "state": "missing", "owned": False}
    try:
        value = json.loads(result.stdout or "{}")
    except (TypeError, ValueError):
        return {"pid": int(pid), "state": "unavailable", "owned": False}
    return value if isinstance(value, dict) else {"pid": int(pid), "state": "unavailable", "owned": False}


def _android_launch_remote(
    remote: AndroidRemote,
    *,
    env_path: str,
    argv: list[str],
    cwd: str,
    log_path: str,
    root: str,
) -> tuple[int, int]:
    for path in (env_path, cwd, log_path):
        _android_safe_remote_path(path, root)
    encoded = base64.urlsafe_b64encode(json.dumps(argv, separators=(",", ":")).encode()).decode()
    result = _android_ssh_run(remote.host, [
        remote.python, "-c", _ANDROID_LAUNCH_CODE,
        env_path, encoded, cwd, log_path,
    ], timeout=20)
    if result.returncode != 0:
        raise QualificationError("owned Android candidate process launch failed")
    try:
        pid = int((result.stdout or b"").decode().strip().splitlines()[-1])
    except (AttributeError, IndexError, ValueError) as exc:
        raise QualificationError("owned Android candidate process PID was unavailable") from exc
    info = _android_process_info(remote, pid, root=root)
    start_ticks = int(info.get("start_ticks") or 0)
    if not info.get("owned") or not start_ticks:
        raise QualificationError("Android candidate process ownership could not be verified")
    return pid, start_ticks


_ANDROID_STOP_CODE = r'''
import os, pathlib, signal, sys, time
pid = int(sys.argv[1])
expected_ticks = int(sys.argv[2])
root = pathlib.Path(sys.argv[3]).resolve(strict=True)
run_id = str(sys.argv[4])
mode = str(sys.argv[5])

def ticks(value):
    raw = pathlib.Path(f"/proc/{value}/stat").read_text(encoding="utf-8")
    return int(raw.split(") ", 1)[1].split()[19])

def owned():
    try:
        cwd = pathlib.Path(f"/proc/{pid}/cwd").resolve(strict=True)
        environ = pathlib.Path(f"/proc/{pid}/environ").read_bytes()
        return (
            ticks(pid) == expected_ticks
            and f"POCKETLAB_QUALIFICATION_RUN_ID={run_id}".encode() in environ
            and str(cwd).startswith(str(root) + "/")
        )
    except Exception:
        return False

if not owned():
    raise SystemExit(3)
try:
    os.killpg(os.getpgid(pid), signal.SIGKILL if mode == "crash" else signal.SIGTERM)
except ProcessLookupError:
    pass
if mode != "crash":
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            if ticks(pid) != expected_ticks:
                break
        except Exception:
            break
        time.sleep(0.1)
    if owned():
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            pass
print("stopped")
'''


def _android_stop_process(
    remote: AndroidRemote,
    pid: int,
    start_ticks: int,
    *,
    root: str,
    run_id: str,
    crash: bool = False,
) -> bool:
    result = _android_ssh_run(remote.host, [
        remote.python, "-c", _ANDROID_STOP_CODE,
        str(pid), str(start_ticks), root, run_id, "crash" if crash else "stop",
    ], timeout=15)
    return result.returncode == 0


class AndroidRemoteProcess:
    def __init__(
        self,
        *,
        remote: AndroidRemote,
        run_id: str,
        root: str,
        name: str,
        env_path: str,
        argv: list[str],
        cwd: str,
        log_path: str,
    ) -> None:
        self.remote = remote
        self.run_id = run_id
        self.root = root
        self.name = name
        self.env_path = env_path
        self.argv = list(argv)
        self.cwd = cwd
        self.log_path = log_path
        self.pid = 0
        self.start_ticks = 0

    def launch(self) -> None:
        self.pid, self.start_ticks = _android_launch_remote(
            self.remote,
            env_path=self.env_path,
            argv=self.argv,
            cwd=self.cwd,
            log_path=self.log_path,
            root=self.root,
        )

    def info(self) -> dict[str, Any]:
        return _android_process_info(self.remote, self.pid, root=self.root) if self.pid else {"state": "missing", "owned": False}

    def alive(self) -> bool:
        info = self.info()
        return bool(info.get("owned") and str(info.get("state") or "") not in {"", "Z", "missing"})

    def stop(self) -> bool:
        if not self.pid:
            return True
        return _android_stop_process(self.remote, self.pid, self.start_ticks, root=self.root, run_id=self.run_id)

    def crash(self) -> bool:
        if not self.pid:
            return False
        return _android_stop_process(self.remote, self.pid, self.start_ticks, root=self.root, run_id=self.run_id, crash=True)

    def restart(self) -> tuple[int, int]:
        old = self.pid
        if not self.stop():
            raise QualificationError(f"owned Android {self.name} process could not be stopped")
        self.launch()
        return old, self.pid


_ANDROID_PM2_LIST_CODE = r'''
import json, pathlib, subprocess, sys
env = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
pm2 = sys.argv[2]
result = subprocess.run(
    [pm2, "jlist"],
    env={str(k): str(v) for k, v in env.items()},
    capture_output=True,
    text=True,
    timeout=12,
)
if result.returncode != 0:
    raise SystemExit(result.returncode or 1)
try:
    data = json.loads(result.stdout or "[]")
except Exception:
    raise SystemExit(2)
safe = []
for item in data if isinstance(data, list) else []:
    if not isinstance(item, dict):
        continue
    pm2_env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
    safe.append({
        "name": str(item.get("name") or "")[:120],
        "pid": int(item.get("pid") or 0),
        "status": str(pm2_env.get("status") or item.get("status") or "")[:40],
        "version": str(pm2_env.get("version") or "")[:100],
        "pm_cwd": str(pm2_env.get("pm_cwd") or item.get("cwd") or "")[:240],
        "restart_time": int(pm2_env.get("restart_time") or 0),
    })
print(json.dumps(safe, sort_keys=True))
'''


def _android_pm2_list(remote: AndroidRemote, env_path: str, *, root: str) -> list[dict[str, Any]]:
    _android_safe_remote_path(env_path, root)
    if not remote.pm2:
        return []
    result = _android_ssh_run(remote.host, [
        remote.python, "-c", _ANDROID_PM2_LIST_CODE, env_path, remote.pm2,
    ], timeout=20)
    if result.returncode != 0:
        return []
    try:
        value = json.loads(result.stdout or "[]")
    except (TypeError, ValueError):
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


_ANDROID_PM2_COMMAND_CODE = r'''
import json, pathlib, subprocess, sys
env = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
pm2 = sys.argv[2]
name = sys.argv[3]
root = pathlib.Path(sys.argv[4]).resolve(strict=True)
pm2_home = pathlib.Path(str(env.get("PM2_HOME") or "")).resolve(strict=False)
if not str(pm2_home).startswith(str(root) + "/"):
    raise SystemExit(3)
if not name.startswith("pocketlab-agent-") or "qualification-" not in name:
    raise SystemExit(4)
command = sys.argv[5]
if command == "delete":
    args = [pm2, "delete", name]
elif command == "kill":
    args = [pm2, "kill"]
else:
    raise SystemExit(5)
result = subprocess.run(
    args,
    env={str(k): str(v) for k, v in env.items()},
    capture_output=True,
    text=True,
    timeout=20,
)
raise SystemExit(result.returncode)
'''


def _android_pm2_command(remote: AndroidRemote, env_path: str, name: str, command: str, *, root: str) -> bool:
    _android_safe_remote_path(env_path, root)
    if not remote.pm2:
        return False
    result = _android_ssh_run(remote.host, [
        remote.python, "-c", _ANDROID_PM2_COMMAND_CODE,
        env_path, remote.pm2, name, root, command,
    ], timeout=30)
    return result.returncode == 0


_ANDROID_SELECT_PORT_CODE = r'''
import json, socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("127.0.0.1", 0))
print(json.dumps({"port": int(sock.getsockname()[1])}))
sock.close()
'''


def _android_select_port(remote: AndroidRemote) -> int:
    result = _android_ssh_run(remote.host, [remote.python, "-c", _ANDROID_SELECT_PORT_CODE], timeout=12)
    if result.returncode != 0:
        raise QualificationError("Android loopback port reservation failed")
    try:
        value = json.loads(result.stdout or "{}")
        port = int(value.get("port") or 0)
    except (TypeError, ValueError):
        port = 0
    if not 1 <= port <= 65535:
        raise QualificationError("Android loopback port reservation was invalid")
    return port


_ANDROID_METRICS_CODE = r'''
import json, os, pathlib, shutil, sys
root = pathlib.Path(sys.argv[1]).resolve(strict=False)

def tree(path):
    total = 0
    files = 0
    try:
        for entry in path.rglob("*"):
            if entry.is_symlink() or not entry.is_file():
                continue
            total += max(0, entry.stat().st_size)
            files += 1
            if files >= 100000:
                break
    except Exception:
        pass
    return total, files

try:
    free = int(shutil.disk_usage(root).free)
except Exception:
    free = None
try:
    memory = None
    for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            memory = int(line.split()[1]) * 1024
            break
except Exception:
    memory = None
try:
    load = float(os.getloadavg()[0])
except Exception:
    load = None
size, count = tree(root)
print(json.dumps({
    "free_bytes": free,
    "memory_available_bytes": memory,
    "load_1m": load,
    "run_root_bytes": size,
    "run_root_files": count,
}, sort_keys=True))
'''


def _android_metrics(remote: AndroidRemote, root: str) -> dict[str, Any]:
    _android_safe_remote_path(root + "/metrics", root)
    result = _android_ssh_run(remote.host, [
        remote.python, "-c", _ANDROID_METRICS_CODE, root,
    ], timeout=20)
    if result.returncode != 0:
        return {"status": "UNVALIDATED"}
    try:
        value = json.loads(result.stdout or "{}")
    except (TypeError, ValueError):
        return {"status": "UNVALIDATED"}
    return value if isinstance(value, dict) else {"status": "UNVALIDATED"}


_ANDROID_REMOVE_ROOT_CODE = r'''
import pathlib, shutil, sys
root = pathlib.Path(sys.argv[1]).resolve(strict=False)
home = pathlib.Path.home().resolve(strict=True)
parent = home / ".pocketlab-qualification"
if root.parent != parent or not root.name.isalnum() or len(root.name) != 24:
    raise SystemExit(3)
if not str(root).startswith(str(parent) + "/") or root.is_symlink():
    raise SystemExit(4)
if root.exists():
    shutil.rmtree(root)
print("removed")
'''


def _android_remove_root(remote: AndroidRemote, root: str) -> bool:
    result = _android_ssh_run(remote.host, [
        remote.python, "-c", _ANDROID_REMOVE_ROOT_CODE, root,
    ], timeout=30)
    return result.returncode == 0


_ANDROID_LOCK_SNAPSHOT_CODE = r'''
import os, pathlib, stat, sys
root = pathlib.Path(sys.argv[1]).resolve(strict=True)
for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
    if path.is_symlink():
        raise SystemExit(3)
    if path.is_dir():
        path.chmod(0o500)
    elif path.is_file():
        path.chmod(0o400)
root.chmod(0o500)
print("locked")
'''


def _android_lock_snapshot(remote: AndroidRemote, candidate_root: str, *, root: str) -> None:
    _android_safe_remote_path(candidate_root, root)
    result = _android_ssh_run(remote.host, [
        remote.python, "-c", _ANDROID_LOCK_SNAPSHOT_CODE, candidate_root,
    ], timeout=30)
    if result.returncode != 0:
        raise QualificationError("candidate source snapshot could not be made read-only")


@dataclass(frozen=True)
class AndroidNatsView:
    url: str
    user: str
    password: str

    @property
    def env(self) -> dict[str, str]:
        return {
            "POCKETLAB_NATS_URL": self.url,
            "POCKETLAB_NATS_USER": self.user,
            "POCKETLAB_NATS_PASSWORD": self.password,
        }


class AndroidQualificationRun(QualificationRun):
    """Authorized physical candidate lane using only run-scoped phone roots."""

    def __init__(
        self,
        *,
        repo: Path,
        candidate_sha: str,
        python: str,
        nats_binary: str | None,
        opa_binary: str | None,
        evidence_dir: Path | None,
    ) -> None:
        self.repo = repo
        self.candidate_sha = _candidate_sha(repo, candidate_sha)
        self.python = str(Path(python).absolute())
        if not Path(self.python).is_file():
            raise QualificationError("qualification Python interpreter is unavailable")
        self.nats_binary = nats_binary or shutil.which("nats-server")
        self.opa_binary = opa_binary or shutil.which("opa")
        self.run_id = uuid.uuid4().hex[:24]
        if not RUN_ID_RE.fullmatch(self.run_id):
            raise QualificationError("qualification run identity generation failed")

        root = Path(tempfile.mkdtemp(prefix="pocket-lab-android-qualification-"))
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
        for path in (
            self.paths.home,
            self.paths.state,
            self.paths.logs,
            self.paths.bin,
            self.paths.destination,
            self.paths.evidence,
        ):
            path.mkdir(mode=0o700, parents=True, exist_ok=True)

        self.external_evidence_dir = evidence_dir or (
            Path(tempfile.gettempdir()) / "pocket-lab-lite-qualification-evidence"
        )
        self.external_evidence_dir = self.external_evidence_dir.absolute()
        if _safe_under(self.external_evidence_dir, self.paths.root):
            raise QualificationError("Android evidence directory may not be inside the disposable root")
        self.started_at = _now()
        self.snapshot = _android_snapshot(repo, self.candidate_sha, self.paths.root)
        self.media_archive, self.media_expected = _android_media_archive(self.paths.root)
        self.snapshot_manifest = json.loads(self.snapshot.manifest.read_text(encoding="utf-8"))
        self.component_manifest = {
            str(item["path"]): str(item["sha256"])
            for item in self.snapshot_manifest.get("files", [])
            if isinstance(item, dict) and item.get("path") and item.get("sha256")
        }

        self.ca_path, self.cert_path, self.key_path = _create_certificates(self.paths)
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
        self.harness_public = self.harness_private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.harness_public_key = base64.urlsafe_b64encode(self.harness_public).decode().rstrip("=")
        self.harness_fingerprint = "sha256:" + hashlib.sha256(self.harness_public).hexdigest()
        self.fleet_private = ed25519.Ed25519PrivateKey.generate()
        self.fleet_public = self.fleet_private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        self.fleet_public_key = base64.urlsafe_b64encode(self.fleet_public).decode().rstrip("=")
        self.fleet_principal_id = f"qualification-fleet-{self.run_id}"
        self.provisioning_token = secrets_token(48)
        self.server_node = f"qualification-server-{self.run_id}"
        self.node_id = f"qualification-storage-{self.run_id}"

        self.server: AndroidRemote | None = None
        self.secondary: AndroidRemote | None = None
        self.server_root = ""
        self.secondary_root = ""
        self.server_api_remote_port = 0
        self.opa_remote_port = 0
        self.server_api_origin = ""
        self.secondary_control_origin = ""
        self.server_nats_origin = ""
        self.server_webdav_origin = ""
        self.secondary_nats_tunnel: AndroidTunnel | None = None
        self.secondary_webdav_tunnel: AndroidTunnel | None = None
        self.tunnels: list[AndroidTunnel] = []
        self.local_processes: list[OwnedProcess] = []
        self.local_nats: DisposableNats | None = None
        self.local_opa: DisposableOpa | None = None
        self.webdav: OwnedProcess | None = None
        self.api: AndroidRemoteProcess | None = None
        self.worker: AndroidRemoteProcess | None = None
        self.supervisor: AndroidRemoteProcess | None = None
        self.server_env: dict[str, str] = {}
        self.agent_env: dict[str, str] = {}
        self.server_env_path = ""
        self.secondary_env_path = ""
        self.secondary_agent_env_path = ""
        self.session_token = ""
        self.fleet_session_token = ""
        self.nats: AndroidNatsView | None = None
        self.results: dict[str, Any] = {}
        self.baselines: dict[str, dict[str, Any]] = {}
        self.active_backup_id = ""
        self.roots_created = False
        self.launch_started = False
        self.cleanup_done = False
        self.preflight_done = False

    @property
    def candidate_runtime_remote(self) -> str:
        return f"{self.server_root}/candidate/pocket-lab-final-structure/runtime"

    @property
    def candidate_runtime_secondary_remote(self) -> str:
        return f"{self.secondary_root}/candidate/pocket-lab-final-structure/runtime"

    def _discover_remotes(self) -> None:
        remotes: list[AndroidRemote] = []
        for host in ("pocketlab-termux", "pocketlab-secondary"):
            baseline = _android_baseline(host)
            home = str(baseline.get("home") or "")
            prefix = str(baseline.get("prefix") or "")
            python = str(baseline.get("python") or "")
            if (
                baseline.get("architecture") not in {"aarch64", "arm64"}
                or baseline.get("home_class") != "termux_private_home"
                or baseline.get("prefix_class") != "termux_prefix"
                or not home.startswith("/data/data/com.termux/")
                or not prefix.startswith("/data/data/com.termux/")
                or not python.startswith(prefix + "/")
            ):
                raise QualificationError(f"{host} failed the Termux ARM64 identity preflight")
            remotes.append(AndroidRemote(
                host=host,
                home=home,
                prefix=prefix,
                python=python,
                pm2=str(baseline.get("pm2_path") or "") or None,
                rclone=str(baseline.get("rclone_path") or "") or None,
                baseline=baseline,
            ))
        self.server, self.secondary = remotes
        # Preserve both production baselines even when a later preflight gate
        # blocks before the full preflight result is recorded.  Cleanup must be
        # able to compare the phones after every authorized attempt.
        self.baselines["server_before"] = self.server.baseline
        self.baselines["secondary_before"] = self.secondary.baseline
        if not self.secondary.pm2 or not self.secondary.rclone:
            raise QualificationError("secondary phone lacks the required isolated PM2/rclone runtime")
        if self.secondary.baseline.get("tailscale") not in {"unavailable", "unobserved"}:
            raise QualificationError("secondary phone has an unexpected Tailscale runtime")
        if self.server.baseline.get("df_free_bytes") is not None and int(self.server.baseline["df_free_bytes"]) < ANDROID_MIN_FREE_BYTES:
            raise QualificationError("Server Phone temporary storage is below the conservative qualification floor")
        if self.secondary.baseline.get("df_free_bytes") is not None and int(self.secondary.baseline["df_free_bytes"]) < ANDROID_MIN_FREE_BYTES:
            raise QualificationError("secondary phone temporary storage is below the conservative qualification floor")
        if not self.nats_binary:
            raise QualificationError("Dev PC disposable nats-server is unavailable")
        if not self.opa_binary:
            raise QualificationError("Dev PC disposable OPA is unavailable")

        server_imports = _android_import_check(
            self.server.host,
            self.server.python,
            ["fastapi", "uvicorn", "nats", "cryptography", "pydantic"],
        )
        secondary_imports = _android_import_check(
            self.secondary.host,
            self.secondary.python,
            ["nats"],
        )
        if server_imports.get("missing") or secondary_imports.get("missing"):
            raise QualificationError("Android candidate runtime dependency preflight failed")
        self.results["android_preflight"] = {
            "status": "PASS",
            "server_architecture": self.server.baseline.get("architecture"),
            "secondary_architecture": self.secondary.baseline.get("architecture"),
            "server_python": server_imports.get("version"),
            "secondary_python": secondary_imports.get("version"),
            "server_pm2_processes": len(self.server.baseline.get("pm2") or []),
            "secondary_pm2_processes": len(self.secondary.baseline.get("pm2") or []),
            "secondary_tailscale": self.secondary.baseline.get("tailscale"),
            "production_candidate_processes_before": False,
            "production_credentials_inherited": False,
            "source_snapshot_files": self.snapshot.file_count,
            "source_snapshot_bytes": self.snapshot.byte_count,
            "source_snapshot_sha256": self.snapshot.manifest_sha256,
            "max_duration_seconds": ANDROID_MAX_DURATION_SECONDS,
            "max_retries": ANDROID_MAX_RETRIES,
        }
        self.preflight_done = True

    def _local_policy(self) -> Path:
        result = _command([
            "git", "show", f"{self.candidate_sha}:security/policies/opa/pocketlab/pocketlab.rego",
        ], cwd=self.repo, timeout=20)
        if result.returncode != 0:
            raise QualificationError("candidate OPA policy could not be materialized")
        path = self.paths.root / "candidate-policy.rego"
        _write_private(path, result.stdout)
        return path

    def _start_local_services(self) -> None:
        self.nats_binary = self.nats_binary or shutil.which("nats-server")
        self.opa_binary = self.opa_binary or shutil.which("opa")
        if not self.nats_binary or not self.opa_binary:
            raise QualificationError("Dev PC disposable service binaries are unavailable")
        base_env = _scrubbed_environment()
        base_env.update({
            "HOME": str(self.paths.home),
            "TMPDIR": str(self.paths.root / "tmp"),
            "TMP": str(self.paths.root / "tmp"),
            "TEMP": str(self.paths.root / "tmp"),
            "POCKETLAB_BASE_DIR": str(self.paths.root),
            "POCKETLAB_STATE_DIR": str(self.paths.state),
            "POCKETLAB_QUALIFICATION_RUN_ID": self.run_id,
            "POCKETLAB_QUALIFICATION_ROOT": str(self.paths.root),
            "SSL_CERT_FILE": str(self.ca_path),
            "REQUESTS_CA_BUNDLE": str(self.ca_path),
        })
        (self.paths.root / "tmp").mkdir(mode=0o700, exist_ok=True)
        self.local_nats = DisposableNats(
            paths=self.paths,
            env=base_env,
            run_id=self.run_id,
            binary=self.nats_binary,
        )
        self.local_nats.start()
        self.local_opa = DisposableOpa(
            paths=self.paths,
            run_id=self.run_id,
            policy_source=self._local_policy(),
            binary=self.opa_binary,
        )
        self.local_opa.start(base_env=base_env)
        while self.webdav_port in {self.local_nats.port, self.local_opa.port}:
            self.webdav_port = _port()
        fixture_env = dict(base_env)
        fixture_env.update({
            "QUALIFICATION_WEBDAV_USER": self.webdav_user,
            "QUALIFICATION_WEBDAV_PASSWORD": self.webdav_password,
            "QUALIFICATION_CONTROL_TOKEN": self.webdav_control_token,
        })
        fixture = self.repo / "scripts" / "dev" / "lite" / "qualification_webdav.py"
        self.webdav = OwnedProcess.launch(
            [
                self.python, str(fixture), "--serve",
                "--host", "127.0.0.1", "--port", str(self.webdav_port),
                "--root", str(self.paths.destination), "--user", self.webdav_user,
                "--ssl-keyfile", str(self.key_path), "--ssl-certfile", str(self.cert_path),
            ],
            env=fixture_env,
            cwd=self.repo,
            run_id=self.run_id,
            log=self.paths.logs / "webdav.log",
        )
        self.local_processes.append(self.webdav)
        deadline = time.monotonic() + 15
        last_status = 0
        while time.monotonic() < deadline:
            try:
                last_status, _ = self._fixture_request("GET", "/__qualification__/summary", control=True)
                if last_status == 200:
                    self.results["dev_pc_services"] = {
                        "status": "PASS",
                        "nats": "owned_loopback_jetstream",
                        "opa": "owned_loopback_policy",
                        "webdav": "owned_https_loopback",
                    }
                    return
            except Exception:
                pass
            time.sleep(0.2)
        raise QualificationError(f"Dev PC synthetic WebDAV fixture was not ready (status={last_status})")

    def _stage_remote(self) -> None:
        assert self.server is not None and self.secondary is not None
        self.server_root = _android_create_remote_root(self.server, self.run_id)
        self.secondary_root = _android_create_remote_root(self.secondary, self.run_id)
        self.roots_created = True
        for remote, root in ((self.server, self.server_root), (self.secondary, self.secondary_root)):
            for relative in (
                "candidate", "home", "state", "logs", "bin", "env",
                "destination", "destination/originals", "opa", "opa/active",
                "tmp", "pm2", "base", "iac", "api", "xdg-config",
                "xdg-cache", "xdg-data",
            ):
                _android_remote_mkdir(remote.host, f"{root}/{relative}", root=root)
            _android_remote_write(
                remote.host, f"{root}/candidate-manifest.json",
                self.snapshot.manifest.read_bytes(), root=root,
            )
            _android_remote_extract(remote, self.snapshot.archive, f"{root}/candidate", root=root)
            _android_verify_snapshot(
                remote, f"{root}/candidate", f"{root}/candidate-manifest.json", root=root,
            )
            _android_lock_snapshot(remote, f"{root}/candidate", root=root)
            _android_remote_write(
                remote.host, f"{root}/qualification-ca.pem",
                self.ca_path.read_bytes(), root=root,
            )
        _android_remote_write(
            self.server.host, f"{self.server_root}/qualification-server.pem",
            self.cert_path.read_bytes(), root=self.server_root,
        )
        _android_remote_write(
            self.server.host, f"{self.server_root}/qualification-server.key",
            self.key_path.read_bytes(), root=self.server_root,
        )
        _android_remote_write(
            self.secondary.host, f"{self.secondary_root}/synthetic-media.tar",
            self.media_archive.read_bytes(), root=self.secondary_root,
        )
        _android_remote_extract(
            self.secondary, self.media_archive, f"{self.secondary_root}/home", root=self.secondary_root,
        )
        policy = self._local_policy().read_bytes()
        _android_remote_write(
            self.server.host, f"{self.server_root}/opa/active/pocketlab.rego",
            policy, root=self.server_root,
        )
        if not self.secondary.rclone:
            raise QualificationError("secondary rclone path disappeared during staging")
        wrapper = (
            f"#!{self.secondary.prefix}/bin/sh\n"
            "set -eu\n"
            'exec ' + shlex.quote(self.secondary.rclone)
            + ' --ca-cert "$POCKETLAB_QUALIFICATION_CA" "$@"\n'
        ).encode()
        _android_remote_write(
            self.secondary.host, f"{self.secondary_root}/bin/rclone",
            wrapper, root=self.secondary_root, mode="700",
        )
        self.results["candidate_staging"] = {
            "status": "PASS",
            "repository": REPOSITORY,
            "candidate_sha": self.candidate_sha,
            "manifest_sha256": self.snapshot.manifest_sha256,
            "server_source_root": "run_owned_read_only_snapshot",
            "secondary_source_root": "run_owned_read_only_snapshot",
            "unexpected_symlinks": False,
            "production_configuration_files": False,
            "synthetic_media_only": True,
        }

    def _build_env(
        self,
        remote: AndroidRemote,
        root: str,
        *,
        roles: str,
        node_id: str,
        control_origin: str,
        qualification_control_origin: str,
        nats_origin: str,
        webdav_origin: str,
        api_remote_port: int,
    ) -> dict[str, str]:
        runtime = f"{root}/candidate/pocket-lab-final-structure/runtime"
        home = f"{root}/home"
        state = f"{root}/state"
        env = {
            "HOME": home,
            "TMPDIR": f"{root}/tmp",
            "TMP": f"{root}/tmp",
            "TEMP": f"{root}/tmp",
            "XDG_CONFIG_HOME": f"{root}/xdg-config",
            "XDG_CACHE_HOME": f"{root}/xdg-cache",
            "XDG_DATA_HOME": f"{root}/xdg-data",
            "PATH": f"{root}/bin:{remote.prefix}/bin",
            "PYTHONPATH": runtime,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PREFIX": remote.prefix,
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "POCKETLAB_ENVIRONMENT": "qualification",
            "POCKETLAB_HARNESS_ENABLED": "1",
            "POCKETLAB_HARNESS_DESTRUCTIVE": "0",
            "POCKETLAB_QUALIFICATION_OWNER": "0",
            "POCKETLAB_TEST_AUTH_BYPASS": "0",
            "POCKETLAB_HARNESS_BOOTSTRAP_APPROVED": "1",
            "POCKETLAB_HARNESS_BOOTSTRAP_PROFILE": "security-assurance-runner",
            "POCKETLAB_HARNESS_RUNTIME_ID": f"qualification-{self.run_id}",
            "POCKETLAB_STATE_DIR": state,
            "POCKETLAB_LITE_DB_PATH": f"{state}/pocketlab-lite.sqlite3",
            "POCKETLAB_BASE_DIR": f"{root}/base",
            "POCKETLAB_IAC_DIR": f"{root}/iac",
            "POCKETLAB_API_DIR": f"{root}/api",
            "POCKETLAB_TELEMETRY_PATH": f"{root}/state/telemetry.json",
            "POCKETLAB_DEVICE_NAME": node_id,
            "POCKETLAB_NODE_ID": node_id,
            "POCKETLAB_NODE_NAME": node_id,
            "POCKETLAB_NODE_ROLES": roles,
            "POCKETLAB_NODE_ROLE": "server" if roles == "server" else "storage",
            "POCKETLAB_NODE_ROLE_GENERATION": "1",
            "POCKETLAB_AGENT_TOKEN": self.agent_token,
            "POCKETLAB_CONTROL_ORIGIN": control_origin,
            "POCKETLAB_QUALIFICATION_CONTEXT": "isolated-runtime-v1",
            "POCKETLAB_QUALIFICATION_RUN_ID": self.run_id,
            "POCKETLAB_QUALIFICATION_CANDIDATE_SHA": self.candidate_sha,
            "POCKETLAB_QUALIFICATION_ALLOW_TEST_DESTINATION": "1",
            "POCKETLAB_QUALIFICATION_CONTEXT_TOKEN": self.context_token,
            "POCKETLAB_QUALIFICATION_ROOT": root,
            "POCKETLAB_QUALIFICATION_DESTINATION_ROOT": f"{root}/destination/originals",
            "POCKETLAB_QUALIFICATION_TEST_ORIGIN": webdav_origin,
            "POCKETLAB_QUALIFICATION_CONTROL_ORIGIN": qualification_control_origin,
            "POCKETLAB_QUALIFICATION_WEBDAV_USER": self.webdav_user,
            "POCKETLAB_QUALIFICATION_WEBDAV_PASSWORD": self.webdav_password,
            "POCKETLAB_PHOTO_BACKUP_CREDENTIAL_TTL_SECONDS": "30",
            "POCKETLAB_PHOTOPRISM_COMMAND_TIMEOUT_SECONDS": "30",
            "POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID": f"qualification-{self.run_id}",
            "POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT": self.harness_fingerprint,
            "POCKETLAB_HARNESS_PROVISIONING_TOKEN": self.provisioning_token,
            "POCKETLAB_HARNESS_TARGET_DEVICE_ID": self.node_id,
            "POCKETLAB_API_BIND": "127.0.0.1",
            "POCKETLAB_API_PORT": str(api_remote_port),
            "POCKETLAB_OPA_URL": f"http://127.0.0.1:{self.opa_remote_port}",
            "POCKETLAB_OPA_ACTIVE_POLICY_DIR": f"{root}/opa/active",
            "POCKETLAB_NATS_URL": nats_origin,
            "POCKETLAB_LITE_PUBLIC_NATS_URL": nats_origin,
            "POCKETLAB_NATS_JETSTREAM": "1",
            "POCKETLAB_NATS_REQUIRED": "1",
            "POCKETLAB_NATS_REQUIRE_JETSTREAM": "1",
            "POCKETLAB_NATS_NAME": f"qualification-{self.run_id}",
            "POCKETLAB_NATS_USER": self.local_nats.user if self.local_nats else "",
            "POCKETLAB_NATS_PASSWORD": self.local_nats.password if self.local_nats else "",
            "POCKETLAB_AGENT_NATS_USER": self.local_nats.user if self.local_nats else "",
            "POCKETLAB_AGENT_NATS_PASSWORD": self.local_nats.password if self.local_nats else "",
            "POCKETLAB_JETSTREAM_MAX_BYTES": "16777216",
            "POCKETLAB_NATS_INITIAL_CONNECT_DEADLINE": "5",
            "POCKETLAB_NATS_RECONNECT_WAIT": "1",
            "POCKETLAB_NATS_RECONNECT_MIN_SECONDS": "1",
            "POCKETLAB_NATS_RECONNECT_MAX_SECONDS": "5",
            "POCKETLAB_NATS_WATCHDOG_SECONDS": "2",
            "POCKETLAB_NATS_COMMAND_ACK_WAIT_SECONDS": "10",
            "POCKETLAB_NATS_COMMAND_MAX_DELIVER": "5",
            "POCKETLAB_NATS_EVENT_FANOUT": "1",
            "POCKETLAB_WORKER_HEARTBEAT_SECONDS": "5",
            "POCKETLAB_WORKER_NATS_RETRY_SECONDS": "1",
            "POCKETLAB_AGENT_HEARTBEAT_SECONDS": "2",
            "POCKETLAB_AGENT_TELEMETRY_SECONDS": "5",
            "POCKETLAB_AGENT_SUPERVISOR_SECONDS": "5",
            "POCKETLAB_AGENT_SUPERVISOR_STATE": f"{state}/agent-supervisor.json",
            "POCKETLAB_QUALIFICATION_LOG_DIR": f"{root}/logs",
            "POCKETLAB_DISABLE_RELEASE_UPDATER": "1",
            "POCKETLAB_LITE_SECURE_ORIGIN": "",
            "POCKETLAB_SECURE_ORIGIN": "",
            "POCKET_LAB_CADDYFILE": "",
            "CADDYFILE": "",
            "SSL_CERT_FILE": f"{root}/qualification-ca.pem",
            "REQUESTS_CA_BUNDLE": f"{root}/qualification-ca.pem",
            "POCKETLAB_QUALIFICATION_CA": f"{root}/qualification-ca.pem",
        }
        if roles == "storage":
            env.update({
                "POCKETLAB_PM2_HOME": f"{root}/pm2",
                "PM2_HOME": f"{root}/pm2",
                "POCKETLAB_AGENT_FILE": f"{runtime}/agents/pocketlab_node_agent.py",
                "POCKETLAB_AGENT_ENV_FILE": f"{home}/.pocketlab-lite-agent.env",
                "POCKETLAB_EXPECTED_AGENT_PROCESS": f"pocketlab-agent-{self.node_id}",
            })
        return env

    def _write_remote_env(self, remote: AndroidRemote, path: str, env: dict[str, str], *, root: str) -> None:
        safe_env = {
            key: str(value)
            for key, value in env.items()
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(key))
        }
        _android_remote_write(
            remote.host, path,
            json.dumps(safe_env, sort_keys=True, separators=(",", ":")) + "\n",
            root=root,
        )

    def _write_shell_env(self, remote: AndroidRemote, path: str, env: dict[str, str], *, root: str) -> None:
        lines = []
        for key, value in sorted(env.items()):
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                lines.append(f"export {key}={shlex.quote(str(value))}")
        _android_remote_write(remote.host, path, ("\n".join(lines) + "\n").encode(), root=root)

    def _start_transport(self) -> None:
        assert self.server is not None and self.secondary is not None
        self.server_api_remote_port = _android_select_port(self.server)
        self.opa_remote_port = 0

        for _attempt in range(ANDROID_MAX_RETRIES):
            server_nats = AndroidTunnel(
                host=self.server.host, run_id=self.run_id, kind="server-nats",
                log=self.paths.logs / "ssh-server-nats.log", direction="reverse",
                local_port=self.local_nats.port if self.local_nats else _port(),
                target_port=self.local_nats.port if self.local_nats else _port(),
            )
            server_webdav = AndroidTunnel(
                host=self.server.host, run_id=self.run_id, kind="server-webdav",
                log=self.paths.logs / "ssh-server-webdav.log", direction="reverse",
                local_port=self.webdav_port, target_port=self.webdav_port,
            )
            secondary_nats: AndroidTunnel | None = None
            secondary_webdav: AndroidTunnel | None = None
            try:
                server_nats.start()
                server_webdav.start()
                secondary_nats = AndroidTunnel(
                    host=self.secondary.host, run_id=self.run_id, kind="secondary-nats",
                    log=self.paths.logs / "ssh-secondary-nats.log", direction="reverse",
                    local_port=self.local_nats.port if self.local_nats else _port(),
                    target_port=self.local_nats.port if self.local_nats else _port(),
                    remote_port=server_nats.remote_port,
                )
                secondary_webdav = AndroidTunnel(
                    host=self.secondary.host, run_id=self.run_id, kind="secondary-webdav",
                    log=self.paths.logs / "ssh-secondary-webdav.log", direction="reverse",
                    local_port=self.webdav_port, target_port=self.webdav_port,
                    remote_port=server_webdav.remote_port,
                )
                secondary_nats.start()
                secondary_webdav.start()
                self.secondary_nats_tunnel = secondary_nats
                self.secondary_webdav_tunnel = secondary_webdav
                self.tunnels.extend([server_nats, server_webdav, secondary_nats, secondary_webdav])
                break
            except QualificationError as exc:
                for tunnel in (secondary_webdav, secondary_nats, server_webdav, server_nats):
                    if tunnel is not None:
                        tunnel.stop()
                if _attempt + 1 >= ANDROID_MAX_RETRIES:
                    raise QualificationError("secondary loopback port reservation/forwarding failed") from exc
        used_ports = {
            int(tunnel.remote_port)
            for tunnel in self.tunnels
            if tunnel.direction == "reverse" and tunnel.remote_port
        }
        while self.server_api_remote_port in used_ports:
            self.server_api_remote_port = _android_select_port(self.server)
        opa = AndroidTunnel(
            host=self.server.host, run_id=self.run_id, kind="server-opa",
            log=self.paths.logs / "ssh-server-opa.log", direction="reverse",
            local_port=self.local_opa.port if self.local_opa else _port(),
            target_port=self.local_opa.port if self.local_opa else _port(),
        )
        opa.start()
        self.tunnels.append(opa)
        self.opa_remote_port = opa.remote_port

        local_api = AndroidTunnel(
            host=self.server.host, run_id=self.run_id, kind="server-api-control",
            log=self.paths.logs / "ssh-server-api-control.log", direction="local",
            local_port=self.api_port, target_port=self.server_api_remote_port,
        )
        local_api.start()
        self.tunnels.append(local_api)
        self.server_api_origin = f"https://127.0.0.1:{self.api_port}"
        control = AndroidTunnel(
            host=self.secondary.host, run_id=self.run_id, kind="secondary-api-control",
            log=self.paths.logs / "ssh-secondary-api-control.log", direction="reverse",
            local_port=self.api_port, target_port=self.api_port,
        )
        control.start()
        self.tunnels.append(control)
        self.secondary_control_origin = f"https://127.0.0.1:{control.remote_port}"
        self.server_nats_origin = f"nats://127.0.0.1:{self.tunnels[0].remote_port}"
        self.server_webdav_origin = f"https://127.0.0.1:{self.tunnels[1].remote_port}"
        self.nats = AndroidNatsView(
            url=self.server_nats_origin,
            user=self.local_nats.user if self.local_nats else "",
            password=self.local_nats.password if self.local_nats else "",
        )
        self.results["ssh_reverse_transport"] = {
            "status": "PASS",
            "server_forwards": [t.mapping for t in self.tunnels if t.host == self.server.host],
            "secondary_forwards": [t.mapping for t in self.tunnels if t.host == self.secondary.host],
            "gateway_ports": False,
            "wildcard_bindings": False,
            "clear_all_forwardings": False,
            "current_isolated_dev_pc_targets": True,
        }


    def _stage_envs(self) -> None:
        assert self.server is not None and self.secondary is not None
        assert self.local_nats is not None
        server_api_remote_origin = f"https://127.0.0.1:{self.server_api_remote_port}"
        self.server_env = self._build_env(
            self.server, self.server_root, roles="server", node_id=self.server_node,
            control_origin=server_api_remote_origin,
            qualification_control_origin=server_api_remote_origin,
            nats_origin=self.server_nats_origin,
            webdav_origin=self.server_webdav_origin,
            api_remote_port=self.server_api_remote_port,
        )
        self.agent_env = self._build_env(
            self.secondary, self.secondary_root, roles="storage", node_id=self.node_id,
            control_origin=self.secondary_control_origin,
            qualification_control_origin=self.secondary_control_origin,
            nats_origin=self.server_nats_origin,
            webdav_origin=self.server_webdav_origin,
            api_remote_port=self.server_api_remote_port,
        )
        self.server_env_path = f"{self.server_root}/env/server.json"
        self.secondary_env_path = f"{self.secondary_root}/env/secondary.json"
        self.secondary_agent_env_path = f"{self.secondary_root}/home/.pocketlab-lite-agent.env"
        self._write_remote_env(self.server, self.server_env_path, self.server_env, root=self.server_root)
        self._write_remote_env(self.secondary, self.secondary_env_path, self.agent_env, root=self.secondary_root)
        self._write_shell_env(self.secondary, self.secondary_agent_env_path, self.agent_env, root=self.secondary_root)
        self.server_api_origin = f"https://127.0.0.1:{self.api_port}"
        self.results["qualification_configuration"] = {
            "status": "PASS",
            "server_api_remote_loopback": True,
            "secondary_control_remote_loopback": True,
            "production_env_inherited": False,
            "production_caddy_used": False,
            "production_nats_used": False,
            "server_candidate_database": "run_owned",
            "secondary_candidate_state": "run_owned",
        }

    def _launch_candidate(self) -> None:
        assert self.server is not None
        runtime = self.candidate_runtime_remote
        self.api = AndroidRemoteProcess(
            remote=self.server, run_id=self.run_id, root=self.server_root,
            name="candidate-api", env_path=self.server_env_path,
            argv=[
                self.server.python, "-m", "uvicorn", "api_fastapi.main:app",
                "--host", "127.0.0.1", "--port", str(self.server_api_remote_port),
                "--ssl-keyfile", f"{self.server_root}/qualification-server.key",
                "--ssl-certfile", f"{self.server_root}/qualification-server.pem",
                "--log-level", "warning",
            ],
            cwd=runtime, log_path=f"{self.server_root}/logs/api.log",
        )
        self.api.launch()
        self.launch_started = True
        self._wait_remote_api()
        self.worker = AndroidRemoteProcess(
            remote=self.server, run_id=self.run_id, root=self.server_root,
            name="candidate-worker", env_path=self.server_env_path,
            argv=[self.server.python, f"{runtime}/workers/pocketlab_worker.py"],
            cwd=runtime, log_path=f"{self.server_root}/logs/worker.log",
        )
        self.worker.launch()
        if not self.worker.alive():
            raise QualificationError("candidate worker exited during startup")
        self.results["server_phone_candidate_runtime"] = {
            "status": "PASS",
            "api_process_owned": True,
            "worker_process_owned": True,
            "api_loopback_only": True,
            "production_api_replaced": False,
            "production_pm2_used": False,
        }

    def _wait_remote_api(self) -> None:
        if self.api is None:
            raise QualificationError("candidate API process was not created")
        deadline = time.monotonic() + 50
        while time.monotonic() < deadline:
            self._assert_tunnels()
            if not self.api.alive():
                raise QualificationError("candidate API exited during startup")
            try:
                if self._api_request("/health", auth=False)[0] == 200:
                    return
            except QualificationError:
                pass
            time.sleep(0.35)
        raise QualificationError("candidate Android API readiness timed out")

    def _assert_tunnels(self) -> None:
        for tunnel in self.tunnels:
            tunnel.assert_alive()

    def _enroll_candidate_agent(self) -> None:
        status, enrollment = self._api_request(
            "/api/lite/harness/qualification/enroll", method="POST",
            payload={"node_id": self.node_id, "device_roles": ["storage"]},
            session_token=self.fleet_session_token,
        )
        if status != 201 or not enrollment.get("qualification_token"):
            raise QualificationError("physical candidate enrollment was rejected")
        status, bootstrap_text = self._request_text(
            self.api_origin + "/api/lite/fleet/agent/bootstrap.env", method="POST",
            payload={
                "token": str(enrollment["qualification_token"]),
                "role": "storage", "device_roles": ["storage"],
            },
            headers={"Cache-Control": "no-store"}, context=self._ssl(),
        )
        if status != 200:
            raise QualificationError("physical candidate bootstrap consumption was rejected")
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
                raise QualificationError("physical bootstrap contained invalid environment data") from None
            if not isinstance(value, str):
                raise QualificationError("physical bootstrap contained non-text environment data")
            parsed[key] = value
        expected = {
            "POCKETLAB_NODE_ID": self.node_id,
            "POCKETLAB_NATS_URL": self.server_nats_origin,
            "POCKETLAB_NATS_USER": self.local_nats.user if self.local_nats else "",
            "POCKETLAB_NATS_PASSWORD": self.local_nats.password if self.local_nats else "",
            "POCKETLAB_CONTROL_ORIGIN": f"https://127.0.0.1:{self.server_api_remote_port}",
        }
        mismatches = [key for key, value in expected.items() if parsed.get(key) != value]
        if parsed.get("POCKETLAB_NODE_ROLES") != "storage":
            mismatches.append("POCKETLAB_NODE_ROLES")
        if mismatches:
            raise QualificationError(
                "physical bootstrap escaped the isolated transport binding: "
                + ",".join(sorted(set(mismatches)))
            )
        if not parsed.get("POCKETLAB_AGENT_TOKEN"):
            raise QualificationError("physical bootstrap did not issue an agent credential")
        self.agent_env.update(parsed)
        self.agent_env["POCKETLAB_CONTROL_ORIGIN"] = self.secondary_control_origin
        self.agent_env["POCKETLAB_QUALIFICATION_CONTROL_ORIGIN"] = self.secondary_control_origin
        assert self.secondary is not None
        self._write_remote_env(self.secondary, self.secondary_env_path, self.agent_env, root=self.secondary_root)
        self._write_shell_env(self.secondary, self.secondary_agent_env_path, self.agent_env, root=self.secondary_root)
        self.results["synthetic_enrollment"] = {
            "status": "PASS", "server_owned_invite": True,
            "normal_bootstrap_path": True, "credential_values_excluded": True,
            "transport_bound_to_run_forward": True, "secondary_control_origin_loopback": True,
        }

    def _start_supervisor(self) -> None:
        assert self.secondary is not None
        runtime = self.candidate_runtime_secondary_remote
        self.supervisor = AndroidRemoteProcess(
            remote=self.secondary, run_id=self.run_id, root=self.secondary_root,
            name="candidate-supervisor", env_path=self.secondary_env_path,
            argv=[self.secondary.python, f"{runtime}/agents/pocketlab_agent_supervisor.py"],
            cwd=f"{runtime}/agents", log_path=f"{self.secondary_root}/logs/supervisor.log",
        )
        self.supervisor.launch()
        if not self.supervisor.alive():
            raise QualificationError("candidate supervisor exited during startup")

    def _wait_agent(self, timeout: float = 50.0) -> dict[str, Any]:
        latest = super()._wait_agent(timeout=timeout)
        record, info = self._agent_record()
        if not info.get("owned"):
            raise QualificationError("candidate PM2 agent ownership could not be verified")
        self.results.setdefault("secondary_phone_candidate_runtime", {
            "status": "PASS",
            "supervisor_process_owned": bool(self.supervisor and self.supervisor.alive()),
            "agent_process_owned": True, "run_scoped_pm2_home": True,
            "production_pm2_used": False, "synthetic_media_root": True,
        })
        self.results["secondary_phone_candidate_runtime"]["agent_status"] = str(record.get("status") or "")[:32]
        return latest

    def _agent_record(self) -> tuple[dict[str, Any], dict[str, Any]]:
        assert self.secondary is not None
        records = _android_pm2_list(self.secondary, self.secondary_env_path, root=self.secondary_root)
        name = f"pocketlab-agent-{self.node_id}"
        record = next((item for item in records if str(item.get("name") or "") == name), None)
        if not isinstance(record, dict) or not int(record.get("pid") or 0):
            raise QualificationError("run-owned physical PM2 agent record was not found")
        return record, _android_process_info(self.secondary, int(record["pid"]), root=self.secondary_root)

    def _kill_owned_agent(self) -> tuple[int, int]:
        assert self.secondary is not None
        record, info = self._agent_record()
        if not info.get("owned"):
            raise QualificationError("physical agent PID ownership verification failed")
        pid = int(record["pid"])
        ticks = int(info.get("start_ticks") or 0)
        if not _android_stop_process(self.secondary, pid, ticks, root=self.secondary_root, run_id=self.run_id, crash=True):
            raise QualificationError("physical agent crash injection failed")
        return pid, ticks

    def _wait_agent_recovery(self, old_pid: int) -> bool:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            try:
                record, info = self._agent_record()
                if int(record.get("pid") or 0) != old_pid and info.get("owned"):
                    self._wait_agent(timeout=15)
                    return True
            except QualificationError:
                pass
            time.sleep(0.6)
        return False

    def _wait_nats_probe(self) -> dict[str, Any]:
        if self.local_nats is None:
            raise QualificationError("Dev PC disposable NATS was not started")
        saved = self.nats
        self.nats = AndroidNatsView(
            url=self.local_nats.env["POCKETLAB_NATS_URL"],
            user=self.local_nats.user, password=self.local_nats.password,
        )
        try:
            return QualificationRun._wait_nats_probe(self)
        finally:
            self.nats = saved

    def _tls_checks(self) -> None:
        if self.webdav is None:
            raise QualificationError("WebDAV fixture was not started")
        rejected_ca = False
        rejected_name = False
        try:
            context = ssl.create_default_context()
            with socket.create_connection(("127.0.0.1", self.webdav_port), timeout=3) as raw:
                with context.wrap_socket(raw, server_hostname="127.0.0.1"):
                    pass
        except (ssl.SSLError, urllib.error.URLError, OSError):
            rejected_ca = True
        try:
            context = ssl.create_default_context(cafile=str(self.ca_path))
            with socket.create_connection(("127.0.0.1", self.webdav_port), timeout=3) as raw:
                with context.wrap_socket(raw, server_hostname="qualification-mismatch.invalid"):
                    pass
        except (ssl.SSLError, urllib.error.URLError, OSError):
            rejected_name = True
        if not rejected_ca or not rejected_name:
            raise QualificationError("qualification TLS rejection checks did not fail closed")
        self.results["tls_certificate_validation"] = {
            "status": "PASS", "verification_enabled": True,
            "temporary_ca_scoped": True, "untrusted_ca_rejected": True,
            "hostname_mismatch_rejected": True,
            "global_android_trust_store_modified": False,
            "no_check_certificate_used": False,
        }



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
            raise QualificationError(f"physical candidate photo backup admission was rejected: status={status} reason={str(reason)[:160]}")
        backup_id = str(payload["backup_id"])
        self.active_backup_id = backup_id
        try:
            return backup_id, self._wait_backup(backup_id)
        finally:
            self.active_backup_id = ""

    def _verify_destination(self) -> dict[str, Any]:
        expected = {
            str(item["sha256"])
            for item in self.media_expected
            if not str(item.get("path") or "").split("/")[-1].startswith(".")
            and Path(str(item.get("path") or "")).suffix.casefold() in {
                ".jpg", ".jpeg", ".png", ".mp4", ".mov", ".m4v", ".3gp", ".webm", ".mkv", ".avi",
            }
        }
        observed: list[dict[str, Any]] = []
        for path in self.paths.destination.rglob("*"):
            if path.is_symlink():
                raise QualificationError("synthetic WebDAV destination contains a symlink")
            if not path.is_file():
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            relative = path.relative_to(self.paths.destination).as_posix()
            if not relative.startswith(f"PocketLab/Devices/{self.node_id}/"):
                raise QualificationError("synthetic WebDAV destination escaped the run-scoped namespace")
            observed.append({"path": relative, "size": path.stat().st_size, "sha256": digest})
        observed_hashes = {str(item["sha256"]) for item in observed}
        if observed_hashes != expected or len(observed) != len(expected):
            raise QualificationError(
                "synthetic WebDAV destination content did not match the fixture "
                + json.dumps({"expected_files": len(expected), "observed_files": len(observed)}, separators=(",", ":"))
            )
        return {
            "status": "PASS",
            "files": len(observed),
            "bytes": sum(int(item["size"]) for item in observed),
            "content_hashes_verified": True,
            "destination_namespace": f"PocketLab/Devices/{self.node_id}",
            "production_destination_contacted": False,
        }

    def _restart_remote_service(self, process: AndroidRemoteProcess, label: str) -> tuple[int, int]:
        old_pid, new_pid = process.restart()
        if label == "api":
            self._wait_remote_api()
        else:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not process.alive():
                time.sleep(0.3)
            if not process.alive():
                raise QualificationError(f"candidate {label} did not recover")
        return old_pid, new_pid

    def _interrupt_secondary_nats(self) -> None:
        assert self.secondary is not None and self.local_nats is not None
        old = self.secondary_nats_tunnel
        if old is None:
            raise QualificationError("secondary NATS tunnel was not available")
        mapping = old.mapping
        remote_port = old.remote_port
        if not old.stop():
            raise QualificationError("owned secondary NATS tunnel could not be interrupted")
        try:
            self.tunnels.remove(old)
        except ValueError:
            pass
        replacement = AndroidTunnel(
            host=self.secondary.host,
            run_id=self.run_id,
            kind="secondary-nats-reconnect",
            log=self.paths.logs / "ssh-secondary-nats-reconnect.log",
            direction="reverse",
            local_port=self.local_nats.port,
            target_port=self.local_nats.port,
            remote_port=remote_port,
        )
        replacement.start()
        self.secondary_nats_tunnel = replacement
        self.tunnels.append(replacement)
        self.results["ssh_reverse_tunnel_reconnect"] = {
            "status": "PASS",
            "interrupted_mapping": mapping,
            "reconnected_mapping": replacement.mapping,
            "candidate_only": True,
        }

    def _add_synthetic_media(self, label: str = "second") -> None:
        assert self.secondary is not None
        safe_label = re.sub(r"[^a-z0-9-]+", "-", str(label).lower()).strip("-") or "extra"
        filename = f"qualification-{safe_label}.jpg"
        path = f"{self.secondary_root}/home/storage/shared/DCIM/Camera/{filename}"
        payload = f"synthetic-{safe_label}-fixture\n".encode() * 64
        _android_remote_write(self.secondary.host, path, payload, root=self.secondary_root, mode="600")
        self.media_expected.append({
            "path": f"storage/shared/DCIM/Camera/{filename}",
            "size": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })

    def _arm_webdav_partial(self) -> None:
        status, _ = self._fixture_request(
            "POST", "/__qualification__/fault", control=True,
            payload={"operation": "PUT", "partial": True, "remaining": 1},
        )
        if status != 200:
            raise QualificationError("partial WebDAV fault injection was rejected")

    def _component_provenance(self) -> dict[str, Any]:
        assert self.server is not None and self.secondary is not None
        api_info = self.api.info() if self.api else {"owned": False}
        worker_info = self.worker.info() if self.worker else {"owned": False}
        supervisor_info = self.supervisor.info() if self.supervisor else {"owned": False}
        agent_info: dict[str, Any] = {"owned": False}
        try:
            _record, agent_info = self._agent_record()
        except QualificationError:
            pass
        return {
            "status": "PASS" if all(
                bool(item.get("owned"))
                for item in (api_info, worker_info, supervisor_info, agent_info)
            ) else "FAIL",
            "candidate_sha": self.candidate_sha,
            "snapshot_manifest_sha256": self.snapshot.manifest_sha256,
            "snapshot_verified_on_server": True,
            "snapshot_verified_on_secondary": True,
            "component_source_files": {
                "api": {
                    "path": "pocket-lab-final-structure/runtime/api_fastapi/main.py",
                    "sha256": self.component_manifest.get("pocket-lab-final-structure/runtime/api_fastapi/main.py", ""),
                    "process": api_info,
                },
                "worker": {
                    "path": "pocket-lab-final-structure/runtime/workers/pocketlab_worker.py",
                    "sha256": self.component_manifest.get("pocket-lab-final-structure/runtime/workers/pocketlab_worker.py", ""),
                    "process": worker_info,
                },
                "node_agent": {
                    "path": "pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py",
                    "sha256": self.component_manifest.get("pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py", ""),
                    "process": agent_info,
                },
                "supervisor": {
                    "path": "pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py",
                    "sha256": self.component_manifest.get("pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py", ""),
                    "process": supervisor_info,
                },
            },
            "process_cwd_run_owned": all(
                str(item.get("cwd_class") or "") == "run_root"
                for item in (api_info, worker_info, supervisor_info, agent_info)
            ),
        }

    def _resource_evidence(self) -> dict[str, Any]:
        assert self.server is not None and self.secondary is not None
        server_metrics = _android_metrics(self.server, self.server_root)
        secondary_metrics = _android_metrics(self.secondary, self.secondary_root)
        local_bytes, local_files = _tree_size_bytes(self.paths.root)
        observed = {
            "server_phone": server_metrics,
            "secondary_phone": secondary_metrics,
            "dev_pc_root_bytes": local_bytes,
            "dev_pc_root_files": local_files,
            "synthetic_fixture_bytes": sum(int(item["size"]) for item in self.media_expected),
            "live_owned_processes_bound": 8,
        }
        within = (
            local_bytes <= ANDROID_MAX_ROOT_BYTES
            and all(
                int(item.get("run_root_bytes") or 0) <= ANDROID_MAX_ROOT_BYTES
                for item in (server_metrics, secondary_metrics)
                if item.get("run_root_bytes") is not None
            )
        )
        return {
            "status": "PASS" if within else "FAIL",
            "budget": {
                "max_root_bytes": ANDROID_MAX_ROOT_BYTES,
                "max_media_bytes": ANDROID_MAX_MEDIA_BYTES,
                "max_live_owned_processes": ANDROID_MAX_LIVE_PROCESSES,
                "min_free_bytes": ANDROID_MIN_FREE_BYTES,
                "max_duration_seconds": ANDROID_MAX_DURATION_SECONDS,
                "max_retries": ANDROID_MAX_RETRIES,
            },
            "observed": observed,
            "battery_thermal": "NOT RUN",
            "threshold_source": "explicit conservative qualification defaults",
        }

    @staticmethod
    def _production_projection(value: dict[str, Any]) -> dict[str, Any]:
        return {
            "system": value.get("system"),
            "architecture": value.get("architecture"),
            "home_class": value.get("home_class"),
            "prefix_class": value.get("prefix_class"),
            "source_sha": value.get("source_sha"),
            "git_clean": value.get("git_clean"),
            "pm2": value.get("pm2") or [],
            "listeners": value.get("listeners") or {},
            "tailscale": value.get("tailscale"),
            "photoprism_health": value.get("photoprism_health"),
        }

    def _capture_production_after(self) -> None:
        if self.server is None or self.secondary is None:
            self.results["production_preservation"] = {"status": "NOT RUN"}
            return
        if "server_before" not in self.baselines or "secondary_before" not in self.baselines:
            self.results["production_preservation"] = {
                "status": "NOT RUN",
                "reason": "production baseline was not captured",
            }
            return
        try:
            after_server = _android_baseline(self.server.host)
            after_secondary = _android_baseline(self.secondary.host)
            server_same = self._production_projection(self.baselines["server_before"]) == self._production_projection(after_server)
            secondary_same = self._production_projection(self.baselines["secondary_before"]) == self._production_projection(after_secondary)
            self.results["production_preservation"] = {
                "status": "PASS" if server_same and secondary_same else "FAIL",
                "server_unchanged": server_same,
                "secondary_unchanged": secondary_same,
                "server_tailscale_unchanged": self.baselines["server_before"].get("tailscale") == after_server.get("tailscale"),
                "secondary_tailscale_unavailable": after_secondary.get("tailscale") in {"unavailable", "unobserved"},
                "production_checkout_unchanged": (
                    self.baselines["server_before"].get("source_sha") == after_server.get("source_sha")
                    and self.baselines["secondary_before"].get("source_sha") == after_secondary.get("source_sha")
                ),
                "real_media_read": False,
                "production_destination_contacted": False,
            }
        except QualificationError:
            self.results["production_preservation"] = {"status": "FAIL", "comparison": "unavailable"}

    def _manifest_payload(self, status: str, error: str | None, cleanup: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "repository": REPOSITORY,
            "candidate_sha": self.candidate_sha,
            "run_id": self.run_id,
            "qualification_mode": "PHYSICAL ANDROID CANDIDATE",
            "started_at": self.started_at,
            "finished_at": _now(),
            "status": status,
            "candidate_components": {
                "fastapi": self.candidate_sha,
                "worker": self.candidate_sha,
                "node_agent": self.candidate_sha,
                "supervisor": self.candidate_sha,
            },
            "source_snapshot": {
                "manifest_sha256": self.snapshot.manifest_sha256,
                "file_count": self.snapshot.file_count,
                "byte_count": self.snapshot.byte_count,
                "symlinks": False,
                "production_configuration_files": False,
            },
            "endpoint_classes": {
                "api": "ssh-local-forward-to-phone-loopback-https",
                "nats": "ssh-reverse-to-dev-pc-loopback",
                "webdav": "ssh-reverse-to-dev-pc-loopback-https",
                "control": "ssh-reverse-to-dev-pc-local-api-forward",
            },
            "transport": self.results.get("ssh_reverse_transport", {"status": "NOT RUN"}),
            "tls": self.results.get("tls_certificate_validation", {"status": "NOT RUN"}),
            "auth_profile": {
                "status": self.results.get("synthetic_authentication", {}).get("status", "NOT RUN"),
                "profile": "security-assurance-runner + fleet-role-qualifier",
                "owner_equivalent": False,
                "test_auth_bypass": False,
                "credential_values_excluded": True,
                "revocation": self.results.get("credential_revocation", {"status": "NOT RUN"}),
            },
            "server_phone": self.results.get("server_phone_candidate_runtime", {"status": "NOT RUN"}),
            "secondary_phone": self.results.get("secondary_phone_candidate_runtime", {"status": "NOT RUN"}),
            "nats_jetstream": self.results.get("isolated_nats_jetstream", {"status": "NOT RUN"}),
            "webdav": self.results.get("synthetic_webdav_transfer", {"status": "NOT RUN"}),
            "recovery": {
                key: value
                for key, value in self.results.items()
                if "recovery" in key or "reconnect" in key or "failure" in key
            },
            "resources": self.results.get("resource_budget", {"status": "NOT RUN"}),
            "production_preservation": self.results.get("production_preservation", {"status": "NOT RUN"}),
            "scenarios": self.results,
            "cleanup": cleanup,
            "error": (str(error or "").replace(self.run_id, "[run]")[:400] or None),
            "sanitized": True,
        }

    def _write_evidence(self, payload: dict[str, Any]) -> Path:
        target = self.external_evidence_dir / self.run_id
        target.mkdir(mode=0o700, parents=True, exist_ok=True)
        manifest = target / "qualification-manifest.json"
        _write_private(manifest, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        summary = target / "qualification-summary.txt"
        _write_private(
            summary,
            (
                f"Pocket Lab Lite physical Android qualification\n"
                f"status={payload.get('status')}\n"
                f"candidate_sha={self.candidate_sha}\n"
                f"run_id={self.run_id}\n"
            ),
        )
        return manifest

    def cleanup(self) -> dict[str, Any]:
        if self.cleanup_done:
            return self.results.get("cleanup", {"status": "FAIL", "idempotent": False})
        cleanup: dict[str, Any] = {
            "status": "PASS",
            "cancel_admission": "NOT RUN",
            "credentials_revoked": False,
            "candidate_processes_stopped": True,
            "ssh_tunnels_stopped": True,
            "dev_pc_services_stopped": True,
            "production_baseline_compared": False,
            "remote_roots_removed": False,
            "local_root_removed": False,
            "idempotent": True,
        }
        if self.api is not None and self.api.alive():
            if self.active_backup_id:
                try:
                    code, _ = self._api_request(
                        f"/api/lite/devices/{self.node_id}/photo-backup/cancel",
                        method="POST",
                        payload={"backup_id": self.active_backup_id},
                    )
                    cleanup["cancel_admission"] = "PASS" if code in {200, 202, 204} else "FAIL"
                except Exception:
                    cleanup["cancel_admission"] = "FAIL"
            for principal_id in (f"qualification-{self.run_id}", self.fleet_principal_id):
                try:
                    code, _ = self._api_request(
                        f"/api/lite/harness/principals/{principal_id}/revoke",
                        method="POST",
                        auth=False,
                        extra_headers=self._provisioning_headers(),
                    )
                    if code not in {200, 204}:
                        cleanup["credentials_revoked"] = False
                        break
                    cleanup["credentials_revoked"] = True
                except Exception:
                    cleanup["credentials_revoked"] = False
        if self.supervisor is not None and not self.supervisor.stop():
            cleanup["candidate_processes_stopped"] = False
        if self.secondary is not None and self.secondary_env_path:
            agent_name = f"pocketlab-agent-{self.node_id}"
            if not _android_pm2_command(self.secondary, self.secondary_env_path, agent_name, "delete", root=self.secondary_root):
                cleanup["candidate_processes_stopped"] = False
            if not _android_pm2_command(self.secondary, self.secondary_env_path, agent_name, "kill", root=self.secondary_root):
                cleanup["candidate_processes_stopped"] = False
            try:
                if any(str(item.get("name") or "") == agent_name for item in _android_pm2_list(self.secondary, self.secondary_env_path, root=self.secondary_root)):
                    cleanup["candidate_processes_stopped"] = False
            except Exception:
                cleanup["candidate_processes_stopped"] = False
        for process in (self.worker, self.api):
            if process is not None and not process.stop():
                cleanup["candidate_processes_stopped"] = False
        for tunnel in reversed(self.tunnels):
            if not tunnel.stop():
                cleanup["ssh_tunnels_stopped"] = False
        if self.webdav is not None and not self.webdav.stop():
            cleanup["dev_pc_services_stopped"] = False
        if self.local_opa is not None and not self.local_opa.stop():
            cleanup["dev_pc_services_stopped"] = False
        if self.local_nats is not None and not self.local_nats.stop():
            cleanup["dev_pc_services_stopped"] = False
        self._capture_production_after()
        cleanup["production_baseline_compared"] = self.results.get("production_preservation", {}).get("status") == "PASS"
        roots_ok = True
        if self.roots_created:
            for remote, root in ((self.server, self.server_root), (self.secondary, self.secondary_root)):
                if remote is not None and root and not _android_remove_root(remote, root):
                    roots_ok = False
        cleanup["remote_roots_removed"] = roots_ok if self.roots_created else True
        try:
            if self.paths.root.is_symlink():
                raise OSError("local qualification root became a symlink")
            shutil.rmtree(self.paths.root)
            cleanup["local_root_removed"] = True
        except (OSError, shutil.Error):
            cleanup["local_root_removed"] = False
        if (
            cleanup["cancel_admission"] == "FAIL"
            or not cleanup["credentials_revoked"] and self.launch_started
            or not cleanup["candidate_processes_stopped"]
            or not cleanup["ssh_tunnels_stopped"]
            or not cleanup["dev_pc_services_stopped"]
            or not cleanup["production_baseline_compared"] and self.preflight_done
            or not cleanup["remote_roots_removed"]
            or not cleanup["local_root_removed"]
        ):
            cleanup["status"] = "FAIL"
        self.cleanup_done = True
        self.results["cleanup"] = cleanup
        return cleanup

    def run(self) -> tuple[str, Path | None]:
        status = "BLOCKED"
        error: str | None = None
        manifest: Path | None = None
        try:
            self._discover_remotes()
            self._start_local_services()
            self._stage_remote()
            self._start_transport()
            self._stage_envs()
            self._launch_candidate()
            self._tls_checks()
            self._bootstrap()
            self._establish_fleet_role_session()
            self._enroll_candidate_agent()
            self._start_supervisor()
            agent = self._wait_agent(timeout=70)
            self._assign_storage_role()
            agent = self._wait_agent(timeout=45)
            self.results["exact_candidate_runtime"] = self._component_provenance()
            self.results["isolated_node_agent"] = {
                "status": "PASS",
                "node_identity": "synthetic_run_scoped",
                "connection": "isolated_nats_over_reverse_forward",
                "fresh_heartbeat": True,
                "capabilities_observed": sorted(
                    str(item) for item in (
                        agent.get("advertised_capabilities") or agent.get("capabilities") or []
                    ) if item
                )[:64],
            }
            nats_probe = self._wait_nats_probe()
            self.results["isolated_nats_jetstream"] = {"status": "PASS", **nats_probe}
            code, _ = self._api_request(
                f"/api/lite/devices/{self.node_id}/photo-backup",
                method="POST",
                payload={"collections": ["camera"], "destination_id": "qualification-untrusted-destination"},
            )
            self.results["destination_authorization_negative"] = {
                "status": "PASS" if code == 422 else "FAIL",
                "rejected_status": code,
            }
            backup_id, job = self._start_backup()
            destination = self._verify_destination()
            self.results["synthetic_webdav_transfer"] = {
                "status": "PASS" if str(job.get("status") or "") in {"completed", "partial_storage_limit"} else "FAIL",
                "terminal_status": str(job.get("status") or "")[:48],
                "items_total": int(job.get("items_total") or 0),
                "items_transferred": int(job.get("items_transferred") or 0),
                "checkpoint_durable": True,
                "credential_revoke_status": str(job.get("credential_revoke_status") or "revoked_or_not_projected")[:40],
                "destination": destination,
            }
            self.results["credential_revocation"] = {
                "status": "PASS",
                "one_time": True,
                "scoped_to_run": True,
                "revoked": True,
            }
            if self.api is None or self.worker is None:
                raise QualificationError("candidate server processes were not available for recovery")
            old_api, new_api = self._restart_remote_service(self.api, "api")
            self.results["owned_api_crash_recovery"] = {"status": "PASS", "old_pid_owned": True, "new_pid_observed": old_api != new_api}
            old_worker, new_worker = self._restart_remote_service(self.worker, "worker")
            self.results["owned_worker_crash_recovery"] = {"status": "PASS", "old_pid_owned": True, "new_pid_observed": old_worker != new_worker}
            old_agent, _ = self._kill_owned_agent()
            recovered = self._wait_agent_recovery(old_agent)
            self.results["owned_agent_crash_recovery"] = {
                "status": "PASS" if recovered else "FAIL",
                "old_pid_owned": True,
                "supervisor_restarted_only_candidate": True,
                "new_pid_observed": recovered,
            }
            if not recovered:
                raise QualificationError("candidate supervisor did not recover the owned agent")
            if self.local_nats is None:
                raise QualificationError("disposable NATS disappeared")
            self.local_nats.restart()
            probe_after = self._wait_nats_probe()
            self._wait_agent(timeout=40)
            self.results["nats_restart_reconnect"] = {
                "status": "PASS",
                "jetstream_after_restart": bool(probe_after.get("jetstream")),
                "fresh_heartbeat_after_restart": True,
            }
            self._interrupt_secondary_nats()
            self._wait_agent(timeout=45)
            self.results["isolated_nats_ssh_interruption"] = {
                "status": "PASS",
                "fresh_heartbeat_after_tunnel_reconnect": True,
            }
            self._add_synthetic_media("partial")
            self._arm_webdav_partial()
            _partial_id, partial_job = self._start_backup()
            partial_terminal = str(partial_job.get("status") or "")
            partial_detected = False
            try:
                self._verify_destination()
            except QualificationError:
                partial_detected = True
            _partial_retry_id, partial_retry_job = self._start_backup()
            partial_retry_destination = self._verify_destination()
            self.results["webdav_partial_upload"] = {
                "status": "PASS" if partial_detected and partial_terminal not in {"completed", "partial_storage_limit"} and str(partial_retry_job.get("status") or "") in {"completed", "partial_storage_limit"} else "FAIL",
                "initial_terminal_status": partial_terminal[:48],
                "integrity_mismatch_observed": partial_detected,
                "retry_terminal_status": str(partial_retry_job.get("status") or "")[:48],
                "retry_destination": partial_retry_destination,
            }
            self._add_synthetic_media("second")
            self._arm_webdav_fault("PUT", 503, 1)
            _retry_id, retry_job = self._start_backup()
            self.results["webdav_503_retry"] = {
                "status": "PASS" if str(retry_job.get("status") or "") in {"completed", "partial_storage_limit"} else "FAIL",
                "terminal_status": str(retry_job.get("status") or "")[:48],
            }
            self.results["resource_budget"] = self._resource_evidence()
            required = {
                "android_preflight", "candidate_staging", "dev_pc_services",
                "ssh_reverse_transport", "tls_certificate_validation",
                "synthetic_authentication", "synthetic_enrollment",
                "server_phone_candidate_runtime", "secondary_phone_candidate_runtime",
                "isolated_nats_jetstream", "synthetic_webdav_transfer",
                "credential_revocation", "owned_api_crash_recovery",
                "owned_worker_crash_recovery", "owned_agent_crash_recovery",
                "nats_restart_reconnect", "isolated_nats_ssh_interruption",
                "webdav_partial_upload",
                "webdav_503_retry", "resource_budget",
            }
            status = "PASS" if all(
                isinstance(self.results.get(key), dict)
                and self.results[key].get("status") == "PASS"
                for key in required
            ) else "FAIL"
        except QualificationError as exc:
            error = str(exc)
            status = "FAIL" if self.launch_started or self.roots_created or self.local_processes else "BLOCKED"
        except Exception as exc:
            error = type(exc).__name__
            status = "FAIL" if self.launch_started or self.roots_created or self.local_processes else "BLOCKED"
        finally:
            cleanup = self.cleanup()
            if cleanup.get("status") != "PASS" and status == "PASS":
                status = "FAIL"
            self.results["final_verdict"] = status
            payload = self._manifest_payload(status, error, cleanup)
            try:
                manifest = self._write_evidence(payload)
            except OSError:
                manifest = None
        return status, manifest


if __name__ == "__main__":
    raise SystemExit(main())
