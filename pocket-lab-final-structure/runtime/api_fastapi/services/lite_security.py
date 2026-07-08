from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
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


def default_coverage_summary(root: Path | None = None) -> dict[str, Any]:
    plan = policy.build_quick_scan_plan(root or policy.repo_root())
    return policy.redact_value({
        "profile": policy.SCAN_PROFILE_QUICK,
        "checked_targets": plan.get("checked_targets", []),
        "skipped_targets": plan.get("skipped_targets", []),
        "excluded_groups": plan.get("excluded_groups", []),
        "partial_targets": [],
        "timed_out_targets": [],
        "tool_status": {},
        "source_targets": [
            {key: item.get(key) for key in ("label", "relative", "present", "kind")}
            for item in plan.get("source_targets", [])
        ],
    })


def _scan_profile(command: dict[str, Any] | None = None) -> str:
    try:
        return policy.normalize_scan_profile((command or {}).get("profile"))
    except ValueError:
        return policy.SCAN_PROFILE_QUICK


def _coverage_from_run(run: dict[str, Any] | None = None) -> dict[str, Any]:
    coverage = (run or {}).get("coverage_summary")
    return coverage if isinstance(coverage, dict) else default_coverage_summary()


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
        "scan_profile": policy.SCAN_PROFILE_QUICK,
        "coverage_summary": default_coverage_summary(),
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
    state.setdefault("scan_profile", policy.SCAN_PROFILE_QUICK)
    state.setdefault("coverage_summary", default_coverage_summary())
    last_run = state.get("last_run") if isinstance(state.get("last_run"), dict) else None
    findings = state.get("findings") if isinstance(state.get("findings"), list) else []
    if last_run and not state.get("scan_progress"):
        state["scan_progress"] = scan_progress_for_run(last_run)
    state.setdefault("scan_progress", None)
    state.setdefault("history", security_history(current_run=last_run, current_findings=findings, current_evidence_refs=state.get("evidence_refs") or []))
    state.setdefault("finding_delta", finding_delta_for_run(last_run, findings))
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
    profile = _scan_profile(command)
    coverage_summary = default_coverage_summary(policy.allowed_scan_root(command.get("scope") or command.get("scan_root")))
    run = {
        "run_id": run_id,
        "status": "queued",
        "summary": "Quick safety check queued. Pocket Lab will check basics and skip photos, backups, and large caches.",
        "scan_profile": profile,
        "coverage_summary": coverage_summary,
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
        "tool_results": {},
        "execution_timeline": [],
    }
    run["execution_timeline"] = execution_timeline_for_phase(run, "queued")
    evidence.write_run(run_id, run)
    state = build_state(run, [], [], status_override="queued")
    evidence.write_state(state)
    return run


def mark_running(command: dict[str, Any]) -> dict[str, Any]:
    run_id = str(command.get("run_id") or command.get("command_id") or new_run_id())
    now = deps.now_utc_iso()
    existing = evidence.read_run(run_id) or {}
    profile = _scan_profile(command)
    coverage_summary = default_coverage_summary(policy.allowed_scan_root(command.get("scope") or command.get("scan_root")))
    run = {
        "run_id": run_id,
        "status": "running",
        "summary": "Quick safety check running.",
        "scan_profile": profile,
        "coverage_summary": coverage_summary,
        "tools": ["lynis", "trivy"],
        "requested_at": command.get("requested_at") or existing.get("requested_at") or now,
        "started_at": now,
        "completed_at": None,
        "partial_results": False,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "info_count": 0,
        "tool_results": {},
        "execution_timeline": [],
    }
    run["execution_timeline"] = execution_timeline_for_phase(run, "lynis_running")
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
        stage = "Running Quick Safety Check"
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

    timeline_progress = execution_timeline_progress(run.get("execution_timeline") or [], status)
    if timeline_progress:
        percent = timeline_progress["percent"]
        step = timeline_progress["step"]
        steps_total = timeline_progress["steps_total"]
        stage = timeline_progress["stage"]
    else:
        steps_total = 3

    return policy.redact_value(
        {
            "status": status,
            "stage": stage,
            "step": step,
            "steps_total": steps_total,
            "started_at": started_at,
            "elapsed_seconds": elapsed,
            "estimated_total_seconds": estimated_total,
            "estimated_remaining_seconds": remaining,
            "estimated_remaining_label": _duration_label(remaining),
            "percent": percent,
            "message": "Pocket Lab is checking basics and skipping photos, backups, and large caches in the backend worker.",
        }
    )


