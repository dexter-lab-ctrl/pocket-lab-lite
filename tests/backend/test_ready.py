from pocket_lab_test_utils import client


def test_ready_endpoint_registered():
    response = client().get("/ready")
    assert response.status_code != 404


def test_health_endpoint_registered():
    response = client().get("/health")
    assert response.status_code != 404
