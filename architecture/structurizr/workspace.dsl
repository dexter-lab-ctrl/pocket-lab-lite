workspace "Pocket Lab" "Edge-first self-hosted control plane for apps, fleet, GitOps, drift, releases, security, telemetry, and disaster recovery." {

    model {
        user = person "Operator / Home Lab Admin" "Uses Pocket Lab to install apps, manage devices, monitor health, run GitOps, rotate secrets, and apply releases."

        github = softwareSystem "GitHub Repository" "Source repository for Pocket Lab code, docs, releases, and GitOps state." "External"
        tailscale = softwareSystem "Tailscale / Mesh Network" "Private mesh connectivity for fleet nodes and remote access." "External"
        vaultExternal = softwareSystem "Vault / OpenBao Runtime" "Secrets, leases, and secret rotation backend." "External"
        opaExternal = softwareSystem "OPA Runtime" "Policy decision point for guardrails and security checks." "External"
        gatusExternal = softwareSystem "Gatus Health Engine" "Health probing and status aggregation." "External"
        backupStore = softwareSystem "Backup Storage" "Local or remote backup destination for manifests, state snapshots, and restore material." "External"

        pocketlab = softwareSystem "Pocket Lab" "FastAPI + NATS/JetStream + Worker + React PWA control plane." {
            pwa = container "React / Vite PWA" "Operator UI with Professional and Simple Experience modes." "React, Vite, Playwright-tested PWA"
            api = container "FastAPI Control API" "HTTP API, WebSocket event stream, OpenAPI contract, typed operation submission, release endpoints, health endpoints." "Python, FastAPI"
            nats = container "NATS / JetStream" "Durable command, event, audit, telemetry, and DLQ streams." "NATS, JetStream"
            worker = container "Pocket Lab Worker" "Consumes typed commands, executes domain handlers, emits lifecycle events, writes audit records." "Python worker"
            eventStore = container "Event Journal / Workflow Store" "Stores operation lifecycle, recovery state, workflow snapshots, and event-sourced workflow history." "SQLite / JSON journal"
            auditTrail = container "Audit Trail / Evidence Store" "Stores auditable security, release, vault, policy, and DLQ evidence for review and recovery." "Append-only JSON / SQLite evidence"
            dlqSubjects = container "DLQ / Retry Subjects" "Represents JetStream retry exhaustion and dead-letter subjects for failed commands and events." "NATS JetStream DLQ subjects"
            operationRegistry = container "Typed Operations Catalog" "Backstage-style operation metadata source and generated typed operation catalog." "operations/*.yaml, JSON contract"
            docsPortal = container "MkDocs Documentation Portal" "Generated documentation for OpenAPI, AsyncAPI, Typed Operations, Structurizr, runbooks, architecture, and readiness." "MkDocs Material"
            gitops = container "GitOps / Source Adapter" "Pulls and validates desired state using typed operations and Git abstraction." "Dulwich / Git abstraction"
            blueprint = container "Blueprint / App Catalog Engine" "App catalog refresh, blueprint deploy, package metadata, app source modes." "Catalog metadata, ORAS/go-getter concepts"
            drift = container "Drift Engine" "Scans desired vs actual state and manages preview, approve, apply, ignore workflows." "Python domain service"
            fleet = container "Fleet Agent Control" "Fleet join, node health, telemetry, heartbeat, and mesh onboarding workflows." "NATS-backed fleet workflow"
            vault = container "Identity Vault Adapter" "Secret rotation and dynamic secret lease workflows." "Vault/OpenBao client"
            security = container "Security / Policy Guardrails" "Security scans, OPA configuration, policy checks, secret redaction validation." "OPA / policy integration"
            telemetry = container "NOC Telemetry Adapter" "CPU, memory, disk, health, worker, NATS, and live status telemetry." "Python telemetry service"
            release = container "Release Workflow Orchestrator" "Self-update check/apply workflow with backup, sync, deploy, verify, and catalog refresh stages." "Python release orchestrator"
            backup = container "Backup / Disaster Recovery Engine" "Backup, verify, restore preview, restore execution, manifest validation." "Python DR service"
        }

        user -> pwa "Uses"
        pwa -> api "Calls REST API and WebSocket event stream" "HTTP/WebSocket"
        api -> pwa "Streams operation events and live status updates" "WebSocket / HTTP"
        api -> nats "Publishes typed commands and events" "NATS"
        worker -> nats "Consumes commands and publishes events/audit/DLQ" "NATS"
        nats -> worker "Delivers durable commands to the worker" "NATS / JetStream"
        worker -> eventStore "Records operation lifecycle and workflow state"
        worker -> auditTrail "Writes auditable operation, policy, vault, release, and recovery evidence"
        nats -> dlqSubjects "Routes retry-exhausted messages to dead-letter subjects" "JetStream DLQ"
        dlqSubjects -> auditTrail "Preserves failed command/event evidence for audit and recovery"
        api -> eventStore "Reads operation status, events, and workflow state"
        api -> auditTrail "Reads audit evidence for reviews and operator status"
        pwa -> docsPortal "Reads generated documentation"
        docsPortal -> operationRegistry "Documents typed operations"
        docsPortal -> api "Documents OpenAPI contract"
        docsPortal -> nats "Documents AsyncAPI event contract"

        api -> operationRegistry "Validates typed operation metadata"
        api -> release "Starts release check/apply"
        api -> drift "Starts drift workflows"
        api -> fleet "Starts fleet onboarding"
        api -> vault "Starts secret operations"
        api -> security "Starts security operations"
        api -> telemetry "Reads telemetry and live status"
        api -> blueprint "Refreshes catalog and starts deploy workflows"
        api -> backup "Starts backup/verify/restore workflows"

        worker -> release "Executes release workflow stages"
        worker -> drift "Executes drift domain commands"
        worker -> fleet "Executes fleet domain commands"
        worker -> vault "Executes secret rotation/dynamic lease commands"
        worker -> security "Executes security scans and OPA configuration"
        worker -> dlqSubjects "Publishes failure outcomes when commands cannot be recovered" "NATS / JetStream"
        worker -> blueprint "Executes catalog refresh and blueprint deployment"
        worker -> backup "Executes backup and restore workflows"
        worker -> telemetry "Publishes health and telemetry events"

        gitops -> github "Reads desired state and release source"
        release -> github "Checks and applies releases"
        fleet -> tailscale "Uses mesh connectivity and join material"
        vault -> vaultExternal "Rotates and reads dynamic secrets"
        security -> opaExternal "Evaluates and updates policy guardrails"
        api -> opaExternal "Requests policy decisions before sensitive control-plane actions" "OPA query"
        api -> vaultExternal "Coordinates secret operations through the vault adapter" "Vault/OpenBao API"
        worker -> vaultExternal "Uses secret leases during execution when required" "Vault/OpenBao API"
        telemetry -> gatusExternal "Reads health status"
        backup -> backupStore "Writes and restores backups"

        deploymentEnvironment "Android / Termux Edge Device" {
            deploymentNode "Termux / proot Linux environment" "Android ARM64 local runtime" {
                containerInstance pwa
                containerInstance api
                containerInstance nats
                containerInstance worker
                containerInstance eventStore
                containerInstance auditTrail
                containerInstance dlqSubjects
                containerInstance docsPortal
            }
        }

        deploymentEnvironment "Developer Workstation" {
            deploymentNode "Ubuntu Dev Environment" "Local deterministic stack" {
                containerInstance pwa
                containerInstance api
                containerInstance nats
                containerInstance worker
                containerInstance eventStore
                containerInstance auditTrail
                containerInstance dlqSubjects
                containerInstance docsPortal
            }
        }
    }

    views {
        systemContext pocketlab "system-context" {
            include *
            autolayout lr
            title "Pocket Lab - System Context"
            description "Pocket Lab as an edge-first self-hosted control plane interacting with GitHub, mesh networking, Vault/OpenBao, OPA, Gatus, and backup storage."
        }

        container pocketlab "container-view" {
            include *
            autolayout lr
            title "Pocket Lab - Container View"
            description "Major Pocket Lab runtime containers and their responsibilities."
        }

        container pocketlab "event-driven-runtime" {
            include user pwa api nats worker eventStore operationRegistry docsPortal
            autolayout lr
            title "Pocket Lab - Event Driven Runtime"
            description "Typed operation submission through FastAPI, NATS/JetStream, worker execution, event journal, and UI updates."
        }

        container pocketlab "domain-services" {
            include api nats worker blueprint gitops drift fleet vault security telemetry release backup eventStore auditTrail dlqSubjects
            autolayout tb
            title "Pocket Lab - Domain Services"
            description "Domain services behind App Catalog, GitOps, Drift, Fleet, Vault, Security, Telemetry, Release, and Disaster Recovery."
        }

        container pocketlab "security-review" {
            include user pwa api worker vault security vaultExternal opaExternal operationRegistry auditTrail eventStore
            autolayout lr
            title "Pocket Lab - Security / Policy / Vault / OPA Relationships"
            description "Security review view showing policy checks, vault operations, typed operation validation, audit evidence, and UI/API boundaries."
        }

        container pocketlab "nats-command-event-boundaries" {
            include pwa api nats worker operationRegistry eventStore auditTrail dlqSubjects telemetry
            autolayout lr
            title "Pocket Lab - NATS Command and Event Boundaries"
            description "Event-driven boundary view showing frontend-to-API control, API-to-NATS command publishing, worker command consumption, event emission, and status reconstruction."
        }

        container pocketlab "audit-and-dlq-paths" {
            include api nats worker eventStore auditTrail dlqSubjects release security vault backup
            autolayout lr
            title "Pocket Lab - Audit and DLQ Paths"
            description "Operational resilience view showing audit evidence, retry exhaustion, dead-letter routing, and recovery state."
        }

        deployment pocketlab "Android / Termux Edge Device" "android-termux-deployment" {
            include *
            autolayout tb
            title "Pocket Lab - Android / Termux Deployment"
            description "Primary edge deployment topology for Android/Termux ARM64."
        }

        deployment pocketlab "Developer Workstation" "developer-workstation-deployment" {
            include *
            autolayout tb
            title "Pocket Lab - Developer Workstation Deployment"
            description "Local deterministic dev stack for testing and release validation."
        }

        dynamic pocketlab "typed-operation-flow" {
            user -> pwa "Clicks Install / Update / Rotate Secret / Run Scan"
            pwa -> api "POST typed operation"
            api -> operationRegistry "Validate operation metadata"
            api -> nats "Publish command"
            nats -> worker "Deliver command"
            worker -> eventStore "Record operation.created / worker_claimed"
            worker -> nats "Emit operation logs/events"
            api -> pwa "Stream events via API/WebSocket"
            worker -> eventStore "Record succeeded/failed/DLQ state"
            autolayout lr
            title "Pocket Lab - Typed Operation Flow"
            description "End-to-end runtime flow for typed operations."
        }

        styles {
            element "Person" {
                shape person
                background #08427b
                color #ffffff
            }

            element "Software System" {
                background #1168bd
                color #ffffff
            }

            element "Container" {
                background #438dd5
                color #ffffff
            }

            element "External" {
                background #999999
                color #ffffff
            }

            element "Database" {
                shape cylinder
            }

            relationship "Relationship" {
                color #707070
            }
        }

    }

    !docs docs
}
