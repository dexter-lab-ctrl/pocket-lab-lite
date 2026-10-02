# Universal App Platform

## Status

Source implementation in progress on `feat/universal-app-platform`.

The Universal App Platform introduces a repository-owned, fail-closed application registry and backend adapter boundary. PhotoPrism is the first production application migrated to the platform. Existing PhotoPrism installer, media, backup, recovery, and scanner implementations remain app-specific behind that boundary.

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

Adapters may provide bounded app-specific readiness and live-state hydration. They do not accept arbitrary commands from manifests and do not turn registry data into executable shell.

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

Live catalog hydration delegates to the PhotoPrism adapter rather than embedding PhotoPrism-specific readiness logic in the generic catalog hydrator.

Specialized PhotoPrism media workflows intentionally remain PhotoPrism-specific.

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

Security App Check and backup implementations continue to define their own safe target scope. PhotoPrism user media remains excluded from automatic application scanning and default application backup.

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

A new app must not be enabled merely by adding display metadata.

## Validation

The branch includes targeted registry tests for:

- schema/version projection;
- unsafe IDs;
- duplicate IDs;
- duplicate/invalid routes;
- secret/shell absence from public metadata;
- explicit PhotoPrism adapter binding;
- registry-owned action contracts;
- unknown-app fail-closed behavior.

Full repository validation and runtime qualification remain required before merge.
