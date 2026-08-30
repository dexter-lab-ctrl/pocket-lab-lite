from __future__ import annotations

import pytest

from pocketlab_dev_mcp.policy import (
    UnknownValidationTarget,
    build_validation_targets,
    get_validation_target,
)


def test_policy_contains_only_the_approved_validation_ids():
    targets = build_validation_targets("/fixed/python")
    assert tuple(targets) == (
        "mcp_unit_tests",
        "mcp_python_compile",
        "mcp_shell_syntax",
        "git_diff_check",
        "backend_lite_api",
        "frontend_build",
        "lite_api_check",
        "docs_check",
        "lite_check",
    )
    assert all(isinstance(target.argv, tuple) for target in targets.values())
    assert all(";" not in part for target in targets.values() for part in target.argv)


@pytest.mark.parametrize("candidate", ["lite_check; rm -rf /", "$(whoami)", "`cat /etc/passwd`", "../../outside", "--exec"])
def test_unknown_target_is_rejected_before_execution(candidate: str):
    with pytest.raises(UnknownValidationTarget):
        get_validation_target(candidate)


def test_policy_has_no_caller_supplied_cwd_or_executable():
    target = get_validation_target("git_diff_check")
    assert target.argv == ("git", "diff", "--check")
    assert not hasattr(target, "cwd")
    assert not hasattr(target, "environment")


def test_forbidden_operation_names_are_not_validation_targets():
    forbidden = {
        "shell",
        "exec",
        "run_command",
        "sql",
        "ssh",
        "git_add",
        "git_commit",
        "git_push",
        "git_reset",
        "nats_publish",
        "pm2_restart",
        "tailscale_up",
    }
    assert forbidden.isdisjoint(build_validation_targets())
