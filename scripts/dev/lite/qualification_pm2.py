#!/usr/bin/env python3
"""Run-owned PM2 compatibility shim for the real Lite agent supervisor.

The production supervisor intentionally speaks PM2 because that is the
supported Termux lifecycle.  A disposable Dev PC run must not share the
production PM2 socket or namespace, so this executable implements only the
small command surface the supervisor needs and stores records below its
run-owned ``PM2_HOME``.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _home() -> Path:
    raw = os.environ.get("PM2_HOME", "").strip()
    if not raw:
        raise RuntimeError("qualification PM2_HOME is required")
    path = Path(raw).expanduser()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path


def _state_path() -> Path:
    return _home() / "qualification-processes.json"


def _read() -> list[dict[str, object]]:
    try:
        value = json.loads(_state_path().read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except (FileNotFoundError, OSError, ValueError):
        return []


def _write(records: list[dict[str, object]]) -> None:
    path = _state_path()
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(records, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _write_error(error_type: str, detail: str = "") -> None:
    path = _home() / "qualification-last-error.json"
    detail_text = str(detail or "")
    reason = {
        "qualification PM2_HOME is required": "pm2_home_missing",
        "qualification PM2 name is required": "pm2_name_missing",
        "qualification PM2 name is incomplete": "pm2_name_incomplete",
        "qualification PM2 process name is not run-owned": "process_name_not_run_owned",
        "qualification PM2 command is incomplete": "pm2_command_incomplete",
        "unsupported_command": "unsupported_command",
        "missing_command": "missing_command",
        "process_not_found": "process_not_found",
    }.get(detail_text, "shim_exception")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps({"error_type": str(error_type)[:80], "reason_code": reason, "sanitized": True}) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _start_record(record: dict[str, object]) -> dict[str, object]:
    argv = [str(item) for item in record.get("argv", [])]
    if not argv:
        raise RuntimeError("qualification PM2 record has no command")
    log_dir = Path(os.environ.get("POCKETLAB_QUALIFICATION_LOG_DIR", str(_home() / "logs")))
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    log_path = log_dir / f"{str(record.get('name') or 'agent')}.log"
    log = open(log_path, "ab", buffering=0)
    child_env = dict(os.environ)
    child_env["POCKETLAB_SERVICE_VERSION"] = str(record.get("version") or "")
    child_env["POCKETLAB_QUALIFICATION_PM2_SHIM"] = "1"
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        env=child_env,
        close_fds=True,
        start_new_session=True,
    )
    log.close()
    record = dict(record)
    record["pid"] = process.pid
    record["started_at_epoch"] = time.time()
    record["log_class"] = "run_owned"
    return record


def _alive(record: dict[str, object]) -> bool:
    try:
        pid = int(record.get("pid") or 0)
        os.kill(pid, 0)
        return pid > 0
    except (OSError, TypeError, ValueError):
        return False


def _terminate(record: dict[str, object]) -> None:
    try:
        pid = int(record.get("pid") or 0)
        if pid > 0 and _alive(record):
            os.killpg(pid, signal.SIGTERM)
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline and _alive(record):
                time.sleep(0.05)
            if _alive(record):
                os.killpg(pid, signal.SIGKILL)
    except (OSError, TypeError, ValueError):
        pass


def _jlist() -> int:
    records = _read()
    changed = False
    output = []
    for record in records:
        alive = _alive(record)
        if str(record.get("status") or "") != ("online" if alive else "stopped"):
            record["status"] = "online" if alive else "stopped"
            changed = True
        output.append({
            "name": record.get("name"),
            "pid": record.get("pid") if alive else 0,
            "pm2_env": {
                "status": record.get("status"),
                "version": record.get("version") or "",
                "restart_time": record.get("restart_time", 0),
                "pm_cwd": record.get("cwd") or "",
            },
        })
    if changed:
        _write(records)
    print(json.dumps(output, separators=(",", ":")))
    return 0


def _name_from(args: list[str]) -> str:
    if "--name" not in args:
        raise RuntimeError("qualification PM2 name is required")
    index = args.index("--name")
    if index + 1 >= len(args):
        raise RuntimeError("qualification PM2 name is incomplete")
    return args[index + 1]


def main(argv: list[str] | None = None) -> int:
    args = list(argv or sys.argv[1:])
    if not args:
        _write_error("CommandError", "missing_command")
        return 1
    command = args[0]
    if command == "jlist":
        return _jlist()
    if command == "save":
        _write(_read())
        return 0
    if command == "start":
        name = _name_from(args)
        if name != os.environ.get("POCKETLAB_EXPECTED_AGENT_PROCESS", name):
            raise RuntimeError("qualification PM2 process name is not run-owned")
        if "--" not in args:
            raise RuntimeError("qualification PM2 command is incomplete")
        command_argv = args[args.index("--") + 1 :]
        records = [record for record in _read() if str(record.get("name") or "") != name]
        record = {
            "name": name,
            "argv": command_argv,
            "cwd": os.getcwd(),
            "version": os.environ.get("POCKETLAB_SERVICE_VERSION", ""),
            "run_id": os.environ.get("POCKETLAB_QUALIFICATION_RUN_ID", ""),
            "node_id": os.environ.get("POCKETLAB_NODE_ID", ""),
            "restart_time": 0,
            "status": "stopped",
        }
        records.append(_start_record(record))
        _write(records)
        return 0
    if command in {"restart", "delete"}:
        if len(args) < 2:
            raise RuntimeError("qualification PM2 process name is required")
        name = args[1]
        records = _read()
        found = next((record for record in records if str(record.get("name") or "") == name), None)
        if found is None:
            _write_error("CommandError", "process_not_found")
            return 1
        if command == "delete":
            _terminate(found)
            _write([record for record in records if record is not found])
            return 0
        _terminate(found)
        found["restart_time"] = int(found.get("restart_time") or 0) + 1
        found["status"] = "stopped"
        replacement = _start_record(found)
        _write([replacement if record is found else record for record in records])
        return 0
    _write_error("CommandError", "unsupported_command")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError) as exc:
        try:
            _write_error(type(exc).__name__, str(exc))
        except Exception:
            pass
        print(type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
