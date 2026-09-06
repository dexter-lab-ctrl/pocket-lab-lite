#!/usr/bin/env python3
"""Render promoted-release documentation experiences without network access.

The tracked platform catalog remains source-generated and deterministic. This MkDocs hook
adds richer human-facing release projections from the same committed promoted evidence.
It never polls GitHub, reads transient captures, or infers a release identity.
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PROMOTED = ROOT / "contracts/generated/releases/promoted-release-evidence.json"
INVENTORY_TARGET = "generated/development/release-inventory.md"
RELEASE_HUB_TARGET = "generated/enterprise/hubs/release-change.md"
REQUIRED_ASSETS = ("dist.zip", "checksums.txt", "pocketlab-lite-release.json")


def _escape(value: Any) -> str:
    return html.escape(str(value if value is not None else "unobserved"), quote=True)


def _short_sha(value: Any) -> str:
    text = str(value or "unobserved")
    return text[:12] if len(text) >= 12 else text


def _human_bytes(value: Any) -> str:
    try:
        size = int(value)
    except (TypeError, ValueError):
        return "unobserved"
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return "unobserved"


def _load_releases() -> list[dict[str, Any]]:
    if not PROMOTED.exists():
        return []
    payload = json.loads(PROMOTED.read_text(encoding="utf-8"))
    releases = payload.get("releases")
    if not isinstance(releases, list):
        raise ValueError("promoted release evidence must contain a releases list")
    clean: list[dict[str, Any]] = []
    for row in releases:
        if not isinstance(row, dict):
            raise ValueError("promoted release evidence contains a non-object release row")
        tag = str(row.get("release_tag") or "")
        if not tag.startswith("lite-"):
            raise ValueError("promoted release evidence contains an invalid release tag")
        if row.get("verification_status") != "promoted" or row.get("sanitized") is not True:
            raise ValueError(f"release {tag} is not promoted sanitized evidence")
        clean.append(row)
    return sorted(
        clean,
        key=lambda item: (str(item.get("published_at") or ""), str(item.get("release_tag") or "")),
        reverse=True,
    )


def _artifact_rows(release: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    rows = [row for row in release.get("artifacts", []) if isinstance(row, dict)]
    by_name = {str(row.get("name") or ""): row for row in rows}
    ordered = [by_name[name] for name in REQUIRED_ASSETS if name in by_name]
    verified = len(ordered) == len(REQUIRED_ASSETS) and all(
        row.get("status") == "verified" and row.get("github_asset_presence") == "verified"
        for row in ordered
    )
    return ordered, verified


def _release_card(release: dict[str, Any], *, latest: bool) -> str:
    tag = _escape(release.get("release_tag"))
    artifacts, verified = _artifact_rows(release)
    dist = next((row for row in artifacts if row.get("name") == "dist.zip"), {})
    status_label = "Latest promoted" if latest else "Promoted"
    status_class = "pl-status--verified" if verified else "pl-status--unvalidated"
    published = _escape(str(release.get("published_at") or "unobserved").replace("T", " ").replace("Z", " UTC"))
    source_commit = _escape(_short_sha(release.get("source_commit")))
    tree_hash = _escape(_short_sha(release.get("tree_hash")))
    dist_size = _escape(_human_bytes(dist.get("bytes")))
    binding = release.get("manifest_binding") if isinstance(release.get("manifest_binding"), dict) else {}
    binding_status = _escape(binding.get("status") or "unobserved")

    rows = []
    for artifact in artifacts:
        digest = _escape(artifact.get("sha256"))
        rows.append(
            "<tr>"
            f"<th scope=\"row\"><code>{_escape(artifact.get('name'))}</code></th>"
            f"<td>{_escape(_human_bytes(artifact.get('bytes')))}</td>"
            f"<td><span class=\"pl-status pl-status--verified\">{_escape(artifact.get('status'))}</span></td>"
            f"<td><code>{digest}</code></td>"
            "</tr>"
        )
    artifact_table = (
        '<div class="pl-table-wrap" data-pl-scrollable="true" tabindex="0" '
        f'aria-label="Artifact integrity for {tag}"><table><thead><tr>'
        '<th>Artifact</th><th>Size</th><th>Status</th><th>SHA-256</th>'
        '</tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>"
    )

    return (
        '<article class="pl-card">'
        '<div class="pl-card-head">'
        '<div><span class="pl-card-kicker">Promoted release</span>'
        f'<h3><code>{tag}</code></h3></div>'
        f'<span class="pl-status {status_class}">{status_label}</span>'
        '</div>'
        '<div class="pl-fact-grid">'
        f'<div class="pl-fact"><span>Published</span><strong>{published}</strong></div>'
        f'<div class="pl-fact"><span>Source commit</span><strong><code>{source_commit}</code></strong></div>'
        f'<div class="pl-fact"><span>Tree</span><strong><code>{tree_hash}</code></strong></div>'
        f'<div class="pl-fact"><span>dist.zip</span><strong>{dist_size}</strong></div>'
        f'<div class="pl-fact"><span>Required assets</span><strong>{len(artifacts)}/{len(REQUIRED_ASSETS)} verified</strong></div>'
        f'<div class="pl-fact"><span>Manifest binding</span><strong>{binding_status}</strong></div>'
        '</div>'
        '<details class="pl-disclosure pl-disclosure--compact">'
        '<summary>Artifact integrity and full digests</summary>'
        f'{artifact_table}'
        '</details>'
        '</article>'
    )


def _render_inventory() -> str:
    releases = _load_releases()
    if not releases:
        return (
            "# Release inventory\n\n"
            '<div class="pl-page-lede"><strong>No promoted release evidence is committed.</strong>'
            '<p>Release identity remains unobserved. This page never invents a tag and never polls GitHub during documentation rendering.</p></div>\n\n'
            "[Open Evidence & Promotion](../../../release/evidence-promotion/) to see the release and promotion contract.\n"
        )

    latest = releases[0]
    all_assets_verified = all(_artifact_rows(row)[1] for row in releases)
    latest_tag = _escape(latest.get("release_tag"))
    verified_assets = sum(len(_artifact_rows(row)[0]) for row in releases)
    expected_assets = len(releases) * len(REQUIRED_ASSETS)
    assurance_status = "Verified" if all_assets_verified else "Needs review"
    assurance_class = "pl-status--verified" if all_assets_verified else "pl-status--unvalidated"

    cards = "".join(
        _release_card(release, latest=index == 0)
        for index, release in enumerate(releases)
    )

    return f"""# Release inventory

