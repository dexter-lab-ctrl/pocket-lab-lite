# Adding a Security Assurance Scenario

A Security Assurance scenario expresses a **Pocket Lab security invariant**. A tool is only an evidence source. Do not add a scenario merely to expose a scanner, and never implement a scenario as caller-supplied shell, URL, target, port, argv, NATS subject, template, rule, or filesystem path.

The expansion model is:

```text
Threat
→ STRIDE / OWASP / AP mapping
→ PASSIVE or SAFE_ACTIVE safety class
→ existing fixed executor where possible
→ scenario registry
→ suite
→ normalized sanitized evidence
→ DEV-PC validation
→ exact SHA
→ Server Phone qualification
→ report/review
```

## Required checklist

- [ ] Threat/invariant defined
- [ ] STRIDE mapped
- [ ] OWASP mapped
- [ ] AP path mapped
- [ ] Assets/trust boundaries identified
- [ ] Safety class chosen
- [ ] Capability chosen
- [ ] Existing executor reused where possible
- [ ] Fixed executor implemented/extended if required
- [ ] No arbitrary caller inputs
- [ ] Precondition defined
- [ ] Action defined
- [ ] Expected invariant defined
- [ ] PASS semantics defined
- [ ] FAIL semantics defined
- [ ] BLOCKED semantics defined
- [ ] Cleanup defined
- [ ] Evidence normalized
- [ ] Redaction validated
- [ ] Tests added
- [ ] Suite membership chosen
- [ ] DEV-PC validation passed
- [ ] Server Phone runtime qualification passed where applicable

## Prefer extending an existing fixed scenario

The current registry deliberately keeps one top-level scenario per fixed backend executor when several closely related negative cases are executed by the same bounded probe. Add individual `coverage_cases` to the existing scenario when that avoids running the same executor repeatedly.

Examples include the existing fixed authentication probe table, Caddy proof-strip probe, evidence-redaction canaries, and Security/Lynis/Trivy projection. A `coverage_case` still needs a threat and expected invariant, but it is not a second executable endpoint. The top-level scenario remains the selectable `scenario_id` and the backend continues to own all request details.

## When a genuinely new executor is required

A new top-level scenario is appropriate only when the invariant cannot be proven by an existing fixed executor. The implementation must live in the existing Runtime Security Assurance service/dispatcher or an existing registered tool lane. It owns:

```text
endpoint / method / request shape
test fixture or synthetic identity
fixed target and timeout
expected rejection/reason code
expected invariant
cleanup
sanitization
normalized evidence
```

The request model must continue accepting only registered identity such as `suite_id`, `scenario_id`, and a compatible baseline run ID. Do not add execution parameters to the FastAPI request.

## Threat-model mapping

Reuse the existing AP ID when the threat path is already represented. Attack paths model threats, not tools. Create a new AP only when the threat moves through a genuinely different asset/trust-boundary/control path, then update the canonical threat model first.

Mappings must use the six canonical STRIDE categories and OWASP Top 10 2021 IDs. Do not call an OWASP category `PASS` merely because a tool found nothing; use the execution/evidence classification that the scenario actually supports.

## Suite placement

**Smoke** is small, fast, deterministic, and critical-boundary only. **Standard** is the routine PASSIVE/SAFE_ACTIVE suite. **Adversarial** contains controlled negative/boundary tests and never destructive attacks. **Deep** is manual-intent, heavyweight or broader static/live-runtime evidence.

## Validation

Run at minimum:

```bash
python3 -m py_compile tests/backend/test_lite_security_assurance_scenario_contracts.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q \
  tests/backend/test_lite_security_assurance_scenario_contracts.py
task lite:security:assurance:check
task lite:docs:check
git diff --check
```

For a Server Phone scenario, qualify the **exact published SHA** and preserve the sanitized report identity. If the phone was not exercised, report `SERVER PHONE RUNTIME QUALIFICATION — NOT VALIDATED` rather than inferring success.