def _run_time_value(run: dict[str, Any]) -> float:
    for key in ("completed_at", "started_at", "requested_at"):
        parsed = _parse_iso_timestamp(run.get(key))
        if parsed:
            return parsed.timestamp()
    return 0.0


def _finding_key(finding: dict[str, Any]) -> str:
    for key in ("id", "evidence_ref"):
        value = str(finding.get(key) or "").strip()
        if value:
            return value
    return "|".join(
        str(finding.get(key) or "").strip().lower()
        for key in ("source", "category", "component", "file", "summary")
    )


def _finding_delta_item(finding: dict[str, Any]) -> dict[str, Any]:
    return policy.redact_value(
        {
            "id": finding.get("id") or _finding_key(finding),
            "source": finding.get("source"),
            "category": finding.get("category"),
            "severity": policy.normalize_severity(finding.get("severity")),
            "component": finding.get("component"),
            "file": finding.get("file"),
            "summary": finding.get("summary") or "Security finding",
            "recommendation": finding.get("recommendation"),
        }
    )


def _duration_seconds(run: dict[str, Any]) -> int | None:
    started = _parse_iso_timestamp(run.get("started_at") or run.get("requested_at"))
    completed = _parse_iso_timestamp(run.get("completed_at"))
    if not started or not completed:
        return None
    return max(0, int((completed - started).total_seconds()))


def _findings_for_run(run_id: str) -> list[dict[str, Any]]:
    summary = evidence.read_evidence_summary(run_id) or {}
    findings = summary.get("findings")
    return findings if isinstance(findings, list) else []


def _refs_for_run(run: dict[str, Any]) -> list[str]:
    refs = run.get("evidence_refs")
    if isinstance(refs, list):
        return [str(item) for item in refs]
    summary = evidence.read_evidence_summary(str(run.get("run_id") or "")) or {}
    refs = summary.get("evidence_refs")
    return [str(item) for item in refs] if isinstance(refs, list) else []


def _history_entry(run: dict[str, Any], findings: list[dict[str, Any]], evidence_refs: list[str]) -> dict[str, Any]:
    counts = count_findings(findings)
    score = run.get("score")
    if score is None:
        score = policy.score_for_counts(counts)
    try:
        score = int(score)
    except Exception:
        score = policy.score_for_counts(counts)
    status = str(run.get("status") or "unknown").lower()
    return policy.redact_value(
        {
            "run_id": run.get("run_id"),
            "status": status,
            "score": max(0, min(100, score)),
            "started_at": run.get("started_at") or run.get("requested_at"),
            "completed_at": run.get("completed_at"),
            "duration_seconds": _duration_seconds(run),
            "partial_results": bool(run.get("partial_results")),
            "critical_count": counts.get("critical", 0),
            "high_count": counts.get("high", 0),
            "medium_count": counts.get("medium", 0),
            "low_count": counts.get("low", 0),
            "info_count": counts.get("info", 0),
            "items_to_review": len([item for item in findings if policy.normalize_severity(item.get("severity")) != "info"]),
            "evidence_count": len(evidence_refs),
            "sbom_saved": any("sbom.cdx.json" in str(ref) for ref in evidence_refs),
            "tools": run.get("tools") or ["lynis", "trivy"],
            "scan_profile": run.get("scan_profile") or policy.SCAN_PROFILE_QUICK,
        }
    )


