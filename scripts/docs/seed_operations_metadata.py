#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[2]
OPS_DIR = ROOT / "operations"


OPERATIONS = [
    {
        "metadata": {
            "name": "catalog_refresh",
            "title": "Refresh App Catalog",
            "description": "Refresh Apps & Services / App Catalog metadata.",
            "tags": ["catalog", "apps", "safe-write"],
        },
        "spec": {
            "professionalLabel": "Refresh catalog",
            "simpleLabel": "Update app list",
            "uiEntrypoints": ["App Catalog", "Apps & Services", "Release Workflow"],
            "apiEntrypoints": ["/api/catalog/refresh", "/api/operations/execute"],
            "natsSubject": "pocketlab.commands.catalog.refresh",
            "successEvents": ["pocketlab.events.catalog.refreshed", "pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed", "pocketlab.dlq.original_subject"],
            "backendOwner": "catalog router / action queue / domain command handler",
            "targetShape": {"type": "catalog", "ref": "default"},
            "paramsShape": {"source_mode": "repository|oci|zip|http"},
            "safety": "Write action. Requires FastAPI, NATS, JetStream, and worker readiness. Fails closed when degraded.",
            "notes": "Used by the App Catalog and release workflow to refresh visible app/blueprint state.",
        },
    },
    {
        "metadata": {
            "name": "deploy_blueprint",
            "title": "Deploy Blueprint",
            "description": "Deploy an app or service blueprint from a selected source.",
            "tags": ["blueprint", "app-catalog", "write"],
        },
        "spec": {
            "professionalLabel": "Deploy Workload",
            "simpleLabel": "Install",
            "uiEntrypoints": ["App Catalog", "Blueprint Registry", "Apps & Services"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.operation.execute",
            "successEvents": ["pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed", "pocketlab.dlq.original_subject"],
            "backendOwner": "operation service / worker domain command handler",
            "targetShape": {"type": "repository|oci|zip|http|local", "ref": "blueprint-ref"},
            "paramsShape": {"name": "string", "version": "string", "playbook": "string"},
            "safety": "Privileged write action. Must remain typed, auditable, and policy-guarded.",
            "notes": "Primary App Catalog install/deployment workflow.",
        },
    },
    {
        "metadata": {
            "name": "git_sync",
            "title": "GitOps Sync",
            "description": "Synchronize desired state from a Git source.",
            "tags": ["gitops", "sync", "write"],
        },
        "spec": {
            "professionalLabel": "Sync GitOps",
            "simpleLabel": "Keep my environment updated",
            "uiEntrypoints": ["GitOps Pipeline", "Keep My Environment Updated"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.operation.execute",
            "successEvents": ["pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "GitOps operation handler",
            "targetShape": {"type": "git", "ref": "repo-or-branch"},
            "paramsShape": {"branch": "string", "strategy": "safe-sync"},
            "safety": "Must not reintroduce retired sync shell compatibility paths.",
            "notes": "Replaces retired command-style sync flows with typed operation execution.",
        },
    },
    {
        "metadata": {
            "name": "drift_scan",
            "title": "Run Drift Scan",
            "description": "Compare actual runtime state against desired state.",
            "tags": ["drift", "health", "read"],
        },
        "spec": {
            "professionalLabel": "Run drift scan",
            "simpleLabel": "Check what changed",
            "uiEntrypoints": ["Drift Center", "Health & Issues"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.drift.scan",
            "successEvents": ["pocketlab.events.drift.scan_completed", "pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "drift service / domain command handler",
            "targetShape": {"type": "environment", "ref": "default"},
            "paramsShape": {"scope": "default|fleet|blueprint|security"},
            "safety": "Read/analysis workflow. Remediation must be a separate typed write operation.",
            "notes": "Detects state differences and feeds Drift Center.",
        },
    },
    {
        "metadata": {
            "name": "drift_preview",
            "title": "Preview Drift Remediation",
            "description": "Preview the action required to remediate drift.",
            "tags": ["drift", "preview", "read"],
        },
        "spec": {
            "professionalLabel": "Preview remediation",
            "simpleLabel": "Preview fix",
            "uiEntrypoints": ["Drift Center"],
            "apiEntrypoints": ["/api/operations/preview", "/api/operations/execute"],
            "natsSubject": "pocketlab.commands.drift.preview",
            "successEvents": ["pocketlab.events.operation.previewed"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "drift service",
            "targetShape": {"type": "drift", "ref": "drift-id"},
            "paramsShape": {"dry_run": True},
            "safety": "Preview-only. Must not mutate runtime state.",
            "notes": "Used before approving/applying remediation.",
        },
    },
    {
        "metadata": {
            "name": "drift_approve",
            "title": "Approve Drift Remediation",
            "description": "Approve a drift remediation plan.",
            "tags": ["drift", "approval", "write"],
        },
        "spec": {
            "professionalLabel": "Approve remediation",
            "simpleLabel": "Approve fix",
            "uiEntrypoints": ["Drift Center"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.drift.approve",
            "successEvents": ["pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "drift service",
            "targetShape": {"type": "drift", "ref": "drift-id"},
            "paramsShape": {"approved_by": "operator"},
            "safety": "Approval action. Must be auditable.",
            "notes": "Separates approval from apply.",
        },
    },
    {
        "metadata": {
            "name": "drift_apply",
            "title": "Apply Drift Remediation",
            "description": "Apply approved drift remediation.",
            "tags": ["drift", "remediation", "write"],
        },
        "spec": {
            "professionalLabel": "Apply remediation",
            "simpleLabel": "Fix issue",
            "uiEntrypoints": ["Drift Center"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.drift.apply",
            "successEvents": ["pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed", "pocketlab.dlq.original_subject"],
            "backendOwner": "drift worker handler",
            "targetShape": {"type": "drift", "ref": "drift-id"},
            "paramsShape": {"mode": "approved"},
            "safety": "Write action. Requires healthy control plane and prior approval.",
            "notes": "Should not run as an implicit side effect of scan.",
        },
    },
    {
        "metadata": {
            "name": "drift_ignore",
            "title": "Ignore Drift Finding",
            "description": "Mark a drift finding as accepted or ignored.",
            "tags": ["drift", "exception", "write"],
        },
        "spec": {
            "professionalLabel": "Ignore finding",
            "simpleLabel": "Ignore this change",
            "uiEntrypoints": ["Drift Center"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.drift.ignore",
            "successEvents": ["pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "drift service",
            "targetShape": {"type": "drift", "ref": "drift-id"},
            "paramsShape": {"reason": "string"},
            "safety": "State mutation. Must be auditable.",
            "notes": "Used for intentional drift exceptions.",
        },
    },
    {
        "metadata": {
            "name": "fleet_join",
            "title": "Join Fleet",
            "description": "Create onboarding material for a new fleet or mesh device.",
            "tags": ["fleet", "onboarding", "secret"],
        },
        "spec": {
            "professionalLabel": "Join Fleet",
            "simpleLabel": "Add Device",
            "uiEntrypoints": ["Mesh Fleet", "My Devices"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.fleet.join",
            "successEvents": ["pocketlab.events.fleet.invite_created", "pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "fleet router / fleet service / domain command handler",
            "targetShape": {"type": "fleet-node", "ref": "node-name"},
            "paramsShape": {"role": "compute|storage|observer|controller"},
            "safety": "Sensitive onboarding action. Join secrets must be redacted.",
            "notes": "Supports zero-touch fleet onboarding and mesh agent workflows.",
        },
    },
    {
        "metadata": {
            "name": "rotate_secret",
            "title": "Rotate Secret",
            "description": "Rotate a secret through Identity Vault.",
            "tags": ["vault", "secret", "write"],
        },
        "spec": {
            "professionalLabel": "Rotate Secret",
            "simpleLabel": "Change Password",
            "uiEntrypoints": ["Identity Vault", "Passwords & Access"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.vault.rotate",
            "successEvents": ["pocketlab.events.vault.secret_rotated", "pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "vault domain command handler",
            "targetShape": {"type": "secret", "ref": "vault/path/redacted"},
            "paramsShape": {"rotation_policy": "default"},
            "safety": "High sensitivity. Secret values must never appear in logs/events.",
            "notes": "Simple Mode exposes this as Change Password.",
        },
    },
    {
        "metadata": {
            "name": "secret_read_dynamic",
            "title": "Read Dynamic Secret",
            "description": "Request or renew a dynamic secret lease.",
            "tags": ["vault", "dynamic-secret", "read"],
        },
        "spec": {
            "professionalLabel": "Read dynamic secret",
            "simpleLabel": "Get temporary password",
            "uiEntrypoints": ["Identity Vault", "Passwords & Access"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.vault.dynamic_secret",
            "successEvents": ["pocketlab.events.vault.lease_created", "pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "vault domain command handler",
            "targetShape": {"type": "dynamic-secret", "ref": "role-name"},
            "paramsShape": {"ttl": "string"},
            "safety": "Lease values must be redacted and not persisted in UI-visible events.",
            "notes": "Useful for short-lived credentials.",
        },
    },
    {
        "metadata": {
            "name": "backup_now",
            "title": "Create Backup",
            "description": "Create a runtime backup snapshot.",
            "tags": ["backup", "disaster-recovery", "write"],
        },
        "spec": {
            "professionalLabel": "Backup now",
            "simpleLabel": "Save a copy",
            "uiEntrypoints": ["Disaster Recovery", "Release Workflow"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.operation.execute",
            "successEvents": ["pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "backup/disaster recovery handler",
            "targetShape": {"type": "state", "ref": "default"},
            "paramsShape": {"include_event_journal": True},
            "safety": "Must verify destination space and redact sensitive data.",
            "notes": "Used before release apply and restore workflows.",
        },
    },
    {
        "metadata": {
            "name": "backup_verify",
            "title": "Verify Backup",
            "description": "Verify backup manifest and integrity.",
            "tags": ["backup", "disaster-recovery", "read"],
        },
        "spec": {
            "professionalLabel": "Verify backup",
            "simpleLabel": "Check saved copy",
            "uiEntrypoints": ["Disaster Recovery"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.operation.execute",
            "successEvents": ["pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "backup/disaster recovery handler",
            "targetShape": {"type": "backup", "ref": "backup-id"},
            "paramsShape": {"manifest": "manifest-ref"},
            "safety": "Read/verification workflow. Should not mutate runtime state.",
            "notes": "Prevents restoring from incomplete or corrupt backups.",
        },
    },
    {
        "metadata": {
            "name": "restore_backup",
            "title": "Restore Backup",
            "description": "Restore runtime state from a verified backup.",
            "tags": ["backup", "disaster-recovery", "destructive"],
        },
        "spec": {
            "professionalLabel": "Restore backup",
            "simpleLabel": "Restore saved copy",
            "uiEntrypoints": ["Disaster Recovery"],
            "apiEntrypoints": ["/api/operations/execute", "/api/operations/preview"],
            "natsSubject": "pocketlab.commands.operation.execute",
            "successEvents": ["pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed", "pocketlab.dlq.original_subject"],
            "backendOwner": "backup/disaster recovery handler",
            "targetShape": {"type": "backup", "ref": "backup-id"},
            "paramsShape": {"preview": True, "confirm": True},
            "safety": "Destructive write. Requires preview, confirmation, and healthy control plane.",
            "notes": "Should show overwrite warnings and estimated restore size.",
        },
    },
    {
        "metadata": {
            "name": "release_check",
            "title": "Check Release",
            "description": "Check whether a new Pocket Lab release is available.",
            "tags": ["release", "read"],
        },
        "spec": {
            "professionalLabel": "Check release",
            "simpleLabel": "Check for update",
            "uiEntrypoints": ["Release Workflow"],
            "apiEntrypoints": ["/api/release/self-update/check"],
            "natsSubject": "pocketlab.commands.release.check",
            "successEvents": ["pocketlab.events.release.workflow.started", "pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "release orchestrator",
            "targetShape": {"type": "release-channel", "ref": "stable"},
            "paramsShape": {"channel": "stable|latest"},
            "safety": "Read/check workflow. Must not apply changes.",
            "notes": "Populates current/target release state.",
        },
    },
    {
        "metadata": {
            "name": "release_apply",
            "title": "Apply Release",
            "description": "Apply available release through backup, sync, deploy, verify, and catalog refresh stages.",
            "tags": ["release", "upgrade", "write"],
        },
        "spec": {
            "professionalLabel": "Apply latest",
            "simpleLabel": "Update now",
            "uiEntrypoints": ["Release Workflow"],
            "apiEntrypoints": ["/api/release/self-update/apply"],
            "natsSubject": "pocketlab.commands.release.apply",
            "successEvents": ["pocketlab.events.release.workflow.completed", "pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.release.workflow.failed", "pocketlab.events.operation.failed"],
            "backendOwner": "release orchestrator",
            "targetShape": {"type": "release", "ref": "target-version"},
            "paramsShape": {"channel": "stable|latest", "backup_before_apply": True},
            "safety": "High-impact write. Must backup before apply and fail closed when degraded.",
            "notes": "Release timeline should expose every stage.",
        },
    },
    {
        "metadata": {
            "name": "health_check",
            "title": "Run Health Check",
            "description": "Run health engine check and emit health status.",
            "tags": ["health", "noc", "read"],
        },
        "spec": {
            "professionalLabel": "Refresh health snapshot",
            "simpleLabel": "Check system health",
            "uiEntrypoints": ["NOC Telemetry", "System Status", "Health Engine"],
            "apiEntrypoints": ["/api/health/check"],
            "natsSubject": "pocketlab.commands.health.check",
            "successEvents": ["pocketlab.events.health.checked"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "health engine / Gatus integration",
            "targetShape": {"type": "health", "ref": "control-plane"},
            "paramsShape": {"scope": "all"},
            "safety": "Operational check. Should be safe to run repeatedly.",
            "notes": "Feeds health panels and degraded-mode indicators.",
        },
    },
    {
        "metadata": {
            "name": "security_scan",
            "title": "Run Security Scan",
            "description": "Run security posture or policy scan.",
            "tags": ["security", "policy", "read"],
        },
        "spec": {
            "professionalLabel": "Run security scan",
            "simpleLabel": "Check safety",
            "uiEntrypoints": ["Security Posture", "Safety Center"],
            "apiEntrypoints": ["/api/security/scan"],
            "natsSubject": "pocketlab.commands.security.scan",
            "successEvents": ["pocketlab.events.security.scan_completed"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "security posture / policy guardrails",
            "targetShape": {"type": "security-scope", "ref": "default"},
            "paramsShape": {"scan_type": "policy|posture|secrets"},
            "safety": "Scan workflow. Must redact findings containing secrets.",
            "notes": "Feeds Safety Center and Security Posture.",
        },
    },
    {
        "metadata": {
            "name": "configure_opa",
            "title": "Configure OPA",
            "description": "Configure or refresh OPA policy guardrails.",
            "tags": ["security", "opa", "policy", "write"],
        },
        "spec": {
            "professionalLabel": "Configure OPA",
            "simpleLabel": "Update safety rules",
            "uiEntrypoints": ["Policy Guardrails", "Safety Center"],
            "apiEntrypoints": ["/api/operations/execute"],
            "natsSubject": "pocketlab.commands.security.configure_opa",
            "successEvents": ["pocketlab.events.operation.succeeded"],
            "failureEvents": ["pocketlab.events.operation.failed"],
            "backendOwner": "policy guardrails / OPA integration",
            "targetShape": {"type": "policy", "ref": "opa-bundle"},
            "paramsShape": {"bundle": "string"},
            "safety": "Policy mutation. Must be auditable and recoverable.",
            "notes": "Controls policy behavior for blueprint and security workflows.",
        },
    },
]


def entity_for(operation: dict) -> dict:
    metadata = operation["metadata"]
    spec = operation["spec"]

    return {
        "apiVersion": "pocketlab.io/v1alpha1",
        "kind": "TypedOperation",
        "metadata": metadata,
        "spec": spec,
    }


def main() -> None:
    OPS_DIR.mkdir(parents=True, exist_ok=True)

    for operation in OPERATIONS:
        entity = entity_for(operation)
        name = entity["metadata"]["name"]
        path = OPS_DIR / f"{name}.yaml"

        if path.exists():
            print(f"Keeping existing operation metadata: {path}")
            continue

        path.write_text(
            yaml.safe_dump(entity, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"Wrote operation metadata: {path}")


if __name__ == "__main__":
    main()
