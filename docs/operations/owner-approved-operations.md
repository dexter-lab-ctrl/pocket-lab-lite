# Single-use Owner-approved operations

## Status

This document describes the versioned production contract introduced by the
`feat/owner-approved-operations` change. The only enabled operation is
`photo_backup.bounded_acceptance.v1`. Release-bound, physical Android, and
production PhotoPrism evidence remain separate gates; a local or isolated
qualification result is not production evidence.

## Purpose and boundary

Pocket Lab Lite can receive a request from a registered automation client and
present one bounded operation to a real authenticated Owner. The Owner's
decision is bound to the exact server-normalized descriptor, target identity,
destination contract, and fixed Photo Backup scope. Approval is a short-lived
authorization for one workflow instance, not a permanent backup permission,
an Owner session, or a reusable maintenance session.

The contract deliberately does not accept executable commands, shell text,
URLs, source paths, destination paths, NATS subjects, credential references,
arbitrary handlers, or caller-selected JSON capabilities. The server selects
the registered handler and resolves the target and destination from its own
state.

## Four principals

| Principal | Responsibility | Authority boundary |
| --- | --- | --- |
| Requester | Registered automation client, such as Codex | Signs a bounded descriptor and reads its own sanitized operation evidence |
| Approver | Real Pocket Lab human Owner | Uses the normal Identity session, CSRF protection, policy decision, and required passkey step-up |
| Executor | FastAPI/worker/NATS/agent/supervisor workflow | Runs only the registered handler and existing Photo Backup admission path |
| Observer | Capability-limited registered client | Reads sanitized status and evidence for its own operation only |

Registration does not authenticate an Owner. An approved operation does not
grant the requester any Owner capability. Synthetic qualification principals
are rejected by the production operation service even when they can render a
qualification Owner presentation elsewhere.

## Client registration and proof of possession

An authorized Owner registers a client through a server-issued Ed25519
challenge. The server stores the public key and a server-owned capability set;
the client cannot self-assign capabilities. Registration and revocation use
the normal authenticated Identity session, CSRF checks, Owner authorization,
and the separate `owner.operations.client.register` passkey assurance
purpose.

The production requester-facing path is a short-lived pairing request:

1. The candidate asks for a challenge with its client ID, display name, and
   public key. The server computes the fingerprint and fixed capability; the
   candidate signs the server payload with its private key.
2. The signed request creates a durable `pending` pairing in migration 0042.
   It is not an active client and cannot request, observe, or execute a Photo
   Backup operation. The pairing expires after 15 minutes and can be rejected,
   cancelled by the proving requester, or reconciled to `expired`.
3. Identity & Access → Manage Access → Trusted automation clients shows only
   the sanitized display name, client ID, public-key fingerprint, fixed
   capability, and expiry. The browser never receives or stores the private key
   or the raw signed payload.
4. A real Owner registers the exact pairing. The PWA uses CSRF/origin
   protection and the `owner.operations.client.register` passkey step-up. The
   pairing and active client row are created in one SQLite transaction, so an
   interrupted decision cannot leave half-authorized state.

Pairing challenges use the existing Ed25519 nonce and immutable-binding
verifier, but carry `registration_mode=pairing`. The legacy Owner-initiated
registration challenge carries a different mode, so a pairing proof cannot be
replayed against that endpoint. An active client can later be revoked from the
same Owner-managed surface; revocation consumes outstanding challenges and
cancels eligible bounded operations. Re-registration of a revoked identity is
not an implicit recovery path.

Request, observe, and cancel operations use short-lived, single-use,
server-generated challenges. The signed payload contains the challenge,
client, purpose, nonce, expiry, and a digest of the exact binding. Failed
proof attempts are bounded and active challenges are rate-limited. Proof
material is not accepted in query strings.

## Versioned descriptor

The current descriptor is strict and canonicalized before it is stored:

```json
{
  "contract_version": 1,
  "operation": "photo_backup.bounded_acceptance.v1",
  "requester_id": "registered-qualification-client",
  "target_node_id": "server-resolved-secondary-device",
  "scope": {
    "fixture": "one_server_generated_jpeg",
    "collection": "pictures",
    "repeat": "same_fixture_once"
  },
  "reason": "Production Photo Backup acceptance",
  "idempotency_key": "owner-acceptance-2026-10-18-01"
}
```

The example values are illustrative. The target device, identity revision,
PhotoPrism destination, destination schema, capacity admission, fixture ID,
and resource limits are resolved by the server. Unknown fields, versions,
operation types, target identities, scope values, paths, URLs, and malformed
idempotency keys are rejected. The immutable descriptor and scope digest are
stored with the operation.

## Durable lifecycle and recovery

The SQLite-backed lifecycle is:

```text
pending_approval
  -> approved
  -> executing
  -> verifying
  -> completed
```

It can instead end as `rejected`, `expired`, `cancelled`, `failed`, or
`blocked`. Approval and execution are separate states. The record retains the
operation ID, requester, target binding, immutable scope, deadlines, approval
actor and assurance reference, backup job IDs, execution stage, terminal
reason, sanitized evidence, and append-only operation events.

