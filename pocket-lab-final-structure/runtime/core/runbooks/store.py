from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contracts import utc_now_iso


class RunbookExecutionStore:
    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, execution_id: str) -> Path:
        safe = "".join(ch for ch in execution_id if ch.isalnum() or ch in {"-", "_"})
        return self.state_dir / f"{safe}.json"

    def create(self, execution: dict[str, Any]) -> dict[str, Any]:
        now = utc_now_iso()
        execution = {
            "created_at": now,
            "updated_at": now,
            "events": [],
            "steps": [],
            **execution,
        }
        self.write(execution)
        return execution

    def write(self, execution: dict[str, Any]) -> None:
        execution["updated_at"] = utc_now_iso()
        path = self._path(str(execution["execution_id"]))
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(execution, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        tmp.replace(path)

    def get(self, execution_id: str) -> dict[str, Any] | None:
        path = self._path(execution_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        files = sorted(self.state_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        return [json.loads(path.read_text(encoding="utf-8")) for path in files[:limit]]

    def update(self, execution_id: str, **updates: Any) -> dict[str, Any]:
        execution = self.get(execution_id)
        if not execution:
            raise KeyError(f"Runbook execution not found: {execution_id}")
        execution.update(updates)
        self.write(execution)
        return execution

    def append_event(self, execution_id: str, event: dict[str, Any]) -> dict[str, Any]:
        execution = self.get(execution_id)
        if not execution:
            raise KeyError(f"Runbook execution not found: {execution_id}")
        events = list(execution.get("events") or [])
        events.append({"time": utc_now_iso(), **event})
        execution["events"] = events
        self.write(execution)
        return execution

    def append_step(self, execution_id: str, step: dict[str, Any]) -> dict[str, Any]:
        execution = self.get(execution_id)
        if not execution:
            raise KeyError(f"Runbook execution not found: {execution_id}")
        steps = list(execution.get("steps") or [])
        steps.append({"time": utc_now_iso(), **step})
        execution["steps"] = steps
        self.write(execution)
        return execution
