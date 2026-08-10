---
title: "JetStream problem"
description: "Production runbook for JetStream problem."
generated: true
audience: production
page_type: runbook
confidence: generated
---

# JetStream problem

## Trigger
durable command/event flow degrades

## Impact
affected capability may be unavailable, degraded, stale or safely blocked

## Urgency
high

## User-visible symptom
durable command/event flow degrades

## Known evidence
- canonical operational health
- dependency health
- promoted runtime comparison

## Safe checks
| Command | Class |
| --- | --- |
| pm2 status | READ_ONLY |
| pm2 logs <process> --lines 80 | READ_ONLY |

## Expected output
compare read-only output with canonical health/readiness contract; preserve discrepancy

## Decision tree
1. If read-only health proves dependency unavailable → follow its reviewed recovery path
1. If state is stale but service healthy → refresh/capture through existing explicit workflows
1. If ownership is unclear → stop and escalate; do not improvise destructive repair

## Recovery
only canonical SAFE_REPAIR procedures; generator never invents repair commands

## Verification
rerun read-only health plus relevant parity/docs/domain checks

## Rollback
use release/recovery runbook when a prior change caused the issue

## When not to act
- when evidence is stale/ambiguous
- when action would overwrite identity or secrets
- when healthy online device removal is not explicitly approved

## Evidence to preserve
- sanitized API status
- PM2 status metadata
- promoted runtime comparison
- relevant reason codes

## Escalation
escalate to the source/runtime owner when safe checks do not establish a reviewed repair path
