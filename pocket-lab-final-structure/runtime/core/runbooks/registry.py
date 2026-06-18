from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import RunbookDefinition, RunbookStep


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "runbooks").is_dir() and (parent / "Taskfile.yml").exists():
            return parent
    return current.parents[4]


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


class RunbookRegistry:
    def __init__(self, runbooks_dir: Path | None = None):
        self.runbooks_dir = Path(runbooks_dir) if runbooks_dir else _repo_root() / "runbooks"

    def list(self) -> list[RunbookDefinition]:
        if not self.runbooks_dir.exists():
            return []
        return [self.load(path) for path in sorted(self.runbooks_dir.glob("*.yaml"))]

    def names(self) -> list[str]:
        return [runbook.name for runbook in self.list()]

    def get(self, name: str) -> RunbookDefinition | None:
        normalized = name.strip()
        for runbook in self.list():
            if runbook.name == normalized:
                return runbook
        return None

    def load(self, path: Path) -> RunbookDefinition:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        metadata = _as_dict(data.get("metadata"))
        spec = _as_dict(data.get("spec"))
        steps_raw = _as_list(spec.get("steps"))

        name = str(metadata.get("name") or path.stem).strip()
        title = str(metadata.get("title") or name).strip()

        steps: list[RunbookStep] = []
        for index, raw_step in enumerate(steps_raw, start=1):
            step = _as_dict(raw_step)
            operation = str(step.get("operation") or "").strip()
            step_name = str(step.get("name") or operation or f"step_{index}").strip()

            target_raw = step.get("target")
            if isinstance(target_raw, dict):
                target = dict(target_raw)
            elif isinstance(target_raw, str):
                target = {"type": "runbook", "ref": target_raw}
            else:
                target = {"type": "runbook", "ref": name}

            params = _as_dict(step.get("params"))

            steps.append(
                RunbookStep(
                    name=step_name,
                    operation=operation,
                    target=target,
                    params=params,
                    requires_approval=step.get("requiresApproval") is True,
                    timeout_seconds=(
                        int(step["timeoutSeconds"])
                        if step.get("timeoutSeconds") is not None
                        else None
                    ),
                )
            )

        return RunbookDefinition(
            name=name,
            title=title,
            source_file=str(path),
            spec=spec,
            steps=steps,
            requires_approval=spec.get("requiresApproval") is True,
            severity=str(spec.get("severity") or "medium").lower(),
        )
