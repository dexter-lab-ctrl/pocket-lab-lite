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


_REMOTE_RECOVERY_PROBE = r'''import json, sqlite3, sys
path = sys.argv[1]
conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row
def bounded(row):
    return {key: row[key] for key in row.keys() if key in {
        "request_id", "incident_id", "target_type", "target_id", "status", "execution_state", "verification_state",
        "attempt", "max_attempts", "outcome", "terminal_reason", "safe_summary",
        "before_evidence_json", "after_evidence_json", "updated_at", "completed_at",
    }}
requests = [bounded(row) for row in conn.execute(
    "SELECT * FROM lite_system_health_recovery_requests ORDER BY requested_at DESC LIMIT 8"
)]
events = [
    {key: row[key] for key in row.keys() if key in {"incident_id", "generation", "event_type", "created_at", "safe_summary"}}
    for row in conn.execute(
        "SELECT incident_id,generation,event_type,created_at,safe_summary FROM lite_system_health_events ORDER BY id DESC LIMIT 20"
    )
]
print(json.dumps({"requests": requests, "events": events}, sort_keys=True, separators=(",", ":")))
'''


_REMOTE_RECOVERY_FIXTURE = r'''import json, sqlite3, sys, time
runtime, database, deadline = sys.argv[1:]
sys.path.insert(0, runtime)
from api_fastapi.services import lite_phase3b_projections as projections

degraded = {
    "status": "degraded",
    "connected": True,
    "jetstream_enabled": True,
    "durable_consumer_health": {
        "pocketlab_command_worker_v1": {
            "healthy": False,
            "generation": 1,
            "recoveries": 0,
            "task_alive": False,
            "subscription_present": False,
            "callback_inflight": False,
        }
    },
    "generation": 9001,
    "summary": "Qualification recovery target needs attention.",
    "sanitized": True,
}
healthy = {
    **degraded,
    "status": "healthy",
    "durable_consumer_health": {
        "pocketlab_command_worker_v1": {
            "healthy": True,
            "generation": 2,
            "recoveries": 1,
            "task_alive": True,
            "subscription_present": True,
            "callback_inflight": False,
        }
    },
    "generation": 9002,
    "summary": "Qualification recovery target is healthy.",
}
terminal = {"verified", "execution_failed", "verification_failed", "verification_unavailable", "manual_attention_required", "blocked", "expired", "cancelled"}
conn = sqlite3.connect(database)
try:
    baseline_request_ids = {str(row[0]) for row in conn.execute(
        "SELECT request_id FROM lite_system_health_recovery_requests"
    ).fetchall() if row and row[0]}
finally:
    conn.close()
started = time.monotonic()
while time.monotonic() < float(deadline):
    projections.project("system.nats_remote", degraded)
    conn = sqlite3.connect(database)
    try:
        row = conn.execute(
            "SELECT request_id,status FROM lite_system_health_recovery_requests ORDER BY requested_at DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if row and str(row[0] or "") not in baseline_request_ids and str(row[1] or "") in terminal:
        projections.project("system.nats_remote", healthy)
        print(json.dumps({"status": "PASS", "request_status": str(row[1]), "bounded": True}, sort_keys=True), flush=True)
        raise SystemExit(0)
    time.sleep(0.25)
print(json.dumps({"status": "TIMEOUT", "bounded": True, "elapsed_seconds": round(time.monotonic() - started, 2)}, sort_keys=True), flush=True)
raise SystemExit(1)
'''


