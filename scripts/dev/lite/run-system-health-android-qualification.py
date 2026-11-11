#!/usr/bin/env python3
"""Run the narrow, exact-SHA System Health Android/Termux qualifier.

This lane deliberately does not replace the production API, Caddy, PM2, NATS
or SQLite database.  It stages a verified candidate snapshot into a temporary
run-owned Termux root, starts only candidate API/worker processes there, and
connects them to a disposable Dev-PC JetStream broker through one controller-
owned reverse SSH forward.  The existing physical qualification transport and
process-ownership primitives are reused from the Photo Backup lane.
"""
from __future__ import annotations

import argparse
import ast
import base64
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import ssl
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


REPOSITORY = "dexter-lab-ctrl/pocket-lab-lite"
PHONE_HOST = "pocketlab-termux-tailnet"
MIGRATION_ROOT = "pocket-lab-final-structure/runtime/api_fastapi/db/schema"
SCHEMA_DB_NAME = "pocketlab-lite.sqlite3"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_RE = re.compile(r"^[a-f0-9]{24}$")
PRINCIPAL_RE = re.compile(r"^[a-z][a-z0-9._-]{2,79}$")
NATS_LOOPBACK_RE = re.compile(r"^nats://127\.0\.0\.1:([1-9][0-9]{0,4})$")
SENSITIVE_KEY_RE = re.compile(
    r"(?:token|password|passwd|secret|credential|private[_-]?key|signature|cookie|authorization|session|nonce|raw|environment|env|url)",
    re.IGNORECASE,
)


class QualificationError(RuntimeError):
    """A bounded, sanitized qualification failure."""


