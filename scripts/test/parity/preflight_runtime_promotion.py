#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
PARITY_ROOT = ROOT / ".pocketlab-dev" / "validation" / "parity"
NORMALIZED = PARITY_ROOT / "normalized" / "runtime-comparison.json"
MODEL = ROOT / "contracts" / "parity" / "parity-model.json"
COMPARATOR = ROOT / "scripts" / "test" / "parity" / "compare_runtime_parity.py"

TAG_RE = re.compile(
    r"^lite-[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[1-9][0-9]*$"
)

EXPECTED_RELEASE_ASSETS = {
    "dist.zip",
    "checksums.txt",
    "pocketlab-lite-release.json",
}


class PreflightError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise PreflightError(message)


def run(
    *args: str,
    check: bool = True,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(args),
            cwd=ROOT,
            check=check,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        fail(f"required command is unavailable: {args[0]}")
        raise AssertionError from exc
    except subprocess.TimeoutExpired as exc:
        fail(
            "command timed out: "
            + " ".join(args)
        )
        raise AssertionError from exc


def output(*args: str, timeout: int = 30) -> str:
    return run(
        *args,
        timeout=timeout,
    ).stdout.strip()


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"required evidence file is missing: {path.relative_to(ROOT)}")

    try:
        value = json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        fail(
            f"invalid JSON evidence: {path.relative_to(ROOT)}: {exc}"
        )

    if not isinstance(value, dict):
        fail(
            f"evidence root must be an object: {path.relative_to(ROOT)}"
        )

    return value


def git(*args: str) -> str:
    return output("git", *args)


def local_tag_exists(tag: str) -> bool:
    result = run(
        "git",
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/tags/{tag}",
        check=False,
    )
    return result.returncode == 0


def remote_tag_exists(tag: str) -> bool:
    result = run(
        "git",
        "ls-remote",
        "--exit-code",
        "--tags",
        "origin",
        f"refs/tags/{tag}",
        f"refs/tags/{tag}^{{}}",
        check=False,
        timeout=30,
    )
    return result.returncode == 0


