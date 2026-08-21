from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlsplit
from pathlib import Path
from typing import Any

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations
from .lite_security_policy import redact_value

OPA_BASE_URL = os.environ.get("POCKETLAB_OPA_URL", "http://127.0.0.1:8181").rstrip("/")
OPA_DECISION_PATH = "/v1/data/pocketlab/authz/decision"
OPA_REVISION_PATH = "/v1/data/pocketlab/meta/revision"
PROTECTED_ACTIONS = frozenset({"catalog.install", "device.remove", "identity.passkey.revoke"})


class PolicyDecisionError(RuntimeError):
    def __init__(self, reason_code: str, message: str, *, status_code: int = 403, decision: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason_code = str(reason_code or "policy_denied")[:80]
        self.message = str(message or "This action is blocked by Safety Rules.")[:240]
        self.status_code = int(status_code)
        self.decision = decision or {}


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    return min(max(value, minimum), maximum)


def _policy_root() -> Path:
    configured = os.environ.get("POCKETLAB_OPA_ACTIVE_POLICY_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    state_dir = os.environ.get("POCKETLAB_STATE_DIR", "").strip()
    if state_dir:
        return Path(state_dir).expanduser() / "opa" / "active"
    return Path.home() / ".pocket_lab" / "state" / "opa" / "active"


def _safe_revision() -> str:
    root = _policy_root()
    revision_file = root / "revision.txt"
    try:
        value = revision_file.read_text(encoding="utf-8").strip()
        if value:
            return value[:80]
    except OSError:
        pass
    policy_file = root / "pocketlab.rego"
    try:
        data = policy_file.read_bytes()
    except OSError:
        return "unavailable"
    return hashlib.sha256(data).hexdigest()[:24]


def _observed_opa_revision() -> str | None:
    """Parse only the OPA 1.x data API shape: {"result": "revision"}."""
    try:
        status, payload = _http_json("GET", OPA_REVISION_PATH, timeout=0.25)
    except Exception:
        return None
    result = payload.get("result") if status == 200 else None
    if not isinstance(result, str) or not 8 <= len(result) <= 80:
        return None
    return result


def _policy_consistency() -> tuple[bool, str, str | None]:
    """Require durable, filesystem and OPA-loaded revision agreement in Enterprise Mode.

    Absence of P2.2 state is deliberately compatible with Personal Mode and the
    existing P1 rules runtime.  A present state is strict/fail-closed.
    """
    try:
        with connection() as conn:
            state = conn.execute("SELECT active_revision_id,known_good_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
            operation = conn.execute("SELECT state FROM policy_activation_operations WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain') LIMIT 1").fetchone()
    except sqlite3.OperationalError:
        return True, "", None
    if operation:
        return False, "policy_revision_uncertain" if operation["state"] == "uncertain" else "policy_activation_pending", None
    if not state or not state["active_revision_id"]:
        return True, "", None
    expected = str(state["active_revision_id"])
    if str(state["known_good_revision_id"] or "") != expected or _safe_revision() != expected:
        return False, "policy_revision_mismatch", None
    observed = _observed_opa_revision()
    if observed != expected:
        return False, "policy_revision_mismatch" if observed else "policy_revision_uncertain", observed
    return True, "", observed




def _opa_endpoint_is_loopback() -> bool:
    try:
        parsed = urlsplit(OPA_BASE_URL)
        host = (parsed.hostname or "").strip().casefold()
        if parsed.scheme != "http" or not host or parsed.username or parsed.password or parsed.query or parsed.fragment:
            return False
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False
    except ValueError:
        return False


def _require_loopback_opa() -> None:
    if not _opa_endpoint_is_loopback():
        raise PolicyDecisionError(
            "policy_endpoint_not_loopback",
            "Safety Rules are configured with a non-local policy endpoint, so protected actions are blocked.",
            status_code=503,
        )

def _http_json(method: str, path: str, payload: dict[str, Any] | None = None, *, timeout: float | None = None) -> tuple[int, dict[str, Any]]:
    bounded = timeout if timeout is not None else float(os.environ.get("POCKETLAB_OPA_TIMEOUT_SECONDS", "0.35"))
    bounded = max(0.05, min(2.0, float(bounded)))
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{OPA_BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=bounded) as response:  # noqa: S310 - loopback-only configured endpoint
            raw = response.read(128 * 1024)
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
            return int(response.status), parsed if isinstance(parsed, dict) else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read(16 * 1024)
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            parsed = {}
        return int(exc.code), parsed if isinstance(parsed, dict) else {}


def _normalized_actor(auth_context: dict[str, Any] | None) -> dict[str, str | int | None]:
    actor = (auth_context or {}).get("actor") or {}
    actor_type = str(actor.get("type") or "anonymous").strip().lower()[:32]
    actor_id = str(actor.get("identity_id") or "anonymous").strip()[:120]
    display = str(actor.get("display_name") or actor_id).strip()[:120]
    authorization = (auth_context or {}).get("authorization") or {}
    role = authorization.get("role")
    safe_role = str(role)[:16] if role in {"Owner", "Admin", "Operator", "Viewer", "Auditor"} else None
    try:
        authorization_version = max(1, min(2_147_483_647, int(authorization.get("authorization_version") or 1)))
    except (TypeError, ValueError):
        authorization_version = 1
    identity_class = str(authorization.get("identity_class") or actor_type or "anonymous")[:40]
    return {
        "type": actor_type or "anonymous",
        "id": actor_id or "anonymous",
        "display_name": display or "anonymous",
        "role": safe_role,
        "authorization_version": authorization_version,
        "identity_class": identity_class,
        "enterprise_enabled": bool(authorization.get("enterprise_enabled")),
    }


def build_authorization_input(
    *,
    auth_context: dict[str, Any] | None,
    action_id: str,
    target_type: str,
    target_id: str,
    target_revision: str,
    target: dict[str, Any] | None = None,
    request_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actor = _normalized_actor(auth_context)
    session = (auth_context or {}).get("session") or {}
    assurance = []
    for item in session.get("assurance") or []:
        if not isinstance(item, dict):
            continue
        assurance.append({
            "purpose": str(item.get("purpose") or "")[:80],
            "credential_id": str(item.get("credential_id") or "")[:256],
            "satisfied_at": str(item.get("satisfied_at") or "")[:40],
            "expires_at": str(item.get("expires_at") or "")[:40],
        })
    return {
        "actor": actor,
        "session": {
            "authenticated": bool(session.get("authenticated")),
            "auth_method": str(session.get("auth_method") or (auth_context or {}).get("auth_method") or "")[:48],
            "assurance": assurance[:8],
        },
        "action": {"id": str(action_id)[:120]},
        "target": {
            "type": str(target_type or "unknown")[:80],
            "id": str(target_id or "unknown")[:160],
            "revision": str(target_revision or "unknown")[:160],
            "state": redact_value(target or {}),
        },
        "request": redact_value(request_context or {}),
    }


def _test_decision(input_doc: dict[str, Any]) -> dict[str, Any] | None:
    actor = input_doc.get("actor") or {}
    if os.environ.get("POCKETLAB_TEST_AUTH_BYPASS") == "1" and actor.get("type") == "test":
        return {
            "allow": True,
            "constraints": [],
            "reason_code": "test_bypass_explicit",
            "policy_revision": "test-only",
        }
    return None


def _validate_result(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise PolicyDecisionError("policy_invalid_response", "Safety Rules returned an invalid decision.", status_code=503)
    allow = raw.get("allow")
    reason = raw.get("reason_code")
    constraints = raw.get("constraints", [])
    if not isinstance(allow, bool) or not isinstance(reason, str) or not reason.strip() or not isinstance(constraints, list):
        raise PolicyDecisionError("policy_invalid_response", "Safety Rules returned an invalid decision.", status_code=503)
    requirements = raw.get("requirements", {})
    if not isinstance(requirements, dict):
        raise PolicyDecisionError("policy_invalid_response", "Safety Rules returned an invalid decision.", status_code=503)
    allowed_requirement_keys = {"required_approver_roles", "required_assurance", "approval_lifetime_seconds"}
    if set(requirements) - allowed_requirement_keys:
        raise PolicyDecisionError("policy_invalid_response", "Safety Rules returned an invalid decision.", status_code=503)
    roles = requirements.get("required_approver_roles", [])
    assurance = requirements.get("required_assurance", "")
    lifetime = requirements.get("approval_lifetime_seconds")
    if not isinstance(roles, list) or any(item not in {"Owner", "Admin"} for item in roles) or not isinstance(assurance, str):
        raise PolicyDecisionError("policy_invalid_response", "Safety Rules returned an invalid decision.", status_code=503)
    if lifetime is not None and (not isinstance(lifetime, int) or not 1 <= lifetime <= 900):
        raise PolicyDecisionError("policy_invalid_response", "Safety Rules returned an invalid decision.", status_code=503)
    normalized_requirements: dict[str, Any] = {}
    if roles:
        normalized_requirements["required_approver_roles"] = roles[:2]
    if assurance:
        normalized_requirements["required_assurance"] = assurance[:80]
    if lifetime is not None:
        normalized_requirements["approval_lifetime_seconds"] = lifetime
    return {
        "allow": allow,
        "constraints": [str(item)[:120] for item in constraints[:12]],
        "reason_code": reason.strip()[:80],
        "policy_revision": str(raw.get("policy_revision") or _safe_revision())[:80],
        "requirements": normalized_requirements,
    }


def _server_continuation_facts(input_doc: dict[str, Any]) -> tuple[str | None, str | None]:
    """Resolve continuation state exclusively from durable server records.

    The browser never supplies an approval or exception claim.  An approval is
    scoped to the active candidate revision before OPA evaluates the retry.
    """
    actor = input_doc["actor"]
    try:
        from . import lite_policy_approvals

        revision = _safe_revision()
        if input_doc["action"]["id"] == "device.remove" and input_doc["target"]["type"] == "device" and actor.get("role") in {"Owner", "Admin", "Operator"}:
            return lite_policy_approvals.matching_approved(
                initiating_human_id=str(actor["id"]), action_id="device.remove", target_type="device",
                target_id=str(input_doc["target"]["id"]), policy_revision=revision,
            ), None
        if input_doc["action"]["id"] == "catalog.install" and input_doc["target"]["type"] == "app":
            device_id = str((input_doc["target"].get("state") or {}).get("target_node_id") or "").strip()
            if device_id:
                return None, lite_policy_approvals.matching_exception(
                    human_id=str(actor["id"]), app_id=str(input_doc["target"]["id"]), device_id=device_id, policy_revision=revision,
                )
    except Exception:
        # An unavailable continuation store must not become a grant.  OPA will
        # return approval_required and the original action remains blocked.
        pass
    return None, None


def _record_decision(*, input_doc: dict[str, Any], decision: dict[str, Any], evaluation_ms: float, correlation_id: str) -> dict[str, Any]:
    apply_migrations()
    decision_id = f"decision-{uuid.uuid4().hex}"
    actor = input_doc["actor"]
    target = input_doc["target"]
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO policy_decisions(
                       occurred_at,decision_id,correlation_id,actor_type,actor_id,action_id,
                       target_type,target_id,target_revision,allow,reason_code,policy_revision,evaluation_ms
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    _now_iso(),
                    decision_id,
                    correlation_id[:80],
                    actor["type"],
                    actor["id"],
                    input_doc["action"]["id"],
                    target["type"],
                    target["id"],
                    target["revision"],
                    1 if decision["allow"] else 0,
                    decision["reason_code"],
                    decision["policy_revision"],
                    round(max(0.0, evaluation_ms), 3),
                ),
            )
            retention = _bounded_int("POCKETLAB_POLICY_DECISION_RETENTION", 500, 50, 5000)
            tx.execute(
                "DELETE FROM policy_decisions WHERE decision_row_id NOT IN (SELECT decision_row_id FROM policy_decisions ORDER BY decision_row_id DESC LIMIT ?)",
                (retention,),
            )
            try:
                tx.execute(
                    "INSERT OR REPLACE INTO policy_decision_details(decision_id,constraints_json,evidence_ref) VALUES (?,?,?)",
                    (decision_id, json.dumps(decision.get("constraints") or [], separators=(",", ":")), f"policy:{decision_id}"),
                )
            except Exception:
                # Migration may not be present during a rolling upgrade; the core
                # deny/allow decision must remain authoritative and fail-closed.
                pass
    return {**decision, "decision_id": decision_id, "correlation_id": correlation_id, "evaluation_ms": round(max(0.0, evaluation_ms), 3)}


def evaluate_authorization(
    *,
    auth_context: dict[str, Any] | None,
    action_id: str,
    target_type: str,
    target_id: str,
    target_revision: str,
    target: dict[str, Any] | None = None,
    request_context: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    action = str(action_id or "").strip()
    if action not in PROTECTED_ACTIONS:
        raise PolicyDecisionError("policy_action_not_registered", "This action has no registered Safety Rule.", status_code=503)
    input_doc = build_authorization_input(
        auth_context=auth_context,
        action_id=action,
        target_type=target_type,
        target_id=target_id,
        target_revision=target_revision,
        target=target,
        request_context=request_context,
    )
    continuation_id, exception_id = _server_continuation_facts(input_doc)
    input_doc["continuation"] = {
        "matching_independent_approval": bool(continuation_id),
        "matching_temporary_exception": bool(exception_id),
    }
    started = time.monotonic()
    test = _test_decision(input_doc)
    try:
        _require_loopback_opa()
        consistent, consistency_reason, observed_revision = _policy_consistency()
        if not consistent:
            raise PolicyDecisionError(consistency_reason, "Safety Rules revision consistency is not proved, so this protected action was not started.", status_code=503)
        if test is not None:
            normalized = _validate_result(test)
        else:
            status_code, payload = _http_json("POST", OPA_DECISION_PATH, {"input": input_doc})
            if status_code != 200:
                raise PolicyDecisionError("policy_unavailable", "Safety Rules are not ready, so this protected action was not started.", status_code=503)
            normalized = _validate_result(payload.get("result"))
            if observed_revision:
                normalized["policy_revision"] = observed_revision
    except PolicyDecisionError as exc:
        elapsed = (time.monotonic() - started) * 1000.0
        failed = _record_decision(
            input_doc=input_doc,
            decision={
                "allow": False,
                "constraints": [],
                "reason_code": exc.reason_code,
                "policy_revision": _safe_revision(),
            },
            evaluation_ms=elapsed,
            correlation_id=str(correlation_id or uuid.uuid4().hex),
        )
        raise PolicyDecisionError(exc.reason_code, exc.message, status_code=exc.status_code, decision=failed) from exc
    except (OSError, TimeoutError, urllib.error.URLError, ValueError, json.JSONDecodeError) as exc:
        elapsed = (time.monotonic() - started) * 1000.0
        failed = _record_decision(
            input_doc=input_doc,
            decision={
                "allow": False,
                "constraints": [],
                "reason_code": "policy_unavailable",
                "policy_revision": _safe_revision(),
            },
            evaluation_ms=elapsed,
            correlation_id=str(correlation_id or uuid.uuid4().hex),
        )
        raise PolicyDecisionError("policy_unavailable", "Safety Rules are not ready, so this protected action was not started.", status_code=503, decision=failed) from exc
    elapsed = (time.monotonic() - started) * 1000.0
    recorded = _record_decision(
        input_doc=input_doc,
        decision=normalized,
        evaluation_ms=elapsed,
        correlation_id=str(correlation_id or uuid.uuid4().hex),
    )
    if continuation_id and recorded["allow"]:
        recorded["continuation_approval_id"] = continuation_id
    if exception_id and recorded["allow"]:
        recorded["continuation_exception_id"] = exception_id
    if not recorded["allow"]:
        if recorded.get("reason_code") == "approval_required":
            try:
                from . import lite_policy_approvals

                approval = lite_policy_approvals.create_from_decision(
                    decision_id=recorded["decision_id"],
                    initiating_role=str(input_doc["actor"].get("role") or ""),
                )["approval"]
            except Exception as exc:
                raise PolicyDecisionError(
                    "approval_record_unavailable",
                    "Independent approval could not be recorded, so the device removal remains blocked.",
                    status_code=503,
                    decision=recorded,
                ) from exc
            recorded["approval"] = approval
            raise PolicyDecisionError(
                "approval_required",
                "An independent active Enterprise Owner or Admin must approve this device removal. No removal has started.",
                status_code=409,
                decision=recorded,
            )
        if recorded.get("reason_code") == "passkey_step_up_required":
            raise PolicyDecisionError(
                "passkey_step_up_required",
                "Confirm this sensitive change with your passkey, then try it again.",
                status_code=428,
                decision=recorded,
            )
        raise PolicyDecisionError("policy_denied", "Safety Rules blocked this action.", status_code=403, decision=recorded)
    return recorded


def decision_detail(decision_id: str) -> dict[str, Any] | None:
    apply_migrations()
    with connection() as conn:
        row = conn.execute(
            """SELECT occurred_at,decision_id,correlation_id,actor_type,action_id,target_type,target_id,
                      target_revision,allow,reason_code,policy_revision,evaluation_ms
               FROM policy_decisions WHERE decision_id=? LIMIT 1""",
            (str(decision_id)[:120],),
        ).fetchone()
        if not row:
            return None
        item = dict(row)
        detail = conn.execute(
            "SELECT constraints_json,evidence_ref FROM policy_decision_details WHERE decision_id=? LIMIT 1",
            (item["decision_id"],),
        ).fetchone()
    constraints = []
    evidence_ref = None
    if detail:
        try:
            constraints = json.loads(detail["constraints_json"] or "[]")
        except Exception:
            constraints = []
        evidence_ref = detail["evidence_ref"]
    return {
        "occurred_at": item["occurred_at"],
        "decision_id": item["decision_id"],
        "correlation_id": item["correlation_id"],
        "actor_type": item["actor_type"],
        "action_id": item["action_id"],
        "target_type": item["target_type"],
        "target_id": item["target_id"],
        "target_revision": item["target_revision"],
        "allow": bool(item["allow"]),
        "reason_code": item["reason_code"],
        "policy_revision": item["policy_revision"],
        "evaluation_ms": item["evaluation_ms"],
        "constraints": [str(value)[:120] for value in constraints[:12]],
        "evidence_ref": str(evidence_ref or "")[:160] or None,
        "raw_input_exposed": False,
    }


def list_decisions(*, action_id: str = "", allowed: bool | None = None, reason_code: str = "", policy_revision: str = "", target_type: str = "", limit: int = 50, cursor: int | None = None) -> dict[str, Any]:
    """Bounded, deterministic explorer over existing sanitized decision evidence."""
    safe_limit = max(1, min(int(limit), 100))
    clauses: list[str] = []; values: list[Any] = []
    for column, value in (("action_id", action_id), ("reason_code", reason_code), ("policy_revision", policy_revision), ("target_type", target_type)):
        if value:
            clauses.append(f"{column}=?"); values.append(str(value)[:160])
    if allowed is not None:
        clauses.append("allow=?"); values.append(1 if allowed else 0)
    if cursor is not None:
        clauses.append("decision_row_id<?"); values.append(max(0, int(cursor)))
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with connection() as conn:
        rows = conn.execute(f"SELECT decision_row_id,occurred_at,decision_id,correlation_id,actor_type,actor_id,action_id,target_type,target_id,allow,reason_code,policy_revision,evaluation_ms FROM policy_decisions{where} ORDER BY decision_row_id DESC LIMIT ?", (*values, safe_limit + 1)).fetchall()
    items = [dict(row) for row in rows[:safe_limit]]
    for item in items:
        item["allow"] = bool(item["allow"]); item.pop("decision_row_id", None); item["raw_input_exposed"] = False
    next_cursor = rows[safe_limit - 1]["decision_row_id"] if len(rows) > safe_limit else None
    return {"decisions": items, "next_cursor": next_cursor, "limit": safe_limit, "raw_input_exposed": False}


def policy_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": "destructive_confirmation",
            "label": "Confirm destructive changes",
            "summary": "Requires an explicit confirmation before destructive device cleanup.",
            "status": "active",
            "enforcement": "FastAPI hard guard + Safety Rules context",
            "actions": ["device.remove"],
        },
        {
            "id": "healthy_device_removal_protection",
            "label": "Protect healthy devices",
            "summary": "Keeps device-removal safety assessment and protected-server-host checks outside editable policy.",
            "status": "active",
            "enforcement": "FastAPI hard guard",
            "actions": ["device.remove"],
        },
        {
            "id": "passkey_step_up",
            "label": "Passkey confirmation for sensitive Identity changes",
            "summary": "Requires a recent server-verified passkey step-up before removing a passkey.",
            "status": "active",
            "enforcement": "OPA with server-derived assurance",
            "actions": ["identity.passkey.revoke"],
        },
    ]


def policy_status() -> dict[str, Any]:
    revision = _safe_revision()
    healthy = False
    engine_version = "unknown"
    error_code = "policy_engine_unavailable"
    try:
        _require_loopback_opa()
        status_code, _ = _http_json("GET", "/health", timeout=0.25)
        healthy = status_code == 200
        if healthy:
            error_code = ""
            try:
                version_status, version_payload = _http_json("GET", "/version", timeout=0.25)
                if version_status == 200:
                    engine_version = str(version_payload.get("version") or "unknown")[:40]
            except Exception:
                engine_version = "unknown"
    except PolicyDecisionError as exc:
        healthy = False
        error_code = exc.reason_code
    except Exception:
        healthy = False
    recent: list[dict[str, Any]] = []
    try:
        with connection() as conn:
            rows = conn.execute(
                """SELECT occurred_at,decision_id,correlation_id,actor_type,action_id,target_type,target_id,
                          allow,reason_code,policy_revision,evaluation_ms
                   FROM policy_decisions ORDER BY decision_row_id DESC LIMIT 20"""
            ).fetchall()
            recent = [
                {
                    "occurred_at": row["occurred_at"],
                    "decision_id": row["decision_id"],
                    "correlation_id": row["correlation_id"],
                    "actor_type": row["actor_type"],
                    "action_id": row["action_id"],
                    "target_type": row["target_type"],
                    "target_id": row["target_id"],
                    "allow": bool(row["allow"]),
                    "reason_code": row["reason_code"],
                    "policy_revision": row["policy_revision"],
                    "evaluation_ms": row["evaluation_ms"],
                }
                for row in rows
            ]
    except Exception:
        recent = []
    ready = healthy and revision != "unavailable"
    last_decision_at = recent[0]["occurred_at"] if recent else None
    return {
        "status": "ready" if ready else "degraded",
        "summary": "Safety Rules are active and ready for protected changes." if ready else "Safety Rules are not ready. Protected changes fail closed until they recover.",
        "degraded_reason": "" if ready else (error_code or "policy_not_activated"),
        "engine": {
            "name": "Open Policy Agent",
            "version": engine_version,
            "healthy": healthy,
            "loopback_only": _opa_endpoint_is_loopback(),
            "endpoint_exposed_to_browser": False,
            "reason_code": error_code,
        },
        "active_policy": {
            "revision": revision,
            "bundle_ready": revision != "unavailable",
            "package_status": "active" if revision != "unavailable" else "unavailable",
            "protected_actions": sorted(PROTECTED_ACTIONS),
            "activation_model": "atomic_local_copy",
            "last_known_good": revision != "unavailable",
        },
        "last_decision_at": last_decision_at,
        "policy_groups": [
            {"id": "apps", "label": "Apps", "actions": ["catalog.install"]},
            {"id": "devices", "label": "Devices", "actions": ["device.remove"]},
            {"id": "identity", "label": "Identity", "actions": ["identity.passkey.revoke"]},
        ],
        "templates": policy_templates(),
        "recent_decisions": recent,
        "updated_at": _now_iso(),
    }
