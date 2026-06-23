from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import deps
from . import lite_security_evidence as evidence
from . import lite_security_policy as policy


def new_run_id() -> str:
    stamp = deps.now_utc_iso().replace(":", "").replace("+", "Z").replace(".", "-")
    return f"security-{stamp}-{uuid.uuid4().hex[:8]}"


def default_state() -> dict[str, Any]:
    now = deps.now_utc_iso()
    return {
        "status": "healthy",
        "summary": "No urgent safety issues found.",
        "score": 100,
        "last_run": None,
        "checks_reviewed": 0,
        "items_to_review": 0,
        "critical_issues": [],
        "guidance": policy.GUIDANCE,
        "component_posture": component_posture([]),
        "scan_progress": None,
        "updated_at": now,
    }


def current_state() -> dict[str, Any]:
    state = evidence.read_state()
    if not state:
        return default_state()
    state.setdefault("guidance", policy.GUIDANCE)
    state.setdefault("critical_issues", [])
    state.setdefault("component_posture", component_posture(state.get("findings") or []))
    last_run = state.get("last_run") if isinstance(state.get("last_run"), dict) else None
    if last_run and not state.get("scan_progress"):
        state["scan_progress"] = scan_progress_for_run(last_run)
    state.setdefault("scan_progress", None)
    state.setdefault("updated_at", deps.now_utc_iso())
    return policy.redact_value(state)


def read_run(run_id: str) -> dict[str, Any] | None:
    return evidence.read_run(run_id)


def read_evidence(run_id: str) -> dict[str, Any] | None:
    return evidence.read_evidence_summary(run_id)


def discard_queued_run(run_id: str) -> None:
    existing = evidence.read_run(run_id)
    if existing and str(existing.get("status") or "") == "queued":
        evidence.delete_run(run_id)
    state = evidence.read_state() or {}
    last_run = state.get("last_run") or {}
    if last_run.get("run_id") == run_id and str(last_run.get("status") or "") == "queued":
        evidence.write_state(default_state())


def record_queued_run(command: dict[str, Any]) -> dict[str, Any]:
    run_id = str(command.get("run_id") or command.get("command_id") or new_run_id())
    existing = evidence.read_run(run_id)
    if existing and str(existing.get("status") or "") not in {"", "queued"}:
        return existing
    state = evidence.read_state() or {}
    last_run = state.get("last_run") or {}
    if last_run.get("run_id") == run_id and str(last_run.get("status") or "") not in {"", "queued"}:
        return last_run
    now = deps.now_utc_iso()
    run = {
        "run_id": run_id,
        "status": "queued",
        "summary": "Safety check queued. Pocket Lab will scan local security posture and dependency risks.",
        "tools": ["lynis", "trivy"],
        "requested_at": now,
        "started_at": None,
        "completed_at": None,
        "partial_results": False,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "info_count": 0,
    }
    evidence.write_run(run_id, run)
    state = build_state(run, [], [], status_override="queued")
    evidence.write_state(state)
    return run


def mark_running(command: dict[str, Any]) -> dict[str, Any]:
    run_id = str(command.get("run_id") or command.get("command_id") or new_run_id())
    now = deps.now_utc_iso()
    run = {
        "run_id": run_id,
        "status": "running",
        "summary": "Safety check running.",
        "tools": ["lynis", "trivy"],
        "requested_at": command.get("requested_at"),
        "started_at": now,
        "completed_at": None,
        "partial_results": False,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "info_count": 0,
    }
    evidence.write_run(run_id, run)
    evidence.write_state(build_state(run, [], [], status_override="running"))
    return run


def _command_timeout(name: str) -> int:
    return int(policy.TIMEOUTS.get(name, 180))


def _run_command(args: list[str], *, cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
        )
        return {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": policy.redact_text(completed.stdout or ""),
            "stderr": policy.redact_text(completed.stderr or ""),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": policy.redact_text(exc.stdout or ""),
            "stderr": policy.redact_text(exc.stderr or ""),
            "timed_out": True,
            "timeout_seconds": timeout,
        }
    except Exception as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": policy.redact_text(str(exc)), "timed_out": False}


def missing_tool_finding(source: str) -> dict[str, Any]:
    name = source.capitalize()
    return normalize_finding(
        {
            "id": f"{source}-missing-tool",
            "source": source,
            "category": "missing_tool",
            "severity": "medium",
            "component": "Security tools",
            "summary": f"{name} is not available on this device.",
            "recommendation": f"Install {name} to enable {'host posture' if source == 'lynis' else 'vulnerability and dependency'} checks.",
        }
    )


