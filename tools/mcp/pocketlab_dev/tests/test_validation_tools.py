from __future__ import annotations

import pytest

from pocketlab_dev_mcp.policy import UnknownValidationTarget
from pocketlab_dev_mcp.runner import ProcessResult
from pocketlab_dev_mcp.tools.validation import ValidationTools


class FakeRunner:
    def __init__(self, result: ProcessResult) -> None:
        self.result = result
        self.calls = []

    def run(self, argv, *, timeout_seconds):
        self.calls.append((argv, timeout_seconds))
        return self.result


def test_validation_targets_are_stable(repository_root):
    targets = ValidationTools(repository_root).validation_targets()["targets"]
    assert [target["id"] for target in targets][:4] == [
        "mcp_unit_tests",
        "mcp_python_compile",
        "mcp_shell_syntax",
        "git_diff_check",
    ]


def test_known_target_dispatches_fixed_command(repository_root):
    runner = FakeRunner(ProcessResult(0, 3, "ok", "", False, False))
    result = ValidationTools(repository_root, runner=runner).run_validation("git_diff_check")
    assert result["status"] == "pass"
    assert runner.calls[0][0] == ("git", "diff", "--check")


def test_unknown_target_never_executes(repository_root):
    runner = FakeRunner(ProcessResult(0, 3, "", "", False, False))
    with pytest.raises(UnknownValidationTarget):
        ValidationTools(repository_root, runner=runner).run_validation("$(whoami)")
    assert runner.calls == []


def test_failed_timeout_and_truncated_results_remain_truthful(repository_root):
    failed = ValidationTools(
        repository_root,
        runner=FakeRunner(ProcessResult(2, 3, "", "failure", False, True)),
    ).run_validation("git_diff_check")
    assert failed["status"] == "fail"
    assert failed["truncated"] is True
    timed_out = ValidationTools(
        repository_root,
        runner=FakeRunner(ProcessResult(None, 30, "", "", True, False)),
    ).run_validation("git_diff_check")
    assert timed_out["status"] == "timeout"
