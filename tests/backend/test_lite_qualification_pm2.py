from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[2]
SHIM = ROOT / "scripts" / "dev" / "lite" / "qualification_pm2.py"


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PM2_HOME": str(tmp_path / "pm2"),
        "POCKETLAB_QUALIFICATION_PM2_ALLOW_SERVICES": "test-service",
        "POCKETLAB_QUALIFICATION_LOG_DIR": str(tmp_path / "logs"),
        "POCKETLAB_QUALIFICATION_RUN_ID": "a" * 24,
    }
    return subprocess.run(
        [sys.executable, str(SHIM), *args],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_ecosystem_start_projects_owned_identity_and_supports_stop(tmp_path: Path) -> None:
    worker = tmp_path / "worker.py"
    worker.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    ecosystem = tmp_path / "test-service.config.cjs"
    app = {
        "args": [],
        "cwd": str(tmp_path),
        "interpreter": sys.executable,
        "name": "test-service",
        "script": str(worker),
    }
    ecosystem.write_text(
        "const app = "
        + json.dumps(app, separators=(",", ":"))
        + ";\napp.env = process.env;\nmodule.exports = { apps: [app] };\n",
        encoding="utf-8",
    )

    started = _run(tmp_path, "start", str(ecosystem), "--only", "test-service")
    assert started.returncode == 0, started.stderr
    listed = _run(tmp_path, "jlist")
    assert listed.returncode == 0, listed.stderr
    item = next(value for value in json.loads(listed.stdout) if value["name"] == "test-service")
    projected = item["pm2_env"]
    assert projected["status"] == "online"
    assert projected["pid"] > 0
    assert projected["pm_exec_path"] == str(worker)
    assert projected["exec_interpreter"] == sys.executable
    assert projected["pm_cwd"] == str(tmp_path)
    assert projected["POCKETLAB_SERVICE_VERSION"] == ""

    stopped = _run(tmp_path, "stop", "test-service")
    assert stopped.returncode == 0, stopped.stderr
    listed_after_stop = _run(tmp_path, "jlist")
    assert json.loads(listed_after_stop.stdout)[0]["pm2_env"]["status"] == "stopped"
    deleted = _run(tmp_path, "delete", "test-service")
    assert deleted.returncode == 0, deleted.stderr
    assert json.loads(_run(tmp_path, "jlist").stdout) == []


def test_unlisted_service_name_is_rejected(tmp_path: Path) -> None:
    result = _run(tmp_path, "delete", "not-run-owned")
    assert result.returncode != 0
    error = json.loads((tmp_path / "pm2" / "qualification-last-error.json").read_text(encoding="utf-8"))
    assert error["reason_code"] == "process_name_not_run_owned"
