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
import uuid
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
    "nats_unavailable_recovery",
    "opa_unavailable_fail_closed",
})
ALLOWED_OPERATIONS = frozenset({"restart", "pause_probe_restore"})
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
        operation = str(item.get("operation") or "")
        if identifier in seen or service not in ALLOWED_SERVICES or role not in ALLOWED_ROLES or operation not in ALLOWED_OPERATIONS or str(item.get("safety_class") or "") != "SAFE_ACTIVE" or probe not in ALLOWED_PROBES or not isinstance(item.get("max_uses"), int) or item.get("max_uses") != 1:
            raise FaultControlError("fault_registry_invalid", "A qualification fault entry is invalid.", status_code=503)
        try:
            timeout = int(item.get("recovery_timeout_seconds") or 0)
        except (TypeError, ValueError):
            timeout = 0
        try:
            pause_window = int(item.get("pause_window_seconds") or 0)
        except (TypeError, ValueError):
            pause_window = 0
        pause_valid = operation == "restart" and pause_window == 0 or operation == "pause_probe_restore" and pause_window in range(1, 16)
        probe_valid = (
            (role == "worker" and probe == "worker_online_and_api_nats")
            or (role == "nats" and probe in {"nats_tcp_jetstream_worker", "nats_unavailable_recovery"})
            or (role == "policy" and probe in {"opa_health_and_revision", "opa_unavailable_fail_closed"})
        )
        if timeout not in range(5, 181) or not pause_valid or not probe_valid:
            raise FaultControlError("fault_registry_invalid", "A qualification fault entry has an unsafe recovery policy.", status_code=503)
        seen.add(identifier)
        clean.append({
            "id": identifier,
            "service_role": role,
            "service_name": service,
            "operation": operation,
            "safety_class": "SAFE_ACTIVE",
            "pause_window_seconds": pause_window,
            "recovery_timeout_seconds": timeout,
            "max_uses": 1,
            "probe": probe,
        })
    expected = {"worker_restart_once", "nats_restart_once", "opa_restart_once", "opa_pause_probe_restore", "nats_pause_probe_restore"}
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


def _assurance_run_facts(
    run_ids: set[str] | None = None,
    *,
    principal_id: str | None = None,
) -> list[dict[str, Any]]:
    """Read bounded, non-secret execution facts for an outage-window proof."""
    apply_migrations()
    clauses = ["status IN ('QUEUED','RUNNING','PASS','FAIL','PARTIAL','BLOCKED')"]
    parameters: list[Any] = []
    if principal_id:
        clauses.append("principal_id=?")
        parameters.append(str(principal_id)[:80])
    if run_ids:
        bounded_ids = sorted(str(value)[:80] for value in run_ids if str(value).startswith("assurance-"))[:8]
        if not bounded_ids:
            return []
        placeholders = ",".join("?" for _ in bounded_ids)
        clauses.append(f"run_id IN ({placeholders})")
        parameters.extend(bounded_ids)
    with connection() as conn:
        rows = conn.execute(
            f"""SELECT run_id,status,worker_operation_id,worker_instance_id,
                       checkpoint_generation,last_event_sequence,current_scenario,
                       current_tool,heartbeat_at,updated_at
                  FROM assurance_runs
                 WHERE {' AND '.join(clauses)}
                 ORDER BY requested_at DESC LIMIT 8""",
            tuple(parameters),
        ).fetchall()
    return [
        {
            "run_id": str(row["run_id"]),
            "status": str(row["status"]),
            "worker_operation_id": str(row["worker_operation_id"] or "") or None,
            "worker_instance_id": str(row["worker_instance_id"] or "") or None,
            "checkpoint_generation": int(row["checkpoint_generation"] or 0),
            "last_event_sequence": int(row["last_event_sequence"] or 0),
            "current_scenario": str(row["current_scenario"] or "") or None,
            "current_tool": str(row["current_tool"] or "") or None,
            "heartbeat_at": row["heartbeat_at"],
            "updated_at": row["updated_at"],
            "sanitized": True,
        }
        for row in rows
    ]


