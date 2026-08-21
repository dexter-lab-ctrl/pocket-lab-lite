---
title: "How Pocket Lab works"
description: "Scenario-oriented guide through real Pocket Lab Lite workflows."
generated: true
audience: development
confidence: source-derived
---

# How Pocket Lab works

Use scenarios when you want to understand **what happens**, **who owns execution**, and **where evidence returns**.

## Add Device

**Area:** devices · **Flow:** write/execution · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Identity, authentication, and invite guards</div><span aria-hidden="true">→</span><div>Invite and identity lifecycle</div><span aria-hidden="true">→</span><div>Enrollment and device lifecycle state</div><span aria-hidden="true">→</span><div>Lite node agent</div><span aria-hidden="true">→</span><div>Lite agent supervisor</div><span aria-hidden="true">→</span><div>Sanitized evidence/state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| POST /api/lite/fleet/add-device, GET /api/lite/fleet | src/lite/LiteDevices.jsx, pocket-lab-final-structure/runtime/api_fastapi/services/lite_invites.py |

</details>

## App installation

**Area:** apps · **Flow:** write/execution · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>NATS / JetStream + execution owner</div><span aria-hidden="true">→</span><div>App Catalog</div><span aria-hidden="true">→</span><div>App lifecycle worker</div><span aria-hidden="true">→</span><div>Workflow execution</div><span aria-hidden="true">→</span><div>PhotoPrism</div><span aria-hidden="true">→</span><div>Caddy same-origin proxy</div><span aria-hidden="true">→</span><div>Sanitized evidence/state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| POST /api/lite/catalog/install, GET /api/lite/catalog | src/lite/LiteCatalog.jsx |

</details>

## Backup creation and verification

**Area:** recovery · **Flow:** write/execution · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>NATS / JetStream + execution owner</div><span aria-hidden="true">→</span><div>Backup and verification engine</div><span aria-hidden="true">→</span><div>Backup, restore, and checkpoint state</div><span aria-hidden="true">→</span><div>Worker process</div><span aria-hidden="true">→</span><div>Sanitized evidence/state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| POST /api/lite/recovery/backup, GET /api/lite/recovery/summary | src/lite/LiteRecovery.jsx |

</details>

## Local owner, passkey, recovery, and session lifecycle

**Area:** identity · **Flow:** write/execution · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Identity, authentication, and invite guards</div><span aria-hidden="true">→</span><div>SQLite control-plane store</div><span aria-hidden="true">→</span><div>Sanitized evidence/state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| POST /api/lite/identity/setup, POST /api/lite/identity/login, POST /api/lite/identity/password, POST /api/lite/identity/logout, POST /api/lite/identity/recovery/regenerate, POST /api/lite/identity/recover | src/lite/LiteIdentity.jsx, pocket-lab-final-structure/runtime/api_fastapi/services/lite_identity_auth.py, pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py |

</details>

## Opt-in Enterprise membership and authoritative roles

**Area:** identity · **Flow:** write/execution · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Identity, authentication, and invite guards</div><span aria-hidden="true">→</span><div>SQLite control-plane store</div><span aria-hidden="true">→</span><div>OPA Safety Rules policy engine</div><span aria-hidden="true">→</span><div>Sanitized evidence/state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| GET /api/lite/enterprise/identity, PUT /api/lite/enterprise/identity/mode, GET /api/lite/enterprise/identity/members, PUT /api/lite/enterprise/identity/members/{human_id} | src/lite/LiteIdentity.jsx, pocket-lab-final-structure/runtime/api_fastapi/routers/lite_enterprise_identity.py, pocket-lab-final-structure/runtime/api_fastapi/services/lite_enterprise_identity.py |

</details>

## Device bootstrap and enrollment

**Area:** devices · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Identity, authentication, and invite guards</div><span aria-hidden="true">→</span><div>Invite and identity lifecycle</div><span aria-hidden="true">→</span><div>Enrollment and device lifecycle state</div><span aria-hidden="true">→</span><div>Lite node agent</div><span aria-hidden="true">→</span><div>Lite agent supervisor</div><span aria-hidden="true">→</span><div>Heartbeat, telemetry, and health publishers</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| GET /api/lite/fleet | pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py, pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py |

</details>

## Device offline and reconnect recovery