def normalize_finding(item: dict[str, Any]) -> dict[str, Any]:
    now = deps.now_utc_iso()
    severity = policy.normalize_severity(item.get("severity"))
    source = str(item.get("source") or "unknown").lower()
    category = str(item.get("category") or "misconfiguration")
    summary = str(item.get("summary") or "Security finding detected.")
    finding_id = str(item.get("id") or f"{source}-{category}-{uuid.uuid4().hex[:8]}")
    clean = {
        "id": finding_id[:160],
        "source": source,
        "category": category,
        "severity": severity,
        "component": str(item.get("component") or "Pocket Lab Lite"),
        "file": item.get("file"),
        "summary": summary,
        "recommendation": str(item.get("recommendation") or "Review this item and apply the recommended hardening step."),
        "evidence_ref": item.get("evidence_ref"),
        "first_seen": item.get("first_seen") or now,
        "last_seen": item.get("last_seen") or now,
        "status": str(item.get("status") or "open"),
    }
    return policy.redact_value({k: v for k, v in clean.items() if v is not None})


def normalize_lynis_output(result: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if result.get("timed_out"):
        findings.append(
            normalize_finding(
                {
                    "id": "lynis-timeout",
                    "source": "lynis",
                    "category": "host_hardening",
                    "severity": "medium",
                    "component": "Lite API",
                    "summary": "Lynis timed out before all host checks completed.",
                    "recommendation": "Run the safety check again while the device is charging, or increase the Lynis timeout on faster devices.",
                    "evidence_ref": f"security/evidence/{run_id}/lynis-normalized.json",
                }
            )
        )
        return findings

    raw_lines = f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}".splitlines()
    seen: set[str] = set()
    for index, line in enumerate(raw_lines):
        text = policy.clean_security_text(line)
        lowered = text.lower()
        if not text or policy.should_skip_lynis_text(text):
            continue
        if not ("warning" in lowered or "suggestion" in lowered or "hardening" in lowered or "[ warning ]" in lowered or "[ suggestion ]" in lowered):
            continue
        dedupe_key = policy.lynis_dedupe_key(text)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        severity = "high" if "warning" in lowered or "[ warning ]" in lowered else "low"
        findings.append(
            normalize_finding(
                {
                    "id": f"lynis-{index}",
                    "source": "lynis",
                    "category": "host_hardening",
                    "severity": severity,
                    "component": _component_for_text(text),
                    "summary": "Host hardening item found.",
                    "recommendation": text[:280],
                    "evidence_ref": f"security/evidence/{run_id}/lynis-normalized.json",
                }
            )
        )
        if len(findings) >= 50:
            break

    if result.get("returncode") not in {0, None} and not findings:
        findings.append(
            normalize_finding(
                {
                    "id": "lynis-nonzero",
                    "source": "lynis",
                    "category": "host_hardening",
                    "severity": "low",
                    "component": "Lite API",
                    "summary": "Lynis completed with a non-zero status.",
                    "recommendation": "Review device compatibility. Lynis can be limited on Android/Termux.",
                    "evidence_ref": f"security/evidence/{run_id}/lynis-normalized.json",
                }
            )
        )
    return findings


def _load_json_text(text: str) -> Any:
    if not text.strip():
        return {}
    try:
        return json.loads(text)
    except Exception:
        return {}


