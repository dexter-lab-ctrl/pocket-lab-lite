#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jsonschema

from parity_common import MODEL_PATH, ROOT, assert_safe_text, load_json, semantic_fingerprint, stable_json
import semantic_compare
from semantic_compare import compare_domain

PARITY_ROOT = ROOT / ".pocketlab-dev" / "validation" / "parity"
NORMALIZED_ROOT = PARITY_ROOT / "normalized"
OBSERVATION_SCHEMA = ROOT / "schemas" / "parity" / "parity-runtime-observation.schema.json"
COMPARISON_SCHEMA = ROOT / "schemas" / "parity" / "parity-runtime-comparison.schema.json"
EXPECTED_PROJECTS = ("live-desktop", "live-mobile")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate(payload: dict[str, Any], schema_path: Path) -> None:
    jsonschema.Draft202012Validator(load_json(schema_path)).validate(payload)
    assert_safe_text(stable_json(payload), schema_path.name)


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    text = stable_json(payload)
    if len(text.encode("utf-8")) > 512_000:
        raise RuntimeError("runtime comparison exceeds 512000 bytes")
    assert_safe_text(text, "runtime comparison")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_observation(path: Path, domain: str, kind: str, project: str = "") -> dict[str, Any]:
    if not path.exists():
        return {
            "schema_version": "2.0.0",
            "evidence_kind": kind,
            "domain": domain,
            "status": "capture-failed",
            "sanitized": True,
            "captured_at": utc_now(),
            "source_commit": "0" * 40,
            "release_tag": "",
            "browser_project": project,
            "observations": {},
            "error_code": "missing_evidence",
        }
    payload = load_json(path)
    validate(payload, OBSERVATION_SCHEMA)
    return mark_stale(payload)



