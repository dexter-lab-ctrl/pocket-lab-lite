import asyncio
import json
from pathlib import Path

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir


def _lite_ui_source() -> str:
    lite_files = list(Path("src/lite").glob("Lite*.jsx"))
    lite_files.extend(Path("src/lite/catalog").glob("*.jsx"))
    lite_files.extend(Path("src/lite/components").glob("*.jsx"))
    return "".join(path.read_text() for path in sorted(lite_files))


def _lite_catalog_source() -> str:
    paths = [Path("src/lite/LiteCatalog.jsx")]
    paths.extend(sorted(Path("src/lite/catalog").glob("*.jsx")))
    paths.extend(sorted(Path("src/lite/components").glob("*.jsx")))
    return "".join(path.read_text() for path in paths if path.exists())


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
    assert "AppActionDetailsPanel" in _lite_catalog_source()
    assert "Ready to open" not in ui
    assert "Ready to open" not in css
    assert ">Ready<" in ui or "'Ready'" in ui
    assert "Open full screen" in ui
    assert "lite-home-pill lite-catalog-hero-pill is-secure" in ui
    assert "Remove app" in _lite_catalog_source()
    assert "Confirm remove" in _lite_catalog_source()
    assert "lite-catalog-access-card" in css
    assert "HeartPulse" in _lite_catalog_source()
    assert "Clock3" not in _lite_catalog_source()
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
    assert "has-phone-install" not in ui
    assert "Install to phone" not in ui
    assert "canInstallAppToPhone" not in ui
    assert "Use your browser menu to install it on this phone." not in ui
    assert "Smartphone" in _lite_catalog_source()
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
    mobile_block = css.split("@media (max-width: 1100px)")[-1].split("@keyframes lite-device-mobile-flow")[0]
    assert "display: none" not in mobile_block


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
    security = Path("src/lite/LiteSecurity.jsx").read_text()
    details = Path("src/lite/security/SecurityFindingDetailsLazy.jsx").read_text() if Path("src/lite/security/SecurityFindingDetailsLazy.jsx").exists() else security
    css = Path("src/index.css").read_text()

    ui = security + details
    assert "View details" in ui
    assert "Finding" in ui
    assert "Severity:" in ui
    assert "Source" in ui
    assert "Affected component" in ui
    assert "Recommendation" in ui or "recommended" in ui.lower()
    assert "Evidence reference" in ui
    assert "Close finding details" in ui
    assert "SecurityFindingDetailsLazy" in ui or "SecurityFindingDetailModal" in ui
    assert "finding={item}" in ui or "finding={issue}" in ui
    assert "lite-security-finding-details-panel" in ui or "lite-finding-detail-modal" in ui
    assert "lite-security-finding-details-panel" in css or "lite-finding-detail-modal" in css
    assert "lite-finding-detail-trigger" in css
    assert "lite-security-evidence-dropdown" in security
    assert "lite-security-evidence-dropdown" in css
    assert "lite-finding-detail-backdrop" not in ui
    assert "lite-finding-detail-backdrop" not in css
    assert "onOpenEvidence" not in security
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



def test_lite_photoprism_storage_preview_is_shallow_sanitized_and_read_only(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_app_storage

    root = tmp_path / "storage"
    root.mkdir()
    for name in ["downloads", "movies", "music", "pictures", "dcim"]:
        (root / name).mkdir()
    android_shared = tmp_path / "android-shared"
    android_shared.mkdir()
    (root / "shared").symlink_to(android_shared, target_is_directory=True)
    (root / ".ssh").mkdir()
    (root / "downloads" / "nested").mkdir()
    (root / "pictures" / "photo.jpg").write_text("not read by preview")

    monkeypatch.setattr(lite_app_storage, "_phone_storage_root", lambda: root)

    response = client().get("/api/lite/apps/photoprism/storage-preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["root"] == "~/storage"
    assert payload["root_label"] == "Phone storage"
    assert payload["connect_payload"] == {
        "source_type": "phone_media",
        "label": "Phone storage",
        "source_path": "~/storage",
        "target": "import",
        "mode": "read_only",
    }
    names = [item["name"] for item in payload["subfolders"]]
    assert names[:4] == ["shared", "dcim", "pictures", "movies"]
    assert "downloads" in names
    assert "music" in names
    assert ".ssh" not in names
    assert "nested" not in response.text
    assert "photo.jpg" not in response.text
    assert str(tmp_path) not in response.text
    assert "/storage/emulated/0" not in response.text
    assert "/data/data" not in response.text
    assert all(item["path_summary"].startswith("~/storage/") for item in payload["subfolders"])
    assert all(item.get("included") is True for item in payload["subfolders"])
    assert all("select" not in item for item in payload["subfolders"])


def test_lite_photoprism_storage_preview_reports_not_ready_when_missing(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_app_storage

    monkeypatch.setattr(lite_app_storage, "_phone_storage_root", lambda: tmp_path / "missing-storage")

    response = client().get("/api/lite/apps/photoprism/storage-preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["root"] == "~/storage"
    assert payload["subfolders"] == []
    assert payload["connect_payload"] is None
    assert "termux-setup-storage" in payload["reason"]
    assert "/data/data" not in response.text


def test_lite_photoprism_whole_phone_storage_mapping_is_precisely_allowed():
    api = client()
    created = api.post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Phone storage",
            "source_path": "~/storage",
            "target": "import",
            "mode": "read_only",
        },
    )
    assert created.status_code == 201
    assert "Choose a phone photos, pictures, downloads, or managed media folder" not in created.text
    payload = created.json()
    assert payload["mapping"]["label"] == "Phone storage"
    assert payload["mapping"]["source_path_summary"] == "Phone storage"
    assert payload["mapping"]["mode"] == "read_only"
    assert "source_path" not in payload["mapping"]
    assert "/data/data" not in created.text

    read_write = api.post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Bad",
            "source_path": "~/storage",
            "target": "import",
            "mode": "read_write",
        },
    )
    assert read_write.status_code == 422
    assert "read-only" in read_write.text

    wrong_target = api.post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Bad",
            "source_path": "~/storage",
            "target": "originals",
            "mode": "read_only",
        },
    )
    assert wrong_target.status_code == 422

    wrong_source_type = api.post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "managed_media",
            "label": "Bad",
            "source_path": "~/storage",
            "target": "import",
            "mode": "read_only",
        },
    )
    assert wrong_source_type.status_code == 422


def test_lite_photoprism_storage_mapping_still_rejects_private_and_system_paths():
    api = client()
    unsafe_paths = [
        "~",
        "~/",
        "~/.ssh",
        "~/.pocket_lab",
        "~/.pocketlab-lite-agent.env",
        "~/pocket-lab-lite",
        "~/storage/../.ssh",
        "~/storage;cat",
        "/data/data",
        "/proc",
        "/sys",
        "/dev",
        "/etc",
        "/root",
    ]
    for unsafe_path in unsafe_paths:
        response = api.post(
            "/api/lite/apps/photoprism/storage-mappings",
            json={
                "source_type": "phone_media",
                "label": "Unsafe",
                "source_path": unsafe_path,
                "target": "import",
                "mode": "read_only",
            },
        )
        assert response.status_code == 422, unsafe_path


def test_lite_photoprism_connect_photos_preview_ui_contract_is_present():
    ui = _lite_catalog_source()
    css = Path("src/index.css").read_text()
    api = Path("src/lib/liteApi.js").read_text()

    assert "Connect photos" in ui
    assert "Use phone storage" in ui
    assert "Visible folders" in ui
    assert "PhotoPrism will look for pictures in this phone’s storage" in ui
    assert "These folders are shown for clarity" in ui
    assert "Photos are not moved by this step" in ui
    assert "Run Import photos" in ui
    assert "Index photos" not in ui
    assert "photoprismStoragePreview" in api
    assert "/api/lite/apps/photoprism/storage-preview" in api
    assert "lite-catalog-storage-preview-sheet" in ui
    assert "lite-catalog-storage-preview-sheet" in css
    assert 'role="region"' in ui
    assert "lite-catalog-storage-preview-anchor" in ui
    assert "PhoneStorageConnectedFolders" in ui
    assert "Connected folders from Phone Storage" in ui
    assert "Android shared storage" in ui
    assert "Camera photos" in ui
    assert "lite-catalog-connected-folders" in css
    assert 'type="checkbox"' not in ui
    assert "selectedFolders" not in ui
    assert "folderPicker" not in ui
    assert "multiSelect" not in ui
    assert "phone_pictures" not in ui
    assert "phone_camera" not in ui

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
    assert any(item[0] == "pocketlab.commands.lite.app.backup.create" for item in published)


def test_lite_app_restore_endpoints_are_safe_until_explicit_restore_exists():
    status = client().get("/api/lite/apps/photoprism/backup")
    assert status.status_code == 200
    status_payload = status.json()
    assert status_payload["restore_preview_supported"] is True
    assert status_payload["restore_apply_supported"] is False
    assert status_payload["actions"]["preview_restore"]["enabled"] is False

    preview = client().post(
        "/api/lite/apps/photoprism/restore/preview",
        json={"backup_id": "latest", "reason": "manual app restore preview"},
    )
    assert preview.status_code == 409
    assert preview.json()["status"] == "no_verified_app_backup"

    recovery_preview = client().post(
        "/api/lite/recovery/apps/photoprism/restore/preview",
        json={"backup_id": "latest", "reason": "manual app restore preview"},
    )
    assert recovery_preview.status_code == 409
    assert recovery_preview.json()["status"] == "no_verified_app_backup"

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
    assert "apps/lifecycle" in Path("src/lib/liteApi.js").read_text()
    assert "lite-catalog-summary-panel" in ui
    assert "lite-catalog-manage-layer" in ui
    assert "lite-catalog-manage-backdrop" in ui
    assert "lite-catalog-manage-sheet" in ui
    assert 'role="dialog"' in ui
    assert 'aria-modal="true"' in ui
    assert "Manage" in ui
    assert "Open" in ui
    assert "Media connected" in ui
    assert "Media not connected" in ui
    assert "Protected app" in ui
    assert "Backup ready" in ui
    assert "Runs on Server Phone" in ui
    assert "Needs attention" in ui
    assert "Unified App Lifecycle" not in ui
    assert "lite-catalog-search-wrap" not in ui
    assert "lite-catalog-search-wrap" not in css
    assert "lite-catalog-filter-pills" not in ui
    assert "lite-catalog-filter-pills" not in css
    assert "lite-catalog-summary-panel" in css
    assert "lite-catalog-manage-layer" in css
    assert "lite-catalog-manage-backdrop" in css
    assert "lite-catalog-manage-sheet" in css
    assert "lite-security-app-lifecycle" in css
    assert "lite-recovery-app-lifecycle" in css
    assert "child_process" not in ui
    assert "nats.connect" not in ui
    assert "exec(" not in ui
    assert "subprocess" not in ui


