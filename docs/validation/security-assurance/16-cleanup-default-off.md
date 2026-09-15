# Cleanup and default-off playbook

Cleanup is part of qualification, not an optional courtesy. It must remove
temporary authority while leaving the normal Pocket Lab runtime healthy.

## Client cleanup

Run on `[DEV PC]` or the approved client after the final report is collected:

```bash
python3 scripts/dev/lite/harness.py session-stop --session-id <session-id>
python3 scripts/dev/lite/harness.py principal-revoke --principal-id <principal-id>
```

Use only the session/principal IDs returned by the supported flow. If the
client process has already stopped, the server-side session and principal
revocation still take precedence. Remove the disposable private key and
continuity file from the approved client only after the report is preserved;
never put either in the repository, SQLite, logs, or evidence.

The normal `task lite:security:assurance:qualify` workflow performs its
supported cleanup path. Confirm its final status rather than assuming a
client-side exit means server-side authority is gone.

## Server Phone default-off verification

Run the following read-only checks on `[SERVER PHONE]` using the supported
runtime checkout and launcher procedures:

```bash
task lite:harness:status
task lite:harness:verify-off
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/ready
pm2 status
```

The exact API port may be supplied by the current approved runtime
configuration; do not substitute a public or unrelated host. Inspect only
sanitized status output. PM2 `online` is not a substitute for `/health` and
`/ready`.

## Required final posture

Record the observed values, or the repository-equivalent status, for:

| Check | Required end state |
| --- | --- |
| Harness | disabled; no normal browser authority |
| Destructive qualification | disabled |
| Qualification Owner | disabled |
| Test-auth bypass | disabled |
| Bootstrap grants | consumed or expired; no reusable authority |
| Sessions | zero active temporary sessions, or explicitly expired/revoked |
| Synthetic principals | disposable principal revoked/expired |
| Assurance runs | no active run left unintentionally; terminal status preserved |
| API | health and readiness healthy |
| OPA | healthy/current when used |
| NATS/JetStream | healthy and reconnectable |
| Worker | healthy and no stale run left unexplained |
| PM2 | normal services online after readiness |
| Phone checkout | clean working tree |

The safe qualification posture is equivalent to:

```text
POCKETLAB_HARNESS_ENABLED=0
POCKETLAB_HARNESS_DESTRUCTIVE=0
POCKETLAB_QUALIFICATION_OWNER=0
POCKETLAB_TEST_AUTH_BYPASS=0
```

Do not print environment values to prove this. Use `harness status`,
`verify-off`, sanitized runtime status, and health/readiness evidence.

## Cleanup failure

If cleanup fails, mark the qualification `PARTIAL` or `BLOCKED`, preserve the
sanitized reason, and revoke authority through the supported API/launcher
workflow. Do not reset the phone checkout, drop SQLite tables, delete streams,
or edit tracked source on the Server Phone.
