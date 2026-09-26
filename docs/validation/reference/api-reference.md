# Direct-loopback harness API reference

This reference is extracted from the current FastAPI routers:
`pocket-lab-final-structure/runtime/api_fastapi/routers/harness.py` and
`pocket-lab-final-structure/runtime/api_fastapi/routers/security_assurance.py`.
It documents the supported machine/operator surface, not a browser API.

Every route requires direct loopback transport. Caddy/proxy requests,
forwarded markers, and browser-held proof cannot activate harness authority.
Error bodies are sanitized and contain a bounded `reason_code`, `message`, and
`sanitized: true` field. Extra request fields are rejected by the current
Pydantic models.

## Harness routes

| Method and route | Purpose | Authentication/authority | Input and response |
| --- | --- | --- | --- |
| POST /api/lite/harness/bootstrap/grants | Create process-ephemeral key-bound bootstrap grant | direct loopback; qualification approval state | body `principal_id`, `public_key`; returns bounded grant metadata, never a bearer secret |
| POST /api/lite/harness/bootstrap/challenge | Issue a one-use bootstrap challenge | direct loopback; valid grant | body `grant_id`; returns challenge binding and signing payload |
| POST /api/lite/harness/bootstrap/complete | Verify proof, create disposable principal, consume grant, issue session | direct loopback; valid challenge and Ed25519 proof | body challenge/grant/principal/public-key/signature fields; returns sanitized principal/session metadata |
| GET /api/lite/harness/capabilities | Read server-owned profile/capability manifest | direct loopback; no browser path | no body; returns profile manifest |
| GET /api/lite/harness/status | Read bounded harness posture | direct loopback; no browser path | no body; returns sanitized status |
| POST /api/lite/harness/principals | Legacy/manual public-principal registration | direct loopback; existing operator provisioning authorization | body public principal/profile/expiry fields; returns principal metadata |
| POST /api/lite/harness/principals/{principal_id}/revoke | Revoke a provisioned principal | direct loopback; existing operator provisioning authorization | path principal ID; returns bounded revocation result |
| DELETE /api/lite/harness/principals/{principal_id} | Revoke a provisioned principal through the delete-compatible route | direct loopback; existing operator provisioning authorization | path principal ID; returns bounded revocation result |
| POST /api/lite/harness/principal/revoke | Self-revoke bootstrap-created assurance principal | direct loopback; active session with `security.assurance.cleanup` | empty body; returns bounded cleanup result |
| POST /api/lite/harness/challenge | Issue a normal signed-session challenge | direct loopback; active registered principal/profile | body principal, purpose, profile, target, optional TTL; returns canonical signing payload |
| POST /api/lite/harness/session | Create a normal short-lived harness session | direct loopback; valid one-use challenge/signature | body challenge ID, exact signing payload, signature, optional bindings/TTL; returns session metadata and token only to the process response |
| GET /api/lite/harness/session/{session_id} | Read session status | direct loopback; session header for the same session | path/session header; returns sanitized lifecycle status |
| DELETE /api/lite/harness/session/{session_id} | Revoke a session | direct loopback; session header for the same session | path/session header; returns bounded revocation result |
| POST /api/lite/harness/browser/bridge | Create a short-lived browser projection for UI qualification | direct loopback; authenticated `qualification-owner` session with `qualification.browser_bridge` capability; never a browser authority source | no body; returns process-only bridge metadata/token to the runner; browser receives only the bounded bridge header |

The legacy manual registration path is retained for compatibility. The
operator-approved key-bound bootstrap is the preferred automated qualification
path because the machine proves possession of the private key without receiving
a general-purpose provisioning bearer.

## Security Assurance routes

| Method and route | Purpose | Authentication/authority | Input and response |
| --- | --- | --- | --- |
| GET /api/lite/harness/security-assurance/capabilities | Read assurance capabilities | direct loopback | no body; returns registered capability posture |
| GET /api/lite/harness/security-assurance/suites | Read fixed suite registry | direct loopback | no body; returns suite definitions |
| GET /api/lite/harness/security-assurance/preflight | Run fixed admission checks | session with `security.assurance.read` | query `suite_id`; returns sanitized readiness checks/status |
| GET /api/lite/harness/security-assurance/policy-sync/status | Read policy-source convergence | session with `security.assurance.read` | no body; returns bounded source state |
| POST /api/lite/harness/security-assurance/policy-sync | Request supported policy synchronization | session with `security.assurance.policy_sync` | body `{}` only; returns accepted operation/status |
| GET /api/lite/harness/security-assurance/faults | List fixed qualification fault controls | direct loopback | no body; returns fixed fault metadata |
| POST /api/lite/harness/security-assurance/faults/{fault_id} | Execute one registered fault control | session with `security.assurance.fault_control`; qualification-only | body `{"confirm": true}`; returns bounded fault operation state |
| GET /api/lite/harness/security-assurance/runs | List caller-principal-owned runs | session with `security.assurance.read` | optional bounded `limit`; returns sanitized run summaries |
| POST /api/lite/harness/security-assurance/runs | Admit and publish a registered assurance run | session with `security.assurance.run`; optional scenario/baseline capabilities | body `suite_id`, optional `scenario_id`, optional `baseline_run_id`; returns run/operation/subject metadata |
| GET /api/lite/harness/security-assurance/runs/{run_id} | Read an owned run | session with `security.assurance.read` | path run ID; returns status, preflight, checkpoint and correlation metadata |
| GET /api/lite/harness/security-assurance/runs/{run_id}/findings | Read owned normalized findings | session with `security.assurance.read` | path run ID; returns sanitized findings |
| GET /api/lite/harness/security-assurance/runs/{run_id}/events | Read owned run events | session with `security.assurance.read` | path run ID and bounded `after` sequence; returns sanitized events |
| POST /api/lite/harness/security-assurance/runs/{run_id}/resume | Reconcile/resume an owned run | session with `security.assurance.run` | path run ID; no caller-selected command; returns existing/requeued worker state |
| GET /api/lite/harness/security-assurance/runs/{run_id}/report | Read owned report | session with `security.assurance.report` | path run ID; returns sanitized report/artifact references |
| POST /api/lite/harness/security-assurance/runs/{run_id}/cancel | Request cancellation of an owned run | session with `security.assurance.cancel` | path run ID; no body; returns cancellation/checkpoint state |

## Fixed security rules

- The caller never selects executable, argv, cwd, filesystem path, URL, host,
  port, NATS subject, scanner flags, rules, templates, or environment.
- The assurance worker publishes to the fixed
  `pocketlab.commands.lite.security.assurance` subject through the normal
  FastAPI/JetStream path.
- Run ownership, profile, purpose, target, runtime, revision, principal class,
  expiry, and capability checks are server-side.
- Session tokens are process-only client values; the server persists only
  protected token material consistent with the harness implementation.
- Reports are normalized and sanitized before persistence and response.
- The normal PWA does not expose these routes or hold qualification authority.
