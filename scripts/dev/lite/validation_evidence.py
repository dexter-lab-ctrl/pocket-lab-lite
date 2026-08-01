#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
MAX_OUTPUT_CHARS = 200_000


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def source_commit() -> str:
    explicit = os.environ.get("SOURCE_COMMIT", "").strip()
    if explicit:
        return explicit
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or "uncommitted"
    except Exception:
        return "uncommitted"


def platform_evidence() -> dict[str, str]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "wsl": "true" if "microsoft" in platform.release().lower() else "false",
    }


def sanitize(text: str) -> str:
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text, flags=re.I)
    text = re.sub(r"nats://[^\s/@:]+:[^\s/@]+@", "nats://[REDACTED]@", text, flags=re.I)
    text = re.sub(
        r"(?i)(authorization|cookie|set-cookie|password|token|secret|credential|api[_-]?key|restic_password|tailscale_auth_key)\s*[:=]\s*[^\s,;]+",
        lambda match: f"{match.group(1)}=[REDACTED]",
        text,
    )
    text = re.sub(r"-----BEGIN [^-\n]*PRIVATE KEY-----.*?-----END [^-\n]*PRIVATE KEY-----", "[REDACTED PRIVATE KEY]", text, flags=re.I | re.S)
    return text[-MAX_OUTPUT_CHARS:]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_record(name: str, validation_dir: Path, command: list[str], artifact_paths: list[str]) -> int:
    validation_dir.mkdir(parents=True, exist_ok=True)
    commands_dir = validation_dir / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    started_monotonic = time.monotonic()
    result = subprocess.run(command, text=True, capture_output=True)
    ended_at = utc_now()
    duration = time.monotonic() - started_monotonic
    payload = {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "command": command,
        "source_commit": source_commit(),
        "platform": platform_evidence(),
        "started_at": started_at,
        "ended_at": ended_at,
        "exit_code": result.returncode,
        "result": "passed" if result.returncode == 0 else "failed",
        "status": "passed" if result.returncode == 0 else "failed",
        "duration_seconds": round(duration, 3),
        "artifact_paths": sorted(set(artifact_paths)),
        "stdout": sanitize(result.stdout),
        "stderr": sanitize(result.stderr),
    }
    write_json(commands_dir / f"{name}.json", payload)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def validation_items(validation_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for file in sorted((validation_dir / "commands").glob("*.json")):
        item = json.loads(file.read_text(encoding="utf-8"))
        item["record_path"] = file.as_posix()
        items.append(item)
    return items


def write_validation_indexes(validation_dir: Path, items: list[dict[str, Any]], allure_output: Path) -> None:
    passed = sum(item.get("status") == "passed" for item in items)
    failed = sum(item.get("status") != "passed" for item in items)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "source_commit": source_commit(),
        "platform": platform_evidence(),
        "commands": [
            {
                "name": item.get("name"),
                "command": item.get("command", []),
                "started_at": item.get("started_at"),
                "ended_at": item.get("ended_at"),
                "exit_code": item.get("exit_code"),
                "result": item.get("result", item.get("status")),
                "artifact_paths": item.get("artifact_paths", []),
                "record_path": item.get("record_path"),
            }
            for item in items
        ],
    }
    readiness = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": manifest["generated_at"],
        "source_commit": manifest["source_commit"],
        "status": "passed" if items and failed == 0 else ("failed" if failed else "not_run"),
        "passed": passed,
        "failed": failed,
        "total": len(items),
        "gates": {str(item.get("name")): item.get("result", item.get("status")) for item in items},
    }
    artifacts = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": manifest["generated_at"],
        "source_commit": manifest["source_commit"],
        "allure_results": allure_output.as_posix(),
        "records": [item.get("record_path") for item in items],
        "artifacts": sorted({path for item in items for path in item.get("artifact_paths", [])}),
    }
    write_json(validation_dir / "validation-manifest.json", manifest)
    write_json(validation_dir / "readiness-matrix.json", readiness)
    write_json(validation_dir / "test-artifact-index.json", artifacts)


def allure(validation_dir: Path, output: Path) -> int:
    output.mkdir(parents=True, exist_ok=True)
    for stale in output.glob("*-result.json"):
        stale.unlink()
    items = validation_items(validation_dir)
    for item in items:
        identifier = str(uuid.uuid5(uuid.NAMESPACE_URL, f"pocketlab-lite:{item['name']}"))
        started = item.get("started_at")
        ended = item.get("ended_at")
        try:
            start_ms = int(dt.datetime.fromisoformat(str(started).replace("Z", "+00:00")).timestamp() * 1000)
            stop_ms = int(dt.datetime.fromisoformat(str(ended).replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:
            stop_ms = int(time.time() * 1000)
            start_ms = stop_ms - int(float(item.get("duration_seconds", 0)) * 1000)
        status = "passed" if item.get("status") == "passed" else "failed"
        attachments = []
        for artifact in item.get("artifact_paths", []):
            attachments.append({"name": Path(artifact).name, "source": artifact, "type": "text/plain"})
        result = {
            "uuid": identifier,
            "historyId": hashlib.sha256(item["name"].encode()).hexdigest(),
            "testCaseId": item["name"],
            "name": item["name"],
            "fullName": f"Pocket Lab Lite validation::{item['name']}",
            "status": status,
            "statusDetails": {"message": item.get("stderr", "")[:4000]},
            "stage": "finished",
            "start": start_ms,
            "stop": stop_ms,
            "labels": [
                {"name": "suite", "value": "Pocket Lab Lite"},
                {"name": "feature", "value": "Development documentation platform"},
                {"name": "audience", "value": "development"},
                {"name": "sourceCommit", "value": str(item.get("source_commit", "uncommitted"))},
                {"name": "platform", "value": str(item.get("platform", {}).get("system", "unknown"))},
            ],
            "parameters": [{"name": "command", "value": " ".join(item.get("command", []))}],
            "attachments": attachments,
        }
        write_json(output / f"{identifier}-result.json", result)
    write_validation_indexes(validation_dir, items, output)
    print(f"Generated {len(items)} Allure-compatible result files and validation indexes in {output}")
    return 0


def html_report(validation_dir: Path, output: Path) -> int:
    """Generate a dependency-free bounded HTML index over Allure-compatible records.

    This is intentionally not presented as the upstream Allure UI. When an
    independently provisioned pinned Allure CLI is present, operators can run
    `allure generate allure-results --clean -o allure-report` instead.
    """
    items = validation_items(validation_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for item in items:
        name = str(item.get("name", "unnamed"))
        status = str(item.get("status", "unknown"))
        command = " ".join(str(part) for part in item.get("command", []))
        rows.append(f"<tr><td>{name}</td><td>{status}</td><td><code>{command}</code></td><td>{item.get('duration_seconds', '')}</td></tr>")
    html = """<!doctype html><meta charset=\"utf-8\"><title>Pocket Lab Lite validation evidence</title>
<style>body{font:16px system-ui;max-width:1200px;margin:auto;padding:2rem}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:.5rem;text-align:left}code{white-space:pre-wrap}</style>
<h1>Pocket Lab Lite validation evidence</h1>
<p>This bounded report is generated from Allure-compatible JSON records. It is not the upstream Allure UI.</p>
<table><thead><tr><th>Gate</th><th>Result</th><th>Command</th><th>Seconds</th></tr></thead><tbody>""" + "".join(rows) + "</tbody></table>\n"
    (output / "index.html").write_text(html, encoding="utf-8")
    print(f"Generated bounded validation HTML index at {output / 'index.html'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--name", required=True)
    run_parser.add_argument("--validation-dir", default=".pocketlab-dev/validation")
    run_parser.add_argument("--artifact", action="append", default=[])
    run_parser.add_argument("remainder", nargs=argparse.REMAINDER)
    allure_parser = sub.add_parser("allure")
    allure_parser.add_argument("--validation-dir", default=".pocketlab-dev/validation")
    allure_parser.add_argument("--output", default="allure-results")
    html_parser = sub.add_parser("html")
    html_parser.add_argument("--validation-dir", default=".pocketlab-dev/validation")
    html_parser.add_argument("--output", default="allure-report")
    args = parser.parse_args()
    if args.command == "run":
        command = args.remainder
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise SystemExit("No command supplied after --")
        return run_record(args.name, Path(args.validation_dir), command, list(args.artifact))
    if args.command == "html":
        return html_report(Path(args.validation_dir), Path(args.output))
    return allure(Path(args.validation_dir), Path(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
