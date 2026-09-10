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

The lite profile keeps the core control plane and skips the external observability stack by default.

Normal Lite startup also sets the synthetic qualification harness, destructive
harness, Qualification Owner, and test-bypass flags to disabled defaults. The
explicit qualification launcher and its direct-loopback contract are documented
in [Qualification & maintenance harness](../validation/qualification-maintenance-harness.md).


The lite bootstrap profile starts only the core services needed for low-power devices.

## Included by default

- FastAPI
- NATS / JetStream
- worker
- node/fleet agent when available
- Vault
- Gitea only if App Catalog or GitOps storage requires it
- MariaDB only if required by Gitea
- Caddy or a lightweight static frontend server
- lightweight telemetry sampler

## Excluded by default

The lite profile should not start the external observability stack:

- Prometheus
- Grafana
- Gatus
- Loki
- Promtail

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
ready = ready
lite status = overall healthy or degraded with a clear reason
```
