from __future__ import annotations

import asyncio

from pocketlab_dev_mcp.server import create_server


def test_server_exposes_exactly_the_six_approved_tools(repository_root):
    tools = asyncio.run(create_server(repository_root).list_tools())
    by_name = {tool.name: tool for tool in tools}
    assert set(by_name) == {
        "repo_status",
        "changed_files",
        "validation_targets",
        "run_validation",
        "diagnostic_targets",
        "diagnostic_summary",
    }
    assert by_name["repo_status"].annotations.read_only_hint is True
    assert by_name["changed_files"].annotations.idempotent_hint is True
    assert by_name["validation_targets"].annotations.open_world_hint is False
    assert by_name["run_validation"].annotations.read_only_hint is False
    assert by_name["diagnostic_targets"].annotations.read_only_hint is True
    assert by_name["diagnostic_summary"].annotations.idempotent_hint is True
    assert "scope" in by_name["changed_files"].input_schema["properties"]
    assert "target" in by_name["run_validation"].input_schema["properties"]
    assert set(by_name["diagnostic_summary"].input_schema["properties"]) == {"target"}
