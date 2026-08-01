#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

FORBIDDEN_PREFIXES = ("node_modules/", ".venv/", "docs/", "site/", "storybook-static/", "allure-results/", ".pocketlab-dev/")
FORBIDDEN_SUFFIXES = (".key", ".pem", ".sqlite", ".db", ".har", ".patch")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root)
    archive = root / "dist.zip"
    checksums = root / "checksums.txt"
    if not archive.exists() or not checksums.exists():
        print("dist.zip or checksums.txt is missing. Run task lite:release:dry-run first.")
        return 2
    expected = checksums.read_text().split()[0]
    actual = digest(archive)
    if expected != actual:
        print(f"Checksum mismatch: expected {expected}, got {actual}")
        return 1
    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        required = {"index.html", "manifest.webmanifest", "sw.js"}
        missing = [name for name in required if name not in names]
        forbidden = [name for name in names if name.startswith(FORBIDDEN_PREFIXES) or name.endswith(FORBIDDEN_SUFFIXES)]
    if missing or forbidden:
        print(json.dumps({"missing": missing, "forbidden": forbidden}, indent=2))
        return 1
    manifest = root / "pocketlab-lite-release.json"
    if manifest.exists():
        data = json.loads(manifest.read_text())
        if data.get("product") != "pocket-lab-lite" or data.get("artifact_sha256") != actual:
            print("Release manifest product or artifact digest is invalid")
            return 1
    print(json.dumps({"status": "passed", "artifact": str(archive), "sha256": actual, "entries": len(names)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