def _wait_for_unavailable(supervisor: Any, definition: Mapping[str, Any]) -> dict[str, Any]:
    """Prove the fixed service is unavailable before executing its probe."""
    deadline = time.monotonic() + max(1, min(int(definition["pause_window_seconds"]), 15))
    last: dict[str, Any] = {}
    while True:
        try:
            observed = supervisor.collect()
        except Exception as exc:
            return {"observed": False, "failure_code": "outage_observation_failed", "error_type": type(exc).__name__, "sanitized": True}
        last = observed if isinstance(observed, dict) else {}
        services = last.get("services") if isinstance(last.get("services"), Mapping) else {}
        checks = last.get("checks") if isinstance(last.get("checks"), Mapping) else {}
        if definition["service_role"] == "nats":
            unavailable = services.get("pocket-nats") != "online" or checks.get("nats_tcp_reachable") is not True
        else:
            unavailable = services.get("pocket-opa") != "online"
            if not unavailable:
                try:
                    from . import lite_policy_opa

                    status_code, _ = lite_policy_opa._http_json("GET", "/health", timeout=0.2)
                    unavailable = status_code != 200
                except Exception:
                    unavailable = True
        if unavailable:
            return {
                "observed": True,
                "service_status": services.get(definition["service_name"]),
                "nats_tcp_reachable": checks.get("nats_tcp_reachable") if definition["service_role"] == "nats" else None,
                "sanitized": True,
            }
        if time.monotonic() >= deadline:
            return {
                "observed": False,
                "failure_code": "outage_window_not_observed",
                "service_status": services.get(definition["service_name"]),
                "sanitized": True,
            }
        time.sleep(0.1)


def _fixed_opa_governed_probe(auth_context: Mapping[str, Any]) -> dict[str, Any]:
    """Run one fixed protected-action decision without accepting probe input."""
    from . import lite_policy_opa

    try:
        decision = lite_policy_opa.evaluate_authorization(
            auth_context=dict(auth_context),
            action_id="restore.preview",
            target_type="security-assurance",
            target_id="opa-outage-window-probe",
            target_revision=lite_policy_opa._safe_revision(),
            target={},
            request_context={"source": "registered_assurance_fault", "mutation": False},
            correlation_id=f"assurance-opa-probe-{uuid.uuid4().hex}",
        )
        return {
            "available": True,
            "decision_observed": True,
            "decision_allow": bool(decision.get("allow")),
            "reason_code": str(decision.get("reason_code") or "")[:80],
            "policy_revision_present": bool(decision.get("policy_revision")),
            "fail_closed": decision.get("allow") is not True,
            "sanitized": True,
        }
    except lite_policy_opa.PolicyDecisionError as exc:
        decision = exc.decision if isinstance(exc.decision, Mapping) else {}
        unavailable = exc.reason_code in {
            "policy_unavailable",
            "policy_revision_uncertain",
            "policy_revision_mismatch",
            "policy_source_validation_unavailable",
            "policy_activation_pending",
        }
        return {
            "available": not unavailable,
            "decision_observed": bool(decision),
            "decision_allow": bool(decision.get("allow")) if decision else False,
            "reason_code": exc.reason_code,
            "policy_revision_present": bool(decision.get("policy_revision")) if decision else False,
            "fail_closed": not bool(decision.get("allow")) if decision else True,
            "sanitized": True,
        }
    except Exception as exc:
        return {
            "available": False,
            "decision_observed": False,
            "decision_allow": False,
            "reason_code": "policy_probe_failed",
            "fail_closed": True,
            "error_type": type(exc).__name__,
            "sanitized": True,
        }


def _nats_outage_probe(supervisor: Any) -> dict[str, Any]:
    """Observe only fixed local NATS/JetStream health during the pause."""
    try:
        observed = supervisor.collect()
    except Exception as exc:
        return {"available": False, "reconnect_observed": False, "failure_code": "nats_probe_failed", "error_type": type(exc).__name__, "sanitized": True}
    checks = observed.get("checks") if isinstance(observed, Mapping) else {}
    services = observed.get("services") if isinstance(observed, Mapping) else {}
    return {
        "available": bool(checks.get("nats_tcp_reachable") and checks.get("api_nats_connected")),
        "service_status": services.get("pocket-nats"),
        "nats_tcp_reachable": bool(checks.get("nats_tcp_reachable")),
        "api_nats_connected": bool(checks.get("api_nats_connected")),
        "fixed_subject_only": True,
        "storage_mutation": False,
        "sanitized": True,
    }


