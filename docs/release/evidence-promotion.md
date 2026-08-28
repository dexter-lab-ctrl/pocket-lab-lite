---
title: "Evidence & Promotion"
description: "Exact Pocket Lab Lite release qualification, date-based tag, dist.zip publication, release-evidence capture, explicit promotion, and offline verification process."
status: verified
generated: false
audience: development
page_type: release-procedure
confidence: source-owned
---

# Evidence & Promotion

<div class="pl-page-lede"><strong>From a reviewed `main` commit to an immutable release identity and promoted evidence.</strong><p>Pocket Lab Lite separates qualification, publication, evidence capture, and evidence promotion. A successful build is not automatically promoted evidence, and promoted release evidence does not automatically claim runtime, supply-chain, signature, or provenance health.</p></div>

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Source-owned procedure</span>
<span class="pl-status pl-status--patch-provided">Human-controlled promotion</span>
</div>

<div class="pl-kpi-grid">
<div class="pl-fact"><span>Release workflow</span><strong><code>release-dist.yml</code></strong></div>
<div class="pl-fact"><span>Tag format</span><strong><code>lite-YYYY.MM.DD.N</code></strong></div>
<div class="pl-fact"><span>Required assets</span><strong>3</strong></div>
<div class="pl-fact"><span>Promotion policy</span><strong>Explicit + append-only</strong></div>
</div>

## Release lifecycle

<ol class="pl-journey-stepper" aria-label="Pocket Lab Lite release lifecycle"><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">01</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Qualify</span><p>Run the release gate against an explicitly running isolated Lite stack.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">02</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Dry run</span><p>Build and validate the local <code>dist.zip</code> artifact contract without publishing.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">03</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Publish</span><p>Dispatch the release workflow from <code>main</code> or use a valid pushed Lite tag.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">04</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Verify</span><p>Prove tag → source commit and all three required GitHub Release assets.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">05</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Capture</span><p>Download and verify sanitized release evidence into transient development storage.</p></div></li><li class="pl-journey-step"><span class="pl-journey-marker" aria-hidden="true">06</span><div class="pl-journey-step-content"><span class="pl-journey-stage">Promote</span><p>Append immutable release evidence, validate it offline, then regenerate documentation.</p></div></li></ol>

## 1. Start from a release-ready `main`

Release publication is a human-controlled action. Before creating a release, keep `main` clean, merge reviewed PRs, remove accidental artifacts, and qualify the release candidate.

```bash
cd ~/pocket-lab-lite
git switch main
git fetch origin --prune
git pull --ff-only origin main
git status --short
```

A clean `git status --short` is the expected starting state.

The canonical release gate is:

```bash
LITE_E2E_LIVE=1 task lite:check:release
```

`lite:check:release` requires an explicitly running isolated Caddy/FastAPI/SQLite/NATS/worker/PWA stack. It runs the normal full gate first, then live browser coverage, runtime tests, visual validation, and the release dry-run. Android/Termux validation is opt-in for an explicitly configured test device:

```bash
LITE_E2E_LIVE=1 LITE_ANDROID_GATE=1 task lite:check:release
```

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">Success</span><h3>Release gate completes</h3><p>All recorded release-tier commands succeed and validation evidence is generated under the repo-local development evidence area.</p></article>
<article class="pl-card"><span class="pl-card-kicker">Fail closed</span><h3>No implicit live gate</h3><p>If <code>LITE_E2E_LIVE=1</code> is absent, the release gate exits instead of pretending live qualification occurred.</p></article>
</div>

## 2. Build the artifact contract without publishing

Run the explicit dry-run even when release qualification already exercised it:

```bash
task lite:release:dry-run
```

This invokes:

- `scripts/dev/release-dry-run.sh`
- `scripts/dev/lite/release_artifact_check.py --root .`

The dry-run validates architecture/bootstrap/supply-chain prerequisites, the focused Lite backend contract, and the PWA build. It creates the root release-candidate assets:

```text
dist.zip
checksums.txt
```

A dry-run intentionally has no immutable release tag, so it does **not** create `pocketlab-lite-release.json`.

You can re-check an existing local artifact pair with:

```bash
task lite:release:artifact-check
```

### What success looks like

The artifact checker prints a JSON result with:

```json
{
  "status": "passed",
  "artifact": "dist.zip",
  "sha256": "<verified SHA-256>",
  "entries": 123
}
```