def normalize_trivy_json(payload: Any, run_id: str, *, secret_mode: bool = False, root: Path | None = None) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return findings
    for result in payload.get("Results") or []:
        if not isinstance(result, dict):
            continue
        target = str(result.get("Target") or "")
        for vuln in result.get("Vulnerabilities") or []:
            if not isinstance(vuln, dict):
                continue
            fixed = vuln.get("FixedVersion") or vuln.get("FixedVersions") or "a fixed version"
            pkg = vuln.get("PkgName") or vuln.get("PkgID") or "dependency"
            vid = vuln.get("VulnerabilityID") or uuid.uuid4().hex[:8]
            findings.append(
                normalize_finding(
                    {
                        "id": f"trivy-{vid}-{pkg}",
                        "source": "trivy",
                        "category": "dependency_vulnerability",
                        "severity": vuln.get("Severity"),
                        "component": _component_for_text(f"{target} {pkg}"),
                        "file": target,
                        "summary": "Dependency vulnerability detected.",
                        "recommendation": f"Update {pkg} to {fixed}.",
                        "evidence_ref": f"security/evidence/{run_id}/trivy-normalized.json",
                    }
                )
            )
        for misconfig in result.get("Misconfigurations") or []:
            if not isinstance(misconfig, dict):
                continue
            mid = misconfig.get("ID") or misconfig.get("AVDID") or uuid.uuid4().hex[:8]
            findings.append(
                normalize_finding(
                    {
                        "id": f"trivy-{mid}",
                        "source": "trivy",
                        "category": "misconfiguration",
                        "severity": misconfig.get("Severity"),
                        "component": _component_for_text(f"{target} {misconfig.get('Title') or ''}"),
                        "file": target,
                        "summary": str(misconfig.get("Title") or "Misconfiguration detected."),
                        "recommendation": str(misconfig.get("Resolution") or "Review and harden this configuration."),
                        "evidence_ref": f"security/evidence/{run_id}/trivy-normalized.json",
                    }
                )
            )
        for secret in result.get("Secrets") or []:
            if not isinstance(secret, dict):
                continue
            sid = secret.get("RuleID") or secret.get("ID") or uuid.uuid4().hex[:8]
            protected = secret_mode and policy.is_protected_runtime_secret(target, root)
            findings.append(
                normalize_finding(
                    {
                        "id": f"trivy-secret-{sid}-{target}",
                        "source": "trivy",
                        "category": "protected_runtime_secret" if protected else "secret_exposure",
                        "severity": "low" if protected else "critical",
                        "component": _component_for_text(target),
                        "file": target,
                        "summary": "Protected backend runtime secret found." if protected else "Potential secret-like value found.",
                        "recommendation": (
                            "Keep this server-side config locked down, exclude it from frontend assets and normal evidence, and rotate it during planned maintenance if exposure is suspected."
                            if protected
                            else "Move the value to a server-side secret store, rotate it if it was real, and keep it out of frontend assets and normal evidence."
                        ),
                        "evidence_ref": f"security/evidence/{run_id}/trivy-normalized.json",
                        "redacted": True,
                    }
                )
            )
    return findings[:250]


def _component_for_text(text: str) -> str:
    haystack = str(text or "").lower().replace("\\", "/")
    for rule in policy.COMPONENT_RULES:
        if any(match.lower() in haystack for match in rule.matchers):
            return rule.component
    return "Pocket Lab Lite"



def _parse_iso_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _estimated_security_seconds() -> int:
    try:
        configured = int(os.environ.get("POCKETLAB_LITE_SECURITY_ESTIMATED_SECONDS", "180"))
    except Exception:
        configured = 180
    return max(60, min(configured, 900))


def _duration_label(seconds: int | None) -> str:
    if seconds is None:
        return "calculating"
    safe_seconds = max(0, int(seconds))
    if safe_seconds < 10:
        return "less than 10 sec"
    if safe_seconds < 60:
        return f"about {safe_seconds} sec"
    minutes = max(1, round(safe_seconds / 60))
    return f"about {minutes} min"


def scan_progress_for_run(run: dict[str, Any]) -> dict[str, Any] | None:
    status = str(run.get("status") or "").lower()
    if not status:
        return None

    estimated_total = _estimated_security_seconds()
    started_at = run.get("started_at") or run.get("requested_at")
    started = _parse_iso_timestamp(started_at)
    now = _parse_iso_timestamp(deps.now_utc_iso()) or datetime.now(timezone.utc)
    elapsed = max(0, int((now - started).total_seconds())) if started else 0

    if status == "queued":
        percent = 5
        remaining = estimated_total
        stage = "Waiting for the backend worker"
        step = 1
    elif status == "running":
        percent = max(8, min(95, int(round((elapsed / estimated_total) * 100))))
        remaining = max(0, estimated_total - elapsed)
        stage = "Running Lynis and Trivy"
        step = 2
    elif status in {"succeeded", "degraded", "failed"}:
        percent = 100
        remaining = 0
        stage = "Safety check complete" if status != "failed" else "Safety check needs review"
        step = 3
    else:
        percent = 0
        remaining = estimated_total
        stage = "Preparing safety check"
        step = 1

    return policy.redact_value(
        {
            "status": status,
            "stage": stage,
            "step": step,
            "steps_total": 3,
            "started_at": started_at,
            "elapsed_seconds": elapsed,
            "estimated_total_seconds": estimated_total,
            "estimated_remaining_seconds": remaining,
            "estimated_remaining_label": _duration_label(remaining),
            "percent": percent,
            "message": "Pocket Lab is checking host readiness and dependency risks in the backend worker.",
        }
    )


