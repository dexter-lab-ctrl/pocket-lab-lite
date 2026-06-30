from pathlib import Path

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


def _lite_ui_source() -> str:
    return "\n".join(
        path.read_text()
        for path in sorted(Path("src/lite").glob("Lite*.jsx"))
    )


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
    assert "apps" in payload
    assert "access" in payload
    assert "count" in payload
    app = payload["apps"][0]
    assert app["id"] == "photoprism"
    assert app["name"] == "PhotoPrism"
    assert app["category"] == "Photos"
    assert app["target"]["default_node_id"] == "pocket-lab-lite-server"
    assert app["target"]["supported_roles"] == ["server"]
    assert app["actions"]["install"] is True
    assert app["actions"]["remove"] is False
    assert app["runtime"]["route"] == "/apps/photoprism/"
    assert app["access"]["open_url"] is None
    assert "key" not in response.text.lower()
    assert "password" not in response.text.lower()


def test_lite_catalog_install_validates_app_and_target_before_queue():
    unknown = client().post("/api/lite/catalog/install", json={"app_id": "vault"})
    assert unknown.status_code == 400
    assert "PhotoPrism" in unknown.text

    remote = client().post("/api/lite/catalog/install", json={"app_id": "photoprism", "target_node_id": "other-device"})
    assert remote.status_code == 409
    assert "Server Host" in remote.text


def test_lite_catalog_worker_subject_registered():
    ensure_runtime_path()
    from api_fastapi.services import domain_commands, lite_catalog

    assert lite_catalog.COMMAND_SUBJECT in domain_commands.supported_subjects()


def test_lite_catalog_ui_is_https_aware_and_server_owned():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()

    assert "PhotoPrism" in ui
    assert "Secure access ready" in ui
    assert "Remote access not ready" in ui
    assert "Server Host" in ui
    assert "target_node_id" in ui
    assert "lite-catalog-progress" in ui
    assert "lite-catalog-launcher" not in ui
    assert "lite-catalog-launcher" not in css
    assert "lite-catalog-drawer" not in ui
    assert "lite-catalog-drawer" not in css
    assert "Details" not in Path("src/lite/LiteCatalog.jsx").read_text()
    assert "Ready to open" not in ui
    assert "Ready to open" not in css
    assert ">Ready<" in ui or "'Ready'" in ui
    assert "Open full screen" in ui
    assert "lite-home-pill lite-catalog-hero-pill is-secure" in ui
    assert "Remove" not in Path("src/lite/LiteCatalog.jsx").read_text()
    assert "lite-catalog-access-card" in css
    assert "HeartPulse" in Path("src/lite/LiteCatalog.jsx").read_text()
    assert "Clock3" not in Path("src/lite/LiteCatalog.jsx").read_text()
    assert "lite-catalog-status-badge" in ui
    assert "lite-catalog-trust-marker" in ui
    assert "Self-hosted app" in ui
    assert "/assets/apps/photoprism.svg" in ui
    assert Path("public/assets/apps/photoprism.svg").exists()
    assert "lite-catalog-hero-actions" in ui
    assert "lite-catalog-hero-actions" in css
    assert "lite-catalog-attention-reason" in ui
    assert "Open is not ready yet. Pocket Lab is still checking the app route." in ui
    assert "No apps installed yet" in ui
    assert "lite-catalog-empty-state" in ui
    assert "lite-catalog-actions" in css
    assert "has-phone-install" in ui
    assert "has-phone-install" in css
    assert "Install to phone" in ui
    assert "canInstallAppToPhone" in ui
    assert "Use your browser menu to install it on this phone." in ui
    assert "Smartphone" in Path("src/lite/LiteCatalog.jsx").read_text()
    assert "Add to phone" not in ui
    assert "isStandalonePwa" in ui
    assert "navigator.vibrate" in ui


def test_lite_caddy_generator_supports_app_route_registry():
    script = Path("pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh").read_text()

    assert "write_caddy_app_routes" in script
    assert "handle {path}*" in script
    assert "handle_path {path}*" not in script
    assert "POCKETLAB_LITE_APP_ROUTES" in script
    assert "--caddy-only" in script
    assert "caddy validate --config" in script
    assert "tailscale-status.XXXXXX.json" in script


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

    ui = _lite_ui_source()
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


