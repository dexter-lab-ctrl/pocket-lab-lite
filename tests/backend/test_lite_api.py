import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


@pytest.fixture(autouse=True)
def isolate_lite_runtime_state_per_test(tmp_path):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    yield


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
        assert invite.get("bootstrap_url")
        assert invite.get("bootstrap_command")
        assert invite.get("copy_text") == invite.get("bootstrap_command")
        assert payload.get("copy_text") == payload.get("bootstrap_command")
        assert "curl -fsSL" in invite.get("copy_text")
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
        assert invite.get("bootstrap_url")
        assert invite.get("bootstrap_command")
        assert invite.get("copy_text") == invite.get("bootstrap_command")
        assert "curl -fsSL" in invite.get("copy_text")
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

def test_join_sh_returns_non_empty_script_and_marks_joining(monkeypatch):
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.60:8443")
    api = client()

    created = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "phone-join-script"},
    )
    assert created.status_code == 202

    invite_url = created.json()["invite"]["url"]
    script_path = invite_url.split("http://100.64.0.60:8443", 1)[1]
    script_path = script_path.replace("/api/join?", "/api/join.sh?", 1)

    response = api.get(
        script_path,
        headers={"accept": "*/*", "user-agent": "curl/termux"},
    )

    assert response.status_code == 200
    assert "text/x-shellscript" in response.headers.get("content-type", "")
    assert len(response.text.strip()) > 100
    assert "Pocket Lab Lite device join" in response.text
    assert 'POCKETLAB_NODE_ID="phone-join-script"' in response.text
    assert ".pocketlab-lite-agent.env" in response.text

    fleet = api.get("/api/lite/fleet")
    assert fleet.status_code == 200
    devices = fleet.json()["devices"]
    matching = [
        item for item in devices
        if item.get("id") == "phone-join-script" or item.get("name") == "phone-join-script"
    ]
    assert matching
    assert matching[0]["connection"] == "joining"


def test_join_sh_reuse_is_rejected_after_consumption(monkeypatch):
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.61:8443")
    api = client()

    created = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "storage", "hostname": "phone-single-use"},
    )
    assert created.status_code == 202

    invite_url = created.json()["invite"]["url"]
    script_path = invite_url.split("http://100.64.0.61:8443", 1)[1]
    script_path = script_path.replace("/api/join?", "/api/join.sh?", 1)

    first = api.get(script_path, headers={"accept": "*/*", "user-agent": "curl/termux"})
    assert first.status_code == 200
    assert len(first.text.strip()) > 100

    second = api.get(script_path, headers={"accept": "*/*", "user-agent": "curl/termux"})
    assert second.status_code == 410


def test_lite_bootstrap_script_uses_request_host_for_public_nats_url(monkeypatch):
    monkeypatch.delenv("POCKETLAB_LITE_PUBLIC_NATS_URL", raising=False)
    monkeypatch.delenv("POCKETLAB_PUBLIC_NATS_URL", raising=False)
    monkeypatch.delenv("POCKETLAB_LITE_NATS_URL", raising=False)
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.80:8443")
    monkeypatch.setenv("POCKETLAB_LITE_NATS_PORT", "4222")

    api = client()
    created = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "phone-public-nats"},
    )
    assert created.status_code == 202
    invite = created.json()["invite"]
    bootstrap_url = invite.get("bootstrap_url") or invite["url"].replace(
        "/api/join.sh?", "/api/lite/fleet/agent/bootstrap.sh?", 1
    ).replace("/api/join?", "/api/lite/fleet/agent/bootstrap.sh?", 1)
    script_path = bootstrap_url.split("http://100.64.0.80:8443", 1)[1]

    response = api.get(
        script_path,
        headers={
            "host": "100.64.0.80:8443",
            "accept": "*/*",
            "user-agent": "curl/termux",
        },
    )

    assert response.status_code == 200
    assert "text/x-shellscript" in response.headers.get("content-type", "")
    assert 'export POCKETLAB_NATS_URL="nats://100.64.0.80:4222"' in response.text
    assert 'export POCKETLAB_NATS_URL="nats://127.0.0.1:4222"' not in response.text