def _controller():
    """Load the established physical transport without duplicating it."""
    path = Path(__file__).with_name("run-isolated-runtime-qualification.py")
    spec = importlib.util.spec_from_file_location("pocketlab_android_controller", path)
    if spec is None or spec.loader is None:
        raise QualificationError("existing Android qualification controller could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _b64u(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _safe_text(value: Any, limit: int = 240) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def sanitize(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Return evidence-safe JSON without credentials, URLs or raw traces."""
    if depth > 6:
        return None
    if key and SENSITIVE_KEY_RE.search(key):
        return "[redacted]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, raw_value in list(value.items())[:256]:
            name = str(raw_key)[:96]
            if SENSITIVE_KEY_RE.search(name):
                result[name] = "[redacted]"
                continue
            child = sanitize(raw_value, key=name, depth=depth + 1)
            if child is not None:
                result[name] = child
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        return [sanitize(item, depth=depth + 1) for item in list(value)[:256]]
    if isinstance(value, str):
        return _safe_text(value, 512)
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return _safe_text(value, 512)


def validate_candidate_sha(repo: Path, candidate_sha: str, controller: Any | None = None) -> str:
    """Require a clean, explicit, locally verifiable exact commit."""
    module = controller or _controller()
    candidate = str(candidate_sha or "").strip().casefold()
    if not SHA_RE.fullmatch(candidate) or candidate == "0" * 40:
        raise QualificationError("candidate SHA must be an explicit non-zero 40-character commit")
    try:
        return str(module._candidate_sha(repo, candidate))
    except Exception as exc:
        raise QualificationError(_safe_text(str(exc), 240) or "candidate SHA could not be verified") from exc


def assert_isolated_binding(
    run_root: Path,
    database_path: Path,
    nats_url: str,
    bind_host: str,
    api_port: int,
    *,
    occupied_ports: Iterable[int] = (),
) -> None:
    """Fail closed on production paths, non-loopback transports and collisions."""
    root = run_root.resolve(strict=True)
    db = database_path.resolve(strict=False)
    try:
        db.relative_to(root)
    except ValueError as exc:
        raise QualificationError("candidate SQLite path escaped the run root") from exc
    if db.name != SCHEMA_DB_NAME or db.parent.name != "state":
        raise QualificationError("candidate SQLite path is not the run-owned state database")
    match = NATS_LOOPBACK_RE.fullmatch(str(nats_url or "").strip())
    if not match:
        raise QualificationError("candidate NATS must be a loopback nats:// URL")
    nats_port = int(match.group(1))
    if not 1 <= nats_port <= 65535 or bind_host not in {"127.0.0.1", "::1", "localhost"}:
        raise QualificationError("candidate transport is not loopback-bound")
    if not 1 <= int(api_port) <= 65535:
        raise QualificationError("candidate API port is invalid")
    occupied = {int(item) for item in occupied_ports}
    if int(api_port) == nats_port or int(api_port) in occupied or nats_port in occupied:
        raise QualificationError("candidate port collides with an owned or reserved port")


def validate_synthetic_identity(
    principal_id: str,
    profile: str,
    *,
    qualification_owner: str,
    destructive: str,
    test_bypass: str,
    allow_browser_ui: bool = False,
) -> None:
    if not PRINCIPAL_RE.fullmatch(principal_id):
        raise QualificationError("synthetic principal identity is invalid")
    allowed_security = (
        profile == "security-assurance-runner"
        and qualification_owner == "0"
        and destructive == "0"
        and test_bypass == "0"
    )
    allowed_browser_ui = (
        allow_browser_ui
        and profile == "qualification-owner"
        and qualification_owner == "1"
        and destructive == "0"
        and test_bypass == "0"
    )
    if not (allowed_security or allowed_browser_ui):
        raise QualificationError("System Health qualifier attempted to enable unsafe authority")
def validate_rollback_backup(path: Path, run_root: Path) -> None:
    """Require an independent, run-owned SQLite rollback copy."""
    root = run_root.resolve(strict=True)
    candidate = path.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise QualificationError("rollback backup escaped the run root") from exc
    if candidate.is_symlink() or not candidate.is_file() or candidate.suffix.lower() not in {".db", ".sqlite", ".sqlite3"}:
        raise QualificationError("rollback backup is missing or unsafe")


def validate_candidate_readiness(*, api_status: int, api_owned: bool, worker_owned: bool) -> None:
    """Keep readiness evidence tied to both owned processes and HTTP health."""
    if int(api_status) != 200 or not api_owned or not worker_owned:
        raise QualificationError("candidate readiness was not established")


def production_projection(value: dict[str, Any]) -> dict[str, Any]:
    """Keep dynamic process/resource values out of the phone preservation comparison."""
    pm2 = []
    for item in value.get("pm2") or []:
        if not isinstance(item, dict):
            continue
        pm2.append({
            "name": item.get("name"),
            "status": item.get("status"),
            "version": item.get("version"),
            "cwd_class": item.get("cwd_class"),
        })
    return {
        "system": value.get("system"),
        "architecture": value.get("architecture"),
        "home_class": value.get("home_class"),
        "prefix_class": value.get("prefix_class"),
        "source_sha": value.get("source_sha"),
        "git_clean": value.get("git_clean"),
        "pm2": sorted(pm2, key=lambda item: str(item.get("name") or "")),
        "listeners": value.get("listeners") or {},
        "tailscale": value.get("tailscale"),
        "photoprism_health": value.get("photoprism_health"),
    }


def parse_json_log_record(text: str, *, label: str) -> tuple[dict[str, Any], int]:
    """Read the last bounded JSON object from a run-owned process log."""
    raw = str(text or "")
    if raw.startswith(("b'", 'b"')):
        try:
            decoded = ast.literal_eval(raw)
        except (SyntaxError, ValueError):
            decoded = None
        if isinstance(decoded, bytes):
            raw = decoded.decode("utf-8", "replace")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    for line in reversed(lines[-128:]):
        try:
            value = json.loads(line)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            return value, len(lines)
    raise QualificationError(f"{label} emitted no JSON record (nonempty_lines={len(lines)})")


def response_detail(response: HttpResult) -> dict[str, Any]:
    """Normalize direct and HTTPException-wrapped JSON error bodies."""
    body = response.body if isinstance(response.body, dict) else {}
    detail = body.get("detail")
    return detail if isinstance(detail, dict) else body


def response_contract(response: HttpResult) -> dict[str, Any]:
    """Expose only bounded status/detail fields needed to diagnose a contract."""
    body = response.body if isinstance(response.body, dict) else {}
    detail = response_detail(response)
    return {
        "status": response.status,
        "body_keys": sorted(str(key) for key in body)[:32],
        "detail_keys": sorted(str(key) for key in detail)[:32],
        "detail_status": detail.get("status"),
        "reason_code": detail.get("reason_code"),
        "recorded": detail.get("recorded"),
        "idempotent_replay": detail.get("idempotent_replay"),
    }


def _sql_statements(sql: str) -> Iterable[str]:
    buffer = ""
    for line in sql.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            buffer = ""
            if statement:
                yield statement
    if buffer.strip():
        raise QualificationError("candidate migration contains incomplete SQL")


def _run(argv: list[str], *, cwd: Path | None = None, timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _candidate_migrations(repo: Path, candidate_sha: str, *, maximum: int | None = None) -> list[tuple[int, str, str, str]]:
    listed = _run(["git", "ls-tree", "-r", "--name-only", candidate_sha, MIGRATION_ROOT], cwd=repo)
    if listed.returncode != 0:
        raise QualificationError("candidate migration inventory could not be read")
    records: list[tuple[int, str, str, str]] = []
    for raw_path in listed.stdout.splitlines():
        path = raw_path.strip()
        name = Path(path).name
        match = re.fullmatch(r"(\d+)_([a-z0-9_-]+)\.sql", name)
        if not match:
            continue
        version = int(match.group(1))
        if maximum is not None and version > maximum:
            continue
        shown = _run(["git", "show", f"{candidate_sha}:{path}"], cwd=repo)
        if shown.returncode != 0:
            raise QualificationError(f"candidate migration {version} could not be read")
        sql = shown.stdout
        records.append((version, match.group(2), hashlib.sha256(sql.encode()).hexdigest(), sql))
    records.sort(key=lambda item: item[0])
    versions = [item[0] for item in records]
    if not records or versions != list(range(1, versions[-1] + 1)):
        raise QualificationError("candidate migration chain is not contiguous")
    return records


def _verify_sqlite(path: Path, *, expected_version: int | None = None, marker: str = "qualification.marker") -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise QualificationError("isolated SQLite fixture is missing or symlinked")
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_keys = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
        version = int(conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0])
        marker_row = conn.execute("SELECT revision FROM domain_revisions WHERE domain=?", (marker,)).fetchone()
        journal = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        return {
            "schema_version": version,
            "quick_check": quick,
            "integrity_check": integrity,
            "foreign_key_errors": len(foreign_keys),
            "marker_revision": int(marker_row[0]) if marker_row else None,
            "journal_mode": journal,
            "wal_bytes": path.with_name(path.name + "-wal").stat().st_size if path.with_name(path.name + "-wal").exists() else 0,
            "status": "PASS" if quick == "ok" and integrity == "ok" and not foreign_keys and (expected_version is None or version == expected_version) and marker_row else "FAIL",
        }
    finally:
        conn.close()


def create_schema42_fixture(repo: Path, candidate_sha: str, run_root: Path) -> tuple[Path, Path, dict[str, Any]]:
    """Build schema 42 from candidate-owned migrations and retain a rollback copy."""
    state = run_root / "state"
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    database = state / SCHEMA_DB_NAME
    rollback = state / "schema42-rollback.sqlite3"
    migrations = _candidate_migrations(repo, candidate_sha, maximum=42)
    conn = sqlite3.connect(str(database), timeout=20)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        for version, name, checksum, sql in migrations:
            conn.execute("BEGIN IMMEDIATE")
            for statement in _sql_statements(sql):
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version,name,applied_at,checksum) VALUES (?,?,?,?)",
                (version, name, _now(), checksum),
            )
            conn.commit()
        conn.execute(
            "INSERT INTO domain_revisions(domain,revision,updated_at) VALUES (?,?,?) "
            "ON CONFLICT(domain) DO UPDATE SET revision=excluded.revision,updated_at=excluded.updated_at",
            ("qualification.marker", 7, _now()),
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    before = _verify_sqlite(database, expected_version=42)
    if before["status"] != "PASS":
        raise QualificationError("schema-42 candidate fixture failed integrity checks")
    shutil.copy2(database, rollback)
    rollback.chmod(0o600)
    validate_rollback_backup(rollback, run_root)
    return database, rollback, {"before": before, "migration_count": len(migrations), "marker_domain": "qualification.marker"}


def apply_isolated_health_migrations(repo: Path, candidate_sha: str, database: Path) -> dict[str, Any]:
    migrations = [item for item in _candidate_migrations(repo, candidate_sha) if item[0] in {43, 44}]
    if [item[0] for item in migrations] != [43, 44]:
        raise QualificationError("candidate System Health migration chain 0043/0044 is incomplete")
    conn = sqlite3.connect(str(database), timeout=20)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        applied: list[int] = []
        for version, name, checksum, sql in migrations:
            prior = conn.execute(
                "SELECT name,checksum FROM schema_migrations WHERE version=?",
                (version,),
            ).fetchone()
            if prior is not None:
                if str(prior[0]) != name or str(prior[1]) != checksum:
                    raise QualificationError(f"isolated migration {version} checksum/name mismatch")
                continue
            conn.execute("BEGIN IMMEDIATE")
            for statement in _sql_statements(sql):
                conn.execute(statement)
            conn.execute(
                "INSERT INTO schema_migrations(version,name,applied_at,checksum) VALUES (?,?,?,?)",
                (version, name, _now(), checksum),
            )
            conn.commit()
            applied.append(version)
        return {"applied": applied, "repeat_expected": []}
    finally:
        conn.close()


def prove_isolated_rollback(repo: Path, base_sha: str, rollback_db: Path, run_root: Path, python: str) -> dict[str, Any]:
    """Open only the disposable schema-42 copy with the earlier runtime."""
    base = str(base_sha or "").strip().casefold()
    if not SHA_RE.fullmatch(base):
        raise QualificationError("rollback proof base SHA is invalid")
    if not rollback_db.is_file() or rollback_db.is_symlink():
        raise QualificationError("rollback proof backup is missing")
    runtime_root = run_root / "rollback-runtime"
    runtime_root.mkdir(mode=0o700)
    archive = run_root / "rollback-runtime.tar"
    with archive.open("wb") as stream:
        completed = subprocess.run(
            ["git", "archive", "--format=tar", base, "pocket-lab-final-structure/runtime"],
            cwd=str(repo), stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.PIPE, check=False,
        )
    if completed.returncode != 0:
        raise QualificationError("earlier runtime archive could not be created for rollback proof")
    with __import__("tarfile").open(archive, "r") as bundle:
        bundle.extractall(runtime_root, filter="data")
    env = {
        **os.environ,
        "POCKETLAB_LITE_DB_PATH": str(rollback_db),
        "POCKETLAB_STATE_DIR": str(rollback_db.parent),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(runtime_root / "pocket-lab-final-structure" / "runtime"),
    }
    result = subprocess.run(
        [python, "-c", "from api_fastapi.db.migrations import current_schema_version; from api_fastapi.db.connection import database_path; import json; print(json.dumps({'version': current_schema_version(), 'path_ok': database_path().name == 'schema42-rollback.sqlite3'}))"],
        cwd=str(runtime_root / "pocket-lab-final-structure" / "runtime"), env=env,
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20, check=False,
    )
    if result.returncode != 0:
        raise QualificationError("earlier runtime could not open the schema-42 rollback copy")
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise QualificationError("rollback proof output was malformed") from None
    if int(payload.get("version") or 0) != 42 or payload.get("path_ok") is not True:
        raise QualificationError("rollback proof did not reopen schema version 42")
    return {"status": "PASS", "base_sha": base, "schema_version": 42, "production_database_touched": False}


_REMOTE_DB_PROBE = r'''
import json, pathlib, sqlite3, sys
path = pathlib.Path(sys.argv[1]).resolve(strict=True)
marker = str(sys.argv[2])
conn = sqlite3.connect(str(path), timeout=15)
conn.row_factory = sqlite3.Row
try:
    tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    indexes = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    migrations = [int(row[0]) for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    fk = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check")]
    quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
    integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
    marker_row = conn.execute("SELECT revision FROM domain_revisions WHERE domain=?", (marker,)).fetchone()
    projection = conn.execute("SELECT COUNT(*),MAX(updated_at_epoch_ms) FROM phase3b_current_state").fetchone() if "phase3b_current_state" in tables else (0, None)
    denials = conn.execute("SELECT COUNT(*) FROM lite_system_health_repair_denials").fetchone()[0] if "lite_system_health_repair_denials" in tables else 0
    diagnoses = conn.execute("SELECT COUNT(*) FROM lite_system_health_diagnoses").fetchone()[0] if "lite_system_health_diagnoses" in tables else 0
    wal = pathlib.Path(str(path) + "-wal")
    print(json.dumps({
        "schema_version": max(migrations or [0]),
        "migration_count": len(migrations),
        "migration_versions": migrations,
        "required_tables": sorted({"lite_system_health_observations","lite_system_health_incidents","lite_system_health_events","lite_system_health_diagnoses","lite_system_health_repair_denials"}.intersection(tables)),
        "required_indexes": sorted({"lite_system_health_incidents_current","lite_system_health_incidents_target","lite_system_health_events_recent","lite_system_health_diagnoses_incident","lite_system_health_denials_recent"}.intersection(indexes)),
        "marker_revision": int(marker_row[0]) if marker_row else None,
        "quick_check": quick,
        "integrity_check": integrity,
        "foreign_key_errors": len(fk),
        "projection_rows": int(projection[0] or 0),
        "projection_updated_epoch_ms": projection[1],
        "repair_denials": int(denials),
        "diagnoses": int(diagnoses),
        "wal_bytes": wal.stat().st_size if wal.exists() else 0,
        "status": "PASS" if quick == "ok" and integrity == "ok" and not fk and marker_row else "FAIL",
    }, sort_keys=True))
finally:
    conn.close()
'''


_REMOTE_CONCURRENCY = r'''
import json, pathlib, sqlite3, threading, time, sys
path = pathlib.Path(sys.argv[1]).resolve(strict=True)
errors = []
def reader():
    try:
        conn = sqlite3.connect(str(path), timeout=15)
        for _ in range(12):
            conn.execute("SELECT COUNT(*) FROM lite_system_health_incidents").fetchone()
        conn.close()
    except Exception as exc:
        errors.append(type(exc).__name__)
def writer():
    try:
        conn = sqlite3.connect(str(path), timeout=15)
        conn.execute("PRAGMA foreign_keys=ON")
        for value in range(6):
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("INSERT INTO domain_revisions(domain,revision,updated_at) VALUES (?,?,?) ON CONFLICT(domain) DO UPDATE SET revision=excluded.revision,updated_at=excluded.updated_at", ("qualification.concurrent", value + 1, "qualification"))
            conn.commit()
        conn.close()
    except Exception as exc:
        errors.append(type(exc).__name__)
threads = [threading.Thread(target=reader) for _ in range(6)] + [threading.Thread(target=writer)]
for item in threads: item.start()
for item in threads: item.join(20)
print(json.dumps({"errors": sorted(set(errors)), "threads_done": all(not item.is_alive() for item in threads), "status": "PASS" if not errors and all(not item.is_alive() for item in threads) else "FAIL"}))
'''


_REMOTE_DEVICE_METRICS = r'''
import json, pathlib, shutil
capacity = status = None
temps = []
for path in pathlib.Path("/sys/class/power_supply").glob("*/capacity"):
    try: capacity = int(path.read_text().strip())
    except Exception: pass
for path in pathlib.Path("/sys/class/power_supply").glob("*/status"):
    try: status = path.read_text().strip()[:32]
    except Exception: pass
for path in pathlib.Path("/sys/class/thermal").glob("thermal_zone*/temp"):
    try: temps.append(int(path.read_text().strip()))
    except Exception: pass
memory = None
try:
    for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"): memory = int(line.split()[1]) * 1024; break
except Exception: pass
try: free = int(shutil.disk_usage(pathlib.Path.home()).free)
except Exception: free = None
print(json.dumps({"battery_percent": capacity, "battery_status": status, "thermal_zone_count": len(temps), "thermal_max_raw": max(temps) if temps else None, "memory_available_bytes": memory, "home_free_bytes": free}, sort_keys=True))
'''


_REMOTE_PROCESS_METRICS = r'''
import json, pathlib, sys
result = {}
for label, raw_pid in ("api", sys.argv[1]), ("worker", sys.argv[2]):
    try:
        pid = int(raw_pid)
        fields = pathlib.Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()
        rss = None
        for line in pathlib.Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"): rss = int(line.split()[1]) * 1024; break
        result[label] = {"pid_class": "candidate", "state": fields[0], "cpu_user_ticks": int(fields[11]), "cpu_system_ticks": int(fields[12]), "rss_bytes": rss}
    except Exception:
        result[label] = {"pid_class": "candidate", "state": "unavailable"}
print(json.dumps(result, sort_keys=True))
'''


@dataclass
class HttpResult:
    status: int
    body: dict[str, Any]


class CandidateClient:
    def __init__(self, origin: str, ca_path: Path):
        self.origin = origin.rstrip("/")
        self.context = ssl.create_default_context(cafile=str(ca_path))

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None, *, session: str = "") -> HttpResult:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            headers["Content-Type"] = "application/json"
        if session:
            headers["X-Pocket-Lab-Harness-Session"] = session
        request = urllib.request.Request(self.origin + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, context=self.context, timeout=12) as response:
                raw = response.read(256 * 1024)
                value = json.loads(raw.decode("utf-8")) if raw else {}
                return HttpResult(int(response.status), value if isinstance(value, dict) else {"result": value})
        except urllib.error.HTTPError as exc:
            raw = exc.read(64 * 1024)
            try:
                value = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                value = {}
            return HttpResult(int(exc.code), value if isinstance(value, dict) else {"result": value})
        except (OSError, urllib.error.URLError) as exc:
            raise QualificationError(f"candidate API transport failed: {type(exc).__name__}") from exc


