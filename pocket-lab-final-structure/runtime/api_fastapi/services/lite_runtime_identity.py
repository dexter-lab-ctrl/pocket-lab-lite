"""Fail-closed prepared identity for the installed Lite runtime.

The projection is deliberately separate from the frontend build marker and
from the Git checkout.  An execution owner records it only after observing
the installed artifact, process owners, loaded policy, frontend generation,
and SQLite migration ledger.  Normal reads validate the durable record but do
not perform process, network, or filesystem probes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Mapping

from ..db.connection import begin_immediate

SCHEMA_VERSION = 1
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE = re.compile(r"^[0-9a-f]{40}$")
_GENERATION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REVISION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")

IDENTITY_FIELDS = (
    "coordinated_generation",
    "authenticated_source_commit",
    "installed_artifact_sha256",
    "installed_source_inventory_sha256",
    "fastapi_process_identity_sha256",
    "worker_process_identity_sha256",
    "core_supervisor_identity_sha256",
    "runtime_reconciler_identity_sha256",
    "loaded_policy_revision",
    "loaded_policy_module_sha256",
    "loaded_policy_data_sha256",
    "frontend_generation",
    "sqlite_schema_version",
    "sqlite_migration_ledger_sha256",
)

_PUBLIC_FIELDS = (
    "status",
    "reason_code",
    "observed_at",
    "stale_after",
    *IDENTITY_FIELDS,
    "identity_sha256",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_stamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _canonical(value: Mapping[str, object]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def digest(value: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _validate_identity(values: Mapping[str, object]) -> dict[str, object]:
    missing = [field for field in IDENTITY_FIELDS if field not in values]
    if missing:
        raise ValueError("runtime_identity_incomplete")
    result: dict[str, object] = {}
    for field in IDENTITY_FIELDS:
        value = values[field]
        if field == "sqlite_schema_version":
            if type(value) is not int or value <= 0:
                raise ValueError("runtime_identity_schema_invalid")
        elif field == "authenticated_source_commit":
            if not isinstance(value, str) or not _SOURCE.fullmatch(value):
                raise ValueError("runtime_identity_source_invalid")
        elif field == "loaded_policy_revision":
            if not isinstance(value, str) or not _REVISION.fullmatch(value):
                raise ValueError("runtime_identity_policy_revision_invalid")
        elif field in {"coordinated_generation", "frontend_generation"}:
            if not isinstance(value, str) or not _GENERATION.fullmatch(value):
                raise ValueError("runtime_identity_generation_invalid")
        elif not isinstance(value, str) or not _SHA256.fullmatch(value):
            raise ValueError("runtime_identity_digest_invalid")
        result[field] = value
    return result


def build_observation(*, status: str = "stable", reason_code: str = "observed",
                      observed_at: str | None = None, stale_after: str | None = None,
                      **values: object) -> dict[str, object]:
    """Build a canonical observation from independently supplied evidence.

    This helper hashes only already-observed component identities.  It does not
    derive a backend identity from a frontend build or from an expected SHA.
    """
    if status not in {"stable", "transitioning", "degraded", "unknown"}:
        raise ValueError("runtime_identity_status_invalid")
    if not isinstance(reason_code, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", reason_code):
        raise ValueError("runtime_identity_reason_invalid")
    identity = _validate_identity(values)
    observed = observed_at or _stamp(_now())
    expiry = stale_after or _stamp((_parse_stamp(observed) or _now()) + timedelta(seconds=120))
    if _parse_stamp(observed) is None or _parse_stamp(expiry) is None:
        raise ValueError("runtime_identity_timestamp_invalid")
    result = {"status": status, "reason_code": reason_code,
              "observed_at": observed, "stale_after": expiry, **identity}
    result["identity_sha256"] = digest(identity)
    return result


def record(conn, observation: Mapping[str, object]) -> dict[str, object]:
    """Durably publish one owner-observed projection under the SQLite writer lock."""
    expected = build_observation(**{key: observation[key] for key in (
        "status", "reason_code", "observed_at", "stale_after", *IDENTITY_FIELDS)})
    if expected["identity_sha256"] != observation.get("identity_sha256"):
        raise ValueError("runtime_identity_digest_mismatch")
    if expected["status"] == "stable" and expected["reason_code"] not in {"observed", "converged"}:
        raise ValueError("runtime_identity_stable_reason_invalid")
    with begin_immediate(conn) as tx:
        tx.execute("""INSERT INTO lite_runtime_identity_projection(
            singleton_id,status,reason_code,observed_at,stale_after,
            coordinated_generation,authenticated_source_commit,
            installed_artifact_sha256,installed_source_inventory_sha256,
            fastapi_process_identity_sha256,worker_process_identity_sha256,
            core_supervisor_identity_sha256,runtime_reconciler_identity_sha256,
            loaded_policy_revision,loaded_policy_module_sha256,
            loaded_policy_data_sha256,frontend_generation,sqlite_schema_version,
            sqlite_migration_ledger_sha256,identity_sha256,updated_at)
            VALUES(1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(singleton_id) DO UPDATE SET
            status=excluded.status,reason_code=excluded.reason_code,
            observed_at=excluded.observed_at,stale_after=excluded.stale_after,
            coordinated_generation=excluded.coordinated_generation,
            authenticated_source_commit=excluded.authenticated_source_commit,
            installed_artifact_sha256=excluded.installed_artifact_sha256,
            installed_source_inventory_sha256=excluded.installed_source_inventory_sha256,
            fastapi_process_identity_sha256=excluded.fastapi_process_identity_sha256,
            worker_process_identity_sha256=excluded.worker_process_identity_sha256,
            core_supervisor_identity_sha256=excluded.core_supervisor_identity_sha256,
            runtime_reconciler_identity_sha256=excluded.runtime_reconciler_identity_sha256,
            loaded_policy_revision=excluded.loaded_policy_revision,
            loaded_policy_module_sha256=excluded.loaded_policy_module_sha256,
            loaded_policy_data_sha256=excluded.loaded_policy_data_sha256,
            frontend_generation=excluded.frontend_generation,
            sqlite_schema_version=excluded.sqlite_schema_version,
            sqlite_migration_ledger_sha256=excluded.sqlite_migration_ledger_sha256,
            identity_sha256=excluded.identity_sha256,updated_at=excluded.updated_at""",
            (expected["status"], expected["reason_code"], expected["observed_at"],
             expected["stale_after"], *(expected[field] for field in IDENTITY_FIELDS),
             expected["identity_sha256"], _stamp(_now())))
    return public_projection(conn)


def _unknown(reason: str) -> dict[str, object]:
    return {"schema_version": SCHEMA_VERSION, "status": "unknown", "reason_code": reason,
            "execution_eligible": False, "converged": False, "sanitized": True}


def public_projection(conn, *, now: datetime | None = None) -> dict[str, object]:
    row = conn.execute("SELECT * FROM lite_runtime_identity_projection WHERE singleton_id=1").fetchone()
    if not row:
        return _unknown("runtime_identity_unavailable")
    values = {field: row[field] for field in IDENTITY_FIELDS}
    if row["identity_sha256"] != digest(values):
        return _unknown("runtime_identity_corrupt")
    observed = _parse_stamp(row["observed_at"])
    expiry = _parse_stamp(row["stale_after"])
    if observed is None or expiry is None or expiry <= observed:
        return _unknown("runtime_identity_timestamp_invalid")
    current = now or _now()
    if expiry <= current:
        return {"schema_version": SCHEMA_VERSION, "status": "unknown",
                "reason_code": "runtime_identity_stale", "observed_at": row["observed_at"],
                "stale_after": row["stale_after"], "identity_sha256": row["identity_sha256"],
                "execution_eligible": False, "converged": False, "sanitized": True}
    result = {"schema_version": SCHEMA_VERSION,
              **{field: row[field] for field in _PUBLIC_FIELDS},
              "execution_eligible": row["status"] == "stable",
              "converged": row["status"] == "stable", "sanitized": True}
    return result


def require_converged(conn, *, generation: str | None = None) -> dict[str, object]:
    projection = public_projection(conn)
    if projection.get("status") != "stable" or not projection.get("converged"):
        raise PermissionError(str(projection.get("reason_code") or "runtime_identity_unavailable"))
    if generation is not None and projection.get("coordinated_generation") != generation:
        raise PermissionError("runtime_generation_mismatch")
    return projection
