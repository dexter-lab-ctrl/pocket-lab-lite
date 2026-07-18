from __future__ import annotations


def test_restore_progress_reset_replaces_monotonic_snapshot_and_requests_reader_reconnect(monkeypatch):
    from api_fastapi.services import lite_security

    class Repo:
        def get_progress(self):
            return {
                "run_id": "restored-run",
                "status": "succeeded",
                "percent": 100,
                "requested_at_epoch_ms": 1000,
                "completed_at_epoch_ms": 2000,
            }

    published = {}

    def fake_publish(payload, *, verified, enforce_monotonic=True):
        published.update({
            "payload": payload,
            "verified": verified,
            "enforce_monotonic": enforce_monotonic,
        })
        return dict(payload), True

    monkeypatch.setattr(lite_security, "_publish_sqlite_progress", fake_publish)
    lite_security._SQLITE_PROGRESS_READER_RESET.clear()
    lite_security._SQLITE_PROGRESS_DIRTY.clear()

    result = lite_security.reset_security_progress_after_database_restore(repository=Repo())

    assert published["verified"] is True
    assert published["enforce_monotonic"] is False
    assert result["run_id"] == "restored-run"
    assert result["scan_status"] == "succeeded"
    assert result["active_scan"] is False
    assert result["reader_reconnect_requested"] is True
    assert lite_security._SQLITE_PROGRESS_READER_RESET.is_set()
    assert lite_security._SQLITE_PROGRESS_DIRTY.is_set()