def test_lite_bootstrap_script_starts_local_supervisor(monkeypatch):
    monkeypatch.setenv("POCKETLAB_LITE_PUBLIC_NATS_URL", "nats://100.64.0.91:4222")
    created = client().post(
        "/api/lite/fleet/add-device",
        json={"role": "compute", "hostname": "Supervisor Phone"},
    )
    assert created.status_code == 202
    token = _token_from_url(created.json()["invite"]["bootstrap_url"])

    script = client().get(f"/api/lite/fleet/agent/bootstrap.sh?role=compute&token={token}")

    assert script.status_code == 200
    assert "pocketlab_agent_supervisor.py" in script.text
    assert "pocketlab-agent-supervisor-$POCKETLAB_NODE_ID" in script.text
    assert "not str(p.get(\"name\",\"\")).startswith(\"pocketlab-agent-supervisor-\")" in script.text


def test_lite_fleet_marks_supervisor_reported_stopped_agent(tmp_path):
    from api_fastapi.services import fleet_registry

    _use_isolated_runtime_state(tmp_path)
    fleet_registry.upsert_agent(
        {
            "node_id": "stopped-phone",
            "hostname": "Stopped Phone",
            "role": "compute",
            "status": "agent_stopped",
            "agent_process_status": "stopped",
            "supervisor_status": "healthy",
            "repair_count": 2,
            "checked_at": "2026-06-22T10:00:00Z",
        },
        event_type="fleet.node_supervisor",
    )

    response = client().get("/api/lite/fleet")

    assert response.status_code == 200
    payload = response.json()
    device = next(item for item in payload["devices"] if item["id"] == "stopped-phone")
    assert device["status"] == "agent_stopped"
    assert device["connection"] == "stopped"
    assert device["agent_process_status"] == "stopped"
    assert device["supervisor_status"] == "healthy"
    assert device["supervisor_repair_count"] == 2


