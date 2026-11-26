# Trusted Lifecycle foundations (T0–T2)

Status: source implementation, unqualified. Baseline
`8fa96db378364891e645ed3e22f76218b3412da3` (PR #661).
No test, build, scan, CI remediation, release or device activation was performed
in this implementation session. No production trust roots or signing keys were provisioned.

## T0 — authority and change contracts

The versioned capability inventory describes capabilities, not executable
routes. It references existing domain ownership, including the existing
projection reconciliation operation. Local structured comparison assigns
U0 (locally proven presentation), U1 (unchanged inventory), U2 (restriction),
U3 (optional within locally approved ceiling), U4 (expanded scope), U5
(trust/owner change), or UX (unknown). Unchanged inventory does not prove
arbitrary application or Rego equivalence. Policy/schema change remains
unqualified; actual compatibility admission belongs to T3/T4.

Release commit, artifact digest, policy content, policy contract, registry,
workspace, authority, delegation, root, metadata and recovery revisions are
separate identifiers. An absent independent observation is null, not inferred
from another identifier. The existing OPA source/runtime consistency checks
and PR #661 activation fences retain their ownership and authority.

## T1 — release trust

The existing release worker owns discovery, lease fencing and bounded
subprocesses. Configuring `POCKETLAB_RELEASE_ROOT_SHA256` enables the review
path, not installation. It fetches fixed GitHub release assets (or the
explicit local candidate directory), checks strict bounded JSON, DSSE
Ed25519 thresholds and revocations, expected identity/channel/digests,
independent provenance, expiry and anti-rollback floors. It compares the
candidate inventory with local registry and policy/schema source. Verification
has no extraction or execution side effects. The existing installed identity
remains authoritative for the running PWA, independently of publisher trust.

The publishing workflow retains dist.zip, checksums and release manifest.
It adds capability/policy/migration inventories, signed metadata and GitHub
attestations for both the archive and envelope. Only the protected publishing
job receives signing material; missing configuration fails closed.
See [publishing configuration](trusted-release-publishing.md).

The private state root contains release-trust/root.json and independently
pinned GitHub trusted root bundle github-trusted-root.jsonl. Provision both
fingerprints via protected local configuration; the candidate cannot provision
either. Local-only review uses POCKETLAB_RELEASE_TRUST_SOURCE=local and
release-trust/candidate. The operator clock anchor is boot ID, monotonic
nanoseconds and independently confirmed UTC; it expires after ten minutes
and cannot go backwards against the durable trusted time floor. Root expiry
and metadata expiry are fail-closed. This is an operator trust contract, not
authenticated network time or a complete TUF implementation. Root transitions
require a locally pinned new root and dual independent rotation thresholds.
Compromise of the old rotation threshold or expiry requires out-of-band recovery.

First accepted receipts, current review state and durable floors are separate.
Exact repeat metadata does not replace the first receipt. Automatic checks
can reuse matching historical evidence for up to 24 hours; manual review
reverifies. Cache reuse is not fresh verification. Loss of network or trusted
metadata does not rewrite the installed identity. A configured or durable
pin blocks legacy promotion until T4 supplies qualified trusted promotion.
Unprovisioned workspaces retain the existing legacy path.

## T2 — Owner boundary

SQLite migrations 0056–0060 add independent trust, preferences, boundary,
standing authorization, service delegation and trusted time records.
No existing migration or activation record is rewritten. Default profile is
Notify me. Recommended and Security updates only are preferences, not
execution permission. Enterprise managed is read-only for expanded consent.
Existing release and recovery settings are not migrated into standing consent.

The current Owner may review and record a stable-channel, read-only Risk A
consent for release verification or Safety Rules review. The server constructs
the scope and exact confirmation digest, binds it to the current workspace,
authority versions, policy, trust, registry and expected revisions, and requires
the existing purpose-bound passkey/OPA mechanism. A transaction consumes the
assurance and records the grant, delegation and correlated audit. The current
bounded implementation allows one active grant, lasting 30 days; changing the
boundary revokes prior grants. Scope expansion requires new review. A stale,
revoked, expired, unknown or unsupported record cannot authorize new claims.
The evaluator additionally requires current OPA and runtime evidence; even a
within-boundary result has execution_eligible=false.

The registered service purposes describe existing owner integration points,
not new principals with reusable credentials. No service can broaden its
delegation, manage trust roots, impersonate humans or invoke a human-only
activation API. Migration, maintenance and app execution are not grantable here.
Revocation and Notify narrowing require the current Owner and expected revision
but not a permissive OPA response. Revocation prevents future use; it does not
claim to cancel in-flight work. Future owners must reconcile uncertain outcomes.

## UI and synchronization

System Health Manage contains one Updates & protection destination. It reuses
the current Manage shell, grouped navigation, LiteActionRow, LiteButton,
StateSurface and System Health section/detail classes. Shared haptics and
theme tokens are inherited; no new independent color palette or panel geometry.
The backend provides bounded historical release evidence, impact, preferences,
grant and audit data. Non-Owners get a read-only summary. The review dialog
requires the server-built scope and exact passkey purpose before committing.
No private keys, Owner credentials or authorization facts are persisted in
browser snapshot storage. The existing audit revision stream invalidates
the active lifecycle query; no new polling service is introduced.

## Security model and limitations

| Threat | Control / remaining limitation |
| --- | --- |
| Artifact substitution, spoofed publisher | Digest binding, threshold signature, independent attestation pinned to repository/workflow/source. A signed malicious release is not semantically safe. |
| Replay, downgrade, freeze | Durable metadata/tag/root/time floors, expiry, bounded historical cache. Full TUF timestamp/snapshot roles are not supplied. |
| Stolen release signing key | Rotation role separation, revocation, protected publishing job. Compromised root recovery is independently governed out-of-band. |
| Owner impersonation, stale consent | Current session/role, exact passkey assurance, OPA, revision-fenced transactional scope. |
| Browser or service impersonation | No client keys/actor construction or execution endpoints; current authority is server-derived. |
| Corrupt database or shared Android UID | SQLite transactional safeguards and explicit trust configuration; arbitrary malicious code running as the same UID can undermine local state. Strong isolation or external signer/hardware trust is future work. |

## Future extensions

T3 owns compatible policy proof, active/known-good/observed reconciliation and
fresh authorization. T4 owns coordinated release/schema/checkpoint/rollback
and promotion through existing leases. T5 connects local authority to separately
qualified capabilities. T6 maps existing app/device/identity/safety/recovery
registries. T7 supplies organization restrictions and independent approvals.
Database rollback must preserve intervening user data. None is activated here.

## Authored qualification assets

- `task lite:lifecycle:backend`: synthetic signature, scope, anti-rollback,
  root rotation and isolated revocation fixtures.
- `task lite:lifecycle:ui`: focused Vitest component cases.
- `task lite:lifecycle:mocked`: desktop/mobile Playwright and axe cases,
  including visual specifications. No new approved screenshot baselines.
- Storybook examples cover historical/expired/failed trust, unknown/expanded
  scope, managed restriction, recorded consent and read-only states.

Before any production readiness decision, qualify exact-head forward migrations,
policy and passkey integration, concurrency and revocation, release job with
test-only keys, root transition and replay, provenance verifier/tool availability
on Ubuntu/WSL2 and Android ARM64, existing release and recovery regression,
offline/resource behavior and accessible responsive UI. Use existing task
and evidence tools; no server phone or live publisher modification is needed
for source implementation. Qualification coverage is focused, not exhaustive.