def security_history(
    *,
    current_run: dict[str, Any] | None = None,
    current_findings: list[dict[str, Any]] | None = None,
    current_evidence_refs: list[str] | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for run in evidence.list_runs(limit=40):
        run_id = str(run.get("run_id") or "")
        if not run_id:
            continue
        entries[run_id] = _history_entry(run, _findings_for_run(run_id), _refs_for_run(run))
    if current_run and current_run.get("run_id"):
        run_id = str(current_run.get("run_id"))
        entries[run_id] = _history_entry(current_run, current_findings or [], current_evidence_refs or _refs_for_run(current_run))
    ordered = sorted(entries.values(), key=lambda item: _run_time_value(item), reverse=True)
    return policy.redact_value(ordered[: max(1, limit)])


def _previous_completed_run(current_run_id: str | None) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    for run in sorted(evidence.list_runs(limit=40), key=_run_time_value, reverse=True):
        run_id = str(run.get("run_id") or "")
        if not run_id or run_id == current_run_id:
            continue
        if str(run.get("status") or "").lower() in {"succeeded", "degraded", "failed"}:
            return run, _findings_for_run(run_id)
    return None, []


def finding_delta_for_run(current_run: dict[str, Any] | None, current_findings: list[dict[str, Any]]) -> dict[str, Any]:
    current_run_id = str((current_run or {}).get("run_id") or "") or None
    previous_run, previous_findings = _previous_completed_run(current_run_id)
    if not previous_run:
        return policy.redact_value(
            {
                "baseline": "first_run",
                "previous_run_id": None,
                "new_count": 0,
                "resolved_count": 0,
                "unchanged_count": len(current_findings),
                "new": [],
                "resolved": [],
                "unchanged": [_finding_delta_item(item) for item in current_findings[:10]],
                "summary": "Baseline established. Future checks will show what changed.",
            }
        )

    current_by_key = {_finding_key(item): item for item in current_findings}
    previous_by_key = {_finding_key(item): item for item in previous_findings}
    new_keys = sorted(set(current_by_key) - set(previous_by_key))
    resolved_keys = sorted(set(previous_by_key) - set(current_by_key))
    unchanged_keys = sorted(set(current_by_key) & set(previous_by_key))
    return policy.redact_value(
        {
            "baseline": "compared",
            "previous_run_id": previous_run.get("run_id"),
            "new_count": len(new_keys),
            "resolved_count": len(resolved_keys),
            "unchanged_count": len(unchanged_keys),
            "new": [_finding_delta_item(current_by_key[key]) for key in new_keys[:10]],
            "resolved": [_finding_delta_item(previous_by_key[key]) for key in resolved_keys[:10]],
            "unchanged": [_finding_delta_item(current_by_key[key]) for key in unchanged_keys[:10]],
            "summary": "No new review items." if not new_keys else f"{len(new_keys)} new review item(s).",
        }
    )


def _timeline_step(key: str, title: str, detail: str, status: str) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "detail": detail,
        "status": status,
    }


