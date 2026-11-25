# Pocket Lab Lite Native Control-Plane Retirement Ledger

Status: `VERIFIED` for the final Dev-PC source candidate; exact-head CI, disposable candidate runtime, bootstrap, and isolated backup/upgrade rehearsal are recorded below. Physical Android UI qualification remains separately labelled and deferred by scope.

## Scope and provenance

This ledger records the source-owned retirement of infrastructure that is not part of the current Lite-native execution path. It is intentionally separate from historical implementation reports. Historical records, migrations, audit evidence, backups, release identity, and qualification evidence remain preserved.

The reviewed starting point was local and remote `main` at `eb6d8421cb08d3037267ff9775fd86876cd7fa46`, tagged `lite-2026.11.25.2`. The candidate branch is `refactor/lite-native-control-plane-consolidation`. The final candidate and exact-head CI SHA are `ac6bcbc9eaed015fb84dd14b617047fad4f23bc8`.

## P0A authoritative dependency inventory

| ID | Component and source | Runtime/API reachability | Owner and persistence | Disposition | Regression evidence |
| --- | --- | --- | --- | --- | --- |
| P0A-01 | `runtime/api_fastapi/routers/health.py` health, readiness, and health-engine routes | Active public API | FastAPI reads prepared SQLite projections | ACTIVE / SHARED | Native health and readiness tests |
| P0A-02 | `runtime/api_fastapi/services/lite_phase3b_projections.py` | Active collector and prepared reads | Worker/sampler-owned projections in SQLite | ACTIVE / SHARED | Prepared projection and bounded-read tests |
| P0A-03 | `runtime/api_fastapi/services/lite_identity_auth.py` `identity_readiness` | Active Identity & Access dependency | Native identity state in SQLite | ACTIVE | Identity initialized/uninitialized tests |
| P0A-04 | `runtime/api_fastapi/services/live_status.py` | Background/explicit health sampling | Native sampler and event evidence | ACTIVE / SHARED | Process-local sampler regression |
| P0A-05 | `runtime/core/control_plane_core.py` legacy Gatus snapshot helpers | No supported Lite authority after this change | None; historical records retained | LEGACY HEALTH COUPLING — RETIRE | Source and health-path guards |
| P0A-06 | Vault rotate/dynamic-secret operation definitions and handlers | Previously executable through direct and generic operations | Operation/audit history in SQLite | LEGACY EXECUTABLE — RETIRE | Authenticated/unauthenticated negative tests |
| P0A-07 | GitOps, Gitea, and legacy pipeline API compatibility routes | Compatibility response only where retained | Historical operation evidence retained | COMPATIBILITY — DETERMINISTIC RETIRED RESPONSE | Route and dispatch-negative tests |
| P0A-08 | Prometheus, Grafana, Loki, Promtail, and Gatus bootstrap integrations | No current Lite bootstrap owner | Native diagnostics and evidence replace collection | LEGACY EXECUTABLE — RETIRE | Bootstrap/source and generated-doc checks |
| P0A-09 | `scripts/init-vault.sh`, `init-mariadb.sh`, `start-gitea.sh`, `seed-gitops-repo.sh` | Fresh Lite bootstrap only | None | DORMANT — REMOVE | Bootstrap stage and filesystem tests |
| P0A-10 | Old `src/tabs`, legacy health/telemetry hooks, and obsolete panels | Not reachable from `src/App.jsx` and the Lite screen registry | None | DORMANT — REMOVE | Active-entry reachability and build checks |
| P0A-11 | `runtime/supervisors/pocketlab_runtime_registry.py` legacy process names | Read-only historical/runtime absence detection | Supervisor evidence | SHARED — PRESERVE | Runtime guard tests |
| P0A-12 | Application-specific GitHub release, drift, backup, PhotoPrism, and database integrations | Active supported functionality | Existing release/application state | ACTIVE / COMPATIBILITY | Existing domain regression suites |
| P0A-13 | OPA active policy selection in `lite_policy_opa.py` | Active authorization lifecycle | `$POCKETLAB_STATE_DIR/opa/active`; bounded legacy read fallback | COMPATIBILITY — PRESERVE UNTIL MIGRATION PROOF | Policy lifecycle and fail-closed tests |