def test_lite_restart_agent_reports_stopped_agent_progress(tmp_path):
    from api_fastapi.services import fleet_registry

    _use_isolated_runtime_state(tmp_path)
    fleet_registry.upsert_agent(
        {
            "node_id": "stopped-progress-phone",
            "hostname": "Stopped Progress Phone",
            "role": "compute",
            "status": "agent_stopped",
            "agent_process_status": "stopped",
            "supervisor_status": "repairing",
            "repair_count": 1,
            "checked_at": "2026-06-22T10:00:00Z",
        },
        event_type="fleet.node_supervisor",
    )

    response = client().post(
        "/api/lite/fleet/devices/stopped-progress-phone/restart-agent",
        json={"reason": "stopped agent test"},
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["delivery"] in {"agent_stopped", "supervisor_repairing"}
    assert payload["progress"]["status"] in {"agent_stopped", "repairing"}
    step_ids = [step["id"] for step in payload["progress"]["steps"]]
    assert "local_supervisor" in step_ids
    assert "device_agent" in step_ids



def test_lite_security_ui_has_confidence_trust_boundary_and_coverage_matrix():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    mocks = Path("src/mocks/handlers.js").read_text()

    assert "deriveSecurityConfidence" in ui
    assert "Confidence: High" in ui
    assert "Confidence: Medium" in ui
    assert "Confidence: Low" in ui
    assert "Both Lynis and Trivy completed. Evidence and SBOM were saved." in ui
    assert "You are protected because" in ui
    assert "Browser never runs shell commands" in ui
    assert "Browser to evidence path" in ui
    assert "The browser only requests checks and displays summaries." in ui
    assert "Coverage: 7 protected areas" in ui
    assert "SecurityCoverageMatrixCard" in ui
    assert "aria-expanded" in ui
    assert "not covered by this check" in ui
    assert "lite-security-confidence-card" in css
    assert "lite-security-boundary-flow" in css
    assert "lite-security-coverage-scroll" in css
    assert "security-partial" in mocks
    assert "security-low" in mocks


def test_lite_app_workspace_fails_closed_when_apps_are_not_embeddable():
    ui = _lite_ui_source()

    assert "appWorkspaceEmbedAllowed" in ui
    assert "item?.embedAllowed === true" in ui
    assert "access.embed_allowed === true" in ui
    assert "runtime.embed_allowed === true" in ui
    assert "This app opens full screen for safety." in ui
    assert "preserved the app's own security settings" in ui
    assert "setFrameFallback(true)" in ui
    assert "showFrame" in ui


def test_lite_ui_has_error_boundary_and_safe_restart_steps():
    ui = _lite_ui_source()
    assert "LiteErrorBoundary" in ui
    assert "Pocket Lab needs a moment" in ui
    assert "safeRestartSteps" in ui
    assert "Device agent is stopped" in ui


def test_lite_devices_ui_has_enterprise_polish_without_top_duplicate_refresh():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()

    assert "Self-hosted workspace" in ui
    assert "Simple self-hosted workspace" not in ui
    assert "lite-devices-linked-grid" in ui
    assert "lite-device-card-linked" in ui
    assert "Disconnected from the Pocket Lab Lite server." in ui
    assert "lite-device-card-linked-joined" in css
    assert "lite-device-card-linked-disconnected" in css
    assert "lite-device-cross-card-flow" in css
    assert "lite-device-cross-card-x" in css


def test_lite_device_connection_lines_render_on_stacked_mobile_layout():
    css = Path("src/index.css").read_text()
    assert "@media (max-width: 1100px)" in css
    assert "lite-device-mobile-flow" in css
    assert "top: calc(-1rem - 1px)" in css
    assert "repeating-linear-gradient(180deg" in css
    assert "display: none" not in css.split("@media (max-width: 1100px)")[-1]


def test_lite_security_ui_has_remediation_guidance_and_health_banner():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()

    assert "What should I do?" in ui
    assert "Safe to ignore?" in ui
    assert "Expected" in ui
    assert "Recheck" in ui
    assert "Action needed" in ui
    assert "Review recommended" in ui
    assert "Your Pocket Lab looks safe" in ui
    assert "Mostly safe, recheck recommended" in ui
    assert "Review needed" in ui
    assert "Safety check did not finish" in ui
    assert "Run your first safety check" in ui
    assert "lite-security-remediation-drawer" in ui
    assert "lite-security-health-banner" in ui
    assert "lite-security-action-indicator" in ui
    assert "lite-security-remediation-drawer" in css
    assert "lite-security-health-banner" in css
    assert "@media (max-width: 720px)" in css



def test_lite_security_ui_has_evidence_quality_and_posture_summaries():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()

    assert "Latest evidence" in ui
    assert "View Evidence Receipt" in ui
    assert "Secrets: Hidden" in ui
    assert "Last known good" in ui
    assert "Current check is partial. Last known good state is still available." in ui
    assert "Compared with last check" in ui
    assert "Score:" in ui
    assert "Scan quality" in ui
    assert "Complete scan" in ui
    assert "Partial scan" in ui
    assert "Incomplete scan" in ui
    assert "Run a safety check to measure scan quality." in ui
    assert "lite-security-insight-grid" in ui
    assert "lite-security-receipt-summary-card" in ui
    assert "lite-security-scan-quality-card" in ui
    assert "lite-security-insight-grid" in css
    assert "lite-security-quality-chips" in css
    assert "lite-security-receipt-summary-grid" in css



def test_lite_security_ui_has_mobile_first_finding_detail_modal():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()

    assert "View details" in ui
    assert "Finding" in ui
    assert "Severity:" in ui
    assert "Source:" in ui
    assert "Affected component" in ui
    assert "Recommendation" in ui
    assert "Evidence reference" in ui
    assert "Close finding details" in ui
    assert "lite-finding-detail-modal" in ui
    assert "lite-security-coverage-scroll" in ui
    assert 'role="region"' in ui
    assert "lite-finding-detail-modal" in css
    assert "lite-finding-detail-trigger" in css
    assert "lite-security-evidence-dropdown" in ui
    assert "lite-security-evidence-dropdown" in css
    assert "SecurityFindingDetailModal" in ui
    assert "finding={item}" in ui or "finding={issue}" in ui
    assert "lite-finding-detail-backdrop" not in ui
    assert "lite-finding-detail-backdrop" not in css
    assert "onOpenEvidence" not in ui
    assert "@media (max-width: 720px)" in css


def test_lite_security_ui_has_collapsible_summary_cards():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()

    assert "SecurityCollapseToggle" in ui
    assert "Collapse" in ui
    assert "Show" in ui
    assert "collapsedSecurityCards" in ui
    assert "lite-security-collapse-toggle" in ui
    assert "lite-security-collapsible-body" in ui
    assert "lite-security-card-collapsed" in ui
    assert "Latest evidence" in ui
    assert "Last known good" in ui
    assert "Compared with last check" in ui
    assert "Execution timeline" in ui
    assert "Scan quality" in ui
    assert "Security history" in ui
    assert "Protection dashboard" in ui
    assert "lite-security-latest-evidence-body" in ui
    assert "lite-security-last-known-good-body" in ui
    assert "lite-security-posture-comparison-body" in ui
    assert "lite-security-execution-timeline-body" in ui
    assert "lite-security-scan-quality-body" in ui
    assert "lite-security-history-body" in ui
    assert "lite-security-protection-dashboard-body" in ui
    assert "aria-expanded" in ui
    assert "aria-controls" in ui
    assert "lite-security-collapse-toggle" in css
    assert "lite-security-collapsible-body" in css
    assert "lite-security-card-collapsed" in css
    assert "prefers-reduced-motion" in css


def test_lite_security_ui_preserves_backend_owned_boundaries():
    ui = _lite_ui_source().lower()

    forbidden = [
        "nats.connect(",
        "new websocket",
        "child_process",
        "exec(",
        "shell command",
        "run commands or change your device. any future fix action must stay backend-owned".replace(". any", ". Any").lower(),
    ]
    for term in forbidden[:4]:
        assert term not in ui
    assert "frontend never" not in ui
    assert "this guidance does not run commands or change your device" in ui
    assert "backend-owned" in ui


def test_lite_caddy_generator_adds_portal_only_photoprism_embed_policy():
    script = Path("pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh").read_text()

    assert "@pocketlab_non_app_routes" in script
    assert "header @pocketlab_non_app_routes X-Frame-Options \"DENY\"" in script
    assert "write_caddy_app_routes \"https://${site_label}\"" in script
    assert "header -X-Frame-Options" in script
    assert "header_down -X-Frame-Options" in script
    assert "header_down -Content-Security-Policy" in script
    assert "frame-ancestors 'self' {portal_origin}" in script
    assert "https://[A-Za-z0-9.-]+\\.ts\\.net" in script
    assert "pocket-lab-3.abc.ts.net" not in script


def test_lite_catalog_readiness_marks_photoprism_embeddable_only_when_policy_exists(monkeypatch, tmp_path):
    ensure_runtime_path()
    from api_fastapi.services import lite_catalog_live

    caddyfile = tmp_path / "Caddyfile"
    caddyfile.write_text(
        """
:8443 {
  @pocketlab_non_app_routes {
    not path /apps/*
  }
  header @pocketlab_non_app_routes X-Frame-Options "DENY"
  handle /apps/photoprism/* {
    reverse_proxy 127.0.0.1:2342
  }
}
portal.example.ts.net {
  handle /apps/photoprism/* {
    header -X-Frame-Options
    header Content-Security-Policy "frame-ancestors 'self' https://portal.example.ts.net"
    reverse_proxy 127.0.0.1:2342 {
      header_down -X-Frame-Options
      header_down -Content-Security-Policy
    }
  }
}
"""
    )
    monkeypatch.setenv("POCKETLAB_CADDYFILE", str(caddyfile))
    assert lite_catalog_live._photoprism_embed_origin_from_caddyfile() == "https://portal.example.ts.net"

    payload = {
        "apps": [
            {
                "id": "photoprism",
                "name": "PhotoPrism",
                "status": "ready",
                "install_state": "installed",
                "installed": True,
                "runtime": {"health": "healthy"},
                "actions": {"open": False},
                "access": {},
            }
        ],
        "items": [],
    }
    monkeypatch.setattr(lite_catalog_live, "_photoprism_route_ready", lambda: True)

    hydrated = lite_catalog_live.hydrate_catalog(payload)
    app = hydrated["apps"][0]
    assert app["access"]["route_ready"] is True
    assert app["access"]["open_url"] == "/apps/photoprism/"
    assert app["access"]["embed_allowed"] is True
    assert app["access"]["embed_policy"] == "portal_only"
    assert app["access"]["embed_origin"] == "https://portal.example.ts.net"
    assert app["workspace"]["mode"] == "embed"
    assert app["runtime"]["embed_allowed"] is True




def test_lite_workspace_trusts_embeddable_catalog_contract_without_timeout_probe():
    ui = Path("src/lite/LiteApp.jsx").read_text()

    assert "frameLoadedRef" not in ui
    assert "setFrameReady(true)" in ui
    assert "onError={() => {" in ui
    assert "setFrameFallback(true)" in ui
    assert "contentDocument" not in ui
    assert "documentRef" not in ui
    assert "hasLoadedContent" not in ui
    assert "2500" not in ui

def test_lite_workspace_quick_switcher_has_accessible_safe_controls():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()

    assert "WorkspaceQuickSwitcher" in ui
    assert "lite-workspace-quick-switcher" in ui
    assert "Open Pocket Lab switcher" in ui
    assert "Current app" in ui
    assert "Switch workspace" in ui
    assert "Back to Apps" in ui
    assert "Open full screen" in ui
    assert "aria-modal=\"true\"" in ui
    assert "event.key !== 'Escape'" in ui
    assert "firstActionRef.current.focus" in ui
    assert "triggerRef?.current?.focus" in ui
    assert "pocketlab:workspace:lastTab" in ui
    assert "window.localStorage.setItem('pocketlab:workspace:lastTab'" in ui
    assert "resolveSafeAppOpenPath" in ui
    assert "lite-workspace-switcher-fab" not in ui
    assert "lite-workspace-switcher-fab" not in css
    assert "lite-workspace-bottom-nav" not in ui
    assert "lite-workspace-bottom-nav" not in css
    assert "calc(1rem + env(safe-area-inset-bottom))" in css
    assert "<span>Switch</span>" in ui
    assert "@media (max-width: 767px)" in css

def test_lite_workspace_embed_helper_requires_matching_origin_when_declared():
    ui = _lite_ui_source()

    assert "embed_origin" in ui
    assert "window.location.origin !== embedOrigin" in ui
    assert "return false" in ui
    assert "access.embed_allowed === true" in ui


def test_lite_photoprism_storage_mappings_are_state_backed_and_sanitized():
    api = client()
    created = api.post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Phone photos",
            "source_path": "~/storage/shared/DCIM",
            "target": "import",
            "mode": "read_only",
        },
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["status"] == "created"
    mapping = payload["mapping"]
    assert mapping["label"] == "Phone photos"
    assert mapping["mode_label"] == "Read-only"
    assert mapping["pending_apply"] is True
    assert "source_path" not in mapping
    assert "/data/data" not in created.text
    assert "password" not in created.text.lower()

    listed = api.get("/api/lite/apps/photoprism/storage-mappings")
    assert listed.status_code == 200
    assert listed.json()["count"] == 1

    duplicate = api.post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Duplicate",
            "source_path": "~/storage/shared/DCIM",
            "target": "import",
            "mode": "read_only",
        },
    )
    assert duplicate.status_code == 409
    duplicate_payload = duplicate.json()
    duplicate_detail = duplicate_payload.get("detail") if isinstance(duplicate_payload.get("detail"), dict) else duplicate_payload
    assert duplicate_detail["status"] == "duplicate_mapping"

    deleted = api.delete(f"/api/lite/apps/photoprism/storage-mappings/{mapping['mapping_id']}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "deleted"


def test_lite_photoprism_storage_mapping_rejects_sensitive_paths():
    api = client()
    response = api.post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Secrets",
            "source_path": "~/.ssh",
            "target": "import",
            "mode": "read_only",
        },
    )
    assert response.status_code == 422
    assert "protected" in response.text or "approved" in response.text