def ensure_local_tag(tag: str) -> bool:
    if local_tag_exists(tag):
        print(f"PASS local release tag exists: {tag}")
        return False

    if not remote_tag_exists(tag):
        fail(
            f"release tag {tag} is absent locally and on origin"
        )

    print(
        f"FIX local release tag missing; fetching immutable tag {tag}"
    )

    result = run(
        "git",
        "fetch",
        "--no-tags",
        "origin",
        f"refs/tags/{tag}:refs/tags/{tag}",
        check=False,
        timeout=60,
    )

    if result.returncode != 0:
        fail(
            f"could not fetch release tag {tag}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    if not local_tag_exists(tag):
        fail(
            f"release tag {tag} still missing after fetch"
        )

    print(f"PASS fetched local release tag: {tag}")
    return True


def github_release(tag: str) -> dict[str, Any]:
    if shutil.which("gh") is None:
        fail(
            "GitHub CLI is unavailable; cannot verify the GitHub release"
        )

    result = run(
        "gh",
        "release",
        "view",
        tag,
        "--json",
        "tagName,isDraft,isPrerelease,publishedAt,assets",
        check=False,
        timeout=30,
    )

    if result.returncode != 0:
        fail(
            f"GitHub release {tag} was not found: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        fail(f"GitHub release metadata is invalid JSON: {exc}")

    if payload.get("tagName") != tag:
        fail(
            f"GitHub release returned unexpected tag "
            f"{payload.get('tagName')!r}"
        )

    if payload.get("isDraft"):
        fail(f"GitHub release {tag} is still a draft")

    assets = {
        str(item.get("name") or "")
        for item in payload.get("assets", [])
        if isinstance(item, dict)
    }

    missing = EXPECTED_RELEASE_ASSETS - assets
    if missing:
        fail(
            "GitHub release is missing required assets: "
            + ", ".join(sorted(missing))
        )

    print(
        "PASS GitHub release exists with required assets: "
        + ", ".join(sorted(EXPECTED_RELEASE_ASSETS))
    )

    return payload


def verify_release_manifest(
    tag: str,
    tag_commit: str,
) -> None:
    with tempfile.TemporaryDirectory(
        prefix="pocketlab-parity-release-"
    ) as temporary:
        directory = Path(temporary)

        result = run(
            "gh",
            "release",
            "download",
            tag,
            "--pattern",
            "pocketlab-lite-release.json",
            "--dir",
            str(directory),
            check=False,
            timeout=60,
        )

        if result.returncode != 0:
            fail(
                "could not download release manifest: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

        manifest_path = (
            directory / "pocketlab-lite-release.json"
        )
        manifest = load_json(manifest_path)

        if manifest.get("release_tag") != tag:
            fail(
                "release manifest tag does not match requested release"
            )

        if manifest.get("source_commit") != tag_commit:
            fail(
                "release manifest source commit does not match "
                f"tag commit: manifest={manifest.get('source_commit')} "
                f"tag={tag_commit}"
            )

        if manifest.get("artifact") != "dist.zip":
            fail(
                "release manifest does not identify dist.zip "
                "as the release artifact"
            )

    print(
        "PASS release manifest is bound to requested tag and commit"
    )


def domain_ids() -> list[str]:
    model = load_json(MODEL)

    domains = model.get("domains")
    if not isinstance(domains, list):
        fail("parity model domains must be an array")

    ids: list[str] = []

    for item in domains:
        if not isinstance(item, dict):
            fail("parity model domain entry is invalid")

        domain_id = str(item.get("id") or "").strip()
        if not domain_id:
            fail("parity model contains an empty domain id")

        ids.append(domain_id)

    if len(ids) != len(set(ids)):
        fail("parity model contains duplicate domain ids")

    return ids


def evidence_paths(
    domains: list[str],
) -> list[tuple[Path, str, str | None]]:
    paths: list[tuple[Path, str, str | None]] = []

    for domain in domains:
        paths.append(
            (
                PARITY_ROOT / "backend" / f"{domain}.json",
                "backend",
                None,
            )
        )
        paths.append(
            (
                PARITY_ROOT / "termux" / f"{domain}.json",
                "termux",
                None,
            )
        )

        for project in (
            "live-desktop",
            "live-mobile",
        ):
            paths.append(
                (
                    PARITY_ROOT
                    / "browser"
                    / f"{domain}-{project}.json",
                    "frontend",
                    project,
                )
            )

    return paths


def verify_evidence(
    tag: str,
    tag_commit: str,
    domains: list[str],
) -> list[Path]:
    paths = evidence_paths(domains)
    observed_paths: list[Path] = []

    for path, evidence_kind, browser_project in paths:
        payload = load_json(path)
        observed_paths.append(path)

        relative = path.relative_to(ROOT)

        if payload.get("release_tag") != tag:
            fail(
                f"{relative}: release mismatch "
                f"(found {payload.get('release_tag')!r}, expected {tag!r}). "
                "Re-run fresh runtime capture for this release."
            )

        if payload.get("source_commit") != tag_commit:
            fail(
                f"{relative}: source commit mismatch "
                f"(found {payload.get('source_commit')!r}, "
                f"expected {tag_commit!r}). "
                "Re-run fresh runtime capture after installing the release."
            )

        if payload.get("sanitized") is not True:
            fail(
                f"{relative}: evidence is not marked sanitized"
            )

        if payload.get("status") != "observed":
            fail(
                f"{relative}: evidence status is "
                f"{payload.get('status')!r}, expected 'observed'"
            )

        if str(payload.get("error_code") or ""):
            fail(
                f"{relative}: capture contains error_code="
                f"{payload.get('error_code')!r}"
            )

        if payload.get("evidence_kind") != evidence_kind:
            fail(
                f"{relative}: unexpected evidence_kind "
                f"{payload.get('evidence_kind')!r}"
            )

        if browser_project is not None:
            if payload.get("browser_project") != browser_project:
                fail(
                    f"{relative}: browser project mismatch"
                )

    expected = {
        path.resolve()
        for path, _, _ in paths
    }

    for directory in (
        PARITY_ROOT / "backend",
        PARITY_ROOT / "termux",
        PARITY_ROOT / "browser",
    ):
        if not directory.is_dir():
            fail(
                f"required evidence directory is missing: "
                f"{directory.relative_to(ROOT)}"
            )

        unexpected = {
            path.resolve()
            for path in directory.glob("*.json")
        } - expected

        if unexpected:
            fail(
                "unexpected runtime evidence files are present: "
                + ", ".join(
                    str(path.relative_to(ROOT))
                    for path in sorted(unexpected)
                )
            )

    print(
        f"PASS fresh sanitized runtime inventory: "
        f"{len(domains)} domains, "
        f"{len(paths)} evidence files"
    )

    return observed_paths


def recompute_comparison() -> None:
    print(
        "FIX recomputing normalized runtime comparison "
        "from current evidence"
    )

    result = run(
        os.environ.get(
            "PYTHON",
            str(ROOT / ".venv" / "bin" / "python"),
        ),
        str(COMPARATOR),
        check=False,
        timeout=120,
    )

    # Comparator intentionally uses 2 for a truthful overall
    # partial result. Promotion decides whether that partial
    # state is acceptable.
    if result.returncode not in {0, 2}:
        fail(
            "runtime comparison failed:\n"
            + (result.stdout or "")
            + (result.stderr or "")
        )

    if not NORMALIZED.is_file():
        fail(
            "runtime comparator completed without writing "
            "runtime-comparison.json"
        )

    print(
        "PASS normalized runtime comparison rebuilt"
    )


def verify_comparison(
    tag: str,
    tag_commit: str,
    domains: list[str],
) -> None:
    payload = load_json(NORMALIZED)

    if payload.get("release_tag") != tag:
        fail(
            "normalized comparison release does not match "
            f"{tag}"
        )

    if payload.get("source_commit") != tag_commit:
        fail(
            "normalized comparison source commit does not "
            "match the release tag commit"
        )

    compared_domains = payload.get("domains")
    if not isinstance(compared_domains, list):
        fail("normalized comparison domains are invalid")

    by_id = {
        str(item.get("id") or ""): item
        for item in compared_domains
        if isinstance(item, dict)
    }

    if set(by_id) != set(domains):
        fail(
            "normalized comparison domain inventory does not "
            "match the parity model"
        )

    reported_findings: list[str] = []

    for domain_id in domains:
        item = by_id[domain_id]
        summary = item.get("comparison_summary") or {}

        if not isinstance(summary, dict):
            fail(
                f"{domain_id}: comparison_summary is invalid"
            )

        mismatch = int(summary.get("mismatch", 0) or 0)
        unsupported = int(summary.get("unsupported", 0) or 0)
        not_observed = int(summary.get("not_observed", 0) or 0)

        findings = []

        if mismatch:
            findings.append(f"mismatch={mismatch}")
        if unsupported:
            findings.append(f"unsupported={unsupported}")
        if not_observed:
            findings.append(
                f"not_observed={not_observed}"
            )

        if findings:
            reported_findings.append(
                f"{domain_id}: " + ", ".join(findings)
            )

    if reported_findings:
        print(
            "INFO runtime findings retained as truthful "
            "promotion evidence:"
        )
        for finding in reported_findings:
            print(f"  {finding}")

    print(
        f"PASS normalized comparison is release-bound; "
        f"overall={payload.get('status')}"
    )


def verify_head(tag: str) -> str:
    head = git("rev-parse", "HEAD")
    tag_commit = git("rev-list", "-n", "1", tag)

    if tag_commit != head:
        fail(
            f"release tag {tag} points to {tag_commit[:12]}, "
            f"but current HEAD is {head[:12]}. "
            "Promotion never changes branches or rewrites HEAD."
        )

    print(
        f"PASS release tag and HEAD agree: {head}"
    )
    return head


def preflight(tag: str) -> None:
    if not TAG_RE.fullmatch(tag):
        fail(
            "release tag must use lite-YYYY.MM.DD.N"
        )

    if git("rev-parse", "--is-inside-work-tree") != "true":
        fail("promotion must run inside a Git working tree")

    try:
        git("remote", "get-url", "origin")
    except Exception:
        fail("Git remote 'origin' is unavailable")

    github_release(tag)

    fetched = ensure_local_tag(tag)

    tag_commit = verify_head(tag)

    verify_release_manifest(
        tag,
        tag_commit,
    )

    domains = domain_ids()

    verify_evidence(
        tag,
        tag_commit,
        domains,
    )

    # Always recompute rather than trusting an old normalized
    # comparison. This is deterministic and only writes transient
    # .pocketlab-dev evidence.
    recompute_comparison()

    verify_comparison(
        tag,
        tag_commit,
        domains,
    )

    print(
        "PASS runtime promotion preflight"
        + (" (local tag repaired)" if fetched else "")
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed Pocket Lab Lite runtime promotion preflight"
        )
    )
    parser.add_argument(
        "--release-tag",
        default=os.environ.get(
            "LITE_PARITY_RELEASE_TAG",
            "",
        ),
    )
    args = parser.parse_args()

    try:
        preflight(args.release_tag)
    except PreflightError as exc:
        print(f"FAIL runtime promotion preflight: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
