# 9. Adversarial playbook

Adversarial is an explicit, qualification-only suite. It sends bounded
negative control-boundary requests; it is not a generic penetration-testing
console and it never performs brute force, uncontrolled load, public-network
scanning, or destructive Recovery.

## Run

**[APPROVED CLIENT]** Run the fixed registered suite after Smoke has passed:

```bash
task lite:security:assurance:preflight SUITE=adversarial
task lite:security:assurance:adversarial
```

The profile target is 180 seconds, maximum 600 seconds, and only
`SAFE_ACTIVE` units are permitted. Use `task lite:security:assurance:scenario ID=<registered-id>`
only for a scenario present in the catalog.

## Current registered scenarios

| Scenario | Threat hypothesis | STRIDE | OWASP | AP paths | Expected result |
| --- | --- | --- | --- | --- | --- |
| `harness-auth-boundary` | signed session must bind profile, purpose, target, runtime, and principal | Spoofing, Tampering, Elevation of Privilege | A01, A07 | AP-01, AP-02, AP-03, AP-04, AP-09, AP-10 | invalid or escalated authority rejected; valid bounded authority admitted |
| `caddy-proof-strip` | forwarded qualification proof must not become synthetic authority | Spoofing, Tampering, Elevation of Privilege | A01, A07 | AP-01, AP-02, AP-07, AP-09 | proxy proof denied/stripped with sanitized transport evidence |
| `runtime-readiness` | process-online posture must not bypass readiness | Denial of Service | none | AP-07, AP-11, AP-12 | not-ready admission blocked |
| `evidence-redaction` | injected output must not poison durable evidence or reveal secrets | Repudiation, Information Disclosure, Tampering | A02, A05, A08, A09 | AP-05, AP-06, AP-08 | only normalized sanitized evidence persists |
| `source-boundaries` | source must preserve browser/shell/NATS/user-media boundaries | Tampering, Information Disclosure, Elevation of Privilege | A01, A02, A05, A08 | AP-01, AP-02, AP-04, AP-05, AP-07 | bounded source assertions remain true |
| `adversarial-negative-auth-probes` | malformed and replayed authentication/input claims must fail closed | Spoofing, Tampering, Elevation of Privilege | A01, A03, A07 | AP-01, AP-02, AP-03, AP-04, AP-09, AP-10 | registered negative probes are rejected with current sanitized reason codes |

The negative-probe scenario is the current registry’s bounded grouping for
invalid signatures, replay/expiry, wrong profile/purpose/target/runtime,
capability escalation, Owner attempts, forwarded proof, unknown values,
malformed input, and unauthorized report/cancel checks. The exact set and
reason codes are source-owned; do not invent a client-side variant.

Bootstrap grant replay, wrong key/signature, expiry, production rejection,
and second-use checks are covered by the harness tests and bootstrap protocol;
they are not caller-selectable arbitrary scenarios. Use the [scenario catalog](../reference/scenario-catalog.md)
and [authentication playbook](05-harness-bootstrap-auth.md).

## Pass criteria

An adversarial test passes when the expected denial or bounded recovery is
observed, the reason is sanitized, audit correlation is present, no alternate
authority is granted, and no state outside the approved scope changes. The
negative request itself may return an HTTP error; that is expected. A fault
invariant can pass even when the injected operation returns `FAIL`.
