from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "pocket-lab-final-structure" / "runtime" / "supervisors" / "pocketlab_pm2_identity.py"


def _load():
    spec = importlib.util.spec_from_file_location("pocketlab_pm2_identity_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _daemon(module, pid: int, *, home: str = "/tmp/pm2", node: str = "/usr/bin/node"):
    return module.DaemonObservation(
        pid=pid,
        home=home,
        executable=node,
        ppid=1,
        environment_home=home,
    )


def test_one_canonical_daemon_and_owned_service_topology_is_healthy():
    module = _load()

    report = module.evaluate_identity(
        [_daemon(module, 101)],
        expected_home="/tmp/pm2",
        expected_node="/usr/bin/node",
        pid_file_pid=101,
        pid_file_present=True,
        service_parent_pids=[101, 101],
    )

    assert report.state == "ok"
    assert report.canonical_pid == 101
    assert report.reasons == ()


def test_same_home_duplicate_daemons_require_normalization():
    module = _load()

    report = module.evaluate_identity(
        [_daemon(module, 101), _daemon(module, 102)],
        expected_home="/tmp/pm2",
        expected_node="/usr/bin/node",
        pid_file_pid=101,
        pid_file_present=True,
        service_parent_pids=[101],
    )

    assert report.state == "invalid"
    assert module.PM2_DUPLICATE_DAEMON in report.reasons
    assert module.PM2_NORMALIZATION_REQUIRED in report.reasons


def test_distinct_pm2_home_is_not_silently_accepted():
    module = _load()

    report = module.evaluate_identity(
        [_daemon(module, 101), _daemon(module, 202, home="/tmp/other-pm2")],
        expected_home="/tmp/pm2",
        expected_node="/usr/bin/node",
        pid_file_pid=101,
        pid_file_present=True,
    )

    assert report.state == "invalid"
    assert module.PM2_OWNERSHIP_UNKNOWN in report.reasons
    assert module.PM2_NORMALIZATION_REQUIRED in report.reasons


def test_wrong_or_stale_pid_file_fails_closed():
    module = _load()

    wrong = module.evaluate_identity(
        [_daemon(module, 101)],
        expected_home="/tmp/pm2",
        expected_node="/usr/bin/node",
        pid_file_pid=202,
        pid_file_present=True,
    )
    stale = module.evaluate_identity(
        [],
        expected_home="/tmp/pm2",
        expected_node="/usr/bin/node",
        pid_file_pid=202,
        pid_file_present=True,
    )

    for report in (wrong, stale):
        assert report.state == "invalid"
        assert module.PM2_PIDFILE_OWNER_MISMATCH in report.reasons
        assert module.PM2_NORMALIZATION_REQUIRED in report.reasons


def test_pid_reuse_with_wrong_executable_is_unknown_not_healthy():
    module = _load()

    report = module.evaluate_identity(
        [_daemon(module, 101, node="/usr/bin/python3")],
        expected_home="/tmp/pm2",
        expected_node="/usr/bin/node",
        pid_file_pid=101,
        pid_file_present=True,
    )

    assert report.state == "invalid"
    assert module.PM2_OWNERSHIP_UNKNOWN in report.reasons


def test_ipc_or_socket_owner_mismatch_is_rejected():
    module = _load()

    parent_mismatch = module.evaluate_identity(
        [_daemon(module, 101)],
        expected_home="/tmp/pm2",
        expected_node="/usr/bin/node",
        pid_file_pid=101,
        pid_file_present=True,
        service_parent_pids=[202],
    )
    socket_mismatch = module.evaluate_identity(
        [_daemon(module, 101)],
        expected_home="/tmp/pm2",
        expected_node="/usr/bin/node",
        pid_file_pid=101,
        pid_file_present=True,
        socket_owner_pids={"rpc": [202], "pub": [101]},
    )

    for report in (parent_mismatch, socket_mismatch):
        assert report.state == "invalid"
        assert module.PM2_IPC_OWNER_MISMATCH in report.reasons
        assert module.PM2_NORMALIZATION_REQUIRED in report.reasons


def test_empty_pm2_projection_is_valid_evidence_for_a_canonical_empty_daemon():
    module = _load()

    report = module.evaluate_identity(
        [_daemon(module, 101)],
        expected_home="/tmp/pm2",
        expected_node="/usr/bin/node",
        pid_file_pid=101,
        pid_file_present=True,
        service_parent_pids=[],
    )

    assert report.state == "ok"


def test_live_topology_with_unreadable_child_parent_is_unknown():
    module = _load()

    report = module.evaluate_identity(
        [_daemon(module, 101)],
        expected_home="/tmp/pm2",
        expected_node="/usr/bin/node",
        pid_file_pid=101,
        pid_file_present=True,
        service_parent_unknown=True,
    )

    assert report.state == "invalid"
    assert module.PM2_OWNERSHIP_UNKNOWN in report.reasons


def test_no_daemon_without_pid_file_is_explicitly_absent():
    module = _load()

    report = module.evaluate_identity(
        [],
        expected_home="/tmp/pm2",
        expected_node="/usr/bin/node",
        pid_file_pid=None,
        pid_file_present=False,
    )

    assert report.state == "absent"


def test_discovery_ignores_benign_process_text_and_matches_exact_title(tmp_path):
    module = _load()
    proc_root = tmp_path / "proc"
    proc_root.mkdir()
    node = tmp_path / "node"
    node.write_text("node", encoding="utf-8")
    node.chmod(0o755)

    def fake_process(pid: int, command: str, *, ppid: int = 1):
        directory = proc_root / str(pid)
        directory.mkdir()
        (directory / "cmdline").write_bytes(command.encode() + b"\0")
        (directory / "exe").symlink_to(node)
        (directory / "environ").write_bytes(b"PM2_HOME=/tmp/pm2\0")
        (directory / "stat").write_text(f"{pid} (node) S {ppid} 0 0\n", encoding="utf-8")

    fake_process(101, "PM2 v7.0.1: God Daemon (/tmp/pm2)")
    fake_process(202, "node script.js --text 'PM2 v7.0.1: God Daemon (/tmp/pm2)'")

    discovered = module.discover_daemons(proc_root, expected_node=str(node))

    assert [item.pid for item in discovered] == [101]
