from __future__ import annotations

import os
import errno
import subprocess
import sys
import time

from pocketlab_dev_mcp.runner import ProcessRunner, STDOUT_LIMIT_BYTES, filtered_environment


def test_runner_uses_fixed_root_and_shell_false(repository_root, monkeypatch):
    observed = {}
    original = subprocess.Popen

    def recording_popen(*args, **kwargs):
        observed.update(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", recording_popen)
    result = ProcessRunner(repository_root).run((sys.executable, "-c", "print('ok')"), timeout_seconds=5)
    assert result.exit_code == 0
    assert result.stdout_tail == "ok\n"
    assert observed["shell"] is False
    assert observed["cwd"] == str(repository_root)
    assert observed["start_new_session"] is True


def test_runner_caps_output_and_marks_truncation(repository_root):
    result = ProcessRunner(repository_root).run(
        (sys.executable, "-c", "print('x' * 20000)"), timeout_seconds=5
    )
    assert result.exit_code == 0
    assert result.truncated is True
    assert len(result.stdout_tail.encode()) <= STDOUT_LIMIT_BYTES


def test_runner_preserves_failure_timeout_and_redacts(repository_root):
    runner = ProcessRunner(repository_root)
    failed = runner.run((sys.executable, "-c", "import sys; print('token=secret'); sys.exit(7)"), timeout_seconds=5)
    assert failed.exit_code == 7
    assert "secret" not in failed.stdout_tail
    timeout = runner.run((sys.executable, "-c", "import time; time.sleep(1)"), timeout_seconds=0.01)
    assert timeout.timed_out is True
    assert timeout.exit_code is None


def test_environment_filter_omits_secret_values(repository_root):
    environment = filtered_environment({"PATH": os.environ["PATH"], "API_TOKEN": "never-forward"})
    result = ProcessRunner(repository_root, environment=environment).run(
        (sys.executable, "-c", "import os; print(os.getenv('API_TOKEN', 'absent'))"),
        timeout_seconds=5,
    )
    assert result.stdout_tail == "absent\n"


def test_timeout_terminates_descendant_and_returns_within_bound(repository_root):
    child = (
        "import subprocess, sys, time; "
        "descendant = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
        "print(descendant.pid, flush=True); time.sleep(30)"
    )
    started = time.monotonic()
    result = ProcessRunner(repository_root).run((sys.executable, "-c", child), timeout_seconds=0.25)
    elapsed = time.monotonic() - started
    descendant_pid = int(result.stdout_tail.strip())
    assert result.timed_out is True
    assert result.exit_code is None
    assert elapsed < 5
    for _ in range(20):
        try:
            os.kill(descendant_pid, 0)
        except OSError as exc:
            assert exc.errno == errno.ESRCH
            break
        time.sleep(0.05)
    else:
        raise AssertionError("timed-out descendant remained alive")