The inventory is dependency-based. Names in historical documentation, migration records, legitimate GitHub release support, and application-owned database integrations are not treated as proof of obsolete execution.

## P0B native health authority

The Lite health contract separates:

1. API liveness: the process can answer `/health` and `/healthz` without external fan-out.
2. Control-plane readiness: prepared native evidence is readable, SQLite is usable, native Identity & Access is initialized or explicitly not configured, NATS/JetStream and the required worker consumer are ready, and required storage is usable.
3. Core infrastructure health: native API, identity, NATS/JetStream, worker execution, runtime processes, policy/security, storage, and SQLite observations.
4. Workspace health: the aggregate of required core components, with maintenance and repair states preserved.
5. Optional capability readiness: remote access and secondary-device reachability are reported but do not make local operation unready.
6. Observation freshness and provenance: prepared observations retain status, freshness, source, and unknown/stale semantics.

The supported status vocabulary is `healthy`, `degraded`, `unhealthy`, `starting`, `repairing`, `unknown`, `stale`, `unsupported`, `not_configured`, `optional`, and `maintenance` where the underlying contract uses the corresponding state. Missing or stale evidence remains truthful; no legacy service is forced green.

The request path reads `system.health` with schema/migration side effects disabled. Collection remains owned by the existing sampler/projection infrastructure. `/api/health-engine.json` is a prepared read; explicit collection remains an authenticated write/command path. No request-time Gatus, Vault, PM2, scanner, migration, or socket probe is used.

## P1 public API and execution retirement

| Retired surface | Current behavior | Replacement or compatibility |
| --- | --- | --- |
| `rotate_secret`, `secret_read_dynamic` | Removed from active registry; deterministic retired rejection before task/run/publish | Native Identity & Access supported credential/passkey/recovery flows |
| `pocketlab.commands.vault.rotate`, `pocketlab.commands.vault.dynamic_secret` | No worker execution; historical queued records return a deterministic retired result and are not replayed | Native identity/provider contracts |
| `/api/pipeline_status.json`, `/api/gitops/health.json`, `/api/git_history.json` | Compatibility routes return HTTP 410 with `executed=false` | Native release/source metadata and Lite drift/System Health |
| `/api/observability/status` | HTTP 410 with `executed=false` | `/api/lite/system/health` and runtime diagnostics |
| Legacy health-engine snapshot helpers | Removed from active Lite collection | Prepared native `system.health` |

Shared operation admission, audit, approvals, policy authorization, event architecture, fleet/recovery/application lifecycle, release/source sync, and native identity operations remain in place. Retired historical records are readable where supported and are never silently rewritten or replayed.

The backup projection no longer advertises disabled MariaDB or Gitea infrastructure dump placeholders. The registered PhotoPrism SQLite metadata adapter and application-specific database fail-closed checks remain active; historical backup manifests and restore evidence remain readable.

## P2 legacy observability disposition

Prometheus, Grafana, Loki, Promtail, and Gatus package installation, PM2 ownership, Caddy routes, generated configuration, background probes, and active Lite documentation are retired. Native host telemetry, device heartbeats, runtime diagnostics, security evidence, sanitized log retention, incident history, event streams, and performance observations remain supported. No replacement heavyweight observability stack is introduced.

## P3 bootstrap and frontend

The supported bootstrap stage sequence is now: package installation, PRoot (optional), native binaries, Tailscale, PWA UI, dashboard/API/Caddy, fleet agent, smoke test, and Lite boot recovery. Fresh Lite bootstrap does not install, start, initialize, or configure the retired services. Git, curl, SQLite, Trivy, Lynis, OPA, NATS, Python, and optional PRoot remain available where their active owners require them.

