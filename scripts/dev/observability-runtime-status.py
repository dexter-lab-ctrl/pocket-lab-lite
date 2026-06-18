#!/usr/bin/env python3
"""Capture a local Tier 13 runtime observability status snapshot from FastAPI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".pocketlab-dev/observability/status.json"
DEFAULT_API_URL = "http://127.0.0.1:8000"


def main() -> int:
    api_url = os.environ.get("POCKETLAB_API_URL") or os.environ.get("API_URL") or DEFAULT_API_URL
    endpoint = api_url.rstrip("/") + "/api/observability/status"
    headers = {"Accept": "application/json"}
    token = os.environ.get("POCKETLAB_API_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Pocket-Lab-Token"] = token
    request = Request(endpoint, headers=headers)
    try:
        with urlopen(request, timeout=10) as response:  # nosec B310 - local operator-requested snapshot.
            body = response.read(512_000).decode("utf-8", errors="replace")
    except HTTPError as exc:
        print(f"Tier 13 runtime status request failed: HTTP {exc.code}", file=sys.stderr)
        return 1
    except (TimeoutError, URLError, OSError) as exc:
        print(f"Tier 13 runtime status request failed: {exc}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(body or "{}")
    except json.JSONDecodeError as exc:
        print(f"Tier 13 runtime status returned invalid JSON: {exc}", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"Tier 13 runtime observability status: {payload.get('status', 'unknown')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