def test_lite_bootstrap_script_prefers_explicit_public_nats_url(monkeypatch):
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.81:8443")
    monkeypatch.setenv("POCKETLAB_LITE_PUBLIC_NATS_URL", "nats://100.64.0.99:4222")

    api = client()
    created = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "storage", "hostname": "phone-explicit-nats"},
    )
    assert created.status_code == 202
    invite = created.json()["invite"]
    bootstrap_url = invite.get("bootstrap_url") or invite["url"].replace(
        "/api/join.sh?", "/api/lite/fleet/agent/bootstrap.sh?", 1
    ).replace("/api/join?", "/api/lite/fleet/agent/bootstrap.sh?", 1)
    script_path = bootstrap_url.split("http://100.64.0.81:8443", 1)[1]

    response = api.get(
        script_path,
        headers={"host": "100.64.0.81:8443", "accept": "*/*", "user-agent": "curl/termux"},
    )

    assert response.status_code == 200
    assert 'export POCKETLAB_NATS_URL="nats://100.64.0.99:4222"' in response.text



def test_lite_fleet_stale_agent_renders_offline_connection(tmp_path, monkeypatch):
    from api_fastapi import deps
    from api_fastapi.services import fleet_registry

    isolated_state_dir(tmp_path)
    fleet_registry.upsert_agent(
        {
            "node_id": "stale-phone",
            "hostname": "Stale Phone",
            "role": "compute",
            "status": "online",
        },
        event_type="fleet.node_heartbeat",
    )

    state_path = fleet_registry._state_path("fleet_agents.json")
    state = deps.core.read_json_file(state_path, {})
    assert "agents" in state
    state["agents"]["stale-phone"]["last_seen_epoch"] = 1
    state["agents"]["stale-phone"]["last_seen_at"] = "2026-01-01T00:00:00Z"
    deps.core.write_json_file(state_path, state)

    response = client().get("/api/lite/fleet")
    assert response.status_code == 200
    payload = response.json()
    device = next(item for item in payload["devices"] if item["id"] == "stale-phone")
    assert device["connection"] == "offline"


