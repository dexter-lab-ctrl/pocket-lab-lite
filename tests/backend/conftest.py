from __future__ import annotations

"""Backend-suite isolation for process-global runtime schedulers.

Production database replacement deliberately preserves projection registrations.
That is correct for restore/recovery, but a pytest process repeatedly swaps unrelated
temporary databases while importing one process-global scheduler. These selected
scheduler/database-switch suites require a fresh process-equivalent scheduler state
between tests so callbacks, retry windows and executor shutdown do not leak across
otherwise isolated databases.
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


@pytest.fixture(autouse=True)
def isolate_process_global_projection_scheduler(request):
    filename = Path(str(request.node.fspath)).name
    if filename not in _SCHEDULER_ISOLATED_MODULES:
        yield
        return

    _freshen_projection_scheduler()
    yield
    _freshen_projection_scheduler()