The active frontend entry point is `src/App.jsx` → `src/lite/LiteApp.jsx` → `src/lite/liteScreenRegistry.js`. Reachable screens remain Home, Apps/Catalog, Devices, Safety/Security, Identity & Access, Rules, Recovery, and System Health. Unreachable legacy tabs, panels, hooks, and operation clients were removed. Azure Horizon components, semantic tokens, responsive geometry, accessibility, loading/error states, haptics, and Light/Dark behavior remain governed by the active Lite implementation.

## P4 compatibility and persistence

The authoritative OPA active policy directory is the configured `POCKETLAB_OPA_ACTIVE_POLICY_DIR`, otherwise `$POCKETLAB_STATE_DIR/opa/active`. When no state environment is supplied, `lite_policy_opa.py` retains a bounded read-compatible fallback to `~/.pocket_lab/state/opa/active` if the primary `~/.pocket_lab/opa/active` is absent. Startup remains fail-closed; a missing or invalid policy never becomes allow-all, and no active or known-good policy is silently overwritten. A future migration may retire the fallback only after installed-state evidence and rollback proof.

No applied SQLite migration is rewritten. Historical operation records, audit receipts, event payloads, backup manifests, release identity evidence, and qualification evidence remain retained. This retirement does not drop historical tables or delete legacy data.

## Before-and-after inventories

| Inventory | Before | After |
| --- | --- | --- |
| Mounted API routes | Legacy health/GitOps/observability compatibility and native Lite routes | Native routes plus explicit 410 compatibility responses where transition safety requires them |
| Operation registry | Active Vault secret operations mixed with shared registry | Active registry excludes retired operations; shared infrastructure preserved |
| Executable command subjects | Vault command subjects admitted to handlers/workers | Retired subjects rejected and acknowledged without execution |
| Caddy routes | Legacy Gitea/observability service routes alongside Lite | Same-origin PWA, FastAPI, native diagnostics, NATS-required backend topology |
| Bootstrap stages | Legacy service initialization and package coupling | Native Lite stages with optional PRoot and boot recovery |
| Runtime dependencies | External health/observability services used by Lite status | Prepared native projections, NATS/JetStream, workers, identity, OPA, SQLite, and native telemetry |
| Frontend routes/components | Historical infrastructure tabs and clients | Active Lite screen registry and native API clients |
| Background collectors | Gatus/legacy service probes mixed with native observations | Existing worker/sampler/projection ownership only |
| Generated references | Current-looking legacy observability pages | Generated retirement notices and native runtime/telemetry contracts |

## Security and attack-surface impact

The change removes secret-rotation and dynamic-secret execution admission, legacy service proxies, request-time external health fan-out, and obsolete bootstrap service ownership. OPA lifecycle, approvals, audit evidence, worker ownership, fail-closed policy activation, production-assisted/automatic recovery gates, and security assurance tooling remain unchanged. PR #658 production-assisted and production-automatic recovery activation remains disabled by default; the production qualification allowlists are not broadened.

## Validation ledger

