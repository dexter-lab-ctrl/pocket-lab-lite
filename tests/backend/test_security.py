from pocket_lab_test_utils import client


def test_security_and_opa_endpoints_registered():
    c = client()
    assert c.get("/api/opa_evaluations.json").status_code != 404
    assert c.get("/api/logs/query").status_code != 404
    assert c.get("/loki/api/v1/query").status_code != 404