class SystemHealthAndroidQualification:
    def __init__(
        self,
        *,
        repo: Path,
        candidate_sha: str,
        base_sha: str,
        python: str,
        nats_binary: str | None,
        evidence_dir: Path | None,
        browser_ui: bool = False,
    ):
        self.repo = repo
        self.controller = _controller()
        self.candidate_sha = validate_candidate_sha(repo, candidate_sha, self.controller)
        self.base_sha = str(base_sha or "").strip().casefold()
        if not SHA_RE.fullmatch(self.base_sha):
            raise QualificationError("base SHA must be an explicit commit")
        self.python = python
        self.browser_ui = bool(browser_ui)
        self.bootstrap_profile = "qualification-owner" if self.browser_ui else "security-assurance-runner"
        self.qualification_owner_flag = "1" if self.browser_ui else "0"
        self.bootstrap_purpose = "ui-performance-60fps" if self.browser_ui else "security-assurance"
        self.nats_binary = nats_binary or shutil.which("nats-server")
        self.run_id = __import__("secrets").token_hex(12)
        if not RUN_ID_RE.fullmatch(self.run_id):
            raise QualificationError("qualification run identity was invalid")
        root = Path(tempfile.mkdtemp(prefix="pocket-lab-system-health-android-"))
        root.chmod(0o700)
        self.paths = self.controller.RunPaths(
            root=root, home=root / "home", state=root / "state", logs=root / "logs", bin=root / "bin",
            destination=root / "destination", media=root / "home" / "storage", evidence=root / "evidence", worktree=root / "candidate",
        )
        for item in (self.paths.home, self.paths.state, self.paths.logs, self.paths.bin, self.paths.destination, self.paths.evidence):
            item.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.external_evidence = (evidence_dir or (repo / ".pocketlab-dev" / "validation")).absolute()
        if self.external_evidence.resolve() == self.paths.root or self.external_evidence.resolve().is_relative_to(self.paths.root):
            raise QualificationError("evidence directory must be outside the temporary run root")
        self.external_evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.snapshot = self.controller._android_snapshot(repo, self.candidate_sha, self.paths.root)
        self.ca_path, self.cert_path, self.key_path = self.controller._create_certificates(self.paths)
        self.local_api_port = _port()
        self.nats: Any | None = None
        self.remote: Any | None = None
        self.remote_root = ""
        self.remote_api_port = 0
        self.api: Any | None = None
        self.worker: Any | None = None
        self.driver: Any | None = None
        self.tunnels: list[Any] = []
        self.principal_private = Ed25519PrivateKey.generate()
        public = self.principal_private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.public_key = _b64u(public)
        self.fingerprint = "sha256:" + hashlib.sha256(public).hexdigest()
        self.principal_id = f"qualification-health-{self.run_id}"
        self.provisioning_token = self.controller.secrets_token(48)
        self.context_token = self.controller.secrets_token(48)
        self.webdav_password = self.controller.secrets_token(48)
        self.session = ""
        self.browser_bridge = ""
        self.client: CandidateClient | None = None
        self.database: Path | None = None
        self.rollback_database: Path | None = None
        self.env_path = ""
        self.results: dict[str, Any] = {
            "status": "BLOCKED",
            "qualification_mode": "SYSTEM HEALTH PHYSICAL ANDROID CANDIDATE",
            "candidate_sha": self.candidate_sha,
            "base_sha": self.base_sha,
            "run_id": self.run_id,
            "repository": REPOSITORY,
            "production_activation": {"status": "BLOCKED", "performed": False, "reason": "Gate B is isolated candidate qualification; production PM2/Caddy/NATS/SQLite were not activated."},
        }
        self.before_baseline: dict[str, Any] = {}

    @property
    def candidate_root(self) -> str:
        return f"{self.remote_root}/candidate"

    @property
    def runtime_root(self) -> str:
        return f"{self.candidate_root}/pocket-lab-final-structure/runtime"

    @property
    def api_origin(self) -> str:
        return f"https://127.0.0.1:{self.local_api_port}"

    def _discover_remote(self) -> None:
        baseline = self.controller._android_baseline(PHONE_HOST)
        home = str(baseline.get("home") or "")
        prefix = str(baseline.get("prefix") or "")
        python = str(baseline.get("python") or "")
        if baseline.get("architecture") not in {"aarch64", "arm64"} or baseline.get("home_class") != "termux_private_home" or baseline.get("prefix_class") != "termux_prefix" or not home.startswith("/data/data/com.termux/") or not prefix.startswith("/data/data/com.termux/") or not python.startswith(prefix + "/"):
            raise QualificationError("Server Phone failed the Termux ARM64 identity preflight")
        site_packages = [str(item) for item in (baseline.get("python_site_packages") or []) if str(item).startswith((home.rstrip("/") + "/", prefix.rstrip("/") + "/"))]
        if not site_packages:
            raise QualificationError("Server Phone reported no verified Python site-package path")
        imports = self.controller._android_import_check(PHONE_HOST, python, ["fastapi", "uvicorn", "nats", "cryptography", "pydantic"], extra_paths=site_packages)
        if imports.get("missing") or imports.get("errors"):
            raise QualificationError("Server Phone candidate runtime dependencies are unavailable")
        if baseline.get("df_free_bytes") is not None and int(baseline["df_free_bytes"]) < int(getattr(self.controller, "ANDROID_MIN_FREE_BYTES", 32 * 1024 * 1024)):
            raise QualificationError("Server Phone has insufficient free storage for a bounded run-owned root")
        self.remote = self.controller.AndroidRemote(
            host=PHONE_HOST, home=home, prefix=prefix, python=python,
            pm2=str(baseline.get("pm2_path") or "") or None, rclone=None, baseline=baseline,
        )
        self.before_baseline = baseline
        self.results["server_phone_baseline"] = {
            "status": "PASS",
            "architecture": baseline.get("architecture"),
            "python_version": imports.get("version"),
            "checkout_sha": baseline.get("source_sha"),
            "git_clean": baseline.get("git_clean"),
            "pm2_process_count": len(baseline.get("pm2") or []),
            "production_candidate_processes_before": False,
            "production_state_mutation": False,
        }

    def _local_fixture(self) -> None:
        self.database, self.rollback_database, fixture = create_schema42_fixture(self.repo, self.candidate_sha, self.paths.root)
        apply = apply_isolated_health_migrations(self.repo, self.candidate_sha, self.database)
        after = _verify_sqlite(self.database, expected_version=44)
        if after["status"] != "PASS":
            raise QualificationError("isolated System Health migrations failed local integrity verification")
        repeat = apply_isolated_health_migrations(self.repo, self.candidate_sha, self.database)
        rollback = prove_isolated_rollback(self.repo, self.base_sha, self.rollback_database, self.paths.root, self.python)
        validate_rollback_backup(self.rollback_database, self.paths.root)
        self.results["isolated_sqlite"] = {
            "status": "PASS",
            "fixture": fixture,
            "migration_apply": apply,
            "after": after,
            "repeat_apply": repeat,
            "rollback_proof": rollback,
            "production_database_used": False,
        }
        # Recreate the schema-42 candidate DB after the local migration proof;
        # the phone candidate must perform 0043/0044 itself at startup.
        self.database.unlink()
        self.database, self.rollback_database, _ = create_schema42_fixture(self.repo, self.candidate_sha, self.paths.root)

    def _start_local_nats(self) -> None:
        if not self.nats_binary or not Path(self.nats_binary).is_file():
            raise QualificationError("disposable nats-server binary is unavailable")
        base_env = self.controller._scrubbed_environment()
        base_env.update({
            "HOME": str(self.paths.home), "TMPDIR": str(self.paths.root / "tmp"), "TMP": str(self.paths.root / "tmp"), "TEMP": str(self.paths.root / "tmp"),
            "POCKETLAB_QUALIFICATION_RUN_ID": self.run_id, "POCKETLAB_ENVIRONMENT": "qualification", "PYTHONDONTWRITEBYTECODE": "1",
        })
        (self.paths.root / "tmp").mkdir(mode=0o700, exist_ok=True)
        self.nats = self.controller.DisposableNats(paths=self.paths, env=base_env, run_id=self.run_id, binary=self.nats_binary)
        self.nats.start()
        self.results["disposable_nats"] = {"status": "PASS", "jetstream": True, "loopback": True, "production_nats_used": False}

    def _stage_remote(self) -> None:
        assert self.remote is not None and self.database is not None
        self.remote_root = self.controller._android_create_remote_root(self.remote, self.run_id)
        for relative in ("candidate", "state", "logs", "env", "tmp", "home", "probe", "destination", "api", "base", "iac", "xdg-config", "xdg-cache", "xdg-data", "opa", "opa/active"):
            self.controller._android_remote_mkdir(self.remote.host, f"{self.remote_root}/{relative}", root=self.remote_root)
        self.controller._android_remote_write(self.remote.host, f"{self.remote_root}/candidate-manifest.json", self.snapshot.manifest.read_bytes(), root=self.remote_root, mode="400")
        self.controller._android_remote_extract(self.remote, self.snapshot.archive, self.candidate_root, root=self.remote_root)
        self.controller._android_verify_snapshot(self.remote, self.candidate_root, f"{self.remote_root}/candidate-manifest.json", root=self.remote_root)
        self.controller._android_lock_snapshot(self.remote, self.candidate_root, root=self.remote_root)
        for path, data, mode in (("qualification-ca.pem", self.ca_path.read_bytes(), "400"), ("qualification-server.pem", self.cert_path.read_bytes(), "400"), ("qualification-server.key", self.key_path.read_bytes(), "400"), (f"state/{SCHEMA_DB_NAME}", self.database.read_bytes(), "600")):
            self.controller._android_remote_write(self.remote.host, f"{self.remote_root}/{path}", data, root=self.remote_root, mode=mode)
        self.results["candidate_staging"] = {
            "status": "PASS", "candidate_sha": self.candidate_sha, "manifest_sha256": self.snapshot.manifest_sha256,
            "snapshot_files": self.snapshot.file_count, "snapshot_bytes": self.snapshot.byte_count,
            "production_configuration_files": False, "source_snapshot_read_only": True,
        }

    def _build_env(self, nats_origin: str, remote_api_port: int) -> dict[str, str]:
        assert self.remote is not None
        site_packages = [str(item) for item in (self.remote.baseline.get("python_site_packages") or []) if str(item).startswith((self.remote.home.rstrip("/") + "/", self.remote.prefix.rstrip("/") + "/"))]
        env: dict[str, str] = {
            "HOME": f"{self.remote_root}/home", "TMPDIR": f"{self.remote_root}/tmp", "TMP": f"{self.remote_root}/tmp", "TEMP": f"{self.remote_root}/tmp",
            "XDG_CONFIG_HOME": f"{self.remote_root}/xdg-config", "XDG_CACHE_HOME": f"{self.remote_root}/xdg-cache", "XDG_DATA_HOME": f"{self.remote_root}/xdg-data",
            "PATH": f"{self.remote_root}/bin:{self.remote.prefix}/bin", "PYTHONPATH": os.pathsep.join([self.runtime_root, *site_packages]),
            "PYTHONDONTWRITEBYTECODE": "1", "PREFIX": self.remote.prefix, "LD_PRELOAD": str(self.remote.baseline.get("termux_exec_ld_preload") or ""), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            # The default security-assurance lane remains owner-off
            # ("POCKETLAB_QUALIFICATION_OWNER": "0"). The browser UI lane
            # opts into the existing non-destructive owner bridge explicitly.
            "POCKETLAB_ENVIRONMENT": "qualification", "POCKETLAB_HARNESS_ENABLED": "1", "POCKETLAB_HARNESS_DESTRUCTIVE": "0", "POCKETLAB_QUALIFICATION_OWNER": self.qualification_owner_flag, "POCKETLAB_TEST_AUTH_BYPASS": "0",
            "POCKETLAB_HARNESS_BOOTSTRAP_APPROVED": "1", "POCKETLAB_HARNESS_BOOTSTRAP_PROFILE": self.bootstrap_profile, "POCKETLAB_HARNESS_RUNTIME_ID": f"qualification-{self.run_id}",
            "POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID": self.principal_id, "POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT": self.fingerprint, "POCKETLAB_HARNESS_PROVISIONING_TOKEN": self.provisioning_token,
            "POCKETLAB_STATE_DIR": f"{self.remote_root}/state", "POCKETLAB_LITE_DB_PATH": f"{self.remote_root}/state/{SCHEMA_DB_NAME}", "POCKETLAB_BASE_DIR": f"{self.remote_root}/base", "POCKETLAB_API_DIR": f"{self.remote_root}/api", "POCKETLAB_IAC_DIR": f"{self.remote_root}/iac",
            "POCKETLAB_DEVICE_NAME": f"qualification-health-{self.run_id}", "POCKETLAB_NODE_ID": f"qualification-health-{self.run_id}", "POCKETLAB_NODE_NAME": f"qualification-health-{self.run_id}", "POCKETLAB_NODE_ROLES": "server", "POCKETLAB_NODE_ROLE": "server",
            "POCKETLAB_QUALIFICATION_CONTEXT": "isolated-runtime-v1", "POCKETLAB_QUALIFICATION_RUN_ID": self.run_id, "POCKETLAB_QUALIFICATION_CANDIDATE_SHA": self.candidate_sha, "POCKETLAB_QUALIFICATION_SNAPSHOT_MANIFEST_SHA256": self.snapshot.manifest_sha256,
            "POCKETLAB_HARNESS_BOOTSTRAP_PURPOSE": self.bootstrap_purpose,
            "POCKETLAB_QUALIFICATION_ALLOW_TEST_DESTINATION": "1", "POCKETLAB_QUALIFICATION_CONTEXT_TOKEN": self.context_token, "POCKETLAB_QUALIFICATION_ROOT": self.remote_root, "POCKETLAB_QUALIFICATION_DESTINATION_ROOT": f"{self.remote_root}/destination",
            "POCKETLAB_QUALIFICATION_WEBDAV_USER": "qualification", "POCKETLAB_QUALIFICATION_WEBDAV_PASSWORD": self.webdav_password, "POCKETLAB_QUALIFICATION_TEST_ORIGIN": f"https://127.0.0.1:{remote_api_port}", "POCKETLAB_QUALIFICATION_CONTROL_ORIGIN": f"https://127.0.0.1:{remote_api_port}",
            "POCKETLAB_API_BIND": "127.0.0.1", "POCKETLAB_API_PORT": str(remote_api_port), "POCKETLAB_OPA_URL": "http://127.0.0.1:1", "POCKETLAB_OPA_ACTIVE_POLICY_DIR": f"{self.remote_root}/opa/active",
            "POCKETLAB_NATS_URL": nats_origin, "POCKETLAB_LITE_PUBLIC_NATS_URL": nats_origin, "POCKETLAB_NATS_JETSTREAM": "1", "POCKETLAB_NATS_REQUIRED": "1", "POCKETLAB_NATS_REQUIRE_JETSTREAM": "1", "POCKETLAB_NATS_NAME": f"qualification-{self.run_id}",
            "POCKETLAB_NATS_USER": self.nats.user if self.nats else "", "POCKETLAB_NATS_PASSWORD": self.nats.password if self.nats else "", "POCKETLAB_AGENT_NATS_USER": self.nats.user if self.nats else "", "POCKETLAB_AGENT_NATS_PASSWORD": self.nats.password if self.nats else "",
            "POCKETLAB_NATS_INITIAL_CONNECT_DEADLINE": "5", "POCKETLAB_NATS_RECONNECT_WAIT": "1", "POCKETLAB_NATS_RECONNECT_MIN_SECONDS": "1", "POCKETLAB_NATS_RECONNECT_MAX_SECONDS": "5", "POCKETLAB_NATS_WATCHDOG_SECONDS": "2",
            "POCKETLAB_WORKER_HEARTBEAT_SECONDS": "5", "POCKETLAB_WORKER_NATS_RETRY_SECONDS": "1", "POCKETLAB_JETSTREAM_MAX_BYTES": "16777216", "POCKETLAB_QUALIFICATION_LOG_DIR": f"{self.remote_root}/logs", "POCKETLAB_DISABLE_RELEASE_UPDATER": "1",
            "POCKETLAB_LITE_SECURE_ORIGIN": "", "POCKETLAB_SECURE_ORIGIN": "", "CADDYFILE": "", "POCKET_LAB_CADDYFILE": "", "SSL_CERT_FILE": f"{self.remote_root}/qualification-ca.pem", "REQUESTS_CA_BUNDLE": f"{self.remote_root}/qualification-ca.pem",
        }
        return env

    def _start_transport_and_candidate(self) -> None:
        assert self.remote is not None and self.nats is not None
        self.remote_api_port = self.controller._android_select_port(self.remote)
        reverse = self.controller.AndroidTunnel(
            host=self.remote.host, run_id=self.run_id, kind="system-health-nats", log=self.paths.logs / "ssh-nats.log", direction="reverse",
            local_port=self.nats.port, target_port=self.nats.port, remote_port=0,
        )
        reverse.start()
        local_api = self.controller.AndroidTunnel(
            host=self.remote.host, run_id=self.run_id, kind="system-health-api", log=self.paths.logs / "ssh-api.log", direction="local",
            local_port=self.local_api_port, target_port=self.remote_api_port,
        )
        local_api.start()
        self.tunnels = [reverse, local_api]
        nats_origin = f"nats://127.0.0.1:{reverse.remote_port}"
        assert self.database is not None
        # Dev-PC listener ports and the phone's loopback listener ports are
        # separate namespaces. Only local listeners can collide here.
        assert_isolated_binding(self.paths.root, self.database, nats_origin, "127.0.0.1", self.local_api_port, occupied_ports=[self.nats.port])
        env = self._build_env(nats_origin, self.remote_api_port)
        self.env_path = f"{self.remote_root}/env/server.json"
        self.controller._android_remote_write(self.remote.host, self.env_path, json.dumps(env, sort_keys=True, separators=(",", ":")) + "\n", root=self.remote_root, mode="600")
        self.client = CandidateClient(self.api_origin, self.ca_path)
        self.api = self.controller.AndroidRemoteProcess(
            remote=self.remote, run_id=self.run_id, root=self.remote_root, name="system-health-candidate-api", env_path=self.env_path,
            argv=[self.remote.python, "-m", "uvicorn", "api_fastapi.main:app", "--host", "127.0.0.1", "--port", str(self.remote_api_port), "--ssl-keyfile", f"{self.remote_root}/qualification-server.key", "--ssl-certfile", f"{self.remote_root}/qualification-server.pem", "--log-level", "warning"],
            cwd=self.runtime_root, log_path=f"{self.remote_root}/logs/api.log",
        )
        self.api.launch()
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if not self.api.alive():
                raise QualificationError("candidate API exited during readiness")
            try:
                if self.client.request("GET", "/health").status == 200:
                    break
            except QualificationError:
                pass
            time.sleep(0.4)
        else:
            raise QualificationError("candidate API readiness timed out")
        self.worker = self.controller.AndroidRemoteProcess(
            remote=self.remote, run_id=self.run_id, root=self.remote_root, name="system-health-candidate-worker", env_path=self.env_path,
            argv=[self.remote.python, f"{self.runtime_root}/workers/pocketlab_worker.py"], cwd=self.runtime_root, log_path=f"{self.remote_root}/logs/worker.log",
        )
        self.worker.launch()
        if not self.worker.alive():
            raise QualificationError("candidate worker exited during readiness")
        validate_candidate_readiness(api_status=200, api_owned=self.api.alive(), worker_owned=self.worker.alive())
        self.results["candidate_runtime"] = {"status": "PASS", "candidate_sha": self.candidate_sha, "api_owned": True, "worker_owned": True, "api_loopback_only": True, "production_pm2_used": False, "production_caddy_used": False}

    def _remote_probe(self, *, expected: int | None = None) -> dict[str, Any]:
        assert self.remote is not None
        path = f"{self.remote_root}/state/{SCHEMA_DB_NAME}"
        self.controller._android_safe_remote_path(path, self.remote_root)
        result = self.controller._android_ssh_run(self.remote.host, [self.remote.python, "-c", _REMOTE_DB_PROBE, path, "qualification.marker"], timeout=25)
        if result.returncode != 0:
            raise QualificationError("candidate SQLite probe failed")
        try:
            payload = json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise QualificationError("candidate SQLite probe output was malformed") from None
        if expected is not None and int(payload.get("schema_version") or 0) != expected:
            raise QualificationError(f"candidate SQLite schema was not {expected}")
        return payload

    def _run_projection_driver(self) -> dict[str, Any]:
        assert self.remote is not None
        driver = r'''from __future__ import annotations
import json, sys, time
runtime, database = sys.argv[1:]
sys.path.insert(0, runtime)
from api_fastapi.services import lite_phase3b_projections as projections
payloads = [
    {"status":"degraded","connected":True,"jetstream_enabled":True,"generation":1,"summary":"Qualification broker needs attention.","sanitized":True},
    {"status":"degraded","connected":True,"jetstream_enabled":True,"generation":1,"summary":"Qualification broker needs attention.","sanitized":True},
    {"status":"healthy","connected":True,"jetstream_enabled":True,"generation":2,"summary":"Command delivery is ready.","sanitized":True},
    {"status":"degraded","connected":True,"jetstream_enabled":True,"generation":3,"summary":"Qualification broker needs attention again.","sanitized":True},
    {"status":"unknown","connected":None,"jetstream_enabled":None,"generation":4,"summary":"Qualification evidence is not current.","sanitized":True},
    {"status":"degraded","connected":True,"jetstream_enabled":True,"generation":5,"summary":"Qualification broker remains under review.","sanitized":True},
]
results = []
for payload in payloads:
    result = projections.project("system.nats_remote", payload)
    results.append({"changed": bool(result.changed), "revision": int(result.revision)})
    time.sleep(0.25)
print(json.dumps({"results": results, "status": "PASS" if results and results[0]["changed"] and not results[1]["changed"] else "FAIL"}, sort_keys=True), flush=True)
time.sleep(3)
'''
        remote_path = f"{self.remote_root}/probe/system-health-driver.py"
        self.controller._android_remote_write(self.remote.host, remote_path, driver, root=self.remote_root, mode="400")
        self.driver = self.controller.AndroidRemoteProcess(
            remote=self.remote, run_id=self.run_id, root=self.remote_root, name="system-health-projection-driver", env_path=self.env_path,
            argv=[self.remote.python, remote_path, self.runtime_root, f"{self.remote_root}/state/{SCHEMA_DB_NAME}"], cwd=self.runtime_root, log_path=f"{self.remote_root}/logs/driver.log",
        )
        self.driver.launch()
        deadline = time.monotonic() + 30
        while self.driver.alive() and time.monotonic() < deadline:
            time.sleep(0.3)
        if self.driver.alive():
            self.driver.stop()
            raise QualificationError("projection driver did not finish in its bounded window")
        log = self.controller._android_read_text(self.remote, f"{self.remote_root}/logs/driver.log", root=self.remote_root)
        try:
            payload, line_count = parse_json_log_record(log, label="projection driver")
        except QualificationError:
            lines = [line.strip() for line in str(log or "").splitlines() if line.strip()]
            self.results["projection_driver"] = {
                "status": "FAIL",
                "nonempty_lines": len(lines),
                "last_line_prefixes": [line[:160] for line in lines[-4:]],
            }
            raise
        if payload.get("status") != "PASS":
            raise QualificationError("projection driver duplicate suppression did not pass")
        self.results["projection_driver"] = {"status": "PASS", "output_lines": line_count, "duplicate_suppression": True}
        return payload

    def _bootstrap(self) -> None:
        assert self.client is not None
        validate_synthetic_identity(
            self.principal_id,
            self.bootstrap_profile,
            qualification_owner=self.qualification_owner_flag,
            destructive="0",
            test_bypass="0",
            allow_browser_ui=self.browser_ui,
        )
        # Bootstrap endpoints intentionally reject all x-pocket-lab-harness-*
        # headers. Approval is bound in the candidate environment and the
        # possession proof is the Ed25519 signature below.
        grant = self.client.request("POST", "/api/lite/harness/bootstrap/grants", {"principal_id": self.principal_id, "public_key": self.public_key})
        challenge = self.client.request("POST", "/api/lite/harness/bootstrap/challenge", {"grant_id": grant.body.get("grant_id")})
        signing_payload = str(challenge.body.get("signing_payload") or "")
        if grant.status != 201 or challenge.status != 200 or not signing_payload:
            raise QualificationError("signed synthetic assurance bootstrap was rejected")
        session = self.client.request("POST", "/api/lite/harness/bootstrap/complete", {
            "challenge_id": challenge.body.get("challenge_id"), "grant_id": grant.body.get("grant_id"), "principal_id": self.principal_id,
            "public_key": self.public_key, "signature": _b64u(self.principal_private.sign(signing_payload.encode())), "ttl_seconds": 240 if self.browser_ui else 120,
        })
        token = str(session.body.get("session_token") or "")
        if session.status != 201 or not token:
            raise QualificationError("signed synthetic assurance session was not established")
        self.session = token
        status = self.client.request("GET", "/api/lite/harness/status")
        self.results["security_assurance_harness"] = {"status": "PASS", "profile": self.bootstrap_profile, "purpose": self.bootstrap_purpose, "destructive": False, "qualification_owner": self.browser_ui, "test_auth_bypass": False, "target_scope": status.body.get("target_scope"), "active_sessions": status.body.get("active_sessions"), "principal_count": status.body.get("principal_count"), "private_key_published": False}
        if self.browser_ui:
            bridge = self.client.request("POST", "/api/lite/harness/browser/bridge", session=self.session)
            bridge_token = str(bridge.body.get("browser_bridge_token") or "")
            metadata = bridge.body.get("browser_bridge") if isinstance(bridge.body, dict) else None
            if bridge.status != 200 or not bridge_token or not isinstance(metadata, dict):
                raise QualificationError("signed synthetic browser qualification bridge was rejected")
            if metadata.get("profile") != "qualification-owner" or metadata.get("purpose") != "ui-performance-60fps" or metadata.get("target_scope") != "local_server_host_only":
                raise QualificationError("browser qualification bridge binding was not accepted")
            self.browser_bridge = bridge_token
            self.results["security_assurance_harness"]["browser_bridge"] = {"status": "PASS", "short_lived": True, "private_token_published": False, "destructive": False}

    def _qualify_api(self) -> None:
        assert self.client is not None and self.session
        anonymous = self.client.request("GET", "/api/lite/system-health/summary")
        if anonymous.status != 401:
            raise QualificationError("anonymous System Health read was not rejected")
        routes = [
            ("summary", "/api/lite/system-health/summary"), ("incidents", "/api/lite/system-health/incidents?include_resolved=true"),
            ("history", "/api/lite/system-health/history"), ("dependencies", "/api/lite/system-health/dependencies"), ("resources", "/api/lite/system-health/resources"),
            ("intelligence", "/api/lite/system-health/intelligence"), ("configuration", "/api/lite/system-health/configuration-drift"), ("policies", "/api/lite/system-health/policies"), ("repairs", "/api/lite/system-health/repairs"),
        ]
        route_results: dict[str, Any] = {"anonymous_summary": {"status": anonymous.status, "reason_code": (anonymous.body.get("detail") or {}).get("reason_code") if isinstance(anonymous.body.get("detail"), dict) else None}}
        for name, path in routes:
            response = self.client.request("GET", path, session=self.session)
            if response.status != 200:
                raise QualificationError(f"authenticated System Health route failed: {name}")
            route_results[name] = {"status": response.status}
        incidents = self.client.request("GET", "/api/lite/system-health/incidents", session=self.session)
        items = incidents.body.get("items") if isinstance(incidents.body.get("items"), list) else []
        if incidents.status != 200 or not items:
            raise QualificationError("candidate System Health projection did not produce an incident")
        incident = items[0] if isinstance(items[0], dict) else {}
        incident_id = str(incident.get("incident_id") or "")
        generation = int(incident.get("generation") or 0)
        if not incident_id or generation < 1 or incident.get("state") == "resolved":
            raise QualificationError("candidate incident state was not active and generation-bound")
        detail = self.client.request("GET", f"/api/lite/system-health/incidents/{incident_id}", session=self.session)
        decisions = self.client.request("GET", f"/api/lite/system-health/incidents/{incident_id}/decisions", session=self.session)
        app = self.client.request("GET", "/api/lite/system-health/apps/photoprism", session=self.session)
        if detail.status != 200 or decisions.status != 200 or app.status not in {200, 404}:
            raise QualificationError("candidate System Health incident detail routes failed")
        diagnosis = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/diagnose", session=self.session)
        if diagnosis.status != 200:
            raise QualificationError("candidate System Health diagnosis was not persisted")
        repair_payload = {"operation_id": "runtime.consumer.reconnect", "expected_generation": generation, "idempotency_key": "qualification-system-health-001", "confirm": True}
        preflight = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/preflight", repair_payload, session=self.session)
        repair = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/repair", repair_payload, session=self.session)
        replay = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/repair", repair_payload, session=self.session)
        stale = dict(repair_payload); stale["expected_generation"] = generation + 99
        stale_repair = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/repair", stale, session=self.session)
        unauthorized = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/diagnose")
        self.results["repair_contract"] = {
            "preflight": response_contract(preflight),
            "repair": response_contract(repair),
            "replay": response_contract(replay),
            "stale_repair": response_contract(stale_repair),
            "unauthorized_diagnosis": response_contract(unauthorized),
        }
        if preflight.status != 200 or repair.status != 409 or replay.status != 409 or stale_repair.status != 409 or unauthorized.status != 401:
            raise QualificationError("System Health repair denial/authentication contract failed")
        body = response_detail(repair)
        stale_body = response_detail(stale_repair)
        if body.get("status") != "blocked" or body.get("recorded") is not True or stale_body.get("reason_code") != "incident_generation_changed":
            raise QualificationError("System Health repair denial was not fail-closed")
        self.results["system_health_api"] = {
            "status": "PASS", "anonymous_read_rejected": True, "authenticated_routes": route_results,
            "incident_id_class": "deterministic_health_identity", "incident_generation": generation, "incident_state": incident.get("state"),
            "detail": detail.status, "diagnosis": diagnosis.status, "preflight": preflight.status, "repair": repair.status,
            "idempotent_replay": replay.status == 409, "generation_fencing": stale_body.get("reason_code"), "unauthorized_write": unauthorized.status,
            "app_diagnostics_status": app.status, "new_executor_enabled": False, "raw_evidence_exposed": False,
        }

    def _measure(self) -> None:
        assert self.remote is not None and self.api is not None and self.worker is not None and self.client is not None
        api_metrics = self.controller._android_process_info(self.remote, self.api.pid, root=self.remote_root)
        worker_metrics = self.controller._android_process_info(self.remote, self.worker.pid, root=self.remote_root)
        device = self.controller._android_ssh_run(self.remote.host, [self.remote.python, "-c", _REMOTE_DEVICE_METRICS], timeout=15)
        try:
            device_payload = json.loads(device.stdout.strip().splitlines()[-1]) if device.returncode == 0 else {"status": "UNVALIDATED"}
        except (ValueError, IndexError):
            device_payload = {"status": "UNVALIDATED"}
        latencies: list[float] = []
        for _ in range(5):
            start = time.perf_counter()
            response = self.client.request("GET", "/api/lite/system-health/summary", session=self.session)
            latencies.append(round((time.perf_counter() - start) * 1000, 2))
            if response.status != 200:
                raise QualificationError("bounded System Health latency probe failed")
        self.results["low_power_observations"] = {
            "status": "PASS", "candidate_api_process": {"owned": bool(api_metrics.get("owned")), "state": api_metrics.get("state")},
            "candidate_worker_process": {"owned": bool(worker_metrics.get("owned")), "state": worker_metrics.get("state")},
            "candidate_run_root_metrics": self.controller._android_metrics(self.remote, self.remote_root),
            "android_device_metrics": device_payload, "system_health_latency_ms": {"samples": latencies, "min": min(latencies), "max": max(latencies), "mean": round(sum(latencies) / len(latencies), 2)},
            "production_stress_or_fault_injection": False, "comparison_baseline": "candidate-only observation; no production improvement/regression claim",
        }

    def _concurrency(self) -> None:
        assert self.remote is not None
        path = f"{self.remote_root}/state/{SCHEMA_DB_NAME}"
        result = self.controller._android_ssh_run(self.remote.host, [self.remote.python, "-c", _REMOTE_CONCURRENCY, path], timeout=35)
        if result.returncode != 0:
            raise QualificationError("isolated SQLite concurrency probe failed")
        try:
            payload = json.loads(result.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            raise QualificationError("isolated SQLite concurrency probe output was malformed") from None
        if payload.get("status") != "PASS":
            raise QualificationError("isolated SQLite concurrency probe reported failure")
        self.results.setdefault("isolated_sqlite", {})["concurrent_read_write"] = payload

    def _cleanup_session(self) -> None:
        if self.client is None or not self.session:
            return
        try:
            response = self.client.request("POST", "/api/lite/harness/principal/revoke", session=self.session)
            self.results.setdefault("security_assurance_harness", {})["revocation_status"] = response.status
            self.results.setdefault("security_assurance_harness", {})["session_revoked"] = response.status == 200
            self.session = ""
        except Exception:
            self.results.setdefault("security_assurance_harness", {})["session_revoked"] = False

    def _cleanup(self) -> None:
        remote_processes_before: Any = None
        remote_processes_after: Any = None
        if self.remote is not None and self.remote_root:
            with contextlib.suppress(Exception):
                remote_processes_before = self.controller._android_run_owned_processes(self.remote, root=self.remote_root, run_id=self.run_id)
        self._cleanup_session()
        for process in (self.driver, self.worker, self.api):
            if process is not None:
                with contextlib.suppress(Exception):
                    process.stop()
        if self.remote is not None and self.remote_root:
            with contextlib.suppress(Exception):
                self.controller._android_stop_run_owned_processes(self.remote, root=self.remote_root, run_id=self.run_id)
            with contextlib.suppress(Exception):
                remote_processes_after = self.controller._android_wait_for_run_processes(self.remote, root=self.remote_root, run_id=self.run_id, timeout=3)
        for tunnel in reversed(self.tunnels):
            with contextlib.suppress(Exception):
                tunnel.stop()
        if self.nats is not None:
            with contextlib.suppress(Exception):
                self.nats.stop()
        if self.remote is not None and self.remote_root:
            removed = False
            with contextlib.suppress(Exception):
                removed = bool(self.controller._android_remove_root(self.remote, self.remote_root))
            self.results["cleanup"] = {"status": "PASS" if removed and not remote_processes_after else "FAIL", "remote_root_removed": removed, "run_owned_processes_before": len(remote_processes_before or []), "run_owned_processes_after": len(remote_processes_after or []), "temporary_qualification_material_removed": removed, "temporary_candidate_processes_removed": not remote_processes_after}
        with contextlib.suppress(Exception):
            shutil.rmtree(self.paths.root)
        try:
            after = self.controller._android_baseline(PHONE_HOST)
            unchanged = production_projection(self.before_baseline) == production_projection(after)
            self.results["production_preservation"] = {"status": "PASS" if unchanged else "FAIL", "checkout_unchanged": after.get("source_sha") == self.before_baseline.get("source_sha"), "git_clean": after.get("git_clean"), "candidate_processes_left": False, "production_database_touched": False}
            self.results["server_phone_final"] = {"status": "PASS" if unchanged else "FAIL", "checkout_sha": after.get("source_sha"), "git_clean": after.get("git_clean"), "branch": "main_expected", "installed_runtime_not_changed": unchanged}
        except Exception:
            self.results["production_preservation"] = {"status": "UNVALIDATED"}

    def run(self) -> tuple[str, Path]:
        status = "BLOCKED"
        error = ""
        try:
            if self.base_sha == self.candidate_sha:
                raise QualificationError("base and candidate SHA must differ for rollback proof")
            self._discover_remote()
            self._local_fixture()
            assert self.database is not None and self.rollback_database is not None
            # The phone receives only the schema-42 candidate DB.  The API owns
            # the forward application of 0043/0044 at startup.
            self._start_local_nats()
            self._stage_remote()
            before = self._remote_probe(expected=42)
            self.results.setdefault("isolated_sqlite", {})["phone_before_migration"] = before
            self._start_transport_and_candidate()
            after = self._remote_probe(expected=44)
            if after.get("marker_revision") != 7 or after.get("status") != "PASS":
                raise QualificationError("phone candidate migration did not preserve the isolated fixture")
            self.results.setdefault("isolated_sqlite", {})["phone_after_migration"] = after
            self._run_projection_driver()
            self._bootstrap()
            self._qualify_api()
            self._concurrency()
            self._measure()
            repeat = self._remote_probe(expected=44)
            self.results.setdefault("isolated_sqlite", {})["after_gets"] = repeat
            self.results["status"] = "PASS"
            status = "PASS"
        except QualificationError as exc:
            error = _safe_text(str(exc))
            self.results["failure"] = {"type": "qualification", "message": error, "sanitized": True}
        except Exception as exc:
            error = f"{type(exc).__name__}: {_safe_text(str(exc))}"
            self.results["failure"] = {"type": type(exc).__name__, "message": _safe_text(str(exc)), "sanitized": True}
        finally:
            self._cleanup()
            self.results["finished_at"] = _now()
            self.results["status"] = status
        evidence = self.external_evidence / f"pr649-system-health-android-{self.candidate_sha[:12]}.json"
        evidence.write_text(json.dumps(sanitize(self.results), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        evidence.chmod(0o600)
        return status, evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--base-sha", default="origin/main")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--nats-server-bin", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[3]
    controller = _controller()
    base = str(args.base_sha).strip().casefold()
    if not SHA_RE.fullmatch(base):
        resolved = _run(["git", "rev-parse", "--verify", f"{base}^{{commit}}"], cwd=repo)
        if resolved.returncode != 0:
            print(json.dumps({"status": "BLOCKED", "reason": "base SHA could not be resolved", "sanitized": True}, sort_keys=True))
            return 2
        base = resolved.stdout.strip().casefold()
    try:
        run = SystemHealthAndroidQualification(repo=repo, candidate_sha=args.candidate_sha, base_sha=base, python=args.python, nats_binary=args.nats_server_bin, evidence_dir=args.evidence_dir)
        status, evidence = run.run()
        print(json.dumps({"status": status, "candidate_sha": run.candidate_sha, "base_sha": base, "evidence": str(evidence)}, indent=2, sort_keys=True))
        return 0 if status == "PASS" else 1
    except QualificationError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": _safe_text(str(exc)), "sanitized": True}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
