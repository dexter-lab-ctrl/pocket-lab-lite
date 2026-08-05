#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

API_URL = os.environ.get("LITE_PARITY_API_URL", "http://127.0.0.1:18080").rstrip("/")
OUTPUT = Path(
    os.environ.get(
        "LITE_PARITY_TERMUX_EVIDENCE",
        ".pocketlab-dev/validation/parity/termux/recovery-readonly.json",
    )
)


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 200:
                raise RuntimeError(f"unexpected HTTP status {response.status}")
            payload = json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"unable to read sanitized Recovery summary: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Recovery summary was not a JSON object")
    return payload


def safe_text(value: object, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]


def main() -> int:
    payload = fetch_json(f"{API_URL}/api/lite/recovery/summary")
    latest = payload.get("latest_backup") or payload.get("last_backup") or {}
    if not isinstance(latest, dict):
        latest = {}

    evidence = {
        "recovery_summary": {
            "status": safe_text(payload.get("status")),
            "summary": safe_text(payload.get("summary")),
            "source_revision": payload.get("source_revision"),
            "updated_at": safe_text(payload.get("updated_at")),
            "read_degraded": payload.get("read_degraded") is True,
            "degraded_reason": safe_text(payload.get("degraded_reason")),
            "projection_age_ms": payload.get("projection_age_ms"),
            "data_source": safe_text(payload.get("data_source")),
            "refresh_pending": payload.get("refresh_pending") is True,
            "latest_backup": {
                "backup_id": safe_text(latest.get("backup_id")),
                "verification_status": safe_text(latest.get("verification_status")),
                "created_at": safe_text(latest.get("created_at")),
            },
        },
        "sanitized": True,
        "schema_version": "1.1.0",
        "status": "observed",
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=OUTPUT.parent,
        prefix=f".{OUTPUT.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(OUTPUT)
    print("PASS live Termux read-only parity observation recorded")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
