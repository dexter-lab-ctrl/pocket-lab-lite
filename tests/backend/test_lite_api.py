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

def test_lite_invite_uses_configured_public_base_url(monkeypatch):
    api = client()
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.10:8443")
    response = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "phone-two"},
    )
    assert response.status_code == 202
    invite = response.json()["invite"]
    assert invite["url"].startswith("http://100.64.0.10:8443/api/join.sh?")
    assert "127.0.0.1" not in invite["url"]


def test_lite_invite_autodetects_tailscale_ip_when_request_is_loopback(monkeypatch):
    api = client()
    from api_fastapi.services import lite_invites

    monkeypatch.delenv("POCKETLAB_LITE_INVITE_BASE_URL", raising=False)
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_PORT", "8443")
    monkeypatch.setattr(lite_invites, "_tailscale_ipv4", lambda: "100.64.0.20")
    monkeypatch.setattr(lite_invites, "_lan_ipv4", lambda: "192.168.1.20")

    response = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "storage", "hostname": "storage-phone"},
    )
    assert response.status_code == 202
    invite = response.json()["invite"]
    assert invite["url"].startswith("http://100.64.0.20:8443/api/join.sh?")
    assert "role=storage" in invite["url"]
    assert "127.0.0.1" not in invite["url"]


def test_lite_invite_falls_back_to_lan_ip_when_tailscale_unavailable(monkeypatch):
    api = client()
    from api_fastapi.services import lite_invites

    monkeypatch.delenv("POCKETLAB_LITE_INVITE_BASE_URL", raising=False)
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_PORT", "8443")
    monkeypatch.setattr(lite_invites, "_tailscale_ipv4", lambda: None)
    monkeypatch.setattr(lite_invites, "_lan_ipv4", lambda: "192.168.1.50")

    response = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "lan-phone"},
    )
    assert response.status_code == 202
    invite = response.json()["invite"]
    assert invite["url"].startswith("http://192.168.1.50:8443/api/join.sh?")
    assert "127.0.0.1" not in invite["url"]

def test_join_invite_browser_page_does_not_consume_token(monkeypatch):
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.30:8443")
    api = client()

    created = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "phone-two"},
    )
    assert created.status_code == 202
    invite_url = created.json()["invite"]["url"]
    path = invite_url.split("http://100.64.0.30:8443", 1)[1]

    page = api.get(path, headers={"accept": "text/html", "user-agent": "Mozilla/5.0"})
    assert page.status_code == 200
    assert "Pocket Lab Lite invite ready" in page.text
    assert "curl -fsSL" in page.text
    assert "phone-two" in page.text

    script = api.get(path, headers={"accept": "text/x-shellscript", "user-agent": "curl/8.0"})
    assert script.status_code == 200
    assert "text/x-shellscript" in script.headers.get("content-type", "")
    assert "POCKETLAB_AGENT_TOKEN" in script.text


def test_join_invite_shell_access_is_single_use(monkeypatch):
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.31:8443")
    api = client()

    created = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "storage", "hostname": "storage-phone"},
    )
    assert created.status_code == 202
    invite_url = created.json()["invite"]["url"]
    path = invite_url.split("http://100.64.0.31:8443", 1)[1]

    first = api.get(path, headers={"accept": "text/x-shellscript", "user-agent": "curl/8.0"})
    assert first.status_code == 200

    second = api.get(path, headers={"accept": "text/x-shellscript", "user-agent": "curl/8.0"})
    assert second.status_code == 410
    assert "already been used" in second.text

    browser_after_use = api.get(path, headers={"accept": "text/html", "user-agent": "Mozilla/5.0"})
    assert browser_after_use.status_code == 410
    assert "Invite already used" in browser_after_use.text

def test_lite_fleet_defaults_to_server_host_only_when_no_remote_devices(monkeypatch):
    api = client()
    from api_fastapi.services import lite_status

    monkeypatch.setattr(lite_status, "merged_fleet_nodes", lambda: [])
    monkeypatch.setenv("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server")

    response = api.get("/api/lite/fleet")
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    device = payload["devices"][0]
    assert device["name"] == "Pocket Lab Lite Server"
    assert device["role"] == "server_host"
    assert device["role_label"] == "Server Host"
    assert device["status"] == "healthy"
    assert device["last_seen"]


def test_lite_fleet_filters_dummy_and_deduplicates_invited_devices(monkeypatch):
    api = client()
    from api_fastapi.services import lite_status

    monkeypatch.setenv("POCKETLAB_DEVICE_NAME", "Pocket Lab Lite Server")
    monkeypatch.setattr(
        lite_status,
        "merged_fleet_nodes",
        lambda: [
            {"id": "pixel-edge-1", "name": "pixel-edge-1", "status": "active"},
            {"id": "localhost", "name": "localhost", "status": "active"},
            {"id": "samsung-nfs", "name": "Samsung-nfs", "status": "active", "isCurrent": True},
            {"id": "phone-two", "name": "phone-two", "role": "compute", "status": "invited", "created_at": "2026-06-19T10:00:00Z"},
            {"id": "phone-two", "name": "phone-two", "role": "compute", "status": "joining", "accepted_at": "2026-06-19T10:01:00Z"},
        ],
    )

    response = api.get("/api/lite/fleet")
    assert response.status_code == 200
    devices = response.json()["devices"]
    names = [item["name"] for item in devices]

    assert names.count("Pocket Lab Lite Server") == 1
    assert names.count("phone-two") == 1
    assert "pixel-edge-1" not in names
    assert "localhost" not in names
    assert "Samsung-nfs" not in names

    phone = next(item for item in devices if item["name"] == "phone-two")
    assert phone["status"] == "joining"
    assert phone["connection"] == "joining"
    assert phone["last_seen"]
