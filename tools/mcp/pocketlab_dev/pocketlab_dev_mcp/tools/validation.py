"""Allow-listed local validation operations for the developer MCP."""

from __future__ import annotations

from pathlib import Path

from ..policy import get_validation_target, validation_target_metadata
from ..runner import ProcessRunner


class ValidationTools:
    def __init__(self, repository_root: Path, runner: ProcessRunner | None = None) -> None:
        self.runner = runner or ProcessRunner(repository_root)

    def validation_targets(self) -> dict[str, object]:
        return {"targets": validation_target_metadata()}

    def run_validation(self, target: str) -> dict[str, object]:
        definition = get_validation_target(target)
        result = self.runner.run(definition.argv, timeout_seconds=definition.timeout_seconds)
        status = "timeout" if result.timed_out else "pass" if result.exit_code == 0 else "fail"
        summary = (
            f"{definition.command_label} timed out after {definition.timeout_seconds}s"
            if result.timed_out
            else f"{definition.command_label} {'passed' if status == 'pass' else 'failed'}"
        )
        return {
            "status": status,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "target": definition.identifier,
            "summary": summary,
            "stdout_tail": result.stdout_tail,
            "stderr_tail": result.stderr_tail,
            "truncated": result.truncated,
        }
