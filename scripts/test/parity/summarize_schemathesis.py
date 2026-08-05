#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

URL = re.compile(r"https?://(?:127\.0\.0\.1|localhost):\d+")
SENSITIVE = re.compile(r"(?i)(token|password|secret|authorization|api[_-]?key)=([^&\s]+)")


def category(text: str) -> str:
    value = text.lower()
    if "server error" in value or "[500]" in value or "[502]" in value or "[504]" in value:
        return "server_error"
    if "network error" in value or "read timed out" in value or "connection failed" in value:
        return "network_error"
    if "undocumented http status code" in value:
        return "undocumented_status"
    if "undocumented content-type" in value:
        return "undocumented_content_type"
    if "accepted schema-violating request" in value and ("unexpected" in value or "additionalproperties" in value):
        return "accepted_extra_query_policy"
    if "response does not conform" in value or "schema validation" in value:
        return "response_schema"
    return "other"


def sanitize(text: str) -> str:
    text = URL.sub("http://loopback", text)
    return SENSITIVE.sub(lambda match: f"{match.group(1)}=[Filtered]", text)[:4000]


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", choices=("focused", "discovery"), required=True)
    parser.add_argument("--exit-status", type=int, required=True)
    args = parser.parse_args()

    findings: list[dict[str, str]] = []
    report_error = ""
    if args.junit.exists() and args.junit.stat().st_size:
        try:
            root = ET.parse(args.junit).getroot()
        except ET.ParseError as exc:
            report_error = sanitize(f"Malformed or truncated JUnit report: {exc}")
        else:
            for case in root.iter("testcase"):
                text = "\n".join((item.text or "") for item in list(case.findall("failure")) + list(case.findall("error")))
                if not text:
                    continue
                findings.append({
                    "operation": str(case.attrib.get("name") or "unknown")[:240],
                    "category": category(text),
                    "summary": sanitize(text),
                })
    counts = Counter(item["category"] for item in findings)
    payload = {
        "profile": args.profile,
        "tool_exit_status": args.exit_status,
        "finding_count": len(findings),
        "categories": dict(sorted(counts.items())),
        "findings": findings[:200],
        "gating": args.profile == "focused",
        "report_error": report_error,
        "sanitized": True,
    }
    atomic_write(args.output, payload)
    print(f"PASS Schemathesis {args.profile} summary: {len(findings)} findings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
