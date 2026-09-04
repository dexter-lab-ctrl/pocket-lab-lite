"""Governed reconciliation between repository Safety Rules and durable OPA state.

Repository updates may stage newer Rego, but they must never silently replace a
proved durable policy revision.  This service detects source drift and records a
root-Owner-attributed activation intent.  It intentionally performs no shell,
PM2, OPA, or filesystem pointer mutation; the core supervisor remains the only
runtime activation authority.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations
from . import lite_enterprise_governance, lite_policy_approvals, lite_policy_lifecycle

NONTERMINAL_STATES = frozenset({
    "pending",
    "validating",
    "switching",
    "restarting",
    "verifying",
    "rolling_back",
    "uncertain",
})
SOURCE_SYNC_SUMMARY = "Synchronize repository Safety Rules after a Pocket Lab update."


class PolicySourceSyncError(RuntimeError):
    def __init__(self, reason_code: str, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.reason_code = str(reason_code or "policy_source_sync_failed")[:80]
        self.message = str(message or "Safety Rules could not be synchronized.")[:240]
        self.status_code = int(status_code)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _runtime_contract(conn: sqlite3.Connection) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    state = conn.execute(
        "SELECT active_revision_id,known_good_revision_id,updated_by_operation_id FROM policy_runtime_state WHERE state_id=1"
    ).fetchone()
    if not state or not state["active_revision_id"]:
        return None, None
    revision = conn.execute(
        """SELECT revision_id,template_id,template_version,canonical_parameters_json,
                  manifest_json,content_hash,lifecycle_status
           FROM policy_revisions WHERE revision_id=?""",
        (str(state["active_revision_id"]),),
    ).fetchone()
    return dict(state), dict(revision) if revision else None


def _repository_candidate(revision: dict[str, Any]) -> dict[str, Any]:
    try:
        parameters = json.loads(str(revision.get("canonical_parameters_json") or "{}"))
    except (TypeError, ValueError) as exc:
        raise PolicySourceSyncError(
            "policy_source_contract_invalid",
            "The active Safety Rules parameters could not be verified.",
            status_code=503,
        ) from exc
    if not isinstance(parameters, dict):
        raise PolicySourceSyncError(
            "policy_source_contract_invalid",
            "The active Safety Rules parameters could not be verified.",
            status_code=503,
        )
    try:
        revision_id, tree = lite_policy_lifecycle.policy_source_tree(
            str(revision.get("template_id") or "baseline"),
            str(revision.get("template_version") or "1"),
            parameters,
        )
        manifest, content_hash = lite_policy_lifecycle.manifest_for_tree(tree)
    except lite_policy_lifecycle.PolicyLifecycleError as exc:
        raise PolicySourceSyncError(exc.reason_code, exc.message, status_code=exc.status_code) from exc
    except Exception as exc:
        raise PolicySourceSyncError(
            "policy_source_validation_unavailable",
            "Pocket Lab could not verify the repository Safety Rules source.",
            status_code=503,
        ) from exc
    return {
        "revision_id": revision_id,
        "template_id": str(revision.get("template_id") or "baseline"),
        "template_version": str(revision.get("template_version") or "1"),
        "parameters": parameters,
        "manifest": manifest,
        "content_hash": content_hash,
    }


def source_state() -> dict[str, Any]:
    """Return bounded repository-vs-durable policy state without exposing source."""
    apply_migrations()
    with connection() as conn:
        state, revision = _runtime_contract(conn)
        operation = conn.execute(
            """SELECT operation_id,candidate_revision_id,state,created_at,updated_at
               FROM policy_activation_operations
               WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain')
               ORDER BY created_at LIMIT 1"""
        ).fetchone()
    if not state:
        return {
            "durable": False,
            "active_revision": "",
            "known_good_revision": "",
            "repository_revision": "",
            "source_update_required": False,
            "activation_in_progress": bool(operation),
            "activation_operation": dict(operation) if operation else None,
        }
    if not revision:
        raise PolicySourceSyncError(
            "policy_source_contract_missing",
            "The durable Safety Rules revision has no matching source contract.",
            status_code=503,
        )
    candidate = _repository_candidate(revision)
    active = str(state.get("active_revision_id") or "")
    known_good = str(state.get("known_good_revision_id") or "")
    return {
        "durable": True,
        "active_revision": active,
        "known_good_revision": known_good,
        "repository_revision": candidate["revision_id"],
        "source_update_required": bool(candidate["revision_id"] != active),
        "activation_in_progress": bool(operation),
        "activation_operation": dict(operation) if operation else None,
        "candidate": candidate,
    }


def _public_state(state: dict[str, Any]) -> dict[str, Any]:
    operation = state.get("activation_operation") if isinstance(state.get("activation_operation"), dict) else None
    return {
        "durable": bool(state.get("durable")),
        "active_revision": str(state.get("active_revision") or "")[:80],
        "known_good_revision": str(state.get("known_good_revision") or "")[:80],
        "repository_revision": str(state.get("repository_revision") or "")[:80],
        "source_update_required": bool(state.get("source_update_required")),
        "activation_in_progress": bool(state.get("activation_in_progress")),
        "activation_operation": {
            "operation_id": str(operation.get("operation_id") or "")[:120],
            "candidate_revision_id": str(operation.get("candidate_revision_id") or "")[:80],
            "state": str(operation.get("state") or "")[:40],
            "created_at": operation.get("created_at"),
            "updated_at": operation.get("updated_at"),
        } if operation else None,
    }


def request_source_sync(*, auth_context: dict[str, Any], correlation_id: str | None = None) -> dict[str, Any]:
    """Record an Owner-confirmed source synchronization for supervisor execution."""
    apply_migrations()
    # The service repeats the root-owner + recent-passkey check rather than
    # relying only on the HTTP router, so future internal callers cannot bypass
    # the same assurance boundary.
    _resolved, actor_id = lite_enterprise_governance.require_recent_assurance(
        auth_context,
        "policy.rules.activate",
    )

    # Owner-originated peer approvals are impossible under the authority model.
    # Clean up legacy rows produced by stale policy before considering a new
    # activation.  Cancellation is evidence-preserving and never grants access.
    cleanup = lite_policy_approvals.cancel_impossible_owner_requests(
        actor_human_id=actor_id,
        reason_code="owner_authority_policy_inconsistency",
    )

    state = source_state()
    if not state.get("durable"):
        return {
            "status": "current",
            "accepted": False,
            "activation_required": False,
            "summary": "Safety Rules are using the repository baseline; no durable source update is pending.",
            "cleanup": cleanup,
            "source": _public_state(state),
        }

    candidate = state.get("candidate") if isinstance(state.get("candidate"), dict) else {}
    candidate_revision = str(candidate.get("revision_id") or "")
    if not candidate_revision:
        raise PolicySourceSyncError(
            "policy_source_validation_unavailable",
            "Pocket Lab could not derive the repository Safety Rules revision.",
            status_code=503,
        )

    existing_operation = state.get("activation_operation") if isinstance(state.get("activation_operation"), dict) else None
    if existing_operation:
        if str(existing_operation.get("candidate_revision_id") or "") == candidate_revision:
            return {
                "status": "already_requested",
                "accepted": True,
                "activation_required": True,
                "summary": "Safety Rules update is already being verified by Pocket Lab.",
                "cleanup": cleanup,
                "source": _public_state(state),
                "operation": {
                    "operation_id": str(existing_operation.get("operation_id") or "")[:120],
                    "candidate_revision_id": candidate_revision[:80],
                    "state": str(existing_operation.get("state") or "")[:40],
                },
            }
        raise PolicySourceSyncError(
            "policy_activation_in_progress",
            "Another Safety Rules activation is already in progress.",
            status_code=409,
        )

    if not state.get("source_update_required"):
        return {
            "status": "current",
            "accepted": False,
            "activation_required": False,
            "summary": "Safety Rules already match the repository source.",
            "cleanup": cleanup,
            "source": _public_state(state),
        }

    now = _now()
    operation_id = "plo-" + uuid.uuid4().hex
    safe_correlation = str(correlation_id or uuid.uuid4().hex)[:80]
    manifest_json = _canonical({
        "files": candidate["manifest"],
        "candidate_hash": candidate["content_hash"],
    })
    parameters_json = _canonical(candidate["parameters"])

    try:
        with connection() as conn:
            with begin_immediate(conn) as tx:
                runtime = tx.execute(
                    "SELECT active_revision_id,known_good_revision_id FROM policy_runtime_state WHERE state_id=1"
                ).fetchone()
                if not runtime or str(runtime["active_revision_id"] or "") != str(state.get("active_revision") or ""):
                    raise PolicySourceSyncError(
                        "policy_source_state_changed",
                        "Safety Rules changed while Pocket Lab was preparing the update. Refresh and try again.",
                        status_code=409,
                    )
                nonterminal = tx.execute(
                    """SELECT operation_id,candidate_revision_id,state FROM policy_activation_operations
                       WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain')
                       LIMIT 1"""
                ).fetchone()
                if nonterminal:
                    raise PolicySourceSyncError(
                        "policy_activation_in_progress",
                        "Another Safety Rules activation is already in progress.",
                        status_code=409,
                    )
                tx.execute(
                    """INSERT INTO policy_revisions(
                           revision_id,parent_revision_id,template_id,template_version,
                           canonical_parameters_json,manifest_json,content_hash,created_by_human_id,
                           created_at,validation_status,validation_reason_code,lifecycle_status,
                           change_summary
                       ) VALUES (?,?,?,?,?,?,?,?,?,'pending','','draft',?)
                       ON CONFLICT(revision_id) DO NOTHING""",
                    (
                        candidate_revision,
                        str(runtime["active_revision_id"] or "") or None,
                        candidate["template_id"],
                        candidate["template_version"],
                        parameters_json,
                        manifest_json,
                        candidate["content_hash"],
                        actor_id,
                        now,
                        SOURCE_SYNC_SUMMARY,
                    ),
                )
                revision = tx.execute(
                    "SELECT manifest_json,content_hash FROM policy_revisions WHERE revision_id=?",
                    (candidate_revision,),
                ).fetchone()
                if (
                    not revision
                    or str(revision["manifest_json"] or "") != manifest_json
                    or str(revision["content_hash"] or "") != str(candidate["content_hash"])
                ):
                    raise PolicySourceSyncError(
                        "policy_source_revision_conflict",
                        "The repository Safety Rules candidate did not match its immutable revision record.",
                        status_code=409,
                    )
                tx.execute(
                    """INSERT INTO policy_activation_operations(
                           operation_id,requested_by_human_id,correlation_id,candidate_revision_id,
                           prior_known_good_revision_id,state,created_at,updated_at
                       ) VALUES (?,?,?,?,?,'pending',?,?)""",
                    (
                        operation_id,
                        actor_id,
                        safe_correlation,
                        candidate_revision,
                        str(runtime["known_good_revision_id"] or "") or None,
                        now,
                        now,
                    ),
                )
    except sqlite3.IntegrityError as exc:
        raise PolicySourceSyncError(
            "policy_activation_in_progress",
            "Another Safety Rules activation is already in progress.",
            status_code=409,
        ) from exc

    return {
        "status": "queued",
        "accepted": True,
        "activation_required": True,
        "summary": "Safety Rules update was accepted. The supervisor will stage, restart, verify, and roll back automatically if proof fails.",
        "cleanup": cleanup,
        "source": _public_state(state),
        "operation": {
            "operation_id": operation_id,
            "candidate_revision_id": candidate_revision[:80],
            "state": "pending",
        },
    }
