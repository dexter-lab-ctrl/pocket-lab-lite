# Pocket Lab Lite Codex MCP validation

## Repository qualification

Run these checks from the native WSL repository root:

```bash
python3 -m py_compile \
  tools/mcp/pocketlab_dev/pocketlab_dev_mcp/*.py \
  tools/mcp/pocketlab_dev/pocketlab_dev_mcp/tools/*.py

bash -n \
  scripts/dev/codex/run_pocketlab_mcp.sh \
  scripts/dev/codex/check_mcp_dev.sh

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  .pocketlab-dev/mcp/venv/bin/python -m pytest -q \
  tools/mcp/pocketlab_dev/tests

scripts/dev/codex/check_mcp_dev.sh
```

The transport check initializes the real stdio server, requires the exact six-tool set and nine diagnostic IDs, and calls `repo_status`, `validation_targets`, `diagnostic_targets`, and deterministic `diagnostic_summary(openapi_routes)`. It does not depend on PM2, NATS, a Server Phone, network access, Tailscale, Docker, or scanners. Remote behavior is mocked in the focused MCP tests.

Then call `run_validation` through MCP for `mcp_python_compile`, `mcp_shell_syntax`, and `git_diff_check`. Broader approved targets are available only when deliberately requested.

For this repository-level tooling change, complete the standard gates:

```bash
git diff --check
task lite:docs:generate
task lite:docs:check
task lite:check
```

## Desktop integration qualification

After a human performs the machine-local registration, restart Desktop and ask it to use `repo_status`, list `validation_targets`, list `diagnostic_targets`, and call `diagnostic_summary` with `openapi_routes`. This remains separate `UNVALIDATED` Desktop evidence; do not call `run_validation` in the first Desktop smoke test.

## Rollback

Repository and Desktop rollback require explicit human authorization. The local virtual environment at `.pocketlab-dev/mcp/venv` is disposable. Do not remove it automatically.
