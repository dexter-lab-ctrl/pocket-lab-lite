"""Read-only Enterprise Rules simulation, analysis, and health projections."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..db.connection import connection
from ..db.migrations import apply_migrations
from . import lite_enterprise_identity, lite_policy_lifecycle, lite_policy_opa

SIMULATE_ROLES = frozenset({"Owner", "Admin", "Operator"})
ANALYZE_ROLES = frozenset({"Owner", "Admin", "Auditor"})
SYNTHETIC_FIELDS = frozenset({"confirmed", "revision_validated", "protected_server_host", "assurance_recent"})
ACTION_TARGETS = {"catalog.install": "app", "device.remove": "device", "identity.passkey.revoke": "passkey"}


class PolicyAnalysisError(RuntimeError):
    def __init__(self, reason_code: str, message: str, *, status_code: int = 403):
        super().__init__(message); self.reason_code = reason_code; self.message = message; self.status_code = status_code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _authorize(auth_context: dict[str, Any], allowed: frozenset[str]) -> dict[str, Any]:
    resolved = lite_enterprise_identity.enrich_auth_context(auth_context)
    authorization = resolved.get("authorization") or {}
    if not authorization.get("enterprise_enabled"):
        raise PolicyAnalysisError("enterprise_mode_disabled", "Enterprise Rules analysis is unavailable in Personal Mode.", status_code=404)
    if not authorization.get("membership_active") or authorization.get("role") not in allowed:
        raise PolicyAnalysisError("enterprise_rules_role_required", "Your Enterprise role is not authorized for this Rules view.")
    return resolved


def _revision(revision_id: str) -> dict[str, Any]:
    with connection() as conn:
        row = conn.execute("SELECT * FROM policy_revisions WHERE revision_id=?", (str(revision_id)[:80],)).fetchone()
        state = conn.execute("SELECT active_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
    if not row:
        raise PolicyAnalysisError("policy_simulation_revision_unavailable", "That immutable policy revision is unavailable.", status_code=404)
    result = dict(row)
    active = str(state["active_revision_id"] if state else "")
    if result["validation_status"] == "corrupt":
        raise PolicyAnalysisError("policy_simulation_revision_unavailable", "That policy revision is corrupt.", status_code=409)
    if result["revision_id"] != active and result["validation_status"] != "valid":
        raise PolicyAnalysisError("policy_simulation_revision_unavailable", "Only the active revision or a validated candidate can be simulated.", status_code=409)
    return result


def _synthetic(scenario: Any) -> dict[str, bool]:
    if not isinstance(scenario, dict):
        raise PolicyAnalysisError("policy_simulation_invalid", "Synthetic scenarios must be a flat object.", status_code=422)
    if set(scenario) - SYNTHETIC_FIELDS or any(isinstance(value, (dict, list)) or not isinstance(value, bool) for value in scenario.values()):
        raise PolicyAnalysisError("policy_simulation_invalid", "The synthetic scenario contains an unsupported field or value.", status_code=422)
    return {key: bool(value) for key, value in scenario.items()}


def _input(auth: dict[str, Any], action_id: str, target_id: str, synthetic: dict[str, bool] | None) -> dict[str, Any]:
    target_type = ACTION_TARGETS.get(action_id)
    if not target_type:
        raise PolicyAnalysisError("policy_simulation_invalid", "Select a registered protected action.", status_code=422)
    target_state: dict[str, Any] = {}
    assurance = ((auth.get("session") or {}).get("assurance") or [])
    if synthetic is not None:
        target_state = {key: value for key, value in synthetic.items() if key != "assurance_recent"}
        assurance = ([{"purpose": "identity.passkey.revoke", "credential_id": "synthetic", "satisfied_at": "synthetic", "expires_at": "synthetic"}] if synthetic.get("assurance_recent") else [])
    # Reuse the real evaluator's authoritative actor/session transformation.
    derived = dict(auth)
    derived["session"] = {**(auth.get("session") or {}), "assurance": assurance}
    return lite_policy_opa.build_authorization_input(auth_context=derived, action_id=action_id, target_type=target_type, target_id=target_id, target_revision="simulation", target=target_state)


def _candidate_decision(revision: dict[str, Any], input_doc: dict[str, Any]) -> dict[str, Any]:
    parameters = json.loads(revision["canonical_parameters_json"])
    _, tree = lite_policy_lifecycle.policy_source_tree(revision["template_id"], revision["template_version"], parameters)
    opa = os.environ.get("POCKETLAB_OPA_BIN", "opa")
    with tempfile.TemporaryDirectory(prefix="pocketlab-policy-sim-") as raw:
        root = Path(raw)
        for name, content in tree.items():
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8")
        input_path = root / "input.json"; input_path.write_text(json.dumps(input_doc, sort_keys=True), encoding="utf-8")
        result = subprocess.run([opa, "eval", "--format=json", "--data", str(root), "--input", str(input_path), "data.pocketlab.authz.decision"], capture_output=True, text=True, timeout=3, check=False)
    if result.returncode != 0:
        raise PolicyAnalysisError("policy_simulation_revision_unavailable", "The candidate policy could not be evaluated.", status_code=503)
    try:
        return json.loads(result.stdout)["result"][0]["expressions"][0]["value"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise PolicyAnalysisError("policy_simulation_revision_unavailable", "The candidate policy returned an invalid result.", status_code=503) from exc


def simulate(*, auth_context: dict[str, Any], revision_id: str, action_id: str, target_id: str, mode: str, scenario: Any = None) -> dict[str, Any]:
    apply_migrations(); auth = _authorize(auth_context, SIMULATE_ROLES)
    revision = _revision(revision_id)
    action = str(action_id or "")[:120]; target = str(target_id or "").strip()[:160]
    if not target:
        raise PolicyAnalysisError("policy_simulation_invalid", "Select a bounded target reference.", status_code=422)
    input_mode = str(mode or "real_derived").lower()
    if input_mode not in {"real_derived", "synthetic"}:
        raise PolicyAnalysisError("policy_simulation_invalid", "Select real-derived or synthetic simulation.", status_code=422)
    synthetic = _synthetic(scenario) if input_mode == "synthetic" else None
    if input_mode == "real_derived" and scenario is not None:
        raise PolicyAnalysisError("policy_simulation_invalid", "Real-derived simulation does not accept browser scenario facts.", status_code=422)
    input_doc = _input(auth, action, target, synthetic)
    active = False
    with connection() as conn:
        state = conn.execute("SELECT active_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
        active = bool(state and state["active_revision_id"] == revision["revision_id"])
    if active:
        status, payload = lite_policy_opa._http_json("POST", lite_policy_opa.OPA_DECISION_PATH, {"input": input_doc})
        raw = payload.get("result") if status == 200 else None
    else:
        raw = _candidate_decision(revision, input_doc)
    normalized = lite_policy_opa._validate_result(raw)
    outcome = "allow" if normalized["allow"] else "step_up_required" if normalized["reason_code"] == "passkey_step_up_required" else "block"
    return {"simulation_id": "sim-" + uuid.uuid4().hex, "revision_id": revision["revision_id"], "policy_revision": revision["revision_id"], "action_id": action, "target_type": ACTION_TARGETS[action], "target_id": target, "input_mode": input_mode, "outcome": outcome, "reason_code": normalized["reason_code"], "constraints": normalized["constraints"][:12], "required_assurance": "passkey_step_up" if outcome == "step_up_required" else None, "required_role": None, "synthetic_fields": sorted(synthetic) if synthetic is not None else [], "evaluated_at": _now(), "raw_input_exposed": False}


def analyze(*, auth_context: dict[str, Any], revision_id: str | None = None) -> dict[str, Any]:
    _authorize(auth_context, ANALYZE_ROLES); apply_migrations()
    with connection() as conn:
        state = conn.execute("SELECT active_revision_id FROM policy_runtime_state WHERE state_id=1").fetchone()
    selected = str(revision_id or (state["active_revision_id"] if state else ""))
    if selected:
        _revision(selected)
    actions = sorted(lite_policy_opa.PROTECTED_ACTIONS)
    # Current templates have no ordered rule DSL; only direct action coverage is provable.
    findings = []
    return {"revision_id": selected or None, "status": "complete" if selected else "inconclusive", "complete_typed_analysis": False, "registered_protected_actions": actions, "represented_actions": actions if selected else [], "unmapped_actions": [] if selected else actions, "findings": findings, "finding_categories": [], "unsupported_categories": ["contradiction", "shadowing", "unreachable_rule", "overly_broad_allow", "stale_or_unused_rule"], "proof_rule": "Only direct registered-action coverage is provable because current typed templates do not encode an ordered rule DSL.", "raw_input_exposed": False}


def health(*, auth_context: dict[str, Any]) -> dict[str, Any]:
    _authorize(auth_context, frozenset({"Owner", "Admin", "Operator", "Viewer", "Auditor"})); apply_migrations()
    with connection() as conn:
        state = conn.execute("SELECT * FROM policy_runtime_state WHERE state_id=1").fetchone()
        op = conn.execute("SELECT state FROM policy_activation_operations WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain') ORDER BY created_at DESC LIMIT 1").fetchone()
    filesystem = lite_policy_opa._safe_revision(); observed = lite_policy_opa._observed_opa_revision()
    active = str(state["active_revision_id"] if state else ""); known = str(state["known_good_revision_id"] if state else "")
    if op: consistency, reason = ("uncertain", "policy_revision_uncertain") if op["state"] == "uncertain" else ("activation_pending", "policy_activation_pending")
    elif not active or not observed: consistency, reason = "unavailable", "policy_revision_uncertain"
    elif active != known or active != filesystem or active != observed: consistency, reason = "revision_mismatch", "policy_revision_mismatch"
    else: consistency, reason = "ready", ""
    analysis = analyze(auth_context=auth_context, revision_id=active) if active else {"status": "inconclusive", "findings": []}
    return {"consistency_state": consistency, "degraded_reason": reason, "db_active_revision": active or None, "filesystem_active_revision": filesystem if filesystem != "unavailable" else None, "opa_observed_revision": observed, "known_good_revision": known or None, "activation_operation_state": op["state"] if op else None, "opa_loopback_configured": lite_policy_opa._opa_endpoint_is_loopback(), "opa_reachable": observed is not None, "manifest_integrity": consistency != "corrupt", "registered_protected_actions": sorted(lite_policy_opa.PROTECTED_ACTIONS), "represented_protected_actions": analysis.get("represented_actions", []), "analysis_status": analysis.get("status"), "deterministic_findings_count": len(analysis.get("findings", [])), "checked_at": _now(), "raw_input_exposed": False}
