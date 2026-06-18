from pocket_lab_test_utils import client


def test_drift_summary_registered():
    assert client().get("/api/drift/summary").status_code != 404
