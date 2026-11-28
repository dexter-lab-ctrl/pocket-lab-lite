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
import re
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
        "pm2 log permission denied": "pm2_log_permission_denied",
        "pm2 child spawn permission denied": "pm2_child_spawn_permission_denied",
    }.get(detail_text, "shim_exception")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps({"error_type": str(error_type)[:80], "reason_code": reason, "sanitized": True}) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)


def _allowed_names() -> set[str]:
    """Return the explicitly run-owned PM2 names for this qualification lane.

    The original isolated runtime lane launches one agent and binds the name
    through ``POCKETLAB_EXPECTED_AGENT_PROCESS``.  The integrated lifecycle
    lane also uses the repository's real startup/reconciliation owners, so it
    supplies a finite service allowlist.  No unbounded name-based PM2 control
    is accepted by this shim.
    """
    configured = {
        value.strip()
        for value in os.environ.get("POCKETLAB_QUALIFICATION_PM2_ALLOW_SERVICES", "").split(",")
        if value.strip()
    }
    expected = os.environ.get("POCKETLAB_EXPECTED_AGENT_PROCESS", "").strip()
    if configured:
        if expected:
            configured.add(expected)
        return configured
    return {expected} if expected else set()


def _validate_name(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", name):
        raise RuntimeError("qualification PM2 process name is not run-owned")
    if name not in _allowed_names():
        raise RuntimeError("qualification PM2 process name is not run-owned")


def _ecosystem_record(path: Path, name: str) -> dict[str, object]:
    """Read the single app emitted by pocketlab_runtime_registry.py.

    This intentionally accepts only the repository's JSON-in-CJS shape; it
    never evaluates arbitrary JavaScript from a qualification workspace.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as exc:
        raise RuntimeError("qualification PM2 command is incomplete") from exc
    marker = "const app = "
    start = text.find(marker)
    end_marker = ";\napp.env = process.env;"
    end = text.find(end_marker, start + len(marker))
    if start < 0 or end < 0:
        raise RuntimeError("qualification PM2 command is incomplete")
    try:
        payload = json.loads(text[start + len(marker) : end])
    except (TypeError, ValueError) as exc:
        raise RuntimeError("qualification PM2 command is incomplete") from exc
    if not isinstance(payload, dict) or str(payload.get("name") or "") != name:
        raise RuntimeError("qualification PM2 command is incomplete")
    script = str(payload.get("script") or "")
    if not script:
        raise RuntimeError("qualification PM2 command is incomplete")
    arguments = payload.get("args", [])
    if not isinstance(arguments, list) or not all(isinstance(value, str) for value in arguments):
        raise RuntimeError("qualification PM2 command is incomplete")
    interpreter = str(payload.get("interpreter") or "")
    if interpreter.casefold() in {"none", "fork", "null"}:
        interpreter = ""
    return {
        "script": script,
        "interpreter": interpreter,
        "cwd": str(payload.get("cwd") or os.getcwd()),
        "args": list(arguments),
        "version": os.environ.get("POCKETLAB_SERVICE_VERSION", ""),
        "autorestart": bool(payload.get("autorestart", True)),
        "kill_timeout": payload.get("kill_timeout"),
        "max_restarts": payload.get("max_restarts"),
        "min_uptime": payload.get("min_uptime"),
        "max_memory_restart": payload.get("max_memory_restart"),
        "restart_delay": payload.get("restart_delay"),
        "exp_backoff_restart_delay": payload.get("exp_backoff_restart_delay"),
    }


def _start_record(record: dict[str, object]) -> dict[str, object]:
    argv = [str(item) for item in record.get("argv", [])]
    if not argv:
        raise RuntimeError("qualification PM2 record has no command")
    log_dir = Path(os.environ.get("POCKETLAB_QUALIFICATION_LOG_DIR", str(_home() / "logs")))
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    log_path = log_dir / f"{str(record.get('name') or 'agent')}.log"
    try:
        log = open(log_path, "ab", buffering=0)
    except PermissionError as exc:
        raise RuntimeError("pm2 log permission denied") from exc
    child_env = dict(os.environ)
    child_env["POCKETLAB_SERVICE_VERSION"] = str(record.get("version") or "")
    child_env["POCKETLAB_QUALIFICATION_PM2_SHIM"] = "1"
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=child_env,
            cwd=str(record.get("cwd") or os.getcwd()),
            close_fds=True,
            start_new_session=True,
        )
    except PermissionError as exc:
        log.close()
        raise RuntimeError("pm2 child spawn permission denied") from exc
    log.close()
    record = dict(record)
    record["pid"] = process.pid
    record["started_at_epoch"] = time.time()
    record["log_class"] = "run_owned"
    return record


def _alive(record: dict[str, object]) -> bool:
    try:
        pid = int(record.get("pid") or 0)
        if pid <= 0:
            return False
        # ``kill(pid, 0)`` also succeeds for a zombie.  Treating a defunct
        # candidate as online would suppress supervisor recovery and could
        # leave a stale run-owned process record behind during cleanup.
        try:
            stat = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
            state = stat.rsplit(")", 1)[1].strip().split(" ", 1)[0]
            if state == "Z":
                return False
        except (FileNotFoundError, OSError, UnicodeError, IndexError):
            pass
        os.kill(pid, 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _memory_bytes(pid: int) -> int | None:
    """Return bounded resident memory for the run-owned child process."""
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        statm = Path(f"/proc/{pid}/statm").read_text(encoding="ascii").split()
        if len(statm) < 2:
            return None
        pages = int(statm[1])
        if page_size <= 0 or pages < 0:
            return None
        return pages * page_size
    except (AttributeError, FileNotFoundError, OSError, ValueError, IndexError):
        return None


def _duration_ms(value: object) -> int | None:
    """Parse the bounded PM2 duration forms emitted by the registry."""
    if value in (None, ""):
        return None
    text = str(value).strip().lower()
    match = re.fullmatch(r"(\d+)(ms|s|m)?", text)
    if not match:
        return None
    amount = int(match.group(1))
    unit = match.group(2) or "ms"
    multiplier = {"ms": 1, "s": 1000, "m": 60_000}[unit]
    return amount * multiplier


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
        pid = int(record.get("pid") or 0) if alive else 0
        environment = {
            "status": record.get("status"),
            "version": record.get("version") or "",
            "POCKETLAB_SERVICE_VERSION": record.get("version") or "",
            "POCKETLAB_PROCESS_SPEC_HASH": record.get("process_spec_hash") or "",
            "POCKETLAB_PM2_POLICY_FINGERPRINT": record.get("policy_fingerprint") or "",
            "qualification_run_id": record.get("run_id") or "",
            "restart_time": record.get("restart_time", 0),
            "pm_cwd": record.get("cwd") or "",
            "pm_exec_path": record.get("script") or "",
            "exec_interpreter": record.get("interpreter") or "",
            "pm_uptime": int(float(record.get("started_at_epoch") or 0) * 1000),
            "pid": pid,
            "autorestart": bool(record.get("autorestart", True)),
            "kill_timeout": record.get("kill_timeout"),
            "max_restarts": record.get("max_restarts"),
            "min_uptime": _duration_ms(record.get("min_uptime")),
            "max_memory_restart": record.get("max_memory_restart"),
            "restart_delay": record.get("restart_delay"),
            "exp_backoff_restart_delay": record.get("exp_backoff_restart_delay"),
        }
        memory = _memory_bytes(pid) if pid else None
        item = {
            "name": record.get("name"),
            "pid": pid,
            "pm2_env": environment,
        }
        # PM2's jlist contract projects monitoring counters beside pm2_env.
        # Keep the shape identical so runtime memory policy checks exercise
        # the same observation path as the native daemon.
        if memory is not None:
            item["monit"] = {"memory": memory}
        output.append(item)
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
        name = _name_from(args) if "--name" in args else ""
        process_options: dict[str, object] = {}
        if "--only" in args:
            only_index = args.index("--only")
            if only_index + 1 >= len(args):
                raise RuntimeError("qualification PM2 name is incomplete")
            name = args[only_index + 1]
        if not name:
            raise RuntimeError("qualification PM2 name is required")
        _validate_name(name)
        if "--only" in args:
            ecosystem_index = 1
            if ecosystem_index >= len(args):
                raise RuntimeError("qualification PM2 command is incomplete")
            ecosystem = _ecosystem_record(Path(args[ecosystem_index]).expanduser(), name)
            process_options = ecosystem
            script = str(ecosystem["script"])
            interpreter = str(ecosystem.get("interpreter") or "")
            command_argv = ([interpreter] if interpreter else []) + [script, *[str(value) for value in ecosystem["args"]]]
            cwd = str(ecosystem.get("cwd") or os.getcwd())
            version = str(ecosystem.get("version") or os.environ.get("POCKETLAB_SERVICE_VERSION", ""))
        else:
            if "--" not in args:
                raise RuntimeError("qualification PM2 command is incomplete")
            interpreter = args[1] if len(args) > 1 else ""
            if not interpreter:
                raise RuntimeError("qualification PM2 interpreter is missing")
            # PM2's supported form is ``pm2 start <python> ... -- <script>``.
            # Preserve both pieces so the candidate agent is launched by Python,
            # never as an executable source file.
            command_argv = [interpreter, *args[args.index("--") + 1 :]]
            script = command_argv[-1] if command_argv else ""
            cwd = os.getcwd()
            version = os.environ.get("POCKETLAB_SERVICE_VERSION", "")
        records = [record for record in _read() if str(record.get("name") or "") != name]
        record = {
            "name": name,
            "argv": command_argv,
            "cwd": cwd,
            "script": script,
            "interpreter": interpreter,
            "version": version,
            "run_id": os.environ.get("POCKETLAB_QUALIFICATION_RUN_ID", ""),
            "node_id": os.environ.get("POCKETLAB_NODE_ID", ""),
            "process_spec_hash": os.environ.get("POCKETLAB_PROCESS_SPEC_HASH", ""),
            "policy_fingerprint": os.environ.get("POCKETLAB_PM2_POLICY_FINGERPRINT", ""),
            "autorestart": process_options.get("autorestart", True),
            "kill_timeout": process_options.get("kill_timeout"),
            "max_restarts": process_options.get("max_restarts"),
            "min_uptime": process_options.get("min_uptime"),
            "max_memory_restart": process_options.get("max_memory_restart"),
            "restart_delay": process_options.get("restart_delay"),
            "exp_backoff_restart_delay": process_options.get("exp_backoff_restart_delay"),
            "restart_time": 0,
            "status": "stopped",
        }
        records.append(_start_record(record))
        _write(records)
        return 0
    if command in {"restart", "stop", "delete"}:
        if len(args) < 2:
            raise RuntimeError("qualification PM2 process name is required")
        name = args[1]
        _validate_name(name)
        records = _read()
        found = next((record for record in records if str(record.get("name") or "") == name), None)
        if found is None:
            _write_error("CommandError", "process_not_found")
            return 1
        if command == "delete":
            _terminate(found)
            _write([record for record in records if record is not found])
            return 0
        if command == "stop":
            _terminate(found)
            found["status"] = "stopped"
            _write(records)
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