_REMOTE_NATS_INCIDENT_READY_PROBE = r'''import json, sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
try:
    count = conn.execute(
        "SELECT COUNT(*) FROM lite_system_health_incidents WHERE source='nats' AND state != 'resolved'"
    ).fetchone()[0]
finally:
    conn.close()
print(json.dumps({"active_nats_incidents": int(count)}, sort_keys=True))
'''


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
    all_migrations = _candidate_migrations(repo, candidate_sha)
    migrations = [item for item in all_migrations if item[0] >= 43]
    versions = [item[0] for item in migrations]
    if not versions or versions != list(range(43, versions[-1] + 1)):
        raise QualificationError("candidate forward migration chain after schema 42 is incomplete")
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
        candidate_migrations = _candidate_migrations(repo, self.candidate_sha)
        if not candidate_migrations:
            raise QualificationError("candidate migration inventory is empty")
        self.candidate_schema_version = max(item[0] for item in candidate_migrations)
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
        self.opa: Any | None = None
        self.remote: Any | None = None
        self.remote_root = ""
        self.remote_api_port = 0
        self.api: Any | None = None
        self.worker: Any | None = None
        self.nats_tunnel: Any | None = None
        self.driver: Any | None = None
        self.recovery_fixture: Any | None = None
        self.tunnels: list[Any] = []
        self.opa_policy_path: Path | None = None
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
        after = _verify_sqlite(self.database, expected_version=self.candidate_schema_version)
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
        # the phone candidate must perform the complete forward chain itself at
        # startup, including generation and recovery-request migrations.
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

    def _start_local_opa(self) -> None:
        """Run the exact candidate policy on an isolated Dev-PC loopback port."""
        binary = shutil.which("opa")
        if not binary:
            raise QualificationError("opa is unavailable; no production policy endpoint fallback is permitted")
        policy_source = self.paths.root / "candidate-opa.rego"
        shown = _run(
            ["git", "show", f"{self.candidate_sha}:security/policies/opa/pocketlab/pocketlab.rego"],
            cwd=self.repo,
            timeout=30,
        )
        if shown.returncode != 0 or not shown.stdout.strip():
            raise QualificationError("candidate OPA policy source could not be read")
        policy_source.write_text(shown.stdout, encoding="utf-8")
        policy_source.chmod(0o600)
        base_env = self.controller._scrubbed_environment()
        base_env.update({
            "HOME": str(self.paths.home),
            "TMPDIR": str(self.paths.root / "tmp"),
            "TMP": str(self.paths.root / "tmp"),
            "TEMP": str(self.paths.root / "tmp"),
            "POCKETLAB_QUALIFICATION_RUN_ID": self.run_id,
        })
        (self.paths.root / "tmp").mkdir(mode=0o700, parents=True, exist_ok=True)
        self.opa_policy_path = policy_source
        self.opa = self.controller.DisposableOpa(
            paths=self.paths,
            run_id=self.run_id,
            policy_source=policy_source,
            binary=binary,
        )
        while self.opa.port in {self.nats.port if self.nats is not None else 0, self.local_api_port}:
            self.opa.port = _port()
        self.opa.start(base_env=base_env)
        policy_revision = self.opa.revision_path.read_text(encoding="utf-8").strip()[:24]
        self.results["isolated_opa_policy"] = {
            "status": "PASS",
            "transport": "loopback_http_reverse_ssh",
            "candidate_policy_source": "exact_candidate_git_object",
            "policy_revision": policy_revision,
            "devpc_owned": True,
            "production_opa_used": False,
        }

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

    def _build_env(self, nats_origin: str, opa_origin: str, remote_api_port: int) -> dict[str, str]:
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
            # The adapter is enabled only inside this disposable qualification
            # candidate so the backend lane can exercise its fail-closed
            # denial contract. The security-assurance profile remains
            # non-owner and cannot execute recovery; the installed runtime and
            # production activation remain default-off.
            "POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER": "1",
            "POCKETLAB_HARNESS_BOOTSTRAP_APPROVED": "1", "POCKETLAB_HARNESS_BOOTSTRAP_PROFILE": self.bootstrap_profile, "POCKETLAB_HARNESS_RUNTIME_ID": f"qualification-{self.run_id}",
            "POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID": self.principal_id, "POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT": self.fingerprint, "POCKETLAB_HARNESS_PROVISIONING_TOKEN": self.provisioning_token,
            "POCKETLAB_STATE_DIR": f"{self.remote_root}/state", "POCKETLAB_LITE_DB_PATH": f"{self.remote_root}/state/{SCHEMA_DB_NAME}", "POCKETLAB_BASE_DIR": f"{self.remote_root}/base", "POCKETLAB_API_DIR": f"{self.remote_root}/api", "POCKETLAB_IAC_DIR": f"{self.remote_root}/iac",
            "POCKETLAB_DEVICE_NAME": f"qualification-health-{self.run_id}", "POCKETLAB_NODE_ID": f"qualification-health-{self.run_id}", "POCKETLAB_NODE_NAME": f"qualification-health-{self.run_id}", "POCKETLAB_NODE_ROLES": "server", "POCKETLAB_NODE_ROLE": "server",
            "POCKETLAB_QUALIFICATION_CONTEXT": "isolated-runtime-v1", "POCKETLAB_QUALIFICATION_RUN_ID": self.run_id, "POCKETLAB_QUALIFICATION_CANDIDATE_SHA": self.candidate_sha, "POCKETLAB_QUALIFICATION_SNAPSHOT_MANIFEST_SHA256": self.snapshot.manifest_sha256,
            "POCKETLAB_HARNESS_BOOTSTRAP_PURPOSE": self.bootstrap_purpose,
            "POCKETLAB_QUALIFICATION_ALLOW_TEST_DESTINATION": "1", "POCKETLAB_QUALIFICATION_CONTEXT_TOKEN": self.context_token, "POCKETLAB_QUALIFICATION_ROOT": self.remote_root, "POCKETLAB_QUALIFICATION_DESTINATION_ROOT": f"{self.remote_root}/destination",
            "POCKETLAB_QUALIFICATION_WEBDAV_USER": "qualification", "POCKETLAB_QUALIFICATION_WEBDAV_PASSWORD": self.webdav_password, "POCKETLAB_QUALIFICATION_TEST_ORIGIN": f"https://127.0.0.1:{remote_api_port}", "POCKETLAB_QUALIFICATION_CONTROL_ORIGIN": f"https://127.0.0.1:{remote_api_port}",
            "POCKETLAB_API_BIND": "127.0.0.1", "POCKETLAB_API_PORT": str(remote_api_port), "POCKETLAB_OPA_URL": opa_origin, "POCKETLAB_OPA_ACTIVE_POLICY_DIR": f"{self.remote_root}/opa/active",
            "POCKETLAB_NATS_URL": nats_origin, "POCKETLAB_LITE_PUBLIC_NATS_URL": nats_origin, "POCKETLAB_NATS_JETSTREAM": "1", "POCKETLAB_NATS_REQUIRED": "1", "POCKETLAB_NATS_REQUIRE_JETSTREAM": "1", "POCKETLAB_NATS_NAME": f"qualification-{self.run_id}",
            "POCKETLAB_NATS_USER": self.nats.user if self.nats else "", "POCKETLAB_NATS_PASSWORD": self.nats.password if self.nats else "", "POCKETLAB_AGENT_NATS_USER": self.nats.user if self.nats else "", "POCKETLAB_AGENT_NATS_PASSWORD": self.nats.password if self.nats else "",
            "POCKETLAB_NATS_INITIAL_CONNECT_DEADLINE": "5", "POCKETLAB_NATS_RECONNECT_WAIT": "30", "POCKETLAB_NATS_RECONNECT_MIN_SECONDS": "1", "POCKETLAB_NATS_RECONNECT_MAX_SECONDS": "5", "POCKETLAB_NATS_WATCHDOG_SECONDS": "2",
            "POCKETLAB_WORKER_DURABLE": "pocketlab_command_worker_v1", "POCKETLAB_WORKER_QUEUE": "pocketlab_command_worker_v1", "POCKETLAB_WORKER_RECOVERY_SECONDS": "2", "POCKETLAB_WORKER_HEARTBEAT_SECONDS": "5", "POCKETLAB_WORKER_NATS_RETRY_SECONDS": "1", "POCKETLAB_JETSTREAM_MAX_BYTES": "16777216", "POCKETLAB_QUALIFICATION_LOG_DIR": f"{self.remote_root}/logs", "POCKETLAB_DISABLE_RELEASE_UPDATER": "1",
            "POCKETLAB_LITE_SECURE_ORIGIN": "", "POCKETLAB_SECURE_ORIGIN": "", "CADDYFILE": "", "POCKET_LAB_CADDYFILE": "", "SSL_CERT_FILE": f"{self.remote_root}/qualification-ca.pem", "REQUESTS_CA_BUNDLE": f"{self.remote_root}/qualification-ca.pem",
        }
        return env

    def _start_transport_and_candidate(self) -> None:
        assert self.remote is not None and self.nats is not None and self.opa is not None
        self.remote_api_port = self.controller._android_select_port(self.remote)
        reverse = self.controller.AndroidTunnel(
            host=self.remote.host, run_id=self.run_id, kind="system-health-nats", log=self.paths.logs / "ssh-nats.log", direction="reverse",
            local_port=self.nats.port, target_port=self.nats.port, remote_port=0,
        )
        reverse.start()
        self.nats_tunnel = reverse
        self.tunnels.append(reverse)
        opa_tunnel = self.controller.AndroidTunnel(
            host=self.remote.host, run_id=self.run_id, kind="system-health-opa", log=self.paths.logs / "ssh-opa.log", direction="reverse",
            local_port=self.opa.port, target_port=self.opa.port, remote_port=0,
        )
        opa_tunnel.start()
        self.tunnels.append(opa_tunnel)
        local_api = self.controller.AndroidTunnel(
            host=self.remote.host, run_id=self.run_id, kind="system-health-api", log=self.paths.logs / "ssh-api.log", direction="local",
            local_port=self.local_api_port, target_port=self.remote_api_port,
        )
        local_api.start()
        self.tunnels.append(local_api)
        nats_origin = f"nats://127.0.0.1:{reverse.remote_port}"
        opa_origin = f"http://127.0.0.1:{opa_tunnel.remote_port}"
        assert self.database is not None
        # Dev-PC listener ports and the phone's loopback listener ports are
        # separate namespaces. Only local listeners can collide here.
        if len({self.nats.port, self.opa.port, self.local_api_port}) != 3:
            raise QualificationError("candidate local transport ports are not distinct")
        assert_isolated_binding(self.paths.root, self.database, nats_origin, "127.0.0.1", self.local_api_port, occupied_ports=[self.nats.port, self.opa.port])
        env = self._build_env(nats_origin, opa_origin, self.remote_api_port)
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

    def _pause_candidate_nats_for_recovery(self) -> bool:
        """Create a bounded unhealthy owner state in the isolated candidate only."""
        if not self.browser_ui or self.nats_tunnel is None:
            return False
        # The candidate environment already contains the first dynamic
        # reverse-forward port. Pin that owned port before restarting the
        # tunnel; otherwise the phone would receive a new port while the
        # worker still points at the original NATS origin.
        if self.nats_tunnel.remote_port:
            self.nats_tunnel.requested_remote_port = int(self.nats_tunnel.remote_port)
        if not self.nats_tunnel.stop():
            raise QualificationError("candidate NATS tunnel ownership could not be paused")
        # Let the worker's existing disconnect callback publish the unhealthy
        # owner state before an independent API admission request is sent.
        # A fixed sleep is not sufficient on Termux: the SSH process can close
        # before the NATS client and its prepared projection observe the loss.
        # This is a read-only prepared read; it does not collect, mutate, or
        # execute anything on the candidate API path.
        if self.client is None or not self.session:
            raise QualificationError("candidate recovery transport has no authenticated read session")
        deadline = time.monotonic() + 30.0
        last_status = "unknown"
        last_response = 0
        while time.monotonic() < deadline:
            response = self.client.request("GET", "/api/lite/system/health", session=self.session)
            last_response = response.status
            if response.status == 200:
                components = response.body.get("components") if isinstance(response.body, dict) else None
                if isinstance(components, dict):
                    last_status = str(components.get("nats") or "unknown").strip().lower()
                    if last_status in {"degraded", "unavailable", "unhealthy"}:
                        self.results["recovery_transport"] = {
                            "status": "PASS",
                            "candidate_nats_tunnel_paused": True,
                            "candidate_nats_prepared_status": last_status,
                            "production_transport_touched": False,
                        }
                        return True
            time.sleep(0.5)
        raise QualificationError(
            f"candidate NATS disconnect was not observed by prepared health read (status={last_status}, response={last_response})"
        )

    def _resume_candidate_nats_after_recovery_admission(self, paused: bool) -> None:
        if not paused or self.nats_tunnel is None:
            return
        self.nats_tunnel.start()
        self.results["recovery_transport"] = {
            "status": "PASS",
            "candidate_nats_tunnel_restarted": True,
            "production_transport_touched": False,
        }

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

    def _start_recovery_projection_fixture(self, *, bounded_seconds: int = 120) -> None:
        """Keep one bounded degraded NATS target current during recovery admission."""
        assert self.remote is not None
        bounded_seconds = max(120, min(int(bounded_seconds), 900))
        if self.recovery_fixture is not None and self.recovery_fixture.alive():
            raise QualificationError("a recovery projection fixture is already running")
        remote_path = f"{self.remote_root}/probe/system-health-recovery-fixture.py"
        self.controller._android_remote_write(
            self.remote.host, remote_path, _REMOTE_RECOVERY_FIXTURE, root=self.remote_root, mode="400"
        )
        self.recovery_fixture = self.controller.AndroidRemoteProcess(
            remote=self.remote, run_id=self.run_id, root=self.remote_root, name="system-health-recovery-fixture", env_path=self.env_path,
            argv=[self.remote.python, remote_path, self.runtime_root, f"{self.remote_root}/state/{SCHEMA_DB_NAME}", str(time.time() + bounded_seconds)],
            cwd=self.runtime_root, log_path=f"{self.remote_root}/logs/recovery-fixture.log",
        )
        self.recovery_fixture.launch()
        ready = False
        for _ in range(60):
            if not self.recovery_fixture.alive():
                raise QualificationError("recovery projection fixture exited before readiness")
            probe = self.controller._android_ssh_run(
                self.remote.host,
                [self.remote.python, "-c", _REMOTE_NATS_INCIDENT_READY_PROBE, f"{self.remote_root}/state/{SCHEMA_DB_NAME}"],
                timeout=15,
            )
            if probe.returncode == 0:
                try:
                    ready = int(json.loads(probe.stdout.strip().splitlines()[-1]).get("active_nats_incidents") or 0) > 0
                except (ValueError, IndexError, TypeError):
                    ready = False
            if ready:
                break
            time.sleep(0.5)
        if not ready:
            raise QualificationError("recovery projection fixture did not publish an active NATS incident")
        runs = self.results.setdefault("recovery_projection_fixture", [])
        if isinstance(runs, list):
            runs.append({"status": "PASS", "bounded_seconds": bounded_seconds, "target": "nats/jetstream", "fault_injection": "candidate_sqlite_projection_only"})

    def _stop_recovery_projection_fixture(self) -> None:
        if self.recovery_fixture is not None:
            with contextlib.suppress(Exception):
                self.recovery_fixture.stop()

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
        self.results["incident_candidates"] = [
            {
                "source": _safe_text(item.get("source"), 64),
                "target_id": _safe_text(item.get("target_id"), 128),
                "state": _safe_text(item.get("state"), 48),
                "current_monitoring": bool(item.get("current_monitoring")),
                "repair_available": bool(item.get("repair_available")),
                "concern_state": _safe_text(item.get("concern_state"), 48),
            }
            for item in items[:40]
            if isinstance(item, dict)
        ]

        def eligible_incident(rows: Any) -> dict[str, Any]:
            if not isinstance(rows, list):
                return {}
            return next(
                (
                    item for item in rows
                    if isinstance(item, dict)
                    and item.get("source") == "nats"
                    and (item.get("target_id") == "jetstream" or str(item.get("target_id") or "").startswith("consumer:"))
                    and item.get("current_monitoring") is True
                    and item.get("repair_available") is True
                    and item.get("state") != "resolved"
                    and int(item.get("generation") or 0) >= 1
                    and str(item.get("incident_id") or "")
                ),
                {},
            )

        incident: dict[str, Any] = {}
        incident_id = ""
        generation = 0
        detail = decisions = app = diagnosis = None
        repair_payload: dict[str, Any] = {}
        preflight = repair = replay = stale_repair = unauthorized = None
        repair_attempts: list[dict[str, Any]] = []
        transient_race_reasons = {
            "incident_already_resolved",
            "evidence_not_current",
            "unhealthy_evidence_not_confirmed",
            "incident_generation_changed",
        }
        for attempt in range(1, 7):
            current_incidents = self.client.request("GET", "/api/lite/system-health/incidents", session=self.session)
            current_items = current_incidents.body.get("items") if isinstance(current_incidents.body, dict) else []
            incident = eligible_incident(current_items)
            if not incident:
                time.sleep(0.4)
                continue
            incident_id = str(incident.get("incident_id") or "")
            generation = int(incident.get("generation") or 0)
            self.results["recovery_selection"] = {
                "source": _safe_text(incident.get("source"), 64),
                "target_id": _safe_text(incident.get("target_id"), 128),
                "generation": generation,
                "enrollment_generation": int(incident.get("enrollment_generation") or 0),
                "attempt": attempt,
            }
            detail = self.client.request("GET", f"/api/lite/system-health/incidents/{incident_id}", session=self.session)
            decisions = self.client.request("GET", f"/api/lite/system-health/incidents/{incident_id}/decisions", session=self.session)
            app = self.client.request("GET", "/api/lite/system-health/apps/photoprism", session=self.session)
            if detail.status != 200 or decisions.status != 200 or app.status not in {200, 404}:
                raise QualificationError("candidate System Health incident detail routes failed")
            diagnosis = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/diagnose", session=self.session)
            if diagnosis.status != 200:
                raise QualificationError("candidate System Health diagnosis was not persisted")
            repair_payload = {
                "operation_id": "runtime.consumer.reconnect",
                "expected_generation": generation,
                "idempotency_key": f"qualification-system-health-{attempt:03d}",
                "confirm": True,
            }
            preflight = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/preflight", repair_payload, session=self.session)
            nats_paused = self._pause_candidate_nats_for_recovery()
            try:
                repair = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/repair", repair_payload, session=self.session)
            finally:
                self._resume_candidate_nats_after_recovery_admission(nats_paused)
            repair_detail = response_detail(repair)
            repair_attempts.append({
                "attempt": attempt,
                "preflight_status": preflight.status,
                "repair_status": repair.status,
                "repair_reason_code": _safe_text(repair_detail.get("reason_code"), 80),
            })
            if not self.browser_ui and repair.status == 403:
                # The security-assurance profile is intentionally not granted
                # the qualification-owner recovery capability. Exercise the
                # same request again, then prove generation fencing and
                # anonymous-write rejection without treating the expected
                # fail-closed 403 as an execution failure.
                replay = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/repair", repair_payload, session=self.session)
                stale = dict(repair_payload)
                stale["expected_generation"] = generation + 99
                stale["idempotency_key"] = f"{repair_payload['idempotency_key']}-stale"
                stale_repair = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/repair", stale, session=self.session)
                unauthorized = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/diagnose")
                break
            if repair.status == 202:
                replay = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/repair", repair_payload, session=self.session)
                stale = dict(repair_payload)
                stale["expected_generation"] = generation + 99
                stale["idempotency_key"] = f"{repair_payload['idempotency_key']}-stale"
                stale_repair = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/repair", stale, session=self.session)
                unauthorized = self.client.request("POST", f"/api/lite/system-health/incidents/{incident_id}/diagnose")
                break
            if not self.browser_ui or repair_detail.get("reason_code") not in transient_race_reasons:
                break
            time.sleep(0.4)

        if not incident or not incident_id or generation < 1 or repair is None:
            raise QualificationError("candidate System Health projection did not produce an eligible NATS recovery incident")
        self.results["recovery_attempts"] = repair_attempts
        self.results["repair_contract"] = {
            "preflight": response_contract(preflight),
            "repair": response_contract(repair),
            "replay": response_contract(replay),
            "stale_repair": response_contract(stale_repair),
            "unauthorized_diagnosis": response_contract(unauthorized),
        }
        body = response_detail(repair)
        stale_body = response_detail(stale_repair)
        lifecycle: list[str] = []
        if self.browser_ui:
            if preflight.status != 200 or repair.status != 202 or replay.status != 202 or stale_repair.status != 409 or unauthorized.status != 401:
                raise QualificationError("System Health controlled recovery admission/authentication contract failed")
            request = body.get("request") if isinstance(body.get("request"), dict) else {}
            if body.get("status") != "admitted" or not request.get("request_id"):
                raise QualificationError("System Health controlled recovery was not durably admitted")
            deadline = time.monotonic() + 45
            latest_request: dict[str, Any] = {}
            while time.monotonic() < deadline:
                decisions_now = self.client.request("GET", f"/api/lite/system-health/incidents/{incident_id}/decisions", session=self.session)
                requests = decisions_now.body.get("recovery_requests") if isinstance(decisions_now.body, dict) else []
                current_request = next((item for item in requests if isinstance(item, dict) and item.get("request_id") == request.get("request_id")), None)
                if current_request:
                    latest_request = current_request
                    status = str(current_request.get("status") or "")
                    if status and (not lifecycle or lifecycle[-1] != status):
                        lifecycle.append(status)
                    if status in {"verified", "execution_failed", "verification_failed", "verification_unavailable", "manual_attention_required", "blocked", "expired", "cancelled"}:
                        break
                time.sleep(1)
            self.results["recovery_lifecycle"] = lifecycle
            self.results["recovery_last_request"] = latest_request
            if not lifecycle or lifecycle[-1] != "verified":
                raise QualificationError("System Health recovery did not reach independently verified state")
        else:
            if preflight.status != 200 or repair.status not in {403, 409} or stale_repair.status != 409 or unauthorized.status != 401:
                raise QualificationError("System Health repair denial/authentication contract failed")
            if repair.status == 403:
                if body.get("status") != "denied" or body.get("reason_code") != "harness_capability_denied" or replay.status != 403:
                    raise QualificationError("System Health capability denial was not fail-closed")
            elif body.get("status") != "blocked" or body.get("recorded") is not True or replay.status != 409:
                raise QualificationError("System Health repair denial was not fail-closed")
        if stale_body.get("reason_code") != "incident_generation_changed":
            raise QualificationError("System Health stale generation was not rejected")
        self.results["system_health_api"] = {
            "status": "PASS", "anonymous_read_rejected": True, "authenticated_routes": route_results,
            "incident_id_class": "deterministic_health_identity", "incident_generation": generation, "incident_state": incident.get("state"),
            "detail": detail.status, "diagnosis": diagnosis.status, "preflight": preflight.status, "repair": repair.status,
            "idempotent_replay": replay.status in {202, 409}, "denial_replay": (not self.browser_ui and replay.status == repair.status), "generation_fencing": stale_body.get("reason_code"), "unauthorized_write": unauthorized.status,
            "app_diagnostics_status": app.status, "new_executor_enabled": False, "controlled_recovery_verified": self.browser_ui,
            "recovery_lifecycle": lifecycle, "raw_evidence_exposed": False,
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

    def capture_candidate_diagnostics(self) -> None:
        """Capture bounded, sanitized owner-state evidence before cleanup."""
        if self.remote is None or not self.remote_root:
            return
        logs: dict[str, list[str]] = {}
        for name in ("api.log", "worker.log", "driver.log", "recovery-fixture.log"):
            try:
                raw = self.controller._android_read_text(self.remote, f"{self.remote_root}/logs/{name}", root=self.remote_root)
            except Exception:
                continue
            safe_lines: list[str] = []
            for line in str(raw or "").splitlines()[-80:]:
                if re.search(r"token|password|secret|cookie|authorization|private[_ -]?key", line, re.IGNORECASE):
                    safe_lines.append("[redacted diagnostic line]")
                    continue
                safe_lines.append(re.sub(r"https?://[^\s]+", "[url]", _safe_text(line, 360)))
            if safe_lines:
                logs[name] = safe_lines
        probe = self.controller._android_ssh_run(
            self.remote.host,
            [self.remote.python, "-c", _REMOTE_RECOVERY_PROBE, f"{self.remote_root}/state/{SCHEMA_DB_NAME}"],
            timeout=20,
        )
        database: dict[str, Any] = {"status": "UNVALIDATED"}
        if probe.returncode == 0:
            try:
                parsed = json.loads(probe.stdout.strip().splitlines()[-1])
                database = sanitize(parsed)
                database["status"] = "PASS"
            except (ValueError, IndexError, TypeError):
                database = {"status": "UNVALIDATED"}
        self.results["candidate_recovery_diagnostics"] = {
            "status": "PASS" if database.get("status") == "PASS" else "UNVALIDATED",
            "database": database,
            "log_tails": logs,
            "sanitized": True,
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
        for process in (self.recovery_fixture, self.driver, self.worker, self.api):
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
        if self.opa is not None:
            with contextlib.suppress(Exception):
                self.opa.stop()
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
            # The phone receives only the schema-42 candidate DB. The candidate
            # API owns the complete forward migration chain at startup.
            self._start_local_nats()
            self._stage_remote()
            self._start_local_opa()
            before = self._remote_probe(expected=42)
            self.results.setdefault("isolated_sqlite", {})["phone_before_migration"] = before
            self._start_transport_and_candidate()
            after = self._remote_probe(expected=self.candidate_schema_version)
            if after.get("marker_revision") != 7 or after.get("status") != "PASS":
                raise QualificationError("phone candidate migration did not preserve the isolated fixture")
            self.results.setdefault("isolated_sqlite", {})["phone_after_migration"] = after
            self._run_projection_driver()
            self._bootstrap()
            # The backend-only lane owns its own bounded degraded projection
            # fixture.  Without this, the API recovery contract is exercised
            # against whichever incidental observations the candidate startup
            # produced, so the required eligible NATS target is never
            # guaranteed and the lane can fail before testing authorization.
            self._start_recovery_projection_fixture()
            self._qualify_api()
            self._concurrency()
            self._measure()
            repeat = self._remote_probe(expected=self.candidate_schema_version)
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
        evidence = self.external_evidence / f"pr657-system-health-android-{self.candidate_sha[:12]}.json"
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
