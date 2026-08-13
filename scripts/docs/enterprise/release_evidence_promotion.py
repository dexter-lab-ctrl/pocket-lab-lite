#!/usr/bin/env python3
"""Explicit GitHub Release evidence capture, validation, and promotion.

This command is never invoked by MkDocs generators/checks. Capture may use the authenticated `gh`
CLI on a developer/CI host. Promotion is explicit, atomic, append-only per release tag, and stores
only sanitized release identity/artifact evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
TRANSIENT = ROOT / ".pocketlab-dev/release-evidence"
CANONICAL = ROOT / "contracts/generated/releases/promoted-release-evidence.json"
REQUIRED = ("dist.zip", "checksums.txt", "pocketlab-lite-release.json")
TAG_RE = re.compile(r"^lite-[A-Za-z0-9._-]+$")
SHA_RE = re.compile(r"^[a-f0-9]{64}$")
COMMIT_RE = re.compile(r"^[a-f0-9]{40}$")


def stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, separators=(",", ": ")) + "\n"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: str) -> str:
    return subprocess.check_output(list(args), cwd=ROOT, text=True, stderr=subprocess.STDOUT).strip()


def fail(message: str, code: int = 2) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)




def ensure_dev_host() -> None:
    prefix = os.environ.get("PREFIX", "")
    if os.environ.get("TERMUX_VERSION") or "com.termux" in prefix:
        fail("release evidence capture/promotion belongs on WSL2/Ubuntu/CI; Termux remains lightweight", 3)
    try:
        os_name = subprocess.check_output(["uname", "-o"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        os_name = ""
    if os_name == "Android":
        fail("release evidence capture/promotion belongs on WSL2/Ubuntu/CI; Termux remains lightweight", 3)


def parse_checksums(text: str) -> dict[str, str]:
    out = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([a-fA-F0-9]{64})\s+\*?(.+)", line.strip())
        if match:
            out[match.group(2).strip()] = match.group(1).lower()
    return out


def validate_capture(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    tag = str(payload.get("release_tag") or "")
    if not TAG_RE.fullmatch(tag): errors.append("invalid release_tag")
    if not COMMIT_RE.fullmatch(str(payload.get("source_commit") or "")): errors.append("invalid source_commit")
    if not COMMIT_RE.fullmatch(str(payload.get("tree_hash") or "")): errors.append("invalid tree_hash")
    assets = {x.get("name"): x for x in payload.get("artifacts", []) if isinstance(x, dict)}
    for name in REQUIRED:
        row = assets.get(name)
        if not row: errors.append(f"missing required artifact {name}"); continue
        if not SHA_RE.fullmatch(str(row.get("sha256") or "")): errors.append(f"invalid sha256 for {name}")
        if not isinstance(row.get("bytes"), int) or row["bytes"] <= 0: errors.append(f"invalid size for {name}")
    if payload.get("sanitized") is not True: errors.append("capture is not marked sanitized")
    if payload.get("verification_status") not in {"verified", "promoted"}: errors.append("verification_status is not verified/promoted")
    return errors


def capture(repo: str, tag: str) -> Path:
    ensure_dev_host()
    if not TAG_RE.fullmatch(tag): fail("TAG must match lite-* release naming")
    if not shutil.which("gh"): fail("GitHub CLI `gh` is required for explicit release evidence capture")
    try:
        run("gh", "auth", "status")
    except subprocess.CalledProcessError as exc:
        fail(f"gh authentication check failed: {exc.output[-400:]}")
    release_json = json.loads(run("gh", "api", f"repos/{repo}/releases/tags/{tag}"))
    if release_json.get("tag_name") != tag or release_json.get("draft") or release_json.get("prerelease"):
        fail("release must be the requested non-draft, non-prerelease tag")
    api_assets = {str(x.get("name")): x for x in release_json.get("assets", []) if isinstance(x, dict) and x.get("name")}
    missing_api = [name for name in REQUIRED if name not in api_assets]
    if missing_api:
        fail(f"GitHub Release is missing required assets: {', '.join(missing_api)}")
    commit = run("gh", "api", f"repos/{repo}/commits/{tag}", "--jq", ".sha")
    if not COMMIT_RE.fullmatch(commit): fail("GitHub tag did not resolve to a 40-hex commit")
    tree = run("gh", "api", f"repos/{repo}/git/commits/{commit}", "--jq", ".tree.sha")
    if not COMMIT_RE.fullmatch(tree): fail("GitHub commit did not resolve to a 40-hex tree")

    target = TRANSIENT / tag
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release-evidence-", dir=target) as temp_name:
        temp = Path(temp_name)
        for asset in REQUIRED:
            run("gh", "release", "download", tag, "--repo", repo, "--pattern", asset, "--dir", str(temp))
        missing = [x for x in REQUIRED if not (temp / x).is_file()]
        if missing: fail(f"release download missing required assets: {', '.join(missing)}")
        manifest = json.loads((temp / "pocketlab-lite-release.json").read_text(encoding="utf-8"))
        if manifest.get("release_tag") != tag: fail("release manifest tag does not match GitHub release")
        if manifest.get("source_commit") != commit: fail("release manifest source commit does not match GitHub tag commit")
        checksums = parse_checksums((temp / "checksums.txt").read_text(encoding="utf-8"))
        dist_sha = sha256(temp / "dist.zip")
        if checksums.get("dist.zip") != dist_sha: fail("checksums.txt does not verify dist.zip")
        manifest_digest = str(manifest.get("dist_zip_sha256") or manifest.get("artifact_sha256") or manifest.get("sha256") or "")
        if manifest_digest and manifest_digest != dist_sha: fail("release manifest dist.zip digest does not match downloaded artifact")
        artifacts = []
        verification = {
            "dist.zip": "SHA-256 verified against checksums.txt and GitHub asset digest where provided",
            "checksums.txt": "parsed and used to verify dist.zip; GitHub asset digest verified where provided",
            "pocketlab-lite-release.json": "JSON parsed and tag + source commit bound; GitHub asset digest verified where provided",
        }
        for name in REQUIRED:
            local_sha = sha256(temp / name)
            api_digest = str(api_assets[name].get("digest") or "")
            if api_digest:
                if api_digest != f"sha256:{local_sha}":
                    fail(f"GitHub asset digest does not match downloaded {name}")
                github_digest_status = "verified"
            else:
                github_digest_status = "unobserved"
            artifacts.append({
                "name": name, "sha256": local_sha, "bytes": (temp / name).stat().st_size, "status": "verified",
                "github_asset_presence": "verified", "github_digest_status": github_digest_status,
                "verification": verification[name],
            })
        published_at = release_json.get("published_at") or "unobserved"
        payload = {
            "schema_version": "1.0.0", "release_tag": tag, "source_commit": commit, "tree_hash": tree,
            "repository": repo, "published_at": published_at,
            "observed_at": published_at, "verification_status": "verified",
            "artifacts": artifacts, "manifest_binding": {"release_tag": tag, "source_commit": commit, "dist_zip_sha256": dist_sha, "status": "verified"},
            "sanitized": True, "source": "explicit-gh-release-capture", "raw_urls_included": False,
        }
        errors = validate_capture(payload)
        if errors: fail("; ".join(errors))
        out = target / "capture.json"
        tmp = out.with_suffix(".json.tmp"); tmp.write_text(stable(payload), encoding="utf-8"); tmp.replace(out)
        print(f"PASS captured sanitized release evidence: {out.relative_to(ROOT)}")
        return out


def promote(tag: str) -> None:
    ensure_dev_host()
    if os.environ.get("POCKETLAB_RELEASE_EVIDENCE_PROMOTE") != "1":
        fail("promotion requires POCKETLAB_RELEASE_EVIDENCE_PROMOTE=1", 3)
    capture_path = TRANSIENT / tag / "capture.json"
    if not capture_path.exists(): fail(f"capture not found for {tag}; run capture first")
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    errors = validate_capture(payload)
    if errors: fail("capture validation failed: " + "; ".join(errors))
    canonical = {"schema_version": "1.0.0", "releases": []}
    if CANONICAL.exists(): canonical = json.loads(CANONICAL.read_text(encoding="utf-8"))
    rows = canonical.get("releases", []) if isinstance(canonical.get("releases"), list) else []
    existing = next((x for x in rows if x.get("release_tag") == tag), None)
    promoted = {**payload, "verification_status": "promoted", "promotion_rule": "explicit-only; immutable per release tag"}
    if existing:
        comparable_existing = {k:v for k,v in existing.items() if k not in {"verification_status","promotion_rule"}}
        comparable_new = {k:v for k,v in promoted.items() if k not in {"verification_status","promotion_rule"}}
        if comparable_existing != comparable_new:
            fail(f"refusing to rewrite historical promoted evidence for {tag}", 4)
        print(f"PASS release evidence already promoted and unchanged: {tag}")
        return
    rows.append(promoted)
    rows.sort(key=lambda x: (str(x.get("published_at") or ""), str(x.get("release_tag") or "")))
    CANONICAL.parent.mkdir(parents=True, exist_ok=True)
    tmp = CANONICAL.with_suffix(".json.tmp"); tmp.write_text(stable({"schema_version":"1.0.0","releases":rows}), encoding="utf-8"); tmp.replace(CANONICAL)
    print(f"PASS promoted release evidence: {CANONICAL.relative_to(ROOT)}")


def check() -> None:
    if not CANONICAL.exists():
        print("PASS no promoted release evidence file exists; release authority remains unobserved")
        return
    doc = json.loads(CANONICAL.read_text(encoding="utf-8"))
    seen=set()
    for row in doc.get("releases", []):
        errors=validate_capture(row)
        if errors: fail(f"invalid promoted release {row.get('release_tag')}: {'; '.join(errors)}")
        tag=row["release_tag"]
        if tag in seen: fail(f"duplicate promoted release tag: {tag}")
        seen.add(tag)
    print(f"PASS promoted release evidence validated: {len(seen)} release(s)")


def main() -> int:
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest="command",required=True)
    c=sub.add_parser("capture"); c.add_argument("--repo",required=True); c.add_argument("--tag",required=True)
    p=sub.add_parser("promote"); p.add_argument("--tag",required=True)
    sub.add_parser("check")
    args=parser.parse_args()
    if args.command=="capture": capture(args.repo,args.tag)
    elif args.command=="promote": promote(args.tag)
    else: check()
    return 0

if __name__=="__main__": raise SystemExit(main())
