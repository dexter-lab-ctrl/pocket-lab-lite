#!/usr/bin/env python3
"""Deepen the existing enterprise Documentation Platform projections without adding new UX surfaces.

The parent enterprise generator remains the orchestrator. This module only derives richer contracts,
page bodies and deterministic diagrams from repository source, canonical generated contracts and
already-promoted sanitized evidence. It never captures runtime, runs scanners, promotes evidence,
or accesses a remote service.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

DOCS_SCRIPT_ROOT = Path(__file__).resolve().parents[1]
ENTERPRISE_SCRIPT_ROOT = Path(__file__).resolve().parent
for _script_root in (DOCS_SCRIPT_ROOT, ENTERPRISE_SCRIPT_ROOT):
    if str(_script_root) not in sys.path:
        sys.path.insert(0, str(_script_root))

from threat_model_experience import (
    build_security_atlas,
    enrich as enrich_threat_model,
    render_security_atlas_svg,
    render_svg as render_threat_svg,
)
from threat_model_poster import (
    build_security_poster,
    render_security_poster_svg,
    render_threat_model_overview,
    render_threat_model_subpages,
    threat_model_nav,
)

from release_model import (
    active_limitations as shared_active_limitations,
    build_artifact_evidence,
    canonical_release_records as shared_canonical_release_records,
    comparison_state as shared_comparison_state,
    release_assurance as build_release_assurance,
)

STRIDE = ["Spoofing", "Tampering", "Repudiation", "Information Disclosure", "Denial of Service", "Elevation of Privilege"]
BOUNDARIES = [
    ("application-container", "Application-container boundary"),
    ("browser", "Browser trust boundary"),
    ("control-api", "Control API boundary"),
    ("durable-state", "Durable-state boundary"),
    ("external-release", "External release boundary"),
    ("managed-device", "Managed-device boundary"),
    ("messaging-execution", "Messaging and execution boundary"),
    ("server-host", "Server-host boundary"),
    ("private-network", "Private network and Tailnet boundary"),
]
RELEASE_DIMENSIONS = {
    # Source-only roots deliberately exclude enterprise generated outputs so the
    # release-delta engine cannot fingerprint its own result.
    "git-source": [
        "src", "scripts", "tasks", "Taskfile.yml", ".github/workflows",
        "contracts/metadata", "contracts/parity",
        "schemas", "architecture/metadata", "operations", "runbooks",
        "package.json", "package-lock.json", "requirements-dev.txt",
        "requirements-docs.txt", "pocket-lab-final-structure/runtime/requirements.txt",
    ],
    "openapi": ["contracts/generated/lite-openapi.json"],
    "asyncapi-events": ["contracts/generated/lite-asyncapi.json"],
    "sqlite-schema-migrations": ["pocket-lab-final-structure/runtime/api_fastapi/migrations", "pocket-lab-final-structure/runtime/migrations"],
    "architecture": ["architecture/metadata", "scripts/docs/graphviz"],
    "trust-boundaries": ["architecture/metadata/pocket-lab-architecture.json", "scripts/docs/enterprise/enterprise_completion.py"],
    "capabilities": ["contracts/generated/knowledge/capabilities.json", "contracts/generated/device-capabilities.json"],
    "operational-health": ["contracts/generated/runtime/domain-operational-health.json"],
    "runtime-topology": ["contracts/generated/knowledge/runtime-topology.json"],
    "semantic-parity": ["contracts/parity/parity-model.json", "contracts/parity/runtime-verification-baseline.json"],
    "platform-capability-evidence": ["contracts/generated/documentation-intelligence/platform-matrix.json"],
    "reason-codes": ["contracts/generated/reason-codes.json"],
    "task-inventory": ["Taskfile.yml", "tasks"],
    "security-controls": ["security", "scripts/docs/enterprise/enterprise_completion.py"],
    "threat-model": ["scripts/docs/enterprise/enterprise_completion.py", "scripts/docs/check_threat_model.py", "architecture/metadata"],
    "sbom": ["contracts/generated/supply-chain/sbom-dev.cdx.json", "contracts/generated/supply-chain/sbom-release.cdx.json", "contracts/generated/supply-chain/sbom-runtime.cdx.json"],
    "dependency-versions": ["package-lock.json", "requirements-dev.txt", "requirements-docs.txt", "pocket-lab-final-structure/runtime/requirements.txt"],
    "vulnerabilities": ["contracts/generated/supply-chain/vulnerability-correlation.json"],
    "licenses": ["contracts/generated/supply-chain/license-inventory.json"],
    "release-artifacts": [".github/workflows/release-dist.yml", "tasks/Taskfile.release.yml", "scripts/dev/lite/release_artifact_check.py"],
    "documentation-coverage": ["contracts/generated/knowledge/index.json", "mkdocs.yml"],
    "validation-coverage": ["tests", "tasks", "Taskfile.yml"],
}


def stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, separators=(",", ": ")) + "\n"


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()


def git_maybe(root: Path, *args: str) -> str | None:
    try:
        return git(root, *args)
    except Exception:
        return None


def _canonical_release_records(root: Path) -> list[dict[str, Any]]:
    """Compatibility wrapper around the shared canonical release authority."""
    return shared_canonical_release_records(root)


def current_release_baseline(root: Path) -> dict[str, Any]:
    """Compatibility projection for callers that need baseline readiness.

    Release comparison is now release-to-release only. A single qualified release establishes
    the baseline but never authorizes a release-to-HEAD historical delta.
    """
    state = shared_comparison_state(root)
    selected_baseline = state.get("baseline") if state.get("comparison_state") == "comparable" else None
    return {
        "head": git_maybe(root, "rev-parse", "HEAD") or "unavailable",
        "head_tree": git_maybe(root, "rev-parse", "HEAD^{tree}"),
        "baseline": selected_baseline,
        "current": state.get("current"),
        "comparison_state": state.get("comparison_state"),
        "candidate_count": state.get("candidate_count", 0),
        "baseline_policy": state.get("baseline_policy"),
    }

def ref_paths_digest(root: Path, ref: str, paths: Iterable[str]) -> tuple[str | None, int]:
    records: list[str] = []
    count = 0
    for raw in paths:
        path = raw.strip("/")
        if path == ".":
            continue
        listing = git_maybe(root, "ls-tree", "-r", ref, "--", path) or ""
        for line in listing.splitlines():
            # mode type object<TAB>path; blob id + path gives deterministic source snapshot.
            parts = line.split("\t", 1)
            if len(parts) == 2:
                records.append(parts[0].split()[-1] + "\t" + parts[1])
                count += 1
    if not records:
        return None, 0
    return sha_bytes(("\n".join(sorted(records)) + "\n").encode()), count


def worktree_paths_digest(root: Path, paths: Iterable[str]) -> tuple[str | None, int]:
    records: list[str] = []
    count = 0
    excluded = {".git", ".venv", "node_modules", ".pocketlab-dev", "site", "dist", "pwa_dist", "__pycache__", ".pytest_cache"}
    for raw in paths:
        rel = raw.strip("/")
        if rel == ".":
            continue
        target = root / rel
        candidates = [target] if target.is_file() else sorted(target.rglob("*")) if target.is_dir() else []
        for path in candidates:
            if not path.is_file(): continue
            r = path.relative_to(root)
            if any(part in excluded for part in r.parts): continue
            records.append(str(r) + "\t" + sha_bytes(path.read_bytes()))
            count += 1
    if not records: return None, 0
    return sha_bytes(("\n".join(sorted(records)) + "\n").encode()), count




def read_ref_json(root: Path, ref: str, rel: str) -> Any:
    raw = git_maybe(root, "show", f"{ref}:{rel}")
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def current_json(root: Path, rel: str) -> Any:
    return read_json(root / rel, None)


def api_operations(doc: Any) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    if not isinstance(doc, dict):
        return out
    for path, spec in (doc.get("paths") or {}).items():
        if not isinstance(spec, dict):
            continue
        for method in spec:
            if str(method).lower() in {"get", "post", "put", "patch", "delete", "options", "head"}:
                out.add((str(method).upper(), str(path)))
    return out


def async_channels(doc: Any) -> set[str]:
    return set(map(str, (doc.get("channels") or {}).keys())) if isinstance(doc, dict) else set()


def vuln_ids(doc: Any) -> set[str]:
    if not isinstance(doc, dict):
        return set()
    items = doc.get("items") or doc.get("vulnerabilities") or []
    return {str(x.get("id")) for x in items if isinstance(x, dict) and x.get("id")}


def license_keys(doc: Any) -> set[str]:
    if not isinstance(doc, dict):
        return set()
    keys: set[str] = set()
    for item in doc.get("items") or []:
        if not isinstance(item, dict):
            continue
        for lic in item.get("licenses") or []:
            keys.add(str(lic))
        if item.get("license"):
            keys.add(str(item["license"]))
    return keys


def health_rank(value: str) -> int | None:
    value = value.lower().strip()
    ranks = {
        "healthy": 5, "ready": 5, "online": 5, "verified": 5,
        "degraded": 3, "partial": 3, "stale": 2, "unknown": 1,
        "unvalidated": 1, "offline": 0, "failed": 0, "unavailable": 0,
    }
    return ranks.get(value)


def health_values(doc: Any) -> list[int]:
    values: list[int] = []
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"status", "health", "state", "readiness"} and isinstance(child, str):
                    rank = health_rank(child)
                    if rank is not None:
                        values.append(rank)
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(doc)
    return values


def specialized_dimension_classification(root: Path, baseline_tag: str, current_tag: str, name: str, default: str) -> tuple[str, dict[str, Any]]:
    details: dict[str, Any] = {}
    if name == "openapi":
        old = api_operations(read_ref_json(root, baseline_tag, "contracts/generated/lite-openapi.json"))
        new = api_operations(read_ref_json(root, current_tag, "contracts/generated/lite-openapi.json"))
        removed, added = sorted(old - new), sorted(new - old)
        details = {"operations_added": [f"{m} {p}" for m, p in added], "operations_removed": [f"{m} {p}" for m, p in removed]}
        if removed: return "breaking", details
        if added: return "non-breaking", details
    elif name == "asyncapi-events":
        old = async_channels(read_ref_json(root, baseline_tag, "contracts/generated/lite-asyncapi.json"))
        new = async_channels(read_ref_json(root, current_tag, "contracts/generated/lite-asyncapi.json"))
        removed, added = sorted(old - new), sorted(new - old)
        details = {"channels_added": added, "channels_removed": removed}
        if removed: return "breaking", details
        if added: return "non-breaking", details
    elif name == "vulnerabilities":
        old = vuln_ids(read_ref_json(root, baseline_tag, "contracts/generated/supply-chain/vulnerability-correlation.json"))
        new = vuln_ids(read_ref_json(root, current_tag, "contracts/generated/supply-chain/vulnerability-correlation.json"))
        new_ids, resolved = sorted(new-old), sorted(old-new)
        details = {"new_vulnerabilities": new_ids, "resolved_vulnerabilities": resolved}
        if new_ids: return "new-vulnerability", details
        if resolved: return "resolved-vulnerability", details
    elif name == "licenses":
        old = license_keys(read_ref_json(root, baseline_tag, "contracts/generated/supply-chain/license-inventory.json"))
        new = license_keys(read_ref_json(root, current_tag, "contracts/generated/supply-chain/license-inventory.json"))
        added = sorted(new-old)
        details = {"licenses_added": added, "licenses_removed": sorted(old-new)}
        if added: return "new-license", details
    elif name in {"operational-health", "runtime-topology", "semantic-parity", "platform-capability-evidence"}:
        rel = RELEASE_DIMENSIONS[name][0]
        old_values = health_values(read_ref_json(root, baseline_tag, rel))
        new_values = health_values(read_ref_json(root, current_tag, rel))
        if old_values and new_values:
            old_avg, new_avg = sum(old_values)/len(old_values), sum(new_values)/len(new_values)
            details = {"from_health_score": round(old_avg, 3), "to_health_score": round(new_avg, 3)}
            if new_avg > old_avg: return "improved", details
            if new_avg < old_avg: return "degraded", details
        elif not old_values and new_values:
            return "newly-observed", {"observations": len(new_values)}
        elif old_values and not new_values:
            return "no-longer-observed", {"previous_observations": len(old_values)}
    return default, details

def release_delta(root: Path) -> dict[str, Any]:
    refs = shared_comparison_state(root)
    classifications = ["added", "removed", "changed", "breaking", "non-breaking", "improved", "degraded", "newly-observed", "no-longer-observed", "evidence-stale", "new-vulnerability", "resolved-vulnerability", "new-license", "dependency-added", "dependency-removed", "dependency-updated", "architecture-drift", "not-comparable", "unknown", "unchanged"]
    current = refs.get("current")
    baseline = refs.get("baseline")
    if refs.get("comparison_state") != "comparable" or not baseline or not current:
        state = refs.get("comparison_state")
        status = "initial-canonical-comparison-baseline" if state == "baseline-only" else "comparison-evidence-unavailable" if state == "comparison-evidence-unavailable" else "no-comparable-verified-prior-release"
        reason = refs.get("reason") or "a second verified canonical release is required"
        return {
            "implementation_status": "implemented",
            "evidence_status": "baseline-only" if state == "baseline-only" else "verified-releases-local-history-unavailable" if state == "comparison-evidence-unavailable" else "not-comparable",
            "status": status,
            "comparison_state": refs.get("comparison_state"),
            "classifications": classifications,
            "from": None,
            "to": current,
            "baseline_policy": refs.get("baseline_policy"),
            "dimensions": [{"dimension": d, "status": "not-comparable", "classification": "not-comparable", "source_paths": paths, "details": {"reason": reason}} for d, paths in RELEASE_DIMENSIONS.items()],
        }
    dimensions=[]
    for name, paths in RELEASE_DIMENSIONS.items():
        old_digest, old_count = ref_paths_digest(root, baseline["tag"], paths)
        new_digest, new_count = ref_paths_digest(root, current["tag"], paths)
        if old_digest is None and new_digest is None:
            cls="not-comparable"
        elif old_digest is None:
            cls="added"
        elif new_digest is None:
            cls="removed"
        elif old_digest == new_digest:
            cls="unchanged"
        else:
            cls="architecture-drift" if name in {"architecture","trust-boundaries"} else "changed"
        detail: dict[str, Any] = {}
        if cls not in {"not-comparable", "added", "removed", "unchanged"}:
            cls, detail = specialized_dimension_classification(root, baseline["tag"], current["tag"], name, cls)
        dimensions.append({"dimension":name,"status":"comparable" if cls!="not-comparable" else "not-comparable","classification":cls,"from_digest":old_digest,"to_digest":new_digest,"from_objects":old_count,"to_objects":new_count,"source_paths":paths,"details":detail})
    changed=[x for x in dimensions if x["classification"] not in {"unchanged","not-comparable"}]
    diff_names=(git_maybe(root,"diff","--name-status",baseline["tag"],current["tag"],"--") or "").splitlines()
    stats=Counter(line.split("\t",1)[0][0] for line in diff_names if line)
    return {
        "implementation_status":"implemented", "evidence_status":"release-promoted", "status":"comparable",
        "comparison_state":"comparable", "classifications":classifications, "from":baseline, "to":current,
        "baseline_policy":refs.get("baseline_policy"),
        "summary":{"dimensions_changed":len(changed),"dimensions_total":len(dimensions),"files_added":stats.get("A",0),"files_modified":stats.get("M",0),"files_deleted":stats.get("D",0),"files_renamed":stats.get("R",0)},
        "dimensions":dimensions,
    }

def release_evidence(root: Path, delta: dict[str, Any]) -> dict[str, Any]:
    runtime=read_json(root/"contracts/parity/runtime-verification-baseline.json",{}) or {}
    health=read_json(root/"contracts/generated/runtime/domain-operational-health.json",{}) or {}
    parity=read_json(root/"contracts/generated/parity/runtime-drift.json",{}) or {}
    limitations=read_json(root/"contracts/generated/parity/accepted-limitations.json",{}) or {}
    provenance=read_json(root/"contracts/generated/release-provenance.json",{}) or {}
    signature_evidence=read_json(root/"contracts/generated/release-signatures.json",{}) or {}
    release_manifest=read_json(root/"pocketlab-lite-release.json",{}) or {}
    release_record = next((x for x in shared_canonical_release_records(root) if x.get("tag") == (runtime.get("release_tag") or runtime.get("release"))), None)
    artifacts=build_artifact_evidence(root, release_record)
    fingerprints={}
    for name,path in {"openapi":root/"contracts/generated/lite-openapi.json","asyncapi":root/"contracts/generated/lite-asyncapi.json","architecture":root/"architecture/metadata/pocket-lab-architecture.json","operational_health":root/"contracts/generated/runtime/domain-operational-health.json","documentation":root/"contracts/generated/documentation-intelligence/index.json"}.items():
        fingerprints[name]=sha_bytes(path.read_bytes()) if path.exists() else None
    sbom=root/"contracts/generated/supply-chain/sbom-release.cdx.json"; sec=root/"contracts/generated/supply-chain/security-analysis.json"
    local_source=os.environ.get("SOURCE_COMMIT") or "uncommitted"
    local_tree=os.environ.get("SOURCE_TREE_HASH") or "uncommitted"
    supply_present=all((root/p).exists() for p in ["contracts/generated/supply-chain/automation-summary.json","contracts/generated/supply-chain/sbom-release.cdx.json","contracts/generated/supply-chain/vulnerability-correlation.json"])
    assurance=build_release_assurance(
        root, runtime, health.get("domains") or {}, parity.get("items") or [], supply_present, artifacts,
        provenance, signature_evidence or provenance.get("signing",{}), local_source, local_tree,
    )
    active=shared_active_limitations(limitations, health.get("domains") or {})
    exact_tag=(release_record or {}).get("tag") if assurance["authorities"]["release"]["status"]=="verified" else None
    return {
        "implementation_status":"implemented", "evidence_status":"source-and-canonical-evidence", "status":"release-assurance-model-operational",
        "source_commit":local_source, "tree_hash":local_tree, "exact_tag":exact_tag,
        "build_timestamp":release_manifest.get("build_timestamp") or release_manifest.get("created_at") or "unobserved",
        "artifacts":artifacts, "frontend_version":(read_json(root/"package.json",{}) or {}).get("version") or "unobserved",
        "backend_identity":runtime.get("source_commit") or "unobserved", "database_migration_level":latest_migration(root),
        "fingerprints":fingerprints, "runtime_baseline_binding":runtime.get("release_tag") or runtime.get("release") or "unobserved",
        "sbom_digest":sha_bytes(sbom.read_bytes()) if sbom.exists() else None, "security_scan_digest":sha_bytes(sec.read_bytes()) if sec.exists() else None,
        "signatures":signature_evidence or provenance.get("signing",{"status":"unobserved","workflow":"implemented via scripts/docs/enterprise/release_provenance.py"}),
        "provenance":provenance or {"implementation_status":"implemented","evidence_status":"unobserved","formal_slsa_level":"not-claimed"},
        "device_compatibility":["Android/Termux ARM64","ARM64 Ubuntu/proot","Ubuntu/WSL2 development"],
        "known_limitations":active, "breaking_changes":[x for x in delta.get("dimensions",[]) if x.get("classification")=="breaking"],
        "validation_outcomes":"canonical validation evidence only; never polled live",
        "authorities":assurance["authorities"], "assurance":assurance, "evidence_gaps":assurance["evidence_gaps"], "lineage":assurance["lineage"],
    }

def latest_migration(root: Path) -> str:
    candidates=[]
    for base in [root/"pocket-lab-final-structure/runtime/api_fastapi/migrations",root/"pocket-lab-final-structure/runtime/migrations"]:
        if base.exists(): candidates.extend(p.name for p in base.glob("*.sql"))
    return sorted(candidates)[-1] if candidates else "unobserved"


def task_workflow_group(name: str, commands: list[str]) -> str:
    low = (name + " " + " ".join(commands)).lower()
    if any(token in low for token in ["release", "dist.zip", "tag"]):
        return "Release loop"
    if any(token in low for token in ["recovery", "backup", "restore", "diagnostic"]):
        return "Recovery-diagnostics loop"
    if any(token in low for token in ["security", "syft", "grype", "osv", "semgrep", "gitleaks", "scancode", "scorecard", "cosign", "threat"]):
        return "Security-analysis loop"
    if any(token in low for token in ["runtime", "termux", "promote", "capture"]):
        return "Runtime-evidence loop"
    if any(token in low for token in ["schemathesis", "oasdiff", "openapi", "api:", "contracts"]):
        return "API-validation loop"
    if "docs" in low or "mkdocs" in low or "knowledge" in low or "architecture" in low:
        return "Documentation loop"
    return "Development loop"


def task_handbook(root: Path) -> list[dict[str, Any]]:
    rows=[]
    files=[root/"Taskfile.yml",*sorted((root/"tasks").glob("Taskfile*.yml"))]
    for path in files:
        data=yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name,spec in sorted((data.get("tasks") or {}).items()):
            if not isinstance(spec,dict): continue
            deps=[]
            for dep in spec.get("deps",[]) or []: deps.append(dep if isinstance(dep,str) else str(dep.get("task") or "structured-dependency"))
            commands=[]
            for raw in spec.get("cmds",[]) or []:
                if isinstance(raw,str): commands.append(raw)
                elif isinstance(raw,dict): commands.append(f"task {raw['task']}" if raw.get("task") else str(raw.get("cmd") or "structured command"))
            joined="\n".join(commands)
            refs=sorted(set(re.findall(r"(?:^|[\s'\"])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.{}@:+-]+)+)",joined)))
            refs=[x for x in refs if not x.startswith(("http://","https://"))]
            outputs=[x for x in refs if any(seg in x for seg in ["contracts/generated","docs/generated",".pocketlab-dev","dist.zip","checksums.txt","pocketlab-lite-release.json"])]
            inputs=[x for x in refs if x not in outputs]
            low=(name+" "+joined).lower()
            capture="capture" in low and any(x in low for x in ["runtime","termux","evidence"])
            promote="promote" in low and any(x in low for x in ["runtime","termux","evidence","supply-chain"])
            repo_mut=any(x in low for x in ["generate","promote","release","write","sync","migration"])
            runtime_mut=any(x in low for x in ["restart","install","restore","apply","bootstrap","release:apply"])
            heavy=any(x in low for x in ["playwright","mkdocs","graphviz","schemaspy","schemathesis","oasdiff","syft","grype","osv-scanner","semgrep","gitleaks","scancode","scorecard","cosign"])
            termux=any(x in low for x in ["termux","android","server-phone"])
            validation_outcome="gate-defined" if any(x in name for x in [":check",":test",":validate",":verify"]) else "not-a-validation-task"
            rows.append({"name":name,"purpose":spec.get("desc") or "No canonical description declared.","audience":"developer/operator" if termux else "developer","source":str(path.relative_to(root)),"dependencies":sorted(set(deps)),"aliases":sorted(set(spec.get("aliases",[]) or [])),"commands":commands,"environment":sorted(set(re.findall(r"\b(?:POCKETLAB|LITE|NATS|TAILSCALE)_[A-Z0-9_]+\b",joined))),"inputs":inputs[:24],"outputs":outputs[:24],"generated_artifacts":[x for x in outputs if x.startswith(("contracts/generated","docs/generated"))],"side_effects":{"repository_mutation":repo_mut,"runtime_mutation":runtime_mut,"network_or_external_tools":heavy or "gh " in low},"runtime_mutation":runtime_mut,"repository_mutation":repo_mut,"captures_runtime":capture,"promotes_evidence":promote,"requires_termux":termux and (capture or runtime_mut),"requires_wsl2":heavy and not termux,"safe_local":not capture and not promote and not runtime_mut,"expected_runtime_class":"heavy-dev" if heavy else "bounded","related_tasks":sorted(set(deps+[x[5:] for x in commands if x.startswith("task ")])),"failure_modes":["dependency task failure","missing required local tool or evidence","generated drift" if "docs" in low or "generate" in low else "command failure"],"validation_outcome":validation_outcome,"example_invocation":f"task {name}","workflow_group":task_workflow_group(name,commands),"implementation_status":"implemented"})
    return rows


def event_encyclopedia(root: Path) -> list[dict[str, Any]]:
    data=read_json(root/"contracts/generated/lite-asyncapi.json",{}) or {}; rows=[]
    reason_data=read_json(root/"contracts/generated/reason-codes.json",{}) or {}; reason_codes=[x.get("code") or x.get("id") for x in reason_data.get("reason_codes",[]) if isinstance(x,dict)]
    trace=read_json(root/"contracts/generated/knowledge/traceability.json",{}) or {}; trace_items=trace.get("items",[]) if isinstance(trace.get("items",[]),list) else []
    source_candidates=[*sorted((root/"pocket-lab-final-structure/runtime").rglob("*.py")),*sorted((root/"scripts").rglob("*.py"))]
    source_cache={path:path.read_text(encoding="utf-8",errors="ignore") for path in source_candidates if path.is_file()}
    for subject,value in sorted((data.get("channels") or {}).items()):
        if not isinstance(value,dict): continue
        source=list(value.get("x-pocketlab-source") or [])
        if not source:
            source=[str(path.relative_to(root)) for path,text in source_cache.items() if subject in text][:20]
        if not source:
            source=["unobserved-in-source-search; channel remains canonical from AsyncAPI"]
        domain=value.get("x-pocketlab-domain") or (subject.split(".")[2] if len(subject.split("."))>2 else "platform")
        related_tests=sorted({t for x in trace_items if isinstance(x,dict) and subject in str(x) for t in x.get("tests",[])})[:12]
        rows.append({"event_name":subject.replace("."," / "),"domain":domain,"publisher":value.get("x-pocketlab-publisher") or ["unobserved-in-canonical-AsyncAPI"],"consumers":value.get("x-pocketlab-consumer") or ["unobserved-in-canonical-AsyncAPI"],"nats_subject":subject,"schema":"AsyncAPI channel metadata; payload schema is unobserved when channel has no message binding","payload_fields":[],"lifecycle":"command" if ".commands." in f".{subject}." else "event/telemetry","durability":value.get("x-pocketlab-durable") or "unvalidated","replay":value.get("x-pocketlab-stream") or "unvalidated","ordering":"subject/consumer scoped; no global ordering inferred","idempotency":"consumer-specific; only canonical operation guarantees apply","acknowledgment":value.get("x-pocketlab-delivery") or "unvalidated","failure_handling":value.get("x-pocketlab-retry") or "unvalidated","audit_implications":"sanitized lifecycle evidence must remain observable where runtime path declares audit/event ownership","related_api":"derive through source and traceability links","reason_codes":reason_codes[:12] if domain in {"devices","security","recovery"} else [],"ui_state":"FastAPI projection only; browser never subscribes to NATS","sanitized_example":{"subject":subject,"domain":domain,"status":"example-without-payload"},"tests":related_tests,"source_owner":source,"runtime_owner":"publisher/consumer processes listed above","security_classification":value.get("x-pocketlab-security-classification") or "internal metadata","redacted_fields":value.get("x-pocketlab-redacted-fields") or [],"implementation_status":"implemented"})
    return rows


def source_dependency_inventory(root: Path, baseline_tag: str | None) -> dict[str, Any]:
    package=read_json(root/"package.json",{}) or {}; lock=read_json(root/"package-lock.json",{}) or {}; direct=set((package.get("dependencies") or {}))|set((package.get("devDependencies") or {}))
    rows=[]
    packages=lock.get("packages") or {}
    for path,item in sorted(packages.items()):
        if not path.startswith("node_modules/") or not isinstance(item,dict): continue
        name=path.split("node_modules/")[-1]
        rows.append({"name":name,"version":str(item.get("version") or "unobserved"),"ecosystem":"npm","category":"Node dependency","direct":name in direct,"transitive":name not in direct,"purpose":"runtime/frontend dependency" if name in (package.get("dependencies") or {}) else "development/tooling dependency","license":item.get("license") or "unobserved","architecture":"browser/developer/runtime depending on package","arm64_support":"package/source metadata does not establish architecture-specific support" if not item.get("cpu") else "declared CPU constraints: "+",".join(map(str,item.get("cpu") or [])),"runtime_or_dev":"runtime" if name in (package.get("dependencies") or {}) else "development","vulnerability_status":"canonical scanner evidence when promoted","upstream_posture":"OpenSSF/normalized evidence when promoted","release_introduced":dependency_introduced(root,baseline_tag,"npm",name,str(item.get("version") or ""))})
    for rel,scope in [("requirements-dev.txt","development"),("requirements-docs.txt","development"),("pocket-lab-final-structure/runtime/requirements.txt","runtime")]:
        p=root/rel
        if not p.exists(): continue
        for raw in p.read_text(encoding="utf-8").splitlines():
            line=raw.strip()
            if not line or line.startswith("#") or line.startswith("-"): continue
            m=re.match(r"([A-Za-z0-9_.-]+)\s*(?:==|~=|>=|<=|>|<)?\s*([^;\s]+)?",line)
            if not m: continue
            name=m.group(1); version=m.group(2) or "constraint/source-defined"
            rows.append({"name":name,"version":version,"ecosystem":"PyPI","category":"Python dependency","direct":True,"transitive":False,"purpose":f"{scope} Python dependency","license":"unobserved until ScanCode/SBOM evidence","architecture":"platform-dependent","arm64_support":"verify from package wheel/source metadata; not inferred","runtime_or_dev":scope,"vulnerability_status":"canonical scanner evidence when promoted","upstream_posture":"normalized evidence when promoted","release_introduced":dependency_introduced(root,baseline_tag,"PyPI",name,version)})

    # Runtime/system/external-app inventory is bounded to already-promoted sanitized runtime evidence.
    runtime=read_json(root/"contracts/parity/runtime-verification-baseline.json",{}) or {}
    found: dict[tuple[str,str],dict[str,Any]]={}
    allowed_names={"name","service","component","package","tool","app"}; version_keys={"version","runtime_version","app_version","service_version"}
    def walk(value:Any)->None:
        if isinstance(value,dict):
            name=next((value.get(k) for k in allowed_names if isinstance(value.get(k),str)),None)
            version=next((value.get(k) for k in version_keys if isinstance(value.get(k),(str,int,float))),None)
            if name and version:
                clean_name=re.sub(r"[^A-Za-z0-9_.+/-]","-",str(name))[:120]; clean_version=re.sub(r"[^A-Za-z0-9_.+~-]","-",str(version))[:80]
                if clean_name and clean_version:
                    found[(clean_name,clean_version)]={"name":clean_name,"version":clean_version,"ecosystem":"promoted-runtime","category":"OS/system/runtime package or external application","direct":True,"transitive":False,"purpose":"runtime component observed in promoted sanitized baseline","license":"unobserved unless canonical SBOM/license evidence correlates it","architecture":"promoted Android/Termux ARM64 runtime","arm64_support":"observed on promoted ARM64 runtime","runtime_or_dev":"runtime","vulnerability_status":"canonical runtime/SBOM scanner evidence when promoted","upstream_posture":"normalized evidence when promoted","release_introduced":"runtime-baseline-derived; release introduction requires historical promoted baseline"}
            for child in value.values(): walk(child)
        elif isinstance(value,list):
            for child in value: walk(child)
    walk(runtime)
    rows.extend(found[k] for k in sorted(found))

    release_manifest=read_json(root/"pocketlab-lite-release.json",{}) or {}
    if release_manifest.get("artifact"):
        rows.append({"name":str(release_manifest.get("artifact")),"version":str(release_manifest.get("release_tag") or "release-staging"),"ecosystem":"release-artifact","category":"Release artifact","direct":True,"transitive":False,"purpose":"Pocket Lab Lite release payload","license":"repository license applies; artifact contents are inventoried by release SBOM","architecture":str(release_manifest.get("target") or "web-pwa"),"arm64_support":"PWA artifact is architecture-neutral; runtime compatibility remains release evidence","runtime_or_dev":"release","vulnerability_status":"release SBOM/scanner evidence when promoted","upstream_posture":"release provenance/signature evidence","release_introduced":str(release_manifest.get("release_tag") or "unobserved")})

    dedup={}
    for row in rows:
        dedup[(row["ecosystem"],row["name"],row["version"],row["runtime_or_dev"])]=row
    rows=sorted(dedup.values(),key=lambda x:(x["ecosystem"],x["name"],x["version"],x["runtime_or_dev"]))
    return {"implementation_status":"implemented","evidence_status":"source-derived-plus-promoted-runtime/tool-evidence","dependencies":rows,"counts":{"total":len(rows),"direct":sum(1 for x in rows if x["direct"]),"transitive":sum(1 for x in rows if x["transitive"]),"runtime":sum(1 for x in rows if x["runtime_or_dev"]=="runtime"),"development":sum(1 for x in rows if x["runtime_or_dev"]=="development"),"release":sum(1 for x in rows if x["runtime_or_dev"]=="release")},"inventory_surfaces":["Node dependencies","Python dependencies","promoted runtime/system components","external applications visible in promoted runtime evidence","release artifacts"]}


def dependency_introduced(root: Path, baseline_tag: str | None, ecosystem: str, name: str, version: str) -> str:
    if not baseline_tag: return "not-comparable"
    files=["package-lock.json"] if ecosystem=="npm" else ["requirements-dev.txt","requirements-docs.txt","pocket-lab-final-structure/runtime/requirements.txt"]
    old=""
    for p in files: old += (git_maybe(root,"show",f"{baseline_tag}:{p}") or "")+"\n"
    if name not in old: return "current-release-candidate"
    if version and version not in old: return "version-changed-since-baseline"
    return "present-in-baseline"


def supply_chain_current_snapshot(root: Path) -> dict[str, Any]:
    """Project promoted canonical supply-chain evidence without reading transient scanner output."""
    supply_root = root / "contracts/generated/supply-chain"
    automation = read_json(supply_root / "automation-summary.json", {}) or {}
    sbom_dev = read_json(supply_root / "sbom-dev.cdx.json", {}) or {}
    sbom_release = read_json(supply_root / "sbom-release.cdx.json", {}) or {}
    sbom_runtime = read_json(supply_root / "sbom-runtime.cdx.json", {}) or {}
    vulnerabilities = read_json(supply_root / "vulnerability-correlation.json", {}) or {}
    licenses = read_json(supply_root / "license-inventory.json", {}) or {}
    security = read_json(supply_root / "security-analysis.json", {}) or {}
    scorecard = read_json(supply_root / "scorecard-checks.json", {}) or {}

    tool_rows = []
    for item in automation.get("tool_statuses", []) if isinstance(automation, dict) else []:
        if not isinstance(item, dict):
            continue
        tool_rows.append({
            "step_id": str(item.get("step_id") or item.get("tool") or "unobserved"),
            "tool": str(item.get("tool") or item.get("step_id") or "unobserved"),
            "status": str(item.get("status") or "unobserved"),
            "exit_code": item.get("exit_code"),
            "duration_seconds": item.get("duration_seconds"),
        })

    scorecard_rows = []
    for item in scorecard.get("checks", []) if isinstance(scorecard, dict) else []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        scorecard_rows.append({
            "name": str(item.get("name")),
            "status": str(item.get("status") or "unobserved"),
            "score": item.get("score"),
            "reason": str(item.get("reason") or "unobserved"),
            "blocking": bool(item.get("blocking", True)),
        })

    gitleaks = security.get("gitleaks") if isinstance(security, dict) else {}
    semgrep = security.get("semgrep") if isinstance(security, dict) else {}
    trivy_security = security.get("trivy") if isinstance(security, dict) else {}
    package_coverage = licenses.get("package_license_coverage") if isinstance(licenses, dict) else {}
    deep_coverage = licenses.get("deep_source_license_coverage") if isinstance(licenses, dict) else {}
    vuln_items = vulnerabilities.get("items", []) if isinstance(vulnerabilities, dict) else []

    source_refs = [
        "contracts/generated/supply-chain/automation-summary.json",
        "contracts/generated/supply-chain/sbom-dev.cdx.json",
        "contracts/generated/supply-chain/sbom-release.cdx.json",
        "contracts/generated/supply-chain/sbom-runtime.cdx.json",
        "contracts/generated/supply-chain/vulnerability-correlation.json",
        "contracts/generated/supply-chain/license-inventory.json",
        "contracts/generated/supply-chain/security-analysis.json",
        "contracts/generated/supply-chain/scorecard-checks.json",
    ]
    present = [ref for ref in source_refs if (root / ref).exists()]
    return {
        "schema_version": "1.0.0",
        "implementation_status": "implemented",
        "evidence_status": "promoted-canonical" if bool(automation.get("capture_complete")) else "partial-or-unobserved",
        "run_id": automation.get("run_id") or "unobserved",
        "source_commit": automation.get("source_commit") or "unobserved",
        "qualification_surface": automation.get("qualification_surface") or "unobserved",
        "capture_complete": bool(automation.get("capture_complete")),
        "sbom": {
            "dev_components": len(sbom_dev.get("components", []) or []) if isinstance(sbom_dev, dict) else 0,
            "release_components": len(sbom_release.get("components", []) or []) if isinstance(sbom_release, dict) else 0,
            "runtime_components": len(sbom_runtime.get("components", []) or []) if isinstance(sbom_runtime, dict) else 0,
        },
        "vulnerabilities": {
            "evidence_status": vulnerabilities.get("evidence_status") or vulnerabilities.get("status") or "unobserved",
            "finding_count": len(vuln_items or []) if isinstance(vuln_items, list) else 0,
            "scanner_disagreement_is_failure": bool(vulnerabilities.get("scanner_disagreement_is_failure", False)),
        },
        "licenses": {
            "package_license_coverage": package_coverage if isinstance(package_coverage, dict) else {},
            "deep_source_license_coverage": deep_coverage if isinstance(deep_coverage, dict) else {},
            "package_rows": len(licenses.get("items", []) or []) if isinstance(licenses, dict) else 0,
            "trivy_license_rows": len(licenses.get("trivy_detected_licenses", []) or []) if isinstance(licenses, dict) else 0,
        },
        "security": {
            "gitleaks_finding_count": (gitleaks or {}).get("finding_count", 0) if isinstance(gitleaks, dict) else 0,
            "semgrep_finding_count": (semgrep or {}).get("finding_count", 0) if isinstance(semgrep, dict) else 0,
            "trivy_counts": (trivy_security or {}).get("counts", {}) if isinstance(trivy_security, dict) else {},
        },
        "repository_posture": {
            "status": (scorecard.get("status") or "unobserved") if isinstance(scorecard, dict) else "unobserved",
            "provider": (scorecard.get("provider") or "openssf-scorecard") if isinstance(scorecard, dict) else "openssf-scorecard",
            "checks": sorted(scorecard_rows, key=lambda x: x["name"]),
            "observed_count": sum(1 for x in scorecard_rows if x["status"] == "observed"),
            "provider_unavailable_count": sum(1 for x in scorecard_rows if x["status"] == "provider-unavailable"),
        },
        "tool_coverage": sorted(tool_rows, key=lambda x: x["step_id"]),
        "source_refs": present,
        "raw_scanner_output_included": False,
        "live_capture_performed": False,
    }


def supply_chain_baseline_readiness(root: Path) -> dict[str, Any]:
    baseline = current_release_baseline(root)
    selected = baseline.get("baseline") if isinstance(baseline, dict) else None
    return {
        "status": "ready" if isinstance(selected, dict) else "not-ready",
        "candidate_count": int(baseline.get("candidate_count") or 0) if isinstance(baseline, dict) else 0,
        "selected_baseline": selected,
        "head": baseline.get("head") if isinstance(baseline, dict) else None,
        "head_tree": baseline.get("head_tree") if isinstance(baseline, dict) else None,
        "baseline_policy": baseline.get("baseline_policy") if isinstance(baseline, dict) else "verified canonical release baseline required",
        "reason": "comparable verified prior release selected" if isinstance(selected, dict) else (baseline.get("comparison_state") == "comparison-evidence-unavailable" and "verified releases exist but matching local Git tags are unavailable for deterministic historical reads" or "no second verified canonical release is available for release-to-release comparison"),
    }


def supply_chain_change(inventory: dict[str,Any], root: Path, baseline_tag: str | None) -> dict[str, Any]:
    snapshot = supply_chain_current_snapshot(root)
    readiness = supply_chain_baseline_readiness(root)
    empty={"schema_version":"1.1.0","implementation_status":"implemented","evidence_status":"not-comparable","status":"no-comparable-verified-prior-release","current_snapshot":snapshot,"baseline_readiness":readiness,"historical_comparison":{"status":"not-comparable","from":None,"to":"current-source","reason":readiness["reason"]},"dependencies_added":[],"dependencies_removed":[],"versions_changed":[],"new_vulnerabilities":[],"resolved_vulnerabilities":[],"new_licenses":[],"removed_licenses":[],"license_classification_changes":[],"upstream_posture_changes":[],"scanner_history_comparable":False,"rule":"scanner disagreement is represented, never converted automatically into a release failure; no historical delta is fabricated without a verified prior release"}
    if not baseline_tag:
        return empty
    current={(x["ecosystem"],x["name"]):x["version"] for x in inventory["dependencies"] if x["ecosystem"] in {"npm","PyPI"}}
    old={}
    old_lock=git_maybe(root,"show",f"{baseline_tag}:package-lock.json")
    if old_lock:
        try:
            d=json.loads(old_lock)
            for path,item in (d.get("packages") or {}).items():
                if path.startswith("node_modules/") and isinstance(item,dict): old[("npm",path.split("node_modules/")[-1])]=str(item.get("version") or "unobserved")
        except json.JSONDecodeError: pass
    for rel in ["requirements-dev.txt","requirements-docs.txt","pocket-lab-final-structure/runtime/requirements.txt"]:
        text=git_maybe(root,"show",f"{baseline_tag}:{rel}") or ""
        for line in text.splitlines():
            m=re.match(r"\s*([A-Za-z0-9_.-]+)\s*(?:==|~=|>=|<=|>|<)?\s*([^;\s]+)?",line)
            if m and not line.lstrip().startswith("#"): old[("PyPI",m.group(1))]=m.group(2) or "constraint/source-defined"
    added=[{"ecosystem":k[0],"name":k[1],"version":v,"classification":"dependency-added"} for k,v in current.items() if k not in old]
    removed=[{"ecosystem":k[0],"name":k[1],"version":v,"classification":"dependency-removed"} for k,v in old.items() if k not in current]
    changed=[{"ecosystem":k[0],"name":k[1],"from":old[k],"to":v,"classification":"dependency-updated"} for k,v in current.items() if k in old and old[k]!=v]

    cur_v=read_json(root/"contracts/generated/supply-chain/vulnerability-correlation.json",{}) or {}; old_v=read_ref_json(root,baseline_tag,"contracts/generated/supply-chain/vulnerability-correlation.json") or {}
    cur_ids={str(x.get("id")) for x in cur_v.get("items",[]) if isinstance(x,dict) and x.get("id")}; old_ids={str(x.get("id")) for x in old_v.get("items",[]) if isinstance(x,dict) and x.get("id")}
    cur_l=read_json(root/"contracts/generated/supply-chain/license-inventory.json",{}) or {}; old_l=read_ref_json(root,baseline_tag,"contracts/generated/supply-chain/license-inventory.json") or {}
    def licenses(doc:Any)->set[str]:
        out=set()
        if isinstance(doc,dict):
            for item in doc.get("items",[]) or []:
                if isinstance(item,dict): out.update(map(str,item.get("licenses") or []))
            for item in doc.get("scancode_detected_expressions",[]) or []:
                if isinstance(item,dict) and item.get("expression"): out.add(str(item["expression"]))
        return out
    cur_lic,old_lic=licenses(cur_l),licenses(old_l)
    old_score=read_ref_json(root,baseline_tag,"contracts/generated/supply-chain/scorecard-checks.json") or {}; cur_score=read_json(root/"contracts/generated/supply-chain/scorecard-checks.json",{}) or {}
    def scores(doc:Any)->dict[str,Any]: return {str(x.get("name")):x.get("score") for x in (doc.get("checks") or []) if isinstance(x,dict) and x.get("name")} if isinstance(doc,dict) else {}
    oscore,cscore=scores(old_score),scores(cur_score)
    upstream=[{"check":name,"from":oscore.get(name),"to":score} for name,score in sorted(cscore.items()) if name in oscore and oscore[name]!=score]
    comparable_scanners=bool(old_v or old_l or old_score)
    return {"schema_version":"1.1.0","implementation_status":"implemented","evidence_status":"source-comparable; normalized scanner/license/upstream deltas only when historical canonical artifacts exist","status":"comparable","current_snapshot":snapshot,"baseline_readiness":readiness,"historical_comparison":{"status":"comparable","from":baseline_tag,"to":"current-source","reason":"verified canonical prior-release baseline selected"},"from":baseline_tag,"to":"current-source","dependencies_added":added,"dependencies_removed":removed,"versions_changed":changed,"new_vulnerabilities":[{"id":x,"classification":"new-vulnerability"} for x in sorted(cur_ids-old_ids)] if old_v else [],"resolved_vulnerabilities":[{"id":x,"classification":"resolved-vulnerability"} for x in sorted(old_ids-cur_ids)] if old_v else [],"new_licenses":[{"license":x,"classification":"new-license"} for x in sorted(cur_lic-old_lic)] if old_l else [],"removed_licenses":[{"license":x} for x in sorted(old_lic-cur_lic)] if old_l else [],"license_classification_changes":[],"upstream_posture_changes":upstream if old_score else [],"scanner_history_comparable":comparable_scanners,"rule":"scanner disagreement is represented, never converted automatically into a release failure; historical deltas require verified canonical evidence"}


def threat_model(root: Path, supply: dict[str,Any], release: dict[str,Any], deps: list[dict[str,Any]]) -> dict[str,Any]:
    health=read_json(root/"contracts/generated/runtime/domain-operational-health.json",{}) or {}; domains=health.get("domains") or {}
    controls=[
      {"id":"CTRL-BROWSER-NATS","description":"Frontend does not connect directly to NATS.","boundaries":["browser","messaging-execution"],"threats":["Spoofing","Tampering","Elevation of Privilege"],"implementation":["src/","pocket-lab-final-structure/runtime/api_fastapi/"],"source_refs":["contracts/generated/knowledge/requirements.json"],"tests":["tests/backend/test_lite_api.py","security/static-analysis/pocketlab-architecture.yml"],"runtime_evidence":[],"status":"mitigation-source-derived","freshness":"source-current","owner":"frontend/control-api"},
      {"id":"CTRL-BROWSER-SHELL","description":"Frontend does not execute shell commands.","boundaries":["browser"],"threats":["Tampering","Elevation of Privilege"],"implementation":["src/"],"source_refs":["contracts/generated/knowledge/requirements.json"],"tests":["security/static-analysis/pocketlab-architecture.yml"],"runtime_evidence":[],"status":"mitigation-source-derived","freshness":"source-current","owner":"frontend"},
      {"id":"CTRL-API-CONTROL","description":"FastAPI remains the frontend-facing control API.","boundaries":["browser","control-api","messaging-execution"],"threats":["Spoofing","Tampering","Elevation of Privilege"],"implementation":["pocket-lab-final-structure/runtime/api_fastapi/"],"source_refs":["contracts/generated/lite-openapi.json"],"tests":["tests/backend/test_lite_api.py","tests/parity/test_api_contract_fences.py"],"runtime_evidence":["contracts/parity/runtime-verification-baseline.json"],"status":"control-observed" if (domains.get("home") or {}).get("runtime_status")=="observed" else "control-partial","freshness":(domains.get("home") or {}).get("freshness","unvalidated"),"owner":"FastAPI"},
      {"id":"CTRL-EXECUTION-OWNERS","description":"Workers, agents and supervisors own execution and recovery.","boundaries":["messaging-execution","managed-device","server-host"],"threats":["Tampering","Denial of Service","Elevation of Privilege"],"implementation":["pocket-lab-final-structure/runtime/workers/","pocket-lab-final-structure/runtime/agents/"],"source_refs":["architecture/metadata/pocket-lab-architecture.json"],"tests":["tests/backend/test_lite_worker_recovery.py"],"runtime_evidence":["contracts/parity/runtime-verification-baseline.json"],"status":"control-observed" if (domains.get("devices") or {}).get("runtime_status")=="observed" else "control-partial","freshness":(domains.get("devices") or {}).get("freshness","unvalidated"),"owner":"worker/agent/supervisor"},
      {"id":"CTRL-EVIDENCE-SANITIZE","description":"Runtime/scanner evidence is sanitized before canonical documentation ingestion.","boundaries":["durable-state","external-release","server-host"],"threats":["Information Disclosure","Repudiation"],"implementation":["scripts/docs/runtime/","scripts/docs/enterprise/supply_chain_automation.py"],"source_refs":["contracts/metadata/documentation-platform.json"],"tests":["tests/docs/test_enterprise_documentation.py"],"runtime_evidence":["contracts/parity/runtime-verification-baseline.json"],"status":"control-observed" if health.get("sanitized") is True else "control-partial","freshness":health.get("promoted_at") or "unvalidated","owner":"evidence pipeline"},
      {"id":"CTRL-EXPLICIT-PROMOTION","description":"Runtime and scanner evidence promotion is explicit; MkDocs does not capture or promote.","boundaries":["external-release","durable-state","server-host"],"threats":["Tampering","Repudiation","Information Disclosure"],"implementation":["scripts/docs/runtime/promote_termux_runtime.py","scripts/docs/enterprise/supply_chain_automation.py"],"source_refs":["contracts/metadata/documentation-platform.json"],"tests":["tests/docs/test_enterprise_documentation.py"],"runtime_evidence":["contracts/parity/runtime-verification-baseline.json"],"status":"control-observed" if (root/"contracts/parity/runtime-verification-baseline.json").exists() else "control-unvalidated","freshness":health.get("promoted_at") or "unvalidated","owner":"developer/CI explicit promotion"},
      {"id":"CTRL-SUPPLY-CHAIN","description":"Pinned WSL2/CI tooling produces sanitized normalized SBOM/security evidence before docs consumption.","boundaries":["external-release","application-container"],"threats":["Tampering","Information Disclosure","Elevation of Privilege"],"implementation":["scripts/dev/lite/documentation_security_tools.py","scripts/docs/enterprise/supply_chain_automation.py"],"source_refs":["contracts/metadata/documentation-security-tools.json"],"tests":["tests/docs/test_enterprise_completion.py"],"runtime_evidence":["contracts/generated/supply-chain/automation-summary.json"],"status":"control-observed" if supply.get("normalized_artifacts") else "mitigation-source-derived","freshness":"canonical artifact dependent","owner":"WSL2/CI security automation"},
    ]
    for control in controls:
        control["boundary"] = list(control.get("boundaries") or [])
        control["threats_mitigated"] = list(control.get("threats") or [])
        control["mitigation_adequacy"] = "human-review-required"
    owasp={"Spoofing":["OWASP Top 10 A07 Identification and Authentication Failures"],"Tampering":["OWASP Top 10 A08 Software and Data Integrity Failures"],"Repudiation":["OWASP Top 10 A09 Security Logging and Monitoring Failures"],"Information Disclosure":["OWASP Top 10 A01 Broken Access Control","OWASP Top 10 A02 Cryptographic Failures"],"Denial of Service":["No direct OWASP Top 10 mapping; availability/resilience control review"],"Elevation of Privilege":["OWASP Top 10 A01 Broken Access Control"]}
    boundary_assets={"browser":["PWA session/UI state","safe snapshots"],"control-api":["API request/response contracts","authorization/context"],"messaging-execution":["commands","events","durable consumers"],"durable-state":["SQLite state","audit evidence","backup metadata"],"managed-device":["device identity","agent state","bootstrap state"],"server-host":["Termux runtime","PM2 services","local secrets"],"private-network":["Tailnet connectivity","same-origin remote access"],"application-container":["PhotoPrism runtime/config","app route"],"external-release":["dist.zip","SBOM","release manifest","provenance"]}
    threats=[]; boundaries=[]
    for bid,label in BOUNDARIES:
        boundaries.append({"id":bid,"label":label,"assets":boundary_assets.get(bid,["control-plane state"]),"actors":["operator","Pocket Lab service","joined device"] + (["external release service"] if bid=="external-release" else []),"entry_points":["repository-defined API/event/runtime/release flow"],"data_flows":["UI → Caddy → FastAPI → NATS/JetStream → worker/agent/supervisor → evidence → FastAPI → UI"],"data_classifications":["sanitized operational metadata","restricted identity/configuration metadata where applicable"],"secrets_handled":"runtime-owned only; never rendered by Documentation Platform","allowed_flows":["canonical control-plane paths only"],"forbidden_flows":["frontend → NATS","frontend → shell","documentation generator → live runtime","raw scanner output → MkDocs"],"trust_assumptions":["canonical contracts are reviewed","promoted runtime evidence is sanitized","tool evidence is normalized before promotion"],"controls":[c["id"] for c in controls if bid in c["boundaries"]],"runtime_evidence":posture_signals(root,domains,release,deps,supply,bid),"tests":["tests/docs/test_enterprise_completion.py"],"owner":"architecture/security owner derived from source","residual_risk":"human review required","review_status":"human-review-required"})
        for stride in STRIDE:
            relevant=[c["id"] for c in controls if bid in c["boundaries"] and stride in c["threats"]]
            threats.append({"id":f"THR-{bid.upper()}-{re.sub('[^A-Z]','',stride.upper())[:12]}","boundary":bid,"stride":stride,"scenario":f"Source-derived candidate {stride} threat affecting the {label}.","assets":boundary_assets.get(bid,["control-plane state"]),"controls":relevant,"mitigations":relevant,"owasp_mappings":owasp[stride],"runtime_evidence":[x["source"] for x in posture_signals(root,domains,release,deps,supply,bid)],"tests":["tests/docs/test_enterprise_completion.py"],"owner":"security/architecture review","residual_risk":"unvalidated until human review","review_status":"candidate-human-review-required"})
    posture=production_threat_posture(root,domains,release,deps,supply,controls)
    return {"schema_version":"2.0.0","implementation_status":"implemented","generator":"scripts/docs/enterprise/generate_enterprise_documentation.py","source_commit":os.environ.get("SOURCE_COMMIT") or "uncommitted","posture":"current-promoted-threat-posture","posture_rule":"derived only from canonical source plus promoted sanitized runtime/security/release/dependency evidence; never live monitoring","boundaries":boundaries,"threats":threats,"controls":controls,"production_posture":posture,"human_review_required":["threat relevance","mitigation adequacy","residual risk","risk acceptance","exceptions"]}


def posture_signals(root:Path,domains:dict[str,Any],release:dict[str,Any],deps:list[dict[str,Any]],supply:dict[str,Any],boundary:str)->list[dict[str,Any]]:
    signals=[]
    mapping={"managed-device":"devices","private-network":"devices","server-host":"home","messaging-execution":"home","application-container":"apps","durable-state":"recovery","control-api":"home","external-release":"security","browser":"home"}
    domain=mapping.get(boundary)
    if domain and isinstance(domains.get(domain),dict):
        d=domains[domain]; state="evidence-stale" if d.get("freshness")=="stale" else "control-observed" if d.get("runtime_status")=="observed" and d.get("evidence_status")=="release-promoted" else "control-partial"
        signals.append({"signal":f"{domain} operational health","state":state,"observed":d.get("operational_health"),"source":"contracts/generated/runtime/domain-operational-health.json"})
    if boundary in {"private-network","managed-device"}:
        d=domains.get("devices") or {}; comp={x.get("comparison_id"):x for x in d.get("evidence",[]) if isinstance(x,dict)}
        value=(comp.get("devices-termux-remote_access_ready") or {}).get("observed_value")
        signals.append({"signal":"Tailscale readiness","state":"control-observed" if value is True else "control-partial" if value is not None else "control-unvalidated","observed":value,"source":"contracts/generated/runtime/domain-operational-health.json"})
    if boundary in {"messaging-execution","server-host","control-api"}:
        nats=[x for x in deps if x.get("dependency")=="NATS/JetStream"]
        state="control-observed" if any(x.get("state")=="healthy" and x.get("evidence_authority")=="verified-runtime-baseline" for x in nats) else "control-partial" if nats else "control-unvalidated"
        signals.append({"signal":"NATS/JetStream health","state":state,"observed":sorted({x.get("state") for x in nats}),"source":"contracts/generated/documentation-intelligence/dependency-health.json"})
    if boundary in {"managed-device","server-host","messaging-execution"}:
        for depname,label in [("node agent","node-agent status"),("agent supervisor","supervisor status"),("worker","worker status")]:
            matches=[x for x in deps if str(x.get("dependency")).lower()==depname]
            signals.append({"signal":label,"state":"control-observed" if any(x.get("state")=="healthy" and x.get("evidence_authority")=="verified-runtime-baseline" for x in matches) else "control-partial" if matches else "control-unvalidated","observed":sorted({x.get("state") for x in matches}),"source":"contracts/generated/documentation-intelligence/dependency-health.json"})
    if boundary in {"external-release","application-container","server-host"}:
        signals.append({"signal":"scanner results","state":"control-observed" if supply.get("normalized_artifacts") else "control-unvalidated","observed":supply.get("status"),"source":"contracts/generated/supply-chain/automation-summary.json"})
        signals.append({"signal":"release evidence","state":"control-observed" if release.get("status") in {"release-evidence-model-operational","release-assurance-model-operational"} else "control-partial","observed":release.get("status"),"source":"contracts/generated/documentation-enterprise/release-evidence.json"})
    if boundary in {"external-release","application-container","messaging-execution"}:
        signals.append({"signal":"dependency health","state":"control-observed" if deps else "control-unvalidated","observed":Counter(x.get("state") for x in deps),"source":"contracts/generated/documentation-intelligence/dependency-health.json"})
        vuln=root/"contracts/generated/supply-chain/vulnerability-correlation.json"
        signals.append({"signal":"SBOM/vulnerability evidence","state":"control-observed" if vuln.exists() else "control-unvalidated","observed":"normalized canonical evidence present" if vuln.exists() else "unobserved","source":"contracts/generated/supply-chain/vulnerability-correlation.json"})
    return signals


def production_threat_posture(root:Path,domains:dict[str,Any],release:dict[str,Any],deps:list[dict[str,Any]],supply:dict[str,Any],controls:list[dict[str,Any]])->dict[str,Any]:
    signals=[]
    for bid,_ in BOUNDARIES:
        signals.extend([{**x,"boundary":bid} for x in posture_signals(root,domains,release,deps,supply,bid)])
    counts=Counter(x["state"] for x in signals)
    return {"implementation_status":"implemented","live_monitoring":False,"authority":"promoted/canonical evidence only","promoted_runtime_release":(read_json(root/"contracts/parity/runtime-verification-baseline.json",{}) or {}).get("release_tag") or "unobserved","states":["control-observed","control-partial","control-unvalidated","mitigation-source-derived","evidence-stale","not-applicable"],"signals":signals,"state_counts":dict(sorted(counts.items())),"security_operational_health":(domains.get("security") or {}).get("operational_health","unvalidated"),"controls_verified":sum(1 for x in controls if x.get("status")=="control-observed"),"controls_source_derived":sum(1 for x in controls if x.get("status")=="mitigation-source-derived")}


def configuration_intelligence(config:list[dict[str,Any]])->list[dict[str,Any]]:
    out=[]
    for row in config:
        sources=row.get("source") or []
        joined=" ".join(sources).lower(); name=row["name"]
        if "tailscale" in name.lower(): purpose="Remote access/Tailnet runtime configuration"
        elif "nats" in name.lower(): purpose="NATS/JetStream connection or runtime configuration"
        elif "security" in name.lower(): purpose="Security scan/profile configuration"
        elif "backup" in name.lower() or "restic" in name.lower(): purpose="Backup/recovery configuration"
        elif "docs" in joined or "scripts/docs" in joined: purpose="Documentation/developer automation configuration"
        else: purpose="Pocket Lab runtime/development configuration discovered from source"
        owner="documentation tooling" if "scripts/docs" in joined else "frontend" if "src/" in joined else "bootstrap/runtime" if "bootstrap" in joined else "FastAPI/runtime" if "api_fastapi" in joined else "repository tooling"
        affected = sorted({"frontend" if "src/" in src.lower() else "FastAPI" if "api_fastapi" in src.lower() else "bootstrap/runtime" if "bootstrap" in src.lower() else "documentation" if "scripts/docs" in src.lower() or "mkdocs" in src.lower() else "repository tooling" for src in sources})
        out.append({**row,"purpose":purpose,"owner":owner,"required":"source-required where fail-closed code validates presence; otherwise optional/unvalidated","restart_required":"likely-runtime-restart" if owner in {"bootstrap/runtime","FastAPI/runtime"} else "no-runtime-restart-for-doc-tooling" if owner=="documentation tooling" else "source-dependent","affects_release":owner in {"bootstrap/runtime","FastAPI/runtime","frontend"},"affects_runtime":owner!="documentation tooling","affected_components":affected,"validation":"source-discovery + secret-value redaction; actual runtime value is never rendered","related_troubleshooting":["Development Troubleshooting","Production Troubleshooting"]})
    return out


def api_ui_traces(root:Path)->list[dict[str,Any]]:
    openapi=read_json(root/"contracts/generated/lite-openapi.json",{}) or {}; asyncapi=read_json(root/"contracts/generated/lite-asyncapi.json",{}) or {}; trace=read_json(root/"contracts/generated/knowledge/traceability.json",{}) or {}; trace_items=trace.get("items",[]) if isinstance(trace.get("items"),list) else []
    actions={"Add Device":["invite","bootstrap"],"Restart Agent":["restart"],"Install App":["/apps/","install"],"Open App":["catalog","/apps/"],"Run Security Check":["security/check"],"Back Up":["recovery/backup"],"Preview Restore":["restore/preview","preview"],"Restore":["restore"],"Remove Old Device":["remove","retire"]}
    source_files=list((root/"pocket-lab-final-structure/runtime/api_fastapi").rglob("*.py")); source_text={p:p.read_text(encoding="utf-8",errors="ignore") for p in source_files}
    frontend_files=list((root/"src").rglob("*.js"))+list((root/"src").rglob("*.jsx")); frontend_text={p:p.read_text(encoding="utf-8",errors="ignore") for p in frontend_files}
    subjects=list((asyncapi.get("channels") or {}).keys())
    rows=[]
    for action,keys in actions.items():
        endpoints=[]
        for path,methods in (openapi.get("paths") or {}).items():
            if any(k.lower() in path.lower() for k in keys):
                for method,spec in methods.items():
                    if method.lower() in {"get","post","put","patch","delete"} and isinstance(spec,dict): endpoints.append({"method":method.upper(),"path":path,"operation_id":spec.get("operationId")})
        endpoints=endpoints[:10]
        operation_ids=[x["operation_id"] for x in endpoints if x.get("operation_id")]
        backend=[]
        for oid in operation_ids:
            fn=oid.split("_api_lite",1)[0]
            for p,text in source_text.items():
                if f"def {fn}(" in text or f"async def {fn}(" in text: backend.append(str(p.relative_to(root)))
        front=[]
        for p,text in frontend_text.items():
            if any(e["path"].replace("{app_id}","")[:20] in text for e in endpoints): front.append(str(p.relative_to(root)))
        ev=[s for s in subjects if any(k.replace("/","").replace("-","") in s.replace(".","").replace("-","") for k in keys)][:10]
        tests=sorted({t for x in trace_items if isinstance(x,dict) and any(e["path"] in x.get("name","") for e in endpoints) for t in x.get("tests",[])})[:12]
        handler=sorted(set(backend)) or ["pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"]
        frontend=front or ["source-discovered UI call site unobserved; API remains authoritative"]
        event_bindings=ev or ["no exact channel binding source-derived for this action"]
        owner="FastAPI/Caddy read path" if action == "Open App" else "FastAPI → NATS/JetStream → worker"
        if action in {"Add Device","Restart Agent","Remove Old Device"}: owner="FastAPI → NATS/JetStream → node agent/supervisor"
        rows.append({"action":action,"ui_component":frontend,"frontend":frontend,"api":endpoints or [{"method":"unvalidated","path":"unvalidated","operation_id":None}],"fastapi_handler":handler,"backend_handler":handler,"nats_or_event":event_bindings,"events":event_bindings,"worker_agent_supervisor":"worker for queued domain actions; node agent/supervisor for device execution/recovery; exact owner remains endpoint-specific","execution_owner":owner,"result_event":"canonical lifecycle/event projection when declared","frontend_projection":"FastAPI/TanStack safe read projection","error_reason_codes":"contracts/generated/reason-codes.json","related_reason_codes":"contracts/generated/reason-codes.json","tests":tests or ["tests/backend/test_lite_api.py","tests/parity/test_api_contract_fences.py"],"evidence":"backend-owned sanitized evidence/projection","failure_states":["request rejected or backend unavailable","command undeliverable/timeout where asynchronous","backend result failed/blocked where operation is guarded"],"source_files":sorted(set(frontend+handler)),"implementation_status":"implemented"})
    return rows


def privacy_map(root:Path)->list[dict[str,Any]]:
    return [
      {"category":"SQLite durable state","source":"FastAPI/services/migrations","storage":"Pocket Lab SQLite","retention":"domain lifecycle policy; device/audit history retained independently from connectivity","sanitization":"not copied wholesale into docs; generated projections are bounded","access":"backend services/FastAPI","network_exposure":"same-origin API projection only","backup_behavior":"included according to Recovery policy","deletion_behavior":"explicit transactional lifecycle","privacy_risk":"identity/operational metadata","controls":["backend ownership","bounded projections","backup/recovery policy"]},
      {"category":"NATS/JetStream messages","source":"AsyncAPI/NATS bus","storage":"JetStream only where stream/durability is declared","retention":"stream policy","sanitization":"event/evidence payload redaction rules","access":"FastAPI/workers/agents; never browser direct","network_exposure":"private runtime/Tailnet only","backup_behavior":"not treated as primary durable backup state","deletion_behavior":"stream retention policy","privacy_risk":"command/event metadata","controls":["no browser NATS","sanitized lifecycle evidence"]},
      {"category":"Device identity","source":"durable enrollment registry","storage":"SQLite + device-local environment","retention":"until explicit retirement/rejoin lifecycle","sanitization":"tokens/secrets excluded from docs","access":"backend/device agent","network_exposure":"private control paths","backup_behavior":"identity metadata subject to recovery policy; invite secrets excluded","deletion_behavior":"explicit retirement/repair","privacy_risk":"device identifiers and enrollment state","controls":["fail-closed identity guard","no secret overwrite"]},
      {"category":"Promoted runtime evidence","source":"explicit sanitized Termux capture/promotion","storage":"contracts/parity/runtime-verification-baseline.json and generated projections","retention":"release/evidence lifecycle","sanitization":"required before promotion","access":"repository/docs generators","network_exposure":"none from MkDocs generation","backup_behavior":"repository history","deletion_behavior":"explicit evidence lifecycle","privacy_risk":"host/runtime metadata","controls":["explicit promotion","path/secret redaction"]},
      {"category":"Logs and audit events","source":"runtime services/audit store","storage":"runtime logs/durable audit store","retention":"bounded/operator policy","sanitization":"raw logs never rendered in normal docs","access":"backend/operator diagnostics","network_exposure":"not public","backup_behavior":"policy-dependent","deletion_behavior":"retention/rotation","privacy_risk":"operational context may contain identifiers","controls":["redacted summaries","backend-only evidence"]},
      {"category":"Backup metadata","source":"Recovery subsystem","storage":"SQLite/manifests/receipts","retention":"backup retention policy","sanitization":"repository/password/internal paths excluded","access":"FastAPI/worker","network_exposure":"safe summaries only","backup_behavior":"metadata accompanies verified recovery state","deletion_behavior":"explicit retention/cleanup","privacy_risk":"backup existence/timestamps","controls":["restic secret isolation","restore preview/confirmation"]},
      {"category":"Security scanner evidence","source":"Termux bounded profiles or WSL2/CI supply-chain capture","storage":"raw transient .pocketlab-dev then sanitized canonical summaries","retention":"raw transient; promoted summary explicit","sanitization":"raw findings/paths/secrets excluded from docs","access":"worker/developer CI then generated docs summary","network_exposure":"none required by docs","backup_behavior":"canonical summaries may be versioned","deletion_behavior":"raw capture removable after promotion","privacy_risk":"scanner output may reveal paths/secrets","controls":["normalizer","redaction","explicit promotion"]},
      {"category":"App metadata","source":"App Catalog/PhotoPrism lifecycle","storage":"SQLite/app configuration/runtime","retention":"app lifecycle policy","sanitization":"credentials/media paths excluded","access":"FastAPI/worker/app runtime","network_exposure":"same-origin /apps route and safe API","backup_behavior":"app settings/metadata per Recovery policy","deletion_behavior":"explicit remove lifecycle","privacy_risk":"app/media configuration","controls":["same-origin routing","backend-owned actions"]},
      {"category":"Release evidence","source":"Git/release workflow/SBOM/provenance","storage":"repository + release artifacts","retention":"release history","sanitization":"no credentials/private paths","access":"developers/operators","network_exposure":"GitHub release only when explicitly published","backup_behavior":"release archive","deletion_behavior":"release governance","privacy_risk":"low; build metadata","controls":["checksums","Cosign workflow","SLSA-style metadata without unsupported level claims"]},
    ]


def fmea(root:Path,deps:list[dict[str,Any]])->list[dict[str,Any]]:
    reason_data=read_json(root/"contracts/generated/reason-codes.json",{}) or {}; reasons=reason_data.get("reason_codes",[]) or []
    out=[]; seen=set()
    severity_definitions={
      "critical":"control-plane safety, durable state, or recovery ownership can be lost; immediate operator attention is warranted",
      "high":"a primary user capability can be blocked or materially degraded until recovery succeeds",
      "moderate":"a bounded capability can degrade while core control-plane safety remains intact",
      "low":"limited operator inconvenience with no expected control-plane safety impact",
    }
    for d in deps:
        key=(d.get("domain"),d.get("dependency"));
        if key in seen: continue
        seen.add(key); dep=str(d.get("dependency")); low=dep.lower()
        automatic="reconnect/retry" if "nats" in low else "supervisor recovery" if "agent" in low or "supervisor" in low else "backend-owned retry/readiness guard where implemented"
        severity="high" if d.get("blocking") else "moderate"
        out.append({"component":dep,"failure_mode":f"{dep} unavailable, stale or disconnected","detection":d.get("evidence_authority"),"reason_codes":[str(x.get("code") or x.get("id")) for x in reasons if isinstance(x,dict) and any(w in stable(x).lower() for w in re.findall(r"[a-z]+",low))][:8],"user_impact":f"{d.get('domain')} may degrade, block writes or become unavailable","automatic_recovery":automatic,"manual_recovery":"follow the matching production incident runbook; do not infer destructive commands","evidence":d.get("root_cause"),"severity":severity,"severity_definition":severity_definitions[severity],"occurrence":"not numerically scored without canonical incident frequency evidence","detectability":"evidence-dependent","residual_risk":"human review; no arbitrary RPN","human_review_required":True,"input_evidence":["contracts/generated/documentation-intelligence/dependency-health.json","contracts/generated/reason-codes.json","pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py","contracts/generated/lite-asyncapi.json","contracts/generated/lite-openapi.json","contracts/generated/recovery-contract.json"],"implementation_status":"implemented"})
    return out

def reliability(root:Path)->list[dict[str,Any]]:
    health=read_json(root/"contracts/generated/runtime/domain-operational-health.json",{}) or {}; domains=health.get("domains") or {}
    gates=read_json(root/"contracts/generated/parity/validation-gates.json",{}) or {}
    gate_by_id={str(x.get("id")):x for x in (gates.get("items") or []) if isinstance(x,dict) and x.get("id")}
    def objective_state(value:Any)->str:
        if not isinstance(value,dict): return "unknown"
        flattened=stable(value).lower()
        if value.get("freshness")=="stale" or any(x in flattened for x in ['degraded','offline','unavailable','failed','blocked','stale']): return "degraded"
        if any(x in flattened for x in ['healthy','ready','online','observed','verified','pass']): return "pass"
        return "unknown"
    stale=any((x or {}).get("freshness")=="stale" for x in domains.values() if isinstance(x,dict))
    docs_gate=gate_by_id.get("docs-parity",{})
    return [
      {"objective":"heartbeat freshness","target":"Devices canonical freshness threshold","latest_promoted_observation":(domains.get("devices") or {}).get("freshness") or "unobserved","status":objective_state(domains.get("devices")),"evidence":"contracts/generated/runtime/domain-operational-health.json"},
      {"objective":"API availability expectations","target":"FastAPI/Caddy dependencies observed healthy for normal read/control paths","latest_promoted_observation":(domains.get("home") or {}).get("operational_health") or "unobserved","status":objective_state(domains.get("home")),"evidence":"promoted Home operational health"},
      {"objective":"command delivery latency","target":"bounded command-delivery latency is measured only when promoted command timing evidence exists; readiness alone is not treated as latency","latest_promoted_observation":"unobserved" if not (domains.get("devices") or {}).get("command_delivery_latency") else (domains.get("devices") or {}).get("command_delivery_latency"),"status":"unknown" if not (domains.get("devices") or {}).get("command_delivery_latency") else objective_state(domains.get("devices")),"evidence":"promoted Devices operational health / command evidence when present"},
      {"objective":"supervisor recovery time","target":"recovery duration is reported only from promoted supervisor recovery timing evidence","latest_promoted_observation":"unobserved" if not (domains.get("devices") or {}).get("supervisor_recovery_time") else (domains.get("devices") or {}).get("supervisor_recovery_time"),"status":"unknown" if not (domains.get("devices") or {}).get("supervisor_recovery_time") else objective_state(domains.get("devices")),"evidence":"promoted Devices operational health / supervisor recovery evidence when present"},
      {"objective":"runtime evidence freshness","target":"promoted evidence freshness remains explicit per-domain","latest_promoted_observation":health.get("promoted_at") or "unobserved","status":"degraded" if stale else "pass" if domains else "unknown","evidence":"promoted operational-health contract"},
      {"objective":"documentation determinism","target":"zero drift on consecutive generator checks","latest_promoted_observation":docs_gate.get("status") or "unobserved","status":"pass" if docs_gate.get("status")=="verified" else "unknown","evidence":docs_gate.get("evidence") or "task lite:docs:enterprise:check"},
    ]

def state_from_health(d:Any)->str:
    if not isinstance(d,dict): return "control-unvalidated"
    if d.get("freshness")=="stale": return "evidence-stale"
    return "control-observed" if d.get("runtime_status")=="observed" else "control-partial"


def adr_intelligence(root:Path)->dict[str,Any]:
    data=read_json(root/"contracts/generated/knowledge/adrs.json",{}) or {}; raw=data.get("items",[]) or []
    items=[]
    for item in raw:
        if not isinstance(item,dict):
            continue
        sources=list(item.get("source_refs") or [])
        items.append({**item,
            "decision": item.get("name") or item.get("description") or item.get("id"),
            "selected_approach": item.get("description") or item.get("name"),
            "reason": item.get("context") or "source-derived context",
            "affected_components": sorted({Path(x).parts[0] if isinstance(x,str) and x else "unvalidated" for x in sources}),
            "related_risks": list(item.get("security_implications") or []) + list(item.get("trade_offs") or []),
            "related_threats": ["Threat Model cross-reference required where the decision affects a modeled trust boundary"],
            "tests": ["tests/docs/test_enterprise_completion.py"],
            "release_introduced": "source-history-derived only when a canonical release attribution exists; otherwise unvalidated",
            "superseded_by": item.get("superseded_by") or None,
            "implementation_status": "implemented",
        })
    relationships=[]
    for i,a in enumerate(items):
        arefs=set(a.get("source_refs") or [])
        for b in items[i+1:]:
            shared=sorted(arefs & set(b.get("source_refs") or []))
            if shared: relationships.append({"from":a.get("id"),"to":b.get("id"),"relationship":"shared-source-context","source_refs":shared})
    return {"implementation_status":"implemented","evidence_status":"source-derived","entities":items,"relationships":relationships,"fields":["decision","context","alternatives","selected approach","reason","consequences","affected components","related risks","related threats","tests","release introduced","superseded-by"],"live_state":False}


def ownership(root:Path)->list[dict[str,Any]]:
    rows=[
      {"capability":"Control API","source_owner":"FastAPI routers/services","runtime_owner":"pocket-api","recovery_owner":"core supervisor/operator","control_owner":"FastAPI","presentation_owner":"React/Vite PWA","evidence_owner":"API/runtime projections","source_refs":["pocket-lab-final-structure/runtime/api_fastapi/"],"architecture":["Architecture → Control plane"],"threats":["control-api"],"tests":["tests/backend/test_lite_api.py","tests/parity/"]},
      {"capability":"Messaging and command execution","source_owner":"NATS bus/domain commands","runtime_owner":"NATS/JetStream + worker","recovery_owner":"worker consumer supervision/core supervisor","control_owner":"FastAPI","presentation_owner":"FastAPI projection to UI","evidence_owner":"events/audit/command state","source_refs":["pocket-lab-final-structure/runtime/api_fastapi/services/nats_bus.py","pocket-lab-final-structure/runtime/workers/pocketlab_worker.py"],"architecture":["Architecture → Event and execution"],"threats":["messaging-execution"],"tests":["tests/backend/test_nats_required.py","tests/backend/test_lite_worker_recovery.py"]},
      {"capability":"Managed devices","source_owner":"fleet/device services","runtime_owner":"node agent","recovery_owner":"agent supervisor","control_owner":"FastAPI","presentation_owner":"Devices UI","evidence_owner":"heartbeats/fleet/recovery evidence","source_refs":["pocket-lab-final-structure/runtime/agents/"],"architecture":["Architecture → Device runtime"],"threats":["managed-device"],"tests":["tests/backend/test_lite_api.py"]},
      {"capability":"Security","source_owner":"Security policy/services","runtime_owner":"worker + bounded Lynis/Trivy profiles","recovery_owner":"worker consumer recovery/supervisor","control_owner":"FastAPI","presentation_owner":"Security UI","evidence_owner":"sanitized Security projection","source_refs":["pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py"],"architecture":["Architecture → Security boundaries"],"threats":["server-host","managed-device","application-container"],"tests":["tests/backend/test_lite_security.py","tests/backend/test_lite_api.py"]},
      {"capability":"Recovery","source_owner":"Recovery/backup services","runtime_owner":"worker/restic","recovery_owner":"Recovery workflow/operator","control_owner":"FastAPI","presentation_owner":"Recovery UI","evidence_owner":"backup/verify/preview/checkpoint receipts","source_refs":["pocket-lab-final-structure/runtime/api_fastapi/services/lite_backup.py"],"architecture":["Architecture → Durable state"],"threats":["durable-state"],"tests":["tests/backend/test_lite_recovery.py","tests/parity/test_backup_recovery_parity.py"]},
      {"capability":"Documentation Platform","source_owner":"canonical metadata/generators","runtime_owner":"none","recovery_owner":"developer/CI regeneration","control_owner":"deterministic generators","presentation_owner":"MkDocs","evidence_owner":"source + canonical/promoted evidence","source_refs":["scripts/docs/","contracts/metadata/documentation-platform.json"],"architecture":["Documentation Platform → Generation pipeline"],"threats":["external-release"],"tests":["tests/docs/"]},
      {"capability":"Supply-chain automation","source_owner":"tool metadata + automation scripts","runtime_owner":"WSL2/CI only","recovery_owner":"developer/CI rerun from verified cache","control_owner":"explicit capture/promote tasks","presentation_owner":"generated Supply Chain/Release docs","evidence_owner":"sanitized canonical supply-chain contracts","source_refs":["contracts/metadata/documentation-security-tools.json","scripts/docs/enterprise/supply_chain_automation.py"],"architecture":["Architecture → External release","Documentation Platform → Evidence model"],"threats":["external-release"],"tests":["tests/docs/test_enterprise_completion.py"]},
    ]
    return rows

def validation_coverage(root:Path)->dict[str,Any]:
    task_text="\n".join(p.read_text(encoding="utf-8",errors="ignore") for p in [root/"Taskfile.yml",*sorted((root/"tasks").glob("Taskfile*.yml"))])
    gate_doc=read_json(root/"contracts/generated/parity/validation-gates.json",{}) or {}
    gates=[x for x in (gate_doc.get("items") or []) if isinstance(x,dict)]
    by_id={str(x.get("id")):x for x in gates if x.get("id")}
    openapi=read_json(root/"contracts/parity/openapi-baseline-promotion.json",{}) or {}
    runtime=read_json(root/"contracts/parity/runtime-verification-baseline.json",{}) or {}
    supply=root/"contracts/generated/supply-chain"
    specs=[
      ("backend tests",["pytest","test_lite_api"],["parity-backend","parity-api"],[]),
      ("parity",["parity"],["release-readiness","parity-contracts","parity-selectors"],[]),
      ("Playwright",["playwright"],["parity-playwright-mocked","parity-playwright-live"],[]),
      ("accessibility",["a11y"],["parity-a11y"],[]),
      ("OpenAPI",["openapi"],["api-breaking"],["contracts/parity/openapi-baseline-promotion.json"]),
      ("Schemathesis",["schemathesis"],["api-schemathesis"],[]),
      ("oasdiff",["oasdiff","breaking-changes"],["api-breaking"],[]),
      ("architecture drift",["architecture","check"],[],["contracts/generated/architecture-catalog.json"]),
      ("knowledge determinism",["knowledge","check"],[],["contracts/generated/knowledge/index.json"]),
      ("runtime evidence",["runtime","compare"],[],["contracts/parity/runtime-verification-baseline.json"]),
      ("SBOM",["supply-chain","capture"],[],["contracts/generated/supply-chain/sbom-dev.cdx.json"]),
      ("vulnerability analysis",["security-tools","supply-chain"],[],["contracts/generated/supply-chain/vulnerability-correlation.json"]),
      ("secret scanning",["gitleaks","supply-chain"],[],["contracts/generated/supply-chain/security-analysis.json"]),
      ("static analysis",["semgrep","supply-chain"],[],["contracts/generated/supply-chain/security-analysis.json"]),
      ("documentation strict build",["mkdocs","--strict"],["docs-parity"],[]),
    ]
    rank={"verified":5,"promoted":5,"patch-provided":4,"partial":3,"unvalidated":2,"unobserved":1}
    rows=[]
    for name,tokens,ids,files in specs:
        present=all(t.lower() in task_text.lower() for t in tokens)
        evidence=[]; statuses=[]
        for gid in ids:
            gate=by_id.get(gid)
            if gate:
                statuses.append(str(gate.get("status") or "unobserved")); evidence.append({"kind":"validation-gate","id":gid,"status":gate.get("status"),"evidence":gate.get("evidence"),"task":gate.get("task")})
        for rel in files:
            path=root/rel
            if path.exists():
                status="observed"
                if rel.endswith("openapi-baseline-promotion.json"): status=str(openapi.get("status") or "observed")
                elif rel.endswith("runtime-verification-baseline.json"): status="promoted" if runtime.get("promoted_at") else str(runtime.get("status") or "observed")
                evidence.append({"kind":"canonical-artifact","path":rel,"status":status}); statuses.append(status)
        latest=max(statuses,key=lambda x:rank.get(x,3)) if statuses else "unobserved"
        rows.append({"name":name,"implementation_status":"implemented","gate_discoverable":present,"latest_verified_status":latest,"canonical_evidence":evidence,"source":"Taskfiles + recorded canonical contracts only","live_polling":False})
    return {"implementation_status":"implemented","status":"repository-evidence-only","checks":rows,"rule":"never poll CI; never claim current PASS without recorded canonical output"}

def change_advisor()->dict[str,Any]:
    rules=[
      ("pocket-lab-final-structure/runtime/api_fastapi/",["OpenAPI","API/UI trace","Schemathesis","parity","reason codes","events","docs","release compatibility"],["lite:api:check","lite:api:schemathesis","lite:api:breaking-changes","lite:docs:check","lite:check"],["backend/API","security when auth/evidence changes"]),
      ("src/",["frontend build","API usage","Playwright","accessibility","safe snapshots","documentation"],["lite:test:frontend","lite:test:e2e:mocked","lite:test:a11y","lite:docs:check"],["frontend","backend API owner for contract changes"]),
      ("pocket-lab-final-structure/runtime/agents/",["device commands","heartbeats","supervisor recovery","fleet states","threat model"],["lite:check","lite:docs:check"],["device runtime","security"]),
      ("pocket-lab-final-structure/runtime/workers/",["command execution","NATS consumers","evidence","runbooks","FMEA"],["lite:check","lite:docs:check"],["worker runtime","security"]),
      ("pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/",["Android/Termux bootstrap","identity","Caddy/Tailscale","release","threat model"],["bash -n","lite:docs:check","lite:check"],["bootstrap/runtime","security"]),
      ("contracts/",["generated contracts","knowledge","parity","release delta","documentation"],["lite:contracts:check","lite:docs:check"],["contract owner"]),
      ("scripts/docs/",["generated docs","determinism","page anatomy","MkDocs"],["lite:docs:sync","lite:docs:check"],["documentation platform"]),
      ("security/",["static analysis","controls","threat model","supply-chain evidence"],["lite:docs:supply-chain:capture","lite:docs:check"],["security"]),
      (".github/workflows/",["release provenance","Scorecard","token permissions","release evidence"],["lite:release:dry-run","lite:docs:check"],["release/security"]),
    ]
    return {"implementation_status":"implemented","executes_changes":False,"inputs":["source path graph","API/event contracts","test ownership","documentation graph","architecture/trust boundaries","security controls","release contract","runtime/promoted evidence metadata"],"algorithm":"bounded deterministic prefix/rule intersection; no ML and no runtime mutation","rules":[{"path_prefix":p,"potential_impacts":i,"recommended_tests_tasks":t,"generated_artifacts":["Documentation Intelligence","Release Delta","Knowledgebase"] if "docs" in p or "contracts" in p else ["Release Delta","Change Impact"],"required_reviews":r,"security_review":"required" if "security" in " ".join(i).lower() or "bootstrap" in p or "workflows" in p else "risk-based"} for p,i,t,r in rules]}

def upgrade_migration(root:Path,delta:dict[str,Any])->dict[str,Any]:
    baseline=(delta.get("from") or {}).get("tag") if isinstance(delta.get("from"),dict) else None
    current=(delta.get("to") or {}).get("tag") if isinstance(delta.get("to"),dict) else None
    migration=[x for x in delta.get("dimensions",[]) if x.get("dimension")=="sqlite-schema-migrations"]
    dep=[x for x in delta.get("dimensions",[]) if x.get("dimension")=="dependency-versions"]
    return {"implementation_status":"implemented","status":"comparable" if baseline and current else "not-comparable","from_release":baseline,"to_release":current or "not-comparable","database_migrations":migration,"agent_compatibility":"review agent/supervisor and bootstrap source changes in release delta","runtime_changes":"compare only promoted runtime evidence; repository HEAD is never treated as a release baseline","backup_requirement":"run/verify recovery backup according to release policy before destructive migration/update","breaking_api_changes":"use existing oasdiff evidence plus OpenAPI release-delta dimension","config_changes":"Configuration Intelligence + verified release-to-release delta","dependency_changes":dep,"rollback":"release rollback contract + verified backup/checkpoint where state changes","known_risks":"Known Limitations + FMEA + Threat Model","verification":["task lite:api:breaking-changes","task lite:docs:check","task lite:check"]}


def disaster_recovery()->list[dict[str,Any]]:
    scenarios=[("server phone lost",["release artifacts","external verified backups"],["unreplicated local state"],["replacement Termux host","release identity","backup verification"]),("secondary device lost",["server durable enrollment/audit history"],["device-local data not backed up"],["retire stale identity","explicit rejoin"]),("SQLite corrupted",["release artifacts","verified backup"],["unbacked durable state"],["stop writes","restore verified backup","run parity/health"]),("NATS unavailable",["SQLite durable state","agents may retain local state"],["in-flight delivery until recovery"],["restore NATS/JetStream","verify consumer health","reconcile commands"]),("Tailscale unavailable",["local control plane"],["remote access during outage"],["restore tailscaled/Tailnet","verify Tailnet IPv4 and NATS reachability"]),("PhotoPrism unavailable",["Pocket Lab control state","app backup metadata"],["unbacked app-local changes"],["check route/runtime","repair non-destructively","restore only after preview"]),("bad release",["last-known-good release","backup/checksums"],["changes after bad release if unbacked"],["rollback release","verify API/UI/runtime parity"]),("failed update",["checkpoint/backup","release evidence"],["partial uncheckpointed app/runtime mutation"],["follow explicit update rollback","verify health and evidence"])]
    return [{"scenario":s,"what_survives":surv,"what_is_lost":lost,"recoverability":"recoverable when listed prerequisites are verified; otherwise evidence-limited","dependency_order":["durable state/release identity","FastAPI/Caddy","NATS/worker","agent/supervisor","Tailscale","apps"],"required_evidence":req,"recovery_steps":["preserve sanitized evidence","follow matching incident/recovery runbook","avoid identity/secret overwrite","verify each dependency before advancing"],"verification":["health/readiness","parity","device/app/recovery readiness"],"rollback":"use last-known-good release/backup and explicit domain rollback","implementation_status":"implemented"} for s,surv,lost,req in scenarios]


def troubleshooting() -> list[dict[str,Any]]:
    scenarios=[
      ("API unavailable","Lite API cannot be reached","FastAPI/Caddy or local dependency unavailable","API unavailable"),("NATS unavailable","write paths cannot safely deliver commands","NATS/JetStream unavailable","NATS unavailable"),("JetStream problem","durable command/event flow degrades","consumer/stream health degraded","JetStream problem"),("agent offline","device appears Offline","heartbeat/NATS/Tailscale interruption","Agent offline"),("agent stopped","device reports Agent stopped","PM2 node-agent process stopped","Agent stopped"),("supervisor absent","automatic agent recovery unavailable","supervisor process absent","Supervisor absent"),("Tailscale unavailable","Remote access not ready","tailscaled/Tailnet readiness issue","Tailscale unavailable"),("PhotoPrism unavailable","app route does not open","PhotoPrism runtime/Caddy route issue","PhotoPrism unavailable"),("backup stale","latest backup evidence is old","backup execution/freshness issue","Backup stale"),("restore blocked","restore cannot proceed","preview/checkpoint/health guard unsatisfied","Restore blocked"),("security scan stuck","Safety Check does not advance","worker/consumer/scanner issue","Security scan stuck"),("Caddy routing issue","same-origin route fails","Caddy configuration/runtime issue","Caddy routing issue"),("release mismatch","installed/runtime release identities differ","source/release/runtime binding not converged","Release mismatch"),("runtime evidence stale","docs show an old promoted observation","new capture has not been explicitly promoted","Runtime evidence stale"),("docs generation drift","lite:docs:check reports drift","generated artifacts are out of sync or generator nondeterministic","Docs generation drift"),("parity mismatch","semantic/runtime parity differs","backend/frontend/runtime contract divergence","Parity mismatch")]
    checks={"API unavailable":[("curl -fsS http://127.0.0.1:8443/api/lite/status","READ_ONLY"),("pm2 status","READ_ONLY")],"NATS unavailable":[("pm2 status","READ_ONLY"),("ss -ltnp","READ_ONLY")],"Tailscale unavailable":[("tailscale status","READ_ONLY"),("tailscale ip -4","READ_ONLY")],"docs generation drift":[("task lite:docs:enterprise:check","READ_ONLY"),("git diff --check","READ_ONLY")],"parity mismatch":[("task lite:parity:runtime:compare","READ_ONLY")]}
    default=[("pm2 status","READ_ONLY"),("pm2 logs <process> --lines 80","READ_ONLY")]
    out=[]
    for scenario,symptom,cause,title in scenarios:
        safe_checks=[{"command":c,"class":k} for c,k in checks.get(scenario,default)]
        out.append({"scenario":scenario,"title":title,"trigger":symptom,"symptom":symptom,"impact":"affected capability may be unavailable, degraded, stale or safely blocked","urgency":"high" if scenario in {"API unavailable","NATS unavailable","JetStream problem","restore blocked"} else "moderate","interpretation":cause,"likely_causes":[cause],"known_evidence":["canonical operational health","dependency health","promoted runtime comparison"],"safe_checks":safe_checks,"expected_result":"compare read-only output with canonical health/readiness contract; preserve discrepancy","next_diagnostic_step":"open related generated runbook and follow dependency-specific checks","decision_tree":["If read-only health proves dependency unavailable → follow its reviewed recovery path","If state is stale but service healthy → refresh/capture through existing explicit workflows","If ownership is unclear → stop and escalate; do not improvise destructive repair"],"repair_options":"only canonical SAFE_REPAIR procedures; generator never invents repair commands","verification":"rerun read-only health plus relevant parity/docs/domain checks","rollback":"use release/recovery runbook when a prior change caused the issue","when_not_to_act":["when evidence is stale/ambiguous","when action would overwrite identity or secrets","when healthy online device removal is not explicitly approved"],"do_not_do":["do not bypass FastAPI/NATS ownership","do not overwrite device identity","do not expose secrets","do not run destructive commands inferred from documentation"],"evidence_to_preserve":["sanitized API status","PM2 status metadata","promoted runtime comparison","relevant reason codes"],"related_runbook":f"generated/enterprise/operate/runbooks/{re.sub('[^a-z0-9]+','-',scenario.lower()).strip('-')}.md","escalation":"escalate to the source/runtime owner when safe checks do not establish a reviewed repair path","implementation_status":"implemented"})
    return out


def documentation_quality(root:Path)->list[dict[str,Any]]:
    op=read_json(root/"contracts/generated/runtime/domain-operational-health.json",{}) or {}; domains=op.get("domains") or {}
    allowed={"complete","partial","missing","not-applicable"}; rows=[]
    for domain in ["home","apps","devices","security","recovery","identity","rules"]:
        api="partial" if domain in {"identity","rules"} else "complete"
        evidence="complete" if domain in domains else "partial"
        row={"domain":domain,"architecture_documented":"complete","api_documented":api,"events_documented":"complete","runbook_present":"complete","threat_model_present":"complete","operational_health_modeled":"complete" if domain in domains else "partial","evidence_coverage":evidence,"troubleshooting":"complete","release_impact":"complete","ownership":"complete","privacy_map":"complete","quality":"partial" if api=="partial" else "complete","implementation_status":"implemented"}
        if any(row[k] not in allowed for k in ["architecture_documented","api_documented","events_documented","runbook_present","threat_model_present","operational_health_modeled","evidence_coverage","troubleshooting","release_impact","ownership","privacy_map","quality"]): raise RuntimeError("documentation quality vocabulary drift")
        rows.append(row)
    return rows

def contribution_matrix()->list[dict[str,Any]]:
    definitions={
      "Backend API":(["pocket-lab-final-structure/runtime/api_fastapi/","tests/backend/"],["OpenAPI","parity","reason codes","event metadata"],["backend/API owner","security when authorization/evidence changes"]),
      "Frontend":(["src/","tests/e2e/","tests/docs/"],["frontend API usage","safe snapshots","UX/documentation contracts"],["frontend owner","API owner when contracts change"]),
      "SQLite migration":(["pocket-lab-final-structure/runtime/api_fastapi/migrations/","tests/backend/"],["SQLite schema","migration inventory","backup/recovery"],["durable-state owner","recovery reviewer"]),
      "NATS/event":(["pocket-lab-final-structure/runtime/api_fastapi/services/nats_bus.py","contracts/events/"],["AsyncAPI","event encyclopedia","delivery/reason contracts"],["messaging owner","security"]),
      "Worker":(["pocket-lab-final-structure/runtime/workers/"],["commands","events","evidence","runbooks"],["worker owner","security"]),
      "Node agent":(["pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py"],["device capability","heartbeat","command/evidence contracts"],["device-runtime owner","security"]),
      "Supervisor":(["pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py"],["recovery","reason codes","device health"],["device-runtime owner","recovery reviewer"]),
      "Security scanner":(["pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py","scripts/docs/enterprise/supply_chain_automation.py","security/"],["security evidence","Threat Model","SBOM/vulnerability evidence"],["security owner"]),
      "Device bootstrap":(["pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/"],["invite/bootstrap","identity","runtime configuration"],["bootstrap owner","security"]),
      "Tailscale":(["pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/","architecture/metadata/"],["remote-access readiness","Threat Model","dependency health"],["network/runtime owner","security"]),
      "Application integration":(["pocket-lab-final-structure/runtime/api_fastapi/services/lite_app_actions.py","src/lite/"],["app lifecycle","routes","backup/security/recovery evidence"],["app owner","security/recovery as applicable"]),
      "Documentation generator":(["scripts/docs/","mkdocs.yml"],["generated documentation","source fingerprints","page anatomy"],["Documentation Platform owner"]),
      "Generated contracts":(["contracts/metadata/","schemas/"],["knowledge/parity/intelligence/release contracts"],["contract owner"]),
      "Release workflow":([".github/workflows/release-dist.yml","tasks/Taskfile.release.yml"],["release manifest","checksums","SBOM","signing/provenance"],["release owner","security"]),
    }
    rows=[]
    for change,(files,contracts,reviewers) in definitions.items():
        low=change.lower()
        rows.append({"change_type":change,"affected_files":files,"contracts":contracts,"tests":["focused owner tests","task lite:docs:check","task lite:check"],"documentation":["regenerate canonical generated outputs","review release/change impact","never hand-edit generated docs"],"evidence":["source validation","promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth"],"security_review":"required" if any(x in low for x in ["security","bootstrap","tailscale","release","nats","agent","supervisor"]) else "risk-based","reviewers":reviewers,"review_checklist":["architecture boundary preserved","contracts updated before generated projections","focused tests added/updated","generated drift closed","evidence status truthful","no secrets/private paths exposed"],"common_mistakes":["editing generated output directly","claiming runtime truth from source alone","bypassing FastAPI/NATS ownership","recording PASS without validation output"]})
    return rows


def coverage_requirements()->list[dict[str,Any]]:
    names=[
      "Close five Documentation Experience gaps","Documentation Platform tab","Executable Task Reference","Contribution & Review onboarding","Event encyclopedia","Release evidence","Development diagnostic handbook","First-class generated threat model","Security Atlas deterministic projections","Production promoted threat posture","Production Living Knowledgebase","Dedicated Architecture","Production incident runbooks","Production troubleshooting","Configuration Intelligence","API-to-UI trace explorer","Data lifecycle & privacy map","FMEA/resilience catalog","SLO/reliability objectives","ADR intelligence","Dependency/software supply-chain inventory","Security controls catalog","Developer change simulator","Ownership/responsibility map","Validation coverage dashboard","Upgrade/migration intelligence","Disaster recovery architecture","Documentation quality scorecard","Threat Dragon integration","Syft/CycloneDX SBOM","Trivy integration","OSV-Scanner correlation","Grype corroboration","Dependency-Track optional export","OpenSSF Scorecard checks","ScanCode licensing","Gitleaks secrets","Semgrep Community rules","Graphviz architecture/flow diagrams","Event encyclopedia automation","Task reference automation","Contribution guidance automation","Troubleshooting diagnostic-fact automation","Incident runbook automation","Failure Mode and Effects Analysis","Release delta","Supply-chain change intelligence","Cosign artifact signing workflow","SLSA-style provenance","Heavy WSL2/CI execution","Lightweight Termux evidence boundary","Tool bootstrap/download","Output normalization","Page-anatomy enforcement" ]
    return [{"requirement":x,"implementation_status":"implemented","evidence_status":"implementation-verified-by-source-tests; observed security/release/runtime evidence remains independently classified","source_refs":["scripts/docs/enterprise/generate_enterprise_documentation.py","scripts/docs/enterprise/enterprise_completion.py","scripts/docs/enterprise/supply_chain_automation.py","scripts/dev/lite/documentation_security_tools.py"]} for x in names]


def flow_dot(title:str, rows:list[tuple[str,str]])->str:
    lines=["digraph flow {",'  graph [rankdir="LR", bgcolor="transparent", label="'+title.replace('"',"'")+'", labelloc="t"];','  node [shape="box", style="rounded,filled", fillcolor="#f8fafc"];']
    for i,(a,b) in enumerate(rows): lines.append(f'  n{i} [label="{a.replace(chr(34),chr(39))}"]; n{i} -> m{i}; m{i} [label="{b.replace(chr(34),chr(39))}"];')
    lines.append("}"); return "\n".join(lines)+"\n"


def flow_svg(title:str, rows:list[tuple[str,str]])->str:
    esc=lambda x:html.escape(str(x),quote=True); width=1080; row=54; height=70+max(1,len(rows))*row
    out=['<?xml version="1.0" encoding="UTF-8"?>',f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">','<style>.t{font-family:system-ui,sans-serif;fill:#101828}.h{font-size:17px;font-weight:700}.s{font-size:12px}.b{fill:#f8fafc;stroke:#98a2b3}.e{stroke:#667085;stroke-width:1.5}</style>',f'<text class="t h" x="24" y="30">{esc(title)}</text>']
    if not rows: rows=[("No source-derived rows","Unvalidated")]
    for i,(a,b) in enumerate(rows):
        y=50+i*row; out += [f'<rect class="b" x="24" y="{y}" width="420" height="36" rx="7"/>',f'<text class="t s" x="36" y="{y+23}">{esc(a[:62])}</text>',f'<line class="e" x1="444" y1="{y+18}" x2="610" y2="{y+18}"/>',f'<polygon points="610,{y+18} 600,{y+12} 600,{y+24}" fill="#667085"/>',f'<rect class="b" x="620" y="{y}" width="430" height="36" rx="7"/>',f'<text class="t s" x="632" y="{y+23}">{esc(b[:66])}</text>']
    out.append('</svg>'); return "\n".join(out)+"\n"


def render_supply_chain_change_page(change: dict[str, Any], *, table: Callable[..., str]) -> str:
    snapshot = change.get("current_snapshot") if isinstance(change, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    readiness = change.get("baseline_readiness") if isinstance(change, dict) else {}
    readiness = readiness if isinstance(readiness, dict) else {}
    sbom = snapshot.get("sbom") if isinstance(snapshot.get("sbom"), dict) else {}
    vulns = snapshot.get("vulnerabilities") if isinstance(snapshot.get("vulnerabilities"), dict) else {}
    licenses = snapshot.get("licenses") if isinstance(snapshot.get("licenses"), dict) else {}
    security = snapshot.get("security") if isinstance(snapshot.get("security"), dict) else {}
    posture = snapshot.get("repository_posture") if isinstance(snapshot.get("repository_posture"), dict) else {}
    package_cov = licenses.get("package_license_coverage") if isinstance(licenses.get("package_license_coverage"), dict) else {}
    deep_cov = licenses.get("deep_source_license_coverage") if isinstance(licenses.get("deep_source_license_coverage"), dict) else {}

    current_rows = [
        ["Capture status", "complete" if snapshot.get("capture_complete") else "partial/unobserved"],
        ["Run ID", snapshot.get("run_id") or "unobserved"],
        ["Source commit", snapshot.get("source_commit") or "unobserved"],
        ["Qualification surface", snapshot.get("qualification_surface") or "unobserved"],
        ["Development SBOM components", sbom.get("dev_components", 0)],
        ["Release SBOM components", sbom.get("release_components", 0)],
        ["Runtime SBOM components", sbom.get("runtime_components", 0)],
        ["Vulnerability evidence", f"{vulns.get('evidence_status', 'unobserved')} ({vulns.get('finding_count', 0)} normalized findings)"],
        ["Package-license coverage", f"{package_cov.get('status', 'unobserved')} via {package_cov.get('authority', 'unobserved')}"],
        ["Package rows", licenses.get("package_rows", 0)],
        ["Trivy license rows", licenses.get("trivy_license_rows", 0)],
        ["Deep source-license coverage", deep_cov.get("status", "unobserved")],
        ["Gitleaks findings", security.get("gitleaks_finding_count", 0)],
        ["Semgrep findings", security.get("semgrep_finding_count", 0)],
        ["Scorecard posture", posture.get("status", "unobserved")],
    ]
    tool_rows = [[x.get("step_id"), x.get("status"), x.get("exit_code"), x.get("duration_seconds")] for x in snapshot.get("tool_coverage", []) if isinstance(x, dict)]
    posture_rows = [[x.get("name"), x.get("status"), x.get("score"), x.get("reason")] for x in posture.get("checks", []) if isinstance(x, dict)]
    selected = readiness.get("selected_baseline") if isinstance(readiness.get("selected_baseline"), dict) else None
    baseline_rows = [
        ["Readiness", readiness.get("status") or "not-ready"],
        ["Verified candidates", readiness.get("candidate_count", 0)],
        ["Selected baseline", selected.get("tag") if selected else "none"],
        ["Selected commit", selected.get("commit") if selected else "none"],
        ["Policy", readiness.get("baseline_policy") or "verified canonical prior release required"],
        ["Reason", readiness.get("reason") or "not-comparable"],
    ]

    body = "# Supply-chain Change Intelligence\n\n"
    body += "Current promoted evidence and historical change are intentionally separate authorities. This page never reads transient scanner output and never fabricates an N-1 delta.\n\n"
    body += "## Current promoted snapshot\n\n" + table(["Signal", "Value"], current_rows) + "\n"
    body += "### Tool coverage\n\n" + (table(["Step", "Status", "Exit", "Duration (s)"], tool_rows) if tool_rows else "No promoted tool-status evidence is available.\n") + "\n"
    body += "### Repository posture\n\n" + (table(["Control", "Status", "Score", "Reason"], posture_rows) if posture_rows else "No promoted Scorecard posture is available.\n") + "\n"
    body += "## Baseline readiness\n\n" + table(["Signal", "Value"], baseline_rows) + "\n"
    body += "## Historical comparison\n\n"
    if change.get("status") != "comparable":
        body += "!!! info \"No comparable verified prior release\"\n    Current promoted supply-chain evidence is available, but no verified N-1 canonical release baseline satisfies the tag + commit + tree + ancestry policy. Dependency, vulnerability, license, and upstream deltas therefore remain explicitly not comparable.\n\n"
        empty_note = "Historical comparison unavailable until a verified canonical prior-release baseline exists.\n"
        body += "### Dependencies added\n\n" + empty_note + "\n"
        body += "### Dependencies removed\n\n" + empty_note + "\n"
        body += "### Versions changed\n\n" + empty_note + "\n"
        body += "### Vulnerability changes\n\n" + empty_note + "\n"
        body += "### License changes\n\n" + empty_note + "\n"
        body += "### Upstream posture changes\n\n" + empty_note + "\n"
        return body

    body += f"Compared **{change.get('from')}** → **{change.get('to', 'current-source')}** using verified canonical evidence.\n\n"
    body += "### Dependencies added\n\n" + (table(["Ecosystem", "Name", "Version"], [[x.get("ecosystem"), x.get("name"), x.get("version")] for x in change.get("dependencies_added", [])]) if change.get("dependencies_added") else "No dependency additions observed.\n") + "\n"
    body += "### Dependencies removed\n\n" + (table(["Ecosystem", "Name", "Version"], [[x.get("ecosystem"), x.get("name"), x.get("version")] for x in change.get("dependencies_removed", [])]) if change.get("dependencies_removed") else "No dependency removals observed.\n") + "\n"
    body += "### Versions changed\n\n" + (table(["Ecosystem", "Name", "From", "To"], [[x.get("ecosystem"), x.get("name"), x.get("from"), x.get("to")] for x in change.get("versions_changed", [])]) if change.get("versions_changed") else "No dependency version changes observed.\n") + "\n"
    body += "### Vulnerability changes\n\n"
    body += (table(["Direction", "ID"], [["new", x.get("id")] for x in change.get("new_vulnerabilities", [])] + [["resolved", x.get("id")] for x in change.get("resolved_vulnerabilities", [])]) if change.get("new_vulnerabilities") or change.get("resolved_vulnerabilities") else "No comparable vulnerability changes observed, or the historical canonical vulnerability artifact is unavailable.\n") + "\n"
    body += "### License changes\n\n"
    body += (table(["Direction", "License"], [["new", x.get("license")] for x in change.get("new_licenses", [])] + [["removed", x.get("license")] for x in change.get("removed_licenses", [])]) if change.get("new_licenses") or change.get("removed_licenses") else "No comparable license changes observed, or the historical canonical license artifact is unavailable.\n") + "\n"
    body += "### Upstream posture changes\n\n"
    body += (table(["Check", "From", "To"], [[x.get("check"), x.get("from"), x.get("to")] for x in change.get("upstream_posture_changes", [])]) if change.get("upstream_posture_changes") else "No comparable upstream posture changes observed, or the historical canonical Scorecard artifact is unavailable.\n") + "\n"
    body += "Scanner disagreement remains evidence, not an automatic release failure.\n"
    return body


def _html_text(value: Any, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, bool):
        value = "yes" if value else "no"
    if isinstance(value, (list, tuple, set)):
        value = ", ".join(str(x) for x in value) if value else fallback
    return html.escape(str(value))


def _chip_list(values: Iterable[Any], *, code: bool = False, empty: str = "None recorded") -> str:
    cleaned = [str(x).strip() for x in values if str(x).strip()]
    if not cleaned:
        return f'<span class="pl-chip pl-chip--muted">{html.escape(empty)}</span>'
    cls = "pl-chip pl-chip--code" if code else "pl-chip"
    return '<span class="pl-chip-list">' + "".join(f'<span class="{cls}">{html.escape(x)}</span>' for x in cleaned) + "</span>"


def _fact(label: str, value: Any, *, code: bool = False) -> str:
    rendered = _html_text(value)
    if code and rendered != "—":
        rendered = f"<code>{rendered}</code>"
    return f'<div class="pl-fact"><span>{html.escape(label)}</span><strong>{rendered}</strong></div>'


def render_production_troubleshooting(rows: list[dict[str, Any]]) -> str:
    body = "# Production Troubleshooting\n\n"
    body += '<div class="pl-page-lede"><strong>Diagnose first. Repair second.</strong><p>Start from the visible symptom, use read-only checks, and open the linked runbook before any mutating action. Commands remain classified so the page never turns into an unsafe copy/paste wall.</p></div>\n\n'
    body += '<div class="pl-troubleshooting-grid">\n'
    for row in rows:
        body += '<article class="pl-troubleshooting-card">'
        body += f'<div class="pl-card-kicker">Symptom</div><h2>{_html_text(row.get("title"))}</h2>'
        body += f'<p class="pl-card-lead">{_html_text(row.get("symptom"))}</p>'
        body += '<div class="pl-fact-grid">'
        body += _fact("Impact", row.get("impact")) + _fact("Interpretation", row.get("interpretation"))
        body += '</div>'
        checks = row.get("safe_checks") or []
        body += '<h3>Safe checks</h3><div class="pl-command-stack">'
        for check in checks:
            cmd = check.get("command") if isinstance(check, dict) else check
            body += f'<div class="pl-command"><code>{_html_text(cmd)}</code></div>'
        body += '</div>'
        body += '<details class="pl-disclosure pl-disclosure--compact"><summary>Decision details</summary><div class="pl-detail-list">'
        body += f'<div class="pl-detail-row"><div><strong>Expected result</strong></div><div>{_html_text(row.get("expected_result"))}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Next diagnostic step</strong></div><div>{_html_text(row.get("next_diagnostic_step"))}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Do not act when</strong></div><div>{_chip_list(row.get("when_not_to_act") or [])}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Runbook</strong></div><div><code>{_html_text(row.get("related_runbook"))}</code></div></div>'
        body += '</div></details></article>\n'
    body += '</div>\n'
    return body


def render_adr_intelligence_page(adr: dict[str, Any]) -> str:
    entities = adr.get("entities") or []
    body = "# ADR Intelligence\n\n"
    body += '<div class="pl-page-lede"><strong>Decisions, not just documents.</strong><p>Each architecture decision is presented with status, rationale, consequences and operational implications so reviewers can understand why the system is shaped this way.</p></div>\n\n'
    body += '<figure class="pl-generated-diagram pl-generated-diagram--contained"><img src="../../../assets/enterprise/adr-relationships.svg" alt="ADR relationship graph" loading="lazy"><figcaption>Relationship view across source-derived architecture decisions.</figcaption></figure>\n\n'
    body += '<div class="pl-adr-grid">\n'
    for row in entities:
        title = row.get("name") or row.get("id")
        body += '<article class="pl-adr-card">'
        body += f'<div class="pl-card-head"><div><span class="pl-card-kicker">Architecture decision</span><h2>{_html_text(title)}</h2></div><span class="pl-state-pill">{_html_text(row.get("status"))}</span></div>'
        body += f'<p class="pl-card-lead">{_html_text(row.get("context"))}</p>'
        body += '<div class="pl-fact-grid">'
        body += _fact("Selected approach", row.get("selected_approach") or row.get("decision"))
        body += _fact("Reason", row.get("reason"))
        body += '</div>'
        body += f'<h3>Consequences</h3>{_chip_list(row.get("consequences") or [])}'
        body += f'<h3>Trade-offs</h3>{_chip_list(row.get("trade_offs") or [])}'
        body += '<details class="pl-disclosure pl-disclosure--compact"><summary>Security, runtime and provenance</summary><div class="pl-detail-list">'
        body += f'<div class="pl-detail-row"><div><strong>Alternatives</strong></div><div>{_chip_list(row.get("alternatives") or [])}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Security implications</strong></div><div>{_chip_list(row.get("security_implications") or [])}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Runtime implications</strong></div><div>{_chip_list(row.get("runtime_implications") or [])}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Source</strong></div><div>{_chip_list(row.get("source_refs") or [], code=True)}</div></div>'
        body += '</div></details></article>\n'
    body += '</div>\n'
    return body


def render_api_ui_trace_page(rows: list[dict[str, Any]]) -> str:
    body = "# API-to-UI Trace Explorer\n\n"
    body += '<div class="pl-page-lede"><strong>Follow an action end to end.</strong><p>Trace user intent through UI ownership, FastAPI, messaging or execution, and the evidence that projects the result back to the interface.</p></div>\n\n'
    body += '<figure class="pl-generated-diagram pl-generated-diagram--contained"><img src="../../../assets/enterprise/api-ui-trace.svg" alt="API to UI relationship graph" loading="lazy"><figcaption>High-level relationship view; each trace below keeps exact source and evidence details on demand.</figcaption></figure>\n\n'
    body += '<div class="pl-trace-grid">\n'
    for row in rows:
        apis = [f"{x.get('method')} {x.get('path')}" for x in row.get("api") or [] if isinstance(x, dict)]
        ui = row.get("ui_component") or row.get("frontend") or []
        handlers = row.get("fastapi_handler") or row.get("backend_handler") or []
        events = row.get("nats_or_event") or row.get("events") or []
        body += '<article class="pl-trace-card">'
        body += f'<span class="pl-card-kicker">Action trace</span><h2>{_html_text(row.get("action"))}</h2>'
        stages = [
            ("UI", ", ".join(str(x) for x in ui) or "unobserved"),
            ("API", ", ".join(apis) or "unobserved"),
            ("Handler", ", ".join(str(x) for x in handlers) or "unobserved"),
            ("Execution", str(row.get("worker_agent_supervisor") or row.get("execution_owner") or "unobserved")),
            ("Projection", str(row.get("frontend_projection") or row.get("evidence") or "unobserved")),
        ]
        body += '<div class="pl-trace-flow">' + ''.join(f'<div><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>' for label, value in stages) + '</div>'
        body += '<details class="pl-disclosure pl-disclosure--compact"><summary>Events, failures, tests and evidence</summary><div class="pl-detail-list">'
        body += f'<div class="pl-detail-row"><div><strong>NATS / events</strong></div><div>{_chip_list(events, code=True)}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Reason / failure states</strong></div><div>{_html_text(row.get("error_reason_codes") or row.get("failure_states"))}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Tests</strong></div><div>{_chip_list(row.get("tests") or [], code=True)}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Source files</strong></div><div>{_chip_list(row.get("source_files") or [], code=True)}</div></div>'
        body += '</div></details></article>\n'
    body += '</div>\n'
    return body


def render_event_encyclopedia_page(rows: list[dict[str, Any]]) -> str:
    body = "# Event encyclopedia\n\n"
    body += '<div class="pl-page-lede"><strong>Understand the event contract before chasing a message.</strong><p>Subjects, owners, delivery semantics and UI consequences are separated so event flow remains auditable without exposing credentials or live broker state.</p></div>\n\n'
    body += '## Event flow model\n\n<figure class="pl-generated-diagram pl-generated-diagram--contained"><img src="../../../assets/enterprise/event-flows.svg" alt="Event flow model" loading="lazy"><figcaption>Source-derived publisher → subject → consumer relationships.</figcaption></figure>\n\n'
    body += '<div class="pl-event-grid">\n'
    for row in rows:
        body += '<article class="pl-event-card">'
        body += f'<div class="pl-card-head"><div><span class="pl-card-kicker">{_html_text(row.get("domain"))}</span><h2><code>{_html_text(row.get("nats_subject"))}</code></h2></div><span class="pl-state-pill">{_html_text(row.get("lifecycle"))}</span></div>'
        body += '<div class="pl-fact-grid">'
        body += _fact("Publisher", row.get("publisher")) + _fact("Consumers", row.get("consumers"))
        body += _fact("Durability", row.get("durability")) + _fact("Replay", row.get("replay"))
        body += '</div>'
        body += f'<h3>Delivery semantics</h3>{_chip_list([row.get("ordering"), row.get("idempotency"), row.get("acknowledgment")])}'
        body += '<details class="pl-disclosure pl-disclosure--compact"><summary>Schema, failure handling and evidence</summary><div class="pl-detail-list">'
        body += f'<div class="pl-detail-row"><div><strong>Schema</strong></div><div><code>{_html_text(row.get("schema"))}</code></div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Failure handling</strong></div><div>{_html_text(row.get("failure_handling"))}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Audit implications</strong></div><div>{_html_text(row.get("audit_implications"))}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>UI state</strong></div><div>{_html_text(row.get("ui_state"))}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Tests</strong></div><div>{_chip_list(row.get("tests") or [], code=True, empty="No exact source-derived test link")}</div></div>'
        body += f'<div class="pl-detail-row"><div><strong>Ownership</strong></div><div>{_chip_list(row.get("source_owner") or [], code=True)} <span class="pl-muted">runtime: {_html_text(row.get("runtime_owner"))}</span></div></div>'
        body += '</div></details></article>\n'
    body += '</div>\n'
    return body



def render_release_assurance_page(release: dict[str, Any], delta: dict[str, Any], *, table: Callable[..., str]) -> str:
    assurance = release.get("assurance", {})
    authorities = assurance.get("authorities", {})
    dims = assurance.get("dimensions", [])
    artifacts = release.get("artifacts", {})
    body = "# Release Assurance\n\n## Summary\n\n"
    body += '<div class="pl-page-lede"><strong>Release identity, runtime binding, artifact integrity and evidence gaps—kept as independent authorities.</strong><p>Local working-tree state is informational and cannot erase a verified release identity. MkDocs never polls GitHub or runtime.</p></div>\n\n'
    body += '<div class="pl-kpi-grid pl-release-kpis">'
    body += _fact("Assurance status", assurance.get("overall"))
    rel = authorities.get("release", {})
    runtime = authorities.get("runtime", {})
    body += _fact("Release identity", (rel.get("value") or {}).get("tag") or rel.get("status"))
    body += _fact("Runtime binding", (runtime.get("value") or {}).get("release_tag") or runtime.get("status"))
    body += _fact("Historical comparison", assurance.get("comparison_state"))
    body += '</div>\n\n'
    body += "## Release evidence\n\nRelease, runtime, supply-chain and local generation state are independent authorities. Missing evidence stays unobserved.\n\n## Evidence authorities\n\n"
    authority_labels={"release":"Release authority","runtime":"Runtime authority","supply_chain":"Supply-chain authority","local_repository":"Local repository authority"}
    body += table(["Authority", "Status", "Confidence", "Value", "Source"], [[authority_labels.get(name,name.replace("_"," ").title()), row.get("status"), row.get("confidence"), row.get("value"), row.get("source")] for name,row in authorities.items()])
    body += "\n## Assurance matrix\n\n"
    body += table(["Dimension", "Status", "Evidence"], [[x.get("id"),x.get("status"),x.get("evidence")] for x in dims])
    body += "\n## Artifact evidence\n\n"
    artifact_rows=[]
    for name,row in artifacts.items():
        artifact_rows.append([
            row.get("filename") or name, row.get("release_presence",{}).get("status"),
            row.get("integrity",{}).get("status"), (row.get("integrity",{}).get("value") or {}).get("verification"),
            row.get("binding",{}).get("status"), row.get("local_staging",{}).get("status")
        ])
    body += table(["Artifact","Release presence","Integrity","Verification detail","Binding","Local staging"],artifact_rows)
    body += "\n## Release delta\n\n"
    if delta.get("status") == "initial-canonical-comparison-baseline":
        body += "**Initial canonical comparison baseline.** Historical release-to-release comparison is intentionally unavailable until a second qualified release is promoted.\n"
    else:
        body += f"**{delta.get('status')}**. Release-to-release comparison requires two verified canonical release records and never falls back to release-to-HEAD.\n"
    body += "\n## Evidence gaps\n\n"
    gaps=release.get("evidence_gaps", [])
    body += table(["Dimension","Status","Why"],[[x.get("dimension"),x.get("status"),x.get("reason")] for x in gaps]) if gaps else "No assurance evidence gaps are currently recorded.\n"
    body += "\n## Known limitations\n\n"
    limitations=release.get("known_limitations", [])
    body += table(["Area","Type","Limitation","Implementation","Health"],[[x.get("label"),x.get("category"),x.get("description"),x.get("implementation_status"),x.get("operational_health")] for x in limitations]) if limitations else "No active canonical limitations are available.\n"
    body += "\n## Evidence lineage\n\n"
    body += '<div class="pl-lineage">'
    for i,row in enumerate(release.get("lineage", [])):
        if i: body += '<span aria-hidden="true">→</span>'
        body += f'<div><strong>{_html_text(row.get("from"))} → {_html_text(row.get("to"))}</strong><span><code>{_html_text(row.get("source"))}</code></span></div>'
    body += '</div>\n\n'
    body += "## Compatibility\n\n" + ", ".join(release.get("device_compatibility", [])) + ".\n\n"
    body += "## Validation outcomes\n\n" + str(release.get("validation_outcomes")) + ". This page does not poll GitHub Actions or runtime.\n\n"
    body += "## Provenance\n\nCosign/signature and SLSA-style provenance remain evidence dimensions. No formal SLSA level is claimed unless separately promoted evidence supports it.\n"
    return body


def render_threat_model_page(
    threat: dict[str, Any],
    atlas: dict[str, Any],
    *,
    table: Callable[..., str],
    heading: str = "Threat Model",
    asset_prefix: str = "../../assets/enterprise",
) -> str:
    posture=threat.get("production_posture", {})
    viz=threat.get("visualization", {})
    summary=viz.get("posture_summary", {})
    body=f"# {heading}\n\n"
    body += threat_model_nav(nested=True) + "\n\n"
    body += '<div class="pl-page-lede"><strong>Architecture-aware threat reasoning backed by promoted evidence.</strong><p>This is not live monitoring. Animated paths represent modeled control/evidence flow, never observed network traffic or active attacks.</p></div>\n\n'
    body += '## Current promoted threat posture\n\n'
    body += '<div class="pl-kpi-grid pl-threat-kpis">'
    control_states=summary.get("control_states", {})
    posture_states=summary.get("posture_states", {})
    evidence_gaps=sum(int(posture_states.get(key,0) or 0) for key in ("control-partial","control-unvalidated","evidence-stale"))
    for label,value in [
        ("Trust boundaries",summary.get("trust_boundaries")), ("STRIDE candidates",summary.get("stride_candidates")),
        ("Security controls",summary.get("controls")), ("Controls observed",control_states.get("control-observed",0)),
        ("Reviewed attack paths",summary.get("attack_paths")), ("Posture evidence gaps",evidence_gaps), ("Human review","Required")
    ]:
        body += f'<div class="pl-kpi"><span>{_html_text(label)}</span><strong>{_html_text(value)}</strong></div>'
    body += '</div>\n\n'
    body += f'Promoted runtime release: **{posture.get("promoted_runtime_release","unobserved")}** · authority: **{posture.get("authority","promoted/canonical evidence only")}**.\n\n'
    body += '## Security Atlas\n\n'
    body += '<div class="pl-page-lede"><strong>Architecture is the map.</strong><p>Security Atlas explains threats, assets, controls, trust boundaries, reviewed attack paths and evidence. Every view is generated from the canonical security model; the presentation layer never becomes a truth source.</p></div>\n\n'
    body += f'<figure class="pl-security-atlas-poster"><img src="{asset_prefix}/security-atlas.svg" alt="Pocket Lab Lite Security Atlas poster showing Architecture, Threat Atlas, System Atlas, Attack Surface Atlas, Control Atlas and Evidence Atlas" loading="lazy"><figcaption>Canonical source → deterministic projection → human review. No live monitoring or automatic exploit prediction.</figcaption></figure>\n\n'
    body += '<div class="pl-atlas-toolbar" role="tablist" aria-label="Security Atlas views">'
    for index,view in enumerate(atlas.get("views", [])):
        selected='true' if index == 0 else 'false'
        body += f'<button type="button" class="md-button{" md-button--primary" if index == 0 else ""}" role="tab" aria-selected="{selected}" data-atlas-view="{_html_text(view.get("id"))}">{_html_text(view.get("label"))}<span>{_html_text(view.get("entry_count",0))}</span></button>'
    body += '</div>\n'
    body += '<div class="pl-atlas-layout"><div class="pl-atlas-catalog">\n'
    for index,view in enumerate(atlas.get("views", [])):
        hidden='' if index == 0 else ' hidden'
        body += f'<section class="pl-atlas-panel" data-atlas-panel="{_html_text(view.get("id"))}"{hidden}><div class="pl-atlas-panel-head"><h3>{_html_text(view.get("label"))}</h3><p>{_html_text(view.get("description"))}</p></div><div class="pl-atlas-grid">\n'
        for entry in (x for x in atlas.get("catalog", []) if x.get("view") == view.get("id")):
            body += (
                f'<button class="pl-atlas-card" type="button" aria-pressed="false" '
                f'data-catalog-id="{_html_text(entry.get("catalog_id"))}" '
                f'data-catalog-kind="{_html_text(entry.get("kind"))}" '
                f'data-catalog-target="{_html_text(entry.get("target_id"))}" '
                f'data-catalog-title="{_html_text(entry.get("title"))}" '
                f'data-catalog-summary="{_html_text(entry.get("summary"))}" '
                f'data-catalog-meta="{_html_text(entry.get("meta"))}">'
                f'<span class="pl-card-kicker">{_html_text(entry.get("kind"))}</span>'
                f'<strong>{_html_text(entry.get("title"))}</strong>'
                f'<small>{_html_text(entry.get("summary"))}</small></button>\n'
            )
        body += '</div></section>\n'
    body += '</div><aside class="pl-threat-detail pl-atlas-detail" id="threat-selection" aria-live="polite"><strong>Select a catalog entry</strong><p>Threats, controls, boundaries, assets and paths remain evidence-bound and source-derived.</p></aside></div>\n\n'
    body += '## Threat Model Diagram\n\n'
    body += '<div class="pl-threat-toolbar" role="toolbar" aria-label="Threat model diagram controls"><button type="button" data-threat-mode="system" class="md-button md-button--primary">System</button><button type="button" data-threat-mode="controls" class="md-button">Controls</button><button type="button" data-threat-mode="attack-paths" class="md-button">Attack paths</button><button type="button" data-threat-mode="evidence" class="md-button">Evidence posture</button><button type="button" data-threat-motion="toggle" class="md-button">Pause animation</button></div>\n'
    body += f'<div class="pl-threat-canvas"><object id="pl-threat-model-svg" data="{asset_prefix}/threat-model-detail.svg" type="image/svg+xml" aria-label="Interactive Pocket Lab Lite threat model diagram"><img src="{asset_prefix}/threat-model-detail.svg" alt="Pocket Lab Lite threat model diagram"></object><p class="pl-muted">Blue = modeled allowed/control flow · red dashed = selected modeled attack path · shields = controls. Motion never means live traffic.</p></div>\n\n'
    body += '### Attack-path explorer\n\n<div class="pl-threat-path-grid">\n'
    for path in threat.get("attack_paths", []):
        body += f'<button class="pl-threat-path-card" type="button" data-attack-path-id="{_html_text(path.get("id"))}"><span class="pl-card-kicker">{_html_text(path.get("id"))}</span><strong>{_html_text(path.get("name"))}</strong><small>{_html_text(" · ".join(path.get("stride",[])))}</small></button>\n'
    body += '</div>\n\n'
    body += '## Threat framework\n\n'
    fw=threat.get("framework",{})
    body += f'Primary framework: **{fw.get("primary","STRIDE")}**. Reference mapping: **{", ".join(fw.get("reference_mappings",[]))}**.\n\n'
    body += table(["STRIDE","Pocket Lab interpretation"],[[name,text] for name,text in (fw.get("definitions") or {}).items()])
    body += '\n## How Pocket Lab applies STRIDE\n\n' + '\n'.join(f'{i}. {x}' for i,x in enumerate(fw.get("application",[]),1)) + '\n\n'
    body += '!!! info "Candidate does not mean exploitable"\n    STRIDE candidates identify what deserves review. Exploitability, mitigation adequacy, residual risk and risk acceptance remain human-review decisions.\n\n'
    body += '## Three truth layers\n\n' + table(["Layer","Question","Authority"],[[x.get("id"),x.get("question"),x.get("authority")] for x in threat.get("truth_layers",[])])
    body += '\n## Security controls\n\n'
    body += table(["Control","Where used","Threats mitigated","Effect","Current evidence","If the control fails"],[[x.get("id"),x.get("where_used"),x.get("threats_mitigated"),x.get("effect"),x.get("status"),x.get("failure_consequences")] for x in threat.get("controls",[])])
    body += '\nControls **mitigate or reduce exposure**. The page does not claim complete threat prevention unless separate evidence explicitly proves it.\n\n'
    body += '## Where controls are used\n\n'
    boundary_ids=[x.get("id") for x in threat.get("boundaries",[])]
    rows=[]
    for control in threat.get("controls",[]):
        rows.append([control.get("id"), *["✓" if b in control.get("boundaries",[]) else "—" for b in boundary_ids]])
    body += table(["Control",*boundary_ids],rows)
    body += '\n## Modeled attack paths\n\n'
    body += table(["Path","Entry","Target","Boundaries","STRIDE","Controls","Consequences","Review"],[[x.get("id")+" "+x.get("name",""),x.get("entry_point"),x.get("target"),x.get("boundaries"),x.get("stride"),x.get("controls"),x.get("consequences"),x.get("review_status")] for x in threat.get("attack_paths",[])])
    body += '\nThese are **reviewed modeled attack-path scenarios**, not confirmed exploits.\n\n'
    body += '## Architecture integration\n\n'
    ai=threat.get("architecture_integration",{})
    body += f'The diagram is an overlay on the [canonical Pocket Lab Lite Architecture](../../production/architecture/index.md). {ai.get("rule")} It currently binds **{ai.get("component_count",0)}** architecture components into the security view.\n\n'
    body += '## Current evidence posture\n\n'
    body += table(["Signal","Boundary","State","Observed","Source"],[[x.get("signal"),x.get("boundary"),x.get("state"),x.get("observed"),x.get("source")] for x in posture.get("signals",[])])
    body += '\n## What this threat model does not do\n\n' + '\n'.join(f'- {x}' for x in threat.get("exclusions",[])) + '\n\n'
    body += '## Consequences of not threat modelling\n\n' + '\n'.join(f'- {x}' for x in threat.get("consequences_without_model",[])) + '\n\n'
    body += '## Evidence lineage\n\n<div class="pl-lineage">'
    for i,row in enumerate(viz.get("evidence_lineage",[])):
        if i: body += '<span aria-hidden="true">→</span>'
        body += f'<a class="pl-intent-link" href="#evidence-lineage" data-evidence-id="{_html_text(row.get("id"))}"><strong>{_html_text(row.get("label"))}</strong><span><code>{_html_text(row.get("source"))}</code></span></a>'
    body += '</div>\n\n'
    body += '## Threat Dragon\n\nThreat Dragon remains a **derived human-review surface only**. Canonical Pocket Lab source, contracts and promoted evidence remain authoritative; manual review notes must be reconciled back into repository-owned source.\n\n'
    body += '## Human review required\n\n' + '\n'.join(f'- {x}' for x in threat.get("human_review_required",[])) + '\n'
    return body

def complete(root:Path, index:dict[str,Any], outputs:dict[Path,str], *, frontmatter:Callable[...,str], table:Callable[...,str], deps:list[dict[str,Any]], base_config:list[dict[str,Any]], supply:dict[str,Any]) -> tuple[dict[str,Any],dict[Path,str]]:
    doc=root/"docs/generated/enterprise"; out=root/"contracts/generated/documentation-enterprise"; diagrams=root/"docs/generated/assets/enterprise"
    delta=release_delta(root); tasks=task_handbook(root); events=event_encyclopedia(root); baseline=(delta.get("from") or {}).get("tag") if isinstance(delta.get("from"),dict) else None
    inventory=source_dependency_inventory(root,baseline); supply_change=supply_chain_change(inventory,root,baseline)
    # Supply-chain change is part of Release Delta, not a parallel truth system.
    delta["supply_chain_change"] = supply_change
    for dimension in delta.get("dimensions", []):
        if dimension.get("dimension") == "dependency-versions":
            dimension.setdefault("details", {})["supply_chain_change"] = {"dependencies_added":supply_change.get("dependencies_added",[]),"dependencies_removed":supply_change.get("dependencies_removed",[]),"versions_changed":supply_change.get("versions_changed",[]),"upstream_posture_changes":supply_change.get("upstream_posture_changes",[])}
        elif dimension.get("dimension") == "vulnerabilities":
            dimension.setdefault("details", {})["supply_chain_change"] = {"new_vulnerabilities":supply_change.get("new_vulnerabilities",[]),"resolved_vulnerabilities":supply_change.get("resolved_vulnerabilities",[]),"scanner_history_comparable":supply_change.get("scanner_history_comparable",False)}
        elif dimension.get("dimension") == "licenses":
            dimension.setdefault("details", {})["supply_chain_change"] = {"new_licenses":supply_change.get("new_licenses",[]),"removed_licenses":supply_change.get("removed_licenses",[]),"license_classification_changes":supply_change.get("license_classification_changes",[])}
    release=release_evidence(root,delta); threat=enrich_threat_model(threat_model(root,supply,release,deps), root); atlas=build_security_atlas(threat); config=configuration_intelligence(base_config); traces=api_ui_traces(root); trouble=troubleshooting(); privacy=privacy_map(root); fm=fmea(root,deps); slo=reliability(root); adr=adr_intelligence(root); owners=ownership(root); validation=validation_coverage(root); advisor=change_advisor(); upgrade=upgrade_migration(root,delta); disaster=disaster_recovery(); quality=documentation_quality(root); contrib=contribution_matrix(); requirements=coverage_requirements()
    poster=build_security_poster(threat,atlas)
    provenance=read_json(root/"contracts/generated/release-provenance.json",{}) or {"implementation_status":"implemented","evidence_status":"unobserved-until-explicit-generate/sign","formal_slsa_level":"not-claimed","workflow":"scripts/docs/enterprise/release_provenance.py"}
    controls=threat["controls"]
    updates={"release_delta":delta,"release_evidence":release,"tasks":tasks,"events":events,"threat_model":threat,"security_atlas":{"implementation_status":"implemented","source_model":atlas.get("source_model"),"live_monitoring":False,"contract":"contracts/generated/documentation-enterprise/security-atlas.json","views":atlas.get("views",[])},"configuration":config,"api_ui_traces":traces,"troubleshooting":trouble,"privacy_map":privacy,"fmea":fm,"reliability_objectives":slo,"adr_intelligence":adr,"security_controls":controls,"change_advisor":advisor,"ownership":owners,"validation_coverage":validation,"upgrade_migration":upgrade,"disaster_recovery":disaster,"documentation_quality":quality,"supply_chain_inventory":inventory,"supply_chain_change":supply_change,"provenance":provenance,"contribution_review":contrib,"requirements_coverage":requirements}
    updates["security_poster"]={
        "implementation_status":"implemented",
        "source_model":poster.get("source_model"),
        "architecture_model":poster.get("architecture_model"),
        "live_monitoring":False,
        "presentation_modes":[row.get("id") for row in poster.get("modes",[])],
        "contract":"contracts/generated/documentation-enterprise/security-poster.json",
    }
    index["schema_version"]="2.0.0"; index["items"].update(updates); index["implementation_status"]="implemented"
    outputs[root/"contracts/security/threat-model.json"]=stable(threat)
    for name,payload in {"release-delta.json":delta,"release-evidence.json":release,"release-assurance.json":release.get("assurance",{}),"threat-model-visualization.json":threat.get("visualization",{}),"security-atlas.json":atlas,"supply-chain-change.json":supply_change,"validation-coverage.json":validation,"documentation-quality.json":{"items":quality},"requirements-coverage.json":{"schema_version":"1.0.0","items":requirements},"dependency-inventory.json":inventory,"threat-posture.json":threat["production_posture"],"task-handbook.json":{"items":tasks},"event-encyclopedia.json":{"items":events},"security-controls.json":{"items":controls},"configuration-intelligence.json":{"items":config},"api-ui-trace.json":{"items":traces},"fmea.json":{"items":fm},"reliability-objectives.json":{"items":slo}}.items(): outputs[out/name]=stable(payload)

    outputs[out/"security-poster.json"]=stable(poster)

    def page(title:str,desc:str,audience:str,body:str,page_type:str="reference")->str:
        rendered=frontmatter(title,desc,audience,page_type)+body.strip()+"\n"
        # Generated Markdown must satisfy git diff --check. Do not rely on Markdown's
        # two-space hard-break convention because it creates trailing whitespace.
        return "\n".join(line.rstrip() for line in rendered.splitlines())+"\n"
    outputs[doc/"engineering/task-reference.md"]=page("Task Reference","Executable engineering handbook generated from Taskfiles.","development","# Task Reference — executable engineering handbook\n\n## Workflow map\n\nTasks remain source-derived; commands are documented but never executed by this page.\n\n"+table(["Workflow","Task count"],[[g,sum(1 for x in tasks if x['workflow_group']==g)] for g in ["Development loop","Documentation loop","API-validation loop","Runtime-evidence loop","Security-analysis loop","Release loop","Recovery-diagnostics loop"]])+"\n"+"\n".join(f"## `{x['name']}`\n\n**Purpose:** {x['purpose']}\n\n**Audience:** {x['audience']}\n\n**Dependencies:** {', '.join(x['dependencies']) or 'None'}\n\n**Aliases:** {', '.join(x['aliases']) or 'None'}\n\n**Commands:**\n\n"+"\n".join(f"- `{c}`" for c in x['commands'])+f"\n\n**Environment:** {', '.join(x['environment']) or 'None source-discovered'}\n\n**Inputs:** {', '.join(x['inputs']) or 'No explicit file inputs discovered'}\n\n**Outputs:** {', '.join(x['outputs']) or 'No explicit file outputs discovered'}\n\n**Generated artifacts:** {', '.join(x['generated_artifacts']) or 'None discovered'}\n\n**Side effects:** repository mutation={x['repository_mutation']}; runtime mutation={x['runtime_mutation']}; captures runtime={x['captures_runtime']}; promotes evidence={x['promotes_evidence']}\n\n**Runtime:** requires Termux={x['requires_termux']}; requires WSL2={x['requires_wsl2']}; safe local={x['safe_local']}; class={x['expected_runtime_class']}\n\n**Related tasks:** {', '.join(x['related_tasks']) or 'None'}\n\n**Failure modes:** {', '.join(x['failure_modes'])}\n\n**Validation outcome:** {x['validation_outcome']}\n\n**Example:** `{x['example_invocation']}`\n" for x in tasks),"handbook")
    outputs[doc/"engineering/contribution-review.md"]=page("Contribution & Review","Developer onboarding from setup through release review.","development","# Contribution & Review — developer onboarding\n\n## Before coding\nInspect ownership, contracts, current generated state and architecture boundaries.\n\n## During implementation\nChange canonical source, not generated artifacts. Keep execution backend-owned and evidence sanitized.\n\n## Testing\nUse Change Impact Advisor plus focused tests, then the normal gates.\n\n## Documentation\nRegenerate deterministic outputs; MkDocs never captures/promotes runtime.\n\n## Evidence\nCapture runtime/security evidence only through explicit bounded workflows.\n\n## Before commit\nRun `git diff --check`, relevant tests and generated checks.\n\n## PR review\nReview source, contracts, generated delta, security implications and evidence status.\n\n## Merge\nMerge only validated source + generated outputs; keep `main` clean.\n\n## Release\nUse the existing annotated date tag + `dist.zip` workflow; release/runtime promotion remain distinct.\n\n## Change-type matrix\n\n"+table(["Change type","Contracts/tests/docs/evidence","Security review"],[[x["change_type"],f"{x['contracts']}; {x['tests']}; {x['documentation']}; {x['evidence']}",x['security_review']] for x in contrib]),"handbook")
    outputs[doc/"engineering/events.md"]=page("Events","Event encyclopedia generated from canonical AsyncAPI metadata.","development",render_event_encyclopedia_page(events),"handbook")
    outputs[doc/"engineering/release-evidence.md"]=page("Release Assurance","Independent release/runtime/artifact/supply-chain authorities with explicit evidence gaps.","development",render_release_assurance_page(release,delta,table=table),"release")
    outputs[doc/"engineering/troubleshooting.md"]=page("Development Troubleshooting","Diagnostic handbook with command safety classification.","development","# Development Troubleshooting — diagnostic handbook\n\n"+"\n".join(f"## {x['title']}\n\n### Symptom\n{x['symptom']}\n\n### Interpretation\n{x['interpretation']}\n\n### Causes\n- {x['likely_causes'][0]}\n\n### Safe checks\n"+table(["Command","Safety"],[[c['command'],c['class']] for c in x['safe_checks']])+f"\n### Expected result\n{x['expected_result']}\n\n### Next diagnostic step\n{x['next_diagnostic_step']}\n\n### Repair options\n{x['repair_options']}\n\n### Verification\n{x['verification']}\n\n### Rollback\n{x['rollback']}\n\n### Do not do\n"+"\n".join(f"- {v}" for v in x['do_not_do'])+"\n\n### Evidence\n"+"\n".join(f"- {v}" for v in x['evidence_to_preserve'])+"\n" for x in trouble),"troubleshooting")
    outputs[doc/"operate/troubleshooting.md"]=page("Production Troubleshooting","Plain-language production diagnostic companion with safe progressive disclosure.","production",render_production_troubleshooting(trouble),"troubleshooting")
    outputs[doc/"operate/incident-runbooks.md"]=page("Production Incident Runbooks","Operator-safe incident decision support generated from canonical diagnostics.","production","# Production Incident Runbooks\n\n"+"\n".join(f"## {x['title']}\n\n### Trigger\n{x['trigger']}\n\n### Impact\n{x['impact']}\n\n### Urgency\n{x['urgency']}\n\n### User-visible symptom\n{x['symptom']}\n\n### Known evidence\n"+"\n".join(f"- {v}" for v in x['known_evidence'])+"\n\n### Safe checks\n"+table(["Command","Class"],[[c['command'],c['class']] for c in x['safe_checks']])+f"\n### Expected output\n{x['expected_result']}\n\n### Decision tree\n"+"\n".join(f"1. {v}" for v in x['decision_tree'])+f"\n\n### Recovery\n{x['repair_options']}\n\n### Verification\n{x['verification']}\n\n### Rollback\n{x['rollback']}\n\n### When not to act\n"+"\n".join(f"- {v}" for v in x['when_not_to_act'])+"\n\n### Evidence to preserve\n"+"\n".join(f"- {v}" for v in x['evidence_to_preserve'])+f"\n\n### Escalation\n{x['escalation']}\n" for x in trouble),"runbook")
    for x in trouble:
        slug=re.sub(r"[^a-z0-9]+","-",x['scenario'].lower()).strip("-")
        body=f"# {x['title']}\n\n## Trigger\n{x['trigger']}\n\n## Impact\n{x['impact']}\n\n## Urgency\n{x['urgency']}\n\n## User-visible symptom\n{x['symptom']}\n\n## Known evidence\n"+"\n".join(f"- {v}" for v in x['known_evidence'])+"\n\n## Safe checks\n"+table(["Command","Class"],[[c['command'],c['class']] for c in x['safe_checks']])+f"\n## Expected output\n{x['expected_result']}\n\n## Decision tree\n"+"\n".join(f"1. {v}" for v in x['decision_tree'])+f"\n\n## Recovery\n{x['repair_options']}\n\n## Verification\n{x['verification']}\n\n## Rollback\n{x['rollback']}\n\n## When not to act\n"+"\n".join(f"- {v}" for v in x['when_not_to_act'])+"\n\n## Evidence to preserve\n"+"\n".join(f"- {v}" for v in x['evidence_to_preserve'])+f"\n\n## Escalation\n{x['escalation']}\n"
        outputs[doc/"operate/runbooks"/f"{slug}.md"]=page(x['title'],f"Production runbook for {x['title']}.","production",body,"runbook")
    outputs[doc/"threat-model/index.md"]=page(
        "Threat Model",
        "Pocket Lab Lite Security Architecture Poster over the canonical saved threat model; never live monitoring.",
        "production",
        render_threat_model_overview(threat,poster),
        "reference",
    )
    for slug,spec in render_threat_model_subpages(threat,poster).items():
        outputs[doc/"threat-model"/f"{slug}.md"]=page(
            spec["title"], spec["description"], "production", spec["body"], "reference"
        )
    outputs[doc/"threat-model/catalog.md"]=page(
        "Security Atlas Catalog",
        "Expert catalog of threats, systems, attack surface, controls and evidence over the canonical Pocket Lab Lite architecture.",
        "production",
        render_threat_model_page(
            threat, atlas, table=table, heading="Security Atlas Catalog", asset_prefix="../../../assets/enterprise"
        ),
        "reference",
    )
    for b in threat['boundaries']:
        bt=[x for x in threat['threats'] if x['boundary']==b['id']]
        body=f"# {b['label']}\n\n## Boundary\n{b['label']}\n\n## Assets\n"+"\n".join(f"- {x}" for x in b['assets'])+"\n\n## Actors\n"+"\n".join(f"- {x}" for x in b['actors'])+"\n\n## Entry points\n"+"\n".join(f"- {x}" for x in b['entry_points'])+"\n\n## Data flows\n"+"\n".join(f"- {x}" for x in b['data_flows'])+"\n\n## Allowed flows\n"+"\n".join(f"- {x}" for x in b['allowed_flows'])+"\n\n## Forbidden flows\n"+"\n".join(f"- {x}" for x in b['forbidden_flows'])+"\n\n## Threats\n"+table(["STRIDE","Scenario","OWASP mapping","Controls"],[[x['stride'],x['scenario'],x['owasp_mappings'],x['controls']] for x in bt])+"\n## Controls\n"+"\n".join(f"- `{x}`" for x in b['controls'])+"\n\n## Runtime evidence\n"+table(["Signal","State","Source"],[[x['signal'],x['state'],x['source']] for x in b['runtime_evidence']])+f"\n## Residual risk\n{b['residual_risk']}\n\n## Review status\n{b['review_status']}\n"
        outputs[doc/"threat-model"/f"{b['id']}.md"]=page(b['label'],f"Generated STRIDE threat model for {b['label']}.","production",body,"threat-model")
    outputs[doc/"reference/configuration.md"]=page("Configuration Intelligence","Source-derived sanitized configuration catalog.","development","# Configuration Intelligence\n\nNo runtime secret values are read or rendered.\n\n"+table(["Name","Purpose","Owner","Default","Required","Secret?","Scope","Restart","Release","Runtime","Validation"],[[x['name'],x['purpose'],x['owner'],x['default'],x['required'],x['secret'],x['runtime_scope'],x['restart_required'],x['affects_release'],x['affects_runtime'],x['validation']] for x in config]))
    outputs[doc/"reference/api-ui-trace.md"]=page("API-to-UI Trace Explorer","Source-derived UI → API → execution → evidence traces.","development",render_api_ui_trace_page(traces))
    outputs[doc/"reference/data-lifecycle.md"]=page("Data Lifecycle & Privacy Map","Storage, retention, sanitization, exposure and deletion intelligence.","production","# Data Lifecycle & Privacy Map\n\n![Data lifecycle](../../assets/enterprise/data-lifecycle.svg){ loading=lazy }\n\n"+table(["Category","Storage","Retention","Sanitization","Access","Network exposure","Backup","Deletion","Privacy risk"],[[x['category'],x['storage'],x['retention'],x['sanitization'],x['access'],x['network_exposure'],x['backup_behavior'],x['deletion_behavior'],x['privacy_risk']] for x in privacy]))
    outputs[doc/"reference/fmea.md"]=page("Failure-mode & Resilience Catalog","Categorical FMEA with source-derived detection/recovery and no invented numeric RPN.","development","# Failure-mode & Resilience Catalog / FMEA\n\n"+table(["Component","Failure mode","Detection","Impact","Automatic recovery","Manual recovery","Severity","Occurrence","Detectability","Residual risk"],[[x['component'],x['failure_mode'],x['detection'],x['user_impact'],x['automatic_recovery'],x['manual_recovery'],x['severity'],x['occurrence'],x['detectability'],x['residual_risk']] for x in fm]))
    outputs[doc/"reference/reliability.md"]=page("Reliability Objectives","SLO-style engineering objectives from promoted evidence; not live monitoring.","production","# Reliability Objectives — not live monitoring\n\n"+table(["Objective","Target","Latest promoted observation","Status","Evidence"],[[x['objective'],x['target'],x['latest_promoted_observation'],x['status'],x['evidence']] for x in slo]))
    outputs[doc/"reference/adr-intelligence.md"]=page("ADR Intelligence","Architecture decisions with consequences, security/runtime implications and relationship graph.","development",render_adr_intelligence_page(adr))
    outputs[doc/"reference/supply-chain.md"]=page("Software Supply Chain","Source dependency inventory plus explicit WSL2/CI normalized security/SBOM evidence.","development","# Software Supply Chain\n\n## Automation boundary\n\nHeavy tools run only through explicit WSL2/CI tasks. MkDocs never invokes them. Existing Termux Trivy remains bounded and runtime-owned.\n\n## Inventory\n\n"+table(["Name","Version","Ecosystem","Direct?","Purpose","Runtime/dev","License","Release introduced"],[[x['name'],x['version'],x['ecosystem'],x['direct'],x['purpose'],x['runtime_or_dev'],x['license'],x['release_introduced']] for x in inventory['dependencies'][:350]])+"\n## Canonical promoted tool artifacts\n\n"+table(["Artifact","Present"],[[name,(root/'contracts/generated/supply-chain'/name).exists()] for name in ["sbom-dev.cdx.json","sbom-release.cdx.json","sbom-runtime.cdx.json","vulnerability-correlation.json","license-inventory.json","security-analysis.json","scorecard-checks.json"]])+"\n## Optional Dependency-Track\n\n`task lite:docs:supply-chain:dependency-track:export` stages canonical CycloneDX files for optional import. Documentation never depends on a live Dependency-Track service.\n")
    outputs[doc/"reference/security-controls.md"]=page("Security Controls","Threat → control → source/tests/runtime evidence traceability.","development","# Security Controls Catalog\n\n![Security controls](../../assets/enterprise/security-controls.svg){ loading=lazy }\n\n"+table(["Control","Description","Boundaries","Threats","Implementation","Tests","Runtime evidence","Status","Freshness","Owner"],[[x['id'],x['description'],x['boundaries'],x['threats'],x['implementation'],x['tests'],x['runtime_evidence'],x['status'],x['freshness'],x['owner']] for x in controls]))
    outputs[doc/"reference/change-advisor.md"]=page("Change Impact Advisor","Deterministic source-path change simulation without executing changes.","development","# Change Impact Advisor\n\nThis advisor predicts consequences; it never mutates source/runtime. Inputs: "+", ".join(advisor['inputs'])+". Algorithm: "+advisor['algorithm']+".\n\n"+table(["Changed path","Potential impacts","Tests/tasks","Generated artifacts","Reviews","Security"],[[x['path_prefix'],x['potential_impacts'],x['recommended_tests_tasks'],x['generated_artifacts'],x['required_reviews'],x['security_review']] for x in advisor['rules']]))
    outputs[doc/"reference/ownership.md"]=page("Ownership & Responsibility Map","Source/runtime/recovery/control/presentation/evidence ownership with architecture, threat and test cross-links.","development","# Ownership & Responsibility Map\n\n"+table(["Capability","Source","Runtime","Recovery","Control","Presentation","Evidence","Architecture","Threats","Tests"],[[x['capability'],x['source_owner'],x['runtime_owner'],x['recovery_owner'],x['control_owner'],x['presentation_owner'],x['evidence_owner'],x['architecture'],x['threats'],x['tests']] for x in owners]))
    outputs[doc/"reference/validation-coverage.md"]=page("Validation Coverage Dashboard","Repository-native validation coverage; never live CI polling.","development","# Validation Coverage Dashboard\n\n"+table(["Gate","Implemented","Discoverable","Latest canonical status","Canonical evidence"],[[x['name'],x['implementation_status'],x['gate_discoverable'],x['latest_verified_status'],x['canonical_evidence']] for x in validation['checks']]))
    outputs[doc/"reference/upgrade-migration.md"]=page("Upgrade & Migration Intelligence","Release-comparable upgrade, migration, compatibility, rollback and backup guidance.","production","# Upgrade & Migration Intelligence\n\n"+table(["Field","Value"],[["From",upgrade['from_release'] or 'not-comparable'],["To",upgrade['to_release']],["Database migrations",upgrade['database_migrations']],["Agent compatibility",upgrade['agent_compatibility']],["Runtime changes",upgrade['runtime_changes']],["Backup requirement",upgrade['backup_requirement']],["API breaking changes",upgrade['breaking_api_changes']],["Config changes",upgrade['config_changes']],["Rollback",upgrade['rollback']],["Verification",upgrade['verification']]]))
    outputs[doc/"reference/disaster-recovery.md"]=page("Disaster Recovery Architecture","Scenario-specific survivability, dependency order, recovery and verification.","production","# Disaster Recovery Architecture\n\n![Disaster recovery dependency order](../../assets/enterprise/disaster-recovery.svg){ loading=lazy }\n\n"+table(["Scenario","Survives","Lost","Recoverability","Dependency order","Evidence","Verification","Rollback"],[[x['scenario'],x['what_survives'],x['what_is_lost'],x['recoverability'],x['dependency_order'],x['required_evidence'],x['verification'],x['rollback']] for x in disaster]))
    outputs[doc/"reference/documentation-quality.md"]=page("Documentation Quality Scorecard","Categorical documentation coverage derived from generated/canonical evidence.","development","# Documentation Quality Scorecard\n\n"+table(["Domain","Architecture","API","Events","Runbook","Threat","Health","Evidence","Troubleshooting","Release","Ownership","Quality"],[[x['domain'],x['architecture_documented'],x['api_documented'],x['events_documented'],x['runbook_present'],x['threat_model_present'],x['operational_health_modeled'],x['evidence_coverage'],x['troubleshooting'],x['release_impact'],x['ownership'],x['quality']] for x in quality]))
    outputs[doc/"reference/supply-chain-change.md"]=page("Supply-chain Change Intelligence","Current promoted supply-chain snapshot, tool coverage, repository posture, baseline readiness and verified release-to-release deltas.","development",render_supply_chain_change_page(supply_change, table=table))
    outputs[doc/"release/index.md"]=page("Release","Release evidence, full multidimensional delta, supply-chain change, upgrade and provenance.","production","# Release\n\n## Summary\n\nThis page explains the current release evidence and change surface without conflating source HEAD, promoted runtime, GitHub publication, signatures or scanner evidence.\n\n## Release evidence\n\nSource/release/runtime identities remain separate. Current source commit: `"+str(release['source_commit'])+"`; runtime binding: `"+str(release['runtime_baseline_binding'])+"`.\n\n## Release delta\n\nStatus: **"+delta['status']+"**. From **"+str((delta.get('from') or {}).get('tag') if isinstance(delta.get('from'),dict) else 'not-comparable')+"** to **"+str((delta.get('to') or {}).get('tag') if isinstance(delta.get('to'),dict) else 'not-comparable')+"**. Repository HEAD is never substituted for a release.\n\n"+table(["Dimension","Classification","From digest","To digest"],[[x['dimension'],x['classification'],x.get('from_digest'),x.get('to_digest')] for x in delta['dimensions']])+"\n## Compatibility\n\nSupported targets: "+", ".join(release['device_compatibility'])+". Upgrade compatibility remains evidence-bound and is generated only from a comparable release baseline.\n\n## Validation outcomes\n\n"+str(release['validation_outcomes'])+". No continuous CI/runtime polling occurs here.\n\n## Supply-chain change\n\nSupply-chain change is embedded in the Release Delta machine contract and rendered here from the same canonical comparison: dependencies, versions, vulnerabilities, licenses and upstream posture remain evidence-scoped and fail closed when historical scanner evidence is unavailable.\n\n## Known limitations\n\n"+str(release['known_limitations'])+". Local or GitHub release assets remain unobserved unless explicitly verified.\n\n## Provenance\n\nCosign signing is explicit. SLSA-style provenance is generated without claiming a formal SLSA level.\n","release")

    event_rows=[]
    for x in events[:80]: event_rows.append((x['publisher'][0] if x['publisher'] else 'publisher',f"{x['nats_subject']} → projection/UI"))
    trace_rows=[(x['action'],f"{x['api'][0]['method']} {x['api'][0]['path']} → backend execution") for x in traces]
    privacy_rows=[(x['category'],f"{x['storage']} → {x['sanitization']}") for x in privacy]
    adr_rows=[(x.get('name') or x.get('id'),x.get('status') or 'source-derived') for x in adr['entities']]
    control_rows=[(x['id'],f"{','.join(x['boundaries'])} → {x['status']}") for x in controls]
    dr_rows=[(x['scenario']," → ".join(x['dependency_order'])) for x in disaster]
    assets={"event-flows":("Event encyclopedia flow",event_rows),"api-ui-trace":("API-to-UI trace",trace_rows),"data-lifecycle":("Data lifecycle and sanitization",privacy_rows),"adr-relationships":("ADR intelligence",adr_rows),"security-controls":("Threat/control coverage",control_rows),"disaster-recovery":("Disaster recovery dependency order",dr_rows)}
    for name,(title,rows) in assets.items(): outputs[diagrams/f"{name}.dot"]=flow_dot(title,rows); outputs[diagrams/f"{name}.svg"]=flow_svg(title,rows)
    outputs[diagrams/"threat-model-detail.svg"] = render_threat_svg(threat)
    outputs[diagrams/"threat-model.svg"] = render_security_poster_svg(poster)
    outputs[diagrams/"security-atlas.svg"] = render_security_atlas_svg(atlas)
    return index,outputs
