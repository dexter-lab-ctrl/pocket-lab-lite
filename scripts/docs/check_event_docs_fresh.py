#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]

WATCHED = [
    "contracts/asyncapi/pocketlab-nats-jetstream.yaml",
    "docs/runtime/nats-jetstream-event-contract.md",
    "docs/runtime/generated/nats-jetstream-asyncapi",
]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def git_diff(paths: list[str]) -> str:
    result = subprocess.run(
        ["git", "diff", "--", *paths],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout


def main() -> None:
    run(["python3", "scripts/docs/generate_event_docs.py"])

    diff = git_diff(WATCHED)
    if diff.strip():
        print("Generated event docs are not fresh.")
        print("Run: task docs:events")
        print(diff[:4000])
        raise SystemExit(1)

    print("Generated event docs are fresh.")


if __name__ == "__main__":
    main()
