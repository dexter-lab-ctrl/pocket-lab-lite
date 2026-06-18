#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / ".pocketlab-dev/validation/command-results"
LOG_DIR = ROOT / ".pocketlab-dev/validation/logs"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an existing Pocket Lab validation command and record release evidence")
    parser.add_argument("gate_id", help="Validation gate id from scripts/docs/validation_evidence_lib.py")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to run after --")
    args = parser.parse_args()

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("ERROR: provide a command after --")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    started = now_iso()
    completed = None
    stdout_path = LOG_DIR / f"{args.gate_id}.stdout.log"
    stderr_path = LOG_DIR / f"{args.gate_id}.stderr.log"

    print(f"Recording validation gate `{args.gate_id}`: {' '.join(shlex.quote(part) for part in command)}")
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
        proc = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, text=True)
        completed = now_iso()

    result = {
        "schemaVersion": "pocketlab.validation.command-result.v1",
        "gate_id": args.gate_id,
        "command": command,
        "command_display": " ".join(shlex.quote(part) for part in command),
        "started_at": started,
        "finished_at": completed,
        "exit_code": proc.returncode,
        "stdout_log": rel(stdout_path),
        "stderr_log": rel(stderr_path),
    }
    result_path = OUT_DIR / f"{args.gate_id}.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {rel(result_path)}")
    if proc.returncode:
        print(f"Gate `{args.gate_id}` failed with exit code {proc.returncode}")
        print(f"Stdout: {rel(stdout_path)}")
        print(f"Stderr: {rel(stderr_path)}")
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
