from pocket_lab_test_utils import client


def test_fleet_endpoints_registered():
    c = client()
    assert c.get("/api/fleet.json").status_code != 404
    assert c.get("/api/fleet/agents").status_code != 404
