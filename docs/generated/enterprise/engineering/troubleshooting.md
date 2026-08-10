---
title: "Development Troubleshooting"
description: "Diagnostic handbook with command safety classification."
generated: true
audience: development
page_type: troubleshooting
confidence: generated
---

# Development Troubleshooting — diagnostic handbook

## API unavailable

### Symptom
Lite API cannot be reached

### Interpretation
FastAPI/Caddy or local dependency unavailable

### Causes
- FastAPI/Caddy or local dependency unavailable

### Safe checks
| Command | Safety |
| --- | --- |
| curl -fsS http://127.0.0.1:8443/api/lite/status | READ_ONLY |
| pm2 status | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## NATS unavailable

### Symptom
write paths cannot safely deliver commands

### Interpretation
NATS/JetStream unavailable

### Causes
- NATS/JetStream unavailable

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| ss -ltnp | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## JetStream problem

### Symptom
durable command/event flow degrades

### Interpretation
consumer/stream health degraded

### Causes
- consumer/stream health degraded

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Agent offline

### Symptom
device appears Offline

### Interpretation
heartbeat/NATS/Tailscale interruption

### Causes
- heartbeat/NATS/Tailscale interruption

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Agent stopped

### Symptom
device reports Agent stopped

### Interpretation
PM2 node-agent process stopped

### Causes
- PM2 node-agent process stopped

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Supervisor absent

### Symptom
automatic agent recovery unavailable

### Interpretation
supervisor process absent

### Causes
- supervisor process absent

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Tailscale unavailable

### Symptom
Remote access not ready

### Interpretation
tailscaled/Tailnet readiness issue

### Causes
- tailscaled/Tailnet readiness issue

### Safe checks
| Command | Safety |
| --- | --- |
| tailscale status | READ_ONLY |
| tailscale ip -4 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## PhotoPrism unavailable

### Symptom
app route does not open

### Interpretation
PhotoPrism runtime/Caddy route issue

### Causes
- PhotoPrism runtime/Caddy route issue

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Backup stale

### Symptom
latest backup evidence is old

### Interpretation
backup execution/freshness issue

### Causes
- backup execution/freshness issue

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Restore blocked

### Symptom
restore cannot proceed

### Interpretation
preview/checkpoint/health guard unsatisfied

### Causes
- preview/checkpoint/health guard unsatisfied

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Security scan stuck

### Symptom
Safety Check does not advance

### Interpretation
worker/consumer/scanner issue

### Causes
- worker/consumer/scanner issue

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Caddy routing issue

### Symptom
same-origin route fails

### Interpretation
Caddy configuration/runtime issue

### Causes
- Caddy configuration/runtime issue

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Release mismatch

### Symptom
installed/runtime release identities differ

### Interpretation
source/release/runtime binding not converged

### Causes
- source/release/runtime binding not converged

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Runtime evidence stale

### Symptom
docs show an old promoted observation

### Interpretation
new capture has not been explicitly promoted

### Causes
- new capture has not been explicitly promoted

### Safe checks
| Command | Safety |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Docs generation drift

### Symptom
lite:docs:check reports drift

### Interpretation
generated artifacts are out of sync or generator nondeterministic

### Causes
- generated artifacts are out of sync or generator nondeterministic

### Safe checks
| Command | Safety |
| --- | --- |
| task lite:docs:enterprise:check | READ_ONLY |
| git diff --check | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Parity mismatch

### Symptom
semantic/runtime parity differs

### Interpretation
backend/frontend/runtime contract divergence

### Causes
- backend/frontend/runtime contract divergence

### Safe checks
| Command | Safety |
| --- | --- |
| task lite:parity:runtime:compare | READ_ONLY |

### Expected result
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Next diagnostic step
open related generated runbook and follow dependency-specific checks

### Repair options
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### Do not do
- do not bypass FastAPI/NATS ownership
- do not overwrite device identity
- do not expose secrets
- do not run destructive commands inferred from documentation

### Evidence
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes
