from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from contracts import utc_now_iso


def _stage(
    stage_id: str,
    title: str,
    purpose: str,
    files: list[dict[str, Any]],
    subsystems: list[str],
    steps: list[str],
    operations: list[dict[str, str]],
) -> Dict[str, Any]:
    return {
        "id": stage_id,
        "title": title,
        "purpose": purpose,
        "files": files,
        "subsystems": subsystems,
        "steps": steps,
        "operations": operations,
    }


def build_release_workflow(root_dir: str | Path) -> Dict[str, Any]:
    root = Path(root_dir)
    files = [
        {
            "path": "src/App.jsx",
            "role": "Adds the Release workflow tab to the application shell.",
        },
        {
            "path": "src/components/Header.jsx",
            "role": "Surfaces the Release workflow in the top navigation.",
        },
        {
            "path": "src/components/OTAUpdater.jsx",
            "role": "Keeps OTA/update actions aligned with the release promotion path and auto-refreshes clients.",
        },
        {
            "path": "src/main.jsx",
            "role": "Registers the PWA service worker so the release bundle can activate automatically.",
        },
        {
            "path": "vite.config.js",
            "role": "Configures Vite PWA auto-update for the served frontend bundle.",
        },
        {
            "path": "src/lib/operations.js",
            "role": "Provides typed helper calls for workflow execution and refreshes.",
        },
        {
            "path": "src/tabs/ReleaseWorkflowTab.jsx",
            "role": "Shows the concrete end-to-end release workflow and exposes stage actions.",
        },
        {
            "path": "src/tabs/GitOpsTab.jsx",
            "role": "Runs git sync and repository reconciliation from the UI.",
        },
        {
            "path": "src/tabs/AppStoreTab.jsx",
            "role": "Promotes catalogued workloads and blueprint sources.",
        },
        {
            "path": "src/tabs/BlueprintTab.jsx",
            "role": "Deploys repo, zip, OCI, or HTTP blueprint sources.",
        },
        {
            "path": "src/tabs/DriftCenterTab.jsx",
            "role": "Validates drift before and after promotion.",
        },
        {
            "path": "src/tabs/SecurityPostureTab.jsx",
            "role": "Blocks release promotion when posture is weak.",
        },
        {
            "path": "src/tabs/IdentityVaultTab.jsx",
            "role": "Handles vault-backed credentials and secret rotation during release prep.",
        },
        {
            "path": "pocket-lab-final-structure/runtime/api_fastapi/pocket_lab_fastapi_server.py",
            "role": "Exposes the workflow JSON endpoint, release auto-update APIs, and state views.",
        },
        {
            "path": "pocket-lab-final-structure/runtime/core/release_workflow.py",
            "role": "Defines the authoritative release workflow structure.",
        },
        {
            "path": "pocket-lab-final-structure/runtime/core/release_auto_update.py",
            "role": "Polls GitHub releases and auto-applies the release lifecycle.",
        },
        {
            "path": "pocket-lab-final-structure/runtime/api_fastapi/services/release_orchestrator.py",
            "role": "Runs release check/apply as event-orchestrated stages over the Pocket Lab event bus.",
        },
        {
            "path": "pocket-lab-final-structure/runtime/core/operations/service.py",
            "role": "Executes typed operations for the release lifecycle.",
        },
        {
            "path": "pocket-lab-final-structure/runtime/core/operations/registry.py",
            "role": "Maps release helper operations to canonical deployment actions.",
        },
        {
            "path": "Taskfile.yml",
            "role": "Declares operator-facing release tasks.",
        },
        {
            "path": "pocket-lab-final-structure/README.md",
            "role": "Documents the release sequence for the archive.",
        },
    ]

    stages = [
        _stage(
            "develop-and-validate",
            "1. Develop and validate locally",
            "Change code safely before any public commit.",
            [
                {
                    "path": "src/App.jsx",
                    "note": "Wire the release workflow UI into the app shell.",
                },
                {
                    "path": "src/components/Header.jsx",
                    "note": "Expose the workflow as a visible navigation entry.",
                },
                {
                    "path": "src/components/OTAUpdater.jsx",
                    "note": "Keep update messaging aligned with release promotion.",
                },
                {
                    "path": "src/lib/operations.js",
                    "note": "Add helpers for workflow fetch/refresh calls.",
                },
                {
                    "path": "src/tabs/ReleaseWorkflowTab.jsx",
                    "note": "Render the step-by-step release plan.",
                },
                {
                    "path": "pocket-lab-final-structure/runtime/api_fastapi/pocket_lab_fastapi_server.py",
                    "note": "Serve workflow metadata from FastAPI.",
                },
                {
                    "path": "pocket-lab-final-structure/runtime/core/release_workflow.py",
                    "note": "Store the canonical workflow definition.",
                },
            ],
            [
                "Frontend PWA",
                "Pocket Lab FastAPI/NATS control plane",
                "Typed operation client",
                "Workflow metadata service",
            ],
            [
                "Edit the relevant frontend and backend files.",
                "Run the frontend build and verify the release tab renders.",
                "Preview the typed operations before promotion.",
            ],
            [
                {"name": "preview", "operation": "drift_scan"},
                {"name": "validate", "operation": "backup_verify"},
            ],
        ),
        _stage(
            "commit-and-release-artifact",
            "2. Commit and publish the code release",
            "Turn the validated change set into the source of truth.",
            [
                {
                    "path": "Taskfile.yml",
                    "note": "Add release tasks so operators can run the same flow by name.",
                },
                {
                    "path": "pocket-lab-final-structure/README.md",
                    "note": "Record the workflow in the archive documentation.",
                },
                {
                    "path": "src/tabs/GitOpsTab.jsx",
                    "note": "Surface repo sync and release sequencing.",
                },
            ],
            ["GitHub Repo", "Release tagging", "Taskfile", "GitOps UI"],
            [
                "Commit only source files and workflow docs.",
                "Push the change set to the public GitHub repository.",
                "Create or update the release tag that the PWA updater checks.",
            ],
            [
                {"name": "sync", "operation": "git_sync"},
            ],
        ),
        _stage(
            "sync-and-catalog",
            "3. Sync repository state and refresh the catalog",
            "Make the GitHub commit visible to Pocket Lab services.",
            [
                {
                    "path": "src/tabs/GitOpsTab.jsx",
                    "note": "Trigger git sync from the UI.",
                },
                {
                    "path": "pocket-lab-final-structure/runtime/core/operations/service.py",
                    "note": "Execute the git sync and catalog-aware operation.",
                },
                {
                    "path": "pocket-lab-final-structure/runtime/core/operations/registry.py",
                    "note": "Keep compatibility aliases mapped to typed operations.",
                },
            ],
            [
                "GitOps subsystem",
                "Dulwich repository layer",
                "Catalog store",
                "Release workflow API",
            ],
            [
                "Pull the new commit into the local repo cache.",
                "Refresh the catalog so blueprint and app-store views show the new version.",
                "Persist the repo snapshot and any rollback pointer.",
            ],
            [
                {"name": "git_sync", "operation": "git_sync"},
                {"name": "catalog_refresh", "operation": "catalog_refresh"},
            ],
        ),
        _stage(
            "gate-and-deploy",
            "4. Gate the release and deploy the target runtime",
            "Use the existing safety subsystems before any rollout.",
            [
                {
                    "path": "src/tabs/SecurityPostureTab.jsx",
                    "note": "Confirm policy posture is acceptable.",
                },
                {
                    "path": "src/tabs/IdentityVaultTab.jsx",
                    "note": "Ensure secrets and dynamic credentials are ready.",
                },
                {
                    "path": "src/tabs/AppStoreTab.jsx",
                    "note": "Promote catalogued workloads.",
                },
                {
                    "path": "src/tabs/BlueprintTab.jsx",
                    "note": "Deploy the selected blueprint source.",
                },
                {
                    "path": "pocket-lab-final-structure/runtime/core/operations/service.py",
                    "note": "Run backup, deploy, and restore logic through typed ops.",
                },
                {
                    "path": "pocket-lab-final-structure/runtime/core/artifacts/oras_store.py",
                    "note": "Serve OCI blueprint artifacts when used.",
                },
                {
                    "path": "pocket-lab-final-structure/runtime/core/ansible/runner_service.py",
                    "note": "Run the actual deploy playbook execution.",
                },
            ],
            [
                "Security guardrails",
                "Vault",
                "App Store",
                "Blueprint engine",
                "Ansible runner",
                "OCI store",
            ],
            [
                "Take a backup snapshot before promotion.",
                "Apply the blueprint or workload through the typed operation layer.",
                "Rotate secrets only when the deployment path requires it.",
            ],
            [
                {"name": "backup_now", "operation": "backup_now"},
                {"name": "deploy_blueprint", "operation": "deploy_blueprint"},
                {"name": "rotate_secret", "operation": "rotate_secret"},
            ],
        ),
        _stage(
            "verify-and-propagate",
            "5. Verify drift, health, and user propagation",
            "Confirm the change is stable and visible to users.",
            [
                {
                    "path": "src/tabs/DriftCenterTab.jsx",
                    "note": "Run post-deploy drift scans and review diffs.",
                },
                {
                    "path": "src/components/OTAUpdater.jsx",
                    "note": "Detect the new release tag and prompt the user-facing refresh.",
                },
                {
                    "path": "src/App.jsx",
                    "note": "Keep the updated UI in the shell navigation.",
                },
                {
                    "path": "pocket-lab-final-structure/runtime/api_fastapi/pocket_lab_fastapi_server.py",
                    "note": "Expose health, drift, catalog, and operations state through FastAPI routers.",
                },
            ],
            [
                "Drift Center",
                "Health engine",
                "PWA auto-update",
                "Operations history",
                "User clients",
            ],
            [
                "Run drift verification after deployment.",
                "Check health-engine and telemetry status.",
                "Let the browser service worker pick up the new frontend bundle.",
            ],
            [
                {"name": "drift_scan", "operation": "drift_scan"},
                {"name": "release_verify", "operation": "release_verify"},
            ],
        ),
        _stage(
            "self-update-propagation",
            "6. Auto-apply the release and refresh user instances",
            "Close the last mile so a GitHub commit can propagate without manual intervention.",
            [
                {
                    "path": "pocket-lab-final-structure/runtime/core/release_auto_update.py",
                    "note": "Polls GitHub Releases and drives the release lifecycle automatically.",
                },
                {
                    "path": "pocket-lab-final-structure/runtime/api_fastapi/pocket_lab_fastapi_server.py",
                    "note": "Exposes self-update status/check/apply endpoints through FastAPI.",
                },
                {
                    "path": "src/components/OTAUpdater.jsx",
                    "note": "Observes release status and refreshes the browser when the new bundle is active.",
                },
                {
                    "path": "src/main.jsx",
                    "note": "Registers the PWA service worker so a new build can activate automatically.",
                },
                {
                    "path": "vite.config.js",
                    "note": "Keeps the PWA registered with auto-update mode enabled.",
                },
            ],
            [
                "Release auto-updater",
                "GitHub Releases",
                "PWA service worker",
                "Browser clients",
                "Reload loop",
            ],
            [
                "Detect a newer release tag from GitHub.",
                "Automatically run backup, sync, catalog refresh, deploy, drift verification, health verification, and app refresh readiness through the typed operation layer.",
                "Mark the release applied, then let the PWA/service worker and browser reload pull the new bundle.",
            ],
            [],
        ),
    ]

    return {
        "name": "Pocket Lab Release Workflow",
        "version": "1.1-phase8",
        "updated_at": utc_now_iso(),
        "root_dir": str(root),
        "ignore": ["24. Desktop Version (Future)"],
        "files": files,
        "stages": stages,
        "summary": [
            "Frontend change is committed to GitHub.",
            "GitOps sync updates the repo cache and catalog.",
            "Security, vault, drift, and health gates protect promotion.",
            "Blueprint and workload deployment happens through typed operations.",
            "Clients receive the new release through the served PWA bundle.",
            "A NATS-backed release orchestrator emits each update stage as live events for Simple and Professional Mode.",
        ],
    }
