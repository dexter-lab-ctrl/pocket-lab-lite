# Adding a Security Assurance Tool

A new tool is justified only when an existing registered tool cannot produce the evidence required by a defined Pocket Lab security invariant. The normal expansion path is **threat → scenario → fixed executor/tool → suite → normalized evidence**, never **threat → arbitrary shell script**.

Before adding software, inspect `security/assurance/tools.yaml` and the existing execution lanes. Pocket Lab already has worker-owned local tooling and DEV-PC static/live-runtime tools; do not move heavyweight scanners onto Android merely to label them runtime tests.

## Required checklist

- [ ] Purpose justified
- [ ] Existing tool cannot satisfy need
- [ ] Execution lane selected
- [ ] Version pinned
- [ ] Approved installation source
- [ ] Checksum/signature/receipt policy
- [ ] Fixed command_id
- [ ] Fixed target
- [ ] Fixed argv
- [ ] Parser
- [ ] Sanitizer
- [ ] Resource class
- [ ] Timeout
- [ ] Output bound
- [ ] Retry semantics
- [ ] Checkpoint semantics
- [ ] Suite membership
- [ ] Tests
- [ ] Tool-manager install/check
- [ ] Actual harness execution
- [ ] Evidence/report integration

## Execution lanes

Use `server_phone_worker` only when evidence genuinely requires local runtime/host state. Pocket Lab Security, Lynis, Trivy, and OPA stay worker/backend owned.

Use `dev_pc_static` for source, dependency, secret, SBOM, signature, and package analysis. Existing examples include Bandit, Semgrep, Gitleaks, OSV-Scanner, Syft, Grype, pip-audit, npm audit, and Cosign.

Use `dev_pc_live_runtime` for bounded network/API/TLS analysis of the actual Server Phone. Existing contracts include Schemathesis, Nuclei safe templates, fixed-loopback nmap, testssl.sh, and OWASP ZAP baseline.

## Fixed-contract rules

The tool registry must own the target, command ID, argv, timeout, output bound, rules/templates, and retry/checkpoint semantics. A client may select a registered suite/tool workflow but must not supply scanner arguments or a target.

For the current live-runtime tools:

- Nuclei uses only checked-in reviewed templates under `security/assurance/nuclei-safe-templates/`; no public exploit templates or Interactsh.
- nmap remains bound to the registered loopback target and Pocket Lab-owned listener ports. Full-range enumeration and LAN, Tailnet, or public scanning remain prohibited.
- ZAP remains baseline/passive and route-allowlisted; no unrestricted spider or active attack mode.
- Schemathesis remains route/method allowlisted and bounded in examples/workers.
- testssl.sh remains bound to the fixed Pocket Lab Caddy TLS/SNI tunnel.

A scanner alert is evidence requiring interpretation; it is not automatically a demonstrated exploit.

## Parser and sanitization

Persist only normalized findings. Never persist raw credential matches, Authorization headers, cookies, private keys, NATS/Tailscale/Recovery secrets, user media, or unbounded scanner payloads. The report publication workflow consumes normalized sanitized evidence only.

## Validation

Run:

```bash
task lite:security:assurance:tools:check
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q \
  tests/backend/test_lite_security_assurance_scenario_contracts.py
task lite:security:assurance:check
task lite:docs:check
git diff --check
```

For a newly added tool, also run its real registered harness/tool-manager execution before claiming the integration validated. `check` proves readiness metadata; it does not prove a scan was executed.
