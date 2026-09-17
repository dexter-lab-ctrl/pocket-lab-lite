#!/usr/bin/env python3
"""Security Assurance report publisher routed into the Security & Assurance hub.

The established report implementation is preserved in security_assurance_report_core.py.
This thin adapter changes the canonical publication directory and adds explicit model/evidence
navigation while retaining the existing sanitization, validation, and atomic publication path.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import security_assurance_report_core as _core

for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

REPORTS_DIR = REPO_ROOT / "docs" / "generated" / "enterprise" / "hubs" / "security-assurance" / "reports"

_ORIGINAL_RENDER_MARKDOWN = _core.render_markdown
_ORIGINAL_RENDER_INDEX = _core.render_index


def _model_links(model: Mapping[str, Any]) -> str:
    lines = [
        "", "## Model ↔ Assurance Evidence Links", "",
        "These links correlate this exact qualification with the canonical model. They do not change the authority of the Threat Model, assurance registry, or this report.", "",
    ]
    seen = set()
    for item in model.get("attack_paths", []) or []:
        ap_id = str(item.get("attack_path_id") or item.get("id") or "")
        if not ap_id or ap_id in seen:
            continue
        seen.add(ap_id)
        lines.append(
            f"- **{ap_id}** — [Security Atlas](../../../threat-model/catalog.md?atlas-attack-path={ap_id}#security-atlas) · "
            f"[Model ↔ evidence](../model-assurance-evidence.md#{ap_id.lower()})"
        )
    scenario_ids = sorted({str(item.get("scenario_id") or item.get("id") or "") for item in model.get("scenarios", []) or [] if str(item.get("scenario_id") or item.get("id") or "")})
    if scenario_ids:
        lines += ["", "**Scenarios in this qualification:** " + ", ".join(f"[`{sid}`](../scenario-model.md#{sid.lower()})" for sid in scenario_ids) + "."]
    lines += ["", "[STRIDE correlation](../stride-evidence.md) · [OWASP correlation](../owasp-evidence.md) · [How to read security documentation](../how-to-read.md)", ""]
    return "\n".join(lines)


def _human_review_clarifier(model: Mapping[str, Any]) -> str:
    rows = []
    for item in model.get("attack_paths", []) or []:
        ap_id = str(item.get("attack_path_id") or item.get("id") or "")
        if not ap_id:
            continue
        requires_human = bool(item.get("human_review_required"))
        canonical = {}
        threat = model.get("canonical_threat_model")
        if isinstance(threat, Mapping):
            canonical = next((dict(p) for p in threat.get("attack_paths", []) or [] if isinstance(p, Mapping) and str(p.get("id") or "") == ap_id), {})
        requires_human = requires_human or str(canonical.get("review_status") or "") == "human-review-required"
        rows.append((
            ap_id,
            item.get("classification") or "NOT_ASSESSED",
            item.get("status") or "NOT_ASSESSED",
            "HUMAN_REVIEW_REQUIRED" if requires_human else "NOT_APPLICABLE",
            "Automated PASS does not satisfy the human assurance decision." if requires_human else "No separate human decision is asserted by this row.",
        ))
    if not rows:
        return ""
    return "\n".join([
        "", "### Human assurance decision is separate from automation", "",
        "Threat-model review status and qualification execution classification answer different questions. A path can have automated checks that PASS while its human security-review decision remains **HUMAN_REVIEW_REQUIRED**.", "",
        "| AP | Automation classification | Automated qualification result | Human assurance decision | Interpretation |",
        "| --- | --- | --- | --- | --- |",
        *("| " + " | ".join(str(v).replace("|", "\\|") for v in row) + " |" for row in rows),
        "",
    ])


def render_markdown(model: Mapping[str, Any], history=None) -> str:
    text = _ORIGINAL_RENDER_MARKDOWN(model, history)
    marker = "\n## 19. Out of Scope\n"
    clarification = _human_review_clarifier(model)
    if marker in text and clarification:
        text = text.replace(marker, clarification + marker, 1)
    return text.rstrip() + _model_links(model) + "\n"


def render_index(models):
    base = _ORIGINAL_RENDER_INDEX(models)
    values = sorted(models, key=lambda x: (str(x.get("qualification_completed_at") or ""), str(x.get("report_id") or "")), reverse=True)
    latest = {}
    for model in values:
        suite = str(model.get("suite") or "").lower()
        if suite in {"smoke", "standard", "adversarial", "deep"} and suite not in latest:
            latest[suite] = model
    rows = []
    for suite in ("smoke", "standard", "adversarial", "deep"):
        item = latest.get(suite)
        if item is None:
            rows.append((suite.title(), "No published evidence", "—", "—", "—"))
            continue
        rows.append((suite.title(), item.get("overall_status"), str(item.get("runtime_sha") or "")[:10], item.get("qualification_id"), item.get("qualification_completed_at")))
    shas = sorted({str(item.get("runtime_sha") or "") for item in latest.values() if item.get("runtime_sha")})
    historical = max(len(values) - len(latest), 0)
    summary = [
        "", "## Latest qualification per suite", "",
        "This is a latest-per-suite view, not a synthetic cross-suite qualification verdict.", "",
        "| Suite | Result | Runtime SHA | Qualification | Completed UTC |",
        "| --- | --- | --- | --- | --- |",
        *("| " + " | ".join(str(v).replace("|", "\\|") for v in row) + " |" for row in rows),
        "",
        f"Historical qualification artifacts outside the latest-per-suite set: **{historical}**.", "",
        ("Latest suite evidence uses one runtime SHA." if shas and len(shas) == 1 else "Latest suite evidence spans different runtime SHAs or is incomplete; keep the suite qualifications separate."),
        "",
        "[Open Model ↔ Assurance Evidence](../model-assurance-evidence.md) · [How the pieces fit together](../model-and-evidence.md)", "",
    ]
    return base.rstrip() + "\n" + "\n".join(summary)


def publish_model(model, output_dir=REPORTS_DIR):
    old_markdown, old_index = _core.render_markdown, _core.render_index
    _core.render_markdown, _core.render_index = render_markdown, render_index
    try:
        return _core.publish_model(model, output_dir=output_dir)
    finally:
        _core.render_markdown, _core.render_index = old_markdown, old_index


def rebuild_index(output_dir=REPORTS_DIR):
    old_index = _core.render_index
    _core.render_index = render_index
    try:
        return _core.rebuild_index(output_dir=output_dir)
    finally:
        _core.render_index = old_index


def check_published(qualification_id, output_dir=REPORTS_DIR):
    return _core.check_published(qualification_id, output_dir=output_dir)


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
            run, report = _core._fetch_remote(args.qualification_id)
            model = _core.build_model(run, report)
            if args.command == "generate":
                result = {"status": "PASS", "report_id": model["report_id"], "qualification_id": model["qualification_id"], "model_sha256": _core._sha256_bytes(_core._canonical(model).encode("utf-8")), "sanitized": True, "canonical_report_directory": str(REPORTS_DIR)}
            else:
                result = publish_model(model)
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
        return 0
    except (OSError, _core.ReportError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)[:300], "sanitized": True}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
