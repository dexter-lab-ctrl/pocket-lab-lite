"""Review-only adapter for the existing release worker and subprocess.

Local operator staging is intentionally bounded to one fixed candidate directory.
No network access, extraction, install, activation or arbitrary metadata paths.
A local administrator must independently provision the root SHA-256 and clock
anchor; the candidate itself cannot supply either. This is not TUF rotation or
independently verified build provenance.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid

from .lite_release_trust import MAX_BYTES, Root, TrustError, _parse, strict_json, verify
from .lite_release_contract import parse_lite_tag

FILES = {
    "artifact_sha256": "dist.zip",
    "release_manifest_sha256": "pocketlab-lite-release.json",
    "policy_sha256": "pocketlab-lite-policy-inventory.json",
    "migration_inventory_sha256": "pocketlab-lite-migration-inventory.json",
}
MAX_ARTIFACT = 256 * 1024 * 1024


def _read(directory: Path, name: str, limit: int, *, hash_only: bool = False):
    # Fixed filenames only. Refuse symlink traversal in the controlled directory.
    if directory.is_symlink() or directory.parent.is_symlink():
        raise TrustError("unsafe_trust_directory")
    path = directory / name
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise TrustError("trust_file_size_or_type_invalid")
        if not hash_only:
            raw = stream.read(limit + 1)
            if len(raw) > limit:
                raise TrustError("trust_file_size_or_type_invalid")
            return raw
        h = hashlib.sha256()
        total = 0
        while chunk := stream.read(1024 * 1024):
            total += len(chunk)
            if total > limit:
                raise TrustError("trust_file_size_or_type_invalid")
            h.update(chunk)
        if total != info.st_size:
            raise TrustError("candidate_changed")
        return h.hexdigest()


def _clock(directory: Path):
    # A local administrator attests a recently independently checked UTC time.
    # Linux boot identity + monotonic time limit reuse. Not an authenticated
    # network time protocol; the operator and OS remain explicit trust assumptions.
    try:
        anchor = strict_json(_read(directory, "clock-anchor.json", 4096))
        if set(anchor) != {"boot_id", "monotonic_ns", "utc"}:
            return None
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        if anchor["boot_id"] != boot or type(anchor["monotonic_ns"]) is not int:
            return None
        elapsed = time.monotonic_ns() - anchor["monotonic_ns"]
        if not 0 <= elapsed <= 600_000_000_000:
            return None
        if not isinstance(anchor["utc"], str) or not anchor["utc"].endswith("Z"):
            return None
        now = datetime.fromisoformat(anchor["utc"][:-1] + "+00:00") + timedelta(microseconds=elapsed // 1000)
        return now
    except (OSError, ValueError, TypeError, OverflowError):
        return None


def inspect_candidate(request):
    """Called exclusively inside the existing bounded release subprocess."""
    state = Path(os.environ.get("POCKETLAB_STATE_DIR", ".")).expanduser().resolve()
    root_dir = state / "release-trust"
    pin = os.environ.get("POCKETLAB_RELEASE_ROOT_SHA256", "")
    tag = str(request.get("release_tag") or "")
    if not pin:
        return {"state": "trust_setup_required", "reason_code": "independent_root_required"}
    if not re.fullmatch(r"[0-9a-f]{64}", pin):
        return {"state": "verification_failed", "reason_code": "root_pin_invalid"}
    try:
        parse_lite_tag(tag)
        root_bytes = _read(root_dir, "root.json", MAX_BYTES)
        if hashlib.sha256(root_bytes).hexdigest() != pin:
            raise TrustError("root_pin_mismatch")
        root = _parse(Root, root_bytes)
        if request.get("pinned_root_sha256") not in (None, "", pin):
            raise TrustError("root_rotation_requires_review")
        candidate = root_dir / "candidate"
        observed = {key: _read(candidate, name, MAX_ARTIFACT if name == "dist.zip" else MAX_BYTES, hash_only=True)
                    for key, name in FILES.items()}
        manifest = _read(candidate, "pocketlab-lite-capabilities.json", MAX_BYTES)
        envelope = _read(candidate, "pocketlab-lite-trust.dsse.json", MAX_BYTES)
        floor = int(request.get("highest_version") or 0)
        receipt = verify(envelope, pinned_root=root, trusted_now=_clock(root_dir),
                         highest_version=max(0, floor - 1),
                         highest_root=int(request.get("highest_root") or 0),
                         expected_tag=tag, expected_commit=str(request.get("source_commit") or ""),
                         channel=str(request.get("channel") or ""), observed_digests=observed,
                         capability_manifest=manifest)
        if observed["artifact_sha256"] != request.get("artifact_sha256"):
            raise TrustError("discovered_artifact_mismatch")
        if request.get("highest_tag") and parse_lite_tag(tag) < parse_lite_tag(request["highest_tag"]):
            raise TrustError("release_tag_rollback")
        if receipt["metadata_version"] == floor and receipt["metadata_sha256"] != request.get("highest_digest"):
            raise TrustError("metadata_version_conflict")
        return {"state": "historical_evidence", "reason_code": receipt["reason_code"],
                "root_sha256": pin, "receipt": receipt}
    except FileNotFoundError:
        return {"state": "metadata_unavailable", "reason_code": "local_candidate_or_root_missing"}
    except TrustError as exc:
        return {"state": "verification_failed", "reason_code": str(exc)}
    except (OSError, ValueError, TypeError):
        return {"state": "verification_failed", "reason_code": "candidate_invalid"}


def floor_request(conn):
    floor = conn.execute("SELECT * FROM lite_release_trust_floor WHERE singleton_id=1").fetchone()
    pin = conn.execute("SELECT root_sha256 FROM lite_release_trust_pin WHERE singleton_id=1").fetchone()
    return {"highest_version": floor["metadata_version"] if floor else 0,
            "highest_root": floor["root_version"] if floor else 0,
            "highest_tag": floor["release_tag"] if floor else "",
            "highest_digest": floor["metadata_sha256"] if floor else "",
            "pinned_root_sha256": pin["root_sha256"] if pin else ""}


def persist(tx, observation, tag):
    """Must be called under the current existing release lease transaction."""
    state = observation["state"]
    reason = observation["reason_code"]
    stamp = datetime.now(timezone.utc).isoformat()
    receipt = observation.get("receipt")
    if receipt is not None:
        old = floor_request(tx)
        version = receipt["metadata_version"]
        root_pin = observation["root_sha256"]
        if (old["pinned_root_sha256"] not in ("", root_pin)
                or version < old["highest_version"]
                or receipt["root_version"] < old["highest_root"]
                or (version == old["highest_version"] and receipt["metadata_sha256"] != old["highest_digest"])
                or (old["highest_tag"] and parse_lite_tag(tag) < parse_lite_tag(old["highest_tag"]))):
            state, reason = "verification_failed", "durable_trust_floor_conflict"
        elif version > old["highest_version"]:
            tx.execute("INSERT OR IGNORE INTO lite_release_trust_pin VALUES (1,?,?)",
                       (root_pin, receipt["root_version"]))
            tx.execute("""INSERT INTO lite_release_trust_floor VALUES (1,?,?,?,?)
                       ON CONFLICT(singleton_id) DO UPDATE SET metadata_version=excluded.metadata_version,
                       root_version=excluded.root_version, metadata_sha256=excluded.metadata_sha256,
                       release_tag=excluded.release_tag""",
                       (version, receipt["root_version"], receipt["metadata_sha256"], tag))
            correlation = str(uuid.uuid4())
            tx.execute("INSERT INTO lite_release_trust_receipts VALUES (?,?,?,?,?,?)",
                       (correlation, version, receipt["root_version"], tag, receipt["checked_at"],
                        json.dumps({**receipt, "correlation_id": correlation}, sort_keys=True, separators=(",", ":"))))
    tx.execute("""INSERT INTO lite_release_trust_observation VALUES (1,?,?,?,?)
               ON CONFLICT(singleton_id) DO UPDATE SET state=excluded.state,
               reason_code=excluded.reason_code,checked_at=excluded.checked_at,release_tag=excluded.release_tag""",
               (state, reason, stamp, tag))