def execution_timeline_for_phase(run: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    tool_results = run.get("tool_results") or {}
    profile = str(run.get("scan_profile") or policy.SCAN_PROFILE_QUICK)
    quick_prefix = "Quick " if profile == policy.SCAN_PROFILE_QUICK else ""
    lynis_status = str((tool_results.get("lynis") or {}).get("status") or "").lower()
    trivy_status = str((tool_results.get("trivy") or {}).get("status") or "").lower()
    posture_status = str((tool_results.get("config_posture") or {}).get("status") or "").lower()

    def tool_state(status: str) -> str:
        if status == "completed":
            return "completed"
        if status in {"timed_out", "missing_tool", "partial", "skipped", "skipped_overall_budget"}:
            return "review"
        if status in {"failed", "error"}:
            return "failed"
        return "pending"

    request_status = "completed" if phase in {
        "queued", "lynis_running", "trivy_running", "posture_running", "evidence_saving",
        "completed", "degraded", "failed"
    } else "pending"

    worker_status = "completed" if phase in {
        "lynis_running", "trivy_running", "posture_running", "evidence_saving",
        "completed", "degraded", "failed"
    } else "pending"

    if phase == "lynis_running":
        lynis_step_status = "running"
    elif phase in {"trivy_running", "posture_running", "evidence_saving", "completed", "degraded", "failed"}:
        lynis_step_status = tool_state(lynis_status or "completed")
    else:
        lynis_step_status = "pending"

    if phase == "trivy_running":
        trivy_step_status = "running"
    elif phase in {"posture_running", "evidence_saving", "completed", "degraded", "failed"}:
        trivy_step_status = tool_state(trivy_status or "completed")
    else:
        trivy_step_status = "pending"

    if phase == "posture_running":
        posture_step_status = "running"
    elif phase in {"evidence_saving", "completed", "degraded", "failed"}:
        posture_step_status = tool_state(posture_status or "completed")
    else:
        posture_step_status = "pending"

    if phase == "evidence_saving":
        evidence_status = "running"
    elif phase in {"completed", "degraded", "failed"}:
        evidence_status = "completed"
    else:
        evidence_status = "pending"

    lynis_detail = "Checks host readiness."
    if lynis_status == "completed":
        lynis_detail = "Host readiness checks completed."
    elif lynis_status == "timed_out":
        lynis_detail = "Host readiness partially checked."
    elif lynis_status == "missing_tool":
        lynis_detail = "Lynis is not available on this device."
    elif phase == "lynis_running":
        lynis_detail = "Host readiness is being checked."

    trivy_detail = "Checks Pocket Lab files while skipping photos, backups, caches, and large runtime folders."
    if trivy_status == "completed":
        trivy_detail = "Pocket Lab files, config, secret-like values, and SBOM checks completed."
    elif trivy_status == "partial":
        trivy_detail = "Trivy completed with partial results."
    elif trivy_status == "missing_tool":
        trivy_detail = "Trivy is not available on this device."
    elif phase == "trivy_running":
        trivy_detail = "Pocket Lab files are being checked with Quick Safety exclusions."

    posture_detail = "Checks service/config readiness metadata only."
    if posture_status == "completed":
        posture_detail = "Config posture metadata was checked without dumping raw config."
    elif posture_status in {"partial", "timed_out"}:
        posture_detail = "Config posture metadata was partially checked."
    elif phase == "posture_running":
        posture_detail = "Config posture metadata is being checked."

    evidence_count = len(run.get("evidence_refs") or [])
    evidence_detail = "Sanitized evidence appears after completion."
    if phase == "evidence_saving":
        evidence_detail = "Sanitized evidence is being finalized."
    elif phase in {"completed", "degraded", "failed"}:
        evidence_detail = f"{evidence_count} sanitized file(s) ready." if evidence_count else "Sanitized evidence was finalized."

    return [
        _timeline_step("request_accepted", "Request accepted", "FastAPI accepted the quick safety request.", request_status),
        _timeline_step("worker_picked_up", "Worker picked it up", "The backend worker started the bounded check.", worker_status),
        _timeline_step("lynis_host_check", f"{quick_prefix}host check", lynis_detail, lynis_step_status),
        _timeline_step("trivy_dependency_secret_check", "Pocket Lab files checked", trivy_detail, trivy_step_status),
        _timeline_step("config_posture_check", "Config posture checked", posture_detail, posture_step_status),
        _timeline_step("evidence_saved", "Evidence saved", evidence_detail, evidence_status),
    ]


def execution_timeline_progress(timeline: list[dict[str, Any]], run_status: str) -> dict[str, Any] | None:
    if not isinstance(timeline, list) or not timeline:
        return None

    total = max(1, len(timeline))
    completed_states = {"completed", "review", "failed"}
    units = 0.0
    active_index: int | None = None
    pending_index: int | None = None

    for index, step in enumerate(timeline):
        status = str((step or {}).get("status") or "").lower()
        if status in completed_states:
            units += 1.0
        elif status == "running":
            units += 0.5
            if active_index is None:
                active_index = index
        elif pending_index is None:
            pending_index = index

    status = str(run_status or "").lower()
    all_terminal_steps = all(str((step or {}).get("status") or "").lower() in completed_states for step in timeline)

    if status in {"succeeded", "degraded", "failed"} and all_terminal_steps:
        percent = 100
    else:
        percent = int(round((units / total) * 100))
        if status in {"queued", "running"}:
            percent = max(5, min(95, percent))
        else:
            percent = max(0, min(100, percent))

    current_index = active_index
    if current_index is None:
        current_index = pending_index
    if current_index is None:
        current_index = total - 1

    current = timeline[current_index] if current_index < len(timeline) else {}
    stage = str(current.get("title") or "Security check progress")

    return {
        "percent": percent,
        "step": current_index + 1,
        "steps_total": total,
        "stage": stage,
    }


def _write_intermediate_running_state(
    run: dict[str, Any],
    findings: list[dict[str, Any]],
    evidence_refs: list[str],
) -> None:
    evidence.write_run(str(run["run_id"]), run)
    evidence.write_state(
        build_state(
            run,
            findings,
            evidence_refs,
            status_override="running",
            summary_override="Quick safety check running.",
        )
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
        "scan_profile": run.get("scan_profile") or policy.SCAN_PROFILE_QUICK,
        "coverage_summary": _coverage_from_run(run),
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
            "scan_profile": run.get("scan_profile") or policy.SCAN_PROFILE_QUICK,
            "coverage_summary": _coverage_from_run(run),
            "findings": findings[:100],
            "evidence_refs": evidence_refs,
            "history": security_history(current_run=run, current_findings=findings, current_evidence_refs=evidence_refs),
            "finding_delta": finding_delta_for_run(run, findings),
            "execution_timeline": run.get("execution_timeline") or execution_timeline_for_phase(
                run,
                "completed" if str(run.get("status") or "").lower() == "succeeded"
                else "degraded" if str(run.get("status") or "").lower() == "degraded"
                else "failed" if str(run.get("status") or "").lower() == "failed"
                else "lynis_running" if str(run.get("status") or "").lower() == "running"
                else "queued"
            ),
            "scan_progress": scan_progress_for_run(run),
            "updated_at": deps.now_utc_iso(),
        }
    )


