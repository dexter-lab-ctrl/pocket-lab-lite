#!/usr/bin/env python3
"""Resolve the OPA policy revision that Lite startup is allowed to run.

This helper is intentionally read-only with respect to Pocket Lab governance
state. It never creates revisions, changes activation operations, updates
policy_runtime_state, or mutates OPA pointers. Once P2.2 durable runtime state
exists, that proved state is authoritative across source updates and reboots.

The optional ``--locked-exec`` mode holds the same activation lock used by the
Lite core supervisor while it re-resolves authority and runs one bounded child
command. This prevents startup pointer/restart work from racing supervisor
policy reconciliation without moving governance writes into bootstrap code.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import sys
import time
from typing import Any, Iterable

REVISION_RE = re.compile(r"^[A-Za-z0-9._-]{8,80}$")
NONTERMINAL_STATES = frozenset(
    {"pending", "validating", "switching", "restarting", "verifying", "rolling_back", "uncertain"}
)
REQUIRED_POLICY_TABLES = frozenset(
    {"policy_revisions", "policy_runtime_state", "policy_activation_operations"}
)
DEFAULT_LOCK_TIMEOUT_SECONDS = 15.0
MAX_LOCK_TIMEOUT_SECONDS = 60.0
LOCK_TIMEOUT_EXIT = 75


def _state_dir() -> Path:
    configured = os.environ.get("POCKETLAB_STATE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    base = os.environ.get("POCKETLAB_BASE_DIR", "").strip()
    if base:
        return (Path(base).expanduser() / "state").resolve(strict=False)
    return (Path.home() / ".pocket_lab").resolve(strict=False)


def _database_path(state_dir: Path) -> Path:
    configured = os.environ.get("POCKETLAB_LITE_DB_PATH", "").strip()
    return (
        Path(configured).expanduser().resolve(strict=False)
        if configured
        else state_dir / "pocketlab-lite.sqlite3"
    )


def _result(mode: str, *, revision_id: str = "", reason_code: str = "") -> dict[str, str]:
    return {
        "mode": str(mode),
        "revision_id": str(revision_id),
        "reason_code": str(reason_code),
    }


def _blocked(reason_code: str) -> dict[str, str]:
    return _result("blocked", reason_code=reason_code)


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if row and row[0]
    }


def _connect_read_only(path: Path) -> sqlite3.Connection:
    # URI mode=ro prevents accidental database creation or writes. Keep the
    # timeout short because startup can safely remain fail-closed while the
    # control plane/supervisor recover an unavailable governance database.
    conn = sqlite3.connect(
        f"file:{path.as_posix()}?mode=ro",
        uri=True,
        timeout=2.0,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    conn.execute("PRAGMA busy_timeout = 2000")
    return conn


def _safe_manifest_path(raw: object) -> PurePosixPath | None:
    value = str(raw or "")
    if not value or "\\" in value:
        return None
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path


def _canonical_entries(entries: Iterable[dict[str, str]]) -> str:
    return json.dumps(list(entries), sort_keys=True, separators=(",", ":"))


def _validated_stage_contract(
    state_dir: Path,
    revision_id: str,
) -> tuple[str, list[dict[str, str]], str]:
    """Return (status, files, candidate_hash) for one immutable stage.

    status is one of ``valid``, ``unavailable`` or ``corrupt``. Every file in
    the manifest is bounded beneath the stage and must be a regular, non-symlink
    file with the exact recorded SHA-256. Extra files are rejected except for
    revision.txt and manifest.json, which are stage metadata by contract.
    """
    stage_root = state_dir / "opa" / "stage"
    stage = stage_root / revision_id
    try:
        if not stage.is_dir() or stage.is_symlink():
            return "unavailable", [], ""
        if stage.parent.resolve(strict=True) != stage_root.resolve(strict=True):
            return "corrupt", [], ""
        revision_file = stage / "revision.txt"
        manifest_file = stage / "manifest.json"
        if (
            not revision_file.is_file()
            or revision_file.is_symlink()
            or revision_file.read_text(encoding="utf-8").strip() != revision_id
            or not manifest_file.is_file()
            or manifest_file.is_symlink()
        ):
            return "corrupt", [], ""
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("revision") != revision_id:
            return "corrupt", [], ""
        raw_files = manifest.get("files")
        candidate_hash = manifest.get("candidate_hash")
        if not isinstance(raw_files, list) or not isinstance(candidate_hash, str):
            return "corrupt", [], ""

        entries: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in raw_files:
            if not isinstance(item, dict):
                return "corrupt", [], ""
            safe = _safe_manifest_path(item.get("path"))
            digest = str(item.get("sha256") or "")
            if safe is None or not re.fullmatch(r"[0-9a-f]{64}", digest):
                return "corrupt", [], ""
            rel = safe.as_posix()
            if rel in seen or rel in {"revision.txt", "manifest.json"}:
                return "corrupt", [], ""
            seen.add(rel)
            path = stage.joinpath(*safe.parts)
            if not path.is_file() or path.is_symlink():
                return "corrupt", [], ""
            resolved = path.resolve(strict=True)
            if stage.resolve(strict=True) not in resolved.parents:
                return "corrupt", [], ""
            observed = hashlib.sha256(path.read_bytes()).hexdigest()
            if observed != digest:
                return "corrupt", [], ""
            entries.append({"path": rel, "sha256": digest})

        actual_files = {
            path.relative_to(stage).as_posix()
            for path in stage.rglob("*")
            if path.is_file()
        }
        if actual_files != seen | {"revision.txt", "manifest.json"}:
            return "corrupt", [], ""

        entries.sort(key=lambda item: item["path"])
        observed_candidate_hash = hashlib.sha256(
            _canonical_entries(entries).encode("utf-8")
        ).hexdigest()
        if observed_candidate_hash != candidate_hash:
            return "corrupt", [], ""
        return "valid", entries, candidate_hash
    except (OSError, ValueError, json.JSONDecodeError, UnicodeError):
        return "corrupt", [], ""


def _durable_manifest_matches(
    row: sqlite3.Row,
    stage_files: list[dict[str, str]],
    stage_candidate_hash: str,
) -> bool:
    try:
        manifest = json.loads(str(row["manifest_json"] or ""))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        return False
    durable_hash = str(row["content_hash"] or "")
    return (
        durable_hash != ""
        and manifest.get("candidate_hash") == durable_hash
        and stage_candidate_hash == durable_hash
        and manifest.get("files") == stage_files
    )


def resolve_authority() -> dict[str, str]:
    state_dir = _state_dir()
    database = _database_path(state_dir)
    if not database.exists():
        return _result("baseline_bootstrap")

    try:
        conn = _connect_read_only(database)
        try:
            tables = _table_names(conn)
            present = tables & REQUIRED_POLICY_TABLES
            if not present:
                # Pre-P2.2 / Personal-mode database: preserve the existing
                # repository baseline bootstrap contract.
                return _result("baseline_bootstrap")
            if not REQUIRED_POLICY_TABLES.issubset(tables):
                return _blocked("policy_startup_schema_incomplete")

            operation = conn.execute(
                """
                SELECT state
                FROM policy_activation_operations
                WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain')
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if operation is not None:
                state = str(operation["state"] or "")
                if state == "uncertain":
                    return _blocked("policy_revision_uncertain")
                if state in NONTERMINAL_STATES:
                    return _blocked("policy_activation_pending")
                return _blocked("policy_startup_operation_state_invalid")

            runtime = conn.execute(
                """
                SELECT active_revision_id, known_good_revision_id
                FROM policy_runtime_state
                WHERE state_id=1
                """
            ).fetchone()
            if runtime is None:
                return _result("baseline_bootstrap")
            active = str(runtime["active_revision_id"] or "")
            known_good = str(runtime["known_good_revision_id"] or "")
            if not active and not known_good:
                return _result("baseline_bootstrap")
            if not active or not known_good:
                return _blocked("policy_startup_runtime_state_incomplete")
            if active != known_good:
                return _blocked("policy_startup_runtime_state_mismatch")
            if REVISION_RE.fullmatch(active) is None:
                return _blocked("policy_startup_revision_invalid")

            revision = conn.execute(
                """
                SELECT revision_id, manifest_json, content_hash,
                       validation_status, lifecycle_status
                FROM policy_revisions
                WHERE revision_id=?
                """,
                (active,),
            ).fetchone()
            if revision is None:
                return _blocked("policy_startup_revision_unknown")
            if (
                str(revision["validation_status"] or "") != "valid"
                or str(revision["lifecycle_status"] or "") != "active"
            ):
                return _blocked("policy_startup_revision_unproved")

            stage_status, files, candidate_hash = _validated_stage_contract(state_dir, active)
            if stage_status == "unavailable":
                return _blocked("policy_startup_durable_stage_unavailable")
            if stage_status != "valid":
                return _blocked("policy_startup_durable_stage_corrupt")
            if not _durable_manifest_matches(revision, files, candidate_hash):
                return _blocked("policy_startup_durable_stage_mismatch")
            return _result("durable", revision_id=active)
        finally:
            conn.close()
    except (OSError, sqlite3.Error):
        return _blocked("policy_startup_database_unavailable")