def test_lite_restart_agent_endpoint_queues_command(tmp_path, monkeypatch):
    from api_fastapi import deps
    from api_fastapi.services import fleet_registry

    isolated_state_dir(tmp_path)
    fleet_registry.upsert_agent(
        {
            "node_id": "restart-phone",
            "hostname": "Restart Phone",
            "role": "compute",
            "status": "online",
        },
        event_type="fleet.node_heartbeat",
    )

    response = client().post(
        "/api/lite/fleet/devices/restart-phone/restart-agent",
        json={"reason": "test restart"},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["node_id"] == "restart-phone"
    assert payload["command_id"]

    state_path = fleet_registry._state_path("fleet_agent_commands.json")
    commands = deps.core.read_json_file(state_path, {})
    assert "commands" in commands
    assert commands["commands"][0]["command"] == "agent.restart"
    assert commands["commands"][0]["node_id"] == "restart-phone"



def _use_isolated_runtime_state(tmp_path):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    return state, deps


def test_lite_remove_joining_device_succeeds_and_fleet_no_longer_includes_it(tmp_path):
    from api_fastapi.services import fleet_registry

    _use_isolated_runtime_state(tmp_path)
    fleet_registry.upsert_agent(
        {
            "node_id": "old-phone",
            "hostname": "Old Phone",
            "role": "compute",
            "status": "joining",
        },
        event_type="fleet.agent_join_started",
    )

    api = client()
    before = api.get("/api/lite/fleet")
    assert before.status_code == 200
    assert any(item["id"] == "old-phone" for item in before.json()["devices"])

    response = api.post(
        "/api/lite/fleet/remove-device",
        json={"device_id": "old-phone", "confirm": True, "reason": "Old test device cleanup"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "removed"
    assert payload["device_id"] == "old-phone"
    assert payload["removed_device_records"] >= 1
    assert payload["message"] == "Old device record removed."

    after = api.get("/api/lite/fleet")
    assert after.status_code == 200
    assert all(item["id"] != "old-phone" for item in after.json()["devices"])


def test_lite_remove_device_cleans_matching_latest_invite(tmp_path, monkeypatch):
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.70:8443")
    _use_isolated_runtime_state(tmp_path)

    api = client()
    created = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "Test Phone 5"},
    )
    assert created.status_code == 202
    assert created.json()["status"] == "invite_ready"
    assert api.get("/api/lite/fleet").json().get("latest_invite") is not None

    response = api.post(
        "/api/lite/fleet/remove-device",
        json={"device_id": "test-phone-5", "confirm": True, "reason": "Old test device cleanup"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["removed_invite_records"] == 1
    assert api.get("/api/lite/fleet").json().get("latest_invite") is None


def test_lite_remove_device_requires_confirm_true(tmp_path):
    from api_fastapi.services import fleet_registry

    _use_isolated_runtime_state(tmp_path)
    fleet_registry.upsert_agent(
        {"node_id": "confirm-phone", "hostname": "Confirm Phone", "role": "compute", "status": "joining"},
        event_type="fleet.agent_join_started",
    )

    response = client().post(
        "/api/lite/fleet/remove-device",
        json={"device_id": "confirm-phone", "confirm": False},
    )

    assert response.status_code == 400
    assert "Confirm removal" in response.text


def test_lite_remove_unknown_device_returns_404(tmp_path):
    _use_isolated_runtime_state(tmp_path)

    response = client().post(
        "/api/lite/fleet/remove-device",
        json={"device_id": "missing-phone", "confirm": True},
    )

    assert response.status_code == 404


def test_lite_remove_server_host_is_blocked(tmp_path):
    _use_isolated_runtime_state(tmp_path)

    response = client().post(
        "/api/lite/fleet/remove-device",
        json={"device_id": "pocket-lab-lite-server", "confirm": True},
    )

    assert response.status_code == 409
    assert "server" in response.text.lower()


def test_lite_remove_is_current_device_is_blocked(tmp_path):
    from api_fastapi import deps

    _use_isolated_runtime_state(tmp_path)
    deps.core.write_json_file(
        deps.settings().state_dir / "fleet.json",
        [
            {
                "id": "current-phone",
                "name": "Current Phone",
                "role": "compute",
                "status": "joining",
                "is_current": True,
            }
        ],
    )

    response = client().post(
        "/api/lite/fleet/remove-device",
        json={"device_id": "current-phone", "confirm": True},
    )

    assert response.status_code == 409
    assert "current" in response.text.lower()


def test_lite_remove_online_healthy_device_is_protected(tmp_path):
    from api_fastapi.services import fleet_registry

    _use_isolated_runtime_state(tmp_path)
    fleet_registry.upsert_agent(
        {
            "node_id": "online-phone",
            "hostname": "Online Phone",
            "role": "compute",
            "status": "online",
        },
        event_type="fleet.node_heartbeat",
    )

    response = client().post(
        "/api/lite/fleet/remove-device",
        json={"device_id": "online-phone", "confirm": True},
    )

    assert response.status_code == 409
    assert "Online devices are protected" in response.text


def test_lite_remove_device_writes_audit_evidence(tmp_path):
    from api_fastapi import deps
    from api_fastapi.services import fleet_registry

    _use_isolated_runtime_state(tmp_path)
    fleet_registry.upsert_agent(
        {"node_id": "audit-phone", "hostname": "Audit Phone", "role": "compute", "status": "joining"},
        event_type="fleet.agent_join_started",
    )

    response = client().post(
        "/api/lite/fleet/remove-device",
        json={"device_id": "audit-phone", "confirm": True, "reason": "Old test device cleanup"},
    )

    assert response.status_code == 200
    audit = deps.core.read_json_file(deps.settings().state_dir / "fleet_device_audit.json", {})
    assert audit["events"][0]["event_type"] == "lite.audit.fleet.device_removed"
    assert audit["events"][0]["device_id"] == "audit-phone"
    assert audit["events"][0]["reason"] == "Old test device cleanup"


def test_lite_add_device_rejects_duplicate_existing_device_name(tmp_path):
    from api_fastapi.services import fleet_registry

    _use_isolated_runtime_state(tmp_path)
    fleet_registry.upsert_agent(
        {
            "node_id": "kitchen-tablet",
            "hostname": "Kitchen Tablet",
            "role": "compute",
            "status": "joining",
        },
        event_type="fleet.agent_join_started",
    )

    response = client().post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "Kitchen Tablet"},
    )

    assert response.status_code == 409
    detail = response.json()
    assert detail["status"] == "duplicate_device"
    assert detail["summary"] == "A device with this name already exists."
    assert detail["existing_device"]["device_id"] == "kitchen-tablet"
    assert "token_hash" not in response.text
    assert "token=" not in response.text


def test_lite_add_device_duplicate_matching_is_case_and_separator_insensitive(tmp_path):
    from api_fastapi.services import fleet_registry

    _use_isolated_runtime_state(tmp_path)
    fleet_registry.upsert_agent(
        {
            "node_id": "test-phone-9",
            "hostname": "Test Phone 9",
            "role": "compute",
            "status": "joining",
        },
        event_type="fleet.agent_join_started",
    )

    for duplicate_name in ("test-phone-9", "TEST PHONE 9", "test_phone_9"):
        response = client().post(
            "/api/lite/fleet/add-device",
            json={"role": "compute", "hostname": duplicate_name},
        )
        assert response.status_code == 409
        assert response.json()["status"] == "duplicate_device"


def test_lite_add_device_rejects_duplicate_active_invite_name(tmp_path, monkeypatch):
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.71:8443")
    _use_isolated_runtime_state(tmp_path)

    api = client()
    first = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "storage", "hostname": "Backup Phone"},
    )
    assert first.status_code == 202

    second = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "storage", "hostname": "backup-phone"},
    )

    assert second.status_code == 409
    detail = second.json()
    assert detail["status"] == "duplicate_device"
    assert detail["existing_device"]["source"] in {"fleet_agents.json", "fleet_invites.json"}


