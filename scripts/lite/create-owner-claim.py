#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "pocket-lab-final-structure" / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from api_fastapi.services.lite_webauthn import WebAuthnError, issue_owner_claim  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a short-lived Pocket Lab Lite first-owner passkey claim.")
    parser.add_argument("--origin", required=True, help="Exact Pocket Lab browser origin, e.g. https://server-name.tailnet.ts.net")
    parser.add_argument("--ttl", type=int, default=None, help="Claim TTL in seconds (60-1800).")
    args = parser.parse_args()
    try:
        claim = issue_owner_claim(origin=args.origin, ttl_seconds=args.ttl)
    except WebAuthnError as exc:
        print(f"ERROR {exc.reason_code}: {exc.message}", file=sys.stderr)
        return 2
    print("Pocket Lab Lite owner claim created.")
    print(f"Expires: {claim['expires_at']}")
    print("Open this link only on the intended Pocket Lab device/browser:")
    print(claim["claim_url"])
    print("The raw claim is shown once here and is not stored in Pocket Lab state or audit output.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
