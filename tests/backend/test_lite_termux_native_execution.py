from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
COMMON = (
    ROOT
    / "pocket-lab-final-structure"
    / "pocket-lab-bootstrap-production-scripts-patched"
    / "scripts"
    / "lib"
    / "common.sh"
)


def _run(
    tmp_path: Path,
    script: str,
    *,
    prefix: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    selected_prefix = prefix or (tmp_path / "prefix")
    selected_prefix.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(home),
            "PREFIX": str(selected_prefix),
            "TERMUX_VERSION": "0.118.3-test",
            "COMMON_PATH": str(COMMON),
        }
    )
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", "-lc", 'source "$COMMON_PATH"\n' + script],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_pm2_invocation_bypasses_env_shebang_with_native_node(tmp_path: Path):
    prefix = tmp_path / "prefix"
    bin_dir = prefix / "bin"
    bin_dir.mkdir(parents=True)
    cli = prefix / "lib" / "node_modules" / "pm2" / "bin" / "pm2"
    cli.parent.mkdir(parents=True)
    cli.write_text("#!/usr/bin/env node\n", encoding="utf-8")
    cli.chmod(0o755)
    (bin_dir / "pm2").symlink_to(cli)
    node = bin_dir / "node"
    node.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$@" >"$NODE_ARGS"\n'
        'if [[ "${2:-}" == "jlist" ]]; then printf "[]\\n"; fi\n',
        encoding="utf-8",
    )
    node.chmod(0o755)
    args = tmp_path / "node-args"

    result = _run(
        tmp_path,
        "pm2 status",
        prefix=prefix,
        extra_env={"NODE_ARGS": str(args)},
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert args.read_text(encoding="utf-8").splitlines() == [str(cli), "status"]


def test_tailscaled_helper_uses_native_bash_for_env_shebang(tmp_path: Path):
    prefix = tmp_path / "prefix"
    bin_dir = prefix / "bin"
    bin_dir.mkdir(parents=True)
    shutil.copy2("/bin/bash", bin_dir / "bash")
    helper = bin_dir / "tailscaled-start"
    marker = tmp_path / "tailscale-started"
    helper.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >"$TAILSCALE_MARKER"\n',
        encoding="utf-8",
    )
    helper.chmod(0o755)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path / "home"),
            "PREFIX": str(prefix),
            "TERMUX_VERSION": "0.118.3-test",
            "COMMON_PATH": str(COMMON),
            "TAILSCALE_MARKER": str(marker),
        }
    )
    result = subprocess.run(
        ["bash", "-lc", 'source "$COMMON_PATH"\ntailscaled_start --service=status'],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert marker.read_text(encoding="utf-8").strip() == "--service=status"


def test_native_node_rejects_outside_termux_path(tmp_path: Path):
    prefix = tmp_path / "prefix"
    result = _run(
        tmp_path,
        'POCKETLAB_NATIVE_NODE=/bin/bash pocketlab_resolve_native_node',
        prefix=prefix,
    )
    assert result.returncode != 0
    assert result.stdout.strip() == ""


def test_exact_process_identity_does_not_match_similarly_named_process(tmp_path: Path):
    prefix = tmp_path / "prefix"
    binary = prefix / "bin" / "sshd"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    result = _run(
        tmp_path,
        f'''\
ps() {{
  printf '%s\\n' '101 {binary} -D' '102 {binary}-session -D'
}}
pocketlab_process_has_executable sshd
ps() {{
  printf '%s\\n' '102 {binary}-session -D'
}}
if pocketlab_process_has_executable sshd; then exit 1; fi
''',
        prefix=prefix,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_empty_pm2_state_is_not_saved(tmp_path: Path):
    marker = tmp_path / "saved"
    result = _run(
        tmp_path,
        f'''\
pm2() {{
  case "${{1:-}}" in
    jlist) printf '%s\\n' '[]' ;;
    save) : >"{marker}" ;;
  esac
}}
pm2_save_if_nonempty
[[ ! -e "{marker}" ]]
pm2() {{
  case "${{1:-}}" in
    jlist) printf '%s\\n' '[{{"name":"pocket-api"}}]' ;;
    save) : >"{marker}" ;;
  esac
}}
pm2_save_if_nonempty
[[ -e "{marker}" ]]
''',
    )
    assert result.returncode == 0, result.stderr or result.stdout
