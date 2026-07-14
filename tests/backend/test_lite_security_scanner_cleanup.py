from __future__ import annotations

import os
import shlex
import time
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _pid_is_live(pid: int) -> bool:
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.exists():
        try:
            state = proc_stat.read_text().split()[2]
            return state != "Z"
        except (OSError, IndexError):
            pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group proof")
def test_scanner_timeout_terminates_and_reaps_descendant_process_group(
    tmp_path,
):
    ensure_runtime_path()
    from api_fastapi.services import lite_security

    child_pid_file = tmp_path / "child.pid"
    script = (
        f"sleep 60 & echo $! > {shlex.quote(str(child_pid_file))}; wait"
    )
    result = lite_security._run_command(
        ["/bin/sh", "-c", script],
        cwd=tmp_path,
        timeout=1,
    )

    assert result["timed_out"] is True
    assert result["process_cleanup"] == "complete"
    child_pid = int(child_pid_file.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and _pid_is_live(child_pid):
        time.sleep(0.05)
    assert _pid_is_live(child_pid) is False
