#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jsonschema

from parity_common import ROOT, assert_safe_text, semantic_fingerprint, stable_json
from semantic_compare import compare_domain
import compare_runtime_parity as runtime_compare

PLAYWRIGHT_REPORT = ROOT / ".pocketlab-dev" / "validation" / "playwright-results.json"
PARITY_ROOT = ROOT / ".pocketlab-dev" / "validation" / "parity"
COMPARISON = PARITY_ROOT / "normalized" / "runtime-comparison.json"
BASELINE = ROOT / "contracts" / "parity" / "runtime-verification-baseline.json"
MODEL = ROOT / "contracts" / "parity" / "parity-model.json"
COMPARISON_SCHEMA = ROOT / "schemas" / "parity" / "parity-runtime-comparison.schema.json"
BASELINE_SCHEMA = ROOT / "schemas" / "parity" / "parity-runtime-baseline.schema.json"
OBSERVATION_SCHEMA = ROOT / "schemas" / "parity" / "parity-runtime-observation.schema.json"
EXPECTED_PROJECTS = {"live-desktop", "live-mobile"}
EXPECTED_TESTS = {
    "Caddy and FastAPI render every current Lite tab without write actions",
    "live Recovery projection meaning reaches the rendered UI",
    "capture sanitized semantic observations for every Lite tab",
}
RELEASE_TAG_RE = re.compile(r"^lite-\d{4}\.\d{2}\.\d{2}\.\d+$")
LEGACY_COVERAGE = {"verified", "unvalidated"}


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"missing runtime evidence: {display_path(path)}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON in {display_path(path)}: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"runtime evidence must be an object: {display_path(path)}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
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
            statuses = [str(result.get("status") or "") for result in (test.get("results") or [])]
            if not statuses or statuses[-1] != "passed":
                raise SystemExit(f"live Playwright test did not pass: {project}: {title}")
            observed[project].add(title)
    missing = {project: sorted(EXPECTED_TESTS - titles) for project, titles in observed.items() if titles != EXPECTED_TESTS}
    if missing:
        raise SystemExit(f"live Playwright evidence is incomplete: {missing}")
    return {"projects": sorted(observed), "tests_per_project": len(EXPECTED_TESTS), "status": "verified"}


