#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "pocket-lab-final-structure" / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from api_fastapi.db.health import database_health  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect the Pocket Lab Lite SQLite database without exposing secrets."
    )
    parser.add_argument(
        "--initialize",
        action="store_true",
        help="Apply pending migrations before checking health.",
    )
    args = parser.parse_args()
    health = database_health(initialize=args.initialize)
    print(json.dumps(health, indent=2))
    healthy = (
        health.get("reachable")
        and health.get("schema_current")
        and health.get("quick_check") == "ok"
        and health.get("journal_mode") == "wal"
        and health.get("foreign_keys") is True
    )
    return 0 if healthy else 2


if __name__ == "__main__":
    raise SystemExit(main())