def test_lite_catalog_includes_storage_and_device_capability_summary():
    api = client()
    api.post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Pictures",
            "source_path": "~/storage/shared/Pictures",
            "target": "import",
            "mode": "read_only",
        },
    )
    payload = api.get("/api/lite/catalog").json()
    app = payload["apps"][0]
    assert app["host_device_id"] == "pocket-lab-lite-server"
    assert app["host_device_name"]
    assert app["storage"]["count"] == 1
    assert app["storage"]["mappings"][0]["label"] == "Pictures"
    assert app["device_relationships"]["media_from"]
    assert "media_storage" in app["available_device_capabilities"]


def test_lite_fleet_adds_app_aware_device_capabilities(tmp_path):
    ensure_runtime_path()
    from api_fastapi.services import fleet_registry

    fleet_registry.upsert_agent(
        {
            "node_id": "storage-phone-1",
            "name": "Storage Phone",
            "role": "storage",
            "status": "online",
            "storage": {"available_gb": 92, "media_roots": ["Pictures", "DCIM"]},
        },
        event_type="fleet.node_heartbeat",
    )
    payload = client().get("/api/lite/fleet").json()
    storage = next(item for item in payload["devices"] if item["id"] == "storage-phone-1")
    assert storage["capabilities"] == ["media_storage", "backup_target"]
    assert "Storage Node" in storage["capability_labels"]
    assert storage["storage"]["available_gb"] == 92
    assert payload["capability_summary"]["available_device_capabilities"]["media_storage"] == 1


