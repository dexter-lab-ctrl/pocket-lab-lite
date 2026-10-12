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
