from pocket_lab_test_utils import client


def test_catalog_endpoint_registered():
    assert client().get("/api/catalog.json").status_code != 404
