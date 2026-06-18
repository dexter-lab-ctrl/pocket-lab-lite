#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import textwrap


ROOT = Path.cwd()
DOCS = ROOT / "docs"


def write_doc(path: str, content: str) -> None:
    target = DOCS / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    print(f"wrote: docs/{path}")


def patch_mkdocs_nav() -> None:
    mkdocs = ROOT / "mkdocs.yml"
    if not mkdocs.exists():
        print("mkdocs.yml not found; skipping nav patch")
        return

    text = mkdocs.read_text(encoding="utf-8")

    replacements = {
        "architecture/enterprise-architecture-blueprint.html": "architecture/enterprise-architecture-blueprint.md",
        "product/pocket_lab_ui_screen_reference_manual.md": "product/ui-screen-reference.md",
        "product/ui-screen-reference.md": "product/ui-screen-reference.md",
        "api/pocket_lab_backend_api_contract_reference.md": "api/backend-api-contract.md",
        "api/backend-api-contract.md": "api/backend-api-contract.md",
        "runtime/pocket_lab_nats_jetstream_event_contract.md": "runtime/nats-jetstream-event-contract.md",
        "runtime/nats-jetstream-event-contract.md": "runtime/nats-jetstream-event-contract.md",
        "runtime/pocket_lab_typed_operations_catalog.md": "runtime/typed-operations-catalog.md",
        "runtime/typed-operations-catalog.md": "runtime/typed-operations-catalog.md",
        "deployment-runtime-blueprint.md": "architecture/deployment-runtime-blueprint.md",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    # Ensure plugin does not produce strict-mode failures on moved/copied docs.
    if "git-revision-date-localized:" in text and "enable_git_follow: false" not in text:
        text = text.replace(
            "  - git-revision-date-localized:\n      enable_creation_date: true",
            "  - git-revision-date-localized:\n      enable_creation_date: true\n      enable_git_follow: false\n      fallback_to_build_date: true",
        )

    mkdocs.write_text(text, encoding="utf-8")
    print("patched: mkdocs.yml")


def fix_archived_readme_links() -> None:
    p = DOCS / "history/documentation-project/DOCS_SOURCE_README.md"
    if not p.exists():
        return

    text = p.read_text(encoding="utf-8")
    text = text.replace("./dev/README.md", "../dev-legacy/README.md")
    text = text.replace("./prod/README.md", "../prod-legacy/README.md")
    p.write_text(text, encoding="utf-8")
    print("fixed: docs/history/documentation-project/DOCS_SOURCE_README.md links")


def main() -> None:
    print("==> Populating high-quality Pocket Lab documentation pages")

    sections = [
        "product",
        "architecture",
        "security",
        "operations",
        "release",
        "validation",
        "performance",
        "platform",
        "blueprints",
        "fleet",
        "observability",
    ]
    for section in sections:
        (DOCS / section).mkdir(parents=True, exist_ok=True)

    write_doc(
        "product/operator-guide.md",
        r"""
        # Pocket Lab Product Overview / Operator Guide

        ## Purpose

        Pocket Lab is an edge-first, self-hosted control-plane and lab orchestration platform for constrained environments such as Android/Termux, small Linux nodes, home labs, portable security labs, and edge devices.

        The app gives an operator a browser-based interface to manage Apps and Services, GitOps synchronization, Blueprint deployment, Drift detection, Fleet devices, Vault and secrets workflows, Security Posture, NOC telemetry, Backup and Restore, Release updates, and event/audit visibility.

        ## Runtime Model

        Pocket Lab is built around four core layers:

        ```mermaid
        flowchart LR
          User[Operator] --> UI[React / Vite PWA]
          UI --> API[FastAPI Control Plane]
          API --> NATS[NATS / JetStream]
          NATS --> Worker[Typed Operation Worker]
          Worker --> State[State + Event Journal]
          Worker --> Tools[Git / Ansible / ORAS / Vault / OPA]
          State --> UI
        ```

        The UI does not execute local commands directly. User actions become typed operations. FastAPI validates and accepts the request, NATS / JetStream persists the command, and the worker executes the operation.

        ## User Modes

        Pocket Lab supports both non-technical and technical operators.

        | Professional Mode | Simple Mode |
        |---|---|
        | App Catalog | Apps & Services |
        | GitOps Pipeline | Keep My Environment Updated |
        | Drift Center | Health & Issues |
        | Mesh Fleet | My Devices |
        | Identity Vault | Passwords & Access |
        | Security Posture | Safety Center |
        | NOC Telemetry | System Status |

        Simple Mode keeps the same backend behavior but changes labels and explanations so non-technical users can safely operate the platform.

        ## Core Operator Workflows

        ### Refresh Apps and Services

        1. Open **App Catalog** or **Apps & Services**.
        2. Click **Refresh catalog**.
        3. Pocket Lab submits a typed `catalog_refresh` operation.
        4. FastAPI publishes a command through NATS / JetStream.
        5. The worker refreshes catalog state and emits operation events.
        6. The UI updates status using live events or recent event replay.

        ### Install or Deploy an App

        1. Open **App Catalog**.
        2. Select repository, OCI artifact, ZIP, HTTP/HTTPS, or local source mode.
        3. Select the blueprint/app reference.
        4. Click **Deploy Workload** or **Install**.
        5. Pocket Lab submits `deploy_blueprint`.
        6. Progress appears in the operation panel.

        ### Check System Status

        1. Open **NOC Telemetry** or **System Status**.
        2. Review API, NATS, worker, health engine, CPU, memory, disk, fleet, and event state.
        3. If degraded, use the degraded-mode runbook before running write operations.

        ### Apply a Release

        1. Open **Release Workflow**.
        2. Click **Check release**.
        3. Review current and target release state.
        4. Click **Apply latest** only if the control plane is healthy.
        5. Pocket Lab runs backup, sync, deploy, verify, and catalog refresh stages.

        ### Respond to Drift

        1. Open **Drift Center**.
        2. Review detected differences between desired and actual state.
        3. Decide whether to rescan, preview, approve, apply, or ignore.
        4. Use operation history and events to verify the outcome.

        ## Safety Behavior

        Pocket Lab avoids hidden or unsafe fallbacks.

        | Condition | Expected Behavior |
        |---|---|
        | NATS unavailable | Write actions fail closed. |
        | JetStream unavailable | Durable writes are blocked. |
        | Worker unavailable | Operations are not executed locally as a fallback. |
        | Vault sealed | Secrets workflows show degraded state. |
        | WebSocket unavailable | UI falls back to recent events where supported. |
        | Malformed data | UI fails soft instead of crashing. |
        | Retired operation path | Build/test gates should reject it. |

        ## Operator Do / Do Not

        Operators should:

        - Use typed UI actions instead of direct state edits.
        - Review degraded banners before write operations.
        - Validate release readiness before applying updates.
        - Verify backups before risky changes.
        - Use event history to troubleshoot failures.

        Operators should not:

        - Bypass FastAPI and NATS for writes.
        - Reintroduce retired operation names.
        - Call internal service APIs directly from the frontend.
        - Store plaintext secrets in docs, logs, events, or backup manifests.
        - Ignore failed release or restore stages.

        ## Related Docs

        - [Screen-by-Screen UI/UX Manual](ui-screen-reference.md)
        - [Backend API Contract](../api/backend-api-contract.md)
        - [NATS / JetStream Event Contract](../runtime/nats-jetstream-event-contract.md)
        - [Typed Operations Catalog](../runtime/typed-operations-catalog.md)
        - [Degraded Mode Runbook](../operations/degraded-mode-runbook.md)
        """,
    )

    write_doc(
        "architecture/deployment-runtime-blueprint.md",
        r"""
        # Deployment / Runtime Blueprint

        ## Purpose

        This blueprint describes how Pocket Lab runs as a production-style edge control plane. It focuses on runtime components, process boundaries, state, startup order, and safety behavior.

        ## Runtime Topology

        ```mermaid
        flowchart TB
          Browser[Browser / PWA] --> FastAPI[FastAPI Control Plane]
          FastAPI --> NATS[NATS Server]
          NATS --> JetStream[JetStream Streams]
          JetStream --> Worker[Pocket Lab Worker]
          Worker --> State[State Directory]
          Worker --> Journal[Event Journal]
          Worker --> Tools[Git / Ansible / ORAS / Vault / OPA]
          FastAPI --> State
          FastAPI --> Journal
          Journal --> Browser
        ```

        ## Core Runtime Components

        | Component | Responsibility |
        |---|---|
        | React/Vite PWA | Operator interface and workflow launcher. |
        | FastAPI | API contract, readiness, route validation, and command submission. |
        | NATS | Command and event transport. |
        | JetStream | Durable command/event persistence. |
        | Worker | Executes typed operations and emits lifecycle events. |
        | Event journal | Supports replay, recovery, and operator evidence. |
        | State directory | Stores runtime state, catalog state, workflow state, fleet metadata, release state, and backup metadata. |

        ## Startup Order

        ```mermaid
        sequenceDiagram
          participant N as NATS / JetStream
          participant A as FastAPI
          participant W as Worker
          participant U as UI

          N->>N: Start streams and durable consumers
          A->>N: Verify NATS and JetStream readiness
          W->>N: Subscribe to command subjects
          U->>A: Load /ready and runtime status
          A->>U: Return healthy or degraded state
        ```

        Recommended order:

        1. Start NATS with JetStream enabled.
        2. Start FastAPI.
        3. Start the Pocket Lab worker.
        4. Serve the PWA/static frontend.
        5. Start optional observability and fleet integrations.

        ## State Model

        | State Category | Examples |
        |---|---|
        | Operation state | Accepted, running, succeeded, failed, retrying, dead-lettered. |
        | Event journal | Append-only operation, health, release, fleet, and audit events. |
        | Catalog state | App/blueprint metadata and refresh results. |
        | Release state | Current version, target version, release stages, failures. |
        | Fleet state | Agent ID, role, last seen, status, telemetry. |
        | Backup state | Backup references, manifests, checksums, verification status. |

        ## Runtime Readiness

        Pocket Lab distinguishes health from readiness.

        | State | Meaning |
        |---|---|
        | Healthy | API, NATS, JetStream, worker, and state are available. |
        | Degraded | Reads may work but writes may be blocked. |
        | Unavailable | Control plane cannot operate safely. |
        | Maintenance | A dependency is intentionally unavailable. |

        ## Write Flow

        ```mermaid
        flowchart LR
          Button[UI Button] --> API[FastAPI Write Route]
          API --> Auth{Authorized?}
          Auth -- No --> Reject[Reject]
          Auth -- Yes --> Ready{NATS + JetStream + Worker Ready?}
          Ready -- No --> Block[Fail Closed]
          Ready -- Yes --> Cmd[Publish Typed Command]
          Cmd --> Worker[Worker Executes]
          Worker --> Events[Emit Events]
          Events --> UI[UI Updates]
        ```

        ## Runtime Environment Variables

        | Variable | Purpose |
        |---|---|
        | `POCKETLAB_STATE_DIR` | Root state directory. |
        | `POCKETLAB_NATS_URL` | NATS connection URL. |
        | `POCKETLAB_NATS_REQUIRED` | Enforces NATS requirement for write safety. |
        | `POCKETLAB_NATS_REQUIRE_JETSTREAM` | Enforces JetStream requirement. |
        | `POCKETLAB_AUTH_TOKEN` | Optional API authentication token. |
        | `POCKETLAB_WRITE_TOKEN` | Optional write-protection token. |
        | `POCKETLAB_RELEASE_CHANNEL` | Release channel selection. |
        | `POCKETLAB_LOG_LEVEL` | Runtime logging verbosity. |

        ## Network Interfaces

        | Interface | Consumer | Purpose |
        |---|---|---|
        | `/health` | Supervisors | Basic API liveness. |
        | `/ready` | UI / supervisors | Runtime readiness and degraded state. |
        | `/api/*` | UI | Backend API contract. |
        | `/ws/events` | UI | Live event stream. |
        | NATS subjects | API / worker / agents | Durable commands and events. |

        ## Deployment Units

        | Unit | Required | Notes |
        |---|---|---|
        | PWA static bundle | Yes | Built from React/Vite. |
        | FastAPI service | Yes | Owns API contract. |
        | Worker service | Yes | Owns operation execution. |
        | NATS + JetStream | Yes | Required for safe writes. |
        | Persistent state volume | Yes | Required for replay/recovery. |
        | Optional tools | Depends | Git, Ansible, ORAS, Vault, OPA, etc. |

        ## Backup Scope

        Backups should include state, event journal, operation history, release metadata, fleet metadata, catalog metadata, and backup manifests. Secrets should only be included if encrypted and explicitly governed by the secret-handling policy.
        """,
    )

    # Compatibility copy if old nav or external links use the root path.
    write_doc(
        "deployment-runtime-blueprint.md",
        (DOCS / "architecture/deployment-runtime-blueprint.md").read_text(encoding="utf-8"),
    )

    write_doc(
        "security/security-architecture-threat-model.md",
        r"""
        # Security Architecture & Threat Model

        ## Purpose

        This document defines Pocket Lab's security architecture, trust boundaries, likely threats, and required mitigations.

        ## Security Principles

        Pocket Lab follows these principles:

        - Typed operations only.
        - Fail-closed write behavior.
        - No browser-side local command execution.
        - No retired compatibility paths.
        - Redacted logs, events, audit records, and DLQ payloads.
        - API contract governance.
        - Least-privilege NATS subject permissions.
        - Clear trust boundaries.
        - Safe degraded-mode behavior.

        ## Trust Boundaries

        ```mermaid
        flowchart TB
          Browser[Browser / PWA] --> API[FastAPI API Boundary]
          API --> Bus[NATS / JetStream Boundary]
          Bus --> Worker[Worker Execution Boundary]
          Worker --> State[State Store Boundary]
          Worker --> Secrets[Vault / Secret Boundary]
          Worker --> Tools[External Tool Boundary]
        ```

        ## Protected Assets

        | Asset | Protection Requirement |
        |---|---|
        | API tokens | Never expose in UI, logs, or events. |
        | Write tokens | Required for protected write routes where enabled. |
        | Vault secrets | Never persist unredacted. |
        | Operation payloads | Validate and redact sensitive fields. |
        | NATS subjects | Restrict by client role. |
        | Event journal | Redact sensitive data and preserve integrity. |
        | Backups | Verify integrity and protect sensitive content. |

        ## Threat Scenarios

        | Threat | Example | Mitigation |
        |---|---|---|
        | Malicious blueprint | Blueprint attempts unsafe execution or secret exfiltration. | Policy guardrails, typed operation validation, source validation. |
        | Poisoned catalog | Catalog returns malformed or malicious payloads. | Contract validation and UI fail-soft guards. |
        | Token leakage | Token appears in operation logs or UI events. | Redaction tests and structured logging policy. |
        | Worker bypass | UI attempts direct execution instead of worker path. | All writes route through FastAPI and NATS. |
        | Event injection | Untrusted producer emits fake success events. | NATS permissions and audit checks. |
        | Fleet spoofing | Fake agent reports healthy status. | Agent identity, scoped subjects, validated join payloads. |
        | Release tampering | Bad artifact applied to runtime. | Release dry-run, verification, backup, rollback. |

        ## Authentication and Authorization

        | Route Type | Requirement |
        |---|---|
        | Read routes | Authentication where configured. |
        | Write routes | Write authorization where configured. |
        | WebSocket events | Session/read authorization where configured. |
        | Fleet join | Controlled join payload or token. |

        ## NATS Permission Model

        | Role | Publish | Subscribe |
        |---|---|---|
        | FastAPI | Command subjects, audit records | Status/reply subjects if needed |
        | Worker | Operation events, audit records, DLQ | Command subjects |
        | Fleet agent | Fleet telemetry/events | Agent-scoped command subjects |
        | UI | None directly | Via FastAPI/WebSocket only |

        ## Redaction Requirements

        Redact values whose keys or meanings include:

        - `token`
        - `secret`
        - `password`
        - `authorization`
        - `api_key`
        - `private_key`
        - Vault response material
        - Fleet join secrets

        Redaction applies to FastAPI logs, worker logs, event journal entries, audit events, UI-visible event streams, and DLQ records.

        ## Fail-Closed Write Model

        ```mermaid
        flowchart LR
          Write[Write Request] --> Auth{Authorized?}
          Auth -- No --> Deny[Deny]
          Auth -- Yes --> Ready{Control Plane Ready?}
          Ready -- No --> Block[Fail Closed]
          Ready -- Yes --> Typed{Typed Operation?}
          Typed -- No --> Deny
          Typed -- Yes --> NATS[Publish Command]
        ```

        ## Required Security Gates

        | Gate | Purpose |
        |---|---|
        | `task test:redaction` | Ensures secrets are not emitted in logs/events. |
        | `task test:nats-permissions` | Simulates subject permission boundaries. |
        | `task check:api-contract` | Prevents frontend/backend contract drift. |
        | `task test:faults` | Validates fail-closed behavior. |
        | `task test:network` | Ensures frontend writes use typed non-legacy payloads. |
        | `task test:e2e` | Validates operator workflows remain non-legacy. |

        ## Maintenance Rule

        Any change to auth, secrets, policies, NATS subjects, operation payloads, fleet identity, backup behavior, or release behavior must update this document.
        """,
    )

    write_doc(
        "operations/degraded-mode-runbook.md",
        r"""
        # Reliability / Degraded Mode Runbook

        ## Purpose

        This runbook explains how Pocket Lab behaves during partial failures and how an operator should recover safely.

        ## Design Principle

        Pocket Lab is designed to remain readable where possible while blocking unsafe writes when required infrastructure is unavailable.

        ```mermaid
        flowchart LR
          Failure[Runtime Failure] --> UI[Show Degraded State]
          UI --> Reads[Allow Safe Reads]
          UI --> Writes{Write Requested?}
          Writes -- No --> Continue[Continue Monitoring]
          Writes -- Yes --> Ready{NATS + JetStream + Worker Ready?}
          Ready -- No --> Block[Fail Closed]
          Ready -- Yes --> Execute[Run Typed Operation]
        ```

        ## Scenario: NATS Unavailable

        | Area | Behavior |
        |---|---|
        | UI | Shows degraded control plane. |
        | API | Rejects write operations. |
        | Worker | Cannot receive commands. |
        | Safety | No local fallback execution. |

        Recovery:

        1. Restart NATS with JetStream enabled.
        2. Verify `/api/nats/status`.
        3. Verify `/ready`.
        4. Restart worker if needed.
        5. Retry the typed operation.

        ## Scenario: Worker Unavailable

        | Area | Behavior |
        |---|---|
        | UI | Shows worker unavailable/degraded. |
        | API | Should not allow unsafe writes. |
        | NATS | Commands should not be silently executed elsewhere. |

        Recovery:

        ```bash
        task dev:status
        task test:nats
        ```

        ## Scenario: JetStream Unavailable

        JetStream is required for durable write workflows. If JetStream is unavailable, Pocket Lab should not accept durable write operations.

        Recovery:

        1. Check NATS server configuration.
        2. Verify stream creation.
        3. Confirm durable consumer state.
        4. Restart worker and recheck readiness.

        ## Scenario: Vault Sealed

        | Area | Behavior |
        |---|---|
        | UI | Identity Vault / Passwords & Access shows degraded state. |
        | Backend | Secret operations fail safely. |
        | Logs | No secret material is emitted. |

        Recovery:

        1. Unseal or recover Vault.
        2. Refresh health engine state.
        3. Retry secret operation only after readiness is healthy.

        ## Scenario: WebSocket Unavailable

        The UI should reconnect or use recent event replay.

        Check:

        ```bash
        task test:websockets
        ```

        ## Scenario: Low Disk

        | Area | Behavior |
        |---|---|
        | NOC Telemetry | Shows low disk warning. |
        | Backup | May be blocked if insufficient space exists. |
        | Release | Should not proceed without safe backup capacity. |

        Recovery:

        1. Remove old logs or stale artifacts.
        2. Verify backup destination capacity.
        3. Recheck telemetry.
        4. Retry operation.

        ## Scenario: Stale Fleet Agent

        | Area | Behavior |
        |---|---|
        | Mesh Fleet | Shows stale/offline state. |
        | Events | Last heartbeat remains available. |
        | Operator | Investigates network, identity, and process health. |

        ## Scenario: Malformed Health or Catalog Payload

        The UI should fail soft and avoid React tree crashes.

        Recovery:

        1. Check recent frontend/backend changes.
        2. Run API contract tests.
        3. Run frontend E2E tests.
        4. Validate mock fixture shape.

        ```bash
        task check:api-contract
        task test:e2e
        task test:faults
        ```

        ## Recovery Order

        Use this order for most degraded scenarios:

        1. Restore NATS / JetStream.
        2. Restore FastAPI.
        3. Restore worker.
        4. Refresh health snapshot.
        5. Replay recent events.
        6. Retry typed operation.

        ## Validation

        ```bash
        task test:faults
        task test:websockets
        task check:api-contract
        ```

        ## Maintenance Rule

        Add or update a scenario whenever a new dependency, operation, event stream, fleet state, release stage, or degraded behavior is introduced.
        """,
    )

    write_doc(
        "release/release-workflow-upgrade-guide.md",
        r"""
        # Release Workflow & Upgrade Guide

        ## Purpose

        This guide explains how Pocket Lab checks, applies, verifies, and recovers from releases.

        ## Release Flow

        ```mermaid
        flowchart LR
          Check[Check Release] --> Backup[Create Backup]
          Backup --> Sync[Sync Artifacts]
          Sync --> Deploy[Deploy Runtime Update]
          Deploy --> Verify[Verify Health and Drift]
          Verify --> Catalog[Refresh Catalog]
          Catalog --> Notify[Notify Operator / PWA Refresh]
        ```

        ## User-Facing Controls

        | Control | Purpose |
        |---|---|
        | Check release | Checks whether a newer release exists. |
        | Apply latest | Starts release apply workflow. |
        | Release timeline | Shows stage progress and failures. |
        | Current/target version | Displays installed and available release state. |
        | Health status | Indicates whether the environment is safe to update. |

        ## Release Stages

        | Stage | Related Operation | Purpose |
        |---|---|---|
        | Prepare | `release_prepare`, `backup_now` | Create safety backup and prepare state. |
        | Sync | `release_sync`, `git_sync` | Sync release source or artifact. |
        | Deploy | `release_deploy`, `deploy_blueprint` | Apply runtime update. |
        | Verify | `release_verify`, `drift_scan` | Confirm expected state. |
        | Catalog refresh | `catalog_refresh` | Refresh Apps & Services state. |

        ## Backend Sequence

        ```mermaid
        sequenceDiagram
          participant UI
          participant API
          participant NATS
          participant Worker
          participant Events

          UI->>API: POST /api/release/self-update/apply
          API->>NATS: Publish release command
          Worker->>NATS: Consume command
          Worker->>Events: release.stage.started
          Worker->>Events: release.stage.completed
          Worker->>Events: release.workflow.completed
          API->>UI: Status and events
        ```

        ## Required Safety Rules

        - Backup must occur before apply.
        - Writes must use typed operations.
        - Retired paths must not be reintroduced.
        - Events must be persisted for replay.
        - Failed stages must be visible in the UI.
        - Rollback must be possible from a verified backup.
        - Catalog should refresh after successful release.

        ## Release Dry Run

        Before tagging or publishing:

        ```bash
        task release:dry-run
        ```

        The dry run should validate build artifacts, release metadata, PWA output, backend package readiness, documentation build, and required release files.

        ## Failure Recovery

        | Failure | Recovery |
        |---|---|
        | Check failed | Verify release source and network. |
        | Backup failed | Stop release; fix backup first. |
        | Sync failed | Check Git or artifact source. |
        | Deploy failed | Inspect logs and restore backup if needed. |
        | Verify failed | Treat as drift or partial update. |
        | Catalog refresh failed | Retry after control plane is healthy. |

        ## Rollback Guidance

        Rollback should use:

        1. Last verified backup.
        2. Release event timeline.
        3. Restore operation.
        4. Drift scan.
        5. Catalog refresh.
        6. Health verification.

        ## Maintenance Rule

        Any change to release stages, route names, event names, backup behavior, or UI release controls must update this guide and the Typed Operations Catalog.
        """,
    )

    write_doc(
        "validation/readiness-matrix.md",
        r"""
        # Validation / Release Gate Matrix

        ## Purpose

        This matrix tracks Pocket Lab's release-readiness gates and explains what each gate protects.

        ## Gate Matrix

        | Gate | Purpose | Release Requirement |
        |---|---|---|
        | `task check:api-contract` | Verifies frontend API calls are represented in FastAPI OpenAPI. | Required |
        | `task check:schemas` | Validates fixtures and event payloads. | Required |
        | `task test:backend` | Validates backend routes, services, and runtime behavior. | Required |
        | `task test:frontend` | Validates React/Vite build, lint, and frontend tests. | Required |
        | `task test:iac` | Validates IaC and drift assumptions. | Required |
        | `task test:bootstrap` | Validates Day 0 bootstrap scripts. | Required |
        | `task test:nats` | Validates NATS/FastAPI/worker typed operation flow. | Required |
        | `task test:nats-permissions` | Simulates subject permission boundaries. | Required |
        | `task test:websockets` | Validates live event stream behavior. | Required |
        | `task test:network` | Ensures frontend write payloads are typed and non-legacy. | Required |
        | `task test:redaction` | Ensures secrets are redacted from logs/events. | Required |
        | `task test:visual` | Runs visual regression checks. | Required |
        | `task test:lighthouse` | Validates production PWA quality. | Required |
        | `task test:a11y` | Validates accessibility basics. | Required |
        | `task test:golden` | Runs release-candidate golden operator path. | Required |
        | `task test:faults` | Validates degraded-mode and fail-closed behavior. | Required |
        | `task test:flakes` | Validates no hidden skips/focus/quarantine and repeated stability. | Required |
        | `task test:e2e` | Runs broad non-visual E2E suite. | Required |
        | `task test:performance` | Runs edge performance smoke tests. | Required |
        | `task android:smoke` | Validates Android/Termux target assumptions. | Required before edge release |
        | `task release:dry-run` | Validates release artifact workflow. | Required before tag/release |

        ## Release Blockers

        A release should not proceed if any of these fail:

        - API contract
        - Backend tests
        - Frontend build/tests
        - NATS integration
        - NATS permissions
        - Redaction
        - Golden path
        - Fault/degraded behavior
        - Full E2E
        - Release dry-run

        ## Evidence Requirements

        Each gate result should record:

        - Command
        - Date/time
        - Result
        - Important output
        - Fixes applied
        - Remaining advisories

        ## Advisory Debt

        Advisory debt may include npm audit warnings, non-critical Lighthouse improvements, or Git revision metadata warnings before docs are committed. Advisory debt should be tracked but does not always block release.

        ## Maintenance Rule

        Update this matrix whenever a gate is added, removed, renamed, or changes scope.
        """,
    )

    write_doc(
        "validation/test-strategy-quality-gates.md",
        r"""
        # Test Strategy & Quality Gates Guide

        ## Purpose

        This guide explains Pocket Lab's layered testing strategy and how each gate contributes to release confidence.

        ## Strategy

        ```mermaid
        flowchart TB
          Static[Static / Contract Checks] --> Unit[Backend + Frontend]
          Unit --> Integration[NATS / WebSockets / Network]
          Integration --> UI[Visual / Accessibility / E2E]
          UI --> Resilience[Golden / Faults / Flakes]
          Resilience --> Release[Performance / Android / Release Dry Run]
        ```

        ## Gate Definitions

        ### API Contract

        ```bash
        task check:api-contract
        ```

        Confirms frontend API calls are present in FastAPI OpenAPI.

        ### Backend

        ```bash
        task test:backend
        ```

        Validates backend routes, services, state handling, and runtime behavior.

        ### Frontend

        ```bash
        task test:frontend
        ```

        Validates React/Vite build, linting, type checks, and frontend tests.

        ### NATS

        ```bash
        task test:nats
        ```

        Validates command submission, worker consumption, and event emission.

        ### NATS Permissions

        ```bash
        task test:nats-permissions
        ```

        Validates subject permission assumptions for API, worker, and fleet agents.

        ### WebSockets

        ```bash
        task test:websockets
        ```

        Validates event stream behavior and fallback expectations.

        ### Network Contracts

        ```bash
        task test:network
        ```

        Validates typed non-legacy frontend write payloads.

        ### Redaction

        ```bash
        task test:redaction
        ```

        Ensures secrets are not leaked to logs, events, audit records, or UI-visible streams.

        ### Visual

        ```bash
        task test:visual
        ```

        Owns screenshot baselines and visual regression.

        ### Lighthouse

        ```bash
        task test:lighthouse
        ```

        Measures production PWA quality.

        ### Accessibility

        ```bash
        task test:a11y
        ```

        Validates critical accessibility issues are not introduced.

        ### Golden Path

        ```bash
        task test:golden
        ```

        Validates release-candidate operator workflow.

        ### Faults

        ```bash
        task test:faults
        ```

        Validates degraded-mode and fail-closed behavior.

        ### Flakes

        ```bash
        task test:flakes
        ```

        Validates no focused tests, no hidden skips/fixmes, no quarantine leaks, and repeated high-signal Playwright stability.

        ### E2E

        ```bash
        task test:e2e
        ```

        Validates broad non-visual UI workflows.

        ### Performance

        ```bash
        task test:performance
        ```

        Validates lightweight edge performance smoke budgets.

        ### Android Smoke

        ```bash
        task android:smoke
        ```

        Validates target Android/Termux runtime assumptions.

        ### Release Dry Run

        ```bash
        task release:dry-run
        ```

        Validates release artifact generation before publishing.

        ## Gate Ownership

        | Gate Type | Owner |
        |---|---|
        | API contracts | Backend + frontend |
        | NATS contracts | Runtime |
        | UI workflows | Frontend |
        | Fault behavior | Platform |
        | Security/redaction | Security |
        | Release dry-run | Release engineering |
        | Android smoke | Platform/edge |

        ## Maintenance Rule

        A code change that modifies a tab, API route, event subject, typed operation, runtime dependency, release stage, or security behavior must update tests and documentation.
        """,
    )

    write_doc(
        "performance/edge-performance-guide.md",
        r"""
        # Edge Performance Guide

        ## Purpose

        Pocket Lab is designed for edge environments. The goal is predictable responsiveness on constrained hardware, not massive centralized throughput.

        ## Performance Philosophy

        Pocket Lab should be:

        - Fast to start.
        - Lightweight in memory.
        - Responsive in the UI.
        - Resilient under degraded runtime conditions.
        - Safe on small ARM/Termux-style systems.

        ## Performance Smoke Gate

        ```bash
        task test:performance
        ```

        This gate validates lightweight performance assumptions such as FastAPI import/startup time, workflow journal rebuild time, state helper performance, and basic runtime sanity.

        It is not a heavy load test.

        ## Recommended Edge Budgets

        | Area | Suggested Budget |
        |---|---|
        | FastAPI import/startup smoke | Less than a few seconds. |
        | Workflow journal rebuild smoke | Sub-second for normal edge state. |
        | Typed operation accept | Fast local acknowledgement, typically under 500 ms. |
        | UI tab switch | Should feel immediate. |
        | Catalog render | Should handle 50–100 entries. |
        | Event replay | Should load recent events without UI freeze. |

        ## What Pocket Lab Does Not Need Yet

        Pocket Lab does not currently need 1000-user load testing, large-cluster throughput testing, high-volume NATS stress tests on every commit, or long soak tests on every push.

        ## Future Checks

        Recommended future checks:

        - App Catalog render with 100 entries.
        - Event panel render with 250 events.
        - Fleet view with 25–50 agents.
        - Release timeline render with many stages.
        - Worker command accept latency.
        - WebSocket fallback response time.
        - Memory sanity on Android/Termux.

        ## Troubleshooting

        | Symptom | Likely Cause |
        |---|---|
        | Slow startup | Heavy import or blocking initialization. |
        | Slow journal rebuild | Event log too large or inefficient replay. |
        | UI freeze | Large unvirtualized list or malformed payload. |
        | Slow operation accept | NATS, API, or worker readiness issue. |
        | Slow catalog | Large catalog or expensive normalization. |

        ## Maintenance Rule

        Keep performance checks fast enough for CI. Run deeper edge benchmarks before major releases or platform changes.
        """,
    )

    write_doc(
        "platform/android-termux-operations-guide.md",
        r"""
        # Android / Termux Operations Guide

        ## Purpose

        This guide explains Pocket Lab's target edge platform model for Android and Termux-style deployments.

        ## Platform Goals

        Pocket Lab should run on constrained edge devices with ARM-friendly runtime choices, minimal heavy dependencies, restartable processes, local-first behavior, optional mesh connectivity, and clear degraded-state messaging.

        ## Expected Runtime Shape

        ```mermaid
        flowchart TB
          Android[Android Device] --> Termux[Termux Environment]
          Termux --> FastAPI[FastAPI]
          Termux --> NATS[NATS / JetStream]
          Termux --> Worker[Worker]
          Termux --> PWA[PWA Static Assets]
          Termux --> State[State Directory]
          Worker --> Tools[Git / Ansible / ORAS / Vault / Policy Tools]
        ```

        ## Service Startup

        Recommended order:

        1. NATS / JetStream
        2. FastAPI
        3. Worker
        4. PWA/static frontend
        5. Optional fleet agent
        6. Optional observability components

        ## Operator Access

        | Component | Access |
        |---|---|
        | PWA | Browser URL |
        | FastAPI | Local API port |
        | NATS | Local service only |
        | Logs | Termux filesystem or process logs |
        | State | Pocket Lab state directory |

        ## Android Smoke Gate

        ```bash
        task android:smoke
        ```

        This should verify that required commands exist, runtime directories are writable, NATS can start, FastAPI can start, the worker can connect, API health works, PWA assets can be served, and storage/permissions are acceptable.

        ## Platform Constraints

        | Constraint | Guidance |
        |---|---|
        | Limited memory | Avoid heavy background services. |
        | Mobile storage | Monitor disk usage and backup growth. |
        | Process lifecycle | Use restartable process supervision. |
        | Network changes | Expect IP and connectivity changes. |
        | Battery limits | Avoid unnecessary polling. |
        | Native dependencies | Prefer ARM-friendly and pure-Python where possible. |

        ## Troubleshooting

        | Issue | Action |
        |---|---|
        | API not reachable | Check FastAPI process and port binding. |
        | NATS unavailable | Restart NATS and verify JetStream. |
        | Worker disconnected | Check NATS URL and worker logs. |
        | UI stale | Refresh PWA and check API status. |
        | Low disk | Clean logs/backups and verify state. |
        | Permission denied | Check Termux storage and executable permissions. |

        ## Safety

        Android/Termux deployments must preserve the same fail-closed model as Linux deployments. The worker must not be bypassed for local shell execution.
        """,
    )

    write_doc(
        "operations/backup-restore-disaster-recovery.md",
        r"""
        # Backup, Restore & Disaster Recovery Guide

        ## Purpose

        This guide explains how Pocket Lab protects runtime state and recovers from failures.

        ## Backup Principles

        Backups should be explicit, verifiable, restorable, redacted where required, taken before risky operations, and associated with release workflows.

        ## Backup Scope

        | Data | Include |
        |---|---|
        | State directory | Yes |
        | Event journal | Yes |
        | Operation records | Yes |
        | Catalog metadata | Yes |
        | Release metadata | Yes |
        | Fleet metadata | Yes |
        | Backup manifests | Yes |
        | Secrets | Only if encrypted and allowed |

        ## Do Not Back Up Unprotected

        - Plaintext tokens.
        - Vault root material.
        - Private keys.
        - Unredacted secret responses.
        - Temporary logs containing sensitive values.

        ## Operations

        | Operation | Purpose |
        |---|---|
        | `backup_now` | Create backup snapshot. |
        | `backup_verify` | Verify manifest/checksum integrity. |
        | `restore_backup` | Restore from selected backup. |

        ## Release Backup Flow

        ```mermaid
        flowchart LR
          Apply[Apply Release] --> Backup[backup_now]
          Backup --> Sync[release_sync]
          Sync --> Deploy[release_deploy]
          Deploy --> Verify[release_verify]
          Verify --> Done[Release Complete]
        ```

        If backup fails, release should not continue.

        ## Restore Flow

        ```mermaid
        flowchart LR
          Select[Select Backup] --> Preview[Restore Preview]
          Preview --> Confirm[Operator Confirm]
          Confirm --> Restore[restore_backup]
          Restore --> Verify[backup_verify / drift_scan]
          Verify --> Refresh[Refresh UI State]
        ```

        ## Restore Safety

        Restore workflows should show what will be restored, what will be overwritten, estimated size, backup timestamp/ref, manifest status, and destructive-change warnings.

        ## Disaster Scenarios

        | Scenario | Recovery |
        |---|---|
        | Failed release | Restore last pre-release backup. |
        | Corrupted state | Restore verified state snapshot. |
        | Lost catalog | Refresh catalog after restoring state. |
        | Worker failure | Restore worker then replay events. |
        | Fleet state loss | Restore fleet metadata and recheck agents. |
        | Drift after restore | Run drift scan and reconcile. |

        ## Verification

        After restore:

        ```bash
        task test:backend
        task check:api-contract
        task test:faults
        ```

        For release recovery:

        ```bash
        task release:dry-run
        ```

        ## Maintenance Rule

        Any change to backup format, manifest fields, restore behavior, or release backup behavior must update this guide.
        """,
    )

    write_doc(
        "blueprints/blueprint-authoring-guide.md",
        r"""
        # App Catalog / Blueprint Authoring Guide

        ## Purpose

        This guide explains how to create and maintain Pocket Lab blueprints for Apps & Services.

        ## Blueprint Concept

        A blueprint is a deployable workload definition. It may include metadata, source reference, Ansible playbook, configuration defaults, policy expectations, runtime requirements, and rollback guidance.

        ## Source Modes

        | Mode | Purpose |
        |---|---|
        | Repository | Git-backed blueprint source. |
        | OCI artifact | Blueprint packaged as OCI artifact. |
        | ZIP archive | Packaged archive source. |
        | HTTP/HTTPS | Remote source reference. |
        | Local path | Local development or imported blueprint. |

        ## Recommended Layout

        ```text
        blueprint-name/
          blueprint.yaml
          README.md
          playbooks/
            site.yml
          roles/
          files/
          templates/
          policies/
        ```

        ## Metadata Example

        ```yaml
        id: example-app
        name: Example App
        description: Example self-hosted workload
        version: 1.0.0
        category: observability
        entrypoint: playbooks/site.yml
        requires:
          - fastapi
          - nats
        operations:
          deploy: deploy_blueprint
          rollback: rollback_blueprint
        ```

        ## Deployment Operation Example

        ```json
        {
          "operation": "deploy_blueprint",
          "target": {
            "type": "repository",
            "ref": "example-app"
          },
          "params": {
            "name": "example-app",
            "playbook": "site.yml"
          }
        }
        ```

        ## Authoring Rules

        Blueprints should avoid hardcoded secrets, use Vault/secret references, provide idempotent playbooks, support repeated apply, emit useful operation logs, include rollback notes, declare dependencies, avoid unsupported shell assumptions, and remain ARM/edge friendly where possible.

        ## Policy Checks

        Policy checks should verify no plaintext secrets, no unjustified privileged tasks, no unsupported destructive commands, valid metadata, explicit source/version, and expected playbook presence.

        ## Catalog Refresh

        After adding or updating a blueprint:

        1. Commit blueprint changes.
        2. Run catalog refresh.
        3. Verify the App Catalog shows the blueprint.
        4. Run preview/deploy in a controlled environment.
        5. Check events for operation output.

        ## Testing

        ```bash
        task test:iac
        task test:e2e
        task test:faults
        task check:api-contract
        ```

        ## Maintenance Rule

        Any blueprint that changes deployment behavior must update its README, metadata, policy expectations, and rollback notes.
        """,
    )

    write_doc(
        "fleet/mesh-fleet-guide.md",
        r"""
        # Fleet Agent / Mesh Fleet Guide

        ## Purpose

        This guide explains how Pocket Lab manages edge devices through Mesh Fleet.

        ## Core Concepts

        | Concept | Meaning |
        |---|---|
        | Agent | Edge node reporting to Pocket Lab. |
        | Role | Device function such as compute, storage, observer, or controller. |
        | Heartbeat | Periodic agent status update. |
        | Last seen | Timestamp of last report. |
        | Stale | Agent has not reported recently. |
        | Offline | Agent unavailable. |
        | Join payload | Onboarding material for a new device. |

        ## Fleet Lifecycle

        ```mermaid
        flowchart LR
          Join[fleet_join] --> Register[Register Agent]
          Register --> Heartbeat[Heartbeat]
          Heartbeat --> Status[Online / Stale / Offline]
          Status --> Actions[Operator Actions]
        ```

        ## UI States

        | State | UI Behavior |
        |---|---|
        | Online | Agent healthy and recently seen. |
        | Stale | Agent has missed heartbeat threshold. |
        | Offline | Agent unavailable. |
        | Unknown | Agent has incomplete status. |

        ## Fleet Join Operation

        The `fleet_join` operation creates onboarding material for an edge node. It should generate join information, avoid exposing secrets unnecessarily, associate identity with a role, emit fleet events, and display status in Mesh Fleet.

        ## Fleet Events

        Representative event subjects:

        - `pocketlab.events.fleet.joined`
        - `pocketlab.events.fleet.heartbeat`
        - `pocketlab.events.fleet.stale`
        - `pocketlab.events.fleet.offline`

        ## Agent Data Example

        ```json
        {
          "agent_id": "edge-01",
          "name": "edge-01",
          "role": "compute",
          "status": "online",
          "last_seen": "2026-06-07T00:00:00Z",
          "telemetry": {
            "cpu_usage_percent": 22,
            "memory_usage_mb": 512,
            "free_space_mb": 4096
          }
        }
        ```

        ## Security

        Fleet onboarding must protect join secrets, agent identity, mesh tokens, role assignment, and agent command subjects.

        ## Troubleshooting

        | Problem | Action |
        |---|---|
        | Agent stale | Check network and heartbeat process. |
        | Agent offline | Restart agent and verify identity. |
        | Wrong role | Reissue join or update fleet metadata. |
        | No telemetry | Check agent telemetry collector. |
        | Join failure | Verify join payload and token validity. |

        ## Validation

        ```bash
        task test:e2e
        task test:faults
        task test:nats-permissions
        ```

        ## Maintenance Rule

        Any new fleet state, role, command subject, or event subject must update this guide and the NATS contract.
        """,
    )

    write_doc(
        "observability/observability-logging-guide.md",
        r"""
        # Observability & Logging Guide

        ## Purpose

        This guide explains Pocket Lab's observability model: event streams, audit records, logs, telemetry, and operator-facing diagnostics.

        ## Observability Layers

        ```mermaid
        flowchart TB
          UI[UI Event Panels] --> API[FastAPI Events API]
          API --> Journal[Event Journal]
          Worker --> Journal
          Worker --> WorkerLogs[Worker Logs]
          API --> APILogs[API Logs]
          NATS[NATS / JetStream] --> Streams[Command and Event Streams]
        ```

        ## Event Sources

        | Source | Purpose |
        |---|---|
        | FastAPI | Accepts operations and emits control-plane events. |
        | Worker | Emits operation progress and result events. |
        | Health engine | Emits service health events. |
        | Fleet agents | Emit heartbeat and telemetry events. |
        | Release workflow | Emits release stage events. |
        | Security/policy | Emits posture and guardrail events. |

        ## UI Event Controls

        | Control | Purpose |
        |---|---|
        | Replay recent | Loads recent event history. |
        | Clear | Clears current UI event list. |
        | Reconnecting badge | Indicates WebSocket reconnection. |
        | Event list | Shows recent operation, health, release, or fleet events. |

        ## Backend Event Interfaces

        | Endpoint | Purpose |
        |---|---|
        | `/api/events/recent` | Recent event replay. |
        | `/ws/events` | Live event stream. |
        | `/api/health-engine.json` | Health snapshot. |
        | `/api/nats/status` | NATS status. |
        | `/api/workers/status` | Worker status. |

        ## Event Envelope

        ```json
        {
          "event_id": "evt-123",
          "operation_id": "op-123",
          "correlation_id": "corr-123",
          "subject": "pocketlab.events.operation.succeeded",
          "status": "succeeded",
          "time": "2026-06-07T00:00:00Z",
          "message": "Operation completed",
          "payload": {}
        }
        ```

        ## Correlation

        Every write workflow should be traceable through API request, NATS command, worker logs, operation events, audit events, and UI event panels.

        ## Redaction

        Observability must never expose tokens, passwords, API keys, Vault material, private keys, or join secrets.

        Redaction applies to logs, events, audit records, DLQ messages, and UI event streams.

        ## Logging Guidance

        | Log Type | Contents |
        |---|---|
        | API log | Request, route, status, correlation ID. |
        | Worker log | Operation lifecycle, handler, result. |
        | Event log | Structured operation state. |
        | Audit log | Security-relevant actions. |
        | Error log | Failure reason without secrets. |

        ## Troubleshooting

        | Symptom | Check |
        |---|---|
        | Button clicked but no progress | `/api/events/recent`, NATS status, worker status. |
        | Operation accepted but not completed | Worker logs and DLQ. |
        | UI stream stale | WebSocket status and recent replay. |
        | Release stuck | Release timeline events. |
        | Fleet stale | Fleet heartbeat events. |

        ## Validation

        ```bash
        task test:websockets
        task test:faults
        task test:redaction
        task test:e2e
        ```

        ## Maintenance Rule

        Any new event subject, payload field, log field, or redaction rule must update this guide and the NATS / JetStream Event Contract.
        """,
    )

    patch_mkdocs_nav()
    fix_archived_readme_links()

    print("\n==> Done writing docs")
    print("Next run:")
    print("  mkdocs build --strict")


if __name__ == "__main__":
    main()
