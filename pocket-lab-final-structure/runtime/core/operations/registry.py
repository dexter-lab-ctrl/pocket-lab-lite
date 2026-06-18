from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from contracts import OperationRequest, OperationTarget


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
            "rotate_secret": OperationSpec(
                "rotate_secret", "rotate_secret", "Secret rotation"
            ),
            "fleet_join": OperationSpec(
                "fleet_join", "fleet_join", "Fleet node onboarding"
            ),
            "policy_deploy": OperationSpec(
                "policy_deploy", "policy_deploy", "OPA / policy deployment"
            ),
            "secret_read_dynamic": OperationSpec(
                "secret_read_dynamic", "secret_read_dynamic", "Dynamic secret issuance"
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
