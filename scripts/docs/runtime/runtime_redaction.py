#!/usr/bin/env python3
"""Fail-closed redaction and secret detection for Termux runtime documentation."""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
from pathlib import Path
from typing import Any, Iterable

from runtime_common import ROOT

ALLOWLISTED_KEYS = {
    "host_role", "ipv4_ready", "private_connectivity_ready", "address_redacted", "hostname_redacted",
    "network_identity_removed", "secrets_removed", "raw_paths_removed", "forbidden_fields_found",
    "certificate_material_removed", "private_key_material_removed", "media_paths_removed",
}
FORBIDDEN_KEY = re.compile(
    r"(?:^|_)(?:user(?:name)?|host(?:name)?|serial|ip(?:v4|v6)?|address|fqdn|tailnet|"
    r"password|passwd|token|secret|credential|cookie|authorization|private_key|certificate_path|"
    r"key_path|home_path|media_path|storage_path|command_line|environment|env)(?:_|$)",
    re.I,
)
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private-key", re.compile(r"-----BEGIN [^-]+PRIVATE KEY-----", re.I)),
    ("pem-material", re.compile(r"-----BEGIN (?:CERTIFICATE|OPENSSH PRIVATE KEY)-----", re.I)),
    ("bearer-token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I)),
    ("tailscale-key", re.compile(r"\btskey-[A-Za-z0-9_-]+", re.I)),
    ("nats-credential", re.compile(r"nats://[^\s/@:]+:[^\s/@]+@", re.I)),
    ("credential-url", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:]+:[^\s/@]+@", re.I)),
    ("secret-assignment", re.compile(r"\b(?:password|passwd|[a-z0-9_-]*token|secret|api[_-]?key|authkey)\s*[:=]\s*[^\s,;}]{4,}", re.I)),
    ("cookie", re.compile(r"\b(?:Set-)?Cookie\s*[:=]\s*[^\s]+", re.I)),
    ("tailnet-fqdn", re.compile(r"\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net\b", re.I)),
    ("termux-path", re.compile(r"/data/data/com\.termux/files/(?:home|usr)(?:/[^\s\"']*)?", re.I)),
    ("android-storage-path", re.compile(r"/(?:storage/emulated/\d+|sdcard|mnt/sdcard)(?:/[^\s\"']*)?", re.I)),
    ("unix-home-path", re.compile(r"/home/[A-Za-z0-9._-]+(?:/[^\s\"']*)?")),
    ("windows-home-path", re.compile(r"[A-Za-z]:\\Users\\[^\s\\]+(?:\\[^\s\"']*)?", re.I)),
    ("certificate-path", re.compile(r"[^\s\"']+\.(?:crt|pem|key)\b", re.I)),
    ("android-serial", re.compile(r"\b(?:R[0-9A-Z]{10,}|[0-9A-F]{16})\b")),
)


class RuntimeSafetyError(ValueError):
    """Raised without echoing the sensitive value."""


def _string_categories(value: str) -> set[str]:
    found = {label for label, pattern in PATTERNS if pattern.search(value)}
    for token in re.findall(r"(?<![A-Za-z0-9:])(?:\d{1,3}\.){3}\d{1,3}(?![A-Za-z0-9])", value):
        try:
            ipaddress.ip_address(token)
        except ValueError:
            continue
        found.add("ipv4-address")
    for token in re.findall(r"(?<![A-Za-z0-9])(?:[0-9A-Fa-f]{0,4}:){2,}[0-9A-Fa-f:]{0,4}(?![A-Za-z0-9])", value):
        try:
            ipaddress.ip_address(token)
        except ValueError:
            continue
        found.add("ipv6-address")
    return found


def forbidden_categories(value: Any, *, path: tuple[str, ...] = ()) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text not in ALLOWLISTED_KEYS and FORBIDDEN_KEY.search(key_text):
                found.add(f"forbidden-field:{key_text}")
            found.update(forbidden_categories(item, path=(*path, key_text)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.update(forbidden_categories(item, path=(*path, str(index))))
    elif isinstance(value, str):
        found.update(_string_categories(value))
    return found


def assert_safe(value: Any, *, context: str = "runtime artifact") -> None:
    categories = sorted(forbidden_categories(value))
    if categories:
        safe_categories = ", ".join(category.split(":", 1)[0] for category in categories[:10])
        raise RuntimeSafetyError(f"{context} contains forbidden sensitive categories: {safe_categories}")


def scan_paths(paths: Iterable[Path]) -> list[str]:
    failures: list[str] = []
    for path in paths:
        candidates = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
        for candidate in candidates:
            if candidate.stat().st_size > 10_000_000:
                failures.append(f"{candidate.relative_to(ROOT) if candidate.is_relative_to(ROOT) else candidate}: oversized")
                continue
            if candidate.suffix.lower() not in {".json", ".md", ".txt", ".yml", ".yaml"}:
                continue
            text = candidate.read_text(encoding="utf-8", errors="ignore")
            categories = sorted(_string_categories(text))
            if categories:
                label = candidate.relative_to(ROOT).as_posix() if candidate.is_relative_to(ROOT) else candidate.as_posix()
                failures.append(f"{label}: {', '.join(categories)}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", nargs="+", type=Path, required=True)
    args = parser.parse_args()
    failures = scan_paths(args.paths)
    if failures:
        print("Forbidden sensitive material detected:")
        for failure in failures:
            print(f" - {failure}")
        return 1
    print("PASS Termux runtime artifacts contain no forbidden sensitive material")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
