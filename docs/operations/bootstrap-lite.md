# Bootstrap Lite

## Current implementation status

Pocket Lab Lite supports a dedicated bootstrap profile:

```bash
bash scripts/bootstrap.sh --profile lite
```

or:

```bash
bash scripts/bootstrap.sh --lite
```

The Lite profile is the native edge-first control plane. It does not install,
start, or initialize the retired infrastructure stack.

Normal Lite startup also sets the synthetic qualification harness, destructive
harness, Qualification Owner, and test-bypass flags to disabled defaults. The
explicit qualification launcher and its direct-loopback contract are documented
in [Qualification & maintenance harness](../validation/qualification-maintenance-harness.md).


The Lite bootstrap profile starts only the core services needed for low-power
devices and keeps all execution behind the supported FastAPI/NATS/worker path.

## Included by default

- FastAPI
- NATS / JetStream
- worker
- node/fleet agent when available
- native Identity & Access and passkey support
- OPA policy runtime and fail-closed policy lifecycle
- SQLite state, prepared projections, and migrations
- Caddy same-origin HTTPS gateway
- native telemetry, runtime diagnostics, and resource observations
- Tailscale when remote access is configured

## Excluded by default

The following legacy services are retired from Lite and must not be installed
or started by a fresh bootstrap:

- Prometheus
- Grafana
- Gatus
- Loki
- Promtail
- Vault / OpenBao
- Gitea
- MariaDB
- legacy GitOps infrastructure orchestration

## Intended command

```bash
bash scripts/bootstrap.sh --profile lite
```

or:

```bash
bash scripts/bootstrap.sh --lite
```

## Validation

```bash
bash -n scripts/*.sh
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/ready
curl -s http://127.0.0.1:8080/api/lite/status
```

Expected result:

```text
health = healthy
ready = ready or a truthful setup/degraded response
lite status = overall healthy or degraded with a clear reason
```