def count_findings(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {severity: 0 for severity in policy.SEVERITIES}
    for finding in findings:
        severity = policy.normalize_severity(finding.get("severity"))
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def component_posture(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    postures: list[dict[str, Any]] = []
    for rule in policy.COMPONENT_RULES:
        related = [item for item in findings if item.get("component") == rule.component]
        severities = {policy.normalize_severity(item.get("severity")) for item in related}
        if "critical" in severities or "high" in severities:
            status = "needs_attention"
        elif related:
            status = "review"
        else:
            status = "healthy"
        postures.append(
            {
                "component": rule.component,
                "status": status,
                "checks": list(rule.checks),
                "findings": [item.get("id") for item in related[:10]],
            }
        )
    return postures


def build_state(
    run: dict[str, Any],
    findings: list[dict[str, Any]],
    evidence_refs: list[str],
    *,
    status_override: str | None = None,
    summary_override: str | None = None,
) -> dict[str, Any]:
    counts = count_findings(findings)
    score = policy.score_for_counts(counts)
    mapped_status, mapped_summary = policy.status_for_score(score, counts)
    if not status_override and mapped_status == "healthy" and any(item.get("category") == "missing_tool" for item in findings):
        mapped_status = "review"
        mapped_summary = "Needs review"
    status = status_override or mapped_status
    summary = summary_override or ("No urgent safety issues found." if status == "healthy" else mapped_summary)
    if status in {"queued", "running"}:
        summary = summary_override or ("Safety check queued." if status == "queued" else "Safety check running.")
    last_run = {
        "run_id": run.get("run_id"),
        "status": run.get("status"),
        "started_at": run.get("started_at"),
        "completed_at": run.get("completed_at"),
        "tools": run.get("tools") or ["lynis", "trivy"],
        "critical_count": counts.get("critical", 0),
        "high_count": counts.get("high", 0),
        "medium_count": counts.get("medium", 0),
        "low_count": counts.get("low", 0),
        "info_count": counts.get("info", 0),
        "partial_results": bool(run.get("partial_results")),
    }
    critical = [item for item in findings if policy.normalize_severity(item.get("severity")) == "critical"][:10]
    return policy.redact_value(
        {
            "status": status,
            "summary": summary,
            "score": score,
            "last_run": last_run,
            "checks_reviewed": len([name for name in run.get("tools", []) if name in {"lynis", "trivy"}]),
            "items_to_review": len([item for item in findings if policy.normalize_severity(item.get("severity")) != "info"]),
            "critical_issues": critical,
            "guidance": policy.GUIDANCE,
            "component_posture": component_posture(findings),
            "findings": findings[:100],
            "evidence_refs": evidence_refs,
            "scan_progress": scan_progress_for_run(run),
            "updated_at": deps.now_utc_iso(),
        }
    )


def _trivy_base_args(root: Path) -> list[str]:
    args = ["trivy", "fs"]
    for item in policy.EXCLUDED_DIRS:
        args.extend(["--skip-dirs", item])
    args.append(str(root))
    return args


def _write_sbom(run_id: str, trivy: str, root: Path) -> str | None:
    out = evidence.evidence_dir(run_id) / "sbom.cdx.json"
    args = [trivy, "fs", "--format", "cyclonedx", "--output", str(out)]
    for item in policy.EXCLUDED_DIRS:
        args.extend(["--skip-dirs", item])
    args.append(str(root))
    result = _run_command(args, cwd=root, timeout=_command_timeout("trivy_sbom"))
    if result.get("ok") and out.exists():
        existing = evidence.read_json(out, {})
        evidence.write_json(out, existing if existing else {"status": "created"})
        return f"security/evidence/{run_id}/sbom.cdx.json"
    return None


def run_security_scan(command: dict[str, Any]) -> dict[str, Any]:
    run = mark_running(command)
    run_id = str(run["run_id"])
    started = time.monotonic()
    root = policy.allowed_scan_root(command.get("scope") or command.get("scan_root"))
    findings: list[dict[str, Any]] = []
    tool_results: dict[str, Any] = {}
    evidence_refs: list[str] = []
    partial = False

    lynis = shutil.which("lynis")
    if not lynis:
        missing = missing_tool_finding("lynis")
        missing["evidence_ref"] = f"security/evidence/{run_id}/lynis-normalized.json"
        findings.append(missing)
        tool_results["lynis"] = {"status": "missing_tool", "available": False}
    else:
        result = _run_command([lynis, "audit", "system", "--quick", "--no-colors", "--quiet"], cwd=root, timeout=_command_timeout("lynis"))
        normalized = normalize_lynis_output(result, run_id)
        findings.extend(normalized)
        partial = partial or bool(result.get("timed_out"))
        tool_results["lynis"] = {
            "status": "completed" if not result.get("timed_out") else "timed_out",
            "available": True,
            "returncode": result.get("returncode"),
            "finding_count": len(normalized),
        }
    evidence_refs.append(evidence.write_evidence(run_id, "lynis-normalized.json", {"tool": "lynis", "findings": [f for f in findings if f.get("source") == "lynis"]}))

    if time.monotonic() - started > policy.TIMEOUTS["overall"]:
        partial = True
    else:
        trivy = shutil.which("trivy")
        if not trivy:
            missing = missing_tool_finding("trivy")
            missing["evidence_ref"] = f"security/evidence/{run_id}/trivy-normalized.json"
            findings.append(missing)
            tool_results["trivy"] = {"status": "missing_tool", "available": False}
        else:
            vuln_args = [trivy, "fs", "--format", "json", "--scanners", "vuln,misconfig"]
            for item in policy.EXCLUDED_DIRS:
                vuln_args.extend(["--skip-dirs", item])
            vuln_args.append(str(root))
            vuln_result = _run_command(vuln_args, cwd=root, timeout=_command_timeout("trivy_vuln_misconfig"))
            vuln_findings = normalize_trivy_json(_load_json_text(vuln_result.get("stdout") or ""), run_id, root=root)
            findings.extend(vuln_findings)

            secret_args = [trivy, "fs", "--format", "json", "--scanners", "secret"]
            for item in policy.EXCLUDED_DIRS:
                secret_args.extend(["--skip-dirs", item])
            secret_args.append(str(root))
            secret_result = _run_command(secret_args, cwd=root, timeout=_command_timeout("trivy_secret"))
            secret_findings = normalize_trivy_json(_load_json_text(secret_result.get("stdout") or ""), run_id, secret_mode=True, root=root)
            findings.extend(secret_findings)
            partial = partial or bool(vuln_result.get("timed_out") or secret_result.get("timed_out"))
            sbom_ref = _write_sbom(run_id, trivy, root)
            if sbom_ref:
                evidence_refs.append(sbom_ref)
            tool_results["trivy"] = {
                "status": "completed" if not partial else "partial",
                "available": True,
                "vuln_returncode": vuln_result.get("returncode"),
                "secret_returncode": secret_result.get("returncode"),
                "finding_count": len(vuln_findings) + len(secret_findings),
                "sbom_saved": bool(sbom_ref),
            }

    evidence_refs.append(evidence.write_evidence(run_id, "trivy-normalized.json", {"tool": "trivy", "findings": [f for f in findings if f.get("source") == "trivy"]}))

    counts = count_findings(findings)
    final_status = "degraded" if partial else "succeeded"
    run.update(
        {
            "status": final_status,
            "summary": "Safety check timed out before all checks completed." if partial else "Safety check completed.",
            "completed_at": deps.now_utc_iso(),
            "partial_results": partial,
            "tool_results": tool_results,
            "critical_count": counts.get("critical", 0),
            "high_count": counts.get("high", 0),
            "medium_count": counts.get("medium", 0),
            "low_count": counts.get("low", 0),
            "info_count": counts.get("info", 0),
            "evidence_refs": evidence_refs,
        }
    )
    state = build_state(
        run,
        findings,
        evidence_refs,
        status_override="degraded" if partial else None,
        summary_override="Safety check timed out before all checks completed." if partial else None,
    )
    summary_ref = evidence.write_evidence(
        run_id,
        "summary.json",
        {
            "run": run,
            "score": state.get("score"),
            "status": state.get("status"),
            "summary": state.get("summary"),
            "counts": counts,
            "findings": findings,
            "component_posture": state.get("component_posture"),
            "evidence_refs": evidence_refs,
        },
    )
    if summary_ref not in evidence_refs:
        evidence_refs.insert(0, summary_ref)
    run["evidence_refs"] = evidence_refs
    evidence.write_run(run_id, run)
    state["evidence_refs"] = evidence_refs
    evidence.write_state(state)
    return {"run": run, "state": state, "findings": findings, "evidence_refs": evidence_refs}