def _trivy_base_args(root: Path) -> list[str]:
    args = ["trivy", "fs"]
    args.extend(policy.trivy_skip_args(root))
    args.append(str(root))
    return args


def _write_sbom(run_id: str, trivy: str, root: Path) -> str | None:
    out = evidence.evidence_dir(run_id) / "sbom.cdx.json"
    args = [trivy, "fs", "--format", "cyclonedx", "--output", str(out)]
    args.extend(policy.trivy_skip_args(root))
    args.append(str(root))
    result = _run_command(args, cwd=root, timeout=_command_timeout("trivy_sbom"))
    if result.get("ok") and out.exists():
        existing = evidence.read_json(out, {})
        evidence.write_json(out, existing if existing else {"status": "created"})
        return f"security/evidence/{run_id}/sbom.cdx.json"
    return None


def _safe_presence(root: Path, label: str, candidates: list[str]) -> dict[str, Any]:
    for relative in candidates:
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.exists():
            return {"label": label, "status": "checked", "present": True, "kind": "directory" if candidate.is_dir() else "file"}
    return {"label": label, "status": "partial", "present": False, "kind": "missing"}


def _pm2_summary(root: Path) -> dict[str, Any]:
    pm2 = shutil.which("pm2")
    if not pm2:
        return {"label": "Services summary", "status": "partial", "available": False, "summary": "Service manager metadata is not available."}
    result = _run_command([pm2, "jlist"], cwd=root, timeout=5)
    if result.get("timed_out"):
        return {"label": "Services summary", "status": "timed_out", "available": True, "summary": "Service summary timed out."}
    payload = _load_json_text(result.get("stdout") or "")
    if not isinstance(payload, list):
        return {"label": "Services summary", "status": "partial", "available": True, "summary": "Service summary was not readable."}
    allowed_names = {
        "pocketlab-app-photoprism",
        "pocket-telemetry",
        "pocket-nats",
        "pocket-worker",
        "pocket-node-agent",
        "pocket-api",
        "caddy-proxy",
        "pocketlab-core-supervisor",
    }
    processes = []
    for item in payload[:25]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "")
        if name not in allowed_names and not name.startswith("pocketlab-agent"):
            continue
        env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
        processes.append({
            "name": name,
            "status": str(env.get("status") or item.get("status") or "unknown"),
        })
    online = len([item for item in processes if item.get("status") == "online"])
    return {
        "label": "Services summary",
        "status": "checked" if processes else "partial",
        "available": True,
        "online_count": online,
        "process_count": len(processes),
        "processes": processes[:12],
    }


