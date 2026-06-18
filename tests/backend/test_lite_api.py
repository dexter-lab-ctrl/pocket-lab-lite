from pocket_lab_test_utils import client


def test_lite_status_endpoint_registered():
    response = client().get("/api/lite/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["device"]["mode"] == "lite"
    assert payload["overall"] in {"healthy", "degraded", "unhealthy"}
    assert isinstance(payload["services"], list)
    assert any(item["name"] == "Control API" for item in payload["services"])


def test_lite_catalog_endpoint_registered():
    response = client().get("/api/lite/catalog")
    assert response.status_code == 200
    payload = response.json()
    assert "items" in payload
    assert "count" in payload


def test_lite_read_summary_endpoints_registered():
    for path in (
        "/api/lite/identity",
        "/api/lite/security",
        "/api/lite/fleet",
        "/api/lite/policy",
        "/api/lite/recovery",
    ):
        response = client().get(path)
        assert response.status_code == 200, path
        assert isinstance(response.json(), dict)


def test_lite_write_endpoints_fail_closed_or_queue_without_local_fallback():
    checks = [
        ("/api/lite/security/scan", {"scope": "local"}),
        ("/api/lite/fleet/add-device", {"role": "compute", "hostname": "test-node"}),
        ("/api/lite/recovery/backup", {"dry_run": True}),
    ]
    for path, body in checks:
        response = client().post(path, json=body)
        assert response.status_code in {200, 202, 403, 503}, path
        assert "local fallback" not in response.text.lower()


def test_lite_restore_requires_confirmation():
    response = client().post("/api/lite/recovery/restore", json={"backup_ref": "latest"})
    assert response.status_code == 409
    assert "confirmation_required" in response.text


def test_lite_catalog_remove_does_not_overclaim():
    response = client().post("/api/lite/catalog/remove", json={"app_id": "demo", "confirm": True})
    assert response.status_code == 501
    payload = response.json()
    assert payload["status"] == "not_implemented"


def test_lite_add_device_invite_ready_or_queued_for_compute_role():
    response = client().post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "Kitchen tablet"},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["status"] in {"queued", "invite_ready"}
    if payload["status"] == "invite_ready":
        invite = payload["invite"]
        assert invite["role"] == "compute"
        assert invite["role_label"] == "App Host"
        assert invite.get("url") or invite.get("copy_text")
        assert invite.get("expires_at")


def test_lite_add_device_invite_ready_or_queued_for_storage_role():
    response = client().post(
        "/api/lite/fleet/add-device",
        json={"role": "storage", "hostname": "Backup phone"},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["status"] in {"queued", "invite_ready"}
    if payload["status"] == "invite_ready":
        invite = payload["invite"]
        assert invite["role"] == "storage"
        assert invite["role_label"] == "Storage Node"
        assert invite.get("url") or invite.get("copy_text")
        assert invite.get("expires_at")


def test_lite_add_device_rejects_invalid_role():
    response = client().post(
        "/api/lite/fleet/add-device",
        json={"role": "control", "hostname": "unsupported"},
    )
    assert response.status_code == 422


def test_lite_add_device_invite_response_avoids_raw_secret_internals():
    response = client().post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "Office tablet"},
    )
    assert response.status_code == 202
    payload = response.json()
    text = response.text.lower()
    assert "tailscale_api_key" not in text
    assert "tailscale api key" not in text
    assert "tailnet token" not in text
    assert "nats_password" not in text
    assert "nats password" not in text
    assert "jetstream" not in text
    if payload["status"] == "invite_ready":
        invite = payload["invite"]
        assert invite.get("expires_at")
        assert invite.get("token_hint")
        assert "token_hash" not in invite
        assert "agent_token" not in invite


def test_lite_fleet_returns_role_metadata_and_latest_invite_without_raw_token_hash():
    client().post(
        "/api/lite/fleet/add-device",
        json={"role": "storage", "hostname": "Backup shelf"},
    )
    response = client().get("/api/lite/fleet")
    assert response.status_code == 200
    payload = response.json()
    roles = {item["role"]: item for item in payload.get("roles", [])}
    assert roles["compute"]["role_label"] == "App Host"
    assert roles["storage"]["role_label"] == "Storage Node"
    latest = payload.get("latest_invite")
    assert latest is None or "token_hash" not in latest


def test_lite_devices_ui_does_not_expose_raw_invite_internals():
    from pathlib import Path

    ui = Path("src/lite/LiteApp.jsx").read_text()
    forbidden = [
        "Tailscale API key",
        "tailnet token",
        "NATS",
        "JetStream",
        "fleet_join",
        "node agent",
    ]
    for term in forbidden:
        assert term not in ui