**Area:** devices · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Heartbeat, telemetry, and health publishers</div><span aria-hidden="true">→</span><div>Reconnect watchdog and supervisor recovery</div><span aria-hidden="true">→</span><div>Lite node agent</div><span aria-hidden="true">→</span><div>Lite agent supervisor</div><span aria-hidden="true">→</span><div>NATS / JetStream</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| GET /api/lite/fleet | architecture/metadata/pocket-lab-architecture.json |

</details>

## Documentation generation

**Area:** documentation · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| — | tasks/Taskfile.docs.yml, scripts/docs/lite/generate_docs.py, scripts/docs/lite/generate_platform_catalogs.py |

</details>

## Backend-to-Frontend parity capture and verification

**Area:** validation · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>React / Vite PWA</div><span aria-hidden="true">→</span><div>SQLite control-plane store</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| — | scripts/docs/parity/generate_parity.py, contracts/parity/parity-model.json |

</details>

## PhotoPrism operation

**Area:** apps · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>App Catalog</div><span aria-hidden="true">→</span><div>PhotoPrism</div><span aria-hidden="true">→</span><div>PROot Ubuntu application container</div><span aria-hidden="true">→</span><div>Media readiness and app health probes</div><span aria-hidden="true">→</span><div>Caddy same-origin proxy</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| GET /api/lite/catalog, GET /api/lite/apps/{app_id}/actions | src/lite/LiteCatalog.jsx |

</details>

## Recovery reconciliation

**Area:** recovery · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Audit index, projection refresh, prepared projections, and domain revisions</div><span aria-hidden="true">→</span><div>Backup, restore, and checkpoint state</div><span aria-hidden="true">→</span><div>SQLite control-plane store</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| GET /api/lite/recovery/summary | contracts/parity/parity-model.json |

</details>

## Release and update flow

**Area:** release · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Date-based Lite tag, dist.zip, checksums, and release manifest</div><span aria-hidden="true">→</span><div>Download staging and release verification</div><span aria-hidden="true">→</span><div>Release subprocess</div><span aria-hidden="true">→</span><div>Post-switch health validation</div><span aria-hidden="true">→</span><div>Installed release and runtime state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| GET /api/lite/release | docs/generated/production/release.md |

</details>

## Tailscale and remote access readiness

**Area:** devices · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Tailscale remote access</div><span aria-hidden="true">→</span><div>tailscaled daemon</div><span aria-hidden="true">→</span><div>Remote-access readiness checks</div><span aria-hidden="true">→</span><div>Primary and secondary NATS listeners</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| GET /api/lite/fleet | docs/generated/production/remote-access.md |

</details>

## Remove Old Device

**Area:** devices · **Flow:** write/execution · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Enrollment and device lifecycle state</div><span aria-hidden="true">→</span><div>Explicit retirement and database recovery</div><span aria-hidden="true">→</span><div>Sanitized evidence/state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| POST /api/lite/fleet/remove-device, GET /api/lite/fleet | src/lite/LiteDevices.jsx |

</details>

## Restart Agent

**Area:** devices · **Flow:** write/execution · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>NATS / JetStream + execution owner</div><span aria-hidden="true">→</span><div>Device command executor</div><span aria-hidden="true">→</span><div>Reconnect watchdog and supervisor recovery</div><span aria-hidden="true">→</span><div>Lite node agent</div><span aria-hidden="true">→</span><div>Lite agent supervisor</div><span aria-hidden="true">→</span><div>Sanitized evidence/state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| POST /api/lite/fleet/devices/{node_id}/restart-agent, GET /api/lite/fleet | src/lite/LiteDevices.jsx |

</details>

## Confirmed restore

**Area:** recovery · **Flow:** write/execution · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>NATS / JetStream + execution owner</div><span aria-hidden="true">→</span><div>Restore preview and confirmed restore</div><span aria-hidden="true">→</span><div>Backup and verification engine</div><span aria-hidden="true">→</span><div>Backup, restore, and checkpoint state</div><span aria-hidden="true">→</span><div>Workflow execution</div><span aria-hidden="true">→</span><div>Sanitized evidence/state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| POST /api/lite/recovery/restore, GET /api/lite/recovery/summary | src/lite/LiteRecovery.jsx, runbooks/backup_restore_verify.yaml |

</details>

## Restore preview

**Area:** recovery · **Flow:** write/execution · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Restore preview and confirmed restore</div><span aria-hidden="true">→</span><div>Backup, restore, and checkpoint state</div><span aria-hidden="true">→</span><div>Sanitized evidence/state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| POST /api/lite/recovery/restore/preview, GET /api/lite/recovery/summary | src/lite/LiteRecovery.jsx |