def mark_stale(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("status") != "observed":
        return payload
    max_age = int(os.environ.get("LITE_PARITY_MAX_EVIDENCE_AGE_SECONDS", "86400"))
    captured = datetime.fromisoformat(str(payload["captured_at"]).replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - captured.astimezone(timezone.utc)).total_seconds()
    if age < -300 or age > max_age:
        copy = dict(payload)
        copy["status"] = "stale-evidence"
        copy["error_code"] = "stale_evidence"
        return copy
    return payload

def coverage_status(statuses: list[str]) -> str:
    if statuses and all(status == "observed" for status in statuses):
        return "observed"
    for status in ("runtime-unavailable", "capture-failed", "stale-evidence"):
        if status in statuses:
            return status
    return "unvalidated"


def semantic_status(results: list[dict[str, Any]], capture_statuses: list[str]) -> tuple[str, str]:
    if "runtime-unavailable" in capture_statuses:
        return "runtime-unavailable", "partial"
    if "capture-failed" in capture_statuses:
        return "capture-failed", "partial"
    if "stale-evidence" in capture_statuses:
        return "stale-evidence", "partial"
    values = {item["result"] for item in results}
    mismatches = [item for item in results if item.get("result") == "mismatch"]
    if mismatches:
        if all(item.get("accepted_limitation") is True for item in mismatches):
            return "accepted-limitation", "verified"
        return "drift-detected", "needs-review"
    semantic_values = {item["result"] for item in results if item.get("boundary") != "desktop-mobile"}
    if "not-observed" in semantic_values:
        return "partial", "partial"
    if "mapped" in semantic_values:
        return "verified-with-mapped-presentation", "verified"
    if semantic_values and semantic_values <= {"match", "unsupported"} and "match" in semantic_values:
        return "verified", "verified"
    if semantic_values == {"unsupported"}:
        return "unsupported", "partial"
    return "partial", "partial"


def termux_agreement(domain: dict[str, Any], backend: dict[str, Any], termux: dict[str, Any]) -> list[dict[str, Any]]:
    if backend.get("status") != "observed" or termux.get("status") != "observed":
        return []
    left = backend.get("observations") or {}
    right = termux.get("observations") or {}
    results: list[dict[str, Any]] = []
    fields = ((domain.get("live_observation_contract") or {}).get("backend") or {}).get("fields") or []
    for field in fields:
        field_id = str(field["id"])
        operator = str(field.get("authority_operator") or "exact")
        result = semantic_compare.compare_values(operator, left.get(field_id), right.get(field_id), field)
        result.update({
            "id": f"{domain['id']}-termux-{field_id}",
            "boundary": "live-api-live-termux",
            "severity": str(field.get("authority_severity") or "high"),
            "operator": operator,
            "project": "termux",
            "accepted_limitation": False,
        })
        results.append(result)
    return results


def viewport_agreement(desktop: dict[str, Any], mobile: dict[str, Any]) -> dict[str, Any]:
    left = desktop.get("observations") or {}
    right = mobile.get("observations") or {}
    semantic_keys = ("headings", "button_names", "status_labels")
    left_value = {key: sorted(set(left.get(key) or [])) for key in semantic_keys}
    right_value = {key: sorted(set(right.get(key) or [])) for key in semantic_keys}
    result = semantic_compare.compare_values("exact", left_value, right_value)
    result.update({
        "id": "desktop-mobile-semantic-agreement",
        "boundary": "desktop-mobile",
        "severity": "high",
        "operator": "set-equality",
        "explanation": (
            "desktop and mobile expose the same headings, status labels, and actions"
            if result["result"] == "match"
            else "desktop and mobile semantic surfaces differ"
        ),
        "project": "cross-viewport",
        "accepted_limitation": False,
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare sanitized backend and browser parity observations")
    parser.add_argument("--input-root", default=str(PARITY_ROOT))
    parser.add_argument("--output", default=str(NORMALIZED_ROOT / "runtime-comparison.json"))
    args = parser.parse_args()

    root = Path(args.input_root)
    model = load_json(MODEL_PATH)
    domains_out: list[dict[str, Any]] = []
    source_commits: set[str] = set()
    release_tags: set[str] = set()

    for domain in model["domains"]:
        domain_id = domain["id"]
        backend = read_observation(root / "backend" / f"{domain_id}.json", domain_id, "backend")
        termux = read_observation(root / "termux" / f"{domain_id}.json", domain_id, "termux")
        browsers = {
            project: read_observation(root / "browser" / f"{domain_id}-{project}.json", domain_id, "frontend", project)
            for project in EXPECTED_PROJECTS
        }
        all_observations = [backend, termux, *browsers.values()]
        source_commits.update(item["source_commit"] for item in all_observations if item.get("source_commit") and item["source_commit"] != "0" * 40)
        release_tags.update(item["release_tag"] for item in all_observations if item.get("release_tag"))

        comparisons: list[dict[str, Any]] = termux_agreement(domain, backend, termux)
        for project, browser in browsers.items():
            for result in compare_domain(domain, backend, browser):
                result["project"] = project
                comparisons.append(result)
        if all(browser["status"] == "observed" for browser in browsers.values()):
            comparisons.append(viewport_agreement(browsers["live-desktop"], browsers["live-mobile"]))

        statuses = [backend["status"], termux["status"], *(item["status"] for item in browsers.values())]
        runtime_parity, status = semantic_status(comparisons, statuses)
        counts = Counter(item["result"] for item in comparisons)
        domains_out.append({
            "id": domain_id,
            "label": domain["label"],
            "live_api_coverage": "observed" if backend["status"] == "observed" else backend["status"],
            "live_ui_coverage": coverage_status([item["status"] for item in browsers.values()]),
            "live_termux_coverage": "observed" if termux["status"] == "observed" else termux["status"],
            "runtime_parity": runtime_parity,
            "status": status,
            "comparison_summary": {
                "match": counts["match"],
                "mapped": counts["mapped"],
                "mismatch": counts["mismatch"],
                "unsupported": counts["unsupported"],
                "not_observed": counts["not-observed"],
            },
            "comparisons": sorted(comparisons, key=lambda item: (item["id"], item.get("project", ""))),
            "observation_fingerprints": {
                "backend": semantic_fingerprint(backend.get("observations") or {}),
                "termux": semantic_fingerprint(termux.get("observations") or {}),
                "live_desktop": semantic_fingerprint(browsers["live-desktop"].get("observations") or {}),
                "live_mobile": semantic_fingerprint(browsers["live-mobile"].get("observations") or {}),
            },
        })

    if len(source_commits) > 1:
        raise SystemExit(f"runtime observations use multiple source commits: {sorted(source_commits)}")
    if len(release_tags) > 1:
        raise SystemExit(f"runtime observations use multiple release tags: {sorted(release_tags)}")

    overall = "verified"
    if any(item["status"] == "needs-review" for item in domains_out):
        overall = "needs-review"
    elif any(item["status"] != "verified" for item in domains_out):
        overall = "partial"

    payload = {
        "schema_version": "2.0.0",
        "sanitized": True,
        "generated_at": utc_now(),
        "source_commit": next(iter(source_commits), "0" * 40),
        "release_tag": next(iter(release_tags), ""),
        "status": overall,
        "browser_projects": list(EXPECTED_PROJECTS),
        "domains": domains_out,
    }
    validate(payload, COMPARISON_SCHEMA)
    atomic_write(Path(args.output), payload)
    print(f"PASS runtime semantic comparison: {len(domains_out)} domains, status={overall}")
    return 0 if overall in {"verified", "needs-review"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