def _lock_timeout_seconds() -> float:
    raw = os.environ.get(
        "POCKETLAB_OPA_STARTUP_LOCK_TIMEOUT_SECONDS",
        str(DEFAULT_LOCK_TIMEOUT_SECONDS),
    ).strip()
    try:
        parsed = float(raw)
    except ValueError:
        parsed = DEFAULT_LOCK_TIMEOUT_SECONDS
    return max(1.0, min(parsed, MAX_LOCK_TIMEOUT_SECONDS))


def _acquire_activation_lock(handle: Any, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))


def _locked_exec(command: list[str]) -> int:
    if not command:
        return 64
    state_dir = _state_dir()
    lock_path = state_dir / "opa" / "activation.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        if not _acquire_activation_lock(handle, _lock_timeout_seconds()):
            print(
                json.dumps(
                    _blocked("policy_startup_activation_lock_timeout"),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
            return LOCK_TIMEOUT_EXIT
        authority = resolve_authority()
        child_env = os.environ.copy()
        child_env["POCKETLAB_OPA_STARTUP_MODE"] = authority["mode"]
        child_env["POCKETLAB_OPA_STARTUP_REVISION"] = authority["revision_id"]
        child_env["POCKETLAB_OPA_STARTUP_REASON_CODE"] = authority["reason_code"]
        try:
            completed = subprocess.run(command, check=False, env=child_env)
            return int(completed.returncode)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Resolve the governed OPA revision allowed during Lite startup."
    )
    parser.add_argument(
        "--locked-exec",
        action="store_true",
        help="hold the supervisor activation lock and execute the command after --",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.locked_exec:
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        return _locked_exec(command)
    if args.command:
        parser.error("a child command requires --locked-exec")
    print(json.dumps(resolve_authority(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
