# Pocket Lab Lite Security Assurance Playbook

Status: **IMPLEMENTED documentation for the merged Runtime Security Assurance
Harness**. Commands and identifiers in this playbook are checked against the
current registries, Taskfiles, CLI parsers, and FastAPI routers by
`scripts/docs/check_security_assurance_playbooks.py`.

This is the canonical entry point for safely qualifying the actual Pocket Lab
Lite runtime. The harness is not a generic remote shell. It is a bounded,
server-owned assurance workflow that joins static evidence, supply-chain
evidence, configuration checks, runtime API checks, control-plane checks, and
reviewed threat scenarios.

## What it protects

The harness helps establish that these boundaries are real in the deployed
runtime:

- the PWA uses same-origin Caddy and FastAPI; it never talks directly to NATS;
- the browser never executes shell commands and never receives harness
  authority;
- FastAPI admits only registered suites and scenarios;
- OPA, NATS/JetStream, and the worker remain the execution owners;
- scanner output becomes normalized, sanitized, auditable evidence;
- qualification is explicit and default-off in normal production startup;
- a short authentication lease is separate from a durable assurance run
  lease.

## Who should use it

| Persona | Recommended path |
| --- | --- |
| Human security reviewer | [Architecture](01-architecture.md) → [Prerequisites](03-environment-prerequisites.md) → [Smoke](07-smoke-playbook.md) → [Findings](14-findings-remediation.md) → [Human review](19-human-review-playbook.md) |
| Codex or approved machine client | [Getting started](02-getting-started.md) → [Bootstrap/auth](05-harness-bootstrap-auth.md) → [Preflight](06-preflight.md) → [Fault/recovery](11-fault-recovery-playbook.md) |
| CI/automation service | [Toolchain](04-toolchain-installation.md) → [Command catalog](../reference/command-catalog.md) → [Evidence](15-evidence-reporting.md) |
| Developer | [Architecture](01-architecture.md) → [Tool-specific playbooks](12-tool-specific-playbooks.md) → [Remediation](14-findings-remediation.md) |
| Release engineer | [Exact-head qualification](18-exact-head-release-qualification.md) → [Evidence](15-evidence-reporting.md) → [Cleanup](16-cleanup-default-off.md) |
| Findings reviewer | [Result statuses](../reference/result-status-reference.md) → [STRIDE/OWASP/AP](13-stride-owasp-attack-paths.md) → [Evidence artifacts](../reference/evidence-artifact-reference.md) |

## Five-minute safe path

The commands below are current Taskfile commands. Run each in the stated
environment and use only an already-published, reviewed revision.

1. **[DEV PC]** Confirm the candidate revision and check the fixed toolchain:

   ```bash
   git status --short --branch
   git rev-parse HEAD
   task lite:security:assurance:tools:check
   ```

2. **[SERVER PHONE]** Confirm the consumer checkout and readiness. PM2 being
   `online` is not sufficient:

   ```bash
   git status --short --branch
   git rev-parse HEAD
   curl -fsS http://127.0.0.1:8080/health
   curl -fsS http://127.0.0.1:8080/ready
   pm2 status
   ```

3. **[SERVER PHONE / operator]** Start explicit key-bound qualification with
   the public key file already staged through the approved operator workflow:

   ```bash
   task lite:qualification:start:key-bound \
     PRINCIPAL_ID=codex-security-assurance \
     PUBLIC_KEY_FILE=~/.pocketlab-qualification/codex-security-assurance.pub
   ```

   This path fixes the profile to `security-assurance-runner` and keeps
   destructive, Owner, and test-auth flags off. The old provisioning-token
   startup remains a separate compatibility path; never put its value in a
   playbook, log, report, or model context.

4. **[APPROVED CLIENT / DEV PC]** Generate or reuse a key outside Git, then
   let the bounded client bootstrap and qualify. The client retains session
   material only in process memory:

   ```bash
   task lite:harness:keygen KEY_FILE=~/.pocketlab-qualification/codex-security-assurance.key
   task lite:security:assurance:qualify
   ```

   Use `task lite:security:assurance:qualify:full` only when Deep and the
   fixed DEV-PC lanes are explicitly intended. Do not copy a token from CLI
   output; the client intentionally redacts it.

