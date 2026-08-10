#!/usr/bin/env python3
"""Explicit WSL2/CI supply-chain automation for Pocket Lab Lite.

This program is intentionally not invoked by MkDocs or lite:docs:check.

Lifecycle:
  capture  -> transient raw output under .pocketlab-dev
  promote  -> bounded normalized/CycloneDX contracts under contracts/generated
  check    -> validate already-promoted canonical contracts only

Runtime evidence is never collected here. The runtime SBOM projection is derived solely from the
already-promoted sanitized runtime baseline. Termux Trivy remains owned by the existing bounded
Security profiles and may later contribute only through promoted sanitized evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
META = ROOT / "contracts/metadata/documentation-security-tools.json"
RUNTIME = ROOT / "contracts/parity/runtime-verification-baseline.json"
OUT = ROOT / "contracts/generated/supply-chain"
DEFAULT_RUN_ROOT = ROOT / ".pocketlab-dev/documentation-security/runs"
TOOL_ROOT = ROOT / ".pocketlab-dev/tools/documentation-security/bin"
CANONICAL_FILES = {
    "sbom_dev": "sbom-dev.cdx.json",
    "sbom_release": "sbom-release.cdx.json",
    "sbom_runtime": "sbom-runtime.cdx.json",
    "vulnerabilities": "vulnerability-correlation.json",
    "licenses": "license-inventory.json",
    "security": "security-analysis.json",
    "scorecard": "scorecard-checks.json",
    "summary": "automation-summary.json",
}
PRIVATE = re.compile(r"(?:/home/[^/\s]+|/data/data/com\.termux/files/(?:home|usr)|[A-Za-z]:\\Users\\|nats://[^\s]+@)", re.I)
PRIVATE_PATH_REPLACEMENTS = (
    (re.compile(r"/home/[^/\s\"'<>]+", re.I), "<home>"),
    (re.compile(r"/data/data/com\.termux/files/home", re.I), "<termux-home>"),
    (re.compile(r"/data/data/com\.termux/files/usr", re.I), "<termux-prefix>"),
    (re.compile(r"[A-Za-z]:\\Users\\[^\\/\s\"'<>]+", re.I), "<windows-home>"),
)
SECRET = re.compile(r"(?:BEGIN [A-Z ]*PRIVATE KEY|[\"']?(?:password|passwd|token|secret|api[_-]?key|credential|authorization)[\"']?\s*[=:]\s*[\"']?[^\s,}\]\"']{6,})", re.I)


def stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, separators=(",", ": ")) + "\n"


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def fail(message: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def is_termux() -> bool:
    return bool(os.environ.get("TERMUX_VERSION")) or "com.termux" in os.environ.get("PREFIX", "") or platform.system().lower() == "android"


def sanitize_private_paths(value: Any) -> Any:
    """Redact host-specific filesystem roots while preserving canonical structure.

    Secret-like values are intentionally not rewritten here; ``safe_text`` still
    rejects them fail-closed.  This sanitizer exists only for machine-local path
    material that scanners may embed in otherwise useful normalized evidence.
    """
    if isinstance(value, str):
        text = value
        for pattern, replacement in PRIVATE_PATH_REPLACEMENTS:
            text = pattern.sub(replacement, text)
        return text
    if isinstance(value, list):
        return [sanitize_private_paths(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_private_paths(item) for key, item in value.items()}
    return value


def safe_text(label: str, value: str) -> None:
    if PRIVATE.search(value):
        fail(f"{label}: private path detected in canonical output")
    if SECRET.search(value):
        fail(f"{label}: secret-like value detected in canonical output")


def tool_path(name: str) -> str:
    local = TOOL_ROOT / name
    if local.exists():
        return str(local)
    found = shutil.which(name)
    if not found:
        fail(f"required development tool is missing: {name}; run task lite:docs:security-tools:setup")
    return found


def run_tool(name: str, argv: list[str], output: Path | None, *, timeout: int, allow_nonzero: bool = True) -> dict[str, Any]:
    binary = tool_path(name)
    command = [binary, *argv]
    started = dt.datetime.now(dt.timezone.utc)
    try:
        proc = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout, check=False)
        code = proc.returncode
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(proc.stdout or b"")
        state = "completed" if code == 0 else "findings-or-tool-nonzero" if allow_nonzero else "failed"
        stderr_digest = digest_bytes(proc.stderr or b"")
    except subprocess.TimeoutExpired as exc:
        code = 124
        state = "timed-out"
        stderr_digest = digest_bytes(exc.stderr or b"") if isinstance(exc.stderr, bytes) else "unavailable"
    result = {
        "tool": name,
        "command_shape": [name, *argv],
        "exit_code": code,
        "status": state,
        "started_at": started.isoformat().replace("+00:00", "Z"),
        "stderr_sha256": stderr_digest,
        "raw_output": str(output.relative_to(ROOT)) if output and output.exists() else None,
    }
    if not allow_nonzero and code != 0:
        fail(f"{name} failed with exit code {code}")
    return result


def safe_unzip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        base = destination.resolve()
        for item in zf.infolist():
            target = (destination / item.filename).resolve()
            if base not in target.parents and target != base:
                fail(f"release archive path traversal rejected: {item.filename}")
        zf.extractall(destination)


def new_run_dir() -> Path:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = hashlib.sha256(f"{now}:{os.getpid()}".encode()).hexdigest()[:8]
    return DEFAULT_RUN_ROOT / f"{now}-{suffix}"


def capture(run_dir: Path, include_history: bool) -> int:
    if is_termux():
        fail("heavy supply-chain automation is WSL2/CI-only; use existing bounded Termux Security profiles for runtime scanning", 3)
    raw = run_dir / "raw"
    raw.mkdir(parents=True, exist_ok=False)
    manifest: dict[str, Any] = {
        "schema_version": "1.0.0",
        "mode": "transient-capture",
        "canonical": False,
        "runtime_capture_performed": False,
        "runtime_promotion_performed": False,
        "run_id": run_dir.name,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "tools": [],
        "release_artifact": "present" if (ROOT / "dist.zip").exists() else "missing",
    }

    # Syft is primary for development/release CycloneDX.
    manifest["tools"].append(run_tool("syft", ["dir:.", "-o", "cyclonedx-json"], raw / "syft-dev.cdx.json", timeout=900, allow_nonzero=False))
    if (ROOT / "dist.zip").exists():
        with tempfile.TemporaryDirectory(prefix="pocketlab-release-sbom-") as tmp:
            staging = Path(tmp)
            safe_unzip(ROOT / "dist.zip", staging)
            manifest["tools"].append(run_tool("syft", [f"dir:{staging}", "-o", "cyclonedx-json"], raw / "syft-release.cdx.json", timeout=900, allow_nonzero=False))

    manifest["tools"].append(run_tool("trivy", ["fs", "--format", "json", "--scanners", "vuln,misconfig,secret", "--skip-dirs", ".git", "--skip-dirs", "node_modules", "--skip-dirs", ".venv", "--skip-dirs", "docs/generated", "--skip-dirs", "contracts/generated", "."], raw / "trivy-source.json", timeout=1800))
    manifest["tools"].append(run_tool("trivy", ["sbom", "--format", "json", str(raw / "syft-dev.cdx.json")], raw / "trivy-sbom-dev.json", timeout=900))
    manifest["tools"].append(run_tool("osv-scanner", ["scan", "source", "--format", "json", "--recursive", "."], raw / "osv-source.json", timeout=1200))
    # OSV-Scanner v2 discovers CycloneDX/SPDX SBOMs from the input filename/plugin
    # model. Scan the canonical Syft development SBOM separately so the normalized
    # correlation records whether a vulnerability was observed from source or SBOM.
    manifest["tools"].append(run_tool("osv-scanner", ["scan", "source", "--format", "json", "--lockfile", str(raw / "syft-dev.cdx.json")], raw / "osv-sbom-dev.json", timeout=1200))
    manifest["tools"].append(run_tool("grype", [f"sbom:{raw / 'syft-dev.cdx.json'}", "-o", "json"], raw / "grype-sbom-dev.json", timeout=1200))

    # Secrets coverage is additive: always scan the current worktree (which includes
    # generated docs and promoted evidence), optionally add complete Git history, and
    # independently scan the extracted release staging tree when dist.zip exists.
    gitleaks_reports = [raw / "gitleaks-worktree.json"]
    manifest["tools"].append(run_tool("gitleaks", ["dir", "--redact=100", "--report-format", "json", "--report-path", str(gitleaks_reports[0]), "."], None, timeout=1200))
    if include_history:
        history_report = raw / "gitleaks-history.json"
        gitleaks_reports.append(history_report)
        manifest["tools"].append(run_tool("gitleaks", ["git", "--redact=100", "--report-format", "json", "--report-path", str(history_report), "."], None, timeout=1800))
    if (ROOT / "dist.zip").exists():
        with tempfile.TemporaryDirectory(prefix="pocketlab-release-gitleaks-") as tmp:
            release_staging = Path(tmp)
            safe_unzip(ROOT / "dist.zip", release_staging)
            release_report = raw / "gitleaks-release.json"
            gitleaks_reports.append(release_report)
            manifest["tools"].append(run_tool("gitleaks", ["dir", "--redact=100", "--report-format", "json", "--report-path", str(release_report), str(release_staging)], None, timeout=1200))
    for report in gitleaks_reports:
        if not report.exists():
            report.write_text("[]\n", encoding="utf-8")

    manifest["tools"].append(run_tool("semgrep", ["--metrics=off", "--config", "security/static-analysis/pocketlab-architecture.yml", "--json", "--output", str(raw / "semgrep.json"), "."], None, timeout=1800))
    if not (raw / "semgrep.json").exists():
        (raw / "semgrep.json").write_text('{"results": [], "errors": []}\n', encoding="utf-8")

    scancode_targets = ["package.json", "requirements-dev.txt", "requirements-docs.txt", "pocket-lab-final-structure/runtime/requirements.txt", "operations", "runbooks", "scripts", "src"]
    scancode_targets = [x for x in scancode_targets if (ROOT / x).exists()]
    # ScanCode 32.5.0 is installed in an isolated pinned PyPI environment on both
    # amd64 and arm64 developer/CI hosts; the canonical result is normalized below.
    manifest["tools"].append(run_tool("scancode", ["--license", "--package", "--copyright", "--json-pp", str(raw / "scancode.json"), *scancode_targets], None, timeout=3600))
    if not (raw / "scancode.json").exists():
        (raw / "scancode.json").write_text('{"headers": [], "files": []}\n', encoding="utf-8")

    manifest["tools"].append(run_tool("scorecard", ["--local", ".", "--format", "json", "--checks", "Pinned-Dependencies,Dangerous-Workflow,Branch-Protection,Signed-Releases,Maintained,Token-Permissions"], raw / "scorecard.json", timeout=1800))
    manifest["raw_files"] = [{"path": str(p.relative_to(run_dir)), "sha256": digest_file(p), "bytes": p.stat().st_size} for p in sorted(raw.glob("*")) if p.is_file()]
    (run_dir / "capture-manifest.json").write_text(stable(manifest), encoding="utf-8")
    print(f"PASS transient WSL2/CI supply-chain capture: {run_dir}")
    print("Raw scanner output remains transient and is not documentation truth. Run promote explicitly after review.")
    return 0


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def normalized_component(item: dict[str, Any]) -> dict[str, Any] | None:
    name = str(sanitize_private_paths(str(item.get("name") or ""))).strip()
    version = str(sanitize_private_paths(str(item.get("version") or ""))).strip()
    if not name:
        return None
    licenses: list[dict[str, Any]] = []
    for entry in item.get("licenses") or []:
        if not isinstance(entry, dict):
            continue
        lic = entry.get("license") if isinstance(entry.get("license"), dict) else entry
        lid = lic.get("id") or lic.get("name") if isinstance(lic, dict) else None
        if lid:
            licenses.append({"license": {"id": str(lid)}})
    result = {"type": item.get("type") or "library", "name": name}
    if version:
        result["version"] = version
    if item.get("purl"):
        purl = str(item["purl"])
        # A package URL carrying a local filesystem root is host-specific and can
        # become syntactically invalid if the path is textually redacted.  Omit
        # that optional locator instead; package name/version remain canonical.
        if not PRIVATE.search(purl) and not SECRET.search(purl):
            result["purl"] = purl
    if licenses:
        result["licenses"] = licenses
    return result


def canonical_cdx(source: dict[str, Any] | None, *, target: str, evidence_status: str, source_digest: str | None, release_binding: str | None = None) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    if isinstance(source, dict):
        for item in source.get("components") or []:
            if isinstance(item, dict):
                normalized = normalized_component(item)
                if normalized:
                    components.append(normalized)
    components.sort(key=lambda x: (str(x.get("purl", "")), x["name"], str(x.get("version", ""))))
    dedup: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in components:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key); dedup.append(item)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "name": f"pocket-lab-lite-{target}"},
            "properties": [
                {"name": "pocketlab:evidence-status", "value": evidence_status},
                {"name": "pocketlab:source-generator", "value": "Syft" if source else "Pocket Lab promoted runtime projection" if target == "runtime" else "missing"},
                {"name": "pocketlab:source-digest", "value": source_digest or "unavailable"},
                {"name": "pocketlab:sanitized", "value": "true"},
                {"name": "pocketlab:release-binding", "value": release_binding or "not-applicable"},
            ],
        },
        "components": dedup,
    }


def runtime_components() -> list[dict[str, Any]]:
    baseline = read_json(RUNTIME, {})
    found: dict[tuple[str, str], dict[str, Any]] = {}
    allowed_name_keys = {"name", "service", "component", "package", "tool", "app"}
    version_keys = {"version", "runtime_version", "app_version", "service_version"}
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            name = next((value.get(k) for k in allowed_name_keys if isinstance(value.get(k), str)), None)
            version = next((value.get(k) for k in version_keys if isinstance(value.get(k), (str, int, float))), None)
            if name and version:
                clean_name = re.sub(r"[^A-Za-z0-9_.+/-]", "-", str(name))[:120]
                clean_version = re.sub(r"[^A-Za-z0-9_.+~-]", "-", str(version))[:80]
                if clean_name and clean_version:
                    found[(clean_name, clean_version)] = {"type": "application", "name": clean_name, "version": clean_version}
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(baseline)
    return [found[k] for k in sorted(found)]


def vulnerabilities_from_trivy(data: Any) -> list[dict[str, Any]]:
    out=[]
    if not isinstance(data, dict): return out
    for result in data.get("Results") or []:
        if not isinstance(result, dict): continue
        for finding in result.get("Vulnerabilities") or []:
            if not isinstance(finding, dict): continue
            out.append({"id": finding.get("VulnerabilityID") or "unknown", "package": finding.get("PkgName") or "unknown", "installed": finding.get("InstalledVersion") or "unknown", "fixed": finding.get("FixedVersion") or None, "severity": finding.get("Severity") or "UNKNOWN", "source": "trivy"})
    return out


def vulnerabilities_from_grype(data: Any) -> list[dict[str, Any]]:
    out=[]
    if not isinstance(data, dict): return out
    for match in data.get("matches") or []:
        if not isinstance(match, dict): continue
        vuln=match.get("vulnerability") or {}; artifact=match.get("artifact") or {}
        out.append({"id": vuln.get("id") or "unknown", "package": artifact.get("name") or "unknown", "installed": artifact.get("version") or "unknown", "fixed": ",".join(vuln.get("fix",{}).get("versions") or []) or None, "severity": vuln.get("severity") or "UNKNOWN", "source": "grype"})
    return out


def vulnerabilities_from_osv(data: Any) -> list[dict[str, Any]]:
    out=[]
    if not isinstance(data, dict): return out
    for result in data.get("results") or []:
        if not isinstance(result, dict): continue
        packages = result.get("packages") or []
        for package in packages:
            if not isinstance(package, dict): continue
            pkg = package.get("package") if isinstance(package.get("package"), dict) else package
            name = pkg.get("name") or "unknown"
            version = pkg.get("version") or "unknown"
            for vuln in package.get("vulnerabilities") or []:
                if isinstance(vuln, dict):
                    out.append({"id": vuln.get("id") or "unknown", "package": name, "installed": version, "fixed": None, "severity": "UNRATED", "source": "osv-scanner"})
    return out


def correlate_vulnerabilities(raw: Path) -> dict[str, Any]:
    findings = (
        vulnerabilities_from_trivy(read_json(raw / "trivy-sbom-dev.json", {}))
        + vulnerabilities_from_grype(read_json(raw / "grype-sbom-dev.json", {}))
        + vulnerabilities_from_osv(read_json(raw / "osv-source.json", {}))
        + vulnerabilities_from_osv(read_json(raw / "osv-sbom-dev.json", {}))
    )
    grouped: dict[tuple[str,str], list[dict[str,Any]]] = defaultdict(list)
    for finding in findings:
        grouped[(str(finding["id"]), str(finding["package"]))].append(finding)
    items=[]
    for (vid,pkg), group in sorted(grouped.items()):
        sources=sorted({x["source"] for x in group})
        severities=sorted({str(x.get("severity") or "UNKNOWN") for x in group})
        items.append({"id":vid,"package":pkg,"sources":sources,"correlation":"corroborated" if len(sources)>1 else "single-source","severities":severities,"installed_versions":sorted({str(x.get("installed") or "unknown") for x in group}),"fixed_versions":sorted({str(x["fixed"]) for x in group if x.get("fixed")})})
    return {"schema_version":"1.0.0","evidence_status":"observed" if items else "no-findings-observed-or-no-tool-results","scanner_disagreement_is_failure":False,"items":items,"counts":{"unique_vulnerabilities":len(items),"corroborated":sum(1 for x in items if x["correlation"]=="corroborated"),"single_source":sum(1 for x in items if x["correlation"]=="single-source")}}


def classify_license_expression(expression: str) -> str:
    value = expression.upper().strip()
    if not value or value in {"UNKNOWN", "NOASSERTION", "NONE"}:
        return "unknown"
    strong = ("GPL-", "AGPL-", "SSPL-")
    weak = ("LGPL-", "MPL-", "EPL-", "CDDL-")
    permissive = ("MIT", "BSD", "APACHE-", "ISC", "ZLIB", "UNLICENSE", "0BSD", "BSL-1.0")
    if any(token in value for token in strong) and not any(token in value for token in weak):
        return "strong-copyleft"
    if any(token in value for token in weak):
        return "weak-copyleft"
    if any(token in value for token in permissive):
        return "permissive"
    return "manual-review"


def license_inventory(sbom: dict[str, Any], scancode: Any) -> dict[str, Any]:
    rows=[]
    for comp in sbom.get("components") or []:
        licenses=[]
        for item in comp.get("licenses") or []:
            lic=item.get("license") if isinstance(item,dict) else None
            if isinstance(lic,dict) and (lic.get("id") or lic.get("name")): licenses.append(str(lic.get("id") or lic.get("name")))
        classifications=sorted({classify_license_expression(x) for x in licenses}) or ["unknown"]
        rows.append({"package":comp.get("name"),"version":comp.get("version"),"licenses":sorted(set(licenses)),"classification":classifications[0] if len(classifications)==1 else "manual-review","classification_evidence":classifications})
    detected=Counter()
    if isinstance(scancode,dict):
        for file in scancode.get("files") or []:
            if not isinstance(file,dict): continue
            for det in file.get("license_detections") or []:
                if isinstance(det,dict):
                    expr=det.get("license_expression") or det.get("license_expression_spdx")
                    if expr: detected[str(expr)] += 1
    detected_rows=[{"expression":k,"files":v,"classification":classify_license_expression(k)} for k,v in sorted(detected.items())]
    return {"schema_version":"1.0.0","implementation_status":"implemented","classification_vocabulary":["permissive","weak-copyleft","strong-copyleft","unknown","manual-review"],"items":rows,"scancode_detected_expressions":detected_rows,"policy":"classification is deterministic evidence triage only; license approval, exceptions and legal interpretation remain human-maintained"}


def scorecard_summary(data: Any) -> dict[str, Any]:
    wanted={"Pinned-Dependencies","Dangerous-Workflow","Branch-Protection","Signed-Releases","Maintained","Token-Permissions"}
    checks=[]
    if isinstance(data,dict):
        for item in data.get("checks") or []:
            if isinstance(item,dict) and item.get("name") in wanted:
                checks.append({"name":item.get("name"),"score":item.get("score"),"reason":"recorded-by-scorecard"})
    return {"schema_version":"1.0.0","status":"observed" if checks else "unobserved","checks":sorted(checks,key=lambda x:x["name"])}


def security_summary(raw: Path) -> dict[str, Any]:
    gitleaks_reports = []
    for report in sorted(raw.glob("gitleaks-*.json")):
        data = read_json(report, [])
        if isinstance(data, list):
            gitleaks_reports.extend(data)
    semgrep=read_json(raw/"semgrep.json",{}); trivy=read_json(raw/"trivy-source.json",{})
    trivy_counts=Counter()
    if isinstance(trivy,dict):
        for result in trivy.get("Results") or []:
            if not isinstance(result,dict): continue
            for f in result.get("Vulnerabilities") or []:
                if isinstance(f,dict): trivy_counts[str(f.get("Severity") or "UNKNOWN")]+=1
            for key in ("Misconfigurations","Secrets"):
                if isinstance(result.get(key),list): trivy_counts[key.lower()]+=len(result[key])
    return {"schema_version":"1.0.0","raw_findings_included":False,"gitleaks":{"finding_count":len(gitleaks_reports),"redacted":True,"coverage":[p.name for p in sorted(raw.glob("gitleaks-*.json"))]},"semgrep":{"finding_count":len(semgrep.get("results") or []) if isinstance(semgrep,dict) else 0,"rule_ids":sorted({str(x.get("check_id")) for x in (semgrep.get("results") or []) if isinstance(x,dict) and x.get("check_id")})},"trivy":{"counts":dict(sorted(trivy_counts.items()))}}


def write_canonical(path: Path, payload: Any) -> None:
    payload = sanitize_private_paths(payload)
    text=stable(payload)
    safe_text(str(path.relative_to(ROOT)),text)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def promote(run_dir: Path) -> int:
    if is_termux(): fail("supply-chain promotion is a developer/CI operation, not a Termux operation",3)
    raw=run_dir/"raw"; manifest=read_json(run_dir/"capture-manifest.json",{})
    if not raw.is_dir() or not manifest: fail("run directory has no valid transient capture manifest")
    if manifest.get("runtime_capture_performed") is not False: fail("capture manifest violates the no-live-runtime rule")
    dev_raw=raw/"syft-dev.cdx.json"; release_raw=raw/"syft-release.cdx.json"
    if not dev_raw.exists(): fail("Syft development CycloneDX output is required before promotion")
    dev_source=read_json(dev_raw,{})
    release_manifest=read_json(ROOT/"pocketlab-lite-release.json",{}) or {}
    release_binding=str(release_manifest.get("release_tag") or "unobserved") if release_manifest else None
    dev=canonical_cdx(dev_source,target="development",evidence_status="observed-syft",source_digest=digest_file(dev_raw))
    if release_raw.exists():
        release=canonical_cdx(read_json(release_raw,{}),target="release",evidence_status="observed-syft",source_digest=digest_file(release_raw),release_binding=release_binding)
    else:
        release=canonical_cdx(None,target="release",evidence_status="missing-dist.zip-at-capture",source_digest=None,release_binding=release_binding)
    runtime_baseline=read_json(RUNTIME,{}) or {}
    runtime_binding=str(runtime_baseline.get("release_tag") or runtime_baseline.get("release") or "unobserved") if runtime_baseline else None
    runtime=canonical_cdx(None,target="runtime",evidence_status="release-promoted-runtime-baseline" if RUNTIME.exists() else "missing-promoted-runtime-baseline",source_digest=digest_file(RUNTIME) if RUNTIME.exists() else None,release_binding=runtime_binding)
    runtime["components"]=runtime_components()
    vuln=correlate_vulnerabilities(raw)
    licenses=license_inventory(dev,read_json(raw/"scancode.json",{}))
    security=security_summary(raw)
    scorecard=scorecard_summary(read_json(raw/"scorecard.json",{}))
    summary={"schema_version":"1.0.0","implementation_status":"implemented","run_id":run_dir.name,"source_commit":manifest.get("source_commit"),"capture_manifest_sha256":digest_file(run_dir/"capture-manifest.json"),"raw_output_canonical":False,"runtime_capture_performed":False,"runtime_source":"contracts/parity/runtime-verification-baseline.json","artifacts":{},"tool_statuses":[{"tool":x.get("tool"),"status":x.get("status"),"exit_code":x.get("exit_code")} for x in manifest.get("tools",[]) if isinstance(x,dict)]}
    payloads={CANONICAL_FILES["sbom_dev"]:dev,CANONICAL_FILES["sbom_release"]:release,CANONICAL_FILES["sbom_runtime"]:runtime,CANONICAL_FILES["vulnerabilities"]:vuln,CANONICAL_FILES["licenses"]:licenses,CANONICAL_FILES["security"]:security,CANONICAL_FILES["scorecard"]:scorecard}
    for name,payload in payloads.items():
        write_canonical(OUT/name,payload); summary["artifacts"][name]=digest_file(OUT/name)
    write_canonical(OUT/CANONICAL_FILES["summary"],summary)
    print(f"PASS promoted sanitized supply-chain evidence from {run_dir.name}")
    print("No live runtime capture or runtime promotion was performed.")
    return 0


def check() -> int:
    missing=[name for name in CANONICAL_FILES.values() if not (OUT/name).exists()]
    if missing:
        fail("canonical supply-chain artifacts missing: "+", ".join(missing))
    for name in CANONICAL_FILES.values():
        path=OUT/name; data=read_json(path,None)
        if data is None: fail(f"invalid JSON: {path.relative_to(ROOT)}")
        safe_text(str(path.relative_to(ROOT)),stable(data))
    for key in ("sbom-dev.cdx.json","sbom-release.cdx.json","sbom-runtime.cdx.json"):
        data=read_json(OUT/key,{})
        if data.get("bomFormat")!="CycloneDX" or data.get("specVersion")!="1.6" or not isinstance(data.get("components"),list):
            fail(f"{key} is not a canonical CycloneDX 1.6 JSON document")
    release_manifest=read_json(ROOT/"pocketlab-lite-release.json",{}) or {}
    if release_manifest.get("release_tag"):
        release=read_json(OUT/"sbom-release.cdx.json",{})
        props={x.get("name"):x.get("value") for x in ((release.get("metadata") or {}).get("properties") or []) if isinstance(x,dict)}
        if props.get("pocketlab:release-binding") != str(release_manifest["release_tag"]):
            fail("sbom-release.cdx.json release binding does not match pocketlab-lite-release.json")
    print("PASS canonical supply-chain evidence is present, sanitized, release-bound where applicable, and CycloneDX 1.6-backed")
    return 0


def dependency_track_export(destination: Path) -> int:
    destination.mkdir(parents=True,exist_ok=True)
    for name in ("sbom-dev.cdx.json","sbom-release.cdx.json","sbom-runtime.cdx.json"):
        src=OUT/name
        if not src.exists(): fail(f"run supply-chain promotion first; missing {name}")
        shutil.copy2(src,destination/name)
    (destination/"README.txt").write_text("These CycloneDX files may be imported into an optional Dependency-Track instance. Pocket Lab documentation never depends on a live Dependency-Track service.\n",encoding="utf-8")
    print(f"PASS Dependency-Track import bundle staged at {destination}")
    return 0


def main() -> int:
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="mode",required=True)
    p=sub.add_parser("capture"); p.add_argument("--run-dir"); p.add_argument("--include-git-history",action="store_true")
    p=sub.add_parser("promote"); p.add_argument("--run-dir",required=True)
    sub.add_parser("check")
    p=sub.add_parser("dependency-track-export"); p.add_argument("--output",default=str(ROOT/".pocketlab-dev/documentation-security/dependency-track-import"))
    args=ap.parse_args()
    if args.mode=="capture": return capture(Path(args.run_dir).resolve() if args.run_dir else new_run_dir(),args.include_git_history)
    if args.mode=="promote": return promote(Path(args.run_dir).resolve())
    if args.mode=="check": return check()
    if args.mode=="dependency-track-export": return dependency_track_export(Path(args.output).resolve())
    return 2

if __name__=="__main__": raise SystemExit(main())
