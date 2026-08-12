import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

GENERATOR = (
    ROOT
    / "scripts"
    / "docs"
    / "lite"
    / "generate_contracts.py"
)

OPENAPI = (
    ROOT
    / "contracts"
    / "generated"
    / "lite-openapi.json"
)


def _generate(commit: str, generated_at: str) -> bytes:
    env = os.environ.copy()
    env["SOURCE_COMMIT"] = commit
    env["SOURCE_GENERATED_AT"] = generated_at

    subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "generate",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    return OPENAPI.read_bytes()


def test_openapi_contract_is_independent_of_build_provenance():
    first = _generate(
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "2026-08-12T08:00:00Z",
    )

    second = _generate(
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "2026-08-12T09:00:00Z",
    )

    assert first == second

    schema = json.loads(first)

    assert (
        "x-pocketlab-source-commit"
        not in schema.get("info", {})
    )
