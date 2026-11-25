from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from contracts import OperationRequest, OperationTarget


# Compatibility vocabulary for historical clients and operation records.  These
# names are intentionally absent from OperationRegistry.operations so they
# cannot create new queued runs.
RETIRED_OPERATION_NAMES = frozenset({
    "rotate_secret",
    "secret_read_dynamic",
})
RETIRED_COMMAND_SUBJECTS = frozenset({
    "pocketlab.commands.vault.rotate",
    "pocketlab.commands.vault.dynamic_secret",
})


class RetiredOperationError(ValueError):
    """Raised before a retired operation can create or execute a run."""

    def __init__(self, operation: str):
        self.operation = str(operation or "").strip()
        super().__init__(f"Retired operation: {self.operation}")


def is_retired_operation(operation: str) -> bool:
    return str(operation or "").strip() in RETIRED_OPERATION_NAMES


def is_retired_command_subject(subject: str) -> bool:
    return str(subject or "").strip() in RETIRED_COMMAND_SUBJECTS


def retired_operation_payload(*, operation: str = "", subject: str = "") -> dict[str, Any]:
    """Return bounded, non-executing compatibility evidence."""
    operation_value = str(operation or "").strip()[:80]
    subject_value = str(subject or "").strip()[:120]
    return {
        "status": "retired",
        "accepted": False,
        "executed": False,
        "operation": operation_value or None,
        "command_subject": subject_value or None,
        "reason_code": "legacy_control_plane_retired",
        "replacement": "Native Identity & Access password and passkey flows",
        "historical_record_preserved": True,
        "sanitized": True,
    }


@dataclass
class OperationSpec:
    name: str
    task: str
    description: str = ""


class OperationRegistry:
    def __init__(self):
        self.operations: Dict[str, OperationSpec] = {
            "git_sync": OperationSpec(
                "git_sync", "git_sync", "Repository synchronization and commit"
            ),
            "release_prepare": OperationSpec(
                "release_prepare", "backup_now", "Release snapshot and preflight"
            ),
            "release_sync": OperationSpec(
                "release_sync", "git_sync", "Release repository synchronization"
            ),
            "release_deploy": OperationSpec(
                "release_deploy", "deploy_blueprint", "Release blueprint promotion"
            ),
            "release_verify": OperationSpec(
                "release_verify", "drift_scan", "Release verification and drift scan"
            ),
            "drift_scan": OperationSpec("drift_scan", "drift_scan", "Drift detection"),
            "deploy_blueprint": OperationSpec(
                "deploy_blueprint", "deploy_blueprint", "Blueprint deployment"
            ),
            "backup_now": OperationSpec("backup_now", "backup_now", "On-demand backup"),
            "restore_backup": OperationSpec(
                "restore_backup", "restore_backup", "Backup restore"
            ),
            "fleet_join": OperationSpec(
                "fleet_join", "fleet_join", "Fleet node onboarding"
            ),
            "policy_deploy": OperationSpec(
                "policy_deploy", "policy_deploy", "OPA / policy deployment"
            ),
            "backup_verify": OperationSpec(
                "backup_verify", "backup_verify", "Backup verification"
            ),
        }

    def resolve(self, operation: str) -> OperationSpec:
        return self.operations.get(operation, OperationSpec(operation, operation))


def normalize_operation_request(payload: Dict[str, Any]) -> OperationRequest:
    target_payload = payload.get("target") or {}
    if not isinstance(target_payload, dict):
        target_payload = {}
    target = OperationTarget(
        type=str(target_payload.get("type", "repo")).strip() or "repo",
        ref=str(target_payload.get("ref", "")).strip(),
    )
    operation = str(payload.get("operation") or "").strip()
    return OperationRequest(
        operation=operation,
        target=target,
        params=dict(payload.get("params") or {}),
        dry_run=bool(payload.get("dry_run", False)),
        source=(
            payload.get("source") if isinstance(payload.get("source"), dict) else None
        ),
    )