</details>

## Rollback

**Area:** release · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Last-known-good state and rollback</div><span aria-hidden="true">→</span><div>Installed release and runtime state</div><span aria-hidden="true">→</span><div>Post-switch health validation</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| GET /api/lite/release | runbooks/release_rollback.yaml |

</details>

## Typed Safety Rules authorization, lifecycle, simulation, and continuations

**Area:** rules · **Flow:** write/execution · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Identity, authentication, and invite guards</div><span aria-hidden="true">→</span><div>Fleet, Apps, Security, Recovery, and Release APIs</div><span aria-hidden="true">→</span><div>SQLite control-plane store</div><span aria-hidden="true">→</span><div>OPA Safety Rules policy engine</div><span aria-hidden="true">→</span><div>Sanitized evidence/state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| GET /api/lite/policy, POST /api/lite/catalog/install, POST /api/lite/fleet/remove-device, GET /api/lite/enterprise/rules/revisions, POST /api/lite/enterprise/rules/revisions, GET /api/lite/enterprise/rules/health, POST /api/lite/enterprise/rules/simulations, GET /api/lite/enterprise/rules/approvals, POST /api/lite/enterprise/rules/exceptions | src/lite/LiteRules.jsx, pocket-lab-final-structure/runtime/api_fastapi/services/lite_policy_opa.py, pocket-lab-final-structure/runtime/api_fastapi/services/lite_policy_lifecycle.py, pocket-lab-final-structure/runtime/api_fastapi/services/lite_policy_analysis.py, pocket-lab-final-structure/runtime/api_fastapi/services/lite_policy_approvals.py, security/policies/opa/pocketlab/pocketlab.rego |

</details>

## Sanitized Termux runtime capture

**Area:** validation · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>Lite node agent</div><span aria-hidden="true">→</span><div>Lite agent supervisor</div><span aria-hidden="true">→</span><div>NATS / JetStream</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| — | scripts/docs/runtime/capture_termux_runtime.sh, scripts/docs/runtime/promote_termux_runtime.py |

</details>

## Runtime evidence promotion

**Area:** validation · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>runtime-evidence</div><span aria-hidden="true">→</span><div>Installed release and runtime state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| — | scripts/test/parity/preflight_runtime_promotion.py, scripts/test/parity/promote_runtime_verification.py |

</details>

## Security finding review

**Area:** security · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>Security findings and run state</div><span aria-hidden="true">→</span><div>Security scan coordinator</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| GET /api/lite/security/summary, GET /api/lite/security/details/{run_id} | src/lite/LiteSecurity.jsx |

</details>

## Security scan

**Area:** security · **Flow:** write/execution · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>NATS / JetStream + execution owner</div><span aria-hidden="true">→</span><div>Quick, Full, and App safety checks</div><span aria-hidden="true">→</span><div>Security scan coordinator</div><span aria-hidden="true">→</span><div>Lynis and Trivy scanner adapters</div><span aria-hidden="true">→</span><div>Security findings and run state</div><span aria-hidden="true">→</span><div>Worker process</div><span aria-hidden="true">→</span><div>Sanitized evidence/state</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| POST /api/lite/security/check, GET /api/lite/security/summary, GET /api/lite/security/progress | src/lite/LiteSecurity.jsx, pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py |

</details>

## Pocket Lab Lite startup

**Area:** platform · **Flow:** read/projection · **Confidence:** source-derived

<div class="pl-flow"><div>User intent</div><span aria-hidden="true">→</span><div>Pocket Lab Lite UI</div><span aria-hidden="true">→</span><div>PM2 process manager</div><span aria-hidden="true">→</span><div>Caddy same-origin proxy</div><span aria-hidden="true">→</span><div>FastAPI /api/lite/*</div><span aria-hidden="true">→</span><div>NATS / JetStream</div><span aria-hidden="true">→</span><div>Worker process</div><span aria-hidden="true">→</span><div>Lite node agent</div><span aria-hidden="true">→</span><div>Lite agent supervisor</div><span aria-hidden="true">→</span><div>FastAPI projection</div><span aria-hidden="true">→</span><div>UI result</div></div>

!!! info "Boundary"
    This scenario is read-oriented and does not authorize browser-side execution.

<details class="pl-disclosure"><summary>Routes and source evidence</summary>

| Routes | Source refs |
| --- | --- |
| — | pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh, architecture/metadata/pocket-lab-architecture.json |

</details>