| Evidence | State |
| --- | --- |
| Baseline local/remote `main` and release identity | VERIFIED before implementation |
| Focused native health, operation-retirement, workload-admission, identity, NATS, retired OpenAPI, and active AsyncAPI catalog tests | VERIFIED at the final Dev-PC source candidate; 15 focused tests passed |
| Runtime resilience and backend regression | VERIFIED by the protected gate; 134 resilience tests, 171 selected backend tests, and 416 Lite API/recovery/security tests passed |
| Python compilation and shell syntax | VERIFIED by the protected gate |
| Frontend build, unit, Storybook, mocked desktop/mobile, and accessibility qualification | VERIFIED by the protected gate; 638 unit tests, 656 stories/19 renders, 52 mocked tests passed with 10 repository-defined skips, 2 accessibility tests passed |
| Canonical docs generation/check, Codebase Map, architecture, SchemaSpy, Graphviz, and redaction | VERIFIED by the protected gate; 62 strict documentation tests, 1,546 knowledge entities/4,315 relations, Codebase Map with 5,582 tracked files/25,122 relationships, and the isolated redaction fence passed |
| Full `task lite:check` | VERIFIED at final Dev-PC candidate using the exact protected toolchain and `VALIDATION_DIR=.pocketlab-dev/validation/lite-check-final-3` |
| Exact-head GitHub CI | VERIFIED: [isolated-devpc-qualification](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45695542626/job/139491873513), [quick-and-docs](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45695542626/job/139491873514), and [ui-performance-qualification](https://github.com/dexter-lab-ctrl/pocket-lab-lite/actions/runs/45695542626/job/139491872947) all passed for `ac6bcbc9eaed015fb84dd14b617047fad4f23bc8` |
| Disposable exact-SHA candidate runtime | VERIFIED: run `c18f791368214ed18cce7a4d` passed the repository-owned DEV-PC lane at runtime source SHA `4c31ad6fcaf5930357b114b0e6eaa5614e79e912` with isolated FastAPI, worker, NATS/JetStream, OPA, node agent, supervisor, synthetic enrollment/authentication, crash recovery, reconnect, WebDAV transfer/retry, and cleanup; the final docs-only head is independently covered by the exact-head isolated-devpc CI job |
| Fresh Lite bootstrap contract | VERIFIED: `scripts/dev/check-lite-bootstrap.sh` passed syntax, Lite stage listing, legacy-stage absence, PRoot skip behavior, native boot-recovery inclusion, and Lite/full dry-run topology. This is a non-mutating bootstrap qualification, not a package install on the active phone |
| Disposable backup/upgrade/migration rehearsal | VERIFIED: exact-SHA backend artifact prepared and verified at runtime source SHA `4c31ad6fcaf5930357b114b0e6eaa5614e79e912` (`302` entries; artifact SHA `4b6e9284346a71b7e4a5f186b45457789a21ccc78804e3ced9697c922beb5dc8`); isolated promotion rehearsal passed consistent backup, restore, schema `42 → 54` migrations `43–54`, staged identity, committed lifecycle, and `production_touched=false` / `phone_checkout_touched=false`. The final docs-only head does not alter the runtime artifact payload. A physical Termux package-install and existing-installed-state upgrade were not run |
| Physical Android candidate qualification | DEFERRED / OPTIONAL by the targeted-closure scope: physical UI is reserved for targeted post-deployment smoke; no Server Phone mutation or physical PASS is claimed |
| Performance/resource measurements | VERIFIED for required automated thresholds; OPTIONAL comparative baseline not collected. Current PWA build measured `index` JS 847.95 kB / gzip 256.78 kB and CSS 804.08 kB / gzip 109.94 kB; before/after CPU, idle, memory, SQLite/WAL, collector, response-size, and bundle baselines were not run and no savings claim is made |

## Rollback and limitations

Rollback is a source rollback to the previous reviewed `main` SHA/release, followed by the repository-supported runtime reconciliation path. No destructive production database or device operation is part of this change. The primary remaining compatibility limitation is the bounded OPA legacy-path fallback, which is intentionally retained until safe migration evidence exists. The exact-head Dev-PC and isolated upgrade evidence is verified; physical Android UI smoke and a real package-install/installed-state upgrade remain separate evidence lanes and are not represented as completed here.

## Targeted-closure qualification scope

The closure scope keeps source, protected automated thresholds, exact-head CI, native health/retired-execution regressions, the repository-owned disposable candidate lane, and isolated backup/restore/migration evidence mandatory. Per the requested qualification adjustment, physical Android UI qualification is deferred to targeted post-deployment smoke and no active Server Phone mutation, production deployment, or physical PASS is claimed. Comparative historical CPU, memory, SQLite/WAL, collector-count, response-size, and bundle-size baselines are not required for this closure; the current build measurements remain recorded without a savings claim.