def validate_legacy_baseline(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "1.0.0" or payload.get("sanitized") is not True:
        raise SystemExit("legacy runtime verification baseline schema/sanitization is invalid")
    source_commit = str(payload.get("source_commit") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise SystemExit("legacy runtime verification baseline source_commit is invalid")
    release_tag = str(payload.get("release_tag") or "")
    if not RELEASE_TAG_RE.fullmatch(release_tag):
        raise SystemExit("legacy runtime verification baseline release_tag is invalid")
    domains = payload.get("domains")
    if not isinstance(domains, list):
        raise SystemExit("legacy runtime verification baseline domains must be an array")
    if payload.get("status") == "unvalidated" and not domains:
        return
    if payload.get("status") != "verified" or len(domains) != 1 or domains[0].get("id") != "recovery":
        raise SystemExit("legacy verified runtime baseline must contain Recovery coverage")
    for key in ("live_api_coverage", "live_termux_coverage"):
        if domains[0].get(key) not in LEGACY_COVERAGE:
            raise SystemExit(f"invalid legacy {key}")


def validate_baseline(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") == "1.0.0":
        validate_legacy_baseline(payload)
    else:
        validate_v2(payload, BASELINE_SCHEMA)


def validate_v2(payload: dict[str, Any], schema_path: Path) -> None:
    schema = load_json(schema_path)
    jsonschema.Draft202012Validator(schema).validate(payload)
    assert_safe_text(stable_json(payload), schema_path.name)
    model_domains = {item["id"] for item in load_json(MODEL)["domains"]}
    payload_domains = {item["id"] for item in payload["domains"]}
    if payload_domains != model_domains:
        raise SystemExit(f"runtime baseline domains differ from canonical model: {sorted(model_domains ^ payload_domains)}")


def validate_timestamp_freshness(value: str, label: str) -> None:
    max_age_seconds = int(os.environ.get("LITE_PARITY_MAX_EVIDENCE_AGE_SECONDS", "86400"))
    try:
        captured = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise SystemExit(f"{label} timestamp is malformed") from exc
    age = (datetime.now(timezone.utc) - captured.astimezone(timezone.utc)).total_seconds()
    if age < -300 or age > max_age_seconds:
        raise SystemExit(f"{label} is stale: age_seconds={int(age)}")


def validate_freshness(payload: dict[str, Any]) -> None:
    validate_timestamp_freshness(str(payload["generated_at"]), "runtime semantic comparison")


def validate_promotable_comparison(comparison: dict[str, Any]) -> None:
    incomplete_runtime = {"partial", "capture-failed", "stale-evidence", "runtime-unavailable", "unvalidated"}
    for domain in comparison["domains"]:
        coverage = {
            domain["live_api_coverage"], domain["live_ui_coverage"], domain["live_termux_coverage"]
        }
        if coverage != {"observed"}:
            raise SystemExit(f"runtime comparison is incomplete for {domain['id']}: coverage={sorted(coverage)}")
        if domain["runtime_parity"] in incomplete_runtime:
            raise SystemExit(f"runtime comparison is incomplete for {domain['id']}: parity={domain['runtime_parity']}")
        if any(item["result"] == "not-observed" for item in domain["comparisons"]):
            raise SystemExit(f"runtime comparison contains unobserved fields for {domain['id']}")


def validate_observation(
    path: Path,
    *,
    evidence_kind: str,
    domain: str,
    source_commit: str,
    release_tag: str,
    browser_project: str = "",
) -> dict[str, Any]:
    payload = load_json(path)
    validate_v2_observation = jsonschema.Draft202012Validator(load_json(OBSERVATION_SCHEMA))
    validate_v2_observation.validate(payload)
    assert_safe_text(stable_json(payload), display_path(path))
    if payload["status"] != "observed":
        raise SystemExit(f"runtime observation is incomplete: {display_path(path)}: {payload['status']}")
    if payload["evidence_kind"] != evidence_kind or payload["domain"] != domain:
        raise SystemExit(f"runtime observation identity mismatch: {display_path(path)}")
    if payload["source_commit"] != source_commit:
        raise SystemExit(f"runtime observation source commit mismatch: {display_path(path)}")
    if payload["release_tag"] != release_tag:
        raise SystemExit(f"runtime observation release tag mismatch: {display_path(path)}")
    if evidence_kind == "frontend":
        if payload.get("browser_project") != browser_project:
            raise SystemExit(f"runtime observation browser project mismatch: {display_path(path)}")
    elif payload.get("browser_project"):
        raise SystemExit(f"non-browser observation declares a browser project: {display_path(path)}")
    validate_timestamp_freshness(str(payload["captured_at"]), f"runtime observation {domain}/{evidence_kind}")
    return payload


def validate_evidence_bundle(comparison: dict[str, Any], source_commit: str, release_tag: str) -> dict[str, str]:
    model = load_json(MODEL)
    comparison_by_domain = {item["id"]: item for item in comparison["domains"]}
    hashes: dict[str, str] = {}
    expected_paths: dict[str, set[Path]] = {kind: set() for kind in ("backend", "browser", "termux")}

    for domain in model["domains"]:
        domain_id = domain["id"]
        backend_path = PARITY_ROOT / "backend" / f"{domain_id}.json"
        termux_path = PARITY_ROOT / "termux" / f"{domain_id}.json"
        expected_paths["backend"].add(backend_path)
        expected_paths["termux"].add(termux_path)
        backend = validate_observation(
            backend_path, evidence_kind="backend", domain=domain_id,
            source_commit=source_commit, release_tag=release_tag,
        )
        termux = validate_observation(
            termux_path, evidence_kind="termux", domain=domain_id,
            source_commit=source_commit, release_tag=release_tag,
        )
        browsers: dict[str, dict[str, Any]] = {}
        for project in sorted(EXPECTED_PROJECTS):
            browser_path = PARITY_ROOT / "browser" / f"{domain_id}-{project}.json"
            expected_paths["browser"].add(browser_path)
            browsers[project] = validate_observation(
                browser_path, evidence_kind="frontend", domain=domain_id,
                source_commit=source_commit, release_tag=release_tag, browser_project=project,
            )
            hashes[f"browser-{browser_path.stem}"] = sha256(browser_path)
        hashes[f"backend-{backend_path.stem}"] = sha256(backend_path)
        hashes[f"termux-{termux_path.stem}"] = sha256(termux_path)

        recomputed = runtime_compare.termux_agreement(domain, backend, termux)
        for project, browser in browsers.items():
            for result in compare_domain(domain, backend, browser):
                result["project"] = project
                recomputed.append(result)
        recomputed.append(runtime_compare.viewport_agreement(browsers["live-desktop"], browsers["live-mobile"]))
        recomputed = sorted(recomputed, key=lambda item: (item["id"], item.get("project", "")))
        stored = comparison_by_domain[domain_id]
        if stored["comparisons"] != recomputed:
            raise SystemExit(f"runtime comparison results do not match captured evidence: {domain_id}")
        counts = {name: 0 for name in ("match", "mapped", "mismatch", "unsupported", "not-observed")}
        for item in recomputed:
            counts[item["result"]] += 1
        summary = {
            "match": counts["match"], "mapped": counts["mapped"], "mismatch": counts["mismatch"],
            "unsupported": counts["unsupported"], "not_observed": counts["not-observed"],
        }
        if stored["comparison_summary"] != summary:
            raise SystemExit(f"runtime comparison summary does not match captured evidence: {domain_id}")
        runtime_parity, status = runtime_compare.semantic_status(recomputed, ["observed"] * 4)
        if stored["runtime_parity"] != runtime_parity or stored["status"] != status:
            raise SystemExit(f"runtime comparison status does not match captured evidence: {domain_id}")
        fingerprints = {
            "backend": semantic_fingerprint(backend.get("observations") or {}),
            "termux": semantic_fingerprint(termux.get("observations") or {}),
            "live_desktop": semantic_fingerprint(browsers["live-desktop"].get("observations") or {}),
            "live_mobile": semantic_fingerprint(browsers["live-mobile"].get("observations") or {}),
        }
        if stored["observation_fingerprints"] != fingerprints:
            raise SystemExit(f"runtime comparison fingerprints do not match captured evidence: {domain_id}")

    for kind, expected in expected_paths.items():
        observed = set((PARITY_ROOT / kind).glob("*.json"))
        unexpected = observed - expected
        if unexpected:
            raise SystemExit(f"unexpected stale runtime evidence in {kind}: {[path.name for path in sorted(unexpected)]}")
    return hashes


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    text = stable_json(payload)
    assert_safe_text(text, "promoted runtime baseline")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
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
        raise SystemExit(f"release tag {release_tag} points to {tag_commit[:12]}, not current HEAD {source_commit[:12]}")

    playwright = validate_playwright(load_json(PLAYWRIGHT_REPORT))
    comparison = load_json(COMPARISON)
    validate_v2(comparison, COMPARISON_SCHEMA)
    validate_freshness(comparison)
    if comparison["source_commit"] != source_commit:
        raise SystemExit("runtime semantic comparison source commit does not match current HEAD")
    if comparison["release_tag"] != release_tag:
        raise SystemExit("runtime semantic comparison release tag does not match requested promotion tag")
    if set(comparison["browser_projects"]) != EXPECTED_PROJECTS:
        raise SystemExit("runtime semantic comparison is missing live desktop or mobile coverage")
    validate_promotable_comparison(comparison)

    evidence_hashes = {
        "playwright-report": sha256(PLAYWRIGHT_REPORT),
        "runtime-comparison": sha256(COMPARISON),
    }
    evidence_hashes.update(validate_evidence_bundle(comparison, source_commit, release_tag))

    payload = dict(comparison)
    payload["promoted_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload["evidence_hashes"] = evidence_hashes
    payload["playwright"] = playwright
    # The baseline schema is intentionally strict; Playwright detail is represented by its hash.
    payload.pop("playwright", None)
    validate_v2(payload, BASELINE_SCHEMA)
    atomic_write(BASELINE, payload)
    print(f"PASS promoted sanitized all-tab runtime semantic evidence for {release_tag}: status={payload['status']}")


def check() -> None:
    payload = load_json(BASELINE)
    if payload.get("schema_version") == "1.0.0":
        validate_legacy_baseline(payload)
        print("PASS promoted runtime verification baseline (legacy coverage-only format)")
        return
    validate_v2(payload, BASELINE_SCHEMA)
    print("PASS promoted runtime semantic verification baseline")


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote sanitized live semantic parity evidence into a reviewed baseline")
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
