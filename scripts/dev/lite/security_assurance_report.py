#!/usr/bin/env python3
"""Publish sanitized Runtime Security Assurance evidence into MkDocs.

The publication source is the existing normalized/sanitized assurance report
bundle returned by FastAPI. Raw scanner output is never accepted. Publication
is qualification-id specific, fail-closed on sanitization metadata, staged in a
temporary directory, redaction-checked, and atomically moved into the docs tree.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
REPORTS_DIR = REPO_ROOT / "docs" / "generated" / "security-assurance" / "reports"
RUN_ID_RE = re.compile(r"^assurance-[0-9a-f]{32}$")
SAFE_FILE_RE = re.compile(r"^security-assurance-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{7,12}-assurance-[0-9a-f]{32}$")
TERMINAL = frozenset({"PASS", "FAIL", "PARTIAL", "BLOCKED", "CANCELLED"})
SEVERITIES = ("critical", "high", "medium", "low", "info")
BASELINE_STATES = ("NEW", "EXISTING", "REGRESSED", "RESOLVED", "UNCHANGED")
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_BUNDLE_BYTES = 8 * 1024 * 1024
REQUIRED_SANITIZATION = {
    "sanitized": True,
    "raw_scanner_output_persisted": False,
    "raw_credentials_persisted": False,
    "session_tokens_persisted": False,
    "key_material_persisted": False,
    "authorization_headers_persisted": False,
    "user_media_scanned": False,
    "backup_payloads_scanned": False,
}
OUT_OF_SCOPE = (
    "Destructive production Recovery or restore execution",
    "Unrelated LAN or Tailnet hosts and public Internet targets",
    "User media and PhotoPrism media contents",
    "Credential attacks or password guessing",
    "Arbitrary shell execution, caller-selected targets, ports, templates, scanner arguments, or NATS subjects",
)
SANITIZATION_EXCLUSIONS = (
    "private keys", "session tokens", "provisioning tokens", "passwords",
    "authorization headers", "cookies", "CSRF tokens", "NATS credentials",
    "Tailscale credentials", "Recovery encryption material", "raw secret matches",
    "user/PhotoPrism media", "raw scanner output",
)
REPORT_VOCABULARY = (
    ("PASS", "The registered check or scenario executed and met its required invariant for this qualification.", "The whole product is secure or certified."),
    ("PARTIAL", "Valid evidence was produced, but coverage or the resulting condition is incomplete.", "A complete failure or an automatic exploit."),
    ("FAIL", "The registered invariant executed and was not satisfied.", "The issue is automatically exploitable without review."),
    ("BLOCKED", "The harness intentionally could not proceed because a safety, admission, resource, dependency, or prerequisite condition prevented execution.", "The underlying security control necessarily failed."),
    ("CANCELLED", "The qualification or run was intentionally terminated before completion.", "PASS or FAIL."),
    ("NOT_RUN", "The registered suite or tool was not executed as part of this specific qualification.", "Broken, unsupported, failed, or a clean scan with zero findings."),
    ("DEFERRED", "Execution is intentionally postponed because the applicable prerequisite or safe executor is not currently available.", "PASS."),
    ("UNAVAILABLE", "This particular metadata value was not present in the normalized evidence used by this report.", "The whole tool or service was unavailable."),
    ("NOT_APPLICABLE", "The check does not apply to this target, profile, or qualification context.", "An applicable control was tested and passed."),
    ("HUMAN_REVIEW_REQUIRED", "The assurance decision requires a human-governed ceremony or contextual review.", "Automated PASS."),
    ("EVIDENCE_PRESENT", "Applicable evidence exists for the category.", "Every possible weakness in the category was tested."),
    ("NOT_ASSESSED", "No applicable automated evidence was produced for the category.", "PASS."),
    ("NEW", "A current finding has no matching finding in the selected baseline.", "The current code change necessarily introduced it."),
    ("EXISTING", "The finding matches the selected baseline.", "The risk has been accepted or is safe."),
    ("REGRESSED", "Baseline comparison indicates that a known condition became materially worse.", "Automatic exploitability."),
    ("RESOLVED", "A prior baseline finding is absent according to the comparison rules.", "The condition can never recur."),
    ("UNCHANGED", "The current finding materially matches the prior baseline.", "The finding is safe or accepted."),
    ("runtime-reported", "The registry intentionally delegates the tool version to runtime or service evidence instead of pinning a numeric version.", "The tool is unversioned or unknown by design."),
    ("Registered version", "The expected version or version policy declared by the hash-matched security/assurance/tools.yaml used by the qualification.", "Proof that the same version actually executed."),
    ("Observed version", "The version captured from this qualification's normalized runtime or tool receipt.", "The repository's required or pinned version."),
    ("MATCH", "A fixed registered version and an observed version are both present and match after normalization.", "A security result by itself."),
    ("MISMATCH", "A fixed registered version and an observed version are both present but do not match.", "Automatic exploitability; it is a qualification integrity issue requiring review."),
    ("NOT_OBSERVED", "A fixed registered version exists, but this qualification has no observed version for the tool.", "The tool failed; it may simply be NOT_RUN."),
    ("RUNTIME_VERSION_NOT_CAPTURED", "The registry requires runtime-reported version evidence, but this qualification did not capture a usable version value.", "The tool itself did not run when run status says otherwise."),
    ("0 findings", "No normalized findings are associated with the relevant executed evidence set.", "A NOT_RUN tool performed a clean scan."),
    ("Finding", "Sanitized normalized security evidence that requires interpretation in context.", "A demonstrated exploit."),
    ("Scenario", "A registered Pocket Lab security invariant being assessed.", "A scanner product."),
    ("Tool", "A registered evidence source used by a scenario or suite.", "The security requirement itself."),
    ("Scenario coverage", "The percentage of registered applicable scenarios with terminal evidence under the report formula.", "A security score."),
    ("Attack-path coverage", "The percentage of registered attack paths with applicable non-human-only evidence under the report formula.", "The percentage of all real-world attacks prevented."),
    ("Tool readiness", "PASS tools divided by applicable tools that actually participated in the metric; NOT_RUN and DEFERRED are excluded.", "The percentage of all registered tools installed everywhere."),
    ("Sanitized evidence", "Evidence normalized and filtered by Pocket Lab publication rules before report generation.", "Raw scanner output."),
    ("Source SHA / Runtime SHA", "The exact code revision represented by the qualification evidence.", "A later report-publication commit unless it is explicitly the same revision."),
)


class ReportError(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _safe_id(value: str) -> str:
    run_id = str(value or "").strip()
    if not RUN_ID_RE.fullmatch(run_id):
        raise ReportError("invalid qualification id")
    return run_id


def _parse_time(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _compact_timestamp(value: Any) -> str:
    parsed = _parse_time(value)
    if parsed is None:
        raise ReportError("completed qualification has no valid timestamp")
    return parsed.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _bounded_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ReportError(f"{label} is missing or invalid")
    encoded = _canonical(value).encode("utf-8")
    if len(encoded) > MAX_FILE_BYTES:
        raise ReportError(f"{label} exceeds the bounded publication size")
    return dict(value)


def validate_bundle(run: Mapping[str, Any], report: Mapping[str, Any]) -> dict[str, dict[str, Any] | str]:
    run_id = _safe_id(str(run.get("run_id") or ""))
    status = str(run.get("status") or "").upper()
    if status not in TERMINAL:
        raise ReportError("qualification is not terminal")
    if not bool(report.get("available")) or str(report.get("run_id") or "") != run_id:
        raise ReportError("sanitized qualification evidence is unavailable")
    files = report.get("files")
    if not isinstance(files, Mapping):
        raise ReportError("sanitized qualification evidence has no bounded file map")
    required = {
        "manifest.json", "environment.json", "toolchain.json", "findings.json",
        "threat-coverage.json", "owasp-coverage.json", "attack-path-results.json",
        "controls.json", "delta.json", "performance.json", "sanitization.json",
        "checksums.json", "summary.md",
    }
    missing = required - set(str(key) for key in files)
    if missing:
        raise ReportError("sanitized qualification evidence is incomplete: " + ", ".join(sorted(missing)))
    total = 0
    clean: dict[str, dict[str, Any] | str] = {}
    for name in sorted(required):
        value = files[name]
        encoded = (value if isinstance(value, str) else _canonical(value)).encode("utf-8")
        if len(encoded) > MAX_FILE_BYTES:
            raise ReportError(f"normalized evidence file {name} exceeds the publication bound")
        total += len(encoded)
        clean[name] = value if isinstance(value, str) else _bounded_mapping(value, label=name)
    if total > MAX_BUNDLE_BYTES:
        raise ReportError("normalized evidence bundle exceeds the publication bound")
    sanitation = _bounded_mapping(clean["sanitization.json"], label="sanitization.json")
    for key, expected in REQUIRED_SANITIZATION.items():
        if sanitation.get(key) is not expected:
            raise ReportError(f"sanitization marker {key} is missing or unsafe")
    manifest = _bounded_mapping(clean["manifest.json"], label="manifest.json")
    if not bool(manifest.get("sanitized")) or str(manifest.get("run_id") or "") != run_id:
        raise ReportError("manifest does not identify sanitized selected qualification")
    return clean


def _registry_hashes(manifest: Mapping[str, Any]) -> dict[str, str]:
    registry = manifest.get("registry") if isinstance(manifest.get("registry"), Mapping) else {}
    hashes = registry.get("registry_hashes") if isinstance(registry.get("registry_hashes"), Mapping) else {}
    return {str(k): str(v) for k, v in hashes.items() if str(k) and str(v)}


def _load_canonical_context(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Load canonical context only when its hash matches qualification evidence."""
    hashes = _registry_hashes(manifest)
    result: dict[str, Any] = {"threat_model": None, "tools": None, "hash_match": {}}
    candidates = {
        "threat_model": REPO_ROOT / "security" / "threat-model-scenarios.json",
        "tools": REPO_ROOT / "security" / "assurance" / "tools.yaml",
    }
    for key, path in candidates.items():
        expected = hashes.get(key)
        if not expected or not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
            result["hash_match"][key] = False
            continue
        raw = path.read_bytes()
        if _sha256_bytes(raw) != expected:
            result["hash_match"][key] = False
            continue
        try:
            if path.suffix == ".json":
                parsed = json.loads(raw.decode("utf-8"))
            else:
                import yaml
                parsed = yaml.safe_load(raw.decode("utf-8"))
        except Exception:
            result["hash_match"][key] = False
            continue
        result[key] = parsed if isinstance(parsed, Mapping) else None
        result["hash_match"][key] = isinstance(parsed, Mapping)
    return result