def _force_photoprism_installed_for_action_tests(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_app_lifecycle, lite_app_update, lite_photoprism_lifecycle, lite_photoprism_media

    installed_app = {
        "id": "photoprism",
        "name": "PhotoPrism",
        "installed": True,
        "status": "ready",
        "actions": {"open": True},
        "access": {"open_url": "/apps/photoprism/", "route_ready": True},
        "runtime": {"url": "/apps/photoprism/"},
        "host_device_id": "pocket-lab-lite-server",
        "host_device_name": "Pocket Lab Lite Server",
    }

    monkeypatch.setattr(lite_app_lifecycle, "_catalog_app", lambda app_id: dict(installed_app))
    monkeypatch.setattr(lite_app_update, "_catalog_app", lambda app_id: dict(installed_app))
    lite_app_update._write_state({"pending_update_check": None, "latest_update_check": None})
    monkeypatch.setattr(lite_photoprism_lifecycle, "_catalog_app", lambda: dict(installed_app))
    monkeypatch.setattr(lite_photoprism_media, "_matching_media_process_count", lambda: 0)


def test_lite_app_action_center_lists_photoprism_readiness(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    response = client().get("/api/lite/apps/photoprism/actions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["app_id"] == "photoprism"
    actions = payload["actions"]
    for action_id in (
        "open",
        "open_full_screen",
        "install_to_phone",
        "connect_photos",
        "check_app",
        "backup_app",
        "preview_restore",
        "import_photos",
    ):
        assert action_id in actions
        assert "label" in actions[action_id]
    assert actions["import_photos"]["enabled"] is False
    assert "index_photos" not in actions
    assert "cancel_media" not in actions
    assert "Connect a photo folder first" in actions["import_photos"]["reason"]
    assert "password" not in response.text.lower()
    assert "photoprism_admin" not in response.text.lower()
    assert "source_path" not in response.text
    assert "photoprism import" not in response.text.lower()
    assert "photoprism index" not in response.text.lower()


def test_lite_app_action_center_rejects_invalid_app_and_action():
    invalid_app = client().get("/api/lite/apps/vault/actions")
    assert invalid_app.status_code == 404

    invalid_action = client().post(
        "/api/lite/apps/photoprism/actions/delete_everything",
        json={"reason": "bad action"},
    )
    assert invalid_action.status_code == 404


def test_lite_app_action_center_blocks_disabled_media_actions_without_mapping(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    response = client().post(
        "/api/lite/apps/photoprism/actions/import_photos",
        json={"reason": "manual import"},
    )
    assert response.status_code == 409
    payload = response.json().get("detail") or response.json()
    assert payload["status"] == "disabled"
    assert payload["action_id"] == "import_photos"
    assert "Connect a photo folder first" in payload["summary"]

    removed = client().post(
        "/api/lite/apps/photoprism/actions/index_photos",
        json={"reason": "manual index"},
    )
    assert removed.status_code == 404


def test_lite_app_action_center_enables_media_actions_after_mapping_and_queues(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    from api_fastapi.services.nats_bus import BUS

    mapping = client().post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Phone photos",
            "source_path": "~/storage/shared/DCIM",
            "target": "import",
            "mode": "read_only",
        },
    )
    assert mapping.status_code == 201

    actions_response = client().get("/api/lite/apps/photoprism/actions")
    assert actions_response.status_code == 200
    actions = actions_response.json()["actions"]
    assert actions["import_photos"]["enabled"] is True
    assert "index_photos" not in actions
    assert "cancel_media" not in actions

    lifecycle = client().get("/api/lite/apps/lifecycle/photoprism")
    assert lifecycle.status_code == 200
    lifecycle_payload = lifecycle.json()
    assert lifecycle_payload["media"]["mapping_count"] == 1
    assert lifecycle_payload["actions"]["import_photos"]["enabled"] is True
    assert "index_photos" not in lifecycle_payload["actions"]
    assert "cancel_media" not in lifecycle_payload["actions"]

    published: list[tuple[str, str, dict]] = []
    BUS.connected = True
    BUS.js = object()

    async def fake_publish(subject, event_type, data=None, *, trace_id=None):
        published.append((subject, event_type, data or {}))

    monkeypatch.setattr(BUS, "publish_json", fake_publish)

    queued = client().post(
        "/api/lite/apps/photoprism/actions/import_photos",
        json={"reason": "manual photo import"},
    )
    assert queued.status_code == 200
    payload = queued.json()
    assert payload["accepted"] is True
    assert payload["status"] == "queued"
    assert payload["app_id"] == "photoprism"
    assert payload["action_id"] == "import_photos"
    assert payload["media_operation"]["status"] == "queued"
    assert any(item[0] == "pocketlab.commands.lite.app.media" for item in published)
    assert "photoprism index" not in queued.text.lower()
    assert "password" not in queued.text.lower()


def test_lite_app_action_center_worker_subject_registered():
    ensure_runtime_path()
    from api_fastapi.services import domain_commands, lite_photoprism_media

    assert lite_photoprism_media.MEDIA_COMMAND_SUBJECT in domain_commands.supported_subjects()


def test_lite_worker_routes_media_commands_by_subject_before_generic_operation(monkeypatch):
    ensure_runtime_path()
    from workers import pocketlab_worker

    domain_calls: list[tuple[str, dict]] = []
    operation_calls: list[dict] = []
    acked: list[bool] = []

    async def fake_domain(subject, command):
        domain_calls.append((subject, command))

    async def fake_operation(command):
        operation_calls.append(command)

    async def fake_ack(msg):
        acked.append(True)

    monkeypatch.setattr(pocketlab_worker, "execute_domain_command", fake_domain)
    monkeypatch.setattr(pocketlab_worker, "execute_operation_command", fake_operation)
    monkeypatch.setattr(pocketlab_worker.BUS, "delivery_attempt", lambda msg: 1)
    monkeypatch.setattr(pocketlab_worker.BUS, "ack_message", fake_ack)

    class Message:
        subject = "pocketlab.commands.lite.app.media"
        data = json.dumps(
            {
                "data": {
                    "command_id": "photoprism-media-unit",
                    "app_id": "photoprism",
                    "action_id": "import_photos",
                    "operation": "import_photos",
                }
            }
        ).encode("utf-8")

    asyncio.run(pocketlab_worker.command_callback(Message()))

    assert acked == [True]
    assert operation_calls == []
    assert domain_calls
    subject, command = domain_calls[0]
    assert subject == "pocketlab.commands.lite.app.media"
    assert command["operation"] == "import_photos"


def test_lite_media_worker_applies_storage_mappings_before_photoprism_cli(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_app_storage, lite_photoprism_media

    source = tmp_path / "phone-storage"
    source.mkdir()
    (source / "sample.jpg").write_text("fake image")
    app_root = tmp_path / "photoprism"
    env_file = app_root / "config" / "photoprism.env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("PHOTOPRISM_ADMIN_USER=admin")

    created = client().post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Phone storage",
            "source_path": "~/storage",
            "target": "import",
            "mode": "read_only",
        },
    )
    assert created.status_code == 201
    mapping_id = created.json()["mapping"]["mapping_id"]

    calls = []

    class Completed:
        returncode = 0
        stdout = "import completed"
        stderr = ""

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return Completed()

    monkeypatch.setattr(lite_photoprism_media, "_app_root", lambda: app_root)
    monkeypatch.setattr(lite_photoprism_media, "_env_file", lambda: env_file)
    monkeypatch.setattr(lite_app_storage, "resolve_mapping_source_path", lambda source_path: source)
    monkeypatch.setattr(lite_photoprism_media.shutil, "which", lambda name: "/usr/bin/proot-distro" if name == "proot-distro" else None)
    monkeypatch.setattr(lite_photoprism_media.subprocess, "run", fake_run)

    result = lite_photoprism_media.execute_media_operation({
        "command_id": "photoprism-media-apply-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
    })

    assert result["status"] == "succeeded"
    assert result["mapping_apply"]["applied_count"] == 1
    links = list((app_root / "import" / "pocketlab-mappings").iterdir())
    symlinks = [item for item in links if item.is_symlink()]
    assert len(symlinks) == 1
    assert symlinks[0].name.startswith(mapping_id)
    assert symlinks[0].readlink() == source
    assert calls
    assert "photoprism import" in calls[0][0][0][-1]

    listed = client().get("/api/lite/apps/photoprism/storage-mappings").json()["mappings"]
    assert listed[0]["status"] == "applied"
    assert listed[0]["pending_apply"] is False
    assert listed[0]["requires_restart"] is False
    assert "source_path" not in listed[0]


def test_lite_media_worker_fails_safely_when_mapping_source_not_ready(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_app_storage, lite_photoprism_media

    app_root = tmp_path / "photoprism"
    env_file = app_root / "config" / "photoprism.env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("PHOTOPRISM_ADMIN_USER=admin")

    created = client().post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Phone storage",
            "source_path": "~/storage",
            "target": "import",
            "mode": "read_only",
        },
    )
    assert created.status_code == 201

    calls = []
    monkeypatch.setattr(lite_photoprism_media, "_app_root", lambda: app_root)
    monkeypatch.setattr(lite_photoprism_media, "_env_file", lambda: env_file)
    monkeypatch.setattr(lite_app_storage, "resolve_mapping_source_path", lambda source_path: tmp_path / "missing")
    monkeypatch.setattr(lite_photoprism_media.shutil, "which", lambda name: "/usr/bin/proot-distro" if name == "proot-distro" else None)
    monkeypatch.setattr(lite_photoprism_media.subprocess, "run", lambda *args, **kwargs: calls.append((args, kwargs)))

    result = lite_photoprism_media.execute_media_operation({
        "command_id": "photoprism-media-missing-source",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
    })

    assert result["status"] == "failed"
    assert result["mapping_apply"]["status"] == "not_ready"
    assert calls == []
    listed = client().get("/api/lite/apps/photoprism/storage-mappings").json()["mappings"]
    assert listed[0]["pending_apply"] is True


def test_lite_media_domain_failure_marks_operation_failed(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import domain_commands, lite_photoprism_media

    published: list[tuple[str, str, dict]] = []

    async def fake_publish(subject, event_type, data, *, trace_id=None):
        published.append((subject, event_type, data))

    def fail_execute(command):
        raise RuntimeError("Unsupported operation: import_photos")

    monkeypatch.setattr(domain_commands, "_publish", fake_publish)
    monkeypatch.setattr(lite_photoprism_media, "execute_media_operation", fail_execute)

    command = {
        "command_id": "photoprism-media-failed-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
    }
    result = asyncio.run(domain_commands.handle_lite_app_media(command))

    assert result["status"] == "failed"
    state = lite_photoprism_media.media_status("photoprism")
    assert state["operation_running"] is False
    assert state["last_import"]["status"] == "failed"
    assert state["last_import"]["summary"] == "Import photos could not complete."
    assert "Unsupported operation" not in state["last_import"]["summary"]
    assert any(item[0] == "pocketlab.events.lite.app.media.failed" for item in published)


def test_lite_media_status_reconciles_stale_running_operation(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_photoprism_media

    monkeypatch.setattr(lite_photoprism_media, "STALE_OPERATION_SECONDS", 0)
    command = {
        "command_id": "photoprism-media-stale-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
    }
    queued = lite_photoprism_media.record_operation(command, status="queued")
    assert queued["status"] == "queued"

    status = lite_photoprism_media.media_status("photoprism")

    assert status["operation_running"] is False
    assert status["last_import"]["status"] == "failed"
    assert status["last_import"]["summary"] == "Import photos could not complete."
    assert status["evidence"]["count"] >= 1


def test_lite_media_new_command_resets_previous_operation_timestamps(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_photoprism_media

    times = iter([
        "2026-07-01T00:00:00Z",
        "2026-07-01T00:00:01Z",
        "2026-07-01T00:00:05Z",
        "2026-07-01T00:00:06Z",
        "2026-07-01T00:00:07Z",
        "2026-07-01T12:40:00Z",
        "2026-07-01T12:40:01Z",
    ])

    def fake_now():
        try:
            return next(times)
        except StopIteration:
            return "2026-07-01T12:40:02Z"

    monkeypatch.setattr(lite_photoprism_media, "_now", fake_now)

    old_command = {
        "command_id": "photoprism-media-old-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
    }
    new_command = {
        "command_id": "photoprism-media-new-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 3,
    }

    lite_photoprism_media.record_operation(old_command, status="queued")
    old_done = lite_photoprism_media.record_operation(old_command, status="succeeded")
    assert old_done["completed_at"] == "2026-07-01T00:00:05Z"

    new_queued = lite_photoprism_media.record_operation(new_command, status="queued")
    assert new_queued["status"] == "queued"
    assert new_queued["started_at"] == "2026-07-01T12:40:00Z"
    assert new_queued["completed_at"] is None
    assert new_queued["evidence_status"] == "pending"

    state = lite_photoprism_media._read_state()
    stored = state["apps"]["photoprism"]["operations"]["import_photos"]
    assert stored["operation_id"] == "photoprism-media-new-unit"
    assert stored["started_at"] == "2026-07-01T12:40:00Z"
    assert "completed_at" not in stored
    assert "evidence_ref" not in stored


def test_lite_app_action_sheet_ui_source_is_present():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    assert "Manage" in ui
    assert "lite-catalog-manage-layer" in ui
    assert "lite-catalog-manage-backdrop" in ui
    assert "lite-catalog-manage-sheet" in ui
    assert "lite-catalog-manage-scroll" in ui
    assert "createPortal" in ui
    assert "APP_CATALOG_MANAGE_SHEET_PORTAL_OVERLAY" in ui
    assert "APP_CATALOG_MANAGE_PORTAL_STABLE_APP_KEY" in ui
    assert "function catalogAppKey(" in ui
    assert "setManageApp(appKey" in ui
    assert "setManageAppId" not in ui
    assert "updateLiteCatalogVisualViewportVar" in ui
    assert "visualViewport" in ui
    assert "lite-catalog-summary-panel" in ui
    assert "lite-app-action-row" in ui
    assert "@use-gesture/react" in ui
    assert "@react-spring/web" in ui
    assert "bindManageSheetDrag" in ui
    assert "bindCatalogPull" in ui
    assert "bindAppCardLongPress" in ui
    assert "bindManageSectionSwipe" in ui
    assert "{...bindCatalogPull()}" not in ui
    assert "{...bindAppCardLongPress(" not in ui
    assert "{...bindManageSectionSwipe()}" not in ui
    assert "Drag app actions sheet" in ui
    assert "lite-catalog-search-wrap" not in ui
    assert "lite-catalog-search-wrap" not in css
    assert "lite-catalog-filter-pills" not in ui
    assert "lite-catalog-filter-pills" not in css
    assert "Import photos" in ui
    assert "Index photos" not in ui
    assert "Stop photo action" not in ui
    assert "Last import" in ui
    assert "Connect a photo folder first" in ui
    assert "runAppAction" in Path("src/lib/liteApi.js").read_text()
    assert "apps/${encodeURIComponent(appId)}/actions" in Path("src/lib/liteApi.js").read_text()
    assert "lite-catalog-manage-layer" in css
    assert "lite-catalog-manage-backdrop" in css
    assert "lite-catalog-manage-sheet" in css
    assert "lite-catalog-manage-scroll" in css
    assert "--pl-visual-vh" in css
    assert "grid-template-rows: auto auto auto minmax(0, 1fr)" in css
    assert "lite-app-action-row" in css
    assert "lite-app-action-row-result" in css
    assert "touch-action: none" in css
    assert "safe-area-inset-top" in css
    assert "lite-catalog-pull-refresh" in ui
    assert "lite-catalog-gesture-layer" in ui
    assert "useSpring" in ui
    assert "useDrag" in ui
    assert "lite-catalog-quick-actions" in ui
    assert "lite-catalog-manage-section-tabs" in ui
    assert "lite-catalog-manage-section-viewport" in ui
    assert "lite-catalog-pull-refresh" in css
    assert "lite-catalog-quick-actions" in css
    assert "lite-catalog-manage-section-tabs" in css
    assert "lite-catalog-manage-section-viewport" in css
    assert "child_process" not in ui
    assert "nats.connect" not in ui
    assert "photoprism import" not in ui.lower()
    assert "photoprism index" not in ui.lower()
    assert "subprocess" not in ui


def test_lite_storage_backup_targets_endpoint_discovers_ready_storage(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_status

    monkeypatch.setattr(
        lite_status,
        "lite_fleet",
        lambda: {
            "status": "healthy",
            "devices": [
                {
                    "id": "pocket-lab-lite-server",
                    "name": "Pocket Lab Lite Server",
                    "role": "server_host",
                    "connection": "online",
                    "status": "healthy",
                    "is_current": True,
                    "capabilities": ["app_host", "compute", "security_scanner"],
                },
                {
                    "id": "storage-phone-1",
                    "name": "Storage Phone",
                    "role": "storage",
                    "connection": "online",
                    "status": "healthy",
                    "capabilities": ["media_storage", "backup_target"],
                    "storage": {"available_gb": 42},
                },
            ],
        },
    )

    response = client().get("/api/lite/recovery/backup-targets")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready_count"] == 1
    target = payload["targets"][0]
    assert target["device_id"] == "storage-phone-1"
    assert target["name"] == "Storage Phone"
    assert target["ready"] is True
    assert "backup_target" in target["capabilities"]
    assert "password" not in response.text.lower()
    assert "restic" not in response.text.lower()


def test_lite_storage_backup_targets_rejects_offline_target(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_status

    monkeypatch.setattr(
        lite_status,
        "lite_fleet",
        lambda: {
            "devices": [
                {
                    "id": "storage-phone-1",
                    "name": "Storage Phone",
                    "role": "storage",
                    "connection": "offline",
                    "status": "unhealthy",
                    "capabilities": ["media_storage", "backup_target"],
                    "storage": {"available_gb": 42},
                }
            ]
        },
    )

    response = client().post(
        "/api/lite/apps/photoprism/actions/backup_to_storage",
        json={"target_device_id": "storage-phone-1", "reason": "test transfer"},
    )
    assert response.status_code == 409
    payload = response.json().get("detail") or response.json()
    assert payload["status"] == "target_not_ready"
    assert "offline" in payload["summary"].lower()


def test_lite_photoprism_action_center_includes_storage_and_lifecycle_actions(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    response = client().get("/api/lite/apps/photoprism/actions")
    assert response.status_code == 200
    actions = response.json()["actions"]
    for action_id in (
        "backup_to_storage",
        "install_app",
        "update_app",
        "repair_app",
        "remove_app",
    ):
        assert action_id in actions
        assert "label" in actions[action_id]
    assert actions["remove_app"]["requires_confirmation"] is True
    assert actions["remove_app"]["risk"] == "destructive"
    assert actions["update_app"]["enabled"] is True
    assert actions["update_app"].get("readiness_only") is True
    assert actions["update_app"].get("apply_supported") is False
    assert "password" not in response.text.lower()
    assert "backup_key" not in response.text.lower()


def test_lite_remove_app_requires_confirmation_and_reason(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    missing_confirm = client().post(
        "/api/lite/apps/photoprism/actions/remove_app",
        json={"confirm": False, "reason": "validation should not remove"},
    )
    assert missing_confirm.status_code == 409
    assert "confirmation_required" in missing_confirm.text

    missing_reason = client().post(
        "/api/lite/apps/photoprism/actions/remove_app",
        json={"confirm": True},
    )
    assert missing_reason.status_code == 422
    assert "reason_required" in missing_reason.text

    confirmed = client().post(
        "/api/lite/apps/photoprism/actions/remove_app",
        json={"confirm": True, "reason": "user confirmed removal", "preserve_media": True, "preserve_backups": True, "preserve_evidence": True},
    )
    assert confirmed.status_code == 501
    payload = confirmed.json().get("detail") or confirmed.json()
    assert payload["status"] == "not_implemented"
    assert payload["preserve_media"] is True
    assert payload["preserve_backups"] is True
    assert payload["preserve_evidence"] is True
    assert "photo files" not in confirmed.text.lower() or "will not be deleted" not in confirmed.text.lower()
    assert "password" not in confirmed.text.lower()


def test_lite_storage_and_app_lifecycle_ui_source_is_present():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    api = Path("src/lib/liteApi.js").read_text()
    assert "Back up to storage device" in ui
    assert "Saved to Storage Phone" in ui
    assert "Remove app" in ui
    assert "Confirm remove" in ui
    assert "Your photo files and backups will not be deleted by default" in ui
    assert "Repair" in ui
    assert "Update" in ui
    assert "backup-targets" in api
    assert "backup_to_storage" in ui
    assert "install_app" in ui
    assert "remove_app" in ui
    assert "repair_app" in ui
    assert "update_app" in ui
    assert "lite-catalog-remove-confirm" in css
    assert "lite-recovery-backup-targets" in css
    assert "child_process" not in ui
    assert "nats.connect" not in ui
    assert "rsync" not in ui.lower()
    assert "scp" not in ui.lower()
    assert "ssh " not in ui.lower()


def test_lite_photoprism_media_optimizer_deduplicates_overlapping_mappings(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_app_storage, lite_photoprism_media

    storage = tmp_path / "storage"
    dcim = storage / "shared" / "DCIM"
    pictures = storage / "shared" / "Pictures"
    noisy_docs = storage / "shared" / "Android" / "media" / "com.whatsapp" / "WhatsApp" / "Media" / "WhatsApp Documents"
    dcim.mkdir(parents=True)
    pictures.mkdir(parents=True)
    noisy_docs.mkdir(parents=True)
    (dcim / "sample.jpg").write_text("fake image")
    (noisy_docs / "ND4812.pdf").write_text("not a photo")
    app_root = tmp_path / "photoprism"
    env_file = app_root / "config" / "photoprism.env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("PHOTOPRISM_ADMIN_USER=admin")

    for label, source_path in [
        ("Camera folder", "~/storage/shared/DCIM"),
        ("Pictures", "~/storage/shared/Pictures"),
        ("Phone storage", "~/storage"),
    ]:
        created = client().post(
            "/api/lite/apps/photoprism/storage-mappings",
            json={
                "source_type": "phone_media",
                "label": label,
                "source_path": source_path,
                "target": "import",
                "mode": "read_only",
            },
        )
        assert created.status_code == 201

    def resolve_source(source_path):
        if source_path == "~/storage":
            return storage
        if source_path == "~/storage/shared/DCIM":
            return dcim
        if source_path == "~/storage/shared/Pictures":
            return pictures
        raise AssertionError(source_path)

    class Completed:
        returncode = 0
        stdout = "import completed"
        stderr = ""

    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return Completed()

    monkeypatch.setattr(lite_photoprism_media, "_app_root", lambda: app_root)
    monkeypatch.setattr(lite_photoprism_media, "_env_file", lambda: env_file)
    monkeypatch.setattr(lite_app_storage, "resolve_mapping_source_path", resolve_source)
    monkeypatch.setattr(lite_photoprism_media.shutil, "which", lambda name: "/usr/bin/proot-distro" if name == "proot-distro" else None)
    monkeypatch.setattr(lite_photoprism_media.subprocess, "run", fake_run)

    result = lite_photoprism_media.execute_media_operation({
        "command_id": "photoprism-media-optimized-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 3,
    })

    assert result["status"] == "succeeded"
    assert result["mapping_apply"]["runtime_mapping_count"] == 1
    assert result["mapping_apply"]["runtime_roots_used"] == 2
    assert result["mapping_apply"]["overlap_skipped_count"] == 2
    assert result["mapping_apply"]["excluded_noisy_roots"] >= 1
    links = sorted((app_root / "import" / "pocketlab-mappings").iterdir())
    symlinks = [item for item in links if item.is_symlink()]
    assert len(symlinks) == 2
    assert {item.readlink() for item in symlinks} == {dcim, pictures}
    assert not any(item.readlink() == noisy_docs for item in symlinks)
    listed = client().get("/api/lite/apps/photoprism/storage-mappings").json()["mappings"]
    assert {item["status"] for item in listed} == {"applied"}
    assert all(item["pending_apply"] is False for item in listed)
    assert calls


def test_lite_photoprism_media_cancel_stops_running_operation_without_web_server(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_photoprism_media

    command = {
        "command_id": "photoprism-media-cancel-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
    }
    queued = lite_photoprism_media.record_operation(command, status="queued")
    assert queued["status"] == "queued"

    calls: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = "21400 photoprism import"
        stderr = ""

    def fake_run(args, **kwargs):
        calls.append(list(args))
        if args[:2] == ["pgrep", "-af"]:
            return Completed()
        class Empty:
            returncode = 0
            stdout = ""
            stderr = ""
        return Empty()

    monkeypatch.setattr(lite_photoprism_media.subprocess, "run", fake_run)
    monkeypatch.setattr(lite_photoprism_media.time if hasattr(lite_photoprism_media, "time") else lite_photoprism_media, "sleep", lambda *_: None, raising=False)

    result = lite_photoprism_media.cancel_media_action("photoprism", reason="user stopped long import")

    assert result["status"] == "cancelled"
    assert result["cancelled_operations"] == 1
    assert result["processes"]["matched"] >= 1
    assert any(call[:3] == ["pkill", "-TERM", "-f"] for call in calls)
    assert not any("pocketlab-app-photoprism" in " ".join(call) for call in calls)
    status = lite_photoprism_media.media_status("photoprism")
    assert status["operation_running"] is False
    assert status["last_import"]["status"] == "cancelled"
    assert status["last_import"]["progress"]["bounded"] is True


def test_lite_app_action_center_does_not_expose_cancel_or_index(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_photoprism_media

    command = {
        "command_id": "photoprism-media-action-import-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
    }
    lite_photoprism_media.record_operation(command, status="running")

    lifecycle = client().get("/api/lite/apps/lifecycle/photoprism")
    assert lifecycle.status_code == 200
    actions = lifecycle.json()["actions"]
    assert "cancel_media" not in actions
    assert "index_photos" not in actions

    cancelled = client().post(
        "/api/lite/apps/photoprism/actions/cancel_media",
        json={"reason": "stop test media action"},
    )
    assert cancelled.status_code == 404


def test_lite_photoprism_cancel_blocks_late_worker_updates(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_photoprism_media

    command = {
        "command_id": "photoprism-media-late-cancel-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
    }
    lite_photoprism_media.record_operation(command, status="running")
    monkeypatch.setattr(lite_photoprism_media, "_stop_media_processes", lambda: {"status": "stopped", "matched": 2, "terminated": 2, "killed": 2, "remaining": 0})

    cancelled = lite_photoprism_media.cancel_media_action("photoprism", reason="user stopped import")
    assert cancelled["status"] == "cancelled"
    assert cancelled["processes"]["remaining"] == 0

    late = lite_photoprism_media.record_operation(command, status="failed", summary="late worker failure after cancel")
    assert late["status"] == "cancelled"
    status = lite_photoprism_media.media_status("photoprism")
    assert status["operation_running"] is False
    assert status["last_import"]["status"] == "cancelled"


def test_lite_photoprism_lifecycle_reconciles_orphaned_running_operation(monkeypatch):
    ensure_runtime_path()
    from datetime import datetime, timedelta, timezone
    from api_fastapi.services import lite_photoprism_media

    command = {
        "command_id": "photoprism-media-orphaned-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
    }
    lite_photoprism_media.record_operation(command, status="running")
    state = lite_photoprism_media._read_state()
    old = (datetime.now(timezone.utc) - timedelta(seconds=120)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    state["apps"]["photoprism"]["operations"]["import_photos"]["started_at"] = old
    lite_photoprism_media._write_state(state)
    monkeypatch.setattr(lite_photoprism_media, "_matching_media_process_count", lambda: 0)

    status = lite_photoprism_media.media_status("photoprism")
    assert status["operation_running"] is False
    assert status["last_import"]["status"] == "succeeded"
    assert status["last_import"]["progress"]["phase"] == "done"


def test_lite_photoprism_media_failure_hides_app_owned_output(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_app_storage, lite_photoprism_media

    storage = tmp_path / "storage"
    dcim = storage / "shared" / "DCIM"
    excluded = storage / "shared" / "Android" / "media" / "com.whatsapp" / "WhatsApp" / "Media" / "WhatsApp Documents"
    dcim.mkdir(parents=True)
    excluded.mkdir(parents=True)
    app_root = tmp_path / "photoprism"
    env_file = app_root / "config" / "photoprism.env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("PHOTOPRISM_ADMIN_USER=admin")

    created = client().post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Phone storage",
            "source_path": "~/storage",
            "target": "import",
            "mode": "read_only",
        },
    )
    assert created.status_code == 201

    class Completed:
        returncode = 1
        stdout = ""
        stderr = (
            "proot warning: can\'t sanitize binding \"/proc/self/fd/0\": No such file or directory"
            'time="2026-07-01T14:16:13Z" level=error msg="index: could not create preview image for 2024/11/sample.pdf"'
        )

    monkeypatch.setattr(lite_photoprism_media, "_app_root", lambda: app_root)
    monkeypatch.setattr(lite_photoprism_media, "_env_file", lambda: env_file)
    monkeypatch.setattr(lite_app_storage, "resolve_mapping_source_path", lambda source_path: storage)
    monkeypatch.setattr(lite_photoprism_media.shutil, "which", lambda name: "/usr/bin/proot-distro" if name == "proot-distro" else None)
    monkeypatch.setattr(lite_photoprism_media.subprocess, "run", lambda *args, **kwargs: Completed())

    result = lite_photoprism_media.execute_media_operation({
        "command_id": "photoprism-media-output-hidden-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
    })

    assert result["status"] == "failed"
    assert result["mapping_apply"]["runtime_roots_used"] == 1
    assert result["mapping_apply"]["excluded_noisy_roots"] >= 1
    status = lite_photoprism_media.media_status("photoprism")
    public = status["last_import"]
    assert public["status"] == "failed"
    assert public["summary"] == "Import photos could not complete."
    assert "proot warning" not in str(public).lower()
    assert "sample.pdf" not in str(public).lower()
    state = lite_photoprism_media._read_state()
    stored = state["apps"]["photoprism"]["operations"]["import_photos"]
    assert stored["summary"] == "Import photos could not complete."
    assert stored["app_output_hidden"] is True
    evidence = lite_photoprism_media._read_json(lite_photoprism_media._evidence_path(), {})
    latest = evidence["events"][0]
    assert latest["summary"] == "Import photos could not complete."
    assert latest["app_output_hidden"] is True
    assert latest["details_owner"] == "photoprism"
    assert "proot warning" not in str(latest).lower()
    assert "sample.pdf" not in str(latest).lower()


def test_lite_photoprism_media_status_sanitizes_existing_noisy_summaries(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_photoprism_media

    command = {
        "command_id": "photoprism-media-existing-noisy-unit",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
    }
    lite_photoprism_media.record_operation(command, status="failed", summary='time="2026-07-01" level=error msg="could not create preview image for 2024/11/sample.pdf"')

    status = lite_photoprism_media.media_status("photoprism")

    assert status["last_import"]["summary"] == "Import photos could not complete."
    assert "sample.pdf" not in str(status).lower()
    state = lite_photoprism_media._read_state()
    stored = state["apps"]["photoprism"]["operations"]["import_photos"]
    assert stored["summary"] == "Import photos could not complete."
    assert stored["app_output_hidden"] is True


def test_lite_photoprism_index_is_app_owned_and_not_public_lite_action(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_photoprism_media

    command = {
        "command_id": "photoprism-media-historical-index",
        "app_id": "photoprism",
        "action_id": "index_photos",
        "operation": "index_photos",
        "mapping_count": 1,
    }
    lite_photoprism_media.record_operation(command, status="running")
    status = lite_photoprism_media.media_status("photoprism")

    assert status["operation_running"] is False
    assert status["last_index"] is None
    assert status["indexing_owner"] == "photoprism"

def test_lite_photoprism_orphaned_running_index_reconciles_to_finished(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_photoprism_media

    monkeypatch.setattr(lite_photoprism_media, "_matching_media_process_count", lambda: 0)
    command = {
        "command_id": "photoprism-media-orphaned-index",
        "app_id": "photoprism",
        "action_id": "index_photos",
        "operation": "index_photos",
        "mapping_count": 1,
        "progress": lite_photoprism_media._progress_payload("executing", "PhotoPrism is working.", 3),
    }
    lite_photoprism_media.record_operation(command, status="running")
    state = lite_photoprism_media._read_state()
    operation = state["apps"]["photoprism"]["operations"]["index_photos"]
    operation["started_at"] = "2026-07-01T00:00:00Z"
    operation["updated_at"] = "2026-07-01T00:00:00Z"
    lite_photoprism_media._write_state(state)

    changed = lite_photoprism_media.reconcile_orphaned_running_operations("photoprism")
    status = lite_photoprism_media.media_status("photoprism")

    assert changed == 1
    assert status["operation_running"] is False
    assert status["last_index"] is None
    assert status["indexing_owner"] == "photoprism"


def test_lite_photoprism_executing_progress_is_indeterminate():
    ensure_runtime_path()
    from api_fastapi.services import lite_photoprism_media

    command = {
        "command_id": "photoprism-media-progress-wording",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
        "progress": lite_photoprism_media._progress_payload("executing", "Import photos is running.", 3),
    }
    operation = lite_photoprism_media.record_operation(command, status="running", summary="Import photos is running.")

    assert operation["summary"] == "Import photos is running."
    assert operation["progress"]["step"] == "Import photos is running."
    assert operation["progress"]["indeterminate"] is True


def test_lite_app_evidence_endpoint_handles_missing_receipts_safely():
    response = client().get("/api/lite/apps/photoprism/evidence")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["app_id"] == "photoprism"
    assert payload["latest"] is None
    assert payload["items"] == []
    assert payload["backend_only"] is True
    assert payload["debug_only"] is True
    assert payload["normal_ui_dependency"] is False
    assert "normal App Catalog UI does not load" in payload["summary"]
    assert payload["fallback_receipt"]["summary"] == "No detailed receipt yet. Future actions will include proof details."
    text = response.text.lower()
    assert "/data/data" not in text
    assert "nats://" not in text
    assert "token=" not in text
    assert "password=" not in text
    assert "api_key" not in text


def test_lite_app_evidence_exposes_action_state_receipts_without_making_them_latest():
    response = client().get("/api/lite/apps/photoprism/evidence")
    assert response.status_code == 200
    payload = response.json()
    assert payload["latest"] is None
    assert payload["items"] == []
    assert payload["backend_only"] is True
    assert payload["debug_only"] is True
    assert payload["normal_ui_dependency"] is False
    assert payload["by_action"]["open"]["backend_trace"]["execution_owner"] == "Browser navigation"
    assert payload["by_action"]["install_app"]["backend_trace"]["summary"]
    assert payload["by_action"]["remove_app"]["what_did_not_happen"]
    assert "No backend command was queued" in response.text
    assert "password" not in response.text.lower()
    assert "nats://" not in response.text.lower()


def test_lite_app_evidence_import_receipt_has_safe_proofs():
    ensure_runtime_path()
    api = client()
    created = api.post(
        "/api/lite/apps/photoprism/storage-mappings",
        json={
            "source_type": "phone_media",
            "label": "Phone storage",
            "source_path": "~/storage",
            "target": "import",
            "mode": "read_only",
        },
    )
    assert created.status_code == 201

    from api_fastapi.services import lite_photoprism_media

    command = {
        "command_id": "photoprism-media-test-import-receipt",
        "app_id": "photoprism",
        "action_id": "import_photos",
        "operation": "import_photos",
        "mapping_count": 1,
        "runtime_mappings_used": 1,
        "progress": lite_photoprism_media._progress_payload("done", "Import photos completed.", 5),
    }
    lite_photoprism_media.record_operation(command, status="succeeded", summary="Import photos completed.")

    response = api.get("/api/lite/apps/photoprism/evidence")
    assert response.status_code == 200
    payload = response.json()
    latest = payload["latest"]
    assert latest["action_id"] == "import_photos"
    assert latest["status"] == "succeeded"
    proof_ids = {item["id"] for item in latest["proofs"]}
    assert {
        "backend_worker_executed",
        "frontend_no_shell",
        "browser_no_file_access",
        "storage_read_only",
        "secrets_hidden",
        "media_preserved",
        "media_details_owned_by_photoprism",
    }.issubset(proof_ids)
    assert latest["proof_counts"]["passed"] >= 7
    assert latest["redaction"]["secrets_hidden"] is True
    assert latest["redaction"]["raw_logs_hidden"] is True
    assert latest["redaction"]["raw_paths_hidden"] is True
    assert latest["technical_details"]["control_api"] == "FastAPI"
    assert latest["backend_trace"]["execution_owner"] == "Backend worker"
    assert latest["operator_summary"]
    text = response.text.lower()
    assert "/data/data" not in text
    assert "nats://" not in text
    assert "token=" not in text
    assert "password=" not in text
    assert "api_key" not in text
    assert "photoprism admin" not in text


def test_lite_app_evidence_unknown_app_returns_safe_404():
    response = client().get("/api/lite/apps/gitea/evidence")
    assert response.status_code == 404
    text = response.text.lower()
    assert "photoprism" in text
    assert "token" not in text
    assert "password" not in text


def test_lite_app_catalog_ui_uses_lightweight_action_details():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    for marker in (
        "AppActionDetailsButton",
        "AppActionDetailsPanel",
        "Details",
        "Last result",
        "What happened",
        "What changed",
        "What did not happen",
        "Saved for troubleshooting",
        "Technical details",
    ):
        assert marker in ui
    for marker in (
        "lite-app-action-details-button",
        "lite-app-action-details-panel",
        "lite-catalog-action-details-anchor",
    ):
        assert marker in css
    for removed_marker in (
        "PhotoPrismEvidenceCard",
        "PhotoPrismEvidenceReceiptModal",
        "View receipt",
        "Receipt ready",
        "No evidence receipt yet",
        "Evidence needs a moment",
        "lite-catalog-evidence-card",
        "lite-catalog-action-receipt-anchor",
        "selectedReceiptActionId",
        "openEvidenceReceipt",
    ):
        assert removed_marker not in ui
    assert "Plain Language" not in ui


def test_lite_app_safety_repair_actions_are_enabled_when_installed(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    response = client().get("/api/lite/apps/photoprism/actions")
    assert response.status_code == 200
    actions = response.json()["actions"]
    assert actions["check_app"]["enabled"] is True
    assert actions["check_app"]["category"] == "safety"
    assert "route" in actions["check_app"]["summary"].lower()
    assert actions["repair_app"]["enabled"] is True
    assert actions["repair_app"]["category"] == "recovery"
    assert "storage" in actions["repair_app"]["summary"].lower()
    assert "password" not in response.text.lower()
    assert "nats://" not in response.text.lower()


def test_lite_app_update_status_is_readiness_only(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    response = client().get("/api/lite/apps/photoprism/update")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["app_id"] == "photoprism"
    assert payload["update_check_supported"] is True
    assert payload["update_apply_supported"] is False
    assert payload["actions"]["update_app"]["enabled"] is True
    assert payload["actions"]["apply_update"]["enabled"] is False
    assert "No update check has run yet" in payload["readiness"]["summary"]
    assert "nats://" not in response.text.lower()
    assert "/data/data" not in response.text.lower()
    assert "password" not in response.text.lower()


def test_lite_app_update_action_builds_worker_command_and_queued_state(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_actions, lite_app_update

    action = lite_app_actions.prepare_action(
        "photoprism",
        "update_app",
        payload={"reason": "manual update readiness check"},
    )
    assert action["kind"] == "update_check"
    assert action["subject"] == lite_app_update.APP_UPDATE_CHECK_SUBJECT
    command = action["command"]
    assert command["action_id"] == "update_app"
    assert command["readiness_only"] is True
    pending = lite_app_update.record_update_request(command)
    assert pending["status"] == "queued"
    assert pending["progress"]["bounded"] is True
    assert "Update check queued" in pending["progress"]["step"]
    assert "nats://" not in json.dumps(pending).lower()


def test_lite_app_update_readiness_receipt_is_sanitized(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_update

    command = lite_app_update.update_command("photoprism", reason="manual update readiness check")
    result = lite_app_update.create_update_readiness(command)
    assert result["action_id"] == "update_app"
    assert result["apply_supported"] is False
    assert result["update_available"] == "unknown"
    assert result["readiness"] in {"review", "ready", "blocked"}
    receipt = lite_app_update.update_receipt("photoprism", result["operation_id"])
    assert receipt is not None
    proof_ids = {item["id"] for item in receipt["proofs"]}
    assert "no_update_applied" in proof_ids
    assert "backup_freshness_checked" in proof_ids
    assert "restore_preview_checked" in proof_ids
    assert "rollback_readiness_checked" in proof_ids
    assert "app_health_checked" in proof_ids
    assert receipt["redaction"]["secrets_hidden"] is True
    text = json.dumps(receipt).lower()
    assert "no update was installed" in text
    assert "nats://" not in text
    assert "/data/data" not in text
    assert "password=" not in text
    assert "token=" not in text


def test_lite_app_update_receipt_surfaces_in_app_evidence(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_update

    command = lite_app_update.update_command("photoprism", reason="manual update readiness check")
    lite_app_update.create_update_readiness(command)
    response = client().get("/api/lite/apps/photoprism/evidence")
    assert response.status_code == 200
    payload = response.json()
    action_ids = {item.get("action_id") for item in payload.get("items", [])}
    assert "update_app" in action_ids
    assert payload["latest"]["action_id"] == "update_app"
    assert "No update was installed" in response.text
    assert payload["latest"]["backend_trace"]["execution_owner"] == "Backend worker"
    assert "backend_trace" in payload["by_action"]["update_app"]
    assert "nats://" not in response.text.lower()
    assert "/data/data" not in response.text.lower()


def test_lite_app_update_apply_stays_disabled(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    response = client().post(
        "/api/lite/apps/photoprism/update/apply",
        json={"reason": "attempt apply"},
    )
    assert response.status_code == 409
    payload = response.json()
    assert payload["status"] == "disabled"
    assert payload["accepted"] is False
    assert payload["update_apply_supported"] is False


def test_lite_app_update_unknown_app_is_safe():
    response = client().get("/api/lite/apps/vault/update")
    assert response.status_code == 404
    assert "PhotoPrism is the first app" in response.text


def test_lite_app_update_frontend_source_is_readiness_only():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    assert "Check whether PhotoPrism is ready for a safe update." in ui
    assert "Checking update readiness" in ui
    assert "No update was applied" in ui
    assert "LiteActionProgress" in ui
    assert "lite-action-progress__rail" in ui
    assert "update_app: 'readiness'" in ui
    assert "lite-action-progress" in css
    assert "Update Readiness Conveyor" not in ui
    assert "Index photos" not in ui
    assert "Refresh library" not in ui
    assert "Stop photo" not in ui
    assert "nats.connect" not in ui
    assert "exec(" not in ui


def test_lite_app_safety_and_repair_worker_subjects_registered():
    ensure_runtime_path()
    from api_fastapi.services import domain_commands, lite_app_operations

    subjects = domain_commands.supported_subjects()
    assert lite_app_operations.SAFETY_SUBJECT in subjects
    assert lite_app_operations.REPAIR_SUBJECT in subjects
    assert "pocketlab.commands.lite.app.update.check" in subjects


def test_lite_app_check_app_builds_worker_command_and_queued_state(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_actions, lite_app_operations

    action = lite_app_actions.prepare_action(
        "photoprism",
        "check_app",
        payload={"reason": "manual app safety check"},
    )

    assert action["kind"] == "app_operation"
    assert action["subject"] == lite_app_operations.SAFETY_SUBJECT
    assert action["command"]["action_id"] == "check_app"

    queued = lite_app_operations.record_queued_operation(action["command"])
    assert queued["status"] == "queued"
    assert queued["progress"]["phase"] == "queued"
    assert queued["progress"]["bounded"] is True
    assert queued["evidence_ref"].startswith("apps/photoprism/safety/")
    assert "password" not in json.dumps(queued).lower()
    assert "nats://" not in json.dumps(queued).lower()

    router_source = Path("pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py").read_text()
    assert 'kind == "app_operation"' in router_source
    assert "submit_domain_command" in router_source


def test_lite_app_repair_app_builds_worker_command_and_queued_state(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_actions, lite_app_operations

    action = lite_app_actions.prepare_action(
        "photoprism",
        "repair_app",
        payload={"reason": "manual safe repair"},
    )

    assert action["kind"] == "app_operation"
    assert action["subject"] == lite_app_operations.REPAIR_SUBJECT
    assert action["command"]["action_id"] == "repair_app"

    queued = lite_app_operations.record_queued_operation(action["command"])
    assert queued["status"] == "queued"
    assert queued["progress"]["phase"] == "queued"
    assert queued["progress"]["bounded"] is True
    assert queued["evidence_ref"].startswith("apps/photoprism/repair/")
    assert "password" not in json.dumps(queued).lower()
    assert "nats://" not in json.dumps(queued).lower()

def test_lite_app_check_receipt_has_safe_proofs(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_operations

    monkeypatch.setattr(lite_app_operations, "_pm2_process_online", lambda process_name="pocketlab-app-photoprism": "online")
    monkeypatch.setattr(lite_app_operations, "_local_health_ready", lambda: True)
    monkeypatch.setattr(lite_app_operations, "_route_health_ready", lambda: True)
    monkeypatch.setattr(lite_app_operations, "_caddy_route_status", lambda: ("passed", {"caddyfile_checked": True, "prefix_preserved": True}))

    command = lite_app_operations.command_for_operation("photoprism", "check_app", reason="unit check")
    lite_app_operations.record_queued_operation(command)
    result = lite_app_operations.execute_check_app(command)
    assert result["status"] in {"succeeded", "review"}

    response = client().get("/api/lite/apps/photoprism/evidence")
    assert response.status_code == 200
    payload = response.json()
    latest = payload["latest"]
    assert latest["action_id"] == "check_app"
    proof_ids = {item["id"] for item in latest["proofs"]}
    assert {
        "backend_worker_executed",
        "frontend_no_shell",
        "app_route_checked",
        "app_health_checked",
        "storage_mapping_checked",
        "secrets_hidden",
        "raw_logs_hidden",
        "raw_paths_hidden",
        "media_not_scanned",
        "media_details_owned_by_photoprism",
    }.issubset(proof_ids)
    assert latest["redaction"]["secrets_hidden"] is True
    assert latest["redaction"]["raw_logs_hidden"] is True
    assert latest["redaction"]["raw_paths_hidden"] is True
    assert latest["redaction"]["secret_values_saved"] is False
    text = response.text.lower()
    assert "/data/data" not in text
    assert "nats://" not in text
    assert "password=" not in text
    assert "token=" not in text


def test_lite_app_repair_receipt_has_safe_proofs(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_operations

    monkeypatch.setattr(lite_app_operations, "_local_health_ready", lambda: True)
    monkeypatch.setattr(lite_app_operations, "_route_health_ready", lambda: True)
    monkeypatch.setattr(lite_app_operations, "_caddy_route_status", lambda: ("passed", {"caddyfile_checked": True, "prefix_preserved": True}))
    monkeypatch.setattr(lite_app_operations, "_refresh_caddy_route_if_safe", lambda route_needs_refresh: ("skipped", False))
    monkeypatch.setattr(lite_app_operations, "_restart_photoprism_if_safe", lambda health_failed: ("skipped", False))

    command = lite_app_operations.command_for_operation("photoprism", "repair_app", reason="unit repair")
    lite_app_operations.record_queued_operation(command)
    result = lite_app_operations.execute_repair_app(command)
    assert result["status"] in {"succeeded", "review"}

    response = client().get("/api/lite/apps/photoprism/evidence")
    assert response.status_code == 200
    latest = response.json()["latest"]
    assert latest["action_id"] == "repair_app"
    assert latest["backend_trace"]["execution_owner"] == "Backend worker"
    assert "duplicate_events_hidden" in latest["backend_trace"]
    proof_ids = {item["id"] for item in latest["proofs"]}
    assert {
        "backend_worker_executed",
        "frontend_no_shell",
        "repair_bounded",
        "media_preserved",
        "app_route_checked",
        "storage_mapping_checked",
        "app_health_checked",
        "no_destructive_changes",
        "secrets_hidden",
    }.issubset(proof_ids)
    assert any("No photos were deleted" in item for item in latest["what_did_not_happen"])
    assert latest["technical_details"]["destructive_changes"] is False
    assert latest["technical_details"]["app_login_changed"] is False
    assert latest["technical_details"]["database_reset"] is False
    text = response.text.lower()
    assert "/data/data" not in text
    assert "password=" not in text
    assert "token=" not in text


def test_lite_app_operations_reconcile_stale_running(monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.services import lite_app_operations

    monkeypatch.setattr(lite_app_operations, "STALE_OPERATION_SECONDS", 0)
    command = lite_app_operations.command_for_operation("photoprism", "check_app", reason="stale test")
    queued = lite_app_operations.record_queued_operation(command)
    state = deps.core.read_json_file(deps.settings().state_dir / "lite_app_operations.json", {})
    op = state["operations"][queued["operation_id"]]
    op["status"] = "running"
    op["started_at"] = "2020-01-01T00:00:00Z"
    deps.core.write_json_file(deps.settings().state_dir / "lite_app_operations.json", state)

    status = lite_app_operations.app_operation_status("photoprism")
    assert status["last_safety_check"]["status"] == "review"
    assert "did not fake success" in json.dumps(status).lower()


def test_lite_app_safety_repair_frontend_source_is_mobile_safe():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    mocks = Path("src/mocks/handlers.js").read_text()
    assert "Check PhotoPrism health, route, storage, and safety record." in ui
    assert "Fix PhotoPrism route, health, and storage connection safely." in ui
    assert "Checking safely" in ui
    assert "Checking repair" in ui
    assert "LiteActionProgress" in ui
    assert "lite-action-progress" in css
    assert "prefers-reduced-motion" in css
    assert "check_app" in mocks
    assert "repair_app" in mocks
    forbidden = "".join([ui, mocks]).lower()
    assert "index photos" not in forbidden
    assert "refresh library" not in forbidden
    assert "stop photo" not in forbidden
    assert "child_process" not in forbidden
    assert "nats.connect" not in forbidden
    assert "exec(" not in forbidden


def test_lite_app_actions_phase5_unified_contract(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    response = client().get("/api/lite/apps/photoprism/actions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert "action_groups" in payload
    assert "action_list" in payload
    actions = payload["actions"]
    expected_actions = {
        "open",
        "connect_photos",
        "import_photos",
        "check_app",
        "repair_app",
        "backup_app",
        "preview_restore",
        "backup_to_storage",
        "update_app",
    }
    assert expected_actions.issubset(actions)
    forbidden_actions = {"index_photos", "refresh_library", "cancel_media", "stop_photo"}
    assert forbidden_actions.isdisjoint(actions)
    for action_id, action in actions.items():
        assert action["id"] == action_id
        assert action["app_id"] == "photoprism"
        assert action["label"]
        assert action["category"] in {"access", "media", "safety", "recovery", "setup", "danger"}
        assert isinstance(action["enabled"], bool)
        assert action["status"] in {"ready", "queued", "running", "succeeded", "review", "failed", "blocked", "not_ready", "not_supported", "connected", "imported"}
        assert action["summary"]
        assert action["risk"] in {"low", "review", "high", "destructive"}
        assert action["execution_owner"] in {"browser_navigation", "fastapi", "backend_worker"}
        assert isinstance(action["progress"], dict)
        assert {"phase", "step", "indeterminate", "steps"}.issubset(action["progress"])
        assert isinstance(action["result"], dict)
        assert isinstance(action["details"], dict)
        assert isinstance(action["troubleshooting"], dict)
        assert "first_ran_at" in action
        assert "last_ran_at" in action
        assert "run_count" in action
        assert action["run_count"] is None or isinstance(action["run_count"], int)
        assert action["details"]["saved_for_troubleshooting"]["backend_only"] is True
        if action["enabled"] is False:
            assert action["disabled_reason"]
    assert actions["update_app"]["summary"].lower().count("no update") >= 1
    text = response.text.lower()
    for forbidden in ("password", "token", "api_key", "private_key", "nats://", "/data/data", "restic-password", "caddyfile", "pm2"):
        assert forbidden not in text


def test_lite_app_actions_phase5_disabled_response_shape(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    response = client().post(
        "/api/lite/apps/photoprism/actions/import_photos",
        json={"reason": "manual import without mapping"},
    )
    assert response.status_code == 409
    payload = response.json().get("detail") or response.json()
    assert payload["status"] == "disabled"
    assert payload["accepted"] is False
    assert payload["action_id"] == "import_photos"
    assert payload["disabled_reason"] == payload["summary"]
    assert payload["progress"]["phase"] == "blocked"
    assert payload["troubleshooting"]["status"] == "not_started"
    assert payload["troubleshooting"]["backend_only"] is True
    text = response.text.lower()
    for forbidden in ("password", "token", "nats://", "/data/data", "raw log"):
        assert forbidden not in text


def test_lite_app_catalog_phase5_unified_action_ui_source():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    for marker in (
        "normalizeAppAction",
        "groupAppActions",
        "getActionDisplayState",
        "AppActionGroup",
        "lite-app-action-row",
        "actionRowStateLabel",
        "AppActionResultCard",
        "AppActionDetailsButton",
        "AppActionDetailsPanel",
        "AppActionDisabledReason",
        "LiteActionProgress",
        "lite-catalog-action-groups",
        "lite-catalog-manage-sheet",
        "lite-catalog-summary-panel",
        "Details",
        "No update was applied",
    ):
        assert marker in ui
    for marker in (
        "lite-app-action-group",
        "lite-app-action-group.is-safety",
        "[data-lite-manage-portal=\"true\"] .lite-app-action-group.is-safety",
        "rgba(16, 185, 129",
        "lite-app-action-result-card",
        "lite-app-action-details-button",
        "lite-app-action-details-panel",
        "lite-action-progress",
        "lite-action-progress__rail",
        "lite-action-progress__rail-base",
        "lite-action-progress__rail-fill",
        "lite-action-progress__rail-pulse",
        "lite-action-progress__nodes",
        "lite-action-progress__stage",
        "lite-action-progress--signal",
        "lite-action-progress--vault",
        "lite-action-progress--preview",
        "lite-action-progress--readiness",
        "lite-action-progress--media",
        "lite-action-progress--saved_state",
        "lite-action-progress__meta",
        "prefers-reduced-motion",
    ):
        assert marker in css
    for old_marker in (
        "lite-action-progress__track",
        "lite-action-progress__head",
        "lite-action-progress__segments",
        "lite-action-progress__segment",
        "liteActionProgressHeadGlow",
        "liteActionProgressHeadSettle",
    ):
        assert old_marker not in css
    for removed_marker in (
        "AppActionFlowAnimation",
        "lite-app-action-flow",
        "liteAppActionCommandDispatch",
        "liteAppActionWorkerClaim",
        "liteAppActionReceiptStamp",
    ):
        assert removed_marker not in ui
        assert removed_marker not in css
    assert "Index photos" not in ui
    assert "Refresh library" not in ui
    assert "Stop photo" not in ui
    assert "nats.connect" not in ui
    assert "exec(" not in ui




def test_lite_app_catalog_connect_photos_truthful_connected_state():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    backend = Path("pocket-lab-final-structure/runtime/api_fastapi/services/lite_app_actions.py").read_text()
    for marker in (
        "phoneStorageConnected",
        "actionSnapshot?.media",
        "actionSnapshot?.actions?.connect_photos",
        "refreshAppActions('photoprism')",
        "isPhoneStorageConnected",
        "PhoneStorageConnectedFolders",
        "Connected folders from Phone Storage",
        "Android shared storage",
        "Camera photos",
        "Pictures",
        "Videos",
        "Downloads",
        "Music",
        "entry.actionId !== 'connect_photos' && detailsActionId === entry.actionId",
        "!isSimpleMediaShortcut ? (",
        "category === 'access') return",
    ):
        assert marker in ui
    for marker in (
        "lite-catalog-connected-folders",
        "lite-catalog-connected-folder-list",
    ):
        assert marker in css
    assert "Phone storage is already connected" in ui
    assert "status: isPhoneStorageConnected ? 'connected'" in ui
    assert "_apply_connect_photos_truth" in backend
    assert "Phone storage is already connected." in backend
    assert "lite-app-action-group is-access" not in ui


def test_lite_app_catalog_import_photos_truthful_imported_state():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    backend = Path("pocket-lab-final-structure/runtime/api_fastapi/services/lite_app_actions.py").read_text()
    for marker in (
        "photosAlreadyImported",
        "actionSnapshot?.actions?.import_photos",
        "isPhotosImported",
        "Photos are imported. PhotoPrism will handle new photos.",
        "entry.actionId === 'import_photos' && isPhotosImported",
        "isSimpleMediaShortcut",
    ):
        assert marker in ui
    for marker in (
        "_apply_import_photos_truth",
        "_media_import_completed",
        '"status": "imported"',
        "PhotoPrism will handle new photos",
    ):
        assert marker in backend
    assert "lite-catalog-media-note" in css

def test_lite_app_catalog_reusable_action_progress_source():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    progress = Path("src/lite/LiteActionProgress.jsx").read_text()
    for marker in (
        "Request accepted",
        "Details saved",
        "Paused for safety",
        "Needs review",
        "Checking PhotoPrism",
        "Route checked",
        "Health checked",
        "Saving app records",
        "Verifying backup",
        "Preparing restore preview",
        "No changes made",
        "Checking update readiness",
        "Readiness saved",
        "No update was applied",
        "activeStageForSteps",
        "progressPercentForSteps",
        "backendProgressSteps",
    ):
        assert marker in progress
    for old_marker in (
        "lite-action-progress__head",
        "segmentedStageIndex",
        "segmentedProgressPercentForState",
        "isSegmentedAction",
    ):
        assert old_marker not in progress
    assert "<LiteActionProgress" in ui
    assert "lite-catalog-media-flow" in ui
    assert "lite-catalog-media-flow" in css
    assert "prefers-reduced-motion" in css
    forbidden = "".join([ui, progress]).lower()
    assert "index photos" not in forbidden
    assert "refresh library" not in forbidden
    assert "stop photo" not in forbidden
    assert "nats.connect" not in forbidden
    assert "child_process" not in forbidden
    assert "exec(" not in forbidden


def test_lite_app_evidence_exposes_latest_receipt_and_by_action(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_update

    command = lite_app_update.update_command("photoprism", reason="manual update readiness check")
    result = lite_app_update.create_update_readiness(command)
    response = client().get("/api/lite/apps/photoprism/evidence")
    assert response.status_code == 200
    payload = response.json()
    assert payload["receipt"]["action_id"] == "update_app"
    assert payload["receipt_id"] == result["operation_id"]
    assert payload["action_id"] == "update_app"
    assert payload["evidence_ref"].startswith("apps/photoprism/update/")
    assert payload["backend_only"] is True
    assert payload["debug_only"] is True
    assert payload["normal_ui_dependency"] is False
    assert payload["by_action"]["update_app"]["receipt_id"] == result["operation_id"]
    assert payload["latest_by_action"]["update_app"]["proofs"]
    assert payload["by_action"]["open"]["backend_trace"]["execution_owner"] == "Browser navigation"
    assert payload["by_action"]["remove_app"]["backend_trace"]["summary"]
    assert "password" not in response.text.lower()
    assert "nats://" not in response.text.lower()


def test_lite_app_update_status_exposes_latest_receipt_id(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_update

    command = lite_app_update.update_command("photoprism", reason="manual update readiness check")
    result = lite_app_update.create_update_readiness(command)
    response = client().get("/api/lite/apps/photoprism/update")
    assert response.status_code == 200
    payload = response.json()
    assert payload["latest_operation_id"] == result["operation_id"]
    assert payload["latest_receipt_id"] == result["operation_id"]
    assert payload["latest_evidence_ref"] == result["evidence_ref"]
    assert payload["latest_receipt"]["action_id"] == "update_app"
    assert payload["latest_receipt"]["proofs"]
    assert "No update was applied" in response.text or "No update was installed" in response.text


def test_lite_app_actions_surface_backup_preview_and_update_receipt_links(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_lifecycle, lite_app_update

    def fake_backup_payload():
        return {
            "status": "ready",
            "summary": "App backup ready.",
            "latest_backup": {
                "backup_id": "app-backup-photoprism-test",
                "verification_status": "verified",
                "status": "verified",
                "evidence_ref": "apps/photoprism/backups/app-backup-photoprism-test.json",
            },
            "latest_restore_preview": {
                "preview_id": "app-restore-preview-photoprism-test",
                "backup_id": "app-backup-photoprism-test",
                "status": "ready",
                "summary": "Restore preview ready. This phase is preview-only and will not change app state.",
                "evidence_ref": "apps/photoprism/restore-previews/app-restore-preview-photoprism-test.json",
            },
            "restore": {
                "preview_available": True,
                "restore_available": False,
                "restore_apply_supported": False,
                "preview_only": True,
            },
        }

    monkeypatch.setattr(lite_app_lifecycle, "_backup_payload", fake_backup_payload)
    command = lite_app_update.update_command("photoprism", reason="manual update readiness check")
    update_result = lite_app_update.create_update_readiness(command)

    response = client().get("/api/lite/apps/photoprism/actions")
    assert response.status_code == 200
    actions = response.json()["actions"]
    assert actions["backup_app"]["troubleshooting"]["available"] is True
    assert actions["backup_app"]["troubleshooting"]["receipt_id"] == "app-backup-photoprism-test"
    assert actions["backup_app"]["details"]["saved_for_troubleshooting"]["backend_only"] is True
    assert actions["preview_restore"]["troubleshooting"]["available"] is True
    assert actions["preview_restore"]["troubleshooting"]["receipt_id"] == "app-restore-preview-photoprism-test"
    assert actions["preview_restore"]["details"]["saved_for_troubleshooting"]["backend_only"] is True
    assert actions["update_app"]["troubleshooting"]["available"] is True
    assert actions["update_app"]["troubleshooting"]["receipt_id"] == update_result["operation_id"]
    assert actions["update_app"]["details"]["saved_for_troubleshooting"]["backend_only"] is True
    assert "password" not in response.text.lower()
    assert "nats://" not in response.text.lower()


def test_lite_app_preview_restore_waits_for_current_backup(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_backup

    command = lite_app_backup.app_backup_command("photoprism", reason="manual backup before preview")
    lite_app_backup.record_backup_request(command)

    actions_response = client().get("/api/lite/apps/photoprism/actions")
    assert actions_response.status_code == 200
    preview = actions_response.json()["actions"]["preview_restore"]
    assert preview["enabled"] is False
    assert preview["status"] in {"running", "not_ready", "blocked"}
    assert "current app backup" in preview["disabled_reason"].lower()

    run_response = client().post(
        "/api/lite/apps/photoprism/actions/preview_restore",
        json={"reason": "do not preview stale backup"},
    )
    assert run_response.status_code == 409
    payload = run_response.json().get("detail") or run_response.json()
    assert payload["status"] in {"disabled", "backup_still_running"}
    assert "current app backup" in (payload.get("disabled_reason") or payload.get("summary") or "").lower()
    assert "password" not in run_response.text.lower()
    assert "nats://" not in run_response.text.lower()


def test_lite_app_catalog_details_selection_is_action_specific():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    assert "detailsActionId" in ui
    assert "openActionDetails(entry.actionId, app.id || 'photoprism')" in ui
    assert "detailsActionId === entry.actionId" in ui
    assert "lite-catalog-action-details-anchor" in ui
    assert "AppActionDetailsPanel" in ui
    assert "Hide details" in ui
    assert "Saved for troubleshooting" in ui
    assert "lite-app-action-details-panel" in css
    assert "lite-app-action-detail-section--run-history" in css
    assert "liteEvidenceBorderRailOrbit" not in ui
    assert "liteEvidenceRailPerimeterFlow" not in ui
    assert "Hide receipt" not in ui


def test_lite_app_catalog_details_prefer_fresh_action_state():
    ui = _lite_ui_source()
    progress = Path("src/lite/LiteActionProgress.jsx").read_text()
    for marker in (
        "refreshAppActions",
        "liteApi.appActions",
        "normalizeAppActionsPayload",
        "actionFromSnapshot",
        "actionSnapshots",
        "bestResultForAction",
        "detailsForAction",
        "last_result",
        "Run history",
        "formatRunHistoryValue",
        "has_run_evidence",
        "Run count",
    ):
        assert marker in ui
    assert "detailsAvailable ||" not in progress
    assert "hasRunEvidence" in progress
    assert "Not run yet" in progress
    assert "Details saved" in progress
    assert "No backend run needed" in progress
    assert "Reconnect to continue" in progress


def test_lite_app_update_receipt_technical_details_show_versions(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_update

    monkeypatch.setattr(
        lite_app_update,
        "_photoprism_status_payload",
        lambda: {"status": "operational", "version": "240711-e1280b2fb"},
    )
    monkeypatch.setenv("POCKETLAB_PHOTOPRISM_LATEST_VERSION", "240712-future")
    command = lite_app_update.update_command("photoprism", reason="manual update readiness check")
    result = lite_app_update.create_update_readiness(command)
    receipt = lite_app_update.update_receipt("photoprism", result["operation_id"])
    details = receipt["technical_details"]
    assert details["current_version"] == "240711-e1280b2fb"
    assert details["latest_version"] == "240712-future"
    assert details["update_available"] == "Yes"
    assert "current_version_status" not in details
    assert "latest_version_status" not in details


def test_lite_app_update_status_exposes_receipt_aliases(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_update

    command = lite_app_update.update_command("photoprism", reason="manual update readiness check")
    result = lite_app_update.create_update_readiness(command)
    payload = lite_app_update.update_status("photoprism")
    assert payload["latest_operation_id"] == result["operation_id"]
    assert payload["operation_id"] == result["operation_id"]
    assert payload["latest_receipt_id"] == result["operation_id"]
    assert payload["receipt_id"] == result["operation_id"]
    assert payload["latest_evidence_ref"] == result["evidence_ref"]
    assert payload["evidence_ref"] == result["evidence_ref"]
    assert payload["receipt"]["action_id"] == "update_app"


def test_photoprism_action_e2e_script_waits_for_backup_before_preview():
    script = Path("scripts/dev/check-photoprism-app-actions-e2e.sh").read_text()
    assert "wait_for_backup_completion" in script
    assert "Skipping Preview restore because the current backup has not completed yet" in script
    assert "BASH" not in script.splitlines()[-1:]


def test_lite_app_check_details_report_stopped_app_without_repair(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_actions, lite_app_operations

    monkeypatch.setattr(lite_app_operations, "_pm2_process_online", lambda: "offline")
    monkeypatch.setattr(lite_app_operations, "_local_health_ready", lambda: False)
    monkeypatch.setattr(lite_app_operations, "_route_health_ready", lambda: False)
    monkeypatch.setattr(lite_app_operations, "_route_registry_status", lambda: ("passed", {"present": True, "route_path": "/apps/photoprism/"}))
    monkeypatch.setattr(lite_app_operations, "_caddy_route_status", lambda: ("passed", {"caddyfile_checked": True, "prefix_preserved": True}))
    monkeypatch.setattr(lite_app_operations, "_storage_status", lambda: ("passed", {"mapping_count": 1, "read_only": True, "pending_apply": False}))
    monkeypatch.setattr(lite_app_operations, "_backup_status", lambda: ("passed", {"config_backup_available": True}))
    monkeypatch.setattr(lite_app_operations, "_security_ref_status", lambda: ("passed", {"security_evidence_ref": "security/evidence/latest/summary.json"}))

    command = lite_app_operations.command_for_operation("photoprism", "check_app", reason="unit stopped check")
    lite_app_operations.record_queued_operation(command)
    result = lite_app_operations.execute_check_app(command)
    assert result["status"] == "review"

    action = lite_app_actions.app_actions("photoprism")["actions"]["check_app"]
    details = action["details"]
    assert action["last_result"] == "Something changed"
    assert any("not running" in item.lower() for item in details["what_happened"])
    assert any("check only" in item.lower() for item in details["what_changed"])
    assert any("stopped" in item.lower() for item in details.get("what_needs_attention", []))
    assert any("repair" in item.lower() for item in details["what_did_not_happen"])


def test_lite_app_repair_details_report_restart_and_online_after(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_actions, lite_app_operations

    local_health = iter([False, True])
    route_health = iter([False, True])
    monkeypatch.setattr(lite_app_operations, "_local_health_ready", lambda: next(local_health))
    monkeypatch.setattr(lite_app_operations, "_route_health_ready", lambda: next(route_health))
    monkeypatch.setattr(lite_app_operations, "_route_registry_status", lambda: ("passed", {"present": True, "route_path": "/apps/photoprism/"}))
    monkeypatch.setattr(lite_app_operations, "_caddy_route_status", lambda: ("passed", {"caddyfile_checked": True, "prefix_preserved": True}))
    monkeypatch.setattr(lite_app_operations, "_refresh_caddy_route_if_safe", lambda route_needs_refresh: ("skipped", False))
    monkeypatch.setattr(lite_app_operations, "_repair_storage_if_safe", lambda storage_detail: ("passed", False, {"mapping_count": 1, "pending_apply": False}))
    monkeypatch.setattr(lite_app_operations, "_restart_photoprism_if_safe", lambda health_failed: ("changed", True))

    command = lite_app_operations.command_for_operation("photoprism", "repair_app", reason="unit stopped repair")
    lite_app_operations.record_queued_operation(command)
    result = lite_app_operations.execute_repair_app(command)
    assert result["status"] == "succeeded"
    assert result["summary"] == "Repair completed"

    action = lite_app_actions.app_actions("photoprism")["actions"]["repair_app"]
    details = action["details"]
    assert action["last_result"] == "Repair completed"
    assert any("started it again" in item.lower() or "started" in item.lower() for item in details["what_happened"])
    assert "PhotoPrism was restarted." in details["what_changed"]
    assert "PhotoPrism is now online." in details["what_changed"]
    assert "No photos were changed." in details["what_did_not_happen"]
    assert "No database was changed." in details["what_did_not_happen"]


def test_lite_app_action_details_panel_can_show_needs_attention_section():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    assert "what_needs_attention" in ui
    assert "What needs attention" in ui
    assert "lite-app-action-detail-section--attention" in ui
    assert "lite-app-action-detail-section--attention" in css


def test_lite_app_repair_review_reconciles_after_stable_check(monkeypatch):
    _force_photoprism_installed_for_action_tests(monkeypatch)
    ensure_runtime_path()
    from api_fastapi.services import lite_app_actions, lite_app_operations

    monkeypatch.setattr(lite_app_operations, "_installed_from_catalog", lambda app: True)
    repair_local = iter([False, False])
    repair_route = iter([False, False])
    monkeypatch.setattr(lite_app_operations, "_local_health_ready", lambda: next(repair_local))
    monkeypatch.setattr(lite_app_operations, "_route_health_ready", lambda: next(repair_route))
    monkeypatch.setattr(lite_app_operations, "_route_registry_status", lambda: ("passed", {"present": True, "route_path": "/apps/photoprism/"}))
    monkeypatch.setattr(lite_app_operations, "_caddy_route_status", lambda: ("passed", {"caddyfile_checked": True, "prefix_preserved": True}))
    monkeypatch.setattr(lite_app_operations, "_refresh_caddy_route_if_safe", lambda route_needs_refresh: ("skipped", False))
    monkeypatch.setattr(lite_app_operations, "_repair_storage_if_safe", lambda storage_detail: ("passed", False, {"mapping_count": 1, "pending_apply": False}))
    monkeypatch.setattr(lite_app_operations, "_restart_photoprism_if_safe", lambda health_failed: ("changed", True))
    monkeypatch.setattr(lite_app_operations, "_wait_for_photoprism_health", lambda: (False, False))

    repair_command = lite_app_operations.command_for_operation("photoprism", "repair_app", reason="unit early repair")
    lite_app_operations.record_queued_operation(repair_command)
    repair_result = lite_app_operations.execute_repair_app(repair_command)
    assert repair_result["status"] == "review"

    monkeypatch.setattr(lite_app_operations, "_pm2_process_online", lambda: "online")
    monkeypatch.setattr(lite_app_operations, "_local_health_ready", lambda: True)
    monkeypatch.setattr(lite_app_operations, "_route_health_ready", lambda: True)
    monkeypatch.setattr(lite_app_operations, "_storage_status", lambda: ("passed", {"mapping_count": 1, "read_only": True, "pending_apply": False}))
    monkeypatch.setattr(lite_app_operations, "_backup_status", lambda: ("passed", {"config_backup_available": True}))
    monkeypatch.setattr(lite_app_operations, "_security_ref_status", lambda: ("passed", {"security_evidence_ref": "security/evidence/latest/summary.json"}))

    check_command = lite_app_operations.command_for_operation("photoprism", "check_app", reason="unit stable check")
    lite_app_operations.record_queued_operation(check_command)
    check_result = lite_app_operations.execute_check_app(check_command)
    assert check_result["status"] == "succeeded"

    action = lite_app_actions.app_actions("photoprism")["actions"]["repair_app"]
    assert action["last_result"] == "Repair completed"
    assert action["details"]["last_result"] == "Repair completed"
    assert not action["details"].get("what_needs_attention")
    assert "PhotoPrism is now online." in action["details"]["what_changed"]


def test_lite_app_action_details_filters_hidden_placeholder():
    ui = _lite_ui_source()
    assert "item.toLowerCase() !== 'hidden'" in ui
    assert "No app login was changed." in Path("pocket-lab-final-structure/runtime/api_fastapi/services/lite_app_operations.py").read_text()
    assert "No app password was changed." not in Path("pocket-lab-final-structure/runtime/api_fastapi/services/lite_app_operations.py").read_text()
    assert "lite-app-action-details-panel is-" in ui


def test_lite_app_catalog_safe_micro_interaction_source_is_scoped():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    motion = Path("src/lite/LiteMotion.jsx").read_text()

    assert "LitePressableButton" in ui
    assert "LiteElevationSurface" in ui
    assert "useLiteRipple" in ui
    assert "triggerLiteTactileFeedback('selection')" in ui
    assert "haptic={!isDisabled}" in ui
    assert "App Catalog safe micro-interaction primitives" in css
    assert "[data-lite-manage-portal=\"true\"] .lite-motion-ripple" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "navigator.vibrate" in motion
    assert "pointer-events: none" in css
    assert "useDrag" not in motion
    assert "shell" not in motion.lower()
    assert "nats" not in motion.lower()

def test_lite_app_catalog_action_row_polish_source_is_scoped():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    motion = Path("src/lite/LiteMotion.jsx").read_text()

    assert "LiteMotionReveal" in ui
    assert "LiteProgressMorphPanel" in ui
    assert "settle" in ui
    assert "lite-app-action-progress-motion" in ui
    assert "App Catalog action row polish" in css
    assert "lite-action-row-progress-reveal" in css
    assert "lite-action-row-disabled-reveal" in css
    assert "lite-action-row-result-settle" in css
    assert "[data-lite-manage-portal=\"true\"] .lite-motion-progress-morph" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "export function LiteMotionReveal" in motion
    assert "export function LiteProgressMorphPanel" in motion
    assert "useDrag" not in motion
    assert "shell" not in motion.lower()
    assert "nats" not in motion.lower()

def test_lite_app_catalog_contextual_action_animation_source_is_scoped():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    motion = Path("src/lite/LiteMotion.jsx").read_text()

    assert "LiteContextualActionCue" in ui
    assert "LiteContextualActionCue" in motion
    assert "liteContextualActionKind" in motion
    assert "data-action-kind={kind}" in motion
    assert 'aria-hidden="true"' in motion
    assert "pointer-events: none" in css
    assert "App Catalog contextual action animations" in css
    assert "lite-contextual-photos-pulse" in css
    assert "lite-contextual-shield-sweep" in css
    assert "lite-contextual-vault-seal" in css
    assert "lite-contextual-readiness-conveyor" in css
    assert "lite-contextual-danger-attention" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "useDrag" not in motion
    assert "shell" not in motion.lower()
    assert "nats" not in motion.lower()

def test_lite_app_catalog_flip_shared_continuity_source_is_scoped():
    ui = _lite_ui_source()
    css = Path("src/index.css").read_text()
    motion = Path("src/lite/LiteMotion.jsx").read_text()

    assert "APP_CATALOG_FLIP_SHARED_CONTINUITY_IS_PRESENTATION_ONLY" in ui
    assert "LiteFlipGroup" in ui
    assert "LiteSharedElementCue" in ui
    assert "data-lite-flip-key" in ui
    assert "card-to-sheet" in ui
    assert "row-to-details" in ui
    assert "export function useLiteFlipList" in motion
    assert "export function LiteFlipGroup" in motion
    assert "export function LiteSharedElementCue" in motion
    assert "node.animate" in motion
    assert "data-shared-motion=\"visual-clone-only\"" in motion
    assert "App Catalog FLIP and shared visual continuity" in css
    assert "lite-motion-flip-item" in css
    assert "lite-shared-element-cue" in css
    assert "pointer-events: none" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "lite-card-to-sheet-glow" in css
    assert "lite-card-to-sheet-arrival" in css
    assert "lite-shared-element-cue__wake" in motion
    assert "lite-shared-element-cue__arrival" in motion
    assert "useDrag" not in motion
    assert "shell" not in motion.lower()
    assert "nats" not in motion.lower()



def test_lite_app_catalog_refresh_and_icon_source_is_scoped():
    catalog = _lite_catalog_source()
    ui = Path("src/lite/LiteUi.jsx").read_text()
    css = Path("src/index.css").read_text()

    assert "Install to phone" not in catalog
    assert "installAppToPhone" not in catalog
    assert "canInstallAppToPhone" not in catalog
    assert "LiteSavedStateBanner()" in ui
    assert "return null;" in ui
    assert "LiteRefreshButton" in ui
    assert "lite-refresh-status-popover" in ui
    assert "lite-saved-state-banner" not in catalog
    assert "PlugZap" in catalog
    assert "ImageUp" in catalog
    assert "DatabaseBackup" in catalog
    assert "RotateCcw" in catalog
    assert "Toolbox" in catalog
    assert "Megaphone" in catalog
    assert "lite-catalog-action-lucide" in catalog
    assert "liteCatalogActionIconPop" in css
    assert "lite-refresh-control" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_lite_tanstack_query_dependency_and_provider_source():
    package = json.loads(Path("package.json").read_text())
    app = Path("src/lite/LiteApp.jsx").read_text()
    query_client = Path("src/lib/liteQueryClient.js").read_text()

    assert "@tanstack/react-query" in package["dependencies"]
    assert "QueryClientProvider" in app
    assert "liteQueryClient" in app
    assert "createLiteQueryClient" in query_client
    assert "refetchOnReconnect: true" in query_client
    assert "refetchOnWindowFocus: true" in query_client
    assert "retry: false" in query_client
    assert "refetchInterval: false" in query_client


def test_lite_central_polling_policy_phase1_source():
    policy = Path("src/lib/litePollingPolicy.js").read_text()
    hook = Path("src/hooks/useLiteQuery.js").read_text()
    status_hook = Path("src/hooks/useLiteStatus.js").read_text()
    query_client = Path("src/lib/liteQueryClient.js").read_text()

    assert "LITE_CENTRAL_POLLING_POLICY" in policy
    assert "realtime: 2_000" in policy
    assert "active: 5_000" in policy
    assert "normal: 15_000" in policy
    assert "relaxed: 30_000" in policy
    assert "slow: 60_000" in policy
    assert "background: false" in policy
    assert "isLiteLiveStatus" in policy
    assert "hasLiteLiveOperation" in policy
    assert "liteVisiblePollingInterval" in policy
    assert "liteQueryPollingInterval" in policy
    assert "litePollingBackoffInterval" in policy
    assert "litePollingModeFromValue" in policy
    assert "document.visibilityState" in policy

    assert "hasLiteLiveOperation" in hook
    assert "useLiteDocumentVisibility" in hook
    assert "pollingMode = 'normal'" in hook
    assert "enabledWhenHidden = false" in hook
    assert "refetchInterval: resolvedRefetchInterval" in hook
    assert "refetchIntervalInBackground: Boolean(enabledWhenHidden)" in hook
    assert "refetchOnWindowFocus" in hook
    assert "refetchOnReconnect" in hook
    assert "liteQueryPollingInterval" in hook
    assert "failureCount: queryState?.state?.failureCount || 0" in hook
    assert "savedState: isSavedSnapshot(data)" in hook
    assert "setInterval" not in hook

    assert "litePollingIntervals" in status_hook
    assert "pollingMode: 'relaxed'" in status_hook
    assert "Math.max(litePollingIntervals.relaxed, intervalMs)" in status_hook
    assert "refetchInterval: false" in query_client


def test_lite_use_lite_query_phase2_adaptive_polling_source():
    hook = Path("src/hooks/useLiteQuery.js").read_text()
    policy = Path("src/lib/litePollingPolicy.js").read_text()

    assert "pollingMode = 'normal'" in hook
    assert "enabledWhenHidden = false" in hook
    assert "refetchOnWindowFocus = true" in hook
    assert "refetchOnReconnect = true" in hook
    assert "typeof refetchInterval === 'function'" in hook
    assert "liteQueryPollingInterval" in hook
    assert "failureCount: queryState?.state?.failureCount || 0" in hook
    assert "savedState: isSavedSnapshot(data)" in hook
    assert "refetchIntervalInBackground: Boolean(enabledWhenHidden)" in hook
    assert "setInterval" not in hook

    assert "litePollingBackoffInterval" in policy
    assert "liteQueryPollingInterval" in policy
    assert "if (!visible && !enabledWhenHidden) return litePollingIntervals.off" in policy
    assert "if (live) return litePollingIntervals.realtime" in policy
    assert "return litePollingIntervals.slow" in policy


def test_lite_query_wrapper_keeps_safe_snapshot_fallback_source():
    hook = Path("src/hooks/useLiteQuery.js").read_text()
    snapshots = Path("src/lib/liteSafeSnapshots.js").read_text()

    assert "useQuery" in hook
    assert "readLiteSnapshot" in hook
    assert "writeLiteSnapshot" in hook
    assert "attachFreshSnapshotMeta" in hook
    assert "isSafeLiteSnapshotPath" in hook
    assert "isUnsafeLiteSnapshotRequest" in hook
    assert "bootstrap|invite|token|secret|password|evidence|receipt|debug|raw" in hook
    assert "UNSAFE_KEY_PATTERN" in snapshots
    assert "SAFE_LITE_GET_ENDPOINTS" in snapshots
    assert "/api/lite/apps/photoprism/actions" in snapshots


def test_lite_mutation_wrapper_invalidates_after_fastapi_acceptance_source():
    hook = Path("src/hooks/useLiteMutation.js").read_text()

    assert "useMutation" in hook
    assert "isAcceptedLiteMutationResponse" in hook
    assert "invalidateQueries" in hook
    assert "retry: false" in hook
    assert "LITE_BROWSER_ACTION_QUEUE_DISABLED" in hook
    assert "import_photos" in hook
    assert "restart_agent" in hook
    assert "add_device" in hook
    assert "localStorage" not in hook
    assert "queueMicrotask" not in hook


def test_lite_safe_reads_use_query_backed_resource_source():
    status_hook = Path("src/hooks/useLiteStatus.js").read_text()
    catalog = _lite_catalog_source()

    assert "useLiteQuery" in status_hook
    assert "liteQueryKeys.status()" in status_hook
    assert "liteQueryKeys.catalog()" in status_hook
    assert "liteQueryKeys.fleet()" in status_hook
    assert "liteQueryKeys.security()" in status_hook
    assert "liteQueryKeys.recovery()" in status_hook
    assert "useState" not in status_hook
    assert "setInterval" not in status_hook
    assert "useLiteQuery" in catalog
    assert "liteQueryPaths.appActions('photoprism')" in catalog
    assert "useLiteMutation" in catalog
    assert "liteMutationInvalidations" in catalog


def test_lite_tanstack_phase_preserves_app_catalog_safety_markers():
    catalog = _lite_catalog_source()
    ui = Path("src/lite/LiteUi.jsx").read_text()
    vite = Path("vite.config.js").read_text()

    assert "APP_CATALOG_MANAGE_SHEET_PORTAL_OVERLAY" in catalog
    assert "APP_CATALOG_PRIMARY_ACTIONS_OWN_CLICKS" in catalog
    assert "APP_CATALOG_ACTION_ROWS_OWN_CLICKS" in catalog
    assert "AppActionDetailsPanel" in catalog
    assert "resolveAppOpenUrl" in catalog
    assert "window.location.assign(target)" in catalog
    assert "LiteSavedStateBanner()" in ui
    assert "return null;" in ui
    assert "lite-refresh-status-popover" in ui
    assert "navigateFallbackDenylist" in vite
    assert "safeLiteReadApiPattern" in vite
    assert "apps" in vite
    assert "bootstrap" not in vite.lower()


def test_lite_dexie_dependency_and_offline_db_source():
    package = json.loads(Path("package.json").read_text())
    offline_db = Path("src/lib/liteOfflineDb.js").read_text()

    assert "dexie" in package["dependencies"]
    assert "from 'dexie'" in offline_db
    assert "pocketlab_lite_safe_snapshots" in offline_db
    assert "safe_snapshots" in offline_db
    assert "snapshot_events" in offline_db
    assert "ui_cache_meta" in offline_db
    assert "version(LITE_OFFLINE_DB_VERSION).stores" in offline_db
    assert "readOfflineSafeSnapshot" in offline_db
    assert "writeOfflineSafeSnapshot" in offline_db
    assert "deleteOfflineSafeSnapshot" in offline_db
    assert "clearOfflineSafeSnapshots" in offline_db
    assert "recordOfflineSnapshotEvent" in offline_db
    assert "setOfflineCacheMeta" in offline_db
    assert "getOfflineCacheMeta" in offline_db
    assert "pruneExpiredOfflineSnapshots" in offline_db
    assert "estimateLiteCacheHealth" in offline_db


def test_lite_safe_snapshots_use_dexie_under_public_api_source():
    snapshots = Path("src/lib/liteSafeSnapshots.js").read_text()

    assert "./liteOfflineDb.js" in snapshots
    assert "readOfflineSafeSnapshot" in snapshots
    assert "writeOfflineSafeSnapshot" in snapshots
    assert "readLiteSnapshot(path" in snapshots
    assert "readLiteSnapshotAsync" in snapshots
    assert "writeLiteSnapshot(path" in snapshots
    assert "hydrateLiteSnapshotsFromDexie" in snapshots
    assert "SAFE_LITE_GET_ENDPOINTS" in snapshots
    assert "LITE_SNAPSHOT_TTL_MS" in snapshots
    assert "expires_at" in snapshots
    assert "expired" in snapshots
    assert "Saved state expired" in snapshots
    assert "lite-saved-state-banner" not in snapshots


def test_lite_dexie_safe_endpoint_allowlist_and_ttl_source():
    snapshots = Path("src/lib/liteSafeSnapshots.js").read_text()

    for endpoint in [
        "/api/lite/status",
        "/api/lite/catalog",
        "/api/lite/apps/photoprism/actions",
        "/api/lite/fleet",
        "/api/lite/security",
        "/api/lite/recovery",
    ]:
        assert endpoint in snapshots

    for unsafe in [
        "/api/lite/fleet/add-device",
        "/api/lite/security/check",
        "/api/lite/recovery/backup",
        "/api/lite/apps/photoprism/evidence",
        "/api/lite/apps/photoprism/actions/import_photos",
        "/api/lite/fleet/agent/bootstrap.sh",
    ]:
        assert unsafe not in snapshots

    assert "5 * 60 * 1000" in snapshots
    assert "20 * 60 * 1000" in snapshots


def test_lite_dexie_snapshot_rejection_guard_source():
    snapshots = Path("src/lib/liteSafeSnapshots.js").read_text()

    assert "findUnsafeLiteSnapshotContent" in snapshots
    assert "isLiteSnapshotPayloadSafe" in snapshots
    assert "markLiteSnapshotRejected" in snapshots
    for forbidden in [
        "token",
        "secret",
        "password",
        "api[_-]?key",
        "credential",
        "private[_-]?key",
        "invite[_-]?token",
        "bootstrap",
        "command[_-]?payload",
        "raw[_-]?log",
        "evidence[_-]?path",
        "private[_-]?path",
        "restic[_-]?password",
        "vault",
        "unseal",
        "bearer",
        "authorization",
        "nats",
    ]:
        assert forbidden in snapshots
    assert "return { stored: false, rejected: true" in snapshots


def test_lite_query_and_api_fall_back_to_dexie_snapshots_source():
    hook = Path("src/hooks/useLiteQuery.js").read_text()
    api = Path("src/lib/liteApi.js").read_text()

    assert "readLiteSnapshotAsync" in hook
    assert "markLiteSnapshotBackendUnreachable" in hook
    assert "isExpired" in hook
    assert "Saved state expired. Reconnect to continue." in hook
    assert "readLiteSnapshotAsync" in api
    assert "markLiteSnapshotBackendUnreachable" in api
    assert "writeLiteSnapshot(path, data)" in api
    assert "attachFreshSnapshotMeta(path, data)" in api


def test_lite_dexie_phase_preserves_no_browser_action_queue_and_pwa_denylist_source():
    mutation = Path("src/hooks/useLiteMutation.js").read_text()
    catalog = _lite_catalog_source()
    ui = Path("src/lite/LiteUi.jsx").read_text()
    vite = Path("vite.config.js").read_text()

    assert "LITE_BROWSER_ACTION_QUEUE_DISABLED" in mutation
    assert "retry: false" in mutation
    assert "localStorage" not in mutation
    assert "APP_CATALOG_MANAGE_SHEET_PORTAL_OVERLAY" in catalog
    assert "APP_CATALOG_PRIMARY_ACTIONS_OWN_CLICKS" in catalog
    assert "APP_CATALOG_ACTION_ROWS_OWN_CLICKS" in catalog
    assert "AppActionDetailsPanel" in catalog
    assert "window.location.assign(target)" in catalog
    assert "LiteSavedStateBanner()" in ui
    assert "return null;" in ui
    assert "lite-refresh-status-popover" in ui
    assert "navigateFallbackDenylist" in vite
    assert "safeLiteReadApiPattern" in vite
    assert "apps" in vite


def test_lite_zustand_dependency_and_ui_store_source():
    package = json.loads(Path("package.json").read_text())
    lockfile = json.loads(Path("package-lock.json").read_text())
    store = Path("src/stores/liteUiStore.js").read_text()

    assert "zustand" in package["dependencies"]
    assert "zustand" in lockfile["packages"][""]["dependencies"]
    assert "create } from 'zustand'" in store
    assert "activeTab" in store
    assert "mobileMenuOpen" in store
    assert "moreSheetOpen" in store
    assert "activeOverlay" in store
    assert "openOverlay" in store
    assert "closeAllOverlays" in store
    assert "toasts" in store
    assert "pushToast" in store
    assert "dismissToast" in store
    assert "refreshByScope" in store
    assert "beginRefresh" in store
    assert "finishRefresh" in store
    assert "manageAppId" in store
    assert "activeManageSection" in store
    assert "activeDetailsActionId" in store
    assert "setManageApp" in store
    assert "setManageSection" in store
    assert "LITE_UI_STORE_IS_UI_ONLY" in store


def test_lite_zustand_store_remains_ui_only_source():
    store = Path("src/stores/liteUiStore.js").read_text()

    assert "../lib/liteApi" not in store
    assert "liteApi" not in store
    assert "useLiteQuery" not in store
    assert "useLiteMutation" not in store
    assert "localStorage" not in store
    assert "sessionStorage" not in store
    assert "shell" not in store.lower()
    assert "exec(" not in store
    assert "fetch(" not in store
    assert "browser_action_queue" not in store.lower()
    for forbidden in [
        "deviceStatusTruth",
        "securityTruth",
        "backupTruth",
        "actionResultTruth",
        "commandPayload",
    ]:
        assert forbidden not in store
    for forbidden_lower in ["token", "password", "secret", "api_key", "apikey", "credential", "nats"]:
        assert forbidden_lower not in store.lower()


def test_lite_zustand_toast_and_refresh_are_wired_into_ui_source():
    app = Path("src/lite/LiteApp.jsx").read_text()
    ui = Path("src/lite/LiteUi.jsx").read_text()
    toast_host = Path("src/lite/LiteToastHost.jsx").read_text()
    css = Path("src/index.css").read_text()

    assert "LiteToastHost" in app
    assert "useLiteUiStore" in app
    assert "useLiteUiStore" in ui
    assert "useLiteRefreshFeedback" in ui
    assert "beginRefresh(scope)" in ui
    assert "finishRefresh(scope" in ui
    assert "lite-refresh-status-popover" in ui
    assert "LiteSavedStateBanner()" in ui
    assert "return null;" in ui
    assert "useLiteUiStore" in toast_host
    assert "LITE_TOAST_HOST_USES_ZUSTAND" in toast_host
    assert "lite-toast-host" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_lite_zustand_app_catalog_manage_state_source():
    catalog = _lite_catalog_source()

    assert "useLiteUiStore" in catalog
    assert "state.manageAppId" in catalog
    assert "state.setManageApp" in catalog
    assert "state.clearManageApp" in catalog
    assert "state.activeManageSection" in catalog
    assert "state.setManageSection" in catalog
    assert "state.activeDetailsActionId" in catalog
    assert "state.setActiveDetailsAction" in catalog
    assert "state.clearActiveDetailsAction" in catalog
    assert "setManageAppId" not in catalog
    assert "setDetailsActionId" not in catalog
    assert "APP_CATALOG_MANAGE_SHEET_PORTAL_OVERLAY" in catalog
    assert "APP_CATALOG_PRIMARY_ACTIONS_OWN_CLICKS" in catalog
    assert "APP_CATALOG_ACTION_ROWS_OWN_CLICKS" in catalog
    assert "window.location.assign(target)" in catalog
    assert "data-lite-manage-portal=\"true\"" in catalog
    assert "onClick={closeManageSheet}" in catalog
    assert "openActionDetails" in catalog
    assert "AppActionDetailsPanel" in catalog
    assert "onClickCapture" not in catalog
    assert "browser action queue" not in catalog.lower()


def test_lite_zustand_preserves_safe_snapshot_and_pwa_boundaries_source():
    mutation = Path("src/hooks/useLiteMutation.js").read_text()
    snapshots = Path("src/lib/liteSafeSnapshots.js").read_text()
    vite = Path("vite.config.js").read_text()

    assert "LITE_BROWSER_ACTION_QUEUE_DISABLED" in mutation
    assert "retry: false" in mutation
    assert "SAFE_LITE_GET_ENDPOINTS" in snapshots
    assert "/api/lite/apps/photoprism/actions" in snapshots
    assert "lite-saved-state-banner" not in snapshots
    assert "navigateFallbackDenylist" in vite
    assert "safeLiteReadApiPattern" in vite
    assert "apps" in vite





def test_lite_app_catalog_safety_details_and_flow_panel_styling_source():
    catalog = _lite_catalog_source()
    hook = Path("src/hooks/useLiteAppActionFlow.js").read_text()
    css = Path("src/index.css").read_text()
    assert "lite-catalog-flow-panel" not in catalog
    assert "visible: value !== 'idle' || writeBlocked" in hook
    for marker in (
        ".lite-catalog-action-details-anchor",
        ".lite-app-action-details-head",
        ".lite-app-action-details-status",
        ".lite-app-action-details-grid",
        ".lite-app-action-detail-section",
        ".lite-app-action-technical-details",
        ".lite-app-action-group.is-safety .lite-catalog-action-details-anchor .lite-app-action-details-panel",
        ".lite-app-action-group.is-safety .lite-app-action-details-status strong",
        "rgba(16, 185, 129",
    ):
        assert marker in css

def test_lite_xstate_dependencies_are_declared_source():
    package = json.loads(Path("package.json").read_text())
    lockfile = json.loads(Path("package-lock.json").read_text())
    assert "xstate" in package["dependencies"]
    assert "@xstate/react" in package["dependencies"]
    assert "xstate" in lockfile["packages"][""]["dependencies"]
    assert "@xstate/react" in lockfile["packages"][""]["dependencies"]


def test_lite_xstate_machine_files_and_required_states_source():
    machines = {
        "src/machines/liteAddDeviceMachine.js": ["validatingName", "checkingDuplicates", "creatingInvite", "inviteReady", "waitingForDevice", "joined", "online", "blocked", "failed"],
        "src/machines/liteRecoveryFlowMachine.js": ["backupRequested", "backupQueued", "backupRunning", "backupDone", "verifyRequested", "verifying", "verified", "previewRequested", "previewReady", "restoreConfirmationRequired", "checkpointCreating", "restoring", "validatingHealth"],
        "src/machines/liteSecurityCheckMachine.js": ["requestAccepted", "workerPickedUp", "lynisRunning", "trivyRunning", "evidenceSaving", "evidenceSaved", "partialResults"],
        "src/machines/liteAppActionFlowMachine.js": ["reviewing", "confirmationRequired", "submitting", "accepted", "queued", "running", "waitingForBackendState", "resultReady", "detailsReady", "blocked", "failed"],
    }
    for machine_path, required_states in machines.items():
        source = Path(machine_path).read_text()
        assert "createMachine" in source
        for state in required_states:
            assert state in source


def test_lite_xstate_machines_do_not_import_unsafe_runtime_sources():
    unsafe_terms = ["from 'fs'", 'from "fs"', "child_process", "exec(", "spawn(", "pm2", "nats", "jetstream", "shell", "fetch(", "localStorage", "sessionStorage", "browser_action_queue"]
    for machine_path in Path("src/machines").glob("lite*Machine.js"):
        source = machine_path.read_text()
        for unsafe in unsafe_terms:
            assert unsafe.lower() not in source.lower(), machine_path


def test_lite_xstate_hooks_and_screens_preserve_backend_ownership_source():
    hooks = [Path("src/hooks/useLiteAddDeviceFlow.js"), Path("src/hooks/useLiteRecoveryFlow.js"), Path("src/hooks/useLiteSecurityCheckFlow.js"), Path("src/hooks/useLiteAppActionFlow.js")]
    for hook in hooks:
        source = hook.read_text()
        assert "@xstate/react" in source
        assert "useMachine" in source
        assert "fetch(" not in source
        assert "child_process" not in source
    devices = Path("src/lite/LiteDevices.jsx").read_text()
    recovery = Path("src/lite/LiteRecovery.jsx").read_text()
    security = Path("src/lite/LiteSecurity.jsx").read_text()
    catalog = _lite_catalog_source()
    ui = Path("src/lite/LiteUi.jsx").read_text()
    assert "useLiteAddDeviceFlow" in devices and "liteApi.addDevice" in devices and "addDeviceFlow.inviteReady" in devices
    assert "useLiteRecoveryFlow" in recovery and "recoveryFlow.requestRestore" in recovery and "confirm: true" in recovery and "latestBackup.backup_id !== 'latest'" in recovery
    assert "useLiteSecurityCheckFlow" in security and "securityFlow.requestRun" in security and "liteApi.runSecurityScan" in security and "securityExecutionTimeline" in security
    assert "useLiteAppActionFlow" in catalog and "appActionFlow.review" in catalog and "appActionFlow.submit" in catalog and "liteApi.runAppAction" in catalog
    assert "window.location.assign(target)" in catalog
    assert 'data-lite-manage-portal="true"' in catalog
    assert "onClickCapture" not in catalog
    assert "LiteFlowStatusPanel" in ui
    assert "lite-catalog-flow-panel" not in catalog
    assert "visible: value !== 'idle' || writeBlocked" in Path("src/hooks/useLiteAppActionFlow.js").read_text()
    assert "lite-flow-status-panel" in Path("src/index.css").read_text()


def test_lite_xstate_preserves_query_snapshot_zustand_boundaries_source():
    guards = Path("src/machines/liteFlowGuards.js").read_text()
    mutation = Path("src/hooks/useLiteMutation.js").read_text()
    snapshots = Path("src/lib/liteSafeSnapshots.js").read_text()
    store = Path("src/stores/liteUiStore.js").read_text()
    vite = Path("vite.config.js").read_text()
    assert "LITE_XSTATE_WORKFLOW_ONLY" in guards
    assert "LITE_XSTATE_NO_BROWSER_ACTION_QUEUE" in guards
    assert "LITE_XSTATE_NO_OPTIMISTIC_SUCCESS" in guards
    assert "LITE_BROWSER_ACTION_QUEUE_DISABLED" in mutation
    assert "retry: false" in mutation
    assert "SAFE_LITE_GET_ENDPOINTS" in snapshots
    assert "LITE_UI_STORE_IS_UI_ONLY" in store
    assert "navigateFallbackDenylist" in vite and "safeLiteReadApiPattern" in vite and "apps" in vite
    assert "lite-saved-state-banner" not in snapshots


def test_lite_app_catalog_progress_and_safety_details_followup_source():
    catalog = _lite_catalog_source()
    progress = Path("src/lite/LiteActionProgress.jsx").read_text()
    css = Path("src/index.css").read_text()

    assert "lite-catalog-flow-panel" not in catalog
    assert "LiteFlowStatusPanel" not in catalog
    assert "Worker picked it up" not in progress
    assert "'Working'" in progress
    assert "'Done'" in progress
    assert "Done ✓" in progress
    assert "backendProgressSteps" in progress
    assert "normalizeBackendStepStatus" in progress
    assert "progress.steps" in progress
    assert "progress.timeline" in progress
    assert "setInterval" not in progress
    assert "animatedStage" not in progress
    assert "shouldAnimateProgress" not in progress
    assert "isLiveActionState" in progress
    assert "TERMINAL_ACTION_STATES" in progress
    assert "state === \'evidence_saved\' ? 100 : 95" in progress
    assert "troubleshooting records stay backend-only" not in catalog.lower()
    assert "actionId !== 'check_app' && actionId !== 'repair_app'" in catalog
    assert 'kind="row-to-details"' in catalog
    assert 'kind="card-to-sheet"' in catalog
    assert "lite-app-action-group.is-safety .lite-app-action-details-head .lite-shared-element-cue.is-row-to-details" in css
    assert "lite-catalog-flow-panel" not in css
    assert "Pocket Lab asked the backend worker to save PhotoPrism app records." in catalog
    assert "Private backup details stayed hidden." in catalog
    assert "Backup history" in catalog
    assert "Latest backup" in catalog



def test_lite_app_action_progress_uses_backend_step_status_source():
    catalog = _lite_catalog_source()
    progress = Path("src/lite/LiteActionProgress.jsx").read_text()

    assert "normalizeBackendStepStatus" in progress
    assert "backendProgressSteps" in progress
    assert "progress?.steps" in progress
    assert "progress?.timeline" in progress
    assert "step.status === 'completed'" in progress
    assert "step.status === 'active'" in progress
    assert "step.status === 'failed'" in progress
    assert "step.status === 'blocked'" in progress
    assert "progressPercentForSteps" in progress
    assert "completed / steps.length" in progress
    assert "Math.min(95, percent)" in progress
    assert "setInterval" not in progress
    assert "animatedStage" not in progress
    assert "shouldAnimateProgress" not in progress
    assert "steps: [        { id: 'ready'" not in catalog
    assert "steps: []" in catalog
    assert "timeline: []" in catalog
    assert "Array.isArray(progress?.timeline) ? progress.timeline : []" in catalog


def test_lite_action_progress_uses_backend_step_status_source():
    progress_source = Path("src/lite/LiteActionProgress.jsx").read_text()
    catalog_source = _lite_catalog_source()

    assert "backendProgressSteps" in progress_source
    assert "normalizeBackendStepStatus" in progress_source
    assert "progress.steps" in progress_source
    assert "progress.timeline" in progress_source

    assert "completed" in progress_source
    assert "active" in progress_source
    assert "pending" in progress_source
    assert "failed" in progress_source
    assert "blocked" in progress_source

    assert "setInterval" not in progress_source
    assert "animatedStage" not in progress_source
    assert "shouldAnimateProgress" not in progress_source

    assert "No frontend-invented app action completion" not in progress_source
    assert "progress.steps ||" not in catalog_source
    assert "syntheticBusyProgress" in catalog_source
    assert "isTerminalCatalogActionStatus" in catalog_source
    assert "currentMatches && isLiveCatalogActionStatus" in catalog_source



def test_lite_app_catalog_phase3_polling_policy_source():
    catalog = _lite_catalog_source()
    status_hook = Path("src/hooks/useLiteStatus.js").read_text()
    policy = Path("src/lib/litePollingPolicy.js").read_text()

    assert "APP_CATALOG_POLLING_POLICY_PHASE3" in catalog
    assert "hasLivePhotoPrismAppActionsPayload" in catalog
    assert "isLiveAppCatalogAction" in catalog
    assert "APP_CATALOG_LIVE_ACTION_STATUSES" in catalog
    assert "APP_CATALOG_TERMINAL_ACTION_STATUSES" in catalog
    assert "pollingMode: 'relaxed'" in catalog
    assert "queryKey: liteQueryKeys.catalog()" in catalog
    assert "path: liteQueryPaths.catalog" in catalog
    assert "pollingMode: 'normal'" in catalog
    assert "isLive: appActionsLive" in catalog
    assert "staleTime: 5_000" in catalog
    assert "actionBusyKey" in catalog
    assert "liteMutationInvalidations[actionId] || [liteQueryKeys.appActions('photoprism')]" in catalog
    assert "useLiteResource(liteApi.catalog" not in catalog
    assert "export function useLiteResource(loader, dependencies = [], options = {})" in status_hook
    assert "...options" in status_hook
    assert "liteQueryPollingInterval" in policy
    assert "window.setInterval" not in catalog
    assert "refreshAppActions('photoprism')" in catalog
    assert "Adaptive polling for App Catalog actions is owned by useLiteQuery" in catalog


def test_lite_devices_phase4_polling_policy_source():
    devices = Path("src/lite/LiteDevices.jsx").read_text()
    status_hook = Path("src/hooks/useLiteStatus.js").read_text()
    policy = Path("src/lib/litePollingPolicy.js").read_text()

    assert "DEVICES_POLLING_POLICY_PHASE4" in devices
    assert "hasLiveDeviceFleetOperation" in devices
    assert "deviceInviteIsLive" in devices
    assert "deviceRestartProgressIsLive" in devices
    assert "hasLiteLiveOperation" in devices
    assert "isLiteLiveStatus" in devices
    assert "fleetPollingIsLive" in devices
    assert "pollingMode: 'active'" in devices
    assert "isLive: fleetPollingIsLive" in devices
    assert "staleTime: 5_000" in devices
    assert "busy" in devices
    assert "restartBusy" in devices
    assert "removeBusy" in devices
    assert "restartProgress" in devices
    assert "useLiteResource(liteApi.fleet, [], {" in devices
    assert "setInterval" not in devices
    assert "export function useLiteResource(loader, dependencies = [], options = {})" in status_hook
    assert "liteQueryPollingInterval" in policy



def test_lite_security_recovery_phase5_polling_policy_source():
    security = Path("src/lite/LiteSecurity.jsx").read_text()
    recovery = Path("src/lite/LiteRecovery.jsx").read_text()
    policy = Path("src/lib/litePollingPolicy.js").read_text()
    status_hook = Path("src/hooks/useLiteStatus.js").read_text()

    assert "SECURITY_POLLING_POLICY_PHASE5" in security
    assert "hasLiveSecurityOperation" in security
    assert "securityPollingIsLive" in security
    assert "pollingMode: 'slow'" in security
    assert "isLive: securityPollingIsLive" in security
    assert "staleTime: 15_000" in security
    assert "window.setInterval(() => refresh()" not in security
    assert "window.setInterval(refresh" not in security

    assert "RECOVERY_POLLING_POLICY_PHASE5" in recovery
    assert "hasLiveRecoveryOperation" in recovery
    assert "recoveryPollingIsLive" in recovery
    assert "beginRecoveryPollingBurst" in recovery
    assert "recoveryPollingBurstUntil" in recovery
    assert "pollingMode: 'slow'" in recovery
    assert "isLive: recoveryPollingIsLive" in recovery
    assert "staleTime: 15_000" in recovery
    assert "Date.now() + 45_000" in recovery
    assert "window.setInterval" not in recovery

    assert "isLiteLiveStatus" in security
    assert "hasLiteLiveOperation" in security
    assert "isLiteLiveStatus" in recovery
    assert "hasLiteLiveOperation" in recovery
    assert "liteQueryPollingInterval" in policy
    assert "export function useLiteResource(loader, dependencies = [], options = {})" in status_hook



def test_lite_progressive_details_components_exist():
    expected_files = [
        Path("src/lite/components/LiteProgressiveDetails.jsx"),
        Path("src/lite/components/LiteTechnicalDetails.jsx"),
        Path("src/lite/components/LiteHistorySection.jsx"),
    ]
    for path in expected_files:
        assert path.exists()


def test_lite_app_catalog_uses_progressive_details_foundation():
    catalog = _lite_catalog_source()
    details = Path("src/lite/catalog/AppActionDetailsLazy.jsx").read_text()
    progressive = Path("src/lite/components/LiteProgressiveDetails.jsx").read_text()

    assert "React.lazy" in Path("src/lite/catalog/AppCatalogScreen.jsx").read_text()
    assert "import('./AppActionDetailsLazy.jsx')" in Path("src/lite/catalog/AppCatalogScreen.jsx").read_text()
    assert "LiteProgressiveDetails" in details
    assert "LiteTechnicalDetails" in progressive
    assert "LiteHistorySection" in progressive
    assert "Summary" not in details or "summary" in details
    assert "What happened" in progressive
    assert "What changed" in progressive
    assert "What did not happen" in progressive
    assert "Saved for troubleshooting" in progressive
    assert "Next step" in progressive
    assert "detailsActionId === entry.actionId" in catalog


def test_lite_progressive_details_keeps_history_lazy_and_technical_collapsed():
    technical = Path("src/lite/components/LiteTechnicalDetails.jsx").read_text()
    history = Path("src/lite/components/LiteHistorySection.jsx").read_text()
    catalog = _lite_catalog_source()

    assert "TECHNICAL_DETAILS_COLLAPSED_BY_DEFAULT" in technical
    assert "const [open, setOpen] = useState(Boolean(defaultOpen))" in technical
    assert "{open ? (" in technical
    assert "HISTORY_SECTION_COLLAPSED_BY_DEFAULT" in history
    assert "HISTORY_CONTENT_MOUNTS_ONLY_WHEN_OPENED" in history
    assert "const [isOpen, setIsOpen] = useState(false)" in history
    assert "const shouldMountHistory = Boolean(isOpen && enabled)" in history
    assert "{shouldMountHistory ? (" in history
    assert "data-lazy-history" in history
    assert "hidden={!" not in catalog
    assert "window.setInterval" not in catalog


def test_lite_app_catalog_details_preserve_backend_only_evidence_boundary():
    catalog = _lite_catalog_source()
    details = Path("src/lite/catalog/AppActionDetailsLazy.jsx").read_text()
    technical = Path("src/lite/components/LiteTechnicalDetails.jsx").read_text()

    assert "APP_ACTION_DETAILS_BACKEND_EVIDENCE_BOUNDARY" in details
    assert "normal App Catalog details do not fetch backend evidence endpoints" in details
    assert "liteApi.appEvidence" not in catalog
    assert "/api/lite/apps/{app_id}/evidence" not in catalog
    assert "PhotoPrismEvidenceReceiptModal" not in catalog
    assert "PhotoPrismEvidenceCard" not in catalog
    assert "TECHNICAL_DETAILS_SANITIZED_GUARD" in technical
    assert "SENSITIVE_DETAIL_PATTERN" in technical
    assert "Technical details are sanitized and collapsed by default." in technical
    assert "raw JSON" not in catalog

def test_lite_app_catalog_phase_s1_render_reduction_source_contract():
    catalog_wrapper = Path("src/lite/LiteCatalog.jsx").read_text()
    catalog = _lite_catalog_source()
    action_row = Path("src/lite/catalog/AppActionRow.jsx").read_text()
    details_lazy = Path("src/lite/catalog/AppActionDetailsLazy.jsx").read_text()
    progress_slot = Path("src/lite/catalog/AppActionProgressSlot.jsx").read_text()

    expected_files = [
        "AppCatalogScreen.jsx",
        "AppActionRow.jsx",
        "AppActionProgressSlot.jsx",
        "AppActionDetailsLazy.jsx",
        "AppManagePortal.jsx",
        "AppManageSheet.jsx",
        "AppManageSections.jsx",
        "AppStatusChips.jsx",
        "PhotoPrismMediaSummary.jsx",
    ]
    for filename in expected_files:
        assert Path("src/lite/catalog", filename).exists()

    assert "<AppCatalogScreen {...props} />" in catalog_wrapper
    assert "React.memo" in action_row
    assert "export default React.memo(AppActionRow)" in action_row
    assert "React.lazy" in catalog
    assert "import('./AppActionDetailsLazy.jsx')" in catalog
    assert "Loading details…" in catalog
    assert "LiteActionProgress" in progress_slot
    assert "if (!active) return null" in progress_slot
    assert "showProgress ? (" in catalog
    assert "progressSlot={progressSlot}" in catalog
    assert "detailsActionId === entry.actionId" in catalog
    assert "Saved for troubleshooting" in details_lazy
    assert "backend_only" in details_lazy
    assert "window.setInterval" not in catalog
    assert "hidden={!" not in catalog
    assert "normal App Catalog UI does not load" not in catalog


def test_lite_app_catalog_phase_s1_preserves_click_ownership_source():
    catalog = _lite_catalog_source()
    action_row = Path("src/lite/catalog/AppActionRow.jsx").read_text()

    assert "APP_CATALOG_ACTION_ROWS_OWN_CLICKS" in catalog
    assert "APP_CATALOG_PRIMARY_ACTIONS_OWN_CLICKS" in catalog
    assert "APP_CATALOG_MANAGE_PORTAL_STABLE_APP_KEY" in catalog
    assert "APP_CATALOG_MANAGE_SHEET_PORTAL_OVERLAY" in catalog
    assert "onClick={onClick}" in action_row
    assert "openApp(app, event)" in catalog
    assert "onClick={(event) => { stopGestureEvent(event); openManageSheet(app); }}" in catalog
    assert "onPointerDownCapture" not in action_row
    assert "onClickCapture" not in action_row


def test_lite_devices_render_reduction_components_exist():
    expected_files = [
        Path("src/lite/devices/DeviceCard.jsx"),
        Path("src/lite/devices/DeviceDetailsLazy.jsx"),
    ]
    for path in expected_files:
        assert path.exists()


def test_lite_devices_tab_uses_lazy_progressive_details_foundation():
    devices = Path("src/lite/LiteDevices.jsx").read_text()
    card = Path("src/lite/devices/DeviceCard.jsx").read_text()
    details = Path("src/lite/devices/DeviceDetailsLazy.jsx").read_text()

    assert "DEVICES_PROGRESSIVE_DETAILS_MILESTONE_2" in devices
    assert "React.lazy" in devices
    assert "import('./devices/DeviceDetailsLazy.jsx')" in devices
    assert "<Suspense" in devices
    assert "activeDetailsDevice ? (" in devices
    assert "React.memo(DeviceCard" in card
    assert "DEVICES_CARD_ACTIONS_OWN_CLICKS" in card
    assert "LiteProgressiveDetails" in details
    assert "DEVICE_DETAILS_USES_PROGRESSIVE_FOUNDATION" in details
    assert "DEVICE_DETAILS_HISTORY_IS_LAZY" in details
    assert "DEVICE_DETAILS_TECHNICAL_DETAILS_COLLAPSED" in details


def test_lite_devices_details_keep_history_lazy_and_technical_collapsed():
    devices = Path("src/lite/LiteDevices.jsx").read_text()
    details = Path("src/lite/devices/DeviceDetailsLazy.jsx").read_text()
    history = Path("src/lite/components/LiteHistorySection.jsx").read_text()
    technical = Path("src/lite/components/LiteTechnicalDetails.jsx").read_text()

    assert "history={{" in details
    assert "Device history" in details
    assert "technicalDetails={technicalRows(device)}" in details
    assert "const [isOpen, setIsOpen] = useState(false)" in history
    assert "const shouldMountHistory = Boolean(isOpen && enabled)" in history
    assert "{shouldMountHistory ? (" in history
    assert "TECHNICAL_DETAILS_COLLAPSED_BY_DEFAULT" in technical
    assert "const [open, setOpen] = useState(Boolean(defaultOpen))" in technical
    assert "{open ? (" in technical
    assert "hidden={" not in devices
    assert "hidden={!" not in devices
    assert "window.setInterval" not in devices


def test_lite_devices_details_preserve_backend_only_evidence_boundary():
    devices = Path("src/lite/LiteDevices.jsx").read_text()
    details = Path("src/lite/devices/DeviceDetailsLazy.jsx").read_text()
    technical = Path("src/lite/components/LiteTechnicalDetails.jsx").read_text()

    assert "DEVICE_DETAILS_BACKEND_EVIDENCE_BOUNDARY" in details
    assert "normal Devices details do not fetch backend evidence endpoints" in details
    assert "Device events and troubleshooting records stay backend-owned and protected." in details
    assert "No secrets, raw logs, or private paths were loaded into this view." in details
    assert "liteApi.appEvidence" not in devices
    assert "/api/lite/apps/{app_id}/evidence" not in devices
    assert "raw evidence" not in devices.lower()
    assert "raw logs" not in devices.lower()
    assert "SENSITIVE_DETAIL_PATTERN" in technical


def test_lite_devices_render_reduction_preserves_polling_and_click_boundaries():
    devices = Path("src/lite/LiteDevices.jsx").read_text()
    card = Path("src/lite/devices/DeviceCard.jsx").read_text()

    assert "DEVICES_POLLING_POLICY_PHASE4" in devices
    assert "hasLiveDeviceFleetOperation" in devices
    assert "isLive: fleetPollingIsLive" in devices
    assert "pollingMode: 'active'" in devices
    assert "staleTime: 5_000" in devices
    assert "setInterval" not in devices
    assert "onClickCapture" not in card
    assert "onPointerDownCapture" not in card
    assert "onOpenDetails" in card
    assert "onRestartAgent" in card
    assert "onRemoveDevice" in card


def test_lite_recovery_render_reduction_components_exist():
    expected_files = [
        Path("src/lite/recovery/RecoveryActionDetailsLazy.jsx"),
        Path("src/lite/recovery/RecoveryBackupHistory.jsx"),
    ]
    for path in expected_files:
        assert path.exists()


def test_lite_recovery_tab_uses_lazy_progressive_details_foundation():
    recovery = Path("src/lite/LiteRecovery.jsx").read_text()
    action_details = Path("src/lite/recovery/RecoveryActionDetailsLazy.jsx").read_text()
    backup_history = Path("src/lite/recovery/RecoveryBackupHistory.jsx").read_text()

    assert "RECOVERY_RENDER_REDUCTION_MILESTONE_1" in recovery
    assert "RECOVERY_PROGRESSIVE_DETAILS_MILESTONE_2" in recovery
    assert "React.lazy" in recovery
    assert "import('./recovery/RecoveryActionDetailsLazy.jsx')" in recovery
    assert "import('./recovery/RecoveryBackupHistory.jsx')" in recovery
    assert "<React.Suspense" in recovery
    assert "activePanel ? (" in recovery
    assert "LiteProgressiveDetails" in action_details
    assert "RECOVERY_PROGRESSIVE_DETAILS_MILESTONE_2" in action_details
    assert "RECOVERY_HISTORY_MOUNTS_ONLY_WHEN_OPENED" in action_details
    assert "LiteHistorySection" in backup_history
    assert "RECOVERY_HISTORY_NO_ALWAYS_RENDERED_ROWS" in backup_history


def test_lite_recovery_details_keep_history_lazy_and_technical_collapsed():
    recovery = Path("src/lite/LiteRecovery.jsx").read_text()
    action_details = Path("src/lite/recovery/RecoveryActionDetailsLazy.jsx").read_text()
    backup_history = Path("src/lite/recovery/RecoveryBackupHistory.jsx").read_text()
    history = Path("src/lite/components/LiteHistorySection.jsx").read_text()
    technical = Path("src/lite/components/LiteTechnicalDetails.jsx").read_text()

    assert "history={{" in action_details
    assert "Recovery history" in action_details
    assert "technicalDetails={technicalRows" in action_details
    assert "title=\"Backup history\"" in backup_history
    assert "const [isOpen, setIsOpen] = useState(false)" in history
    assert "const shouldMountHistory = Boolean(isOpen && enabled)" in history
    assert "{shouldMountHistory ? (" in history
    assert "TECHNICAL_DETAILS_COLLAPSED_BY_DEFAULT" in technical
    assert "const [open, setOpen] = useState(Boolean(defaultOpen))" in technical
    assert "{open ? (" in technical
    assert "hidden={" not in recovery
    assert "hidden={!" not in recovery
    assert "window.setInterval" not in recovery


def test_lite_recovery_details_preserve_backend_only_evidence_boundary():
    recovery = Path("src/lite/LiteRecovery.jsx").read_text()
    action_details = Path("src/lite/recovery/RecoveryActionDetailsLazy.jsx").read_text()
    technical = Path("src/lite/components/LiteTechnicalDetails.jsx").read_text()

    assert "RECOVERY_BACKEND_ONLY_TROUBLESHOOTING" in action_details
    assert "backend troubleshooting record is kept" in action_details
    assert "The normal UI shows only safe details" in action_details
    assert "The browser did not run recovery commands." in action_details
    assert "The browser did not read backup files." in action_details
    assert "liteApi.recoveryReceipt" not in recovery
    assert "liteApi.securityEvidence" not in recovery
    assert "liteApi.appEvidence" not in recovery
    assert "readJson(`/api/lite/recovery/receipts" not in recovery
    assert "readJson(`/api/lite/security/evidence" not in recovery
    assert "SENSITIVE_DETAIL_PATTERN" in technical


def test_lite_recovery_render_reduction_preserves_polling_and_actions():
    recovery = Path("src/lite/LiteRecovery.jsx").read_text()
    action_details = Path("src/lite/recovery/RecoveryActionDetailsLazy.jsx").read_text()

    assert "RECOVERY_POLLING_POLICY_PHASE5" in recovery
    assert "hasLiveRecoveryOperation" in recovery
    assert "recoveryPollingIsLive" in recovery
    assert "beginRecoveryPollingBurst" in recovery
    assert "pollingMode: 'slow'" in recovery
    assert "isLive: recoveryPollingIsLive" in recovery
    assert "staleTime: 15_000" in recovery
    assert "Date.now() + 45_000" in recovery
    assert "setInterval" not in recovery
    assert "backup()" in recovery
    assert "verifyLatestBackup" in recovery
    assert "previewLatestRestore" in recovery
    assert "restoreLatestBackup" in recovery
    assert "onClose={closeActionPanel}" in recovery
    assert "onOpenEvidence={() => setEvidenceOpen(true)}" in recovery
    assert "onClickCapture" not in action_details
    assert "onPointerDownCapture" not in action_details


def test_lite_security_render_reduction_components_exist():
    expected_files = [
        Path("src/lite/security/SecurityFindingDetailsLazy.jsx"),
        Path("src/lite/security/SecurityHistoryLazy.jsx"),
    ]
    for path in expected_files:
        assert path.exists()


def test_lite_security_tab_uses_lazy_progressive_details_foundation():
    security = Path("src/lite/LiteSecurity.jsx").read_text()
    finding_details = Path("src/lite/security/SecurityFindingDetailsLazy.jsx").read_text()
    history = Path("src/lite/security/SecurityHistoryLazy.jsx").read_text()

    assert "SECURITY_RENDER_REDUCTION_MILESTONE_1" in security
    assert "SECURITY_PROGRESSIVE_DETAILS_MILESTONE_2" in security
    assert "React.lazy" in security
    assert "import('./security/SecurityFindingDetailsLazy.jsx')" in security
    assert "import('./security/SecurityHistoryLazy.jsx')" in security
    assert "<Suspense" in security
    assert "selectedFinding === issue ? (" in security
    assert "selectedFinding === item ? (" in security
    assert "LiteProgressiveDetails" in finding_details
    assert "SECURITY_PROGRESSIVE_DETAILS_MILESTONE_2" in finding_details
    assert "SECURITY_FINDING_DETAILS_ARE_LAZY" in finding_details
    assert "LiteHistorySection" in history
    assert "SECURITY_HISTORY_ROWS_MOUNT_ONLY_WHEN_OPENED" in history


def test_lite_security_details_keep_history_lazy_and_technical_collapsed():
    security = Path("src/lite/LiteSecurity.jsx").read_text()
    finding_details = Path("src/lite/security/SecurityFindingDetailsLazy.jsx").read_text()
    security_history = Path("src/lite/security/SecurityHistoryLazy.jsx").read_text()
    history = Path("src/lite/components/LiteHistorySection.jsx").read_text()
    technical = Path("src/lite/components/LiteTechnicalDetails.jsx").read_text()

    assert "history={{" in finding_details
    assert "Finding history" in finding_details
    assert "technicalDetails={technicalRows" in finding_details
    assert "Security run history" in security_history
    assert "const [isOpen, setIsOpen] = useState(false)" in history
    assert "const shouldMountHistory = Boolean(isOpen && enabled)" in history
    assert "{shouldMountHistory ? (" in history
    assert "TECHNICAL_DETAILS_COLLAPSED_BY_DEFAULT" in technical
    assert "const [open, setOpen] = useState(Boolean(defaultOpen))" in technical
    assert "{open ? (" in technical
    assert "{isSecurityCardCollapsed('securityHistory') ? (" in security
    assert "<SecurityHistoryLazy" in security
    assert "hidden={isSecurityCardCollapsed('securityHistory')}" not in security
    assert "window.setInterval" not in security


def test_lite_security_details_preserve_backend_only_evidence_boundary():
    security = Path("src/lite/LiteSecurity.jsx").read_text()
    finding_details = Path("src/lite/security/SecurityFindingDetailsLazy.jsx").read_text()
    technical = Path("src/lite/components/LiteTechnicalDetails.jsx").read_text()

    assert "SECURITY_BACKEND_ONLY_EVIDENCE_BOUNDARY" in finding_details
    assert "normal Security finding details do not fetch backend evidence endpoints" in finding_details
    assert "A backend troubleshooting record stays protected" in finding_details
    assert "The browser did not run security tools." in finding_details
    assert "Raw scanner output was not loaded into this view." in finding_details
    assert "Secrets, private paths, and backend command payloads stay hidden." in finding_details
    assert "liteApi.securityEvidence" not in finding_details
    assert "readJson(`/api/lite/security/evidence" not in finding_details
    assert "raw evidence" not in finding_details.lower()
    assert "SENSITIVE_DETAIL_PATTERN" in technical
    assert "liteApi.securityEvidence" in security


def test_lite_security_render_reduction_preserves_polling_and_actions():
    security = Path("src/lite/LiteSecurity.jsx").read_text()
    finding_details = Path("src/lite/security/SecurityFindingDetailsLazy.jsx").read_text()

    assert "SECURITY_POLLING_POLICY_PHASE5" in security
    assert "hasLiveSecurityOperation" in security
    assert "securityPollingIsLive" in security
    assert "pollingMode: 'slow'" in security
    assert "isLive: securityPollingIsLive" in security
    assert "staleTime: 15_000" in security
    assert "setInterval" not in security
    assert "runSecurityScan" in security
    assert "checkProtectedApp" in security
    assert "onClickCapture" not in finding_details
    assert "onPointerDownCapture" not in finding_details
