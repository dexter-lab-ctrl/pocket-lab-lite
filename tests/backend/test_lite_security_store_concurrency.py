from __future__ import annotations

import multiprocessing
import os
from pathlib import Path

from pocket_lab_test_utils import ensure_runtime_path


def _reserve_worker(database: str, run_id: str, queue) -> None:
    os.environ["POCKETLAB_LITE_DB_PATH"] = database
    os.environ["POCKETLAB_LITE_SECURITY_ACTIVE_SCOPE"] = "global"
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    result = SecuritySQLiteRepository().reserve_scan(run_id=run_id, profile="quick")
    queue.put((result.reserved, result.reason, result.run.get("run_id")))


def test_lite_security_store_twenty_process_reservation_is_atomic(tmp_path):
    ensure_runtime_path()
    database = str(tmp_path / "state" / "pocketlab-lite.sqlite3")
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    processes = [
        context.Process(
            target=_reserve_worker,
            args=(database, f"security-{index:02d}", queue),
        )
        for index in range(20)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(60)
        assert process.exitcode == 0
    results = [queue.get(timeout=10) for _ in processes]
    assert sum(1 for reserved, _, _ in results if reserved) == 1
    assert sum(1 for _, reason, _ in results if reason == "active") == 19
    accepted_run_ids = {run_id for _, _, run_id in results}
    assert len(accepted_run_ids) == 1