The exact entry count and digest vary by build. The invariant is `status: passed`, a matching checksum, the required `index.html`, `manifest.webmanifest`, and `sw.js`, and no forbidden development/state/secret entries.

## 3. Publish from the repository-owned release workflow

The canonical workflow is:

```text
.github/workflows/release-dist.yml
Build Pocket Lab Lite dist.zip
```

For the normal release path, manually dispatch it **from `main`**. Leave `release_tag` empty to let the workflow allocate the next collision-free UTC date-based tag.

Tag format:

```text
lite-YYYY.MM.DD.N
```

Example shape:

```text
lite-2026.08.28.1
```

The workflow scans both remote tags and existing GitHub Releases with the current UTC date prefix and increments the sequence until it finds an unused identity. The sequence must be a positive integer and the workflow validates the calendar date.

A GitHub CLI equivalent to the workflow-dispatch inputs is:

```bash
gh workflow run release-dist.yml \
  --repo dexter-lab-ctrl/pocket-lab-lite \
  --ref main
```

To request a reviewed explicit tag rather than automatic allocation:

```bash
gh workflow run release-dist.yml \
  --repo dexter-lab-ctrl/pocket-lab-lite \
  --ref main \
  -f release_tag=lite-YYYY.MM.DD.N
```

The workflow refuses a manual dispatch from a non-`main` ref and refuses a source SHA that does not exactly match `origin/main`.

### Annotated-tag path

A pushed tag matching the Lite tag pattern also triggers the workflow. The workflow verifies that the tag resolves to its exact `GITHUB_SHA`. When the workflow needs to create a tag itself, it creates an **annotated** tag with message:

```text
Pocket Lab Lite <release-tag>
```

and pushes that tag before creating the GitHub Release.

## 4. What the release workflow produces and verifies

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">Build identity</span><h3><code>pocketlab-lite-build.json</code></h3><p>Embedded inside the PWA build with product, release/source-build identity, exact source commit, target, and UTC creation time.</p></article>
<article class="pl-card"><span class="pl-card-kicker">Release artifact</span><h3><code>dist.zip</code></h3><p>The packaged PWA. Development documentation, transient validation state, databases, private keys, HARs, and similar forbidden content are rejected by the artifact checker.</p></article>
<article class="pl-card"><span class="pl-card-kicker">Integrity</span><h3><code>checksums.txt</code></h3><p>Contains the SHA-256 used to verify the exact <code>dist.zip</code> published by the workflow.</p></article>
<article class="pl-card"><span class="pl-card-kicker">Release binding</span><h3><code>pocketlab-lite-release.json</code></h3><p>For a release-tagged build, binds product, release tag, source commit, artifact digest, target, and minimum runtime contract.</p></article>
</div>

The published GitHub Release must contain exactly the required release contract assets:

| Required asset | Purpose | Publication invariant |
| --- | --- | --- |
| `dist.zip` | Installable Lite PWA artifact | SHA-256 validated before upload |
| `checksums.txt` | Artifact integrity | Must verify the published `dist.zip` |
| `pocketlab-lite-release.json` | Release identity/binding | Tag, source commit and artifact digest must agree |

The final workflow step verifies that:

1. the tag resolves to the workflow's exact source commit;
2. the GitHub Release exists;
3. all three required assets are present.

Success ends with:

```text
PASS release identity and required assets verified for <release-tag>
```

## 5. Existing-release repair is explicit and bounded

Normal publication refuses to overwrite an existing GitHub Release.

`repair_existing_release=true` is accepted only for an explicit manual workflow dispatch and only when the existing release tag resolves to the **same exact source commit**. Repair mode may replace the three release assets; it does not authorize retagging a different commit under an existing release identity.

Use repair mode only to repair the artifact set for the same immutable release identity.

## 6. Capture release evidence after publication

Release publication and release-evidence promotion are deliberately separate operations.

On WSL2/Ubuntu/CI with authenticated GitHub CLI access:

```bash
task lite:docs:release-assurance:capture \
  TAG=<release-tag> \
  REPO=dexter-lab-ctrl/pocket-lab-lite
```

The capture command:

- requires a non-draft, non-prerelease GitHub Release;
- requires `dist.zip`, `checksums.txt`, and `pocketlab-lite-release.json`;
- resolves the release tag to a 40-hex commit and tree;
- downloads the required assets into transient `.pocketlab-dev` storage;
- verifies `dist.zip` against `checksums.txt`;
- verifies manifest tag and source commit binding;
- verifies GitHub asset digests where GitHub provides them;
- emits only sanitized release identity/artifact evidence.

