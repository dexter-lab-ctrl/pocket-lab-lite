from __future__ import annotations

from typing import Any


CAPABILITY_LABELS: dict[str, str] = {
    "app_host": "App Host",
    "media_storage": "Storage Node",
    "backup_target": "Backup Target",
    "security_scanner": "Security Scanner",
    "compute": "Compute",
}

_CAPABILITIES_BY_ROLE: dict[str, list[str]] = {
    "server_host": ["app_host", "compute", "security_scanner"],
    "compute": ["app_host", "compute"],
    "storage": ["media_storage", "backup_target"],
}

_STORAGE_ROOT_LABELS = {
    "dcim": "DCIM",
    "pictures": "Pictures",
    "movies": "Movies",
    "downloads": "Downloads",
    "managed_media": "Managed media",
}


def normalize_role(role: Any) -> str:
    value = str(role or "compute").strip().lower().replace("-", "_").replace(" ", "_")
    if value in {"server", "server_host"}:
        return "server_host"
    if value in {"storage", "storage_node"}:
        return "storage"
    if value in {"compute", "app_host"}:
        return "compute"
    return "compute"


def capability_ids_for_role(role: Any) -> list[str]:
    return list(_CAPABILITIES_BY_ROLE.get(normalize_role(role), _CAPABILITIES_BY_ROLE["compute"]))


def labels_for_capabilities(capabilities: list[str] | tuple[str, ...] | None) -> list[str]:
    labels: list[str] = []
    for capability in capabilities or []:
        label = CAPABILITY_LABELS.get(str(capability), str(capability).replace("_", " ").title())
        if label not in labels:
            labels.append(label)
    return labels


def _safe_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount < 0:
        return None
    return round(amount, 1)


def _safe_media_roots(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    roots: list[str] = []
    for item in value:
        raw = str(item or "").strip().lower().replace(" ", "_").replace("-", "_")
        label = _STORAGE_ROOT_LABELS.get(raw)
        if label and label not in roots:
            roots.append(label)
    return roots[:6]


def storage_summary_from_node(node: dict[str, Any], capabilities: list[str]) -> dict[str, Any] | None:
    if "media_storage" not in capabilities and "backup_target" not in capabilities:
        return None
    status = str(node.get("connection") or node.get("status") or "unknown").lower()
    ready = status in {"online", "healthy", "active", "ready"}
    telemetry = node.get("storage") if isinstance(node.get("storage"), dict) else {}
    available = (
        telemetry.get("available_gb")
        or node.get("available_gb")
        or node.get("free_storage_gb")
        or node.get("storage_available_gb")
    )
    roots = _safe_media_roots(telemetry.get("media_roots") or node.get("media_roots"))
    return {
        "status": "ready" if ready else "not_ready",
        "ready": bool(ready),
        "available_gb": _safe_float(available),
        "media_roots": roots,
        "summary": "Storage device ready" if ready else "Storage device not ready",
    }


def apply_device_capabilities(device: dict[str, Any]) -> dict[str, Any]:
    capabilities = capability_ids_for_role(device.get("role"))
    device["capabilities"] = capabilities
    device["capability_labels"] = labels_for_capabilities(capabilities)
    storage = storage_summary_from_node(device, capabilities)
    if storage:
        device["storage"] = storage
    return device


def capability_counts(devices: list[dict[str, Any]], *, ready_only: bool = False) -> dict[str, int]:
    counts = {key: 0 for key in CAPABILITY_LABELS}
    for device in devices:
        connection = str(device.get("connection") or "").lower()
        status = str(device.get("status") or "").lower()
        ready = connection == "online" or status in {"healthy", "active", "online", "ready"}
        if ready_only and not ready:
            continue
        for capability in device.get("capabilities") or []:
            if capability in counts:
                counts[capability] += 1
    return counts


def catalog_device_summary(devices: list[dict[str, Any]]) -> dict[str, Any]:
    all_counts = capability_counts(devices)
    ready_counts = capability_counts(devices, ready_only=True)
    server = next((item for item in devices if str(item.get("role") or "") == "server_host"), None)
    storage_devices = [
        {
            "id": item.get("id"),
            "name": item.get("name") or "Storage device",
            "status": item.get("status"),
            "connection": item.get("connection"),
            "ready": str(item.get("connection") or "").lower() == "online" or str(item.get("status") or "").lower() in {"healthy", "ready", "online", "active"},
            "capability_labels": item.get("capability_labels") or labels_for_capabilities(item.get("capabilities") or []),
            "storage": item.get("storage") if isinstance(item.get("storage"), dict) else None,
        }
        for item in devices
        if "media_storage" in (item.get("capabilities") or [])
    ]
    return {
        "host_device_id": (server or {}).get("id") or "pocket-lab-lite-server",
        "host_device_name": (server or {}).get("name") or "Pocket Lab Lite Server",
        "available_device_capabilities": all_counts,
        "ready_device_capabilities": ready_counts,
        "storage_devices": storage_devices,
        "storage_devices_available": all_counts.get("media_storage", 0),
        "storage_devices_ready": ready_counts.get("media_storage", 0),
    }