5. **[DEV PC / approved client]** Read the sanitized report using its returned
   `run_id`, then complete [cleanup](16-cleanup-default-off.md).

   ```bash
   task lite:security:assurance:report RUN_ID=<run-id-from-sanitized-result>
   task lite:harness:verify-off
   ```

## Playbooks

1. [Architecture and trust boundaries](01-architecture.md)
2. [Getting started](02-getting-started.md)
3. [Environment prerequisites](03-environment-prerequisites.md)
4. [Toolchain installation](04-toolchain-installation.md)
5. [Bootstrap and authentication](05-harness-bootstrap-auth.md)
6. [Preflight](06-preflight.md)
7. [Smoke](07-smoke-playbook.md)
8. [Standard](08-standard-playbook.md)
9. [Adversarial](09-adversarial-playbook.md)
10. [Deep](10-deep-playbook.md)
11. [Fault and recovery](11-fault-recovery-playbook.md)
12. [Tool-specific playbooks](12-tool-specific-playbooks.md)
13. [STRIDE, OWASP, and attack paths](13-stride-owasp-attack-paths.md)
14. [Findings and remediation](14-findings-remediation.md)
15. [Evidence and reporting](15-evidence-reporting.md)
16. [Cleanup and default-off](16-cleanup-default-off.md)
17. [Troubleshooting](17-troubleshooting.md)
18. [Exact-head release qualification](18-exact-head-release-qualification.md)
19. [Human review](19-human-review-playbook.md)

## References

- [Command catalog](../reference/command-catalog.md)
- [API reference](../reference/api-reference.md)
- [Task reference](../reference/task-reference.md)
- [Tool matrix](../reference/tool-matrix.md)
- [Scenario catalog](../reference/scenario-catalog.md)
- [Fault-control catalog](../reference/fault-control-catalog.md)
- [Result status reference](../reference/result-status-reference.md)
- [Evidence artifact reference](../reference/evidence-artifact-reference.md)
- [Command completeness mapping](../reference/command-completeness.md)
- [Preserved PR #576 dossier](../evidence-history/runtime-security-assurance-qualification.md)

## Result semantics

`PASS` means the registered invariant and its required preconditions passed;
it does not mean every scanner found nothing. `FAIL` means a required
security assertion or policy threshold failed. `PARTIAL` means execution was
interrupted, resource-limited, or only some units completed. `BLOCKED` means a
required precondition was not available and must not be reinterpreted as a
vulnerability. Human-only coverage is reported as `HUMAN_REVIEW_REQUIRED`.
See the [status reference](../reference/result-status-reference.md).

## Safety warnings

!!! danger "Never turn this into a remote shell"
    Callers select only registered suite, scenario, and fault identifiers.
    They never supply commands, argv, executables, paths, URLs, ports, NATS
    subjects, templates, rules, or environment variables.

!!! warning "Server Phone ownership"
    The Server Phone is a consumer/qualification target, never the development
    workspace. Edit, test, commit, and publish on the DEV PC only.

Server Phone is a consumer/qualification target, never the development workspace.
The four registered suites are `smoke`, `standard`, `adversarial`, and `deep`.

!!! warning "Scope"
    Runtime probes target Pocket Lab-owned local/loopback surfaces only. Do not
    scan user media, PhotoPrism media, backup payloads, LAN/Tailnet peers, or
    the public Internet. Do not run destructive Recovery qualification.

## Evidence and cleanup

The client and server write sanitized evidence outside the repository under
the configured qualification evidence root. Reports contain bounded metadata,
normalized findings, coverage, and checksums; raw credentials and secret
matches are removed. Finish every run by revoking the session and disposable
principal, removing temporary client continuity/key material when appropriate,
stopping qualification, and proving the default-off state.
