# Universal App Platform

## Status

The Universal App Platform foundation lives on `feat/universal-app-platform`. The stacked governance integration on `feat/universal-app-platform-governance-integration` extends that foundation so every registered app can participate in the existing Identity, Rules/OPA, approvals, device-capability, Recovery, Security-evidence, credential-metadata, and audit architecture. Qualification remains separate and is not implied by source-complete status.

The platform uses a repository-owned, fail-closed application registry and backend adapter boundary. PhotoPrism remains the first production application migrated to the platform. Existing PhotoPrism installer, media, backup, recovery, and scanner implementations remain app-specific behind that boundary; cross-feature governance is generic and registry-derived.

## Control flow

```text
Apps UI
  -> FastAPI /api/lite/*
  -> validated app registry
  -> app capability / adapter binding
  -> existing governed operation path
  -> NATS / JetStream where mutation is required
  -> worker / agent / supervisor
  -> app-specific runtime
  -> sanitized evidence / prepared projections
  -> FastAPI
  -> Apps UI
```

The frontend never talks to NATS, executes shell commands, writes Caddy configuration, or receives backend secrets.

## Registry contract

`lite_app_registry.py` owns canonical application identity, route ownership, supported platforms, capabilities, safe action presentation metadata, and backend adapter bindings.

Production app IDs must be lowercase slugs and own exactly:

```text
/apps/<app-id>/
```

Duplicate IDs and duplicate routes fail closed. Unknown or malformed app IDs are rejected.

The public registry projection deliberately excludes backend-only bindings such as upstream addresses, process names, and adapter identifiers.

## Adapter boundary

`lite_app_adapters.py` binds a registered app to backend-owned implementation logic.

Adapters own bounded app-specific catalog projection, lifecycle projection, safety/backup profiles, readiness/live-state hydration, media specialization where applicable, and specialized action preparation. Generic services dispatch through the selected app adapter instead of calling PhotoPrism directly.

Adapters do not accept arbitrary commands from manifests and do not turn registry data into executable shell. Executable behavior remains a static backend implementation owned by the repository.

PhotoPrism readiness remains limited to loopback Pocket Lab routes with short timeouts. Same-origin/Tailscale embed policy remains derived from the server-owned Caddy configuration.

## Capability model

Capabilities declare which governed operations an application supports. A capability does not itself execute anything.

PhotoPrism currently declares:

- install
- open
- repair
- security check
- backup
- backup to storage
- restore preview
- update readiness
- remove
- media sources
- media import

Action definitions are registry-owned presentation metadata. Execution remains bound to existing backend services and operation handlers.

## PhotoPrism migration

The platform now sources PhotoPrism canonical identity, route, upstream, process name, capability set, and supported action definitions from the registry.

Catalog enumeration now walks registered adapter-backed apps. Lifecycle, safety/backup profile reads, live catalog hydration, and specialized install/remove/media action preparation all dispatch through the selected adapter.

PhotoPrism remains the first production adapter and reuses the mature installer, lifecycle, media, backup, recovery, and scanner implementations behind that boundary. Specialized PhotoPrism media workflows intentionally remain PhotoPrism-specific.

## Security invariants

The registry must never become an arbitrary plugin execution format.

Forbidden patterns include:

- shell commands in app definitions
- browser-provided executable handlers
- arbitrary subprocess selection
- arbitrary remote health URLs
- arbitrary filesystem scan targets
- secrets or credentials in public app metadata
- frontend NATS access
- frontend PM2 or Caddy mutation

Security App Check and backup implementations continue to define their own safe target scope. App Check resolves the selected app through its adapter-owned scan contract; route health, app/binary/config targets, backup metadata, action-state evidence, target IDs, and evidence names are derived from that validated contract rather than hardcoded PhotoPrism worker targets. Health probing remains loopback-only and under the app's owned same-origin route. PhotoPrism user media remains excluded from automatic application scanning and default application backup.

## Adding a future application

A future production app should require:

1. a validated registry definition;
2. a backend adapter binding;
3. explicit capabilities;
4. governed operation handlers for every executable capability;
5. same-origin route ownership;
6. safe health/readiness implementation;
7. backup/security scope definitions where supported;
8. backend, frontend, Storybook, and Playwright coverage.

A new app must not be enabled merely by adding display metadata. The registry entry, adapter service declarations, required adapter projection hooks, governed handlers, route/readiness implementation, and declared capabilities must agree or the platform fails closed.

## Validation

The branch defines repository-owned source coverage for:

- registry schema/version, unsafe IDs, duplicate IDs/routes, secret/shell absence, adapter binding and unknown-app fail-closed behavior;
- canonical semantic-action compatibility and app-resource contract derivation;
- Personal Owner and Enterprise Owner/Admin/Operator/Auditor/Viewer authority;
- verified placement and capability mismatch handling;
- exact app approval and temporary-access binding, expiry, stale policy/contract revision and replay rejection;
- credential metadata redaction and identifier validation;
- OPA role, approval, temporary-access, resource-mismatch and placement semantics;
- frontend capability/access/recovery projection and focused invalidation;
- Storybook governance states and mocked Playwright cross-tab/multi-app isolation already owned by the Universal App Platform test surface;
- source guards for frontend execution boundaries, secret projection, executable manifest fields and generic-service app hardcoding.

