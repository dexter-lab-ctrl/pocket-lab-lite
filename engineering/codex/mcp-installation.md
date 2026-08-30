# Pocket Lab Lite Codex MCP installation

## Repository-owned layer

The checked-in implementation is located at:

```text
tools/mcp/pocketlab_dev/
scripts/dev/codex/
```

From the native WSL checkout, create the ignored local environment after reviewing the repository candidate:

```bash
cd "$HOME/pocket-lab-lite"
python3 -m venv .pocketlab-dev/mcp/venv
.pocketlab-dev/mcp/venv/bin/python -m pip install --upgrade pip
.pocketlab-dev/mcp/venv/bin/python -m pip install -e 'tools/mcp/pocketlab_dev[test]'
scripts/dev/codex/check_mcp_dev.sh
```

The launcher resolves `$POCKETLAB_REPO` or `$HOME/pocket-lab-lite`; it contains no Windows path or fixed username.

## Machine-owned Desktop layer

Desktop registration occurs only after repository validation and is machine-local. On the current style of Windows/WSL installation, the effective Desktop Codex home may be under:

```text
/mnt/c/Users/$WINDOWS_USER/.codex
```

Do not commit or edit that configuration as part of the repository implementation. Use the checked example in [config.desktop-wsl.example.toml](examples/config.desktop-wsl.example.toml) as a template. The current Codex CLI confirms stdio registrations accept a command and optional environment variables; it does not confirm a `cwd` configuration key, so the example deliberately omits one.

After registration, fully restart Codex Desktop before integration testing.
