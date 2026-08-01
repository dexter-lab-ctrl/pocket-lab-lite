#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

PATTERNS = {
    "authorization": re.compile(r"Authorization\s*[:=]\s*(?!\[REDACTED\])\S+", re.I),
    "bearer": re.compile(r"Bearer\s+(?!\[REDACTED\])[A-Za-z0-9._~+/=-]{8,}", re.I),
    "private-key": re.compile(r"-----BEGIN [^-]+PRIVATE KEY-----", re.I),
    "nats-userinfo": re.compile(r"nats://[^\s/@:]+:[^\s/@]+@", re.I),
    "restic-password": re.compile(r"RESTIC_PASSWORD\s*[:=]\s*(?!\[REDACTED\])\S+", re.I),
    "tailscale-key": re.compile(r"tskey-[A-Za-z0-9_-]+", re.I),
    "cookie": re.compile(r"(?:Set-)?Cookie\s*[:=]\s*(?!\[REDACTED\])\S+", re.I),
}
TEXT_SUFFIXES = {".md", ".json", ".txt", ".xml", ".html", ".har", ".js", ".jsx", ".ts", ".tsx", ".yml", ".yaml"}


def files_for(path: Path):
    if not path.exists():
        return
    if path.is_file():
        yield path
        return
    for item in path.rglob("*"):
        if item.is_file() and item.suffix.lower() in TEXT_SUFFIXES and item.stat().st_size <= 10_000_000:
            yield item


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", nargs="+", required=True)
    args = parser.parse_args()
    failures = []
    for raw in args.paths:
        for file in files_for(Path(raw)):
            text = file.read_text(encoding="utf-8", errors="ignore")
            for label, pattern in PATTERNS.items():
                if pattern.search(text):
                    failures.append(f"{file}: {label}")
    if failures:
        print("Forbidden secret-like material detected:")
        for failure in failures:
            print(" -", failure)
        return 1
    print("PASS generated Lite documentation/test evidence contains no forbidden secret patterns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