Implementation completeness is distinct from qualification. These checks are **defined but not run in this implementation session**. Repository validation and runtime qualification remain required before merge and are intentionally not claimed by this document.


## Governed app resource model

Every registered app is treated as one canonical Pocket Lab resource. The backend derives the resource envelope from the App Registry; the browser never supplies adapter identity or declared capability truth.

The safe authorization envelope includes:

- `resource_type = app`;
- canonical registry `app_id` and label;
- canonical semantic action such as `app.install` or `app.backup.create`;
- the required declared capability;
- target device when the action actually executes against a device;
- registry schema identity and deterministic contract revision;
- operation/correlation identity;
- server-derived actor authority;
- safe consequence/risk metadata.

Unknown apps, malformed IDs, missing capabilities, unsupported platforms, stale target revisions, and required-but-unverified placements fail closed.

Semantic actions preserve compatibility rather than forcing a flag-day rewrite. Existing identifiers such as `catalog.install`, `backup.create`, and `restore.preview` map to canonical app actions before authorization. Legacy routes therefore cannot bypass the app-resource policy boundary.

## Identity & Access

The existing workspace roles remain authoritative:

- Owner;
- Admin;
- Operator;
- Auditor;
- Viewer.

No second RBAC model is introduced.

In Personal Mode the local Owner keeps direct authority for supported app operations, subject to hard safety guards and any required passkey step-up. No enterprise permissions matrix is added to the default Apps experience.

In Enterprise Mode app-resource authority is projected from the same server-owned role and membership truth used by Identity & Access and Rules. App access is capability-aware and can distinguish direct authority, independent approval, temporary access, or denial.

Owner remains root-equivalent for supported Pocket Lab operations and is never placed into a peer-approval deadlock. Passkey step-up remains separate from independent approval.

## Rules / OPA integration

Protected app mutations use the existing OPA decision path.

OPA input receives only server-derived app facts:

- canonical app ID;
- semantic action;
- required capability;
- platform support;
- whether placement is required;
- verified placement state when required;
- target device identity;
- deterministic app contract revision;
- actor role and Enterprise/Personal mode;
- current operation context and safe consequence metadata.

Rules simulations reuse the same contract builder but do not dispatch adapters, scanner work, NATS commands, PM2 operations, shell commands, or restore application.

The typed policy/template system remains authoritative. The browser does not provide free-form Rego.

## Approvals and temporary access

Independent approvals and temporary access continue to use the existing durable continuation architecture.

App removal approvals bind to:

- initiating actor;
- semantic action;
- `resource_type = app`;
- canonical app ID;
- deterministic target/contract revision;
- requester authorization version;
- policy revision;
- one-time request fingerprint;
- expiration.

Temporary app-install access binds to:

- human identity;
- canonical app ID;
- exact semantic action;
- exact device;
- required capability;
- app contract revision;
- policy revision;
- expiration.

Cross-app, cross-device, stale-policy, stale-contract, expired, and already-consumed continuations do not match.

## Device placement

The registry declares placement requirements; it does not schedule arbitrary workloads.

Supported metadata is bounded to safe concepts such as:

- Server Host only;
- required verified device capabilities;
- backup/restore target capabilities.

For runtime-facing app operations, the backend requires authorized **and observed/verified** effective device capabilities. Advertised capabilities alone are not sufficient. Stale role/capability truth remains fail closed.

PhotoPrism remains Server Host only. The integration does not create a Kubernetes-style scheduler and does not permit manifests to carry executable paths, PM2 commands, shell commands, or remote hosts.

Credential metadata management is intentionally not coupled to runtime placement because it does not execute against the app process.

## Backup & Recovery

The generic app recovery contract can project:

- backup support;
- latest backup;
- latest verified backup;
- backup-target readiness;
- restore-preview support;
- restore-apply support;
- protected-user-data exclusions;
- credential-rebinding expectation;
- recovery readiness and blockers;
- sanitized evidence references.

Restore application remains disabled wherever the adapter currently disables it. The governance integration does not activate destructive restore behavior.

Recovery UI consumes summaries and references, not raw backup payloads.

## App credential lifecycle

App credential handling is a backend-owned metadata contract, not a browser secret manager.

The registry can declare bounded credential purposes. SQLite stores only safe metadata such as:

- credential ID/purpose;
- configured/missing/invalid/needs-rotation state;
- management mode;
- last verified time.

The current integration intentionally does **not** store credential values. No password, API key, private key, database URL, OAuth token, restic secret, NATS credential, or equivalent secret is accepted by the credential metadata API or projected to the browser.

Secret-value storage remains deferred until an approved backend secret primitive is integrated. Recovery may indicate that credential rebinding is required, but restore never exposes secret material.

## Security evidence relationship

Security App Check remains adapter-driven. Governance adds relationship metadata rather than scanner duplication.

Where a governed App Check is started, the command/evidence path may carry only sanitized references:

