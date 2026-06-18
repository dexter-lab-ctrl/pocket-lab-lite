from pocket_lab_test_utils import client


def test_release_workflow_registered():
    assert client().get("/api/release/workflow").status_code != 404