The approval window and execution window are separate. A worker or API restart
reconciles the same durable record and existing Photo Backup job. A dispatch
lease can be reclaimed for the same operation, but it cannot create a second
authorization. The one fixture ID is persisted before later admission or
publish steps so a retry cannot issue a second source fixture. If a target,
requester, destination admission, capacity reserve, credential, heartbeat, or
policy condition is no longer valid, the workflow stops or requests
server-owned cancellation of the exact existing job.

Requester revocation cancels pending work and asks the worker to stop active
work through the existing Photo Backup cancellation and credential-revocation
path. Completed destination media is retained according to the Photo Backup
retention contract; retry never deletes personal media and never uses `rclone
sync`.

## Owner approval

The Identity & Access surface shows a pending approval only when the server
returns a sanitized live projection. It discloses:

- the target Secondary Phone;
- PhotoPrism originals on this server as the fixed destination;
- possible creation of the persistent destination identity anchor;
- one generated synthetic test photo and possible retained destination media;
- one safe repeat of the same fixture;
- expiry and the fact that the decision cannot authorize another request.

The approve action uses the existing authenticated Identity session and CSRF
header, revalidates the Owner, session, passkey assurance, requester, target,
expiry, and policy, and atomically changes only the exact pending record.
Duplicate or concurrent approval loses the state transition. Rejection is
also terminal. Saved or stale browser data never enables an approval action;
the backend remains authoritative.

The action is registered as `owner.operations.approve` in the policy catalog
and OPA input. Personal Mode still requires the local Owner; Enterprise Mode
requires an active Owner membership. Enterprise role labels do not grant this
operation to Admin, Operator, Auditor, or Viewer roles.

## Server-owned Photo Backup handler

After approval, the registered handler reuses the released Photo Backup
implementation. It does not create a second backup engine. The handler:

1. rechecks requester, target identity, destination identity, capacity
   reserves, fixture TTL, and the execution deadline;
2. prepares at most one backend-owned JPEG in the fixed Pictures acceptance
   scope;
3. invokes the normal destination admission, durable job ledger,
   idempotency, NATS/JetStream, worker, agent, supervisor, WebDAV,
   finalization, evidence, and credential-revocation paths;
4. reconciles the durable job after delivery acknowledgment, process restart,
   redelivery, agent restart, or WebDAV failure; and
5. dispatches one repeat using the same fixture and records the final verdict.

The handler cannot widen a collection, select a source path, choose a remote,
or supply a credential. The browser never talks to NATS or WebDAV and never
receives backend secrets.

## Evidence and PhotoPrism indexing truth

Requester and observer reads expose only aggregate counts, fixed scope,
integrity mode, processing state, repeat result, credential-revocation state,
terminal verdict, and bounded lifecycle events. They do not expose Owner
cookies, passkeys, recovery codes, raw PhotoPrism credentials, NATS
credentials, private filesystem fingerprints, originals paths, or raw rclone
output.

A successful WebDAV finalization proves transfer to the authorized originals
namespace. It does not prove that PhotoPrism has indexed the object. The
current repository has no narrow authoritative indexing lookup for this
fixture, so the operation records indexing as `unvalidated` unless a future
supported lookup can prove it. It must never turn an upload result into a
false indexed claim.

## Qualification and production separation

The qualification harness remains loopback/isolated and synthetic. Its
Ed25519 principals and synthetic Owner presentation are not valid production
approval credentials. Development qualification must use disposable API,
NATS/JetStream, agent, and WebDAV infrastructure and must assert that a
qualification approval cannot mutate a production destination. Only a
reviewed exact release and the existing physical Android lane can produce
production runtime evidence.

## Future extension points

The tables and service use a registered operation-handler boundary so future
operations can be added as explicit, statically validated contracts with
named capabilities, restricted targets, independent expiry, revocation,
approval history, and sanitized observation. Possible future identifiers
include `security.quick_check.v1`, `devices.agent_diagnostics.v1`,
`recovery.readiness_check.v1`, and `release.runtime_qualification.v1`.

Those identifiers are not enabled by this change. Generic shell execution,
arbitrary API forwarding, unrestricted maintenance sessions, automated Owner
impersonation, and role-based approval chains remain deferred. Any future
handler must preserve requester/approver/executor/observer separation and
must be added through a separately reviewed policy and migration contract.

## Rollback and limitations

Rollback is the normal reviewed release rollback to the previous known-good
release. A rollback must preserve existing PhotoPrism originals, destination
identity anchors, enrolled device identities, backup job records, and
credential cleanup state. It must not delete accepted destination media to
hide a failed qualification. If a migration or runtime cannot be validated,
stop before release or deployment and leave the draft change open.

This increment does not claim physical Android qualification, production
deployment, a real Owner decision, PhotoPrism indexing, or Mode B acceptance.
Those are independent gates and must be reported separately.
