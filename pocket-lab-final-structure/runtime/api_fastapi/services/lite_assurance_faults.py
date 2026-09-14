"""Fixed qualification-only service interruption controls.

The fault registry is deliberately smaller than the supervisor's general
recovery surface.  Callers select one registered identifier and confirm the
reviewed action; they cannot supply a service name, signal, PID, command,
environment, or restart reason.  The core supervisor remains the owner of the
actual PM2 action and its restart budget.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
FAULTS_REGISTRY_PATH = REPOSITORY_ROOT / "security" / "assurance" / "faults.yaml"
TARGET_SCOPE = "local_server_host_only"
PROFILE = "security-assurance-runner"
PURPOSE = "security.assurance"
REQUIRED_CAPABILITY = "security.assurance.fault_control"
ALLOWED_SERVICES = frozenset({"pocket-worker", "pocket-nats", "pocket-opa"})
ALLOWED_ROLES = frozenset({"worker", "nats", "policy"})
ALLOWED_PROBES = frozenset({
    "worker_online_and_api_nats",
    "nats_tcp_jetstream_worker",
    "opa_health_and_revision",
})
SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789._-")

_USE_LOCK = threading.RLock()
_USED_FAULTS: set[str] = set()


class FaultControlError(RuntimeError):
    def __init__(self, reason_code: str, message: str, *, status_code: int = 403):
        super().__init__(message)
        self.reason_code = str(reason_code or "fault_control_rejected")[:80]
        self.message = str(message or "The qualification fault was rejected.")[:240]
        self.status_code = int(status_code)


def _bounded_file(path: Path) -> bytes:
    try:
        if not path.is_file() or path.stat().st_size > 128 * 1024:
            raise OSError("fault registry unavailable")
        return path.read_bytes()
    except OSError as exc:
        raise FaultControlError(
            "fault_registry_unavailable",
            "The qualification fault registry is unavailable.",
            status_code=503,
        ) from exc


def _registry() -> dict[str, Any]:
    try:
        value = yaml.safe_load(_bounded_file(FAULTS_REGISTRY_PATH).decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise FaultControlError(
            "fault_registry_invalid",
            "The qualification fault registry is invalid.",
            status_code=503,
        ) from exc
    if not isinstance(value, dict) or not isinstance(value.get("faults"), list):
        raise FaultControlError(
            "fault_registry_invalid",
            "The qualification fault registry is invalid.",
            status_code=503,
        )
    return value


def _safe_id(value: Any) -> str:
    result = str(value or "").strip().casefold()
    if not result or len(result) > 80 or result[0] not in "abcdefghijklmnopqrstuvwxyz" or any(char not in SAFE_ID_CHARS for char in result):
        raise FaultControlError("fault_unknown", "The qualification fault is not registered.", status_code=400)
    return result


def validate_registry() -> dict[str, Any]:
    payload = _registry()
    if str(payload.get("schema_version") or "") != "1.0.0" or str(payload.get("target_scope") or "") != TARGET_SCOPE or str(payload.get("required_capability") or "") != REQUIRED_CAPABILITY:
        raise FaultControlError("fault_registry_invalid", "The qualification fault registry is invalid.", status_code=503)
    seen: set[str] = set()
    clean: list[dict[str, Any]] = []
    for item in payload["faults"]:
        if not isinstance(item, Mapping):
            raise FaultControlError("fault_registry_invalid", "A qualification fault entry is invalid.", status_code=503)
        identifier = _safe_id(item.get("id"))
        service = str(item.get("service_name") or "")
        role = str(item.get("service_role") or "")
        probe = str(item.get("probe") or "")
        if identifier in seen or service not in ALLOWED_SERVICES or role not in ALLOWED_ROLES or str(item.get("operation") or "") != "restart" or str(item.get("safety_class") or "") != "SAFE_ACTIVE" or probe not in ALLOWED_PROBES or not isinstance(item.get("max_uses"), int) or item.get("max_uses") != 1:
            raise FaultControlError("fault_registry_invalid", "A qualification fault entry is invalid.", status_code=503)
        try:
            timeout = int(item.get("recovery_timeout_seconds") or 0)
        except (TypeError, ValueError):
            timeout = 0
        if timeout not in range(5, 181) or (role == "worker" and probe != "worker_online_and_api_nats") or (role == "nats" and probe != "nats_tcp_jetstream_worker") or (role == "policy" and probe != "opa_health_and_revision"):
            raise FaultControlError("fault_registry_invalid", "A qualification fault entry has an unsafe recovery policy.", status_code=503)
        seen.add(identifier)
        clean.append({
            "id": identifier,
            "service_role": role,
            "service_name": service,
            "operation": "restart",
            "safety_class": "SAFE_ACTIVE",
            "recovery_timeout_seconds": timeout,
            "max_uses": 1,
            "probe": probe,
        })
    expected = {"worker_restart_once", "nats_restart_once", "opa_restart_once"}
    if {item["id"] for item in clean} != expected:
        raise FaultControlError("fault_registry_invalid", "The qualification fault registry is incomplete.", status_code=503)
    return {
        "schema_version": "1.0.0",
        "target_scope": TARGET_SCOPE,
        "required_capability": REQUIRED_CAPABILITY,
        "faults": clean,
        "sanitized": True,
    }


def list_faults() -> dict[str, Any]:
    return validate_registry()


def fault_def(fault_id: Any) -> dict[str, Any]:
    identifier = _safe_id(fault_id)
    for item in validate_registry()["faults"]:
        if item["id"] == identifier:
            return dict(item)
    raise FaultControlError("fault_unknown", "The qualification fault is not registered.", status_code=400)


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _require_context(auth_context: Mapping[str, Any]) -> tuple[str, str]:
    harness = auth_context.get("harness") if isinstance(auth_context, Mapping) else None
    authorization = auth_context.get("authorization") if isinstance(auth_context, Mapping) else None
    if not isinstance(harness, Mapping) or not isinstance(authorization, Mapping):
        raise FaultControlError("fault_control_denied", "A signed assurance session is required for a fault control.", status_code=403)
    capabilities = {str(value) for value in harness.get("capabilities") or []}
    if (
        harness.get("enabled") is not True
        or harness.get("qualification_environment") is not True
        or harness.get("profile") != PROFILE
        or harness.get("purpose") != PURPOSE
        or harness.get("principal_class") != "qualification"
        or harness.get("target_scope") != TARGET_SCOPE
        or harness.get("destructive_allowed") is True
        or REQUIRED_CAPABILITY not in capabilities
        or authorization.get("role") is not None
        or authorization.get("owner_authority") is True
        or authorization.get("identity_class") != "synthetic_machine"
    ):
        raise FaultControlError("fault_control_denied", "The signed session is not authorized for a qualification fault control.", status_code=403)
    if (
        os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() != "qualification"
        or not _flag("POCKETLAB_HARNESS_ENABLED")
        or not _flag("POCKETLAB_HARNESS_FAULT_CONTROL")
        or _flag("POCKETLAB_HARNESS_DESTRUCTIVE")
        or _flag("POCKETLAB_QUALIFICATION_OWNER")
        or _flag("POCKETLAB_TEST_AUTH_BYPASS")
    ):
        raise FaultControlError("fault_control_disabled", "Qualification fault controls are not explicitly enabled.", status_code=403)
    principal_id = str(harness.get("principal_id") or "").strip()[:80]
    session_id = str(harness.get("session_id") or "").strip()[:100]
    if not principal_id or not session_id:
        raise FaultControlError("fault_control_denied", "The assurance session binding is incomplete.", status_code=403)
    return principal_id, session_id


def _post_fault_observation(supervisor: Any, definition: Mapping[str, Any]) -> dict[str, Any]:
    timeout = max(5, min(int(definition["recovery_timeout_seconds"]), 180))
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() <= deadline:
        try:
            observed = supervisor.collect()
        except Exception as exc:
            return {"healthy": False, "failure_code": "fault_recovery_observation_failed", "error_type": type(exc).__name__}
        last = observed if isinstance(observed, dict) else {}
        services = last.get("services") if isinstance(last.get("services"), Mapping) else {}
        checks = last.get("checks") if isinstance(last.get("checks"), Mapping) else {}
        role = str(definition["service_role"])
        if role == "worker":
            healthy = services.get("pocket-worker") == "online" and checks.get("api_nats_connected") is True
        elif role == "nats":
            healthy = checks.get("nats_tcp_reachable") is True and checks.get("api_nats_connected") is True
        else:
            healthy = services.get("pocket-opa") == "online"
            if healthy and hasattr(supervisor, "_wait_for_opa_revision"):
                try:
                    from . import lite_policy_opa

                    proof = supervisor._wait_for_opa_revision(
                        lite_policy_opa._safe_revision(),
                        timeout_seconds=min(2.0, max(0.1, deadline - time.monotonic())),
                        interval_seconds=0.1,
                    )
                    healthy = bool(proof.get("proved"))
                    last["opa_revision_proof"] = {
                        "proved": bool(proof.get("proved")),
                        "health_ready": bool(proof.get("health_ready")),
                        "observed_revision_present": bool(proof.get("observed_revision")),
                    }
                except Exception:
                    healthy = False
        if healthy:
            return {"healthy": True, "services": {str(definition["service_name"]): services.get(definition["service_name"])}, "checks": {key: checks.get(key) for key in ("nats_tcp_reachable", "api_nats_connected", "api_http_reachable")}, "sanitized": True}
        time.sleep(0.5)
    return {
        "healthy": False,
        "failure_code": "fault_recovery_timeout",
        "services": {str(definition["service_name"]): (last.get("services") or {}).get(definition["service_name"])},
        "checks": {key: (last.get("checks") or {}).get(key) for key in ("nats_tcp_reachable", "api_nats_connected", "api_http_reachable")},
        "sanitized": True,
    }


def _audit(*, event_type: str, reason_code: str, principal_id: str, session_id: str, fault_id: str, result: str, summary: str) -> None:
    apply_migrations()
    with connection() as conn, begin_immediate(conn) as tx:
        from . import lite_harness

        lite_harness._insert_audit(
            tx,
            event_type=event_type,
            reason_code=reason_code,
            principal_id=principal_id,
            principal_class="qualification",
            harness_session_id=session_id,
            purpose=PURPOSE,
            capability=REQUIRED_CAPABILITY,
            target_scope=TARGET_SCOPE,
            operation_id=fault_id,
            result=result,
            summary=summary,
            correlation_id=fault_id,
        )


def execute_fault(*, fault_id: str, auth_context: Mapping[str, Any], confirm: bool) -> dict[str, Any]:
    definition = fault_def(fault_id)
    principal_id, session_id = _require_context(auth_context)
    if confirm is not True:
        raise FaultControlError("fault_confirmation_required", "The reviewed qualification fault requires explicit confirmation.", status_code=400)
    with _USE_LOCK:
        if definition["id"] in _USED_FAULTS:
            raise FaultControlError("fault_already_used", "The one-use qualification fault has already been consumed.", status_code=409)
        _USED_FAULTS.add(definition["id"])
    try:
        from supervisors import pocketlab_core_supervisor

        supervisor = pocketlab_core_supervisor.LiteCoreSupervisor()
        action = supervisor.restart_pm2(str(definition["service_name"]), f"security_assurance_fault:{definition['id']}")
        acted = bool(action.get("acted"))
        # A supervisor backoff or admission guard means the registered fault
        # did not execute.  Keep the one-use control available for the
        # operator after the supported retry window; consuming it here would
        # turn an expected safety throttle into an unrecoverable qualification
        # false negative.  Once PM2 has actually acted, the identifier stays
        # consumed even if post-restart observation is partial.
        if not acted:
            with _USE_LOCK:
                _USED_FAULTS.discard(definition["id"])
        recovery = _post_fault_observation(supervisor, definition) if acted else {"healthy": False, "failure_code": "fault_restart_not_acted", "sanitized": True}
        status = "PASS" if acted and recovery.get("healthy") else "PARTIAL"
        result = {
            "fault_id": definition["id"],
            "service_role": definition["service_role"],
            "service_name": definition["service_name"],
            "operation": "restart",
            "safety_class": "SAFE_ACTIVE",
            "acted": acted,
            "restart_generation": action.get("restart_generation"),
            "status": status,
            "recovery": recovery,
            "sanitized": True,
        }
        _audit(
            event_type="assurance_fault_control_executed",
            reason_code="fault_restarted" if acted else "fault_restart_not_acted",
            principal_id=principal_id,
            session_id=session_id,
            fault_id=definition["id"],
            result="accepted" if acted else "partial",
            summary="A fixed qualification service recovery control was executed and observed.",
        )
        return result
    except FaultControlError:
        raise
    except Exception as exc:
        with _USE_LOCK:
            _USED_FAULTS.discard(definition["id"])
        _audit(
            event_type="assurance_fault_control_failed",
            reason_code="fault_control_execution_failed",
            principal_id=principal_id,
            session_id=session_id,
            fault_id=definition["id"],
            result="rejected",
            summary="A fixed qualification service recovery control could not complete.",
        )
        return {
            "fault_id": definition["id"],
            "service_role": definition["service_role"],
            "service_name": definition["service_name"],
            "operation": "restart",
            "status": "PARTIAL",
            "acted": False,
            "failure_code": "fault_control_execution_failed",
            "error_type": type(exc).__name__,
            "sanitized": True,
        }
