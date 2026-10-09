"""Server-owned, versioned photo-backup destination adapters.

One production adapter is installed: PhotoPrism originals over HTTPS WebDAV.
Disabled adapters have no transport, credential issuer or dispatch handler.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = 2
CURRENT_DESTINATION_ID = "server-photoprism-originals"
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

    def public(self, capacity: dict[str, Any], operational: bool) -> dict[str, Any]:
        available = max(0, int(capacity.get("safe_upload_budget_bytes") or 0))
        reason = str(capacity.get("reason_code") or "")
        eligible = (self.supported and self.write_capable and operational
                    and capacity.get("status") == "ready" and available > 0)
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
            "available_bytes": available if self.supported else None,
            "reserve_policy": "hard_10_percent_planning_15_percent_min_2_gib"
                              if self.supported else None,
            "reason_code": None if eligible else
                ("unsupported_destination" if not self.supported else
                 reason or "destination_unavailable"),
            "sanitized": True,
        }


_PRODUCTION = DestinationAdapter(
    CURRENT_DESTINATION_ID, "Server Phone · PhotoPrism originals",
    "photoprism_originals", "https_webdav", "photoprism",
    True, True, "scoped_photoprism_app_password", "server_volume_fingerprint",
)
_ADAPTERS = {_PRODUCTION.destination_id: _PRODUCTION}
_ADAPTERS.update({
    key: DestinationAdapter(key, label, key, "none", "none", False, False, "none", "none")
    for key, label in DISABLED_CLASSES
})


def adapter(destination_id: str) -> DestinationAdapter:
    """Resolve fixed registry IDs only. Never accept user-supplied URLs/paths."""
    item = _ADAPTERS.get(destination_id)
    if item is None or not item.supported or not item.write_capable:
        raise ValueError("unsupported_destination")
    return item


def destinations(capacity: dict[str, Any], *, operational: bool) -> list[dict[str, Any]]:
    return [entry.public(capacity, operational) for entry in _ADAPTERS.values()]


def require_eligible(destination_id: str, capacity: dict[str, Any], *, operational: bool) -> None:
    item = adapter(destination_id)
    if not item.public(capacity, operational)["eligible"]:
        raise ValueError("destination_unavailable")


def placement(destination_id: str, node_id: str, backup_id: str,
              volume_fingerprint: str) -> dict[str, Any]:
    """Private deterministic placement, no externally supplied destination path."""
    import re
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", node_id):
        raise ValueError("invalid_node_id")
    if not re.fullmatch(r"photo-[a-f0-9]{20}", backup_id):
        raise ValueError("invalid_backup_id")
    if not re.fullmatch(r"[0-9a-f]{64}", volume_fingerprint):
        raise ValueError("destination_identity_unavailable")
    item = adapter(destination_id)
    return {
        "schema_version": SCHEMA_VERSION,
        "destination_id": item.destination_id,
        "destination_type": item.destination_type,
        "transport": item.transport,
        "volume_fingerprint": volume_fingerprint,
        "node_id": node_id,
        "backup_id": backup_id,
        "prefix": f"PocketLab/Devices/{node_id}",
    }