<div class="pl-page-lede"><strong>Promoted Pocket Lab Lite releases, from canonical sanitized evidence.</strong><p>This inventory is rendered from <code>contracts/generated/releases/promoted-release-evidence.json</code>. MkDocs performs no GitHub or runtime polling, local working-tree state cannot erase promoted release identity, and missing evidence remains explicit.</p></div>

<div class="pl-page-meta" markdown>
<span class="pl-status {assurance_class}">{assurance_status}</span>
<span class="pl-status pl-status--patch-provided">Explicit promotion only</span>
</div>

<div class="pl-kpi-grid">
<div class="pl-fact"><span>Promoted releases</span><strong>{len(releases)}</strong></div>
<div class="pl-fact"><span>Latest promoted</span><strong><code>{latest_tag}</code></strong></div>
<div class="pl-fact"><span>Artifact evidence</span><strong>{verified_assets}/{expected_assets} required assets</strong></div>
<div class="pl-fact"><span>Promotion rule</span><strong>Append-only per tag</strong></div>
</div>

## Release contract at a glance

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">Identity</span><h3>Tag → commit → tree</h3><p>Promotion records the immutable release tag, source commit, and Git tree together. A different commit cannot reuse an existing release identity.</p></article>
<article class="pl-card"><span class="pl-card-kicker">Artifacts</span><h3>Three required release assets</h3><p><code>dist.zip</code>, <code>checksums.txt</code>, and <code>pocketlab-lite-release.json</code> must be present and integrity-bound.</p></article>
<article class="pl-card"><span class="pl-card-kicker">Integrity</span><h3>Digest verification</h3><p><code>dist.zip</code> is verified against <code>checksums.txt</code>; manifest tag, commit, and artifact digest are also checked before promotion.</p></article>
<article class="pl-card"><span class="pl-card-kicker">Evidence boundary</span><h3>Static, sanitized authority</h3><p>Raw URLs, credentials, secrets, transient downloads, and local runtime observations are not embedded in this inventory.</p></article>
</div>

