from __future__ import annotations

"""Backend-suite isolation for process-global runtime state.

Production database replacement deliberately preserves projection registrations.
That is correct for restore/recovery, but a pytest process repeatedly swaps unrelated
temporary databases while importing process-global schedulers, SQLite path caches,
and release runtime locks. Selected suites therefore receive process-equivalent
isolation without changing production ownership or recovery contracts.
"""

import sys
from pathlib import Path

import pytest


_SCHEDULER_ISOLATED_MODULES = {
    "test_lite_command_attention_audit_idempotency.py",
    "test_lite_command_lifecycle_reconciliation.py",
    "test_lite_control_plane_sqlite_p3.py",
    "test_lite_devices_durable_enrollment.py",
    "test_lite_dispatch_admission_logging.py",
    "test_lite_e1_e3_e4_transactional_prepared_scheduler.py",
    "test_lite_idle_efficiency_runtime.py",
    "test_lite_phase3a_apps_recovery_semantic_revisions.py",
    "test_lite_revision_sync_n4_n5.py",
}

_RELEASE_ISOLATED_MODULES = {
    "test_lite_native_release.py",
    "test_release_process_isolation.py",
}


def _freshen_projection_scheduler() -> None:
    module = sys.modules.get("api_fastapi.services.projection_scheduler")
    if module is None:
        return
    scheduler = getattr(module, "PROJECTION_SCHEDULER", None)
    if scheduler is None:
        return

    try:
        scheduler.quiesce_for_database_switch(timeout_seconds=2.0)
    except Exception:
        pass
    try:
        scheduler.shutdown(drain_seconds=2.0)
    except Exception:
        pass

    condition = getattr(scheduler, "_condition", None)
    if condition is None:
        return
    with condition:
        scheduler._states.clear()
        scheduler._jobs.clear()
        scheduler._heap.clear()
        scheduler._active_futures.clear()
        scheduler._sequence = 0
        scheduler._dispatcher = None
        scheduler._io_executor = None
        scheduler._cpu_executor = None
        scheduler._accepting = False
        scheduler._shutdown = False
        scheduler._startup_complete = False
        scheduler._event_signal_count = 0
        scheduler._signal_schema_ready = False
        scheduler._dispatcher_started_at = ""
        scheduler._last_dispatch_at = ""
        scheduler._last_dispatch_error_type = ""
        scheduler._dispatcher_restart_count = 0
        scheduler._dispatch_count = 0
        scheduler._future_head_skip_count = 0
        condition.notify_all()


def _freshen_release_runtime_state() -> None:
    try:
        from api_fastapi.db.connection import reset_sqlite_path_cache
        from api_fastapi.db.runtime import SQLITE_READS

        reset_sqlite_path_cache()
        SQLITE_READS.invalidate()
    except Exception:
        pass
    module = sys.modules.get("api_fastapi.services.release_runtime")
    if module is not None:
        module._OPERATION_LOCK = None
        process_lock = getattr(module, "_PROCESS_LOCK", None)
        process_state = getattr(module, "_PROCESS_STATE", None)
        if process_lock is not None and isinstance(process_state, dict):
            with process_lock:
                process_state.update(
                    {
                        "process_alive": False,
                        "process_pid": 0,
                        "active_operation": "",
                        "started_at": "",
                        "last_completed_at": "",
                        "last_error_type": "",
                        "last_error_at": "",
                    }
                )


@pytest.fixture(autouse=True)
def isolate_process_global_projection_scheduler(request, monkeypatch):
    filename = Path(str(request.node.fspath)).name
    if filename not in _SCHEDULER_ISOLATED_MODULES:
        yield
        return

    # Scheduler unit/contract suites model one local execution owner. Production
    # API/worker role separation remains tested elsewhere; without an explicit
    # role here a full-suite process can inherit ownership context from earlier
    # runtime tests and persist dirty signals instead of executing their local
    # ProjectionScheduler instances.
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "test")
    monkeypatch.setenv("POCKETLAB_PROJECTION_EXECUTION_OWNER", "test")

    _freshen_projection_scheduler()
    yield
    _freshen_projection_scheduler()


@pytest.fixture(autouse=True)
def isolate_release_runtime_process_state(request):
    filename = Path(str(request.node.fspath)).name
    if filename not in _RELEASE_ISOLATED_MODULES:
        yield
        return

    _freshen_release_runtime_state()
    yield
    _freshen_release_runtime_state()
