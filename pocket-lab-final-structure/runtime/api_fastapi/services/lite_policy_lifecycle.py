"""Server-owned, typed Enterprise Rules revision lifecycle.

This module intentionally has no shell, PM2, or pointer mutation operations. It
creates immutable intent and durable operation records; the core supervisor is
the only component allowed to materialise and activate a candidate. Explicit
uncertain-operation resolution is limited to read-only proof of an already
recovered local runtime before governance state is terminalized.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import sqlite3
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations
from . import lite_enterprise_identity


class PolicyLifecycleError(RuntimeError):
    def __init__(self, reason_code: str, message: str, *, status_code: int = 403):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.status_code = status_code


# A deliberately small allow-list is safer than accepting policy text. New
# templates need a source review and an explicit version bump.
TEMPLATES: dict[str, dict[str, Any]] = {
    "baseline": {"version": "1", "parameters": {}},
    "passkey_step_up": {
        "version": "1",
        "parameters": {"max_age_seconds": {"type": "integer", "minimum": 60, "maximum": 86_400, "default": 900}},
    },
}
NONTERMINAL_STATES = frozenset({"pending", "validating", "switching", "restarting", "verifying", "rolling_back", "uncertain"})
READ_ROLES = frozenset({"Owner", "Admin", "Operator", "Viewer", "Auditor"})
MUTATE_ROLES = frozenset({"Owner", "Admin"})
MANUAL_RECOVERY_EVIDENCE = "policy:manual-recovery-proved"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: str | bytes) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _actor(auth_context: dict[str, Any], *, mutate: bool) -> str:
    resolved = lite_enterprise_identity.enrich_auth_context(auth_context)
    actor = resolved.get("actor") or {}
    authorization = resolved.get("authorization") or {}
    human_id = str(actor.get("identity_id") or "")
    role = str(authorization.get("role") or "")
    required = MUTATE_ROLES if mutate else READ_ROLES
    if not human_id:
        raise PolicyLifecycleError("human_session_required", "A signed-in human session is required.", status_code=401)
    if not authorization.get("enterprise_enabled"):
        raise PolicyLifecycleError("enterprise_mode_disabled", "Enterprise Rules are unavailable in Personal Mode.", status_code=404)
    if not authorization.get("membership_active") or role not in required:
        raise PolicyLifecycleError("enterprise_rules_role_required", "Your Enterprise role is not authorized for this Rules action.")
    return human_id


def normalize_template(template_id: str, parameters: Any) -> tuple[str, str, dict[str, Any]]:
    """Normalize only approved typed input; policy source can never arrive here."""
    name = str(template_id or "").strip()
    definition = TEMPLATES.get(name)
    if definition is None:
        raise PolicyLifecycleError("policy_template_unknown", "Select an approved policy template.", status_code=422)
    if not isinstance(parameters, dict):
        raise PolicyLifecycleError("policy_parameters_invalid", "Policy parameters must be an object.", status_code=422)
    unknown = sorted(set(parameters) - set(definition["parameters"]))
    if unknown:
        raise PolicyLifecycleError("policy_parameter_unknown", "The policy request contains an unsupported parameter.", status_code=422)
    normalized: dict[str, Any] = {}
    for key, rule in definition["parameters"].items():
        raw = parameters.get(key, rule.get("default"))
        if rule["type"] == "integer" and (isinstance(raw, bool) or not isinstance(raw, int)):
            raise PolicyLifecycleError("policy_parameter_invalid", "A policy parameter has an invalid value.", status_code=422)
        if rule["type"] == "integer" and not rule["minimum"] <= raw <= rule["maximum"]:
            raise PolicyLifecycleError("policy_parameter_invalid", "A policy parameter is outside its approved range.", status_code=422)
        normalized[key] = raw
    return name, str(definition["version"]), normalized


def policy_source_tree(template_id: str, template_version: str, parameters: dict[str, Any]) -> tuple[str, dict[str, str]]:
    """Render the complete, allow-listed OPA runtime candidate deterministically.

    The request contributes only typed values. Every loaded Rego module is read
    from the repository-owned policy directory and the generated metadata is
    part of the returned tree, so the database manifest is a full candidate
    contract rather than a single-module convenience hash.
    """
    source = Path(__file__).resolve().parents[4] / "security" / "policies" / "opa" / "pocketlab"
    tree = {
        path.relative_to(source).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(source.rglob("*.rego"))
        if path.is_file()
    }
    if not tree:
        raise PolicyLifecycleError("policy_source_unavailable", "The approved policy source is unavailable.", status_code=503)
    tree["template.json"] = _canonical({"template_id": template_id, "template_version": template_version, "parameters": parameters}) + "\n"
    _seed_entries, seed = manifest_for_tree(tree)
    revision_id = "plr-" + seed[:32]
    tree["revision.rego"] = f'package pocketlab.meta\n\nrevision := "{revision_id}"\n'
    return revision_id, tree


def manifest_for_tree(tree: dict[str, str]) -> tuple[list[dict[str, str]], str]:
    entries = [{"path": path, "sha256": _hash(contents)} for path, contents in sorted(tree.items())]
    return entries, _hash(_canonical(entries))


def _public_revision(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    manifest = json.loads(data.pop("manifest_json"))
    data.pop("canonical_parameters_json", None)
    data["manifest"] = manifest
    return data


def _state_root() -> Path:
    configured = os.environ.get("POCKETLAB_STATE_DIR") or os.environ.get("STATE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".pocket_lab"


@contextlib.contextmanager
def _activation_lock() -> Any:
    lock_path = _state_root() / "opa" / "activation.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _stage_is_valid(revision: str) -> bool:
    stage = _state_root() / "opa" / "stage" / revision
    try:
        manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("revision") != revision or not isinstance(manifest.get("files"), list):
            return False
        for item in manifest["files"]:
            path = stage / str(item.get("path") or "")
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
                return False
        digest = hashlib.sha256(json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return digest == manifest.get("candidate_hash") and (stage / "revision.txt").read_text(encoding="utf-8").strip() == revision
    except Exception:
        return False


def _pointer_revision(pointer_name: str) -> str:
    state = _state_root()
    pointer = state / "opa" / pointer_name
    stage_root = state / "opa" / "stage"
    try:
        if not pointer.is_symlink():
            return ""
        resolved = pointer.resolve(strict=True)
        if resolved.parent.resolve(strict=True) != stage_root.resolve(strict=True):
            return ""
        revision = (resolved / "revision.txt").read_text(encoding="utf-8").strip()
        if not revision or resolved.name != revision or not _stage_is_valid(revision):
            return ""
        return revision
    except Exception:
        return ""


def _fetch_local_json(url: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=4) as response:  # nosec B310 - fixed loopback OPA probes only
            payload = response.read(256 * 1024).decode("utf-8", errors="replace")
        parsed = json.loads(payload)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _manual_recovery_proof(operation: sqlite3.Row | dict[str, Any]) -> str:
    data = dict(operation)
    active = _pointer_revision("active")
    known_good = _pointer_revision("known-good")
    if not active or active != known_good:
        raise PolicyLifecycleError("policy_recovery_pointer_mismatch", "Recovered policy pointers do not agree.", status_code=409)
    prior_known_good = str(data.get("prior_known_good_revision_id") or "")
    candidate = str(data.get("candidate_revision_id") or "")
    if prior_known_good and active != prior_known_good:
        raise PolicyLifecycleError("policy_recovery_revision_mismatch", "Recovered policy does not match the prior known-good revision.", status_code=409)
    if not prior_known_good and active == candidate:
        raise PolicyLifecycleError("policy_recovery_not_rollback", "Recovered policy still matches the uncertain candidate revision.", status_code=409)
    health = _fetch_local_json("http://127.0.0.1:8181/health")
    metadata = _fetch_local_json("http://127.0.0.1:8181/v1/data/pocketlab/meta/revision")
    observed = (metadata or {}).get("result")
    if health is None or not isinstance(observed, str) or observed != active:
        raise PolicyLifecycleError("policy_recovery_unproved", "Recovered OPA health and revision could not be proved.", status_code=409)
    return active


def create_revision(*, auth_context: dict[str, Any], template_id: str, parameters: Any, change_summary: str) -> dict[str, Any]:
    apply_migrations()
    actor = _actor(auth_context, mutate=True)
    name, version, normalized = normalize_template(template_id, parameters)
    summary = str(change_summary or "").strip()
    if not summary or len(summary) > 240:
        raise PolicyLifecycleError("policy_change_summary_invalid", "Provide a concise change summary.", status_code=422)
    canonical_parameters = _canonical(normalized)
    revision_id, tree = policy_source_tree(name, version, normalized)
    manifest, content_hash = manifest_for_tree(tree)
    # A revision is deterministic and immutable. The supervisor independently
    # recomputes the full runtime candidate manifest before activation.
    now = _now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            prior = tx.execute("SELECT revision_id FROM policy_revisions ORDER BY created_at DESC LIMIT 1").fetchone()
            tx.execute(
                """INSERT INTO policy_revisions(revision_id,parent_revision_id,template_id,template_version,canonical_parameters_json,manifest_json,content_hash,created_by_human_id,created_at,validation_status,validation_reason_code,lifecycle_status,change_summary)
                   VALUES (?,?,?,?,?,?,?,?,?,'pending','','draft',?)
                   ON CONFLICT(revision_id) DO NOTHING""",
                (revision_id, prior["revision_id"] if prior else None, name, version, canonical_parameters, _canonical({"files": manifest, "candidate_hash": content_hash}), content_hash, actor, now, summary),
            )
            row = tx.execute("SELECT * FROM policy_revisions WHERE revision_id=?", (revision_id,)).fetchone()
    return {"revision": _public_revision(row), "created": row["created_at"] == now}


def list_revisions(*, auth_context: dict[str, Any]) -> dict[str, Any]:
    apply_migrations(); _actor(auth_context, mutate=False)
    with connection() as conn:
        rows = conn.execute("SELECT * FROM policy_revisions ORDER BY created_at DESC LIMIT 100").fetchall()
    return {"revisions": [_public_revision(row) for row in rows]}


def read_revision(*, auth_context: dict[str, Any], revision_id: str) -> dict[str, Any]:
    apply_migrations(); _actor(auth_context, mutate=False)
    with connection() as conn:
        row = conn.execute("SELECT * FROM policy_revisions WHERE revision_id=?", (str(revision_id)[:80],)).fetchone()
    if not row:
        raise PolicyLifecycleError("policy_revision_unknown", "That policy revision does not exist.", status_code=404)
    return {"revision": _public_revision(row)}


def compare_revisions(*, auth_context: dict[str, Any], left_revision_id: str, right_revision_id: str) -> dict[str, Any]:
    left = read_revision(auth_context=auth_context, revision_id=left_revision_id)["revision"]
    right = read_revision(auth_context=auth_context, revision_id=right_revision_id)["revision"]
    changed = {key: {"left": left.get(key), "right": right.get(key)} for key in ("template_id", "template_version", "content_hash", "validation_status", "lifecycle_status", "change_summary") if left.get(key) != right.get(key)}
    return {"left": left, "right": right, "changed": changed}


def _admit_operation(*, auth_context: dict[str, Any], candidate_revision_id: str, correlation_id: str | None) -> dict[str, Any]:
    actor = _actor(auth_context, mutate=True)
    now = _now(); operation_id = "plo-" + uuid.uuid4().hex
    with connection() as conn:
        try:
            with begin_immediate(conn) as tx:
                revision = tx.execute("SELECT revision_id FROM policy_revisions WHERE revision_id=?", (candidate_revision_id,)).fetchone()
                if not revision:
                    raise PolicyLifecycleError("policy_revision_unknown", "That policy revision does not exist.", status_code=404)
                runtime = tx.execute("SELECT known_good_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
                tx.execute(
                    """INSERT INTO policy_activation_operations(operation_id,requested_by_human_id,correlation_id,candidate_revision_id,prior_known_good_revision_id,state,created_at,updated_at)
                       VALUES (?,?,?,?,?,'pending',?,?)""",
                    (operation_id, actor, str(correlation_id or uuid.uuid4().hex)[:80], candidate_revision_id, runtime["known_good_revision_id"] if runtime else None, now, now),
                )
        except sqlite3.IntegrityError as exc:
            if "single_nonterminal" in str(exc).lower() or "unique" in str(exc).lower():
                raise PolicyLifecycleError("policy_activation_in_progress", "A policy activation is already in progress.", status_code=409) from exc
            raise
    return read_operation(auth_context=auth_context, operation_id=operation_id)


def request_activation(*, auth_context: dict[str, Any], revision_id: str, correlation_id: str | None = None) -> dict[str, Any]:
    apply_migrations()
    return _admit_operation(auth_context=auth_context, candidate_revision_id=str(revision_id)[:80], correlation_id=correlation_id)


def request_rollback(*, auth_context: dict[str, Any], correlation_id: str | None = None) -> dict[str, Any]:
    apply_migrations(); _actor(auth_context, mutate=True)
    with connection() as conn:
        state = conn.execute("SELECT known_good_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
    revision_id = str(state["known_good_revision_id"] if state else "")
    if not revision_id:
        raise PolicyLifecycleError("policy_known_good_unavailable", "No proved known-good policy revision is available.", status_code=409)
    return _admit_operation(auth_context=auth_context, candidate_revision_id=revision_id, correlation_id=correlation_id)


def resolve_uncertain_operation(*, auth_context: dict[str, Any], operation_id: str) -> dict[str, Any]:
    """Terminalize only an already recovered uncertain operation after local proof.

    The caller supplies only the operation identifier. The recovered revision,
    filesystem pointers, staged hashes, OPA health, and OPA metadata revision are
    derived locally. This function never switches a pointer or restarts OPA.
    """
    apply_migrations()
    actor = _actor(auth_context, mutate=True)
    bounded_operation_id = str(operation_id or "")[:80]
    with _activation_lock():
        with connection() as conn:
            operation = conn.execute("SELECT * FROM policy_activation_operations WHERE operation_id=?", (bounded_operation_id,)).fetchone()
        if not operation:
            raise PolicyLifecycleError("policy_activation_unknown", "That policy activation operation does not exist.", status_code=404)
        if operation["state"] != "uncertain":
            raise PolicyLifecycleError("policy_activation_not_uncertain", "Only an uncertain policy activation can be resolved this way.", status_code=409)
        recovered_revision = _manual_recovery_proof(operation)
        resolved_at = _now()
        resolution_id = "plx-" + uuid.uuid4().hex
        original_reason = str(operation["reason_code"] or "policy_activation_uncertain")[:80]
        with connection() as conn:
            with begin_immediate(conn) as tx:
                current = tx.execute("SELECT state,reason_code FROM policy_activation_operations WHERE operation_id=?", (bounded_operation_id,)).fetchone()
                if not current or current["state"] != "uncertain":
                    raise PolicyLifecycleError("policy_activation_state_changed", "The policy activation changed while recovery was being proved.", status_code=409)
                tx.execute(
                    """INSERT INTO policy_recovery_resolutions(
                           resolution_id,operation_id,requested_by_human_id,requested_at,resolved_at,
                           original_reason_code,recovered_revision_id,status,evidence_ref,summary
                       ) VALUES (?,?,?,?,?,?,?,'proved',?,?)""",
                    (
                        resolution_id,
                        bounded_operation_id,
                        actor,
                        resolved_at,
                        resolved_at,
                        original_reason,
                        recovered_revision,
                        MANUAL_RECOVERY_EVIDENCE,
                        "Operator-restored policy runtime matched validated known-good filesystem and OPA evidence.",
                    ),
                )
                updated = tx.execute(
                    """UPDATE policy_activation_operations
                       SET state='rolled_back',updated_at=?,observed_filesystem_revision=?,observed_opa_revision=?,evidence_ref=?
                       WHERE operation_id=? AND state='uncertain'""",
                    (resolved_at, recovered_revision, recovered_revision, MANUAL_RECOVERY_EVIDENCE, bounded_operation_id),
                )
                if updated.rowcount != 1:
                    raise PolicyLifecycleError("policy_activation_state_changed", "The policy activation changed while recovery was being recorded.", status_code=409)
                resolution = tx.execute("SELECT * FROM policy_recovery_resolutions WHERE resolution_id=?", (resolution_id,)).fetchone()
                terminal = tx.execute("SELECT * FROM policy_activation_operations WHERE operation_id=?", (bounded_operation_id,)).fetchone()
    return {"operation": dict(terminal), "resolution": dict(resolution)}


def read_operation(*, auth_context: dict[str, Any], operation_id: str) -> dict[str, Any]:
    apply_migrations(); _actor(auth_context, mutate=False)
    with connection() as conn:
        row = conn.execute("SELECT * FROM policy_activation_operations WHERE operation_id=?", (str(operation_id)[:80],)).fetchone()
    if not row:
        raise PolicyLifecycleError("policy_activation_unknown", "That policy activation operation does not exist.", status_code=404)
    return {"operation": dict(row)}


def consistency_projection(*, auth_context: dict[str, Any]) -> dict[str, Any]:
    apply_migrations(); _actor(auth_context, mutate=False)
    with connection() as conn:
        state = conn.execute("SELECT * FROM policy_runtime_state WHERE state_id=1").fetchone()
        operation = conn.execute("SELECT * FROM policy_activation_operations WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain') ORDER BY created_at DESC LIMIT 1").fetchone()
    return {"runtime": dict(state) if state else {"active_revision_id": None, "known_good_revision_id": None}, "operation": dict(operation) if operation else None, "consistent": bool(state and not operation and state["active_revision_id"] and state["active_revision_id"] == state["known_good_revision_id"])}
