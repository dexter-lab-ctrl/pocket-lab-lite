from pocket_lab_test_utils import client


def test_nats_status_endpoint_registered():
    response = client().get("/api/nats/status")
    assert response.status_code != 404


def test_nats_required_mode_does_not_use_legacy_local_fallback(monkeypatch):
    monkeypatch.setenv("POCKETLAB_NATS_REQUIRED", "1")
    monkeypatch.setenv("POCKETLAB_NATS_REQUIRE_JETSTREAM", "1")
    response = client().post(
        "/api/operations/execute", json={"operation": "git_sync", "target": "repo"}
    )
    assert response.status_code in {200, 202, 403, 503}
    assert "local fallback" not in response.text.lower()
