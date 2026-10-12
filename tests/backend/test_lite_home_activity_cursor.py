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
