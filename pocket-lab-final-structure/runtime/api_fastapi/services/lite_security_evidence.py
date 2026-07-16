from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .. import deps
from . import lite_security_policy as policy
from . import lite_storage_faults


def security_root() -> Path:
    root = deps.settings().state_dir / "security"
    root.mkdir(parents=True, exist_ok=True)
    (root / "runs").mkdir(parents=True, exist_ok=True)
    (root / "evidence").mkdir(parents=True, exist_ok=True)
    return root


def state_path() -> Path:
    return security_root() / "security_state.json"


def runs_dir() -> Path:
    return security_root() / "runs"


def evidence_dir(run_id: str) -> Path:
    safe = safe_run_id(run_id)
    path = security_root() / "evidence" / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_run_id(run_id: str) -> str:
    value = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(run_id or "").strip())
    return value[:120] or "unknown"


def _write_failpoint_for(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    if "evidence" in parts:
        return "security_evidence_write"
    return "compatibility_json_write"


def write_json(path: Path, data: Any) -> None:
    clean = policy.redact_value(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    lite_storage_faults.raise_if_storage_fault(_write_failpoint_for(path))
    lite_storage_faults.raise_if_storage_fault("atomic_temp_write")
    tmp_name: str | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(clean, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            lite_storage_faults.raise_if_storage_fault("atomic_fsync")
            os.fsync(handle.fileno())
        lite_storage_faults.raise_if_storage_fault("atomic_replace")
        os.replace(tmp_name, path)
        tmp_name = None
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass


def compact_dir() -> Path:
    root = security_root() / "compact"
    root.mkdir(parents=True, exist_ok=True)
    (root / "profiles").mkdir(parents=True, exist_ok=True)
    (root / "details").mkdir(parents=True, exist_ok=True)
    return root


def compact_path(name: str) -> Path:
    safe = safe_run_id(name).replace("-json", ".json") if name.endswith(".json") else safe_run_id(name)
    return compact_dir() / safe


def compact_profile_path(profile: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(profile or "quick").lower())
    return compact_dir() / "profiles" / f"{safe[:32] or 'quick'}.json"


def compact_details_path(run_id: str) -> Path:
    return compact_dir() / "details" / f"{safe_run_id(run_id)}.json"


def write_compact_json(path: Path, data: Any) -> Any:
    clean = policy.redact_value(data)
    write_json(path, clean)
    return clean


def read_compact_json(path: Path, default: Any) -> Any:
    return read_json(path, default)


def read_json(path: Path, default: Any) -> Any:
    return policy.redact_value(deps.core.read_json_file(path, default))


def write_state(state: dict[str, Any]) -> dict[str, Any]:
    clean = policy.redact_value(state)
    write_json(state_path(), clean)
    return clean


def read_state() -> dict[str, Any] | None:
    path = state_path()
    if not path.exists():
        return None
    payload = read_json(path, {})
    return payload if isinstance(payload, dict) else None


def write_run(run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    clean = policy.redact_value(payload)
    write_json(runs_dir() / f"{safe_run_id(run_id)}.json", clean)
    return clean


def read_run(run_id: str) -> dict[str, Any] | None:
    payload = read_json(runs_dir() / f"{safe_run_id(run_id)}.json", None)
    return payload if isinstance(payload, dict) else None


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for path in sorted(runs_dir().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        payload = read_json(path, {})
        if isinstance(payload, dict):
            runs.append(payload)
        if len(runs) >= max(1, limit):
            break
    return runs


def delete_run(run_id: str) -> None:
    path = runs_dir() / f"{safe_run_id(run_id)}.json"
    try:
        path.unlink()
    except FileNotFoundError:
        return


def write_evidence(run_id: str, filename: str, payload: Any) -> str:
    directory = evidence_dir(run_id)
    safe_name = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in filename)
    write_json(directory / safe_name, payload)
    return f"security/evidence/{safe_run_id(run_id)}/{safe_name}"


def read_evidence_summary(run_id: str) -> dict[str, Any] | None:
    path = evidence_dir(run_id) / "summary.json"
    if not path.exists():
        return None
    payload = read_json(path, {})
    return payload if isinstance(payload, dict) else None
