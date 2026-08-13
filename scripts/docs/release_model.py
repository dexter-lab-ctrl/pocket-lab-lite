#!/usr/bin/env python3
"""Shared release identity, assurance, and impact semantics for Documentation Platform.

This module is intentionally read-only. It consumes repository source plus canonical/promoted
release/runtime/security evidence. It never polls GitHub, captures runtime, promotes evidence,
or runs scanners. Explicit capture/promotion is implemented separately.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

EVIDENCE_STATUSES = {
    "verified", "observed", "promoted", "derived", "unobserved",
    "not-applicable", "stale", "invalid",
}
CONFIDENCE_LEVELS = {
    "release-promoted", "runtime-promoted", "canonical-source",
    "source-derived", "local-observation", "unvalidated",
}
VERIFIED_RELEASE_STATES = {"verified", "release-verified", "promoted", "qualified", "validated"}
REQUIRED_RELEASE_ASSETS = ("dist.zip", "checksums.txt", "pocketlab-lite-release.json")
PROMOTED_RELEASE_EVIDENCE = Path("contracts/generated/releases/promoted-release-evidence.json")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, separators=(",", ": ")) + "\n"


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def git_maybe(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def _release_record(item: dict[str, Any], *, source: str) -> dict[str, Any] | None:
    state = str(item.get("verification_status") or item.get("validation_state") or item.get("status") or "").lower()
    if state not in VERIFIED_RELEASE_STATES:
        return None
    tag = str(item.get("release_tag") or item.get("tag") or item.get("name") or "").strip()
    if not re.fullmatch(r"lite-[A-Za-z0-9._-]+", tag):
        return None
    commit = str(item.get("source_commit") or item.get("commit") or "").strip()
    tree = str(item.get("tree_hash") or item.get("tree") or "").strip()
    if commit and not re.fullmatch(r"[a-f0-9]{40}", commit):
        return None
    if tree and not re.fullmatch(r"[a-f0-9]{40}", tree):
        return None
    return {**item, "tag": tag, "commit": commit or None, "tree": tree or None, "verification_status": state, "canonical_source": source}


def canonical_release_records(root: Path) -> list[dict[str, Any]]:
    """Return verified/promoted release records without mutating or inventing history.

    Records may come from the existing release inventory or explicit promoted GitHub-release
    evidence. Duplicate tags must agree on commit/tree; conflicts fail closed by exclusion.
    """
    candidates: list[dict[str, Any]] = []
    index = read_json(root / "contracts/generated/releases/index.json", {}) or {}
    inventory = index.get("release_inventory") if isinstance(index, dict) else {}
    raw_inventory = inventory.get("releases", []) if isinstance(inventory, dict) else []
    for item in raw_inventory if isinstance(raw_inventory, list) else []:
        if isinstance(item, dict):
            record = _release_record(item, source="contracts/generated/releases/index.json")
            if record:
                candidates.append(record)

    promoted = read_json(root / PROMOTED_RELEASE_EVIDENCE, {}) or {}
    for item in promoted.get("releases", []) if isinstance(promoted, dict) else []:
        if isinstance(item, dict):
            record = _release_record(item, source=str(PROMOTED_RELEASE_EVIDENCE))
            if record:
                candidates.append(record)

    by_tag: dict[str, list[dict[str, Any]]] = {}
    for record in candidates:
        by_tag.setdefault(record["tag"], []).append(record)

    resolved: list[dict[str, Any]] = []
    for tag, rows in sorted(by_tag.items()):
        commits = {x.get("commit") for x in rows if x.get("commit")}
        trees = {x.get("tree") for x in rows if x.get("tree")}
        if len(commits) > 1 or len(trees) > 1:
            continue
        merged = dict(rows[-1])
        merged["commit"] = next(iter(commits), merged.get("commit"))
        merged["tree"] = next(iter(trees), merged.get("tree"))
        merged["canonical_sources"] = sorted({x["canonical_source"] for x in rows})
        local_commit = git_maybe(root, "rev-list", "-n", "1", tag)
        local_tree = git_maybe(root, "rev-parse", f"{tag}^{{tree}}")
        merged["local_tag_available"] = bool(local_commit and local_tree)
        merged["local_tag_matches"] = bool(
            local_commit and local_tree
            and (not merged.get("commit") or merged["commit"] == local_commit)
            and (not merged.get("tree") or merged["tree"] == local_tree)
        )
        if local_commit and not merged.get("commit"):
            merged["commit"] = local_commit
        if local_tree and not merged.get("tree"):
            merged["tree"] = local_tree
        resolved.append(merged)
    return resolved


def verified_release_pair(root: Path) -> dict[str, Any]:
    """Select release authority independently from local Git history.

    One promoted/verified release is sufficient to establish the initial canonical baseline.
    Two releases become comparable only when both matching tags are available locally, because
    the deterministic delta engine reads historical files from Git rather than polling GitHub.
    """
    records = [x for x in canonical_release_records(root) if x.get("commit") and x.get("tree")]
    for row in records:
        row["tagged_at"] = (
            git_maybe(root, "log", "-1", "--format=%cI", row["tag"])
            or str(row.get("published_at") or row.get("observed_at") or "unobserved")
        )
    records.sort(key=lambda x: (x["tagged_at"], x["tag"]))
    if not records:
        return {"comparison_state": "no-canonical-release", "baseline": None, "current": None, "eligible_releases": []}
    if len(records) == 1:
        return {"comparison_state": "baseline-only", "baseline": None, "current": records[-1], "eligible_releases": records}
    baseline, current = records[-2], records[-1]
    if baseline.get("local_tag_matches") and current.get("local_tag_matches"):
        return {"comparison_state": "comparable", "baseline": baseline, "current": current, "eligible_releases": records}
    return {
        "comparison_state": "comparison-evidence-unavailable",
        "baseline": baseline,
        "current": current,
        "eligible_releases": records,
        "reason": "two verified releases exist, but matching local Git tags are required for deterministic historical reads",
    }


def comparison_state(root: Path) -> dict[str, Any]:
    pair = verified_release_pair(root)
    return {
        **pair,
        "candidate_count": len(pair["eligible_releases"]),
        "baseline_policy": "two verified canonical release records + matching reachable Git tag/commit/tree; release-to-HEAD comparison is forbidden",
    }


def evidence_item(*, status: str, authority: str, confidence: str, source: str, observed_at: Any = None, freshness: str = "current", sanitized: bool = True, value: Any = None) -> dict[str, Any]:
    if status not in EVIDENCE_STATUSES:
        raise ValueError(f"unsupported evidence status: {status}")
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"unsupported confidence: {confidence}")
    return {
        "status": status,
        "authority": authority,
        "confidence": confidence,
        "source": source,
        "observed_at": observed_at or "unobserved",
        "freshness": freshness,
        "sanitized": bool(sanitized),
        "value": value,
    }


def promoted_release_for_runtime(root: Path, runtime: dict[str, Any]) -> dict[str, Any] | None:
    wanted = str(runtime.get("release_tag") or runtime.get("release") or "").strip()
    records = canonical_release_records(root)
    if wanted:
        return next((x for x in records if x.get("tag") == wanted), None)
    return records[-1] if records else None


def build_artifact_evidence(root: Path, release_record: dict[str, Any] | None) -> dict[str, Any]:
    promoted_assets = {}
    if release_record:
        for item in release_record.get("artifacts", []) or []:
            if isinstance(item, dict) and item.get("name"):
                promoted_assets[str(item["name"])] = item
    mapping = {"dist.zip": "dist.zip", "checksums.txt": "checksums.txt", "release_manifest": "pocketlab-lite-release.json"}
    out: dict[str, Any] = {}
    for key, filename in mapping.items():
        local = root / filename
        promoted = promoted_assets.get(filename)
        release_presence = evidence_item(
            status="verified" if promoted else "unobserved",
            authority="github-release-promoted",
            confidence="release-promoted" if promoted else "unvalidated",
            source=release_record.get("canonical_source") if promoted and release_record else str(PROMOTED_RELEASE_EVIDENCE),
            observed_at=(release_record or {}).get("observed_at"),
            value=filename if promoted else None,
        )
        expected_sha = str((promoted or {}).get("sha256") or "").strip() or None
        integrity = evidence_item(
            status="verified" if promoted and expected_sha else "unobserved",
            authority="release-artifact-integrity",
            confidence="release-promoted" if promoted and expected_sha else "unvalidated",
            source=release_record.get("canonical_source") if promoted and release_record else str(PROMOTED_RELEASE_EVIDENCE),
            observed_at=(release_record or {}).get("observed_at"),
            value={
                "sha256": expected_sha,
                "verification": (promoted or {}).get("verification"),
                "github_digest_status": (promoted or {}).get("github_digest_status", "unobserved"),
            } if expected_sha else None,
        )
        local_sha = sha256_file(local)
        local_staging = evidence_item(
            status="observed" if local_sha else "unobserved",
            authority="local-repository",
            confidence="local-observation" if local_sha else "unvalidated",
            source=filename,
            value={"sha256": local_sha, "bytes": local.stat().st_size if local.exists() else None},
        )
        binding = evidence_item(
            status="verified" if promoted and release_record and release_record.get("commit") else "unobserved",
            authority="release-manifest",
            confidence="release-promoted" if promoted else "unvalidated",
            source=release_record.get("canonical_source") if release_record else str(PROMOTED_RELEASE_EVIDENCE),
            observed_at=(release_record or {}).get("observed_at"),
            value={"release_tag": (release_record or {}).get("tag"), "source_commit": (release_record or {}).get("commit")},
        )
        out[key] = {
            "filename": filename,
            "release_presence": release_presence,
            "integrity": integrity,
            "binding": binding,
            "local_staging": local_staging,
        }
    return out


def active_limitations(limitations: dict[str, Any], op_domains: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in limitations.get("items", []) if isinstance(limitations, dict) else []:
        if not isinstance(item, dict):
            continue
        domain = str(item.get("id") or "")
        state = op_domains.get(domain, {}) if isinstance(op_domains, dict) else {}
        for category in ("accepted_limitations", "known_gaps", "unsupported_operations"):
            for text in item.get(category, []) or []:
                rows.append({
                    "domain": domain,
                    "label": item.get("label") or domain,
                    "category": category,
                    "description": str(text),
                    "implementation_status": state.get("implementation_status", "unvalidated"),
                    "operational_health": state.get("operational_health", "unvalidated"),
                    "source": "contracts/generated/parity/accepted-limitations.json",
                })
    return rows


def material_findings(op_domains: dict[str, Any], parity_rows: list[dict[str, Any]], *, comparison: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "informational": 3}
    for row in parity_rows:
        domain = str(row.get("id") or "unknown")
        label = str(row.get("label") or domain.title())
        for mismatch in row.get("mismatches", []) or []:
            if not isinstance(mismatch, dict) or mismatch.get("accepted_limitation"):
                continue
            raw = str(mismatch.get("severity") or "high").lower()
            severity = "critical" if raw == "critical" else "high" if raw == "high" else "medium"
            findings.append({
                "id": f"parity:{domain}:{mismatch.get('id','mismatch')}:{mismatch.get('project','all')}",
                "domain": domain, "label": label, "severity": severity, "category": "semantic-parity",
                "summary": f"{mismatch.get('id','Runtime parity mismatch')} on {mismatch.get('project','current projection')}",
                "detail": mismatch.get("explanation") or "Required runtime parity comparison does not match.",
                "evidence": ["contracts/generated/parity/runtime-drift.json"], "confidence": "runtime-promoted",
            })
    for domain, state in sorted(op_domains.items()):
        if not isinstance(state, dict):
            continue
        health = str(state.get("operational_health") or "unvalidated")
        label = str(state.get("label") or domain.replace("-", " ").title())
        if health in {"degraded", "unavailable"}:
            severity = "medium" if health == "degraded" else "high"
            findings.append({
                "id": f"health:{domain}:{health}", "domain": domain, "label": label,
                "severity": severity, "category": "operational-health",
                "summary": f"{label} operational health is {health}.",
                "detail": str(state.get("reason") or "Current promoted operational-health evidence requires review."),
                "evidence": ["contracts/generated/runtime/domain-operational-health.json"], "confidence": "runtime-promoted",
            })
        if state.get("freshness") == "stale":
            findings.append({
                "id": f"freshness:{domain}:stale", "domain": domain, "label": label,
                "severity": "medium", "category": "evidence-freshness",
                "summary": f"{label} promoted evidence is stale.",
                "detail": str(state.get("reason") or "Promoted evidence exceeded its freshness threshold."),
                "evidence": ["contracts/generated/runtime/domain-operational-health.json"], "confidence": "runtime-promoted",
            })
        if str(state.get("implementation_status") or "") == "partial":
            findings.append({
                "id": f"implementation:{domain}:partial", "domain": domain, "label": label,
                "severity": "informational", "category": "implementation",
                "summary": f"{label} implementation remains partial.",
                "detail": "Canonical implementation status is partial; no stronger claim is made.",
                "evidence": ["contracts/generated/runtime/domain-operational-health.json"], "confidence": "canonical-source",
            })
    if comparison == "baseline-only":
        findings.append({
            "id": "release:baseline-only", "domain": "release", "label": "Release",
            "severity": "informational", "category": "historical-comparison",
            "summary": "Initial canonical comparison baseline established.",
            "detail": "Historical release-to-release deltas remain unavailable until a second qualified release is promoted.",
            "evidence": [str(PROMOTED_RELEASE_EVIDENCE), "contracts/generated/releases/index.json"], "confidence": "release-promoted",
        })
    return sorted(findings, key=lambda x: (severity_rank.get(x["severity"], 9), x["label"], x["id"]))


def business_dimension_status(classification: str, *, comparison: str) -> str:
    if comparison == "baseline-only":
        return "Baseline established" if classification in {"not-comparable", "unchanged"} else "Verified current state"
    if comparison != "comparable":
        return "Current state available" if classification in {"not-comparable", "unchanged"} else "Verified current state"
    mapping = {
        "unchanged": "Unchanged", "added": "Added", "removed": "Removed", "changed": "Changed",
        "breaking": "Breaking change", "non-breaking": "Non-breaking change", "improved": "Improved",
        "degraded": "Degraded", "newly-observed": "Newly observed", "no-longer-observed": "No longer observed",
        "new-vulnerability": "New vulnerability", "resolved-vulnerability": "Resolved vulnerability",
        "new-license": "New license", "dependency-added": "Dependency added", "dependency-removed": "Dependency removed",
        "dependency-updated": "Dependency updated", "architecture-drift": "Architecture changed", "not-comparable": "Prior snapshot unavailable",
    }
    return mapping.get(classification, classification.replace("-", " ").title())


def release_impact_brief(root: Path, delta: dict[str, Any], op_domains: dict[str, Any], parity_rows: list[dict[str, Any]], capability_rows: list[dict[str, Any]]) -> dict[str, Any]:
    pair = comparison_state(root)
    state = pair["comparison_state"]
    if state == "no-canonical-release":
        comparison = "no-canonical-release"
    else:
        comparison = state
    health_counts = dict(sorted(Counter(str(x.get("operational_health") or "unvalidated") for x in op_domains.values() if isinstance(x, dict)).items()))
    parity_counts = dict(sorted(Counter(str(x.get("runtime_status") or "unvalidated") for x in parity_rows).items()))
    capability_counts = dict(sorted(Counter(str(x.get("status") or "unvalidated") for x in capability_rows).items()))
    dimensions = []
    for row in delta.get("dimensions", []) or []:
        cls = str(row.get("classification") or "not-comparable")
        dimensions.append({
            **row,
            "current_status": business_dimension_status(cls, comparison=comparison),
            "historical_comparison": "Available" if comparison == "comparable" and cls != "not-comparable" else "Awaiting prior baseline" if comparison == "baseline-only" else "Local comparison evidence unavailable" if comparison == "comparison-evidence-unavailable" else "Unavailable",
            "confidence": "High" if cls != "not-comparable" or comparison == "baseline-only" else "Medium",
            "technical_status": row.get("status") or ("comparable" if comparison == "comparable" else "not-comparable"),
        })
    findings = material_findings(op_domains, parity_rows, comparison=comparison)
    unchanged = [x["dimension"] for x in dimensions if x.get("classification") == "unchanged"] if comparison == "comparable" else []
    current_release = pair.get("current") or {}
    delta_to = delta.get("to") if isinstance(delta.get("to"), dict) else {}
    release_tag = current_release.get("tag") or delta.get("to_release") or delta_to.get("tag")
    source_commit = current_release.get("commit") or delta.get("source_commit") or delta_to.get("commit")
    baseline = pair.get("baseline") or {}
    return {
        "status": "release-impact-ready",
        "comparison_state": comparison,
        "comparison_label": "Initial canonical comparison baseline" if comparison == "baseline-only" else "Verified release-to-release comparison" if comparison == "comparable" else "Verified releases awaiting local comparison history" if comparison == "comparison-evidence-unavailable" else "Canonical release evidence not yet promoted",
        "current_release": current_release,
        "comparison_release": pair.get("baseline"),
        # Compatibility aliases remain read-only projections; comparison policy is owned by comparison_state().
        "release": release_tag,
        "to_release": release_tag,
        "from_release": baseline.get("tag"),
        "source_commit": source_commit,
        "current_snapshot": {"operational_health": health_counts, "semantic_parity": parity_counts, "platform_capabilities": capability_counts},
        "dimensions": dimensions,
        "material_findings": findings,
        "requires_attention": [x for x in findings if x["severity"] in {"critical", "high", "medium"}],
        "unchanged": unchanged,
        "technical_delta": delta,
        "baseline_establishment": {
            "active": comparison == "baseline-only",
            "message": "This release establishes the first verified multidimensional release baseline. Historical deltas are intentionally unavailable until another qualified release is promoted." if comparison == "baseline-only" else None,
        },
    }


def release_authorities(root: Path, runtime: dict[str, Any], supply_present: bool, local_source_commit: str, local_tree: str) -> dict[str, Any]:
    release = promoted_release_for_runtime(root, runtime)
    release_verified = bool(release and release.get("commit") and release.get("tree"))
    runtime_tag = runtime.get("release_tag") or runtime.get("release")
    runtime_commit = runtime.get("source_commit")
    runtime_sanitized = runtime.get("sanitized") is True or bool(runtime_tag)
    return {
        "release": evidence_item(status="verified" if release_verified else "unobserved", authority="release", confidence="release-promoted" if release_verified else "unvalidated", source=(release or {}).get("canonical_source") or str(PROMOTED_RELEASE_EVIDENCE), observed_at=(release or {}).get("observed_at"), value={"tag": (release or {}).get("tag"), "commit": (release or {}).get("commit"), "tree": (release or {}).get("tree")}),
        "runtime": evidence_item(status="promoted" if runtime_tag and runtime_commit and runtime_sanitized else "unobserved", authority="runtime", confidence="runtime-promoted" if runtime_tag else "unvalidated", source="contracts/parity/runtime-verification-baseline.json", observed_at=runtime.get("promoted_at"), value={"release_tag": runtime_tag, "source_commit": runtime_commit}),
        "supply_chain": evidence_item(status="promoted" if supply_present else "unobserved", authority="supply-chain", confidence="release-promoted" if supply_present else "unvalidated", source="contracts/generated/supply-chain", value="normalized canonical evidence present" if supply_present else None),
        "local_repository": evidence_item(status="observed", authority="local-repository", confidence="local-observation", source="git/source environment", value={"source_commit": local_source_commit, "tree": local_tree}),
    }


def release_assurance(root: Path, runtime: dict[str, Any], op_domains: dict[str, Any], parity_rows: list[dict[str, Any]], supply_present: bool, artifacts: dict[str, Any], provenance: dict[str, Any], signatures: dict[str, Any], local_source_commit: str, local_tree: str) -> dict[str, Any]:
    authorities = release_authorities(root, runtime, supply_present, local_source_commit, local_tree)
    rel = authorities["release"]
    run = authorities["runtime"]
    release_value = rel.get("value") or {}
    runtime_value = run.get("value") or {}
    runtime_binding = "verified" if rel["status"] == "verified" and run["status"] == "promoted" and release_value.get("tag") == runtime_value.get("release_tag") and (not release_value.get("commit") or release_value.get("commit") == runtime_value.get("source_commit")) else "unobserved" if rel["status"] == "unobserved" else "invalid"
    asset_verified = sum(1 for x in artifacts.values() if x["release_presence"]["status"] == "verified" and x["integrity"]["status"] == "verified")
    artifact_status = "verified" if asset_verified == len(REQUIRED_RELEASE_ASSETS) else "observed" if asset_verified else "unobserved"
    healths = [str(x.get("operational_health") or "unvalidated") for x in op_domains.values() if isinstance(x, dict)]
    health_status = "degraded" if any(x in {"degraded", "unavailable"} for x in healths) else "verified" if healths and all(x == "healthy" for x in healths) else "unobserved"
    parities = [str(x.get("runtime_status") or "unvalidated") for x in parity_rows]
    parity_status = "observed" if any(x in {"needs-review", "partial"} for x in parities) else "verified" if parities and all(x == "verified" for x in parities) else "unobserved"
    prov_status = str(provenance.get("evidence_status") or provenance.get("status") or "unobserved")
    sig_status = str(signatures.get("status") or signatures.get("evidence_status") or "unobserved")
    prov_verified = "verified" if "verified" in prov_status or "promoted" in prov_status else "unobserved"
    sig_verified = "verified" if "verified" in sig_status or "promoted" in sig_status else "unobserved"
    pair = comparison_state(root)
    historical = "verified" if pair["comparison_state"] == "comparable" else "observed" if pair["comparison_state"] == "baseline-only" else "unobserved"
    dimensions = [
        {"id": "source-identity", "status": rel["status"], "evidence": "release tag ↔ commit ↔ tree"},
        {"id": "artifact-integrity", "status": artifact_status, "evidence": f"{asset_verified}/{len(REQUIRED_RELEASE_ASSETS)} promoted release assets have verified digest evidence"},
        {"id": "runtime-binding", "status": runtime_binding, "evidence": "promoted runtime baseline ↔ release authority"},
        {"id": "operational-health", "status": health_status, "evidence": dict(sorted(Counter(healths).items()))},
        {"id": "semantic-parity", "status": parity_status, "evidence": dict(sorted(Counter(parities).items()))},
        {"id": "security-evidence", "status": authorities["supply_chain"]["status"], "evidence": "normalized scanner/security evidence"},
        {"id": "sbom", "status": "verified" if (root / "contracts/generated/supply-chain/sbom-release.cdx.json").exists() else "unobserved", "evidence": "CycloneDX release SBOM"},
        {"id": "provenance", "status": prov_verified, "evidence": prov_status},
        {"id": "signatures", "status": sig_verified, "evidence": sig_status},
        {"id": "migration-evidence", "status": "observed" if any((root / p).exists() for p in ["pocket-lab-final-structure/runtime/api_fastapi/migrations", "pocket-lab-final-structure/runtime/migrations"]) else "unobserved", "evidence": "repository migration inventory"},
        {"id": "historical-delta", "status": historical, "evidence": pair["comparison_state"]},
    ]
    required_good = rel["status"] == "verified" and runtime_binding == "verified"
    has_gaps = any(x["status"] in {"unobserved", "invalid"} for x in dimensions)
    overall = "verified-with-evidence-gaps" if required_good and has_gaps else "verified" if required_good else "partially-evidenced"
    gaps = [{"dimension": x["id"], "status": x["status"], "reason": x["evidence"]} for x in dimensions if x["status"] in {"unobserved", "invalid"}]
    lineage = [
        {"from": "release authority", "to": "runtime baseline", "source": str(PROMOTED_RELEASE_EVIDENCE)},
        {"from": "runtime baseline", "to": "domain operational health", "source": "contracts/parity/runtime-verification-baseline.json"},
        {"from": "domain operational health", "to": "release impact/assurance", "source": "contracts/generated/runtime/domain-operational-health.json"},
        {"from": "release impact/assurance", "to": "MkDocs", "source": "contracts/generated/documentation-enterprise/release-evidence.json"},
    ]
    return {"overall": overall, "authorities": authorities, "dimensions": dimensions, "evidence_gaps": gaps, "lineage": lineage, "comparison_state": pair["comparison_state"]}
