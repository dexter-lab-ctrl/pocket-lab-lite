# PR #657 P4 qualification handoff

**Status: QUALIFIED WITH A DOCUMENTED PERFORMANCE RESIDUAL**

This is the source-authored handoff for the P4.0–P4.7 completion candidate. It
does not authorize merge, production activation, release or Server Phone
deployment.

## Candidate and boundary

- Base: `1ef9bcb622db6ad1d34fc38278822ed434ad6776`
- Exact code-bearing candidate: `57985fac694626d6301f9111f4270292fa351fe0`
- Isolated candidate backend, SQLite, NATS/JetStream, OPA and worker were
  hosted on DEV-PC.
- Controlled recovery was enabled only in the isolated qualification profile.
- The physical Server Phone was a browser/ADB/CDP consumer; its installed
  backend, PWA, database, services and configuration were not used for
  candidate execution or modified.

## Source and DEV-PC evidence

The source implementation includes migrations 0045–0047, durable enrollment
generation fencing, membership-aware prepared reads, bounded historical
records, the existing-owner recovery request ledger, actor-bound OPA admission,
approval compatibility, single-flight/idempotency, bounded retry/deadline and
fresh independent verification. The adapter calls the existing worker/NATS
recovery owner and does not create a second executor.

Recorded qualification results:

| Gate | Result |
| --- | --- |
| Backend P4/System Health suites | `104 passed, 1 warning` |
| OPA/policy/harness | `37 passed` |
| Final focused post-performance run | `17 passed` |
| Frontend targeted run | `18 passed` |
| Storybook build | PASS |
| Production build | PASS |
| Mocked desktop/mobile Playwright and Axe | PASS; final interaction lane `48 passed` |
| Visual System Health run | `42 passed`; no unintended snapshot delta |

Negative coverage includes anonymous/expired/unauthorized actors, stale policy,
wrong workspace, wrong incident and enrollment generation, removed targets,
malformed identities, replay conflicts, duplicate submissions, stale evidence,
historical read-only records, resource denial, disabled adapter and raw-secret
sanitization.

## Physical Android System Health

The repository-owned controller used the verified Server Phone serial
`RZCW71C09GX`, standard-user ADB/CDP, Chrome CDP protocol `1.3`, loopback-only
candidate transport and a short-lived synthetic qualification Owner. Candidate
manifest, response headers, rendered metadata, backend identity and transport
identity matched the exact candidate SHA. The isolated OPA policy revision and
SQLite schema were independently recorded.

The physical browser lane passed entry/first paint, current concern rendering,
Manage opening, diagnosis, recovery preflight/request, verified outcome and
Home return. The isolated API/read fixtures and the mocked/UI suites separately
qualified saved/offline membership, historical removed-device details and
receipts, advanced/dependency/resource disclosures, inner scrolling, mobile
sheet behavior, verification-pending and saved-state/reconnect behavior.
Historical records performed no diagnosis or recovery writes.

The final sanitized evidence record is:

```text
.pocketlab-dev/validation/pr657-system-health-android-ui-57985fac6946/
  pr657-system-health-android-ui-final-57985fac6946.json
```

It records `status=PASS`, API contract PASS, Android UI PASS, recovery lifecycle
`verified` (API admission and execution were independently recorded before the
browser run), SQLite migration/repeat-apply/integrity/rollback PASS,
cleanup PASS and no production mutation. Sanitized screenshots include landing,
diagnosis, verified recovery and Home summary captures.

## Performance

The System Health-only performance collector preserved the PR #588/#589
thresholds, evidence schema, three-repetition baseline-normalized attribution,
exit semantics and nine required interactions. The final aggregate was:

| Classification | Count | Absolute target | Hard gate |
| --- | ---: | ---: | ---: |
| Target/gate pass | 0 | 0 | 0 |
| `PLATFORM_DOMINATED` | 0 | 0 | 0 |
| `MIXED` | 9 | 0 | 0 |
| `APP_INCREMENTAL_COST` | 0 | 0 | 0 |

No stable actionable P4 application regression crossed the repository
`APP_INCREMENTAL_COST` policy. The eight MIXED findings and raw normalized
reports are retained as a legitimate residual; the absolute target and gate
are not reported as globally passing. No broad seven-screen performance run was
performed.

## Device restoration and rollout

The Server Phone remained on the authorized clean `main` checkout and installed
runtime. Qualification-owned browser tabs, candidate forwarding, synthetic
sessions and isolated services were cleaned up. Existing ADB/CDP state was
preserved. Controlled recovery is default-off outside the isolated candidate;
there was no production activation, release publication or deployment.

## Follow-up boundary

The remaining performance residual is evidence, not an implementation blocker.
Any production activation requires a separate policy decision, fresh production
admission and explicit authorization. Existing guardian, worker, supervisor,
agent and protected recovery ownership remains authoritative.
