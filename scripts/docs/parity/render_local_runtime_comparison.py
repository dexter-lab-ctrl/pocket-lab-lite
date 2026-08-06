#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = ROOT / ".pocketlab-dev/validation/parity/normalized/runtime-comparison.json"
DEFAULT_MARKDOWN = ROOT / ".pocketlab-dev/validation/parity/docs/latest-local-runtime.md"
DEFAULT_HTML = ROOT / ".pocketlab-dev/validation/parity/docs/latest-local-runtime.html"
RELEASE_RE = re.compile(r"^lite-\d{4}\.\d{2}\.\d{2}\.\d+$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_RESULTS = {
    "match", "mapped", "mismatch", "unsupported", "not-observed",
    "not-applicable", "capture-corrupted",
}
ALLOWED_PARITY = {
    "verified", "verified-with-mapped-presentation", "drift-detected",
    "accepted-limitation", "unsupported", "partial", "unvalidated",
    "capture-failed", "runtime-unavailable", "stale-evidence",
    "capture-corrupted", "contract-gap",
}


def load_comparison(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("runtime comparison must be an object")
    release = str(payload.get("release_tag") or "")
    commit = str(payload.get("source_commit") or "")
    if not RELEASE_RE.fullmatch(release):
        raise ValueError("runtime comparison release tag is invalid")
    if not COMMIT_RE.fullmatch(commit):
        raise ValueError("runtime comparison source commit is invalid")
    domains = payload.get("domains")
    if not isinstance(domains, list) or not domains:
        raise ValueError("runtime comparison domains must be a non-empty array")
    for domain in domains:
        if not isinstance(domain, dict):
            raise ValueError("runtime comparison domain must be an object")
        if domain.get("runtime_parity") not in ALLOWED_PARITY:
            raise ValueError(f"unsupported runtime parity: {domain.get('runtime_parity')}")
        for item in domain.get("comparisons", []):
            if item.get("result") not in ALLOWED_RESULTS:
                raise ValueError(f"unsupported comparison result: {item.get('result')}")
    return payload


def esc(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Latest local runtime comparison",
        "",
        "> Local, sanitized, unpromoted evidence. This report never replaces the promoted runtime baseline and is not tracked.",
        "",
        f"- Release: `{esc(payload.get('release_tag'))}`",
        f"- Source commit: `{esc(payload.get('source_commit'))}`",
        f"- Overall status: **{esc(payload.get('status'))}**",
        "",
        "## Domain summary",
        "",
        "| Domain | Implementation | Live API | Live UI | Live Termux | Runtime parity | Status |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for domain in payload["domains"]:
        lines.append(
            "| " + " | ".join([
                esc(domain.get("label") or domain.get("id")),
                esc(domain.get("implementation_status")),
                esc(domain.get("live_api_coverage")),
                esc(domain.get("live_ui_coverage")),
                esc(domain.get("live_termux_coverage")),
                esc(domain.get("runtime_parity")),
                esc(domain.get("status")),
            ]) + " |"
        )

    lines += ["", "## Findings", ""]
    findings = 0
    for domain in payload["domains"]:
        items = [
            item for item in domain.get("comparisons", [])
            if item.get("result") not in {"match", "mapped"}
        ]
        if not items:
            continue
        findings += len(items)
        lines += [f"### {esc(domain.get('label') or domain.get('id'))}", ""]
        lines += [
            "| Result | Comparison | Project | Required | Implementation | Explanation |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for item in items:
            lines.append(
                "| " + " | ".join([
                    esc(item.get("result")),
                    esc(item.get("id")),
                    esc(item.get("project")),
                    esc(item.get("required")),
                    esc(item.get("implementation_status")),
                    esc(item.get("explanation")),
                ]) + " |"
            )
        lines.append("")

    if findings == 0:
        lines.append("No non-matching local findings were recorded.")
        lines.append("")

    lines += [
        "## Interpretation",
        "",
        "- `mismatch` is verified semantic drift.",
        "- `capture-corrupted` means browser evidence is not trustworthy enough to prove parity or drift.",
        "- `contract-gap` means the parity model lacks a required implemented mapping.",
        "- `not-applicable` means an optional implemented field has no current runtime object.",
        "- `not-observed` remains blocking only when required and implemented.",
        "",
        "## Promoted baseline separation",
        "",
        "The tracked promoted baseline remains under `contracts/parity/runtime-verification-baseline.json`. Promotion stays explicit and fail-closed.",
        "",
    ]
    return "\n".join(lines)


def render_html(markdown: str) -> str:
    # Deliberately dependency-free local rendering. Markdown remains the canonical local report.
    body = html.escape(markdown)
    return """<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Latest local runtime comparison</title><style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;line-height:1.45}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f6f8fa;padding:1rem;border-radius:.5rem}</style></head><body><pre>""" + body + "</pre></body></html>\n"


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "check"), nargs="?", default="generate")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    args = parser.parse_args()

    payload = load_comparison(args.input)
    markdown = render_markdown(payload)
    html_text = render_html(markdown)

    if args.command == "check":
        if not args.markdown.exists() or args.markdown.read_text(encoding="utf-8") != markdown:
            raise SystemExit("local runtime Markdown report is missing or stale")
        if not args.html.exists() or args.html.read_text(encoding="utf-8") != html_text:
            raise SystemExit("local runtime HTML report is missing or stale")
        print("PASS latest local runtime comparison report is current")
        return 0

    write_atomic(args.markdown, markdown)
    write_atomic(args.html, html_text)
    print(f"PASS wrote local runtime report: {args.markdown.relative_to(ROOT)}")
    print(f"PASS wrote local runtime HTML: {args.html.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
