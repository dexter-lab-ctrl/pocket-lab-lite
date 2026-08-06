#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PLAYWRIGHT_REPORT = ROOT / ".pocketlab-dev" / "validation" / "playwright-results.json"
TERMUX_EVIDENCE = ROOT / ".pocketlab-dev" / "validation" / "parity" / "termux" / "recovery-readonly.json"
BASELINE = ROOT / "contracts" / "parity" / "runtime-verification-baseline.json"
EXPECTED_PROJECTS = {"live-desktop", "live-mobile"}
EXPECTED_TESTS = {
    "Caddy and FastAPI render every current Lite tab without write actions",
    "live Recovery projection meaning reaches the rendered UI",
}
RELEASE_TAG_RE = re.compile(r"^lite-\d{4}\.\d{2}\.\d{2}\.\d+$")
ALLOWED_COVERAGE = {"verified", "unvalidated"}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing runtime evidence: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"runtime evidence must be an object: {path.relative_to(ROOT)}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def iter_specs(node: Any, titles: tuple[str, ...] = ()):
    if isinstance(node, dict):
        title = str(node.get("title") or "").strip()
        current = titles + ((title,) if title else ())
        if isinstance(node.get("tests"), list):
            yield current, node
        for key in ("suites", "specs"):
            for child in node.get(key, []) or []:
                yield from iter_specs(child, current)
    elif isinstance(node, list):
        for child in node:
            yield from iter_specs(child, titles)


def validate_playwright(report: dict[str, Any]) -> dict[str, Any]:
    metadata = (report.get("config") or {}).get("metadata") or {}
    if metadata.get("pocketlab_lite_mode") != "live":
        raise SystemExit("Playwright evidence is not from LITE_E2E_MODE=live")

    observed: dict[str, set[str]] = {project: set() for project in EXPECTED_PROJECTS}
    for titles, spec in iter_specs(report.get("suites", [])):
        title = str(spec.get("title") or (titles[-1] if titles else "")).strip()
        if title not in EXPECTED_TESTS:
            continue
        for test in spec.get("tests", []) or []:
            project = str(test.get("projectName") or "").strip()
            if project not in EXPECTED_PROJECTS:
                continue
            results = test.get("results") or []
            statuses = [str(result.get("status") or "") for result in results]
            if not statuses or statuses[-1] != "passed":
                raise SystemExit(f"live Playwright test did not pass: {project}: {title}")
            observed[project].add(title)

    missing = {
        project: sorted(EXPECTED_TESTS - titles)
        for project, titles in observed.items()
        if titles != EXPECTED_TESTS
    }
    if missing:
        raise SystemExit(f"live Playwright evidence is incomplete: {missing}")
    return {
        "projects": sorted(observed),
        "tests_per_project": len(EXPECTED_TESTS),
        "status": "verified",
    }


def validate_termux(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("sanitized") is not True or payload.get("status") != "observed":
        raise SystemExit("Termux evidence must be sanitized and observed")
    summary = payload.get("recovery_summary")
    if not isinstance(summary, dict):
        raise SystemExit("Termux evidence is missing recovery_summary")
    if not str(summary.get("status") or "").strip():
        raise SystemExit("Termux evidence is missing Recovery status")
    latest = summary.get("latest_backup")
    if not isinstance(latest, dict) or not str(latest.get("backup_id") or "").strip():
        raise SystemExit("Termux evidence is missing the latest backup identity")
    return {
        "status": "verified",
        "recovery_status": str(summary.get("status"))[:64],
        "read_degraded": summary.get("read_degraded") is True,
        "latest_backup_present": True,
    }


def validate_baseline(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "1.0.0" or payload.get("sanitized") is not True:
        raise SystemExit("runtime verification baseline schema/sanitization is invalid")
    source_commit = str(payload.get("source_commit") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise SystemExit("runtime verification baseline source_commit is invalid")
    release_tag = str(payload.get("release_tag") or "")
    if not RELEASE_TAG_RE.fullmatch(release_tag):
        raise SystemExit("runtime verification baseline release_tag is invalid")
    domains = payload.get("domains")
    if not isinstance(domains, list):
        raise SystemExit("runtime verification baseline domains must be an array")
    if payload.get("status") == "unvalidated" and not domains:
        return
    if payload.get("status") != "verified" or len(domains) != 1:
        raise SystemExit("verified runtime baseline must contain one promoted domain")
    recovery = domains[0]
    if recovery.get("id") != "recovery":
        raise SystemExit("only the recovery domain is eligible for this promotion")
    for key in ("live_api_coverage", "live_termux_coverage"):
        if recovery.get(key) not in ALLOWED_COVERAGE:
            raise SystemExit(f"invalid {key}")
    evidence = recovery.get("evidence")
    if not isinstance(evidence, dict):
        raise SystemExit("runtime verification baseline evidence is missing")
    for key in ("playwright_sha256", "termux_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(evidence.get(key) or "")):
            raise SystemExit(f"runtime verification baseline {key} is invalid")


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def promote(release_tag: str) -> None:
    if not RELEASE_TAG_RE.fullmatch(release_tag):
        raise SystemExit("--release-tag must use lite-YYYY.MM.DD.N")
    source_commit = git("rev-parse", "HEAD")
    tag_commit = git("rev-list", "-n", "1", release_tag)
    if tag_commit != source_commit:
        raise SystemExit(
            f"release tag {release_tag} points to {tag_commit[:12]}, not current HEAD {source_commit[:12]}"
        )

    playwright = validate_playwright(load_json(PLAYWRIGHT_REPORT))
    termux = validate_termux(load_json(TERMUX_EVIDENCE))
    payload = {
        "schema_version": "1.0.0",
        "sanitized": True,
        "promoted_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_commit": source_commit,
        "release_tag": release_tag,
        "status": "verified",
        "domains": [
            {
                "id": "recovery",
                "live_api_coverage": "verified",
                "live_termux_coverage": "verified",
                "status": "verified",
                "evidence": {
                    "playwright_sha256": sha256(PLAYWRIGHT_REPORT),
                    "termux_sha256": sha256(TERMUX_EVIDENCE),
                    "playwright": playwright,
                    "termux": termux,
                },
            }
        ],
    }
    validate_baseline(payload)
    atomic_write(BASELINE, payload)
    print(f"PASS promoted sanitized Recovery runtime verification for {release_tag}")


def check() -> None:
    validate_baseline(load_json(BASELINE))
    print("PASS promoted runtime verification baseline")


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote sanitized live parity evidence into a reviewed baseline")
    parser.add_argument("command", choices=("promote", "check"))
    parser.add_argument("--release-tag", default=os.environ.get("LITE_PARITY_RELEASE_TAG", ""))
    args = parser.parse_args()
    if args.command == "promote":
        promote(args.release_tag)
    else:
        check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