def test_lite_storage_and_capability_ui_is_present():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    assert "Media folders" in ui
    assert "Connect photos" in ui
    assert "Use phone photos" in ui
    assert "Use storage device" in ui
    assert "Storage devices:" in ui
    assert "deviceCapabilityLabels" in ui
    assert "lite-catalog-storage-panel" in css
    assert "lite-device-capability-chips" in css


def test_lite_app_security_profiles_are_sanitized_and_photoprism_aware():
    api = client()
    response = api.get("/api/lite/security/apps")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["count"] == 1
    profile = payload["apps"][0]
    assert profile["app_id"] == "photoprism"
    assert profile["name"] == "PhotoPrism"
    assert {item["id"] for item in profile["checks"]} >= {
        "route_safety",
        "config_redaction",
        "media_permissions",
        "backup_readiness",
    }
    assert "source_path" not in response.text
    assert "summary.json" not in response.text
    assert "password" not in response.text.lower()
    assert "secret" not in response.text.lower()

    single = api.get("/api/lite/security/apps/photoprism")
    assert single.status_code == 200
    assert single.json()["app_id"] == "photoprism"

    unsupported = api.get("/api/lite/security/apps/vault")
    assert unsupported.status_code == 404


def test_lite_app_security_check_is_safely_not_implemented():
    response = client().post(
        "/api/lite/security/apps/photoprism/check",
        json={"reason": "manual app safety check"},
    )
    assert response.status_code == 501
    payload = response.json()
    assert payload["status"] == "not_implemented"
    assert payload["accepted"] is False
    assert payload["app_id"] == "photoprism"