## Promoted releases

<div class="pl-card-grid">
{cards}
</div>

## Evidence lifecycle

<div class="pl-lineage"><div><strong>GitHub Release</strong><span>tag + required assets</span></div><span aria-hidden="true">→</span><div><strong>Explicit capture</strong><span>transient, sanitized verification</span></div><span aria-hidden="true">→</span><div><strong>Explicit promotion</strong><span>append-only canonical evidence</span></div><span aria-hidden="true">→</span><div><strong>Release inventory</strong><span>offline documentation projection</span></div></div>

## What this inventory proves

- The listed release identities were explicitly captured and promoted from non-draft, non-prerelease GitHub Releases.
- Required asset presence and SHA-256 integrity evidence were verified before promotion.
- Promotion is immutable per release tag; historical promoted evidence is not silently rewritten.
- This inventory does **not** claim live runtime health, current-device installation state, signatures, provenance, or supply-chain posture unless their separate authorities provide that evidence.

## Continue

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">Procedure</span><h3>Evidence & Promotion</h3><p>The exact release qualification, tag allocation, publication, capture, promotion, and regeneration process.</p><a class="pl-intent-link" href="../../../release/evidence-promotion/">Open Evidence & Promotion</a></article>
<article class="pl-card"><span class="pl-card-kicker">Assurance</span><h3>Release Assurance</h3><p>Independent release, runtime, artifact, supply-chain, and evidence-gap authorities.</p><a class="pl-intent-link" href="../../enterprise/engineering/release-evidence/">Open Release Assurance</a></article>
<article class="pl-card"><span class="pl-card-kicker">Journey</span><h3>Release Feature Journey</h3><p>Source-derived relationships across release, rollback, runtime state, controls, and evidence.</p><a class="pl-intent-link" href="../../enterprise/journeys/release/">Open Release Journey</a></article>
<article class="pl-card"><span class="pl-card-kicker">Product</span><h3>Release and dist.zip</h3><p>The production-facing release artifact and deployment contract.</p><a class="pl-intent-link" href="../../production/release/">Open release guide</a></article>
</div>
"""


def _release_hub_addendum() -> str:
    return """

## Release procedure

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">Evidence & Promotion</span><h3>From qualified main to promoted evidence</h3><p>Follow the exact Pocket Lab Lite release gate, dry-run, UTC date-based tag allocation, GitHub Release asset verification, sanitized capture, explicit promotion, offline check, and documentation regeneration process.</p><a class="pl-intent-link" href="../../../../release/evidence-promotion/">Open Evidence & Promotion</a></article>
</div>
"""


def on_page_markdown(markdown: str, *, page: Any, config: Any, files: Any) -> str | None:
    src_uri = getattr(getattr(page, "file", None), "src_uri", None)
    if src_uri == INVENTORY_TARGET:
        releases = _load_releases()
        page.meta["status"] = "verified" if releases else "unvalidated"
        page.meta["description"] = "Promoted Pocket Lab Lite release identities, required artifacts, integrity evidence, and promotion boundaries."
        return _render_inventory()
    if src_uri == RELEASE_HUB_TARGET:
        return markdown.rstrip() + _release_hub_addendum() + "\n"
    return None
