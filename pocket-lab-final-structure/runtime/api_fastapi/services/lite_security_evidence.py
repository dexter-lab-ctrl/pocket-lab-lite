from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import deps
from . import lite_security_policy as policy


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


def write_json(path: Path, data: Any) -> None:
    deps.core.write_json_file(path, policy.redact_value(data))


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