Success looks like:

```text
PASS captured sanitized release evidence: .pocketlab-dev/release-evidence/<release-tag>/capture.json
```

This command is intentionally rejected on Android/Termux so the Server Phone remains lightweight.

## 7. Promote only reviewed capture evidence

After inspecting the capture, promote it explicitly:

```bash
task lite:docs:release-assurance:promote TAG=<release-tag>
```

The task supplies the required explicit promotion guard and the promotion script writes to:

```text
contracts/generated/releases/promoted-release-evidence.json
```

Promotion is:

- explicit;
- sanitized;
- atomic;
- append-only;
- immutable per release tag.

The same promotion also materializes a deterministic release-manifest snapshot under:

```text
contracts/generated/releases/manifests/<release-tag>/pocketlab-lite-release.json
```

That snapshot gives the source-derived Release Inventory generator a stable, no-network manifest authority without duplicating raw GitHub data or transient capture files.

If the tag is already promoted with identical evidence, promotion is idempotent. If historical evidence or its manifest snapshot differs, the command fails instead of silently rewriting release history.

Success looks like:

```text
PASS promoted release evidence: contracts/generated/releases/promoted-release-evidence.json
PASS release manifest snapshot: contracts/generated/releases/manifests/<release-tag>/pocketlab-lite-release.json
```

## 8. Validate promoted evidence offline

Run:

```bash
task lite:docs:release-assurance:check
```

This performs no GitHub polling. It validates promoted release rows, duplicate-tag exclusion, required artifact evidence, and deterministic manifest-snapshot parity.

Success looks like:

```text
PASS promoted release evidence validated: <N> release(s)
PASS immutable release manifest snapshots validated: <N> release(s)
```

## 9. Regenerate release knowledge and documentation

After evidence promotion, regenerate the repository-owned documentation projections:

```bash
task lite:docs:generate
task lite:docs:check
git diff --check
```

`lite:docs:generate` runs the platform catalog before runtime, parity, health, architecture, Knowledge, Documentation Intelligence, Development/Production, Enterprise, SchemaSpy, diagram, and final Codebase Map projections. This ordering keeps release inventory, release knowledge, assurance, cross-links, and structural fingerprints deterministic.

The Release Inventory then consumes the immutable manifest snapshots while its rendered enterprise experience uses the canonical promoted evidence directly. Neither path polls GitHub during MkDocs generation.

## Evidence authorities stay independent

Promoting a release is not the same as promoting runtime or supply-chain evidence.

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">Release authority</span><h3>GitHub Release evidence</h3><p><code>task lite:docs:release-assurance:capture</code> → explicit promote → offline check. Proves release identity and required artifact integrity.</p></article>
<article class="pl-card"><span class="pl-card-kicker">Runtime authority</span><h3>Server Phone runtime evidence</h3><p><code>lite:runtime:termux:capture</code>, inspect, validate and diff remain separate. Promotion requires the explicit <code>LITE_RUNTIME_PROMOTE=1</code> guard.</p></article>
<article class="pl-card"><span class="pl-card-kicker">Supply chain</span><h3>Scanner/SBOM evidence</h3><p><code>lite:docs:supply-chain:capture</code> produces transient diagnostic evidence; reviewed evidence is promoted separately with <code>lite:docs:supply-chain:promote</code>.</p></article>
<article class="pl-card"><span class="pl-card-kicker">Signatures & provenance</span><h3>No automatic claim</h3><p>Signature and provenance dimensions remain unobserved unless their dedicated verification/promotion paths produce canonical evidence.</p></article>
</div>

### Runtime evidence sequence

```bash
task lite:runtime:termux:capture
task lite:runtime:termux:inspect
task lite:runtime:termux:validate
task lite:runtime:termux:diff
LITE_RUNTIME_PROMOTE=1 task lite:runtime:termux:promote
```

### Supply-chain evidence sequence

```bash
task lite:docs:supply-chain:capture
# Review the reported RUN_DIR before promotion.
task lite:docs:supply-chain:promote RUN_DIR=.pocketlab-dev/documentation-security/runs/<run>
task lite:docs:supply-chain:check
```

These authorities can later be reconciled by Release Assurance, but one authority never silently substitutes for another.

