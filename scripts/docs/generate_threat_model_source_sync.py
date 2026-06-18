#!/usr/bin/env python3
from __future__ import annotations

import subprocess

from threat_model_source_sync_lib import SYNC_MANIFEST, build_sync_manifest, rel, write_json


def main() -> None:
    subprocess.run(["python3", "scripts/docs/generate_threat_model_docs.py"], check=True)

    manifest = build_sync_manifest()
    write_json(SYNC_MANIFEST, manifest)

    summary = manifest["finding_summary"]
    print(f"Wrote {rel(SYNC_MANIFEST)}")
    print(
        "Source sync findings: "
        f"errors={summary['error']} warnings={summary['warning']} info={summary['info']}"
    )


if __name__ == "__main__":
    main()