def _execute_pause_probe_restore(
    *,
    supervisor: Any,
    definition: Mapping[str, Any],
    auth_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Pause one registered service, probe the outage, and always restore it."""
    service = str(definition["service_name"])
    fault_id = str(definition["id"])
    principal_id = str((auth_context.get("harness") or {}).get("principal_id") or "")[:80]
    runs_before = _assurance_run_facts(principal_id=principal_id)
    if definition["service_role"] == "nats" and not any(
        str(item.get("status") or "") in {"QUEUED", "RUNNING"} for item in runs_before
    ):
        return {
            "fault_id": fault_id,
            "service_role": definition["service_role"],
            "service_name": service,
            "operation": definition["operation"],
            "safety_class": definition["safety_class"],
            "acted": False,
            "status": "BLOCKED",
            "failure_code": "nats_fault_requires_active_assurance_run",
            "run_continuity": {"runs_before": runs_before, "sanitized": True},
            "sanitized": True,
        }
    pause = supervisor.qualification_stop_pm2(service, f"security_assurance_fault:{fault_id}:pause")
    if not pause.get("acted"):
        return {
            "fault_id": fault_id,
            "service_role": definition["service_role"],
            "service_name": service,
            "operation": definition["operation"],
            "safety_class": definition["safety_class"],
            "acted": False,
            "status": "PARTIAL",
            "failure_code": "fault_pause_not_acted",
            "pause": pause,
            "sanitized": True,
        }

    outage: dict[str, Any] = {}
    probe: dict[str, Any] = {}
    runs_during: list[dict[str, Any]] = []
    restore: dict[str, Any] = {"acted": False, "failure_code": "restore_not_attempted", "sanitized": True}
    try:
        outage = _wait_for_unavailable(supervisor, definition)
        probe = (
            _fixed_opa_governed_probe(auth_context)
            if definition["service_role"] == "policy"
            else _nats_outage_probe(supervisor)
        )
        if definition["service_role"] == "nats":
            runs_during = _assurance_run_facts(principal_id=principal_id)
    finally:
        restore = supervisor.qualification_start_pm2(service, f"security_assurance_fault:{fault_id}:restore")
    recovery = _post_fault_observation(supervisor, definition) if restore.get("acted") else {"healthy": False, "failure_code": "fault_restore_not_acted", "sanitized": True}
    runs_after = _assurance_run_facts(principal_id=principal_id) if definition["service_role"] == "nats" else []
    before_by_id = {str(item["run_id"]): item for item in runs_before}
    after_by_id = {str(item["run_id"]): item for item in runs_after}
    new_run_ids = sorted(set(after_by_id) - set(before_by_id))[:8]
    run_continuity = {
        "runs_before": runs_before,
        "runs_during": runs_during,
        "runs_after": runs_after,
        "same_run_ids": bool(before_by_id) and set(before_by_id).issubset(after_by_id),
        "worker_operation_ids_preserved": bool(before_by_id)
        and all(after_by_id[run_id].get("worker_operation_id") == before.get("worker_operation_id") for run_id, before in before_by_id.items() if run_id in after_by_id),
        "terminal_statuses_truthful": all(str(item.get("status") or "") in {"QUEUED", "RUNNING", "PASS", "FAIL", "PARTIAL", "BLOCKED"} for item in runs_after),
        "new_run_ids": new_run_ids,
        "duplicate_run_id_created": bool(new_run_ids),
        "sanitized": True,
    }
    if definition["service_role"] == "policy":
        restored_probe = _fixed_opa_governed_probe(auth_context) if recovery.get("healthy") else {"available": False, "sanitized": True}
        probe_success = bool(probe.get("fail_closed")) and probe.get("available") is False and bool(restored_probe.get("available"))
    else:
        restored_probe = _nats_outage_probe(supervisor) if recovery.get("healthy") else {"available": False, "sanitized": True}
        probe_success = probe.get("available") is False and bool(restored_probe.get("available"))
    continuity_success = definition["service_role"] != "nats" or (
        run_continuity["same_run_ids"]
        and run_continuity["worker_operation_ids_preserved"]
        and not run_continuity["duplicate_run_id_created"]
        and run_continuity["terminal_statuses_truthful"]
    )
    status = "PASS" if outage.get("observed") and probe_success and restore.get("acted") and recovery.get("healthy") and continuity_success else "PARTIAL"
    return {
        "fault_id": fault_id,
        "service_role": definition["service_role"],
        "service_name": service,
        "operation": definition["operation"],
        "safety_class": definition["safety_class"],
        "acted": True,
        "status": status,
        "pause": pause,
        "outage": outage,
        "probe_during_outage": probe,
        "restore": restore,
        "recovery": recovery,
        "probe_after_restore": restored_probe,
        "run_continuity": run_continuity,
        "no_arbitrary_service": True,
        "no_storage_mutation": True,
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
        if definition["operation"] == "pause_probe_restore":
            result = _execute_pause_probe_restore(
                supervisor=supervisor,
                definition=definition,
                auth_context=auth_context,
            )
            acted = bool(result.get("acted"))
            if not acted:
                with _USE_LOCK:
                    _USED_FAULTS.discard(definition["id"])
            _audit(
                event_type="assurance_fault_outage_window_executed",
                reason_code="outage_window_proved" if result.get("status") == "PASS" else "outage_window_partial",
                principal_id=principal_id,
                session_id=session_id,
                fault_id=definition["id"],
                result="accepted" if result.get("status") == "PASS" else "partial",
                summary="A fixed qualification outage-window probe was executed with automatic service restoration.",
            )
            return result
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
