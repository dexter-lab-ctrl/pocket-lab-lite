from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class TaskDefinition:
    name: str
    description: str = ""
    operation: str = ""
    defaults: Dict[str, Any] = None

    def asdict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "operation": self.operation,
            "defaults": dict(self.defaults or {}),
        }


class TaskfileRegistry:
    def __init__(self, *taskfile_paths: Path):
        self.taskfile_paths = [Path(p) for p in taskfile_paths if p]
        self.tasks: Dict[str, TaskDefinition] = {}
        self.reload()

    def reload(self) -> None:
        self.tasks.clear()
        for path in self.taskfile_paths:
            if not path.exists():
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for name, payload in (data.get("tasks") or {}).items():
                self.tasks[name] = TaskDefinition(
                    name=name,
                    description=payload.get("desc", "")
                    or payload.get("description", ""),
                    operation=payload.get("operation", name),
                    defaults=payload.get("params", {}) or {},
                )

    def get(self, name: str) -> Optional[TaskDefinition]:
        return self.tasks.get(name)

    def resolve_operation(self, operation: str) -> TaskDefinition:
        task = self.get(operation)
        if task is None:
            return TaskDefinition(name=operation, operation=operation, defaults={})
        return task