def _photoprism_route_health() -> dict[str, Any]:
    if str(os.environ.get("POCKETLAB_LITE_SECURITY_CHECK_PHOTOPRISM_ROUTE", "1")).lower() in {"0", "false", "no"}:
        return {"label": "PhotoPrism route health", "status": "skipped", "summary": "Route health probe disabled."}
    request = urllib.request.Request("http://127.0.0.1:8443/apps/photoprism/api/v1/status", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=3) as response:  # nosec B310 - local same-origin health metadata only
            status_code = int(getattr(response, "status", 0) or 0)
            body = response.read(2048).decode("utf-8", errors="replace")
            payload = _load_json_text(body)
            operational = isinstance(payload, dict) and str(payload.get("status") or "").lower() == "operational"
            return {
                "label": "PhotoPrism route health",
                "status": "checked" if 200 <= status_code < 300 else "partial",
                "route_ready": operational,
                "summary": "PhotoPrism route metadata is operational." if operational else "PhotoPrism route metadata needs review.",
            }
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"label": "PhotoPrism route health", "status": "partial", "route_ready": False, "summary": "PhotoPrism route metadata was not reachable quickly."}


def runtime_config_posture(root: Path) -> dict[str, Any]:
    checks = [
        _pm2_summary(root),
        _safe_presence(root, "Caddy config posture", ["caddy/Caddyfile", "Caddyfile"]),
        _safe_presence(root, "NATS config posture", ["nats/nats-server.conf", ".pocket_lab/nats/nats-server.conf", "pocket-lab-final-structure/nats/nats-server.conf"]),
        {"label": "Security evidence state", "status": "checked", "present": evidence.security_root().exists(), "summary": "Security evidence directory metadata is available."},
        _photoprism_route_health(),
    ]
    status_values = {str(item.get("status") or "") for item in checks}
    if "timed_out" in status_values:
        status = "timed_out"
    elif "partial" in status_values:
        status = "partial"
    else:
        status = "completed"
    return policy.redact_value({"status": status, "checks": checks})


def build_coverage_summary(plan: dict[str, Any], tool_results: dict[str, Any], posture: dict[str, Any] | None = None) -> dict[str, Any]:
    partial_targets: list[str] = []
    timed_out_targets: list[str] = []
    tool_status: dict[str, str] = {}
    for tool, result in (tool_results or {}).items():
        if not isinstance(result, dict):
            continue
        status = str(result.get("status") or "unknown")
        tool_status[str(tool)] = status
        if status in {"partial", "missing_tool", "skipped_overall_budget"}:
            partial_targets.append(str(tool))
        if status in {"timed_out"}:
            timed_out_targets.append(str(tool))
    if isinstance(posture, dict):
        posture_status = str(posture.get("status") or "")
        if posture_status in {"partial"}:
            partial_targets.append("runtime config posture")
        if posture_status in {"timed_out"}:
            timed_out_targets.append("runtime config posture")
    return policy.redact_value({
        "profile": policy.SCAN_PROFILE_QUICK,
        "checked_targets": plan.get("checked_targets", []),
        "skipped_targets": plan.get("skipped_targets", []),
        "excluded_groups": plan.get("excluded_groups", []),
        "partial_targets": sorted(set(partial_targets)),
        "timed_out_targets": sorted(set(timed_out_targets)),
        "tool_status": tool_status,
        "posture_checks": (posture or {}).get("checks", []) if isinstance(posture, dict) else [],
        "source_targets": [
            {key: item.get(key) for key in ("label", "relative", "present", "kind")}
            for item in plan.get("source_targets", [])
        ],
    })


