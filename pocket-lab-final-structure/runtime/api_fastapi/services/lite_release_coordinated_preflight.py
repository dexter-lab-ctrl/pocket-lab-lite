"""Isolated coordinated-candidate staging, never installation.

Only invoked by the existing release verification subprocess after signature,
integrity and provenance verification. No candidate code, SQL, or shell is
executed. A checkpoint is not a rollback authorization or a runtime identity.
"""
from __future__ import annotations

import hashlib
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import zipfile

from . import lite_release_package as package
from .lite_lifecycle_contract import digest
from .lite_release_contract import BUILD_IDENTITY_NAME, inspect_pwa_archive, safe_extract_zip
from .lite_release_trust import TrustError, strict_json

MAX_CHECKPOINT_BYTES = 128 * 1024 * 1024
RESERVE = 32 * 1024 * 1024


def _deadline(deadline_ns):
    if time.monotonic_ns() >= deadline_ns:
        raise TrustError("coordinated_preflight_deadline")


def _stage_source(stream, destination, *, declaration, policy_document, migration_document, deadline_ns):
    # Recheck the exact archive descriptor before writing even inert files.
    evidence = package.inspect_source(stream, declaration=declaration,
        policy_inventory=policy_document, migration_inventory=migration_document)
    if shutil.disk_usage(destination.parent).free < evidence["expanded_bytes"] + RESERVE:
        raise TrustError("coordinated_stage_disk_pressure")
    destination.mkdir(mode=0o700)
    entries = []
    total = 0
    stream.seek(0)
    with zipfile.ZipFile(stream) as archive:
        for item in archive.infolist():
            _deadline(deadline_ns)
            if item.is_dir():
                continue
            name = package._member_name(item.filename)
            path = destination.joinpath(*name.split("/"))
            path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            h = hashlib.sha256()
            written = 0
            with archive.open(item) as member, path.open("xb") as output:
                while chunk := member.read(1024 * 1024):
                    _deadline(deadline_ns)
                    written += len(chunk)
                    total += len(chunk)
                    if written > item.file_size or total > package.MAX_EXPANDED_BYTES:
                        raise TrustError("coordinated_stage_size_mismatch")
                    output.write(chunk)
                    h.update(chunk)
                if written != item.file_size:
                    raise TrustError("coordinated_stage_size_mismatch")
                output.flush()
                os.fsync(output.fileno())
            path.chmod(0o400)
            entries.append({"path": name, "sha256": h.hexdigest()})
    if total != evidence["expanded_bytes"] or len(entries) != evidence["file_count"]:
        raise TrustError("coordinated_stage_inventory_mismatch")
    entries.sort(key=lambda row: row["path"])
    return {"tree_sha256": digest(entries), "source_files": len(entries),
            "native_tree_sha256": digest([row for row in entries if row["path"].startswith((package.RUNTIME, package.BOOTSTRAP))]),
            "source_expanded_bytes": total}


def _frontend(stream, destination, receipt, deadline_ns):
    _deadline(deadline_ns)
    h = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        _deadline(deadline_ns)
        h.update(chunk)
    if h.hexdigest() != receipt["artifact_sha256"]:
        raise TrustError("coordinated_frontend_changed")
    stream.seek(0)
    info = inspect_pwa_archive(stream)
    if shutil.disk_usage(destination.parent).free < info["expanded_bytes"] + RESERVE:
        raise TrustError("coordinated_stage_disk_pressure")
    stream.seek(0)
    with zipfile.ZipFile(stream) as archive:
        item = archive.getinfo(BUILD_IDENTITY_NAME)
        if item.file_size > 16384:
            raise TrustError("frontend_identity_limit")
        identity = strict_json(archive.read(item))
    if (identity.get("release_tag") != receipt["release_tag"]
            or identity.get("source_commit") != receipt["source_commit"]):
        raise TrustError("coordinated_frontend_identity_mismatch")
    stream.seek(0)
    safe_extract_zip(stream, destination)
    _deadline(deadline_ns)
    return {"frontend_files": info["entry_count"], "frontend_expanded_bytes": info["expanded_bytes"],
            "frontend_identity_sha256": digest(identity)}


def _checkpoint(destination, *, expected_schema, deadline_ns):
    from ..db.connection import database_path, online_backup, fast_read_connection
    # Do not run candidate SQL against this file: it can contain private state.
    # Never restore this snapshot automatically, including on preflight failure.
    with fast_read_connection(timeout_ms=250) as conn:
        count = conn.execute("PRAGMA page_count").fetchone()[0]
        size = conn.execute("PRAGMA page_size").fetchone()[0]
    if (count * size > MAX_CHECKPOINT_BYTES or
            shutil.disk_usage(destination.parent).free < count * size + RESERVE):
        raise TrustError("coordinated_checkpoint_disk_pressure")

    def progress(status, remaining, total):
        _deadline(deadline_ns)
        if total * size > MAX_CHECKPOINT_BYTES:
            raise TrustError("coordinated_checkpoint_limit")

    online_backup(destination, pages=64, sleep=0.025, progress=progress)
    with closing(sqlite3.connect(destination.as_uri() + "?mode=ro", uri=True)) as snapshot:
        snapshot.set_progress_handler(lambda: int(time.monotonic_ns() >= deadline_ns), 1000)
        if snapshot.execute("PRAGMA quick_check(1)").fetchone()[0] != "ok":
            raise TrustError("coordinated_checkpoint_integrity_failed")
        schema = snapshot.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0]
        if schema != expected_schema:
            raise TrustError("coordinated_checkpoint_schema_changed")
    _deadline(deadline_ns)
    # Digest is for a discarded rehearsal artifact, not a durable recovery point.
    return {"checkpoint_state": "isolated_copy_checked", "checkpoint_schema": schema,
            "checkpoint_bytes": destination.stat().st_size}


def assess(candidate, receipt, *, declaration, policy_document, migration_document, deadline_ns):
    from .lite_release_trust_runtime import _open_controlled, _read, MAX_ARTIFACT
    from tempfile import TemporaryDirectory
    try:
        _deadline(deadline_ns)
        with TemporaryDirectory(prefix="coordinated-preflight-", dir=candidate) as temporary:
            root = Path(temporary)
            with _open_controlled(candidate, package.SOURCE_ASSET, package.MAX_SOURCE_BYTES) as (source, _):
                source_result = _stage_source(source, root / "source", declaration=declaration,
                    policy_document=policy_document, migration_document=migration_document, deadline_ns=deadline_ns)
            with _open_controlled(candidate, "dist.zip", MAX_ARTIFACT) as (frontend_stream, _):
                frontend = _frontend(frontend_stream, root / "frontend", receipt, deadline_ns)
            checkpoint = _checkpoint(root / "checkpoint.sqlite", expected_schema=receipt["current_schema"], deadline_ns=deadline_ns)
            from .lite_release_migration_rehearsal import assess as rehearse_migrations
            rehearsal = rehearse_migrations(root / "source", migration_document,
                current_schema=receipt["current_schema"], deadline_ns=deadline_ns)
            return {"state": "isolated_preflight_checked", **source_result, **frontend, **checkpoint,
                    "migration_execution": rehearsal, "promotion_eligible": False,
                    "rollback_eligible": False}
    except (TrustError, OSError, sqlite3.Error, ValueError, KeyError, zipfile.BadZipFile) as exc:
        return {"state": "blocked", "reason_code": str(exc) if isinstance(exc, TrustError) else "coordinated_preflight_failed",
                "promotion_eligible": False, "rollback_eligible": False}
