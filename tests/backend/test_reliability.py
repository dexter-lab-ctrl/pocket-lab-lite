from pocket_lab_test_utils import client


def test_reliability_status_registered():
    assert client().get("/api/reliability/status").status_code != 404