def test_lite_add_device_rejects_server_host_name_reuse(tmp_path):
    _use_isolated_runtime_state(tmp_path)

    response = client().post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "Pocket Lab Lite Server"},
    )

    assert response.status_code == 409
    detail = response.json()
    assert detail["status"] == "duplicate_device"
    assert detail["existing_device"]["role"] == "server_host"
    assert detail["existing_device"]["can_remove_old_record"] is False


def test_lite_add_device_allows_unique_device_name(tmp_path):
    _use_isolated_runtime_state(tmp_path)

    response = client().post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "Unique Device Name"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "invite_ready"

def _token_from_url(value: str) -> str:
    from urllib.parse import parse_qs, urlparse

    return parse_qs(urlparse(value).query)["token"][0]


def test_lite_bootstrap_script_blocks_mismatched_existing_identity_before_accept(monkeypatch):
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.90:8443")
    api = client()
    created = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "Kitchen Tablet 2"},
    )
    assert created.status_code == 202
    bootstrap_url = created.json()["invite"]["bootstrap_url"]
    script_path = bootstrap_url.split("http://100.64.0.90:8443", 1)[1]

    response = api.get(script_path, headers={"accept": "*/*", "user-agent": "curl/termux"})

    assert response.status_code == 200
    assert "This phone is already connected as:" in response.text
    assert "The Pocket Lab agent was not restarted." in response.text
    assert "POCKETLAB_LITE_ALLOW_REJOIN=1" in response.text
    assert "/api/lite/fleet/agent/bootstrap.env" in response.text
    assert "/api/lite/fleet/agent/bootstrap-blocked" in response.text


def test_lite_bootstrap_script_preview_does_not_consume_invite(monkeypatch):
    from api_fastapi.services import lite_invites

    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.91:8443")
    api = client()
    created = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "Preview Guard Phone"},
    )
    assert created.status_code == 202
    invite = created.json()["invite"]
    token = _token_from_url(invite["bootstrap_url"])
    script_path = invite["bootstrap_url"].split("http://100.64.0.91:8443", 1)[1]

    response = api.get(script_path, headers={"accept": "*/*", "user-agent": "curl/termux"})

    assert response.status_code == 200
    status, _record = lite_invites.invite_token_status(token, role="compute")
    assert status == "valid"


def test_lite_bootstrap_blocked_records_audit_without_consuming_invite(monkeypatch):
    from api_fastapi import deps
    from api_fastapi.services import lite_invites

    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.92:8443")
    api = client()
    created = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "Wrong Phone Invite"},
    )
    assert created.status_code == 202
    token = _token_from_url(created.json()["invite"]["bootstrap_url"])

    blocked = api.post(
        "/api/lite/fleet/agent/bootstrap-blocked",
        json={
            "role": "compute",
            "token": token,
            "existing_node_id": "secondary-phone8-test",
            "existing_node_name": "Secondary-Phone8-Test",
            "intended_node_id": "wrong-phone-invite",
            "intended_node_name": "Wrong Phone Invite",
        },
    )

    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"
    status, _record = lite_invites.invite_token_status(token, role="compute")
    assert status == "valid"
    audit = deps.core.read_json_file(deps.settings().state_dir / "fleet_invite_audit.json", {})
    assert audit["events"][0]["event_type"] == "pocketlab.audit.fleet.bootstrap_blocked"
    assert audit["events"][0]["existing_node_id"] == "secondary-phone8-test"


