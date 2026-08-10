---
title: "Production Incident Runbooks"
description: "Operator-safe incident decision support generated from canonical diagnostics."
generated: true
audience: production
page_type: runbook
confidence: generated
---

# Production Incident Runbooks

## API unavailable

### Trigger
Lite API cannot be reached

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
high

### User-visible symptom
Lite API cannot be reached

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| curl -fsS http://127.0.0.1:8443/api/lite/status | READ_ONLY |
| pm2 status | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## NATS unavailable

### Trigger
write paths cannot safely deliver commands

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
high

### User-visible symptom
write paths cannot safely deliver commands

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| ss -ltnp | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## JetStream problem

### Trigger
durable command/event flow degrades

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
high

### User-visible symptom
durable command/event flow degrades

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Agent offline

### Trigger
device appears Offline

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
device appears Offline

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Agent stopped

### Trigger
device reports Agent stopped

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
device reports Agent stopped

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Supervisor absent

### Trigger
automatic agent recovery unavailable

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
automatic agent recovery unavailable

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Tailscale unavailable

### Trigger
Remote access not ready

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
Remote access not ready

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| tailscale status | READ_ONLY |
| tailscale ip -4 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## PhotoPrism unavailable

### Trigger
app route does not open

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
app route does not open

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Backup stale

### Trigger
latest backup evidence is old

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
latest backup evidence is old

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Restore blocked

### Trigger
restore cannot proceed

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
high

### User-visible symptom
restore cannot proceed

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Security scan stuck

### Trigger
Safety Check does not advance

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
Safety Check does not advance

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Caddy routing issue

### Trigger
same-origin route fails

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
same-origin route fails

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Release mismatch

### Trigger
installed/runtime release identities differ

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
installed/runtime release identities differ

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Runtime evidence stale

### Trigger
docs show an old promoted observation

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
docs show an old promoted observation

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Docs generation drift

### Trigger
lite:docs:check reports drift

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
lite:docs:check reports drift

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| task lite:docs:enterprise:check | READ_ONLY |
| git diff --check | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path

## Parity mismatch

### Trigger
semantic/runtime parity differs

### Impact
affected capability may be unavailable, degraded, stale or safely blocked

### Urgency
moderate

### User-visible symptom
semantic/runtime parity differs

### Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

### Safe checks
| Command | Class |
| --- | --- |
| task lite:parity:runtime:compare | READ_ONLY |

### Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

### Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

### Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

### Verification
rerun read-only health plus relevant parity/docs/domain checks

### Rollback
use release/recovery runbook when a prior change caused the issue

### When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

### Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

### Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path