## Failure matrix

| Failure | Meaning | Safe next action |
| --- | --- | --- |
| Release gate requires `LITE_E2E_LIVE=1` | Live release qualification was not explicitly enabled | Start/verify the isolated Lite stack, then rerun with the guard |
| `dist.zip` or `checksums.txt` missing | Local artifact contract was not built | Run `task lite:release:dry-run` |
| Checksum mismatch | Artifact bytes differ from the recorded checksum | Rebuild; do not publish or promote the mismatched artifact |
| Manual release source is not `origin/main` | Dispatch does not identify the current reviewed `main` | Update `main`, then dispatch with `--ref main` |
| Release tag already exists at another commit | Immutable release identity collision | Allocate a new valid date-based tag; never move the old identity |
| Existing GitHub Release without repair mode | Workflow refuses silent asset replacement | Use a new release, or explicit same-commit repair when justified |
| Capture missing a required asset | Published release is incomplete | Repair the same-commit release asset set before evidence capture |
| Historical promoted evidence differs | Append-only evidence contract detected a rewrite | Stop and investigate; do not force or delete historical evidence |
| Manifest snapshot drift | Release inventory projection no longer matches promoted authority | Regenerate from reviewed promoted evidence; never hand-edit the snapshot |

## What success means end to end

<div class="pl-lineage"><div><strong>Reviewed main</strong><span>release gate passes</span></div><span aria-hidden="true">→</span><div><strong>Validated artifact</strong><span>dist.zip + checksum contract</span></div><span aria-hidden="true">→</span><div><strong>Annotated Lite tag</strong><span>tag resolves to exact source commit</span></div><span aria-hidden="true">→</span><div><strong>GitHub Release</strong><span>three required assets verified</span></div><span aria-hidden="true">→</span><div><strong>Promoted evidence</strong><span>sanitized, append-only, offline-checkable</span></div></div>

A release is not considered documented merely because a tag exists. The complete Pocket Lab Lite release identity is the reviewed source commit, valid Lite tag, verified artifact set, release manifest binding, and explicitly promoted evidence—while runtime, supply-chain, signature, and provenance claims remain independently evidenced.

## Related pages

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">Inventory</span><h3>Release Inventory</h3><p>Promoted release identities and artifact integrity evidence.</p><a class="pl-intent-link" href="../../generated/development/release-inventory/">Open Release Inventory</a></article>
<article class="pl-card"><span class="pl-card-kicker">Assurance</span><h3>Release Assurance</h3><p>Independent release, runtime, supply-chain, health, parity, signature, and evidence-gap authorities.</p><a class="pl-intent-link" href="../../generated/enterprise/engineering/release-evidence/">Open Release Assurance</a></article>
<article class="pl-card"><span class="pl-card-kicker">Journey</span><h3>Release Feature Journey</h3><p>Architecture, execution, controls, evidence, and rollback relationships.</p><a class="pl-intent-link" href="../../generated/enterprise/journeys/release/">Open Release Journey</a></article>
<article class="pl-card"><span class="pl-card-kicker">Runtime</span><h3>Upgrade & release verification</h3><p>Production-facing installed-release and update verification guidance.</p><a class="pl-intent-link" href="../../generated/production/upgrade/">Open upgrade guidance</a></article>
</div>

## Canonical source ownership

This page is maintained against the repository-owned contracts below. If they change, update this procedure and its regression tests in the same PR.

- `tasks/Taskfile.lite.yml` — release qualification gate.
- `tasks/Taskfile.release.yml` — dry-run and artifact-check tasks.
- `scripts/dev/lite/run-gate.sh` — release-tier validation sequence and explicit live/Android guards.
- `scripts/dev/release-dry-run.sh` — local artifact construction and pre-publication checks.
- `scripts/dev/lite/release_artifact_check.py` — required-file, checksum, forbidden-content, and optional release-manifest validation.
- `.github/workflows/release-dist.yml` — source identity, UTC date-based tag allocation, annotated tag creation, artifact build/upload, repair guard, and final publication verification.
- `scripts/docs/enterprise/release_evidence_promotion.py` — explicit GitHub Release capture, sanitized promotion, immutability, and manifest snapshot projection.
- `contracts/generated/releases/promoted-release-evidence.json` — canonical promoted release authority.
- `engineering/chatgpt/maintenance-release.md` — human-controlled release/readiness discipline.