def test_lite_bootstrap_accept_consumes_invite_and_returns_env(monkeypatch):
    monkeypatch.setenv("POCKETLAB_LITE_INVITE_BASE_URL", "http://100.64.0.93:8443")
    monkeypatch.setenv("POCKETLAB_LITE_PUBLIC_NATS_URL", "nats://100.64.0.93:4222")
    api = client()
    created = api.post(
        "/api/lite/fleet/add-device",
        json={"role": "storage", "hostname": "Accepted Guard Phone"},
    )
    assert created.status_code == 202
    token = _token_from_url(created.json()["invite"]["bootstrap_url"])

    accepted = api.post(
        "/api/lite/fleet/agent/bootstrap.env",
        json={"role": "storage", "token": token},
        headers={"host": "100.64.0.93:8443"},
    )

    assert accepted.status_code == 200
    assert 'export POCKETLAB_NODE_ID="accepted-guard-phone"' in accepted.text
    assert 'export POCKETLAB_NATS_URL="nats://100.64.0.93:4222"' in accepted.text

    reused = api.post(
        "/api/lite/fleet/agent/bootstrap.env",
        json={"role": "storage", "token": token},
    )
    assert reused.status_code == 410

def test_lite_restart_agent_returns_progress_steps(tmp_path):
    from api_fastapi.services import fleet_registry

    _use_isolated_runtime_state(tmp_path)
    fleet_registry.upsert_agent(
        {
            "node_id": "progress-phone",
            "hostname": "Progress Phone",
            "role": "compute",
            "status": "online",
        },
        event_type="fleet.node_heartbeat",
    )

    response = client().post(
        "/api/lite/fleet/devices/progress-phone/restart-agent",
        json={"reason": "test restart progress"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["command_id"]
    assert payload["progress"]["steps"]
    assert payload["progress"]["steps"][0]["id"] == "request_saved"
    assert payload["poll_url"].endswith(payload["command_id"])


def test_lite_restart_agent_status_reports_command_progress(tmp_path):
    from api_fastapi.services import fleet_registry

    _use_isolated_runtime_state(tmp_path)
    fleet_registry.upsert_agent(
        {
            "node_id": "status-phone",
            "hostname": "Status Phone",
            "role": "compute",
            "status": "online",
        },
        event_type="fleet.node_heartbeat",
    )
    queued = client().post(
        "/api/lite/fleet/devices/status-phone/restart-agent",
        json={"reason": "status check"},
    )
    assert queued.status_code == 202
    command_id = queued.json()["command_id"]

    response = client().get(
        f"/api/lite/fleet/devices/status-phone/restart-agent/status?command_id={command_id}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["command_id"] == command_id
    assert payload["progress"]["steps"][1]["id"] == "private_channel"
    assert payload["progress"]["status"] in {"waiting", "completed"}

def test_lite_fleet_reports_remote_access_not_ready_when_tailscale_down(monkeypatch):
    from api_fastapi.services import lite_status

    monkeypatch.setattr(lite_status, "_tailscaled_running", lambda: False)
    monkeypatch.setattr(lite_status, "_tailscale_ipv4_status", lambda: None)
    monkeypatch.setattr(lite_status, "_nats_reachable_on_host", lambda host: False)
    monkeypatch.setattr(lite_status, "merged_fleet_nodes", lambda: [])

    response = client().get("/api/lite/fleet")

    assert response.status_code == 200
    payload = response.json()
    assert payload["remote_access"]["status"] == "unavailable"
    assert payload["remote_access"]["ip"] is None
    assert "Remote access not ready" in payload["remote_access"]["summary"]
    server = payload["devices"][0]
    assert server["role"] == "server_host"
    assert server["tailnet_ip"] is None
    assert server["remote_access_status"] == "unavailable"


def test_lite_fleet_reports_tailscale_ip_only_when_remote_access_ready(monkeypatch):
    from api_fastapi.services import lite_status

    monkeypatch.setattr(lite_status, "_tailscaled_running", lambda: True)
    monkeypatch.setattr(lite_status, "_tailscale_ipv4_status", lambda: "100.13.7.11")
    monkeypatch.setattr(lite_status, "_nats_reachable_on_host", lambda host: host == "100.13.7.11")
    monkeypatch.setattr(lite_status, "merged_fleet_nodes", lambda: [])

    response = client().get("/api/lite/fleet")

    assert response.status_code == 200
    payload = response.json()
    assert payload["remote_access"]["status"] == "healthy"
    assert payload["remote_access"]["ip"] == "100.13.7.11"
    server = payload["devices"][0]
    assert server["tailnet_ip"] == "100.13.7.11"
    assert server["remote_access"] is True
