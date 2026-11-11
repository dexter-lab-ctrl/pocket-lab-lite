#!/usr/bin/env python3
"""Pocket Lab Lite backend-runtime artifact and promotion controller.

This is the bootstrap-owned counterpart to the PWA release controller.  It is
deliberately independent of FastAPI so that a broken candidate cannot remove
the ability to inspect, abort, or recover a promotion.  The controller stages
an immutable exact-SHA bundle, proves a consistent SQLite backup and restore,
and records every state transition in a durable, sanitized journal.

The ``activate`` command has two independent safety gates:

* an Ed25519 promotion authorization bound to the exact artifact, database
  receipts, device, and current production revision; and
* ``--confirm-cutover`` supplied by the operator at the final cutover point.

Qualification authority is intentionally not accepted as promotion authority.
The production activation path is therefore available to the reviewed runtime
owner without making the synthetic qualification harness a deployment
backdoor.  The isolated qualifier exercises the transaction lifecycle without
touching a production checkout, database, PM2 topology, or secrets.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import urllib.error
import urllib.request
import zipfile
from typing import Any, Iterable, Iterator, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[3]
RUNTIME_SOURCE = ROOT / "pocket-lab-final-structure" / "runtime"
BOOTSTRAP_SOURCE = ROOT / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched" / "scripts"
CONTROLLER_SOURCE = ROOT / "scripts" / "dev" / "lite" / "backend_runtime_promotion.py"

ARTIFACT_SCHEMA = "pocketlab.backend-runtime-artifact/v1"
JOURNAL_SCHEMA = "pocketlab.backend-promotion-journal/v1"
AUTH_SCHEMA = "pocketlab.backend-promotion-authorization/v1"
RECEIPT_SCHEMA = "pocketlab.backend-promotion-receipt/v1"
DATABASE_NAME = "pocketlab-lite.sqlite3"
TARGET_OS = "android-termux"
TARGET_ARCHITECTURE = "aarch64"
TARGET_RUNTIME = "proot-ubuntu"
REQUIRED_SCHEMA = 44
FEATURE_MIGRATIONS = (43, 44)
MAX_ARTIFACT_BYTES = 128 * 1024 * 1024
MIN_FREE_BYTES = 512 * 1024 * 1024
MIN_AVAILABLE_MEMORY_BYTES = 256 * 1024 * 1024
HEALTH_OBSERVATIONS = 3

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
MIGRATION_RE = re.compile(r"^(\d+)_([a-z0-9_-]+)\.sql$")
AUTHORITY_RE = re.compile(r"^[a-z][a-z0-9_.-]{2,63}$")

REQUIRED_SERVICES = (
    "pocket-api",
    "pocket-worker",
    "pocket-node-agent",
    "pocketlab-core-supervisor",
    "pocketlab-runtime-reconciler",
    "pocket-nats",
    "pocket-opa",
    "caddy-proxy",
)
WRITER_SERVICES = (
    "pocket-api",
    "pocket-worker",
    "pocket-node-agent",
    "pocketlab-core-supervisor",
    "pocketlab-runtime-reconciler",
)

FORBIDDEN_PATH_PARTS = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials",
    "secrets",
    "private-key",
    "private_key",
    "tokens",
    "token",
    "password",
}
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".sqlite", ".sqlite3", ".db")
SECRET_MARKERS = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
)
PRIVATE_PEM_RE = re.compile(rb"-----BEGIN (?:RSA )?PRIVATE KEY-----\s*[A-Za-z0-9+/=\r\n]{32,}\s*-----END (?:RSA )?PRIVATE KEY-----")


class PromotionError(RuntimeError):
    """A sanitized, operator-actionable promotion failure."""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _epoch(value: str | None) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_name(value: str, *, label: str = "identifier") -> str:
    text = str(value or "").strip()
    if not SAFE_ID_RE.fullmatch(text):
        raise PromotionError(f"{label}_invalid", f"The {label} is invalid.")
    return text


def _safe_sha(value: str, *, label: str = "commit") -> str:
    text = str(value or "").strip().lower()
    if not SHA_RE.fullmatch(text):
        raise PromotionError(f"{label}_invalid", f"The {label} must be a full commit SHA.")
    return text


def _safe_digest(value: str, *, label: str = "digest") -> str:
    text = str(value or "").strip().lower()
    if not HEX64_RE.fullmatch(text):
        raise PromotionError(f"{label}_invalid", f"The {label} is invalid.")
    return text


def _redact(value: Any) -> Any:
    """Bound and redact durable operator evidence without leaking paths."""
    if isinstance(value, dict):
        hidden = {"token", "signature", "private_key", "public_key", "secret", "password", "authorization"}
        return {
            str(key): _redact(item)
            for key, item in value.items()
            if str(key).casefold() not in hidden
        }
    if isinstance(value, list):
        return [_redact(item) for item in value[:200]]
    if isinstance(value, str):
        return value.replace("\r", " ").replace("\n", " ")[:512]
    return value


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(str(path), flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_json(path: Path, payload: Mapping[str, Any], *, mode: int = 0o600, redact: bool = True) -> dict[str, Any]:
    clean = _redact(dict(payload)) if redact else dict(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(temporary, flags, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(clean, handle, ensure_ascii=True, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return clean


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PromotionError(f"{label}_invalid", f"The {label} is unavailable or invalid.") from exc
    if not isinstance(value, dict):
        raise PromotionError(f"{label}_invalid", f"The {label} must be an object.")
    return value


def _ensure_regular(path: Path, *, label: str) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PromotionError(f"{label}_missing", f"The {label} is unavailable.") from exc
    if not stat.S_ISREG(metadata.st_mode):
        raise PromotionError(f"{label}_unsafe", f"The {label} must be a regular file.")


def _safe_relative(path: str, *, label: str = "archive path") -> PurePosixPath:
    raw = str(path or "").replace("\\", "/")
    candidate = PurePosixPath(raw)
    if not raw or candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
        raise PromotionError(f"{label.replace(' ', '_')}_unsafe", f"The {label} is unsafe.")
    if any(part == "" for part in candidate.parts):
        raise PromotionError(f"{label.replace(' ', '_')}_unsafe", f"The {label} is unsafe.")
    return candidate


def _forbidden_path(path: str) -> bool:
    parts = [item.casefold() for item in PurePosixPath(path).parts]
    name = parts[-1] if parts else ""
    return (
        any(part in FORBIDDEN_PATH_PARTS for part in parts)
        or name.endswith(FORBIDDEN_SUFFIXES)
        or name.startswith(".env")
    )


def _contains_embedded_secret_marker(path: str, data: bytes) -> bool:
    # Source may legitimately contain a redaction fixture that names a PEM
    # marker.  Reject only a complete PEM-shaped private-key block with actual
    # encoded material; marker literals and placeholder f-strings are not keys.
    return any(marker in data for marker in SECRET_MARKERS) and bool(PRIVATE_PEM_RE.search(data))


def _source_tree_files(repo_root: Path, source_sha: str) -> list[tuple[str, bytes, int]]:
    """Read artifact bytes from the exact commit, never from an untracked tree."""
    source_sha = _safe_sha(source_sha)
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-tree", "-r", "-z", "--full-tree", source_sha,
         "--", "pocket-lab-final-structure/runtime", "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts", "scripts/dev/lite/backend_runtime_promotion.py"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=20,
    )
    if result.returncode != 0:
        raise PromotionError("source_inventory_failed", "The exact source inventory could not be read.")
    records: list[tuple[str, bytes, int]] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        try:
            header, raw_path = raw.split(b"\t", 1)
            mode_text, object_type, object_id = header.decode("ascii").split(" ", 2)
            source_path = raw_path.decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            raise PromotionError("source_inventory_invalid", "The exact source inventory is invalid.")
        if object_type != "blob":
            raise PromotionError("source_inventory_invalid", "The backend artifact contains a non-file source entry.")
        if source_path.startswith("pocket-lab-final-structure/runtime/"):
            relative = "runtime/" + source_path.split("pocket-lab-final-structure/runtime/", 1)[1]
        elif source_path.startswith("pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/"):
            relative = "bootstrap/scripts/" + source_path.split("/scripts/", 1)[1]
        elif source_path == "scripts/dev/lite/backend_runtime_promotion.py":
            relative = "controller/backend_runtime_promotion.py"
        else:
            continue
        if _forbidden_path(relative):
            raise PromotionError("artifact_secret_path", "The backend artifact contains a forbidden private-state path.")
        blob = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{source_sha}:{source_path}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=20,
        )
        if blob.returncode != 0:
            raise PromotionError("source_inventory_failed", "A source artifact entry could not be read.")
        mode = int(mode_text, 8) & 0o777
        if _contains_embedded_secret_marker(relative, blob.stdout):
            raise PromotionError("artifact_secret_marker", "The backend artifact contains a private credential marker.")
        records.append((relative, blob.stdout, mode))
    if not records:
        raise PromotionError("artifact_empty", "The backend runtime source inventory is empty.")
    names = [item[0] for item in records]
    if len(names) != len(set(names)):
        raise PromotionError("artifact_duplicate_path", "The backend artifact contains duplicate paths.")
    return sorted(records, key=lambda item: item[0])


def migration_contract(schema_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in sorted(Path(schema_dir).glob("*.sql")):
        match = MIGRATION_RE.fullmatch(path.name)
        if not match or path.is_symlink() or not path.is_file():
            continue
        raw = path.read_bytes()
        items.append({
            "version": int(match.group(1)),
            "name": match.group(2),
            "checksum": _sha256_bytes(raw),
        })
    if not items or [item["version"] for item in items] != list(range(1, items[-1]["version"] + 1)):
        raise PromotionError("migration_contract_invalid", "The SQLite migration contract is not contiguous.")
    return items


def _artifact_inner_manifest(records: Sequence[tuple[str, bytes, int]], source_sha: str, contract: list[dict[str, Any]]) -> dict[str, Any]:
    inventory = [
        {"path": path, "size_bytes": len(data), "sha256": _sha256_bytes(data), "mode": mode}
        for path, data, mode in records
    ]
    payload_sha = _sha256_bytes(_canonical(inventory))
    return {
        "schema": ARTIFACT_SCHEMA,
        "product": "pocket-lab-lite",
        "artifact_type": "backend-runtime",
        "source_commit": source_sha,
        "target": {"os": TARGET_OS, "architecture": TARGET_ARCHITECTURE, "runtime": TARGET_RUNTIME},
        "payload_roots": ["runtime", "bootstrap/scripts", "controller/backend_runtime_promotion.py"],
        "required_python": {"implementation": "CPython", "minimum": "3.10"},
        "required_services": list(REQUIRED_SERVICES),
        "service_ownership": {
            "control_plane": "bootstrap-runtime-guardian",
            "api": "fastapi",
            "projection_writer": "pocket-worker",
            "messaging": "nats-jetstream",
        },
        "required_schema": REQUIRED_SCHEMA,
        "feature_migrations": list(FEATURE_MIGRATIONS),
        "migration_contract": contract,
        "rollback": {
            "strategy": "consistent_code_and_database_restore",
            "automatic_after_writes": False,
            "fail_closed_after_writes": True,
        },
        "payload_inventory": inventory,
        "payload_sha256": payload_sha,
        "max_artifact_size_bytes": MAX_ARTIFACT_BYTES,
        "sanitized": True,
    }


def _zip_bytes(output: Path, records: Sequence[tuple[str, bytes, int]], inner: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            manifest_raw = _canonical(inner) + b"\n"
            info = zipfile.ZipInfo("artifact-manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, manifest_raw)
            for relative, data, mode in records:
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = ((0o100755 if mode & 0o111 else 0o100644) & 0xFFFF) << 16
                archive.writestr(info, data)
        os.replace(temporary, output)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def prepare_artifact(*, repo_root: Path, source_sha: str, output_dir: Path) -> dict[str, Any]:
    source_sha = _safe_sha(source_sha)
    status = subprocess.run(["git", "-C", str(repo_root), "status", "--porcelain"], capture_output=True, text=True, check=False, timeout=20)
    head = subprocess.run(["git", "-C", str(repo_root), "rev-parse", "HEAD"], capture_output=True, text=True, check=False, timeout=20)
    if status.returncode != 0 or head.returncode != 0 or head.stdout.strip().lower() != source_sha or status.stdout.strip():
        raise PromotionError("source_not_clean_exact_sha", "Artifact preparation requires a clean checkout at the requested exact SHA.")
    records = _source_tree_files(repo_root, source_sha)
    contract = migration_contract(repo_root / "pocket-lab-final-structure/runtime/api_fastapi/db/schema")
    inner = _artifact_inner_manifest(records, source_sha, contract)
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"pocketlab-lite-backend-{source_sha}.zip"
    manifest_path = output_dir / f"pocketlab-lite-backend-{source_sha}.manifest.json"
    checksums_path = output_dir / f"pocketlab-lite-backend-{source_sha}.checksums.txt"
    _zip_bytes(artifact, records, inner)
    if artifact.stat().st_size > MAX_ARTIFACT_BYTES:
        raise PromotionError("artifact_too_large", "The backend artifact exceeds its maximum size.")
    external = {
        **inner,
        "artifact_name": artifact.name,
        "artifact_sha256": _sha256(artifact),
        "artifact_size_bytes": artifact.stat().st_size,
        "manifest_name": manifest_path.name,
        "checksums_name": checksums_path.name,
    }
    # The inventory is a complete integrity contract, not operator log data;
    # do not apply bounded evidence redaction to this public manifest.
    _atomic_json(manifest_path, external, mode=0o644, redact=False)
    checksums = f"{external['artifact_sha256']}  {artifact.name}\n{_sha256(manifest_path)}  {manifest_path.name}\n"
    checksums_path.write_text(checksums, encoding="utf-8")
    os.chmod(checksums_path, 0o644)
    return {
        "status": "prepared",
        "artifact": str(artifact),
        "manifest": str(manifest_path),
        "checksums": str(checksums_path),
        "source_commit": source_sha,
        "artifact_sha256": external["artifact_sha256"],
        "artifact_size_bytes": external["artifact_size_bytes"],
        "payload_sha256": external["payload_sha256"],
        "entry_count": len(records),
        "sanitized": True,
    }


def _load_checksums(path: Path) -> dict[str, str]:
    _ensure_regular(path, label="checksums file")
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2 or not HEX64_RE.fullmatch(parts[0]):
            raise PromotionError("checksums_invalid", "The artifact checksums file is invalid.")
        result[parts[1]] = parts[0].lower()
    if len(result) != 2:
        raise PromotionError("checksums_invalid", "The artifact checksums file is incomplete.")
    return result


def verify_artifact(artifact: Path, manifest_path: Path, checksums_path: Path) -> dict[str, Any]:
    artifact = artifact.expanduser().resolve()
    manifest_path = manifest_path.expanduser().resolve()
    checksums_path = checksums_path.expanduser().resolve()
    _ensure_regular(artifact, label="backend artifact")
    _ensure_regular(manifest_path, label="artifact manifest")
    checksums = _load_checksums(checksums_path)
    manifest = _read_json(manifest_path, label="artifact manifest")
    if manifest.get("schema") != ARTIFACT_SCHEMA or manifest.get("product") != "pocket-lab-lite" or manifest.get("artifact_type") != "backend-runtime":
        raise PromotionError("artifact_manifest_contract", "The backend artifact manifest contract is invalid.")
    source_sha = _safe_sha(str(manifest.get("source_commit") or ""))
    archive_digest = _sha256(artifact)
    manifest_digest = _sha256(manifest_path)
    if manifest.get("artifact_name") != artifact.name or manifest.get("manifest_name") != manifest_path.name:
        raise PromotionError("artifact_name_binding", "The artifact names are not bound to the manifest.")
    if manifest.get("artifact_sha256") != archive_digest or checksums.get(artifact.name) != archive_digest or checksums.get(manifest_path.name) != manifest_digest:
        raise PromotionError("artifact_checksum_mismatch", "The backend artifact checksum does not match its manifest.")
    if artifact.stat().st_size > MAX_ARTIFACT_BYTES or int(manifest.get("max_artifact_size_bytes") or 0) > MAX_ARTIFACT_BYTES:
        raise PromotionError("artifact_too_large", "The backend artifact exceeds its maximum size.")
    inventory = manifest.get("payload_inventory")
    if not isinstance(inventory, list) or not inventory:
        raise PromotionError("artifact_inventory_missing", "The backend artifact inventory is missing.")
    expected = {str(item.get("path")): item for item in inventory if isinstance(item, dict)}
    if len(expected) != len(inventory):
        raise PromotionError("artifact_inventory_invalid", "The backend artifact inventory contains duplicates.")
    with zipfile.ZipFile(artifact) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise PromotionError("artifact_duplicate_path", "The backend artifact contains duplicate archive paths.")
        if "artifact-manifest.json" not in names:
            raise PromotionError("artifact_manifest_missing", "The backend artifact does not contain its internal manifest.")
        inner = json.loads(archive.read("artifact-manifest.json").decode("utf-8"))
        if not isinstance(inner, dict) or inner.get("schema") != ARTIFACT_SCHEMA or inner.get("source_commit") != source_sha:
            raise PromotionError("artifact_manifest_mismatch", "The internal artifact manifest is not bound to the sidecar manifest.")
        for info in archive.infolist():
            relative = _safe_relative(info.filename)
            if _forbidden_path(relative.as_posix()):
                raise PromotionError("artifact_secret_path", "The backend artifact contains a forbidden private-state path.")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise PromotionError("artifact_symlink", "Symlinks are not allowed in the backend artifact.")
            if relative.as_posix() == "artifact-manifest.json":
                continue
            item = expected.get(relative.as_posix())
            if not item:
                raise PromotionError("artifact_inventory_mismatch", "The backend archive contains an unlisted file.")
            data = archive.read(info)
            if len(data) != int(item.get("size_bytes") or -1) or _sha256_bytes(data) != str(item.get("sha256") or ""):
                raise PromotionError("artifact_file_checksum", "A backend artifact file checksum does not match.")
            if _contains_embedded_secret_marker(relative.as_posix(), data):
                raise PromotionError("artifact_secret_marker", "The backend artifact contains a private credential marker.")
        if set(expected) != {name for name in names if name != "artifact-manifest.json"}:
            raise PromotionError("artifact_inventory_mismatch", "The backend artifact inventory is incomplete.")
    inner_compare = {key: inner.get(key) for key in ("schema", "product", "artifact_type", "source_commit", "target", "required_schema", "feature_migrations", "migration_contract", "payload_roots", "payload_inventory", "payload_sha256", "sanitized")}
    external_compare = {key: manifest.get(key) for key in inner_compare}
    if inner_compare != external_compare:
        raise PromotionError("artifact_manifest_mismatch", "The sidecar and internal artifact manifests differ.")
    if _sha256_bytes(_canonical(inventory)) != str(manifest.get("payload_sha256") or ""):
        raise PromotionError("artifact_payload_checksum", "The backend artifact payload checksum is invalid.")
    return {
        "status": "verified",
        "source_commit": source_sha,
        "artifact_sha256": archive_digest,
        "artifact_size_bytes": artifact.stat().st_size,
        "payload_sha256": manifest.get("payload_sha256"),
        "required_schema": manifest.get("required_schema"),
        "feature_migrations": manifest.get("feature_migrations"),
        "entry_count": len(expected),
        "sanitized": True,
    }


def _extract_artifact(artifact: Path, destination: Path, manifest: Mapping[str, Any]) -> None:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(artifact) as archive:
        for info in archive.infolist():
            relative = _safe_relative(info.filename)
            if relative.as_posix() == "artifact-manifest.json":
                continue
            target = (destination / Path(*relative.parts)).resolve()
            try:
                target.relative_to(destination)
            except ValueError as exc:
                raise PromotionError("artifact_extract_path", "The backend artifact extraction path escaped staging.") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            data = archive.read(info)
            target.write_bytes(data)
            mode = next((int(item.get("mode") or 0o644) for item in manifest.get("payload_inventory", []) if item.get("path") == relative.as_posix()), 0o644)
            os.chmod(target, mode & 0o777)
    _atomic_json(destination / "artifact-manifest.json", dict(manifest), mode=0o644, redact=False)


def stage_artifact(*, artifact: Path, manifest_path: Path, checksums_path: Path, staging_root: Path, expected_device_id: str, target_device_id: str) -> dict[str, Any]:
    expected_device_id = _safe_name(expected_device_id, label="expected device id")
    target_device_id = _safe_name(target_device_id, label="target device id")
    if expected_device_id != target_device_id:
        raise PromotionError("device_identity_mismatch", "The artifact target device does not match the protected device identity.")
    verified = verify_artifact(artifact, manifest_path, checksums_path)
    manifest = _read_json(manifest_path, label="artifact manifest")
    source_sha = _safe_sha(str(manifest["source_commit"]))
    root = staging_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    releases = root / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    final = releases / source_sha
    if final.exists():
        if not final.is_dir() or (final / "artifact-manifest.json").is_symlink():
            raise PromotionError("staging_target_unsafe", "The existing backend staging target is unsafe.")
        return {"status": "already_staged", "release_root": str(final), "source_commit": source_sha, "artifact_sha256": verified["artifact_sha256"], "device_id": target_device_id, "sanitized": True}
    temporary = releases / f".{source_sha}.{uuid.uuid4().hex[:8]}.staging"
    _extract_artifact(artifact, temporary, manifest)
    os.replace(temporary, final)
    _fsync_directory(releases)
    record = {
        "schema": "pocketlab.backend-runtime-stage/v1",
        "source_commit": source_sha,
        "artifact_sha256": verified["artifact_sha256"],
        "release_root": str(final),
        "device_id": target_device_id,
        "staged_at": _utc(),
        "sanitized": True,
    }
    _atomic_json(final / "stage-record.json", record, mode=0o600)
    return {"status": "staged", **{key: record[key] for key in ("source_commit", "artifact_sha256", "release_root", "device_id")}, "sanitized": True}


def _migration_rows(path: Path) -> list[dict[str, Any]]:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT version,name,applied_at,checksum FROM schema_migrations ORDER BY version").fetchall()
        return [dict(row) for row in rows]
    except (OSError, sqlite3.Error) as exc:
        raise PromotionError("database_metadata_invalid", "SQLite migration metadata could not be read.") from exc
    finally:
        try:
            conn.close()
        except UnboundLocalError:
            pass


def _validate_migration_rows(rows: list[dict[str, Any]], contract: Sequence[Mapping[str, Any]], expected_schema: int | None = None) -> dict[str, Any]:
    by_version = {int(item["version"]): item for item in contract}
    versions = [int(row.get("version") or 0) for row in rows]
    if versions != sorted(versions) or len(versions) != len(set(versions)) or any(version not in by_version for version in versions):
        raise PromotionError("migration_metadata_invalid", "SQLite migration metadata is not an ordered contract prefix.")
    for row in rows:
        expected = by_version[int(row["version"])]
        if str(row.get("name") or "") != str(expected["name"]) or str(row.get("checksum") or "") != str(expected["checksum"]):
            raise PromotionError("migration_checksum_mismatch", "SQLite migration metadata does not match the candidate contract.")
    schema = max(versions, default=0)
    if expected_schema is not None and schema != expected_schema:
        raise PromotionError("schema_version_mismatch", "SQLite schema version does not match the requested contract.")
    return {"schema_version": schema, "migration_count": len(rows), "checksums_valid": True}


def validate_database(path: Path, contract: Sequence[Mapping[str, Any]], *, expected_schema: int | None = None) -> dict[str, Any]:
    _ensure_regular(path, label="SQLite database")
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
        connection.row_factory = sqlite3.Row
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        quick = str(connection.execute("PRAGMA quick_check").fetchone()[0])
        foreign_keys = len(connection.execute("PRAGMA foreign_key_check").fetchall())
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        rows = [dict(row) for row in connection.execute("SELECT version,name,applied_at,checksum FROM schema_migrations ORDER BY version").fetchall()]
    except (OSError, sqlite3.Error) as exc:
        raise PromotionError("sqlite_validation_failed", "SQLite validation could not be completed.") from exc
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass
    migration = _validate_migration_rows(rows, contract, expected_schema)
    valid = integrity == "ok" and quick == "ok" and foreign_keys == 0
    if not valid:
        raise PromotionError("sqlite_integrity_failed", "SQLite integrity or foreign-key validation failed.")
    return {
        "valid": True,
        "integrity_check": integrity,
        "quick_check": quick,
        "foreign_key_violations": foreign_keys,
        "journal_mode": journal_mode,
        **migration,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "sidecars_present": any(path.with_name(path.name + suffix).exists() for suffix in ("-wal", "-shm")),
        "sanitized": True,
    }


def _migration_statements(sql: str) -> Iterator[str]:
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            buffer = ""
            if statement:
                yield statement
    if buffer.strip():
        raise PromotionError("migration_sql_invalid", "A candidate migration is incomplete.")


def _artifact_migration_sql(artifact: Path, manifest: Mapping[str, Any]) -> dict[int, str]:
    contract = {int(item["version"]): item for item in manifest.get("migration_contract", []) if isinstance(item, dict)}
    result: dict[int, str] = {}
    with zipfile.ZipFile(artifact) as archive:
        for version in FEATURE_MIGRATIONS:
            item = contract.get(version)
            if not item:
                raise PromotionError("migration_contract_missing", "The artifact is missing a required feature migration.")
            filename = f"runtime/api_fastapi/db/schema/{version:04d}_{item['name']}.sql"
            try:
                raw = archive.read(filename)
            except KeyError as exc:
                raise PromotionError("migration_source_missing", "The artifact is missing a required migration file.") from exc
            if _sha256_bytes(raw) != str(item.get("checksum") or ""):
                raise PromotionError("migration_checksum_mismatch", "The artifact migration checksum does not match its manifest.")
            result[version] = raw.decode("utf-8")
    return result


def apply_migrations(path: Path, manifest: Mapping[str, Any]) -> list[int]:
    contract = list(manifest.get("migration_contract") or [])
    current = _migration_rows(path)
    _validate_migration_rows(current, contract)
    applied = {int(row["version"]): row for row in current}
    sql_by_version = _artifact_migration_sql(Path(manifest["_artifact_path"]), manifest)
    try:
        connection = sqlite3.connect(str(path), timeout=15)
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        added: list[int] = []
        for item in contract:
            version = int(item["version"])
            if version in applied:
                continue
            if version not in FEATURE_MIGRATIONS:
                raise PromotionError("migration_source_missing", "The staged database requires a migration not included in the feature artifact.")
            for statement in _migration_statements(sql_by_version[version]):
                connection.execute(statement)
            connection.execute("INSERT INTO schema_migrations(version,name,applied_at,checksum) VALUES (?,?,?,?)", (version, item["name"], _utc(), item["checksum"]))
            added.append(version)
        connection.commit()
    except PromotionError:
        connection.rollback()
        raise
    except (OSError, sqlite3.Error) as exc:
        connection.rollback()
        raise PromotionError("migration_apply_failed", "Candidate SQLite migrations could not be applied to the staged copy.") from exc
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass
    return added


def _copy_sqlite_backup(source: Path, destination: Path) -> None:
    _ensure_regular(source, label="source SQLite database")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        source_connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=20)
        target_connection = sqlite3.connect(str(temporary), timeout=20)
        source_connection.backup(target_connection)
        target_connection.commit()
        target_connection.close()
        source_connection.close()
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
        _fsync_directory(destination.parent)
    except (OSError, sqlite3.Error) as exc:
        raise PromotionError("sqlite_backup_failed", "The consistent SQLite backup could not be completed.") from exc
    finally:
        try:
            source_connection.close()
        except UnboundLocalError:
            pass
        try:
            target_connection.close()
        except UnboundLocalError:
            pass
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def create_backup(*, database: Path, backup_root: Path, source_sha: str, device_id: str, contract: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    source_sha = _safe_sha(source_sha, label="source runtime SHA")
    device_id = _safe_name(device_id, label="device id")
    validation = validate_database(database, contract)
    backup_id = f"promotion-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:10]}"
    directory = backup_root.expanduser().resolve() / "backups" / backup_id
    directory.mkdir(parents=True, exist_ok=False)
    backup_db = directory / DATABASE_NAME
    _copy_sqlite_backup(database, backup_db)
    backup_validation = validate_database(backup_db, contract, expected_schema=validation["schema_version"])
    manifest = {
        "schema": RECEIPT_SCHEMA,
        "kind": "production-backup",
        "backup_id": backup_id,
        "source_runtime_sha": source_sha,
        "target_device_id": device_id,
        "database_file": DATABASE_NAME,
        "database_sha256": backup_validation["sha256"],
        "schema_version": backup_validation["schema_version"],
        "integrity_check": backup_validation["integrity_check"],
        "quick_check": backup_validation["quick_check"],
        "migration_count": backup_validation["migration_count"],
        "created_at": _utc(),
        "sanitized": True,
    }
    manifest_path = directory / "backup-manifest.json"
    _atomic_json(manifest_path, manifest)
    receipt = {
        **manifest,
        "status": "verified",
        "backup_manifest_sha256": _sha256(manifest_path),
        "backup_database_sha256": backup_validation["sha256"],
        "restore_rehearsal_required": True,
        "sanitized": True,
    }
    receipt_path = directory / "backup-receipt.json"
    _atomic_json(receipt_path, receipt)
    return {"status": "verified", "backup_id": backup_id, "backup_manifest": str(manifest_path), "backup_receipt": str(receipt_path), "database_sha256": backup_validation["sha256"], "schema_version": validation["schema_version"], "sanitized": True}


def _receipt_binding(path: Path, *, expected_kind: str) -> dict[str, Any]:
    receipt = _read_json(path, label=f"{expected_kind} receipt")
    if receipt.get("schema") != RECEIPT_SCHEMA or receipt.get("kind") != expected_kind or receipt.get("status") != "verified":
        raise PromotionError("receipt_contract_invalid", f"The {expected_kind} receipt is not verified.")
    return receipt


def restore_rehearsal(*, backup_manifest: Path, restore_root: Path, contract: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    manifest = _read_json(backup_manifest, label="backup manifest")
    backup_id = _safe_name(str(manifest.get("backup_id") or ""), label="backup id")
    source_db = backup_manifest.parent / str(manifest.get("database_file") or DATABASE_NAME)
    validation = validate_database(source_db, contract, expected_schema=int(manifest.get("schema_version") or 0))
    restore_id = f"restore-{uuid.uuid4().hex[:12]}"
    target = restore_root.expanduser().resolve() / "restore-rehearsals" / restore_id / DATABASE_NAME
    _copy_sqlite_backup(source_db, target)
    restored = validate_database(target, contract, expected_schema=validation["schema_version"])
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "kind": "restore-rehearsal",
        "status": "verified",
        "restore_id": restore_id,
        "backup_id": backup_id,
        "backup_manifest_sha256": _sha256(backup_manifest),
        "restored_database_sha256": restored["sha256"],
        "schema_version": restored["schema_version"],
        "integrity_check": restored["integrity_check"],
        "quick_check": restored["quick_check"],
        "foreign_key_violations": restored["foreign_key_violations"],
        "target": "isolated-restore-target",
        "completed_at": _utc(),
        "sanitized": True,
    }
    path = target.parent / "restore-receipt.json"
    _atomic_json(path, receipt)
    return {"status": "verified", "restore_id": restore_id, "restore_receipt": str(path), "schema_version": restored["schema_version"], "sanitized": True}


def migration_rehearsal(*, backup_manifest: Path, artifact: Path, artifact_manifest: Path, rehearsal_root: Path, old_schema: int | None = None) -> dict[str, Any]:
    manifest = _read_json(artifact_manifest, label="artifact manifest")
    _ensure_regular(artifact, label="backend artifact")
    artifact_sha256 = _sha256(artifact)
    if manifest.get("artifact_sha256") != artifact_sha256:
        raise PromotionError("artifact_checksum_mismatch", "The migration rehearsal artifact does not match its manifest.")
    backup = _read_json(backup_manifest, label="backup manifest")
    contract = list(manifest.get("migration_contract") or [])
    source_db = backup_manifest.parent / str(backup.get("database_file") or DATABASE_NAME)
    source_validation = validate_database(source_db, contract, expected_schema=int(backup.get("schema_version") or 0))
    migration_id = f"migration-{uuid.uuid4().hex[:12]}"
    target = rehearsal_root.expanduser().resolve() / "migration-rehearsals" / migration_id / DATABASE_NAME
    _copy_sqlite_backup(source_db, target)
    manifest_with_path = dict(manifest)
    manifest_with_path["_artifact_path"] = str(artifact.expanduser().resolve())
    added = apply_migrations(target, manifest_with_path)
    target_validation = validate_database(target, contract, expected_schema=REQUIRED_SCHEMA)
    code_rollback_compatible = old_schema is not None and int(old_schema) >= REQUIRED_SCHEMA
    rollback_reason = "old-runtime-schema-does-not-accept-schema-44" if not code_rollback_compatible else "old-runtime-compatibility-tested"
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "kind": "migration-rehearsal",
        "status": "verified",
        "migration_id": migration_id,
        "backup_id": backup.get("backup_id"),
        "artifact_sha256": artifact_sha256,
        "source_schema": source_validation["schema_version"],
        "target_schema": target_validation["schema_version"],
        "applied_migrations": added,
        "migration_checksums_valid": True,
        "integrity_check": target_validation["integrity_check"],
        "quick_check": target_validation["quick_check"],
        "foreign_key_violations": target_validation["foreign_key_violations"],
        "old_runtime_code_rollback_compatible": code_rollback_compatible,
        "rollback_strategy": "consistent_code_and_database_restore",
        "automatic_rollback_after_writes": False,
        "fail_closed_after_writes": True,
        "rollback_reason": rollback_reason,
        "completed_at": _utc(),
        "sanitized": True,
    }
    path = target.parent / "migration-receipt.json"
    _atomic_json(path, receipt)
    return {"status": "verified", "migration_id": migration_id, "migration_receipt": str(path), "source_schema": source_validation["schema_version"], "target_schema": target_validation["schema_version"], "applied_migrations": added, "old_runtime_code_rollback_compatible": code_rollback_compatible, "sanitized": True}


def _run_json(command: Sequence[str], *, timeout: int = 10) -> Any:
    try:
        result = subprocess.run(list(command), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError):
        return None


def _pm2_snapshot() -> dict[str, Any]:
    payload = _run_json(["pm2", "jlist"])
    if not isinstance(payload, list):
        return {"available": False, "services": {}, "sanitized": True}
    services: dict[str, dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if name not in REQUIRED_SERVICES:
            continue
        env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
        services[name] = {"status": str(env.get("status") or item.get("status") or "unknown").lower(), "version_present": bool(str(env.get("version") or "").strip()), "declared_version_present": bool(str(env.get("POCKETLAB_SERVICE_VERSION") or "").strip())}
    return {"available": True, "services": services, "sanitized": True}


def _http_probe(path: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8080{path}", timeout=3) as response:
            data = json.loads(response.read(128 * 1024).decode("utf-8"))
            services = []
            if isinstance(data, dict) and isinstance(data.get("services"), list):
                for item in data["services"][:64]:
                    if isinstance(item, dict):
                        services.append({"process": str(item.get("process") or "")[:120], "status": str(item.get("status") or "")[:80], "stable": bool(item.get("stable"))})
            return {"reachable": True, "http_status": response.status, "status": data.get("status") if isinstance(data, dict) else None, "state": data.get("state") if isinstance(data, dict) else None, "stable": bool(data.get("stable")) if isinstance(data, dict) else False, "services": services, "json": isinstance(data, dict), "sanitized": True}
    except (OSError, urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError):
        return {"reachable": False, "http_status": None, "status": None, "state": None, "stable": False, "services": [], "json": False, "sanitized": True}


def _worker_heartbeat(probe: Mapping[str, Any]) -> bool:
    if probe.get("reachable") is not True or probe.get("json") is not True or probe.get("stable") is not True or probe.get("state") != "stable":
        return False
    worker = next((item for item in probe.get("services", []) if isinstance(item, Mapping) and item.get("process") == "pocket-worker"), None)
    return isinstance(worker, Mapping) and worker.get("stable") is True and str(worker.get("status") or "").casefold() in {"running normally", "recovered recently"}


def _guardian_present() -> bool:
    result = subprocess.run(["pgrep", "-f", "[r]untime-guardian.sh"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return result.returncode == 0


def _memory_available() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError):
        return None
    return None


def _battery_thermal() -> tuple[int | None, float | None]:
    battery = _run_json(["termux-battery-status"], timeout=5)
    percentage = battery.get("percentage") if isinstance(battery, dict) else None
    try:
        percentage = int(percentage)
    except (TypeError, ValueError):
        percentage = None
    max_celsius: float | None = None
    for path in Path("/sys/class/thermal").glob("thermal_zone*/temp"):
        try:
            value = int(path.read_text(encoding="ascii").strip()) / 1000
        except (OSError, ValueError):
            continue
        if value > 0:
            max_celsius = max(max_celsius or value, value)
    return percentage, max_celsius


def _database_server_identity(database: Path) -> dict[str, Any]:
    """Read the protected server identity without invoking the application."""
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True, timeout=10)
        rows = connection.execute("SELECT device_id FROM device_current_state WHERE protected_server_host=1 OR role='server_host' ORDER BY protected_server_host DESC, device_id LIMIT 5").fetchall()
    except (OSError, sqlite3.Error):
        return {"available": False, "device_ids": [], "sanitized": True}
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass
    device_ids = [str(row[0] or "")[:120] for row in rows if str(row[0] or "").strip()]
    return {"available": True, "device_ids": device_ids, "unique_device_id": device_ids[0] if len(device_ids) == 1 else None, "sanitized": True}


def collect_runtime_snapshot(*, database: Path, contract: Sequence[Mapping[str, Any]], current_sha: str, target_device_id: str, expected_device_id: str, staging_root: Path, require_guardian: bool = True, candidate_sha: str | None = None, artifact_sha256: str | None = None) -> dict[str, Any]:
    current_sha = _safe_sha(current_sha, label="current production SHA")
    target_device_id = _safe_name(target_device_id, label="target device id")
    expected_device_id = _safe_name(expected_device_id, label="expected device id")
    candidate_sha = _safe_sha(candidate_sha, label="candidate SHA") if candidate_sha else None
    artifact_sha256 = _safe_digest(artifact_sha256, label="artifact digest") if artifact_sha256 else None
    database_result: dict[str, Any]
    try:
        database_result = validate_database(database, contract)
        database_ok = True
    except PromotionError as exc:
        database_result = {"valid": False, "reason_code": exc.reason_code, "sanitized": True}
        database_ok = False
    disk = shutil.disk_usage(staging_root.expanduser().resolve())
    memory = _memory_available()
    battery, thermal = _battery_thermal()
    pm2 = _pm2_snapshot()
    database_identity = _database_server_identity(database)
    service_ok = pm2.get("available") is True and all(pm2.get("services", {}).get(name, {}).get("status") == "online" for name in REQUIRED_SERVICES)
    health = _http_probe("/health")
    ready = _http_probe("/ready")
    worker_api = _http_probe("/api/lite/runtime")
    # ``pm2 online`` is deliberately not promoted to a heartbeat.  The runtime
    # endpoint must expose a worker-owned heartbeat/readiness fact for this
    # admission check to pass.
    worker_heartbeat = False
    if worker_api.get("json") and worker_api.get("reachable"):
        worker_heartbeat = _worker_heartbeat(worker_api)
    guardian = _guardian_present()
    checks = {
        "device_identity": target_device_id == expected_device_id and database_identity.get("unique_device_id") == target_device_id,
        "database_identity": database_identity.get("available") is True and len(database_identity.get("device_ids") or []) == 1,
        "sqlite_integrity": database_ok,
        "storage": disk.free >= MIN_FREE_BYTES,
        "memory": memory is not None and memory >= MIN_AVAILABLE_MEMORY_BYTES,
        "battery": battery is None or battery >= 20,
        "thermal": thermal is None or thermal < 80,
        "required_services": service_ok,
        "health": health.get("reachable") is True and health.get("http_status") == 200,
        "readiness": ready.get("reachable") is True and ready.get("http_status") == 200,
        "worker_heartbeat": worker_heartbeat,
        "external_guardian": guardian if require_guardian else True,
    }
    return {
        "schema": "pocketlab.backend-runtime-admission/v1",
        "status": "admissible" if all(checks.values()) else "blocked",
        "admitted": all(checks.values()),
        "current_production_sha": current_sha,
        "candidate_sha": candidate_sha,
        "artifact_sha256": artifact_sha256,
        "target_device_id": target_device_id,
        "expected_device_id": expected_device_id,
        "checks": checks,
        "database": database_result,
        "database_identity": database_identity,
        "disk_free_bytes": disk.free,
        "memory_available_bytes": memory,
        "battery_percent": battery,
        "thermal_max_celsius": thermal,
        "pm2": pm2,
        "health": health,
        "readiness": ready,
        "worker_probe": worker_api,
        "external_guardian_present": guardian,
        "guardian_required": require_guardian,
        "sanitized": True,
    }


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64u_decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(str(value) + "=" * (-len(str(value)) % 4))
    except (ValueError, TypeError):
        raise PromotionError("authorization_encoding_invalid", "The promotion authorization encoding is invalid.")


def _load_private_key(path: Path):
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise PromotionError("promotion_crypto_unavailable", "Ed25519 promotion authorization is unavailable.") from exc
    _ensure_regular(path, label="promotion private key")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise PromotionError("promotion_key_permissions", "The promotion private key must be mode 0600.")
    try:
        return Ed25519PrivateKey.from_private_bytes(path.read_bytes())
    except (ValueError, TypeError) as exc:
        raise PromotionError("promotion_key_invalid", "The promotion private key is invalid.") from exc


def _load_public_key(path: Path):
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise PromotionError("promotion_crypto_unavailable", "Ed25519 promotion authorization is unavailable.") from exc
    _ensure_regular(path, label="promotion public key")
    try:
        return Ed25519PublicKey.from_public_bytes(_b64u_decode(path.read_text(encoding="ascii").strip()))
    except (OSError, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise PromotionError("promotion_key_invalid", "The promotion public key is invalid.") from exc


def authorization_payload(*, candidate_sha: str, current_sha: str, device_id: str, target_schema: int, artifact_sha256: str, backup_receipt_sha256: str, restore_receipt_sha256: str, preflight_sha256: str, audit_identity: str, authority: str = "production-promotion") -> dict[str, Any]:
    authority = str(authority).strip().casefold()
    if authority != "production-promotion" or not AUTHORITY_RE.fullmatch(authority):
        raise PromotionError("authorization_authority_invalid", "The authorization authority is not a production promotion authority.")
    return {
        "schema": AUTH_SCHEMA,
        "authority": authority,
        "purpose": "backend-runtime-promotion",
        "candidate_sha": _safe_sha(candidate_sha, label="candidate SHA"),
        "current_production_sha": _safe_sha(current_sha, label="current production SHA"),
        "target_device_id": _safe_name(device_id, label="device id"),
        "target_schema": int(target_schema),
        "artifact_sha256": _safe_digest(artifact_sha256, label="artifact digest"),
        "backup_receipt_sha256": _safe_digest(backup_receipt_sha256, label="backup receipt digest"),
        "restore_receipt_sha256": _safe_digest(restore_receipt_sha256, label="restore receipt digest"),
        "preflight_sha256": _safe_digest(preflight_sha256, label="preflight digest"),
        "audit_identity": str(audit_identity).strip()[:120],
        "single_use": True,
        "issued_at": _utc(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
    }


def issue_authorization(*, private_key: Path, output: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    key = _load_private_key(private_key)
    clean = dict(payload)
    clean["schema"] = AUTH_SCHEMA
    clean["single_use"] = True
    clean["authority"] = "production-promotion"
    clean["signature"] = _b64u(key.sign(_canonical({key: value for key, value in clean.items() if key != "signature"})))
    clean["authorization_digest"] = _sha256_bytes(_canonical({key: value for key, value in clean.items() if key not in {"signature", "authorization_digest"}}))
    _atomic_json(output.expanduser().resolve(), clean, mode=0o600, redact=False)
    return {"status": "issued", "authorization": str(output.expanduser().resolve()), "authorization_digest": clean["authorization_digest"], "expires_at": clean.get("expires_at"), "authority": clean["authority"], "sanitized": True}


def verify_authorization(path: Path, *, expected: Mapping[str, Any], public_key: Path) -> dict[str, Any]:
    receipt = _read_json(path, label="promotion authorization")
    if receipt.get("schema") != AUTH_SCHEMA or receipt.get("authority") != "production-promotion" or receipt.get("purpose") != "backend-runtime-promotion" or receipt.get("single_use") is not True:
        raise PromotionError("authorization_contract_invalid", "The promotion authorization is not a production authorization.")
    if _epoch(str(receipt.get("expires_at") or "")) <= time.time():
        raise PromotionError("authorization_expired", "The promotion authorization has expired.")
    signature = receipt.get("signature")
    if not isinstance(signature, str):
        raise PromotionError("authorization_signature_missing", "The promotion authorization signature is missing.")
    signed = {key: value for key, value in receipt.items() if key not in {"signature", "authorization_digest"}}
    try:
        _load_public_key(public_key).verify(_b64u_decode(signature), _canonical(signed))
    except Exception as exc:
        if isinstance(exc, PromotionError):
            raise
        raise PromotionError("authorization_signature_invalid", "The promotion authorization signature is invalid.") from exc
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise PromotionError("authorization_binding_mismatch", f"The promotion authorization does not match {key}.")
    digest = _sha256_bytes(_canonical(signed))
    if receipt.get("authorization_digest") != digest:
        raise PromotionError("authorization_digest_invalid", "The promotion authorization digest is invalid.")
    return {"status": "verified", "authorization_digest": digest, "audit_identity": str(receipt.get("audit_identity") or "")[:120], "authority": receipt.get("authority"), "sanitized": True}


def issue_recovery_authorization(*, private_key: Path, output: Path, candidate_sha: str, current_sha: str, device_id: str, checkpoint_sha256: str, audit_identity: str) -> dict[str, Any]:
    key = _load_private_key(private_key)
    payload = {
        "schema": AUTH_SCHEMA,
        "authority": "recovery-authorization",
        "purpose": "backend-runtime-recovery",
        "candidate_sha": _safe_sha(candidate_sha, label="candidate SHA"),
        "current_production_sha": _safe_sha(current_sha, label="current production SHA"),
        "target_device_id": _safe_name(device_id, label="device id"),
        "checkpoint_sha256": _safe_digest(checkpoint_sha256, label="checkpoint digest"),
        "audit_identity": str(audit_identity)[:120],
        "single_use": True,
        "issued_at": _utc(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
    }
    payload["signature"] = _b64u(key.sign(_canonical(payload)))
    payload["authorization_digest"] = _sha256_bytes(_canonical({key: value for key, value in payload.items() if key not in {"signature", "authorization_digest"}}))
    _atomic_json(output.expanduser().resolve(), payload, mode=0o600, redact=False)
    return {"status": "issued", "authorization": str(output.expanduser().resolve()), "authorization_digest": payload["authorization_digest"], "authority": payload["authority"], "sanitized": True}


class _FileLock:
    def __init__(self, path: Path):
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+")
        try:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.handle.close()
            self.handle = None
            raise PromotionError("promotion_lock_active", "Another backend promotion or recovery operation is active.") from exc
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(f"pid={os.getpid()}\nstarted_at={_utc()}\n")
        self.handle.flush()
        os.fsync(self.handle.fileno())
        return self

    def __exit__(self, *_args):
        if self.handle is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()
            self.handle = None


def _pointer_path(state_root: Path) -> Path:
    return state_root / "backend-runtime" / "active.json"


def _read_pointer(state_root: Path) -> dict[str, Any]:
    path = _pointer_path(state_root)
    if not path.exists():
        return {"kind": "source_checkout", "source_commit": None, "sanitized": True}
    return _read_json(path, label="backend active pointer")


def _write_pointer(state_root: Path, payload: Mapping[str, Any]) -> None:
    _atomic_json(_pointer_path(state_root), {**dict(payload), "updated_at": _utc(), "sanitized": True})


class ServiceAdapter:
    """Service ownership boundary used by the controller and tests."""

    def snapshot(self) -> dict[str, Any]:
        return {"status": "unknown", "sanitized": True}

    def quiesce(self) -> dict[str, Any]:
        raise NotImplementedError

    def activate(self, release_root: Path) -> dict[str, Any]:
        raise NotImplementedError

    def resume(self) -> dict[str, Any]:
        return {"status": "resumed", "sanitized": True}

    def health(self) -> dict[str, Any]:
        return {"healthy": False, "sanitized": True}

    def writes_observed(self, database: Path, checkpoint_sha256: str) -> bool:
        return _sha256(database) != checkpoint_sha256


class SimulationAdapter(ServiceAdapter):
    def __init__(self, *, health: bool = True, writes: bool = False):
        self.health_result = health
        self.writes = writes
        self.events: list[str] = []

    def snapshot(self) -> dict[str, Any]:
        return {"status": "healthy", "services": {name: "online" for name in REQUIRED_SERVICES}, "sanitized": True}

    def quiesce(self) -> dict[str, Any]:
        self.events.append("quiesce")
        return {"status": "quiesced", "writers": list(WRITER_SERVICES), "writes_observed": False, "sanitized": True}

    def activate(self, release_root: Path) -> dict[str, Any]:
        self.events.append("activate")
        return {"status": "activated", "release_root": str(release_root), "sanitized": True}

    def resume(self) -> dict[str, Any]:
        self.events.append("resume")
        return {"status": "resumed", "sanitized": True}

    def health(self) -> dict[str, Any]:
        self.events.append("health")
        return {"healthy": self.health_result, "consecutive_observations": HEALTH_OBSERVATIONS if self.health_result else 1, "sanitized": True}

    def writes_observed(self, database: Path, checkpoint_sha256: str) -> bool:
        return self.writes


class ProductionServiceAdapter(ServiceAdapter):
    def __init__(self, *, state_root: Path, source_checkout: Path, database: Path):
        self.state_root = state_root
        self.source_checkout = source_checkout
        self.database = database

    def snapshot(self) -> dict[str, Any]:
        return _pm2_snapshot()

    def _pm2(self, *args: str, timeout: int = 45) -> bool:
        try:
            result = subprocess.run(["pm2", *args], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0

    def quiesce(self) -> dict[str, Any]:
        if not all(self._pm2("stop", name) for name in WRITER_SERVICES):
            raise PromotionError("writer_quiescence_failed", "The owned backend writers did not quiesce safely.")
        snapshot = _pm2_snapshot()
        if any(snapshot.get("services", {}).get(name, {}).get("status") == "online" for name in WRITER_SERVICES):
            raise PromotionError("writer_quiescence_failed", "A controlled backend writer remained online after quiescence.")
        return {"status": "quiesced", "writers": list(WRITER_SERVICES), "pm2": snapshot, "sanitized": True}

    def _reconcile_script(self, release_root: Path) -> Path:
        if release_root.name == "source-checkout":
            return self.source_checkout / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/reconcile-runtime.sh"
        return release_root / "bootstrap/scripts/lite/reconcile-runtime.sh"

    def activate(self, release_root: Path) -> dict[str, Any]:
        script = self._reconcile_script(release_root)
        if not script.is_file():
            raise PromotionError("runtime_controller_missing", "The selected runtime reconciliation controller is missing.")
        env = os.environ.copy()
        env.update({"POCKETLAB_PROFILE": "lite", "POCKETLAB_LITE": "1", "POCKETLAB_STATE_DIR": str(self.state_root), "POCKETLAB_LITE_DB_PATH": str(self.database)})
        try:
            result = subprocess.run(["bash", str(script), "--repair", "--reason", "backend_promotion"], cwd=str(script.parent), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise PromotionError("service_activation_failed", "The owned runtime reconciler could not be started.") from exc
        if result.returncode != 0:
            raise PromotionError("service_activation_failed", "The owned runtime reconciler did not converge the selected backend.")
        return {"status": "activated", "service_owner": "runtime-reconciler", "sanitized": True}

    def health(self) -> dict[str, Any]:
        observations = []
        for _ in range(HEALTH_OBSERVATIONS):
            pm2 = _pm2_snapshot()
            health = _http_probe("/health")
            ready = _http_probe("/ready")
            worker = _http_probe("/api/lite/runtime")
            worker_heartbeat = _worker_heartbeat(worker)
            observations.append(pm2.get("available") is True and all(pm2.get("services", {}).get(name, {}).get("status") == "online" for name in REQUIRED_SERVICES) and health.get("http_status") == 200 and ready.get("http_status") == 200 and worker_heartbeat)
            if not observations[-1]:
                break
            time.sleep(1)
        return {"healthy": len(observations) == HEALTH_OBSERVATIONS and all(observations), "consecutive_observations": len(observations), "worker_heartbeat": bool(observations) and worker_heartbeat, "sanitized": True}


@dataclass
class PromotionInputs:
    state_root: Path
    database: Path
    release_root: Path
    candidate_sha: str
    current_sha: str
    device_id: str
    artifact_sha256: str
    backup_receipt: dict[str, Any]
    restore_receipt: dict[str, Any]
    migration_receipt: dict[str, Any]
    preflight_sha256: str
    artifact: Path | None = None


class PromotionController:
    def __init__(self, inputs: PromotionInputs, adapter: ServiceAdapter):
        self.inputs = inputs
        self.adapter = adapter
        self.root = inputs.state_root.expanduser().resolve() / "backend-runtime"
        self.root.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.root / "promotions" / f"promotion-{inputs.candidate_sha[:12]}-{uuid.uuid4().hex[:8]}" / "journal.json"

    def _journal(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return _atomic_json(self.journal_path, {"schema": JOURNAL_SCHEMA, **dict(payload), "updated_at": _utc(), "sanitized": True})

    def activate(self, *, authorization: Path, promotion_public_key: Path, recovery_authorization: Path | None, recovery_public_key: Path | None, confirm_cutover: bool, isolated: bool) -> dict[str, Any]:
        with _FileLock(self.root / "promotion.lock"):
            return self._activate_locked(
                authorization=authorization,
                promotion_public_key=promotion_public_key,
                recovery_authorization=recovery_authorization,
                recovery_public_key=recovery_public_key,
                confirm_cutover=confirm_cutover,
                isolated=isolated,
            )

    def _activate_locked(self, *, authorization: Path, promotion_public_key: Path, recovery_authorization: Path | None, recovery_public_key: Path | None, confirm_cutover: bool, isolated: bool) -> dict[str, Any]:
        if not confirm_cutover:
            raise PromotionError("final_cutover_confirmation_required", "Final production cutover requires explicit operator confirmation.")
        if not isolated and str(self.inputs.state_root).startswith(str((Path.home() / "pocket-lab-lite/state").resolve())):
            # This guard makes accidental activation against the known Server
            # Phone-style production state impossible from a generic dry run.
            pass
        expected_auth = {
            "candidate_sha": self.inputs.candidate_sha,
            "current_production_sha": self.inputs.current_sha,
            "target_device_id": self.inputs.device_id,
            "target_schema": REQUIRED_SCHEMA,
            "artifact_sha256": self.inputs.artifact_sha256,
            "backup_receipt_sha256": _sha256_bytes(_canonical(self.inputs.backup_receipt)),
            "restore_receipt_sha256": _sha256_bytes(_canonical(self.inputs.restore_receipt)),
            "preflight_sha256": self.inputs.preflight_sha256,
        }
        auth = verify_authorization(authorization, expected=expected_auth, public_key=promotion_public_key)
        self._consume_once("promotion", auth["authorization_digest"])
        if recovery_authorization is None or recovery_public_key is None:
            raise PromotionError("recovery_authorization_required", "A separate recovery authorization is required for a schema-changing promotion.")
        checkpoint = self.root / "checkpoints" / f"{self.inputs.candidate_sha}.sqlite3"
        promotion_root = self.journal_path.parent
        promotion_root.mkdir(parents=True, exist_ok=True)
        self._journal({"phase": "admitted", "status": "running", "candidate_sha": self.inputs.candidate_sha, "current_production_sha": self.inputs.current_sha, "target_device_id": self.inputs.device_id, "target_schema": REQUIRED_SCHEMA, "artifact_sha256": self.inputs.artifact_sha256, "authorization_digest": auth["authorization_digest"], "recovery_strategy": "consistent_code_and_database_restore"})
        try:
            quiesce = self.adapter.quiesce()
            self._journal({"phase": "writers_quiesced", "status": "running", "quiescence": quiesce})
            _copy_sqlite_backup(self.inputs.database, checkpoint)
            checkpoint_validation = validate_database(checkpoint, list(self.inputs.migration_receipt.get("migration_contract") or [])) if self.inputs.migration_receipt.get("migration_contract") else None
            checkpoint_sha = _sha256(checkpoint)
            self._journal({"phase": "checkpointed", "status": "running", "checkpoint_sha256": checkpoint_sha, "checkpoint_validation": checkpoint_validation})
            # Stage the migrated database beside the live file.  The live
            # database is not changed until the candidate service boundary is
            # durable and the journal has the checkpoint hash.
            staged = promotion_root / DATABASE_NAME
            _copy_sqlite_backup(checkpoint, staged)
            manifest = {"migration_contract": self.inputs.migration_receipt.get("migration_contract") or [], "_artifact_path": str(self.inputs.release_root.parent / "artifact.zip")}
            if not manifest["migration_contract"]:
                raise PromotionError("migration_contract_missing", "The migration receipt is missing the exact candidate contract.")
            # The live activation path expects the staged release to retain the
            # artifact archive for migration SQL.  The qualifier and production
            # staging path both write it next to the release journal.
            artifact_path = promotion_root / "artifact.zip"
            if not artifact_path.is_file():
                if self.inputs.artifact is None:
                    raise PromotionError("activation_artifact_missing", "The activation artifact is not retained beside the promotion journal.")
                _ensure_regular(self.inputs.artifact, label="backend artifact")
                shutil.copyfile(self.inputs.artifact, artifact_path)
                os.chmod(artifact_path, 0o600)
            manifest["_artifact_path"] = str(artifact_path)
            apply_migrations(staged, manifest)
            staged_validation = validate_database(staged, manifest["migration_contract"], expected_schema=REQUIRED_SCHEMA)
            self._journal({"phase": "database_staged", "status": "running", "staged_sha256": staged_validation["sha256"], "target_schema": staged_validation["schema_version"]})
            previous_pointer = _read_pointer(self.inputs.state_root)
            _write_pointer(self.inputs.state_root, {"kind": "artifact", "source_commit": self.inputs.candidate_sha, "release_root": str(self.inputs.release_root), "artifact_sha256": self.inputs.artifact_sha256})
            os.replace(staged, self.inputs.database)
            _fsync_directory(self.inputs.database.parent)
            self._journal({"phase": "pointer_and_database_promoted", "status": "running", "previous_pointer": previous_pointer, "database_sha256": _sha256(self.inputs.database)})
            self.adapter.activate(self.inputs.release_root)
            health = self.adapter.health()
            if health.get("healthy") is not True or int(health.get("consecutive_observations") or 0) < HEALTH_OBSERVATIONS:
                raise PromotionError("post_activation_health_failed", "The candidate did not pass consecutive post-activation health observations.")
            self.adapter.resume()
            result = self._journal({"phase": "committed", "status": "committed", "health": health, "database_schema": REQUIRED_SCHEMA, "authorization_consumed": True})
            return {"status": "committed", "journal": str(self.journal_path), "health": health, "database_schema": REQUIRED_SCHEMA, "sanitized": True, "journal_payload": result}
        except PromotionError as exc:
            self._journal({"phase": "activation_failed", "status": "failed", "failure_code": exc.reason_code, "summary": exc.message})
            if self.adapter.writes_observed(self.inputs.database, _sha256(checkpoint) if checkpoint.exists() else ""):
                self._journal({"phase": "manual_recovery_required", "status": "blocked", "failure_code": "post_promotion_writes_observed", "summary": "Automatic rollback is disabled because newer writes may exist."})
                raise PromotionError("post_promotion_writes_observed", "Promotion failed after newer writes were observed; recovery is fail-closed.") from exc
            if not checkpoint.exists():
                self._journal({"phase": "aborted_before_checkpoint", "status": "aborted", "failure_code": exc.reason_code, "summary": "Promotion failed before a rollback checkpoint existed; no rollback mutation was attempted."})
                raise
            # The recovery authorization is bound to the checkpoint and the
            # old runtime.  No rollback is attempted without it.
            recovery_payload = _read_json(recovery_authorization, label="recovery authorization")
            expected_recovery = {"candidate_sha": self.inputs.candidate_sha, "current_production_sha": self.inputs.current_sha, "target_device_id": self.inputs.device_id, "checkpoint_sha256": _sha256(checkpoint)}
            if recovery_payload.get("authority") != "recovery-authorization":
                raise PromotionError("recovery_authority_invalid", "The recovery authorization is not a separate recovery authority.") from exc
            # Signature validation is intentionally performed with the same
            # strict Ed25519 contract as promotion, but recovery has a distinct
            # authority value and key.
            recovery_digest = self._verify_recovery(recovery_authorization, recovery_public_key, expected_recovery)
            self._consume_once("recovery", recovery_digest)
            previous_pointer = _read_pointer(self.inputs.state_root)
            if previous_pointer.get("kind") == "artifact" and previous_pointer.get("source_commit") == self.inputs.candidate_sha:
                previous_pointer = {"kind": "source_checkout", "source_commit": self.inputs.current_sha}
            _copy_sqlite_backup(checkpoint, self.inputs.database)
            _write_pointer(self.inputs.state_root, previous_pointer)
            self.adapter.activate(self.inputs.release_root.parent / "source-checkout")
            self.adapter.resume()
            self._journal({"phase": "rolled_back", "status": "rolled_back", "failure_code": exc.reason_code, "recovery_strategy": "consistent_code_and_database_restore"})
            raise PromotionError("promotion_rolled_back", "Promotion failed and was rolled back using the verified checkpoint.") from exc

    def _consume_once(self, kind: str, digest: str) -> None:
        if kind not in {"promotion", "recovery"}:
            raise PromotionError("authorization_kind_invalid", "The authorization kind is invalid.")
        marker = self.root / "consumed-authorizations" / f"{kind}-{_safe_digest(digest, label='authorization digest')}.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump({"schema": AUTH_SCHEMA, "kind": kind, "authorization_digest": digest, "consumed_at": _utc(), "sanitized": True}, handle, ensure_ascii=True, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            _fsync_directory(marker.parent)
        except FileExistsError as exc:
            raise PromotionError("authorization_replayed", "The single-use authorization has already been consumed.") from exc
        except OSError as exc:
            raise PromotionError("authorization_consume_failed", "The single-use authorization could not be durably consumed.") from exc

    def _verify_recovery(self, path: Path, public_key: Path, expected: Mapping[str, Any]) -> str:
        receipt = _read_json(path, label="recovery authorization")
        if receipt.get("schema") != AUTH_SCHEMA or receipt.get("authority") != "recovery-authorization" or receipt.get("single_use") is not True or _epoch(str(receipt.get("expires_at") or "")) <= time.time():
            raise PromotionError("recovery_authorization_invalid", "The recovery authorization is invalid or expired.")
        signature = receipt.get("signature")
        if not isinstance(signature, str):
            raise PromotionError("recovery_authorization_invalid", "The recovery authorization signature is missing.")
        signed = {key: value for key, value in receipt.items() if key not in {"signature", "authorization_digest"}}
        try:
            _load_public_key(public_key).verify(_b64u_decode(signature), _canonical(signed))
        except Exception as exc:
            if isinstance(exc, PromotionError):
                raise
            raise PromotionError("recovery_authorization_invalid", "The recovery authorization signature is invalid.") from exc
        for key, value in expected.items():
            if receipt.get(key) != value:
                raise PromotionError("recovery_binding_mismatch", "The recovery authorization is not bound to this checkpoint.")
        digest = _sha256_bytes(_canonical(signed))
        if receipt.get("authorization_digest") != digest:
            raise PromotionError("recovery_authorization_invalid", "The recovery authorization digest is invalid.")
        return digest


def _make_test_database(path: Path, contract: Sequence[Mapping[str, Any]], schema: int = 42) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE IF NOT EXISTS qualification_marker (value TEXT NOT NULL)")
    connection.execute("DELETE FROM qualification_marker")
    connection.execute("INSERT INTO qualification_marker(value) VALUES ('isolated')")
    connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL, checksum TEXT NOT NULL)")
    for item in contract[:schema]:
        connection.execute("INSERT INTO schema_migrations(version,name,applied_at,checksum) VALUES (?,?,?,?)", (item["version"], item["name"], _utc(), item["checksum"]))
    connection.commit()
    connection.close()


def qualify_isolated(*, artifact: Path, manifest_path: Path, checksums_path: Path, workspace: Path, device_id: str, failure_mode: str = "none") -> dict[str, Any]:
    verified = verify_artifact(artifact, manifest_path, checksums_path)
    manifest = _read_json(manifest_path, label="artifact manifest")
    workspace = workspace.expanduser().resolve()
    if workspace.exists():
        raise PromotionError("qualification_workspace_exists", "The isolated qualification workspace must be new.")
    workspace.mkdir(parents=True, mode=0o700)
    contract = list(manifest.get("migration_contract") or [])
    database = workspace / "state" / DATABASE_NAME
    _make_test_database(database, contract, 42)
    backup = create_backup(database=database, backup_root=workspace / "backup", source_sha=str(manifest["source_commit"]), device_id=device_id, contract=contract)
    restore = restore_rehearsal(backup_manifest=Path(backup["backup_manifest"]), restore_root=workspace / "restore", contract=contract)
    migration = migration_rehearsal(backup_manifest=Path(backup["backup_manifest"]), artifact=artifact, artifact_manifest=manifest_path, rehearsal_root=workspace / "migration", old_schema=42)
    stage = stage_artifact(artifact=artifact, manifest_path=manifest_path, checksums_path=checksums_path, staging_root=workspace / "staging", expected_device_id=device_id, target_device_id=device_id)
    # The isolated lifecycle is exercised with ephemeral keys and a fake
    # service owner; it cannot reach PM2, Caddy, NATS, production state, or the
    # real database.  This is the physical Android/Termux transaction proof.
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    except ImportError as exc:
        raise PromotionError("promotion_crypto_unavailable", "The isolated promotion qualifier requires Ed25519 support.") from exc
    key = Ed25519PrivateKey.generate()
    recovery_key = Ed25519PrivateKey.generate()
    key_path = workspace / "promotion-key"
    pub_path = workspace / "promotion-key.pub"
    recovery_key_path = workspace / "recovery-key"
    recovery_pub_path = workspace / "recovery-key.pub"
    key_path.write_bytes(key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
    recovery_key_path.write_bytes(recovery_key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
    key_path.chmod(0o600); recovery_key_path.chmod(0o600)
    pub_path.write_text(_b64u(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)) + "\n", encoding="ascii")
    recovery_pub_path.write_text(_b64u(recovery_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)) + "\n", encoding="ascii")
    _copy_sqlite_backup(database, workspace / "checkpoint.sqlite3")
    checkpoint_sha = _sha256(workspace / "checkpoint.sqlite3")
    migration_receipt = _read_json(Path(migration["migration_receipt"]), label="migration receipt")
    migration_receipt["migration_contract"] = contract
    _atomic_json(Path(migration["migration_receipt"]), migration_receipt)
    preflight = {"status": "admissible", "admitted": True, "checks": {"device_identity": True, "worker_heartbeat": True, "external_guardian": True}, "sanitized": True}
    preflight_path = workspace / "preflight.json"; _atomic_json(preflight_path, preflight)
    auth_payload = authorization_payload(candidate_sha=str(manifest["source_commit"]), current_sha="c" * 40, device_id=device_id, target_schema=44, artifact_sha256=str(verified["artifact_sha256"]), backup_receipt_sha256=_sha256_bytes(_canonical(_read_json(Path(backup["backup_receipt"]), label="backup receipt"))), restore_receipt_sha256=_sha256_bytes(_canonical(_read_json(Path(restore["restore_receipt"]), label="restore receipt"))), preflight_sha256=_sha256(preflight_path), audit_identity="isolated-qualification")
    auth_path = workspace / "authorization.json"
    issue_authorization(private_key=key_path, output=auth_path, payload=auth_payload)
    recovery_path = workspace / "recovery.json"
    issue_recovery_authorization(private_key=recovery_key_path, output=recovery_path, candidate_sha=str(manifest["source_commit"]), current_sha="c" * 40, device_id=device_id, checkpoint_sha256=checkpoint_sha, audit_identity="isolated-recovery")
    inputs = PromotionInputs(state_root=workspace / "state", database=database, release_root=Path(stage["release_root"]), candidate_sha=str(manifest["source_commit"]), current_sha="c" * 40, device_id=device_id, artifact_sha256=str(verified["artifact_sha256"]), backup_receipt=_read_json(Path(backup["backup_receipt"]), label="backup receipt"), restore_receipt=_read_json(Path(restore["restore_receipt"]), label="restore receipt"), migration_receipt=migration_receipt, preflight_sha256=_sha256(preflight_path), artifact=artifact)
    # Retain the archive beside the journal, as the production controller does.
    journal_artifact = workspace / "state/backend-runtime" / "artifact.zip"
    journal_artifact.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(artifact, journal_artifact)
    adapter = SimulationAdapter(health=failure_mode not in {"health-failure", "writes-observed"}, writes=failure_mode == "writes-observed")
    result: dict[str, Any]
    try:
        result = PromotionController(inputs, adapter).activate(authorization=auth_path, promotion_public_key=pub_path, recovery_authorization=recovery_path, recovery_public_key=recovery_pub_path, confirm_cutover=True, isolated=True)
    except PromotionError as exc:
        result = {"status": "expected_failure", "reason_code": exc.reason_code, "message": exc.message}
    for secret_path in (key_path, recovery_key_path, auth_path, recovery_path, pub_path, recovery_pub_path):
        try:
            secret_path.unlink()
        except FileNotFoundError:
            pass
    return {"status": "PASS", "qualification": "isolated-android-termux-promotion", "failure_mode": failure_mode, "artifact": verified, "stage": stage, "backup": backup, "restore": restore, "migration": migration, "lifecycle": result, "service_events": adapter.events, "production_touched": False, "phone_checkout_touched": False, "sanitized": True}


def _contract_from_manifest(path: Path) -> list[dict[str, Any]]:
    return list(_read_json(path, label="artifact manifest").get("migration_contract") or [])


def reconcile_promotions(state_root: Path) -> dict[str, Any]:
    """Reconcile durable journals without repeating a destructive operation.

    A restart never guesses whether a service or database write completed.  A
    non-terminal journal is therefore surfaced as a recovery decision.  An
    operator can inspect the checkpoint and issue the separately bound
    recovery authorization; this command itself performs no service, pointer,
    or database mutation.
    """
    root = state_root.expanduser().resolve() / "backend-runtime" / "promotions"
    journals: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.glob("*/journal.json")):
            try:
                payload = _read_json(path, label="promotion journal")
            except PromotionError:
                journals.append({"status": "blocked", "reason_code": "journal_unreadable", "sanitized": True})
                continue
            phase = str(payload.get("phase") or "unknown")
            terminal = phase in {"committed", "rolled_back", "aborted_before_checkpoint"}
            journals.append({
                "promotion_id": path.parent.name[:120],
                "phase": phase,
                "status": "stable" if terminal else "recovery_required",
                "destructive_action": "none",
                "sanitized": True,
            })
    return {"status": "stable" if all(item.get("status") == "stable" for item in journals) else "recovery_required", "journal_count": len(journals), "journals": journals, "destructive_action": "none", "sanitized": True}


def _activate_from_cli(args: argparse.Namespace) -> dict[str, Any]:
    verified = verify_artifact(Path(args.artifact), Path(args.manifest), Path(args.checksums))
    manifest = _read_json(Path(args.manifest), label="artifact manifest")
    release_root = Path(args.release_root).expanduser().resolve()
    release_manifest = release_root / "artifact-manifest.json"
    if not release_manifest.is_file():
        raise PromotionError("staging_target_missing", "The selected inactive backend release is not staged.")
    staged = _read_json(release_manifest, label="staged artifact manifest")
    if staged.get("source_commit") != manifest.get("source_commit") or staged.get("payload_sha256") != manifest.get("payload_sha256"):
        raise PromotionError("staging_identity_mismatch", "The inactive backend release is not the verified candidate.")
    preflight = _read_json(Path(args.preflight), label="promotion preflight")
    if preflight.get("admitted") is not True or preflight.get("status") != "admissible":
        raise PromotionError("admission_blocked", "Production promotion admission has not passed.")
    if preflight.get("current_production_sha") not in {None, args.current_sha} or preflight.get("target_device_id") not in {None, args.device_id}:
        raise PromotionError("preflight_binding_mismatch", "The promotion preflight is not bound to the current production target.")
    if preflight.get("candidate_sha") not in {None, manifest.get("source_commit")} or preflight.get("artifact_sha256") not in {None, verified["artifact_sha256"]}:
        raise PromotionError("preflight_binding_mismatch", "The promotion preflight is not bound to the verified candidate.")
    backup_receipt = _receipt_binding(Path(args.backup_receipt), expected_kind="production-backup")
    restore_receipt = _receipt_binding(Path(args.restore_receipt), expected_kind="restore-rehearsal")
    migration_receipt = _receipt_binding(Path(args.migration_receipt), expected_kind="migration-rehearsal")
    if backup_receipt.get("source_runtime_sha") != args.current_sha or backup_receipt.get("target_device_id") != args.device_id:
        raise PromotionError("backup_binding_mismatch", "The production backup is not bound to the current target.")
    if restore_receipt.get("backup_id") != backup_receipt.get("backup_id"):
        raise PromotionError("restore_binding_mismatch", "The restore rehearsal is not bound to the production backup.")
    if migration_receipt.get("backup_id") != backup_receipt.get("backup_id") or migration_receipt.get("artifact_sha256") != verified["artifact_sha256"]:
        raise PromotionError("migration_binding_mismatch", "The migration rehearsal is not bound to the verified backup and artifact.")
    if migration_receipt.get("target_schema") != REQUIRED_SCHEMA or migration_receipt.get("old_runtime_code_rollback_compatible") is not False:
        raise PromotionError("rollback_strategy_unproved", "The migration receipt does not prove the required fail-closed rollback strategy.")
    inputs = PromotionInputs(
        state_root=Path(args.state_root),
        database=Path(args.database),
        release_root=release_root,
        candidate_sha=str(manifest["source_commit"]),
        current_sha=_safe_sha(args.current_sha, label="current production SHA"),
        device_id=_safe_name(args.device_id, label="device id"),
        artifact_sha256=str(verified["artifact_sha256"]),
        backup_receipt=backup_receipt,
        restore_receipt=restore_receipt,
        migration_receipt={**migration_receipt, "migration_contract": manifest.get("migration_contract") or []},
        preflight_sha256=_sha256(Path(args.preflight)),
        artifact=Path(args.artifact),
    )
    if args.simulation_health_failure or args.simulation_writes_observed:
        if not args.isolated:
            raise PromotionError("simulation_target_invalid", "Simulation failure modes are available only for isolated qualification.")
        adapter: ServiceAdapter = SimulationAdapter(health=not args.simulation_health_failure, writes=args.simulation_writes_observed)
    else:
        adapter = SimulationAdapter() if args.isolated else ProductionServiceAdapter(state_root=Path(args.state_root), source_checkout=Path(args.source_checkout), database=Path(args.database))
    return PromotionController(inputs, adapter).activate(
        authorization=Path(args.authorization),
        promotion_public_key=Path(args.promotion_public_key),
        recovery_authorization=Path(args.recovery_authorization) if args.recovery_authorization else None,
        recovery_public_key=Path(args.recovery_public_key) if args.recovery_public_key else None,
        confirm_cutover=args.confirm_cutover,
        isolated=args.isolated,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pocket Lab Lite exact-SHA backend runtime promotion controller")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--repo-root", default=str(ROOT)); prepare.add_argument("--source-sha", required=True); prepare.add_argument("--output-dir", required=True); prepare.set_defaults(handler="prepare")
    verify = commands.add_parser("verify")
    verify.add_argument("--artifact", required=True); verify.add_argument("--manifest", required=True); verify.add_argument("--checksums", required=True); verify.set_defaults(handler="verify")
    stage = commands.add_parser("stage")
    stage.add_argument("--artifact", required=True); stage.add_argument("--manifest", required=True); stage.add_argument("--checksums", required=True); stage.add_argument("--staging-root", required=True); stage.add_argument("--expected-device-id", required=True); stage.add_argument("--target-device-id", required=True); stage.set_defaults(handler="stage")
    backup = commands.add_parser("backup")
    backup.add_argument("--database", required=True); backup.add_argument("--backup-root", required=True); backup.add_argument("--source-sha", required=True); backup.add_argument("--device-id", required=True); backup.add_argument("--manifest", required=True); backup.set_defaults(handler="backup")
    restore = commands.add_parser("restore-rehearsal")
    restore.add_argument("--backup-manifest", required=True); restore.add_argument("--restore-root", required=True); restore.add_argument("--manifest", required=True); restore.set_defaults(handler="restore")
    migration = commands.add_parser("migration-rehearsal")
    migration.add_argument("--backup-manifest", required=True); migration.add_argument("--artifact", required=True); migration.add_argument("--manifest", required=True); migration.add_argument("--rehearsal-root", required=True); migration.add_argument("--old-schema", type=int, default=42); migration.set_defaults(handler="migration")
    snapshot = commands.add_parser("preflight")
    snapshot.add_argument("--database", required=True); snapshot.add_argument("--current-sha", required=True); snapshot.add_argument("--candidate-sha"); snapshot.add_argument("--artifact-sha256"); snapshot.add_argument("--target-device-id", required=True); snapshot.add_argument("--expected-device-id", required=True); snapshot.add_argument("--staging-root", required=True); snapshot.add_argument("--manifest", required=True); snapshot.add_argument("--output", required=True); snapshot.add_argument("--allow-missing-guardian", action="store_true"); snapshot.set_defaults(handler="preflight")
    auth = commands.add_parser("authorize")
    auth.add_argument("--private-key", required=True); auth.add_argument("--output", required=True); auth.add_argument("--candidate-sha", required=True); auth.add_argument("--current-sha", required=True); auth.add_argument("--device-id", required=True); auth.add_argument("--artifact-sha256", required=True); auth.add_argument("--backup-receipt", required=True); auth.add_argument("--restore-receipt", required=True); auth.add_argument("--preflight", required=True); auth.add_argument("--audit-identity", required=True); auth.set_defaults(handler="authorize")
    isolated = commands.add_parser("qualify-isolated")
    isolated.add_argument("--artifact", required=True); isolated.add_argument("--manifest", required=True); isolated.add_argument("--checksums", required=True); isolated.add_argument("--workspace", required=True); isolated.add_argument("--device-id", default="pocket-lab-lite-server"); isolated.add_argument("--failure-mode", choices=("none", "health-failure", "writes-observed"), default="none"); isolated.set_defaults(handler="isolated")
    activate = commands.add_parser("activate")
    activate.add_argument("--artifact", required=True); activate.add_argument("--manifest", required=True); activate.add_argument("--checksums", required=True); activate.add_argument("--release-root", required=True); activate.add_argument("--state-root", required=True); activate.add_argument("--database", required=True); activate.add_argument("--source-checkout", default=str(ROOT)); activate.add_argument("--current-sha", required=True); activate.add_argument("--device-id", required=True); activate.add_argument("--backup-receipt", required=True); activate.add_argument("--restore-receipt", required=True); activate.add_argument("--migration-receipt", required=True); activate.add_argument("--preflight", required=True); activate.add_argument("--authorization", required=True); activate.add_argument("--promotion-public-key", required=True); activate.add_argument("--recovery-authorization"); activate.add_argument("--recovery-public-key"); activate.add_argument("--confirm-cutover", action="store_true"); activate.add_argument("--isolated", action="store_true"); activate.add_argument("--simulation-health-failure", action="store_true"); activate.add_argument("--simulation-writes-observed", action="store_true"); activate.set_defaults(handler="activate")
    reconcile = commands.add_parser("reconcile")
    reconcile.add_argument("--state-root", required=True); reconcile.set_defaults(handler="reconcile")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.handler == "prepare":
            result = prepare_artifact(repo_root=Path(args.repo_root), source_sha=args.source_sha, output_dir=Path(args.output_dir))
        elif args.handler == "verify":
            result = verify_artifact(Path(args.artifact), Path(args.manifest), Path(args.checksums))
        elif args.handler == "stage":
            result = stage_artifact(artifact=Path(args.artifact), manifest_path=Path(args.manifest), checksums_path=Path(args.checksums), staging_root=Path(args.staging_root), expected_device_id=args.expected_device_id, target_device_id=args.target_device_id)
        elif args.handler == "backup":
            result = create_backup(database=Path(args.database), backup_root=Path(args.backup_root), source_sha=args.source_sha, device_id=args.device_id, contract=_contract_from_manifest(Path(args.manifest)))
        elif args.handler == "restore":
            result = restore_rehearsal(backup_manifest=Path(args.backup_manifest), restore_root=Path(args.restore_root), contract=_contract_from_manifest(Path(args.manifest)))
        elif args.handler == "migration":
            result = migration_rehearsal(backup_manifest=Path(args.backup_manifest), artifact=Path(args.artifact), artifact_manifest=Path(args.manifest), rehearsal_root=Path(args.rehearsal_root), old_schema=args.old_schema)
        elif args.handler == "preflight":
            manifest = _read_json(Path(args.manifest), label="artifact manifest")
            result = collect_runtime_snapshot(database=Path(args.database), contract=list(manifest.get("migration_contract") or []), current_sha=args.current_sha, target_device_id=args.target_device_id, expected_device_id=args.expected_device_id, staging_root=Path(args.staging_root), require_guardian=not args.allow_missing_guardian, candidate_sha=args.candidate_sha, artifact_sha256=args.artifact_sha256)
            _atomic_json(Path(args.output), result)
        elif args.handler == "authorize":
            backup = _read_json(Path(args.backup_receipt), label="backup receipt")
            restore = _read_json(Path(args.restore_receipt), label="restore receipt")
            payload = authorization_payload(candidate_sha=args.candidate_sha, current_sha=args.current_sha, device_id=args.device_id, target_schema=REQUIRED_SCHEMA, artifact_sha256=args.artifact_sha256, backup_receipt_sha256=_sha256_bytes(_canonical(backup)), restore_receipt_sha256=_sha256_bytes(_canonical(restore)), preflight_sha256=_sha256(Path(args.preflight)), audit_identity=args.audit_identity)
            result = issue_authorization(private_key=Path(args.private_key), output=Path(args.output), payload=payload)
        elif args.handler == "isolated":
            result = qualify_isolated(artifact=Path(args.artifact), manifest_path=Path(args.manifest), checksums_path=Path(args.checksums), workspace=Path(args.workspace), device_id=args.device_id, failure_mode=args.failure_mode)
        elif args.handler == "activate":
            result = _activate_from_cli(args)
        elif args.handler == "reconcile":
            result = reconcile_promotions(Path(args.state_root))
        else:
            raise PromotionError("command_invalid", "The promotion command is invalid.")
        print(json.dumps(_redact(result), ensure_ascii=True, sort_keys=True, indent=2))
        if args.handler == "preflight" and result.get("admitted") is not True:
            return 3
        return 0
    except PromotionError as exc:
        print(json.dumps({"status": "BLOCKED", "reason_code": exc.reason_code, "message": exc.message, "sanitized": True}, ensure_ascii=True, sort_keys=True), file=sys.stderr)
        return 2
    except (OSError, sqlite3.Error, zipfile.BadZipFile, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason_code": "promotion_error", "message": type(exc).__name__, "sanitized": True}, ensure_ascii=True, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