def test_lite_app_backup_profiles_are_sanitized_and_photoprism_aware():
    api = client()
    response = api.get("/api/lite/recovery/apps")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["count"] == 1
    profile = payload["apps"][0]
    assert profile["app_id"] == "photoprism"
    assert "App config" in profile["included"]
    assert "Storage mappings" in profile["included"]
    assert "Original media" in profile["excluded"]
    assert "Raw secrets" in profile["excluded"]
    assert profile["media"]["default"] == "excluded"
    assert "backup_target" in profile
    assert "restic-password" not in response.text.lower()
    assert "RESTIC_PASSWORD" not in response.text

    single = api.get("/api/lite/recovery/apps/photoprism")
    assert single.status_code == 200
    assert single.json()["app_id"] == "photoprism"

    unsupported = api.get("/api/lite/recovery/apps/vault")
    assert unsupported.status_code == 404


def test_lite_app_backup_queues_existing_worker_owned_backup(monkeypatch):
    from api_fastapi.services.nats_bus import BUS

    published: list[tuple[str, str, dict]] = []
    BUS.connected = True
    BUS.js = object()

    async def fake_publish(subject, event_type, data=None, *, trace_id=None):
        published.append((subject, event_type, data or {}))

    monkeypatch.setattr(BUS, "publish_json", fake_publish)

    response = client().post(
        "/api/lite/recovery/apps/photoprism/backup",
        json={"mode": "config_only", "reason": "manual app backup"},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["accepted"] is True
    assert payload["app_id"] == "photoprism"
    assert payload["mode"] == "config_only"
    assert payload["backup_id"].startswith("app-backup-photoprism-")
    assert any(item[0] == "pocketlab.commands.lite.backup.create" for item in published)


def test_lite_app_restore_endpoints_are_safe_until_explicit_restore_exists():
    preview = client().post(
        "/api/lite/recovery/apps/photoprism/restore/preview",
        json={"backup_id": "latest", "reason": "manual app restore preview"},
    )
    assert preview.status_code == 501
    assert preview.json()["status"] == "not_implemented"

    restore = client().post(
        "/api/lite/recovery/apps/photoprism/restore",
        json={"backup_id": "latest", "preview_id": "preview", "confirm": True},
    )
    assert restore.status_code == 501
    assert restore.json()["status"] == "not_implemented"


def test_lite_app_security_and_backup_ui_source_is_present():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    assert "Protected apps" in ui
    assert "Check app" in ui
    assert "View evidence" in ui
    assert "App backups" in ui
    assert "Back up app" in ui
    assert "Media excluded" in ui
    assert "Backup target" in ui
    assert "Config protected" in ui
    assert "lite-security-app-profiles" in css
    assert "lite-recovery-app-profiles" in css
    assert "child_process" not in ui
    assert "nats.connect" not in ui


def test_lite_unified_app_lifecycle_profile_is_sanitized_and_complete():
    response = client().get("/api/lite/apps/lifecycle")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["count"] == 1
    profile = payload["apps"][0]
    assert profile["app_id"] == "photoprism"
    assert profile["name"] == "PhotoPrism"
    assert profile["status"] in {"ready", "checking", "review", "needs_attention", "offline", "unavailable", "unknown"}
    assert "summary" in profile
    assert profile["host_device"]["label"] == "Runs on Server Phone"
    assert "storage" in profile
    assert "security" in profile
    assert "backup" in profile
    assert "recovery" in profile
    assert "actions" in profile
    assert "attention" in profile
    assert "evidence" in profile
    actions = profile["actions"]
    assert actions["open"]["label"] == "Open"
    assert actions["open_full_screen"]["label"] == "Open full screen"
    assert actions["install_to_phone"]["label"] == "Install to phone"
    assert actions["connect_photos"]["label"] == "Connect photos"
    assert actions["backup_app"]["label"] == "Back up app"
    assert actions["preview_restore"]["enabled"] is False
    assert "reason" in actions["preview_restore"]
    assert "/apps/photoprism/" in response.text or actions["open"].get("enabled") is False
    lowered = response.text.lower()
    for forbidden in ("password", "private_key", "vault_token", "nats_password", "restic_password", "scanner raw output"):
        assert forbidden not in lowered
    assert "source_path" not in response.text
    assert "summary.json" not in response.text


def test_lite_unified_app_lifecycle_detail_and_unsupported_app():
    response = client().get("/api/lite/apps/lifecycle/photoprism")
    assert response.status_code == 200
    profile = response.json()
    assert profile["app_id"] == "photoprism"
    assert profile["host_device"]["id"] == "pocket-lab-lite-server"
    assert profile["storage"]["mapping_count"] >= 0
    assert profile["security"]["summary"]
    assert profile["backup"]["summary"]
    assert profile["evidence"]["summary"]

    unsupported = client().get("/api/lite/apps/lifecycle/vault")
    assert unsupported.status_code == 404


def test_lite_catalog_is_hydrated_with_unified_lifecycle_summary():
    response = client().get("/api/lite/catalog")
    assert response.status_code == 200
    app = response.json()["apps"][0]
    assert app["id"] == "photoprism"
    assert "lifecycle" in app
    assert "lifecycle_summary" in app
    lifecycle = app["lifecycle"]
    assert lifecycle["app_id"] == "photoprism"
    assert lifecycle["host_device"]["label"] == "Runs on Server Phone"
    assert "actions" in lifecycle
    assert lifecycle["actions"]["preview_restore"]["enabled"] is False


def test_lite_security_and_recovery_include_lifecycle_profiles():
    security = client().get("/api/lite/security")
    assert security.status_code == 200
    assert security.json()["app_lifecycle_profiles"]["apps"][0]["app_id"] == "photoprism"

    recovery = client().get("/api/lite/recovery")
    assert recovery.status_code == 200
    assert recovery.json()["app_lifecycle_profiles"]["apps"][0]["app_id"] == "photoprism"


def test_lite_unified_lifecycle_ui_source_is_present():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    assert "Unified App Lifecycle" in ui
    assert "apps/lifecycle" in Path("src/lib/liteApi.js").read_text()
    assert "Media connected" in ui
    assert "Media not connected" in ui
    assert "Protected app" in ui
    assert "Backup ready" in ui
    assert "Runs on Server Phone" in ui
    assert "Needs attention" in ui
    assert "lite-catalog-lifecycle-panel" in css
    assert "lite-security-app-lifecycle" in css
    assert "lite-recovery-app-lifecycle" in css
    assert "child_process" not in ui
    assert "nats.connect" not in ui
    assert "exec(" not in ui
    assert "subprocess" not in ui
