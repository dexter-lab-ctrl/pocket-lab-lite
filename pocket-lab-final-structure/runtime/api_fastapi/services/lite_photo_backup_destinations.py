"""Versioned, server-owned destination capability projections.

Only the configured PhotoPrism originals root is eligible for uploads.
Other storage classes are intentionally disabled until a secured media
transport, identity binding, and recovery adapter exist.
"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 1
CURRENT_DESTINATION_ID = "server-photoprism-originals"
DISABLED_CLASSES = (
    ("server-removable", "Server Phone removable storage"),
    ("managed-nas", "Managed network storage"),
    ("enrolled-storage-node", "Enrolled storage device"),
    ("encrypted-object-store", "Encrypted object storage"),
)


def destinations(capacity: dict[str, Any], *, operational: bool) -> list[dict[str, Any]]:
    """Return only fixed backend-authorized identities, never client paths."""
    available = max(0, int(capacity.get("safe_upload_budget_bytes") or 0))
    enabled = operational and capacity.get("status") == "ready" and available > 0
    entries = [{
        "schema_version": SCHEMA_VERSION,
        "destination_id": CURRENT_DESTINATION_ID,
        "display_name": "Server Phone · PhotoPrism originals",
        "destination_type": "photoprism_originals",
        "transport": "https_webdav",
        "indexing": "photoprism",
        "eligible": enabled,
        "supported": True,
        "available_bytes": available,
        "reserve_policy": "hard_10_percent_planning_15_percent_min_2_gib",
        "reason_code": None if enabled else "destination_unavailable",
        "sanitized": True,
    }]
    for kind, label in DISABLED_CLASSES:
        entries.append({
            "schema_version": SCHEMA_VERSION,
            "destination_id": kind,
            "display_name": label,
            "destination_type": kind,
            "supported": False,
            "eligible": False,
            "reason_code": "unsupported_destination",
            "sanitized": True,
        })
    return entries


def require_eligible(destination_id: str, capacity: dict[str, Any], *, operational: bool) -> None:
    """Reject unknown and unimplemented destinations without path fallback."""
    if destination_id != CURRENT_DESTINATION_ID:
        raise ValueError("unsupported_destination")
    if not destinations(capacity, operational=operational)[0]["eligible"]:
        raise ValueError("destination_unavailable")
