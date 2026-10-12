from pocket_lab_test_utils import ensure_runtime_path
ensure_runtime_path()
from api_fastapi.services import lite_home_activity_cursor as cursor
import pytest

def test_cursor_requires_human_id():
    with pytest.raises(ValueError):
        cursor.read_cursor("")
    with pytest.raises(ValueError):
        cursor.mark_reviewed("",1)

@pytest.mark.parametrize("revision",[-1,True,"1"])
def test_revision_must_be_integer(revision):
    with pytest.raises(ValueError):
        cursor.mark_reviewed("person",revision)

def test_review_cursor_is_durable_per_person(tmp_path, monkeypatch):
    from pocket_lab_test_utils import isolated_state_dir
    from api_fastapi.db.runtime import SQLITE_READS
    state=isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH",str(state / "lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR",str(state))
    SQLITE_READS.close()
    try:
        assert cursor.read_cursor("human-a")["history_revision"] == 0
        assert cursor.mark_reviewed("human-a",7)["history_revision"] == 7
        assert cursor.read_cursor("human-b")["history_revision"] == 0
        assert cursor.mark_reviewed("human-a",3)["history_revision"] == 7
        assert cursor.read_cursor("human-a")["last_reviewed_at"]
    finally:
        SQLITE_READS.close()

def test_authenticated_cursor_endpoints_use_server_revision(monkeypatch):
    import json
    from starlette.requests import Request
    from api_fastapi.routers import lite
    request=Request({"type":"http","method":"GET","path":"/api/lite/home/activity-cursor","headers":[]})
    monkeypatch.setattr(lite.deps,"require_auth",lambda *_args,**_kwargs:{
        "actor":{"type":"human","identity_id":"person-1"},
        "session":{"session_id":"session-1"},
    })
    monkeypatch.setattr(lite,"_home_activity_history_revision",lambda:9)
    monkeypatch.setattr(lite.lite_home_activity_cursor,"read_cursor",
                        lambda identity:{"history_revision":4,"last_reviewed_at":None})
    marker={}
    def review(identity,revision):
        marker.update(identity=identity,revision=revision)
        return {"history_revision":revision,"last_reviewed_at":"2026-10-12T00:00:00Z"}
    monkeypatch.setattr(lite.lite_home_activity_cursor,"mark_reviewed",review)
    before=lite.get_lite_home_activity_cursor(request)
    assert json.loads(before.body)["changed_since_review"] is True
    assert before.headers["cache-control"]=="private, no-store"
    after=lite.review_lite_home_activity(request)
    assert marker=={"identity":"person-1","revision":9}
    assert json.loads(after.body)["changed_since_review"] is False

def test_cursor_rejects_non_human_identity(monkeypatch):
    from fastapi import HTTPException
    from starlette.requests import Request
    from api_fastapi.routers import lite
    request=Request({"type":"http","method":"GET","path":"/api/lite/home/activity-cursor","headers":[]})
    monkeypatch.setattr(lite.deps,"require_auth",lambda *_args,**_kwargs:{
        "actor":{"type":"test","identity_id":"synthetic"},
        "session":{"session_id":"demo"},
    })
    with pytest.raises(HTTPException) as exc:
        lite.get_lite_home_activity_cursor(request)
    assert exc.value.status_code==403