def _canonical_tool_map(canonical_tools: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(canonical_tools, Mapping):
        return {}
    values = canonical_tools.get("toolchain")
    if not isinstance(values, list):
        return {}
    return {
        str(item.get("id")): dict(item)
        for item in values
        if isinstance(item, Mapping) and str(item.get("id") or "")
    }


def _normalized_version(value: Any) -> str | None:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    match = re.search(r"(?<!\d)v?(\d+(?:\.\d+){1,3}(?:[-+][a-z0-9._-]+)?)", raw)
    if match:
        return match.group(1)
    return raw.removeprefix("v")


def _enrich_tools(
    tools: list[Mapping[str, Any]],
    canonical_tools: Any,
    *,
    registry_hash_matches: bool,
) -> list[dict[str, Any]]:
    canonical_map = _canonical_tool_map(canonical_tools) if registry_hash_matches else {}
    enriched: list[dict[str, Any]] = []
    for source in tools:
        item = dict(source)
        tool_id = str(item.get("tool_id") or "")
        canonical = canonical_map.get(tool_id)
        observed = item.get("version")
        status = str(item.get("status") or "").upper()
        if canonical is None:
            item.update({
                "registered_version_policy": None,
                "registered_version_source": None,
                "observed_version": observed,
                "version_state": "REGISTRY_METADATA_UNAVAILABLE",
            })
            enriched.append(item)
            continue
        policy = str(canonical.get("version_pin") or "").strip() or None
        source_name = str(canonical.get("version_source") or "").strip() or None
        if policy == "runtime-reported":
            state = "RUNTIME_REPORTED" if observed not in (None, "") else "RUNTIME_VERSION_NOT_CAPTURED"
        elif observed in (None, ""):
            state = "NOT_OBSERVED"
        else:
            expected = _normalized_version(policy)
            actual = _normalized_version(observed)
            state = "MATCH" if expected is not None and actual == expected else "MISMATCH"
        item.update({
            "registered_version_policy": policy,
            "registered_version_source": source_name,
            "observed_version": observed,
            "version_state": state,
        })
        if status == "NOT_RUN" and item.get("finding_count") in (None, ""):
            item["finding_count"] = 0
        enriched.append(item)
    return enriched


def _counts(findings: Iterable[Mapping[str, Any]]) -> tuple[dict[str, int], dict[str, int]]:
    severity = Counter(str(item.get("severity") or "info").lower() for item in findings)
    baseline = Counter(str(item.get("baseline_state") or "EXISTING").upper() for item in findings)
    return ({key: int(severity.get(key, 0)) for key in SEVERITIES}, {key: int(baseline.get(key, 0)) for key in BASELINE_STATES})


def _coverage_metrics(scenarios: list[Mapping[str, Any]], attacks: list[Mapping[str, Any]], controls: list[Mapping[str, Any]], tools: list[Mapping[str, Any]]) -> dict[str, Any]:
    executed = [s for s in scenarios if str(s.get("status") or "").upper() in TERMINAL]
    passed = [s for s in scenarios if str(s.get("status") or "").upper() == "PASS"]
    ap_total = len(attacks)
    ap_covered = sum(1 for item in attacks if str(item.get("classification") or "") not in {"", "HUMAN_REVIEW_REQUIRED"})
    control_total = len(controls)
    control_tested = sum(1 for item in controls if str(item.get("status") or "").upper() in {"PASS", "FAIL", "PARTIAL", "BLOCKED"})
    relevant_tools = [t for t in tools if str(t.get("status") or "").upper() not in {"NOT_RUN", "DEFERRED"}]
    ready_tools = [t for t in relevant_tools if str(t.get("status") or "").upper() == "PASS"]
    def pct(n: int, d: int) -> float | None:
        return round((100.0 * n / d), 1) if d else None
    return {
        "scenario_coverage_percent": pct(len(executed), len(scenarios)),
        "scenario_pass_percent": pct(len(passed), len(scenarios)),
        "attack_path_coverage_percent": pct(ap_covered, ap_total),
        "control_coverage_percent": pct(control_tested, control_total),
        "tool_readiness_percent": pct(len(ready_tools), len(relevant_tools)),
        "evidence_completeness_percent": 100.0,
        "formula": "each percentage is completed applicable evidence units divided by registered applicable units; missing/blocked units are never treated as passing",
    }


def build_model(run: Mapping[str, Any], report: Mapping[str, Any]) -> dict[str, Any]:
    files = validate_bundle(run, report)
    manifest = _bounded_mapping(files["manifest.json"], label="manifest.json")
    environment = _bounded_mapping(files["environment.json"], label="environment.json")
    toolchain = _bounded_mapping(files["toolchain.json"], label="toolchain.json")
    findings_doc = _bounded_mapping(files["findings.json"], label="findings.json")
    threat = _bounded_mapping(files["threat-coverage.json"], label="threat-coverage.json")
    owasp = _bounded_mapping(files["owasp-coverage.json"], label="owasp-coverage.json")
    attacks = _bounded_mapping(files["attack-path-results.json"], label="attack-path-results.json")
    controls_doc = _bounded_mapping(files["controls.json"], label="controls.json")
    delta = _bounded_mapping(files["delta.json"], label="delta.json")
    performance = _bounded_mapping(files["performance.json"], label="performance.json")
    findings = [dict(x) for x in findings_doc.get("findings", []) if isinstance(x, Mapping)]
    scenarios = [dict(x) for x in threat.get("scenarios", []) if isinstance(x, Mapping)]
    raw_tools = [dict(x) for x in toolchain.get("tools", []) if isinstance(x, Mapping)]
    attack_paths = [dict(x) for x in attacks.get("paths", []) if isinstance(x, Mapping)]
    controls = [dict(x) for x in controls_doc.get("controls", []) if isinstance(x, Mapping)]
    severity_counts, baseline_counts = _counts(findings)
    completed_at = performance.get("completed_at") or run.get("completed_at") or run.get("updated_at")
    timestamp = _compact_timestamp(completed_at)
    revision = str(manifest.get("revision_sha") or run.get("revision_sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ReportError("qualification has no valid source/runtime SHA")
    run_id = _safe_id(str(run.get("run_id") or manifest.get("run_id") or ""))
    report_stem = f"security-assurance-{timestamp}-{revision[:10]}-{run_id}"
    if not SAFE_FILE_RE.fullmatch(report_stem):
        raise ReportError("deterministic report identity is invalid")
    registry_hashes = _registry_hashes(manifest)
    canonical = _load_canonical_context(manifest)
    tools = _enrich_tools(
        raw_tools,
        canonical.get("tools"),
        registry_hash_matches=bool((canonical.get("hash_match") or {}).get("tools")),
    )
    metrics = _coverage_metrics(scenarios, attack_paths, controls, tools)
    suite = str(manifest.get("suite") or run.get("suite_id") or "unknown")
    suites = {name: "NOT_RUN" for name in ("smoke", "standard", "adversarial", "deep")}
    if suite in suites:
        suites[suite] = str(run.get("status") or manifest.get("status") or "PARTIAL").upper()
    model = {
        "schema_version": "1.1.0",
        "report_id": report_stem,
        "qualification_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "qualification_completed_at": str(completed_at or ""),
        "source_sha": revision,
        "runtime_sha": revision,
        "environment": "qualification" if environment.get("qualification_environment") else "unknown",
        "target_scope": str(manifest.get("target_scope") or "local_server_host_only"),
        "profile": str(manifest.get("profile") or "security-assurance-runner"),
        "suite": suite,
        "overall_status": str(run.get("status") or manifest.get("status") or "PARTIAL").upper(),
        "registry_hashes": registry_hashes,
        "canonical_context_hash_match": canonical.get("hash_match", {}),
        "severity_counts": severity_counts,
        "baseline_counts": baseline_counts,
        "metrics": metrics,
        "suite_results": suites,
        "scenarios": scenarios,
        "tools": tools,
        "findings": findings,
        "stride": threat.get("by_category", {}),
        "owasp": owasp.get("categories", []),
        "attack_paths": attack_paths,
        "controls": controls,
        "delta": delta,
        "performance": performance,
        "canonical_threat_model": canonical.get("threat_model"),
        "canonical_tools": canonical.get("tools"),
        "sanitization": dict(files["sanitization.json"]),
        "out_of_scope": list(OUT_OF_SCOPE),
        "sanitized": True,
    }
    return model


def _fmt(value: Any) -> str:
    return "UNAVAILABLE" if value is None or value == "" else str(value)


def _md_escape(value: Any) -> str:
    return str(value if value is not None else "UNAVAILABLE").replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: Iterable[Iterable[Any]]) -> list[str]:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    output.extend("| " + " | ".join(_md_escape(cell) for cell in row) + " |" for row in rows)
    return output


def _finding_tools(model: Mapping[str, Any]) -> dict[str, int]:
    counts = Counter(str(item.get("tool") or "unknown") for item in model.get("findings", []))
    return dict(sorted(counts.items()))


def _observed_version_display(tool: Mapping[str, Any]) -> str:
    observed = tool.get("observed_version")
    if observed not in (None, ""):
        return str(observed)
    if str(tool.get("status") or "").upper() == "NOT_RUN":
        return "NOT_RUN"
    return "UNAVAILABLE"


def _history_models(directory: Path, current: Mapping[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not directory.is_dir():
        return records
    for path in sorted(directory.glob("security-assurance-*.json"), reverse=True):
        if path.name == f"{current.get('report_id')}.json" or path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, Mapping) and value.get("sanitized") is True:
            records.append(dict(value))
        if len(records) >= limit:
            break
    return records


def render_markdown(model: Mapping[str, Any], history: list[Mapping[str, Any]] | None = None) -> str:
    sev = model["severity_counts"]
    baseline = model["baseline_counts"]
    metrics = model["metrics"]
    findings = list(model.get("findings", []))
    tools = list(model.get("tools", []))
    scenarios = list(model.get("scenarios", []))
    lines: list[str] = [
        f"# Security Assurance Report — {model['qualification_id']}", "",
        "!!! info \"Assurance evidence, not certification\"",
        "    This report summarizes bounded Security Assurance evidence. It does not claim that Pocket Lab Lite is certified or universally secure.", "",
        "## How to Read This Report", "",
        "This document represents **one specific Security Assurance qualification**. Status, version, finding, coverage, and baseline terms describe evidence in that qualification unless the report explicitly says otherwise.", "",
    ]
    lines += _table(["Term", "Meaning", "Does NOT mean"], REPORT_VOCABULARY)
    lines += [
        "",
        "> **Per-qualification scope:** `NOT_RUN` means the registered suite or tool did not execute in this qualification. Another suite may have separate qualification evidence.", "",
        "> **Zero findings:** `0` findings on a `NOT_RUN` tool does not mean the tool scanned and found nothing; it means this qualification has no normalized findings from an execution that did not occur.", "",
        "> **Version provenance:** **Registered version** is the expected pin/policy from the hash-matched tool registry; **Observed version** is what this qualification actually captured. They are intentionally separate.", "",
        "## 1. Executive Security Summary", "",
        f"**What was tested:** the registered **{model['suite']}** suite against **{model['target_scope']}** using the fixed harness and registered toolchain.", "",
        f"**Overall result:** **{model['overall_status']}**. The run recorded {len(scenarios)} scenario results and {len(findings)} sanitized normalized findings.", "",
        "**What needs attention:** Critical/High findings and any FAIL/PARTIAL/BLOCKED scenarios remain visible below. Human-only controls are not converted into PASS by absence of scanner findings.", "",
        "**Out of scope:** destructive Recovery, unrelated network targets, user media, credential attacks, and arbitrary command execution.", "",
        "## 2. Qualification Identity", "",
    ]
    lines += _table(["Field", "Value"], [
        ("Qualification ID", model["qualification_id"]), ("Report ID", model["report_id"]),
        ("Generation timestamp UTC", model["generated_at"]), ("Source SHA", model["source_sha"]),
        ("Runtime SHA", model["runtime_sha"]), ("Environment", model["environment"]),
        ("Target scope", model["target_scope"]), ("Profile", model["profile"]), ("Suite", model["suite"]),
        ("Tool registry hash", model["registry_hashes"].get("tools")),
        ("Scenario registry hash", model["registry_hashes"].get("scenarios")),
        ("Suite registry hash", model["registry_hashes"].get("suites")),
        ("Threat-model hash", model["registry_hashes"].get("threat_model")),
    ])
    lines += ["", "## 3. Overall Assurance Verdict", "", f"**{model['overall_status']}** — this is the harness-native terminal result; no separate security score overrides it.", "", "## 4. Security Confidence / Assurance Metrics", ""]
    lines += _table(["Metric", "Value"], [(k.replace("_", " ").title(), _fmt(v)) for k, v in metrics.items() if k != "formula"])
    lines += ["", f"Formula: {metrics['formula']}", "", "## 5. Finding Counts", ""]
    lines += _table(["Class", "Count"], [(s.title(), sev[s]) for s in SEVERITIES] + [(s, baseline[s]) for s in BASELINE_STATES])
    lines += ["", "## 6. Severity Chart", "", "```mermaid", "pie showData", '    title Sanitized findings by severity']
    for severity in SEVERITIES:
        lines.append(f'    "{severity.title()}" : {sev[severity]}')
    lines += ["```", ""] + _table(["Severity", "Findings"], [(s.title(), sev[s]) for s in SEVERITIES])
    lines += ["", "## 7. Findings by Tool", ""] + _table(["Tool", "Finding count"], _finding_tools(model).items())
    lines += ["", "## 8. Findings by Suite", ""] + _table(["Suite", "Result"], model["suite_results"].items())
    lines += ["", "## 9. Complete Finding Register", ""]
    if not findings:
        lines.append("No normalized findings were recorded for this qualification.")
    for item in sorted(findings, key=lambda x: (SEVERITIES.index(str(x.get("severity") or "info").lower()) if str(x.get("severity") or "info").lower() in SEVERITIES else 99, str(x.get("finding_id") or ""))):
        lines += ["", f"### {_md_escape(item.get('finding_id') or 'finding')}", ""]
        lines += _table(["Field", "Value"], [
            ("Severity", item.get("severity")), ("Status", item.get("status")), ("Baseline", item.get("baseline_state")),
            ("Tool", item.get("tool")), ("Scenario", item.get("scenario_id")), ("Rule ID", item.get("rule_id") or item.get("category")),
            ("CVE", ", ".join(item.get("cve") or [])), ("CWE", ", ".join(item.get("cwe") or [])),
            ("Package/component", item.get("component")), ("Asset", item.get("asset")),
            ("Title", item.get("title") or "Untitled normalized finding"),
            ("Summary", item.get("safe_summary") or item.get("title")), ("Security impact", item.get("security_impact") or "Requires review in context"),
            ("Evidence summary", ", ".join(item.get("evidence_refs") or []) or "Sanitized normalized evidence"),
            ("STRIDE", ", ".join(item.get("stride") or [])), ("OWASP", ", ".join(item.get("owasp") or [])),
            ("AP path", ", ".join(item.get("attack_paths") or [])), ("Control", ", ".join(item.get("controls") or [])),
            ("Remediation", item.get("remediation")), ("Retest guidance", f"Re-run scenario {item.get('scenario_id') or 'registered scenario'} in suite {model['suite']} after remediation."),
        ])
    lines += ["", "## 10. STRIDE Matrix", ""]
    stride_rows = []
    for category, counts in sorted((model.get("stride") or {}).items()):
        scenario_ids = [s.get("scenario_id") for s in scenarios if category in (s.get("stride") or [])]
        stride_rows.append((category, len(scenario_ids), counts.get("PASS", 0), counts.get("FAIL", 0), counts.get("PARTIAL", 0), counts.get("BLOCKED", 0), ", ".join(str(x) for x in scenario_ids)))
    lines += _table(["Threat", "Scenarios", "Passed", "Failed", "Partial", "Blocked", "Scenario IDs"], stride_rows)
    lines += ["", "## 11. OWASP Top 10 Matrix", ""]
    lines += _table(["Category", "Applicability", "Scenarios", "Passing", "Result"], [
        (f"{x.get('id')} {x.get('name')}", "TESTED" if int(x.get("scenario_count") or 0) else "HUMAN_REVIEW_REQUIRED", x.get("scenario_count", 0), x.get("passing_scenarios", 0), "EVIDENCE_PRESENT" if int(x.get("scenario_count") or 0) else "NOT_ASSESSED")
        for x in model.get("owasp", [])
    ])
    lines += ["", "## 12. Attack-Path Matrix", ""]
    canonical_paths = {}
    threat_model = model.get("canonical_threat_model")
    if isinstance(threat_model, Mapping):
        canonical_paths = {str(x.get("id")): x for x in threat_model.get("attack_paths", []) if isinstance(x, Mapping)}
    ap_rows = []
    for item in model.get("attack_paths", []):
        canonical = canonical_paths.get(str(item.get("attack_path_id")), {})
        ap_rows.append((item.get("attack_path_id"), item.get("name"), ", ".join(canonical.get("path_nodes") or []) or "UNAVAILABLE", ", ".join(canonical.get("boundaries") or []) or "UNAVAILABLE", ", ".join(item.get("controls") or []), item.get("classification"), item.get("status")))
    lines += _table(["AP", "Threat", "Assets/path", "Trust boundaries", "Controls", "Execution", "Result"], ap_rows)
    lines += ["", "## 13. Toolchain Matrix", ""]
    lines += ["Registered version metadata is loaded only from the `security/assurance/tools.yaml` whose SHA-256 matches the tool-registry hash recorded by this qualification. A registry pin is never substituted for missing observed runtime evidence.", ""]
    lines += _table(["Tool", "Registered version", "Observed version", "Version state", "Version source", "Lane", "Run status", "Findings", "Duration"], [
        (
            x.get("tool_id"),
            x.get("registered_version_policy"),
            _observed_version_display(x),
            x.get("version_state"),
            x.get("registered_version_source"),
            x.get("execution_lane") or "server_phone_worker",
            x.get("status"),
            x.get("finding_count", 0),
            _fmt(x.get("duration_ms")),
        )
        for x in tools
    ])
    perf = model.get("performance") or {}
    finish = perf.get("resource_finish") if isinstance(perf.get("resource_finish"), Mapping) else {}
    lines += ["", "## 14. Runtime / Resource Metrics", ""] + _table(["Metric", "Value"], [
        ("Duration ms", perf.get("duration_ms")), ("Available memory", finish.get("available_memory")),
        ("Battery percent", finish.get("battery_percent")), ("Temperature C", finish.get("temperature_c")),
        ("Free storage", finish.get("free_storage")), ("System load ratio", finish.get("system_load_ratio")),
        ("Retries", perf.get("retries")), ("Checkpoint/resume", perf.get("checkpoint_resume")),
    ])
    lines += ["", "## 15. Security Architecture", "", "```mermaid", "flowchart LR", "  Client[Approved client] --> Harness[Key-bound harness]", "  Harness --> API[FastAPI]", "  API --> NATS[NATS / JetStream]", "  NATS --> Worker[Worker]", "  Worker --> Runtime[Registered runtime scenarios / scanners]", "  DevStatic[DEV-PC static lane] --> Evidence[Sanitized normalized evidence]", "  DevLive[DEV-PC live-runtime lane] --> Evidence", "  Runtime --> Evidence", "  Evidence --> Report[MkDocs Security Assurance report]", "```", "", "## 16. Trust Boundaries", "", "Browser/Caddy; Caddy/FastAPI; machine/harness; FastAPI/OPA; FastAPI/NATS; NATS/worker; worker/scanner; scanner/evidence; and DEV PC/Server Phone are explicit review boundaries.", "", "## 17. Controls Validated", ""]
    lines += _table(["Control", "Scenarios", "Attack paths", "Result"], [(x.get("control_id"), ", ".join(x.get("scenario_ids") or []), ", ".join(x.get("attack_paths") or []), x.get("status")) for x in model.get("controls", [])])
    human = [x for x in model.get("attack_paths", []) if x.get("human_review_required")]
    lines += ["", "## 18. Human Review Required", "", "Physical WebAuthn ceremonies, Enterprise membership/final Owner authority, approval ceremonies, and protected runtime-secret ownership/rotation remain human-governed where applicable.", ""]
    if human:
        lines += _table(["AP", "Reason"], [(x.get("attack_path_id"), x.get("reason")) for x in human])
    lines += ["", "## 19. Out of Scope", ""] + [f"- {item}" for item in model["out_of_scope"]]
    lines += ["", "## 20. Remediation Priorities", ""]
    actionable = [x for x in findings if str(x.get("status") or "open") != "resolved"]
    if actionable:
        lines += _table(["Severity", "Finding", "Remediation"], [(x.get("severity"), x.get("finding_id"), x.get("remediation")) for x in actionable])
    else:
        lines.append("No open normalized findings were recorded. Incomplete or blocked scenario evidence still requires review above.")
    lines += ["", "## 21. Retest Plan", ""]
    if actionable:
        lines += _table(["Finding", "Scenario", "Suite", "Expected fixed invariant"], [(x.get("finding_id"), x.get("scenario_id"), model["suite"], "The registered scenario reaches its expected invariant without the finding recurring.") for x in actionable])
    else:
        lines.append("Re-run the same suite after material security-control changes and compare against this qualification ID.")
    lines += ["", "## 22. Sanitization Statement", "", "This publication contains normalized sanitized evidence only. It excludes: " + ", ".join(SANITIZATION_EXCLUSIONS) + ".", ""]
    historical = list(history or [])
    if historical:
        lines += ["## Historical Trend (bounded)", ""]
        rows = []
        for old in historical:
            compatible = old.get("registry_hashes") == model.get("registry_hashes")
            rows.append((old.get("qualification_completed_at"), old.get("overall_status"), old.get("severity_counts", {}).get("critical"), old.get("severity_counts", {}).get("high"), old.get("severity_counts", {}).get("medium"), old.get("metrics", {}).get("scenario_coverage_percent"), "compatible" if compatible else "different registry revision"))
        lines += _table(["Completed", "Result", "Critical", "High", "Medium", "Scenario coverage %", "Comparison"], rows)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _redaction_failures(paths: Iterable[Path]) -> list[str]:
    sys.path.insert(0, str(SCRIPT_DIR))
    import redaction_check
    failures: list[str] = []
    for root in paths:
        for file in redaction_check.files_for(root):
            text = file.read_text(encoding="utf-8", errors="ignore")
            for label, pattern in redaction_check.PATTERNS.items():
                if pattern.search(text):
                    failures.append(f"{file.name}:{label}")
    return failures


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n")


def render_index(models: list[Mapping[str, Any]]) -> str:
    rows = []
    for model in sorted(models, key=lambda x: (str(x.get("qualification_completed_at") or ""), str(x.get("report_id") or "")), reverse=True):
        sev = model.get("severity_counts") or {}
        metrics = model.get("metrics") or {}
        rows.append((model.get("qualification_completed_at"), str(model.get("runtime_sha") or "")[:10], model.get("qualification_id"), model.get("overall_status"), sev.get("critical", 0), sev.get("high", 0), sev.get("medium", 0), sev.get("low", 0), sev.get("info", 0), model.get("suite"), _fmt(metrics.get("scenario_coverage_percent")), f"[{model.get('report_id')}]({model.get('report_id')}.md)"))
    lines = ["# Security Assurance Reports", "", "Generated reports are sanitized assurance evidence, not security certifications. The newest report is listed first.", ""]
    lines += _table(["Completed UTC", "Runtime SHA", "Qualification", "Result", "Critical", "High", "Medium", "Low", "Info", "Suite", "Coverage %", "Report"], rows)
    return "\n".join(lines).rstrip() + "\n"


def _existing_models(directory: Path) -> list[dict[str, Any]]:
    result = []
    if not directory.is_dir():
        return result
    for path in sorted(directory.glob("security-assurance-*.json")):
        if path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, Mapping) and value.get("sanitized") is True and SAFE_FILE_RE.fullmatch(str(value.get("report_id") or "")):
            result.append(dict(value))
    return result


def publish_model(model: dict[str, Any], output_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    report_id = str(model.get("report_id") or "")
    if not SAFE_FILE_RE.fullmatch(report_id):
        raise ReportError("report id is invalid")
    md_path = output_dir / f"{report_id}.md"
    json_path = output_dir / f"{report_id}.json"
    if md_path.exists() or json_path.exists():
        if md_path.is_file() and json_path.is_file():
            try:
                existing = json.loads(json_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise ReportError("existing report identity is not readable") from None
            if isinstance(existing, Mapping) and existing.get("qualification_id") == model.get("qualification_id") and existing.get("source_sha") == model.get("source_sha"):
                return {"status": "idempotent", "report_id": report_id, "markdown": str(md_path), "json": str(json_path), "index": str(output_dir / "index.md")}
        raise ReportError("report identity already exists with different content")
    output_dir.mkdir(parents=True, exist_ok=True)
    history = _history_models(output_dir, model)
    markdown = render_markdown(model, history)
    existing = _existing_models(output_dir)
    index_text = render_index([*existing, model])
    with tempfile.TemporaryDirectory(prefix=".security-assurance-report-", dir=str(output_dir.parent)) as tmp:
        staging = Path(tmp)
        staged_md = staging / md_path.name
        staged_json = staging / json_path.name
        staged_index = staging / "index.md"
        _write_text(staged_md, markdown)
        _write_json(staged_json, model)
        _write_text(staged_index, index_text)
        failures = _redaction_failures((staging,))
        if failures:
            raise ReportError("redaction validation blocked report publication: " + ", ".join(failures[:8]))
        os.replace(staged_md, md_path)
        os.replace(staged_json, json_path)
        os.replace(staged_index, output_dir / "index.md")
    return {"status": "published", "report_id": report_id, "markdown": str(md_path), "json": str(json_path), "index": str(output_dir / "index.md")}


def rebuild_index(output_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    models = _existing_models(output_dir)
    text = render_index(models)
    with tempfile.TemporaryDirectory(prefix=".security-assurance-index-", dir=str(output_dir.parent)) as tmp:
        staged = Path(tmp) / "index.md"
        _write_text(staged, text)
        failures = _redaction_failures((staged,))
        if failures:
            raise ReportError("redaction validation blocked report index publication")
        os.replace(staged, output_dir / "index.md")
    return {"status": "published", "report_count": len(models), "index": str(output_dir / "index.md")}


def check_published(qualification_id: str, output_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    run_id = _safe_id(qualification_id)
    matches = [m for m in _existing_models(output_dir) if m.get("qualification_id") == run_id]
    if len(matches) != 1:
        raise ReportError("exactly one published report was not found for the qualification")
    model = matches[0]
    report_id = str(model["report_id"])
    md = output_dir / f"{report_id}.md"
    js = output_dir / f"{report_id}.json"
    index = output_dir / "index.md"
    if not all(path.is_file() for path in (md, js, index)):
        raise ReportError("published report files or index are missing")
    if f"({report_id}.md)" not in index.read_text(encoding="utf-8"):
        raise ReportError("report index does not link the selected report")
    failures = _redaction_failures((md, js, index))
    if failures:
        raise ReportError("redaction validation failed for published report")
    sev, base = _counts(model.get("findings", []))
    if sev != model.get("severity_counts") or base != model.get("baseline_counts"):
        raise ReportError("published finding counts do not reconcile")
    return {"status": "PASS", "qualification_id": run_id, "report_id": report_id, "sanitized": True}


def _fetch_remote(qualification_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    sys.path.insert(0, str(SCRIPT_DIR))
    import security_assurance as client
    run_id = _safe_id(qualification_id)
    run = client._request("GET", f"/api/lite/harness/security-assurance/runs/{run_id}", authenticated=True)
    report = client._request("GET", f"/api/lite/harness/security-assurance/runs/{run_id}/report", authenticated=True)
    return run, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("generate", "publish", "check"):
        item = sub.add_parser(name)
        item.add_argument("--qualification-id", required=True)
    sub.add_parser("index")
    args = parser.parse_args()
    try:
        if args.command == "index":
            result = rebuild_index()
        elif args.command == "check":
            result = check_published(args.qualification_id)
        else:
            run, report = _fetch_remote(args.qualification_id)
            model = build_model(run, report)
            if args.command == "generate":
                result = {"status": "PASS", "report_id": model["report_id"], "qualification_id": model["qualification_id"], "model_sha256": _sha256_bytes(_canonical(model).encode("utf-8")), "sanitized": True}
            else:
                result = publish_model(model)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
        return 0
    except (OSError, ReportError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)[:300], "sanitized": True}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
