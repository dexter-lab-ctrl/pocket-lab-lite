"""Server-owned, versioned photo-backup destination adapters.

One production adapter is installed: PhotoPrism originals over HTTPS WebDAV.
Disabled adapters have no transport, credential issuer or dispatch handler.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

SCHEMA_VERSION = 2
CURRENT_DESTINATION_ID = "server-photoprism-originals"
DESTINATION_TRANSPORT = "https_webdav"
DESTINATION_RESERVE_POLICY = "hard_10_percent_planning_15_percent_min_2_gib"
DISABLED_CLASSES = (
    ("server-removable", "Server Phone removable storage"),
    ("managed-nas", "Managed network storage"),
    ("enrolled-storage-node", "Enrolled storage device"),
    ("encrypted-object-store", "Encrypted object storage"),
)


@dataclass(frozen=True)
class DestinationAdapter:
    destination_id: str
    display_name: str
    destination_type: str
    transport: str
    indexing: str
    supported: bool
    write_capable: bool
    credential_strategy: str
    identity_strategy: str
    route_owner: str | None = None

    def public(self, capacity: dict[str, Any], operational: bool) -> dict[str, Any]:
        available: int | None = None
        reason = "destination_unavailable"
        capacity_valid = isinstance(capacity, dict)
        if self.supported and capacity_valid:
            raw_available = capacity.get("safe_upload_budget_bytes")
            capacity_valid = (
                type(raw_available) is int
                and raw_available >= 0
                and isinstance(capacity.get("status"), str)
            )
            if capacity_valid:
                available = raw_available
                candidate_reason = capacity.get("reason_code")
                if isinstance(candidate_reason, str) and candidate_reason.isidentifier():
                    reason = candidate_reason
        eligible = (self.supported and self.write_capable and self.route_owner is not None
                    and operational is True and capacity_valid
                    and capacity.get("status") == "ready" and (available or 0) > 0)
        return {
            "schema_version": SCHEMA_VERSION,
            "destination_id": self.destination_id,
            "display_name": self.display_name,
            "destination_type": self.destination_type,
            "transport": self.transport if self.supported else None,
            "indexing": self.indexing if self.supported else None,
            "credential_strategy": self.credential_strategy if self.supported else None,
            "identity_strategy": self.identity_strategy if self.supported else None,
            "supported": self.supported, "eligible": eligible,
            "available_bytes": available if self.supported and capacity_valid else None,
            "reserve_policy": DESTINATION_RESERVE_POLICY
                              if self.supported else None,
            "reason_code": None if eligible else
                ("unsupported_destination" if not self.supported else
                 reason),
            "sanitized": True,
        }


_PRODUCTION = DestinationAdapter(
    CURRENT_DESTINATION_ID, "Server Phone · PhotoPrism originals",
    "photoprism_originals", DESTINATION_TRANSPORT, "photoprism",
    True, True, "scoped_photoprism_app_password", "server_volume_fingerprint",
    "photoprism_webdav",
)


def _build_registry() -> tuple[dict[str, DestinationAdapter], tuple[DestinationAdapter, ...]]:
    entries = [_PRODUCTION]
    entries.extend(
        DestinationAdapter(key, label, key, "none", "none", False, False, "none", "none")
        for key, label in DISABLED_CLASSES
    )
    ids: set[str] = set()
    routes: set[str] = set()
    registry: dict[str, DestinationAdapter] = {}
    for entry in entries:
        if not entry.destination_id or entry.destination_id in ids:
            raise RuntimeError("duplicate_destination_id")
        if entry.route_owner and entry.route_owner in routes:
            raise RuntimeError("duplicate_destination_route")
        ids.add(entry.destination_id)
        if entry.route_owner:
            routes.add(entry.route_owner)
        registry[entry.destination_id] = entry
    return registry, tuple(entries)


_ADAPTERS, _ADAPTER_ORDER = _build_registry()
_ADAPTERS = MappingProxyType(_ADAPTERS)


def adapter(destination_id: str) -> DestinationAdapter:
    """Resolve fixed registry IDs only. Never accept user-supplied URLs/paths."""
    if not isinstance(destination_id, str):
        raise ValueError("unsupported_destination")
    item = _ADAPTERS.get(destination_id)
    if item is None or not item.supported or not item.write_capable or not item.route_owner:
        raise ValueError("unsupported_destination")
    return item


def destinations(capacity: dict[str, Any], *, operational: bool) -> list[dict[str, Any]]:
    return [entry.public(capacity, operational) for entry in _ADAPTER_ORDER]


def require_eligible(destination_id: str, capacity: dict[str, Any], *, operational: bool) -> None:
    item = adapter(destination_id)
    if not item.public(capacity, operational)["eligible"]:
        raise ValueError("destination_unavailable")


def placement(destination_id: str, node_id: str, backup_id: str,
              volume_fingerprint: str) -> dict[str, Any]:
    """Private deterministic placement, no externally supplied destination path."""
    import re
    if not isinstance(node_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", node_id):
        raise ValueError("invalid_node_id")
    if not isinstance(backup_id, str) or not re.fullmatch(r"photo-[a-f0-9]{20}", backup_id):
        raise ValueError("invalid_backup_id")
    if not isinstance(volume_fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", volume_fingerprint):
        raise ValueError("destination_identity_unavailable")
    item = adapter(destination_id)
    prefix = f"PocketLab/Devices/{node_id}"
    return {
        "schema_version": SCHEMA_VERSION,
        "destination_id": item.destination_id,
        "destination_type": item.destination_type,
        "transport": item.transport,
        "volume_fingerprint": volume_fingerprint,
        "node_id": node_id,
        "backup_id": backup_id,
        "prefix": prefix,
        "authorized_namespace": prefix,
    }