def run_security_scan(command: dict[str, Any]) -> dict[str, Any]:
    run = mark_running(command)
    run_id = str(run["run_id"])
    started = time.monotonic()
    root = policy.allowed_scan_root(command.get("scope") or command.get("scan_root"))
    plan = policy.build_quick_scan_plan(root)
    findings: list[dict[str, Any]] = []
    tool_results: dict[str, Any] = {}
    evidence_refs: list[str] = []
    partial = False
    posture: dict[str, Any] | None = None
    run["scan_profile"] = policy.SCAN_PROFILE_QUICK
    run["coverage_summary"] = build_coverage_summary(plan, tool_results)

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
    run["tool_results"] = tool_results
    run["execution_timeline"] = execution_timeline_for_phase(run, "trivy_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    if time.monotonic() - started > policy.TIMEOUTS["overall"]:
        partial = True
        tool_results["trivy"] = {"status": "skipped_overall_budget", "available": bool(shutil.which("trivy")), "finding_count": 0, "sbom_saved": False}
    else:
        trivy = shutil.which("trivy")
        if not trivy:
            missing = missing_tool_finding("trivy")
            missing["evidence_ref"] = f"security/evidence/{run_id}/trivy-normalized.json"
            findings.append(missing)
            tool_results["trivy"] = {"status": "missing_tool", "available": False}
        else:
            vuln_args = [trivy, "fs", "--format", "json", "--scanners", "vuln,misconfig"]
            vuln_args.extend(policy.trivy_skip_args(root))
            vuln_args.append(str(root))
            vuln_result = _run_command(vuln_args, cwd=root, timeout=_command_timeout("trivy_vuln_misconfig"))
            vuln_findings = normalize_trivy_json(_load_json_text(vuln_result.get("stdout") or ""), run_id, root=root)
            findings.extend(vuln_findings)

            secret_args = [trivy, "fs", "--format", "json", "--scanners", "secret"]
            secret_args.extend(policy.trivy_skip_args(root))
            secret_args.append(str(root))
            secret_result = _run_command(secret_args, cwd=root, timeout=_command_timeout("trivy_secret"))
            secret_findings = normalize_trivy_json(_load_json_text(secret_result.get("stdout") or ""), run_id, secret_mode=True, root=root)
            findings.extend(secret_findings)
            trivy_partial = bool(vuln_result.get("timed_out") or secret_result.get("timed_out"))
            partial = partial or trivy_partial
            sbom_ref = _write_sbom(run_id, trivy, root)
            if sbom_ref:
                evidence_refs.append(sbom_ref)
            tool_results["trivy"] = {
                "status": "completed" if not trivy_partial else "partial",
                "available": True,
                "vuln_returncode": vuln_result.get("returncode"),
                "secret_returncode": secret_result.get("returncode"),
                "finding_count": len(vuln_findings) + len(secret_findings),
                "sbom_saved": bool(sbom_ref),
            }

    evidence_refs.append(evidence.write_evidence(run_id, "trivy-normalized.json", {"tool": "trivy", "profile": policy.SCAN_PROFILE_QUICK, "findings": [f for f in findings if f.get("source") == "trivy"]}))
    run["tool_results"] = tool_results
    run["execution_timeline"] = execution_timeline_for_phase(run, "posture_running")
    _write_intermediate_running_state(run, findings, evidence_refs)

    posture = runtime_config_posture(root)
    tool_results["config_posture"] = {
        "status": posture.get("status") or "completed",
        "available": True,
        "finding_count": 0,
    }
    run["tool_results"] = tool_results
    run["coverage_summary"] = build_coverage_summary(plan, tool_results, posture)
    coverage_ref = evidence.write_evidence(run_id, "coverage-summary.json", run["coverage_summary"])
    if coverage_ref not in evidence_refs:
        evidence_refs.append(coverage_ref)
    run["execution_timeline"] = execution_timeline_for_phase(run, "evidence_saving")
    _write_intermediate_running_state(run, findings, evidence_refs)

    counts = count_findings(findings)
    final_status = "degraded" if partial else "succeeded"
    run.update(
        {
            "status": final_status,
            "summary": "Safety check timed out before all checks completed." if partial else "Safety check completed.",
            "completed_at": deps.now_utc_iso(),
            "partial_results": partial,
            "tool_results": tool_results,
            "coverage_summary": build_coverage_summary(plan, tool_results, posture),
            "critical_count": counts.get("critical", 0),
            "high_count": counts.get("high", 0),
            "medium_count": counts.get("medium", 0),
            "low_count": counts.get("low", 0),
            "info_count": counts.get("info", 0),
            "evidence_refs": evidence_refs,
        }
    )
    run["execution_timeline"] = execution_timeline_for_phase(run, "degraded" if partial else "completed")
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
            "coverage_summary": state.get("coverage_summary"),
            "scan_profile": state.get("scan_profile"),
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
