---
title: "Production Troubleshooting"
description: "Plain-language production diagnostic companion with safe progressive disclosure."
generated: true
audience: production
page_type: troubleshooting
confidence: generated
---

# Production Troubleshooting

Start with symptoms and read-only checks. Open the linked runbook before repair. Technical commands remain classified.

## API unavailable

**Symptom:** Lite API cannot be reached
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** FastAPI/Caddy or local dependency unavailable
**Safe checks:** curl -fsS http://127.0.0.1:8443/api/lite/status, pm2 status
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/api-unavailable.md`

## NATS unavailable

**Symptom:** write paths cannot safely deliver commands
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** NATS/JetStream unavailable
**Safe checks:** pm2 status, ss -ltnp
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/nats-unavailable.md`

## JetStream problem

**Symptom:** durable command/event flow degrades
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** consumer/stream health degraded
**Safe checks:** pm2 status, pm2 logs <process> --lines 80
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/jetstream-problem.md`

## Agent offline

**Symptom:** device appears Offline
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** heartbeat/NATS/Tailscale interruption
**Safe checks:** pm2 status, pm2 logs <process> --lines 80
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/agent-offline.md`

## Agent stopped

**Symptom:** device reports Agent stopped
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** PM2 node-agent process stopped
**Safe checks:** pm2 status, pm2 logs <process> --lines 80
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/agent-stopped.md`

## Supervisor absent

**Symptom:** automatic agent recovery unavailable
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** supervisor process absent
**Safe checks:** pm2 status, pm2 logs <process> --lines 80
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/supervisor-absent.md`

## Tailscale unavailable

**Symptom:** Remote access not ready
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** tailscaled/Tailnet readiness issue
**Safe checks:** tailscale status, tailscale ip -4
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/tailscale-unavailable.md`

## PhotoPrism unavailable

**Symptom:** app route does not open
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** PhotoPrism runtime/Caddy route issue
**Safe checks:** pm2 status, pm2 logs <process> --lines 80
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/photoprism-unavailable.md`

## Backup stale

**Symptom:** latest backup evidence is old
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** backup execution/freshness issue
**Safe checks:** pm2 status, pm2 logs <process> --lines 80
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/backup-stale.md`

## Restore blocked

**Symptom:** restore cannot proceed
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** preview/checkpoint/health guard unsatisfied
**Safe checks:** pm2 status, pm2 logs <process> --lines 80
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/restore-blocked.md`

## Security scan stuck

**Symptom:** Safety Check does not advance
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** worker/consumer/scanner issue
**Safe checks:** pm2 status, pm2 logs <process> --lines 80
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/security-scan-stuck.md`

## Caddy routing issue

**Symptom:** same-origin route fails
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** Caddy configuration/runtime issue
**Safe checks:** pm2 status, pm2 logs <process> --lines 80
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/caddy-routing-issue.md`

## Release mismatch

**Symptom:** installed/runtime release identities differ
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** source/release/runtime binding not converged
**Safe checks:** pm2 status, pm2 logs <process> --lines 80
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/release-mismatch.md`

## Runtime evidence stale

**Symptom:** docs show an old promoted observation
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** new capture has not been explicitly promoted
**Safe checks:** pm2 status, pm2 logs <process> --lines 80
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/runtime-evidence-stale.md`

## Docs generation drift

**Symptom:** lite:docs:check reports drift
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** generated artifacts are out of sync or generator nondeterministic
**Safe checks:** task lite:docs:enterprise:check, git diff --check
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/docs-generation-drift.md`

## Parity mismatch

**Symptom:** semantic/runtime parity differs
**Impact:** affected capability may be unavailable, degraded, stale or safely blocked
**Interpretation:** backend/frontend/runtime contract divergence
**Safe checks:** task lite:parity:runtime:compare
**Expected result:** compare read-only output with canonical health/readiness contract; preserve discrepancy
**Next:** open related generated runbook and follow dependency-specific checks
**Do not act when:** when evidence is stale/ambiguous, when action would overwrite identity or secrets, when healthy online device removal is not explicitly approved
**Runbook:** `generated/enterprise/operate/runbooks/parity-mismatch.md`
