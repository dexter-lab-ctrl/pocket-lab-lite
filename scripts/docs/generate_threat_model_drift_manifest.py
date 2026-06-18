#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from threat_model_drift_lib import MANIFEST, current_manifest_payload, rel, write_json


def main() -> None:
    subprocess.run(["python3", "scripts/docs/check_threat_model.py"], check=True)

    payload = current_manifest_payload()
    payload["metadata"]["sealedAt"] = datetime.now(timezone.utc).isoformat()
    write_json(MANIFEST, payload)

    print(f"Wrote {rel(MANIFEST)}")
    print(f"Source fingerprint: {payload['source_fingerprint']}")
    print(f"Generated output fingerprint: {payload['generated_output_fingerprint']}")


if __name__ == "__main__":
    main()