- app ID;
- semantic action;
- operation/run ID;
- authorization decision ID;
- policy revision;
- app contract revision;
- target device ID where applicable.

Scanner target scope remains adapter-owned. Governance never broadens PhotoPrism media/user-data scan scope.

## Audit and evidence chain

The existing durable IDs and SQLite evidence provide the relationship chain:

```text
human actor
  -> Rules authorization decision
  -> approval / temporary access / step-up when applicable
  -> semantic app action
  -> operation or command ID
  -> worker / adapter result
  -> Security / backup / Recovery evidence
  -> final app lifecycle projection
```

No graph database is introduced. UI/API projections expose only sanitized IDs and summaries.

## Frontend projection and state ownership

The browser continues to use:

- TanStack Query for server state;
- Dexie only for safe read snapshots;
- Zustand for UI state;
- XState for established workflows;
- no offline mutation queue.

Apps stays simple in Personal Mode. Enterprise Mode adds concise Access & Safety summaries under Manage rather than an enterprise matrix on every card.

Identity & Access can show registered app-resource authority using the existing roles surface. Rules lists canonical app actions alongside existing protected actions. Recovery shows per-app recoverability and blockers using existing Recovery patterns.

Mutation invalidation is scoped to the affected app and the cross-feature projections that actually changed. The integration does not add an ad-hoc browser event bus.

## Future app onboarding

A future app integrates with Pocket Lab by adding bounded declarative capabilities and explicit backend adapters. It must not create its own authorization, device-placement, recovery, credential, or policy engine.

Capability absence is a first-class state. A future adapter is not assumed to support media, PROot, credentials, backup, restore preview, Security App Check, update readiness, Server Host placement, or web health semantics.

## Compatibility map

| Existing contract | Canonical governed meaning | Compatibility rule |
| --- | --- | --- |
| `catalog.install` | `app.install` | Legacy identifier remains registered but uses the same role/exception boundary |
| `backup.create` | `app.backup.create` | Existing generic Recovery action remains; app-specific routes use the app semantic action |
| `restore.preview` | `app.restore.preview` | Existing generic Recovery action remains; app-specific preview is app-scoped |
| PhotoPrism media/storage routes | adapter specialization | Retained behind explicit PhotoPrism checks |
| PhotoPrism Server Host placement | app placement declaration | Preserved; no new placement is implied |

## Qualification boundary

Source implementation completeness and executable qualification are intentionally separate.

This branch defines backend, OPA, frontend, Storybook, Playwright, and focused Taskfile coverage for the governed app-resource model. Those checks are **not** evidence of PASS until they are executed in a later qualification session. Server Phone runtime behavior, CI status, performance, accessibility, and release readiness must likewise be qualified separately.


## Source coupling classification

The source-only adversarial review classifies the remaining app couplings as follows:

| Coupling | Classification | Rationale |
| --- | --- | --- |
| `lite_app_governance.py`, registry-derived policy targets, Identity/Rules projections | generic platform integration | App identity/capability/authority comes from the registry and existing governance stack. |
| PhotoPrism media import, storage preview, scanner exclusions, installer/runtime health probes | legitimate app-adapter specialization | These behaviors are specific to PhotoPrism and stay behind the adapter/service boundary. |
| `lite_app_operations.py` PhotoPrism repair internals and legacy catalog runtime state | compatibility seam | Mature pre-platform implementation remains adapter-owned; generic governance does not pretend these are portable implementations. |
| `catalog.install`, `backup.create`, `restore.preview` | compatibility seam | Existing identifiers remain supported but canonicalize to semantic app actions before governed execution where app-scoped. |
| app approvals, temporary access, placement, credential metadata, Recovery and Security evidence links | governance integration | Reuses existing Identity/OPA/continuation/device/evidence systems rather than creating parallel frameworks. |
| synthetic `example-app`, governed MSW scenarios, Storybook and Playwright fixtures | test/docs fixture | Proves capability isolation and generic presentation without becoming a production app. |
| raw secret-value storage | intentionally deferred | No approved app secret-value store is introduced; metadata only is stored. |
| restore apply where an adapter currently disables it | intentionally deferred | Metadata cannot activate destructive restore behavior. |
| missing cross-feature integration found by final source review | none known | Source review closed the identified legacy install, Recovery app-write, Security App Check, continuation, placement, invalidation, and durable evidence seams. Executable qualification is still required. |

### Credential backup policy

The credential contract is deliberately explicit:

- app-specific backup: **neither credential values nor credential metadata**;
- Pocket Lab workspace/database backup: **credential metadata only** where that database is included;
- secret material: **not stored by this feature**;
- restore: may report that manual credential rebinding is required, but never projects secret material.

### Evidence persistence

Existing operation records retain only a whitelisted governance relationship: app ID, semantic action, operation ID, authorization decision ID, policy revision, app contract revision, target device where applicable, and a bounded initiating-actor reference. Install, repair, update-readiness, app backup/restore-preview, and Security App Check reuse their existing durable state/evidence stores. No graph database or duplicate audit engine is added.
