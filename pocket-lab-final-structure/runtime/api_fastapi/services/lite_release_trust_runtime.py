"""Review-only adapter for the existing release worker and subprocess.

Acquisition uses fixed GitHub release assets or an explicit local review directory.
No extraction, install, activation or arbitrary metadata paths.
A local administrator must independently provision the root SHA-256 and clock
anchor; the candidate itself cannot supply either. This is not full TUF.
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
import tempfile
import shutil
from . import lite_release_trust_configuration as config
from contextlib import contextmanager
import uuid

from .lite_release_trust import MAX_BYTES, Root, TrustError, _parse, _expiry, strict_json, verify
from .lite_release_contract import parse_lite_tag

FILES = {
    "artifact_sha256": "dist.zip",
    "release_manifest_sha256": "pocketlab-lite-release.json",
    "policy_sha256": "pocketlab-lite-policy-inventory.json",
    "migration_inventory_sha256": "pocketlab-lite-migration-inventory.json",
}
MAX_ARTIFACT = 256 * 1024 * 1024


@contextmanager
def _open_controlled(directory: Path, name: str, limit: int):
    if Path(name).name != name or name in ("", ".", ".."):
        raise TrustError("unsafe_trust_filename")
    # Open each directory without following symlinks. Ancestors may have
    # different owners; the controlled directory itself must be private.
    absolute = directory.absolute()
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in absolute.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        info = os.fstat(fd)
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise TrustError("unsafe_trust_directory_permissions")
        child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(child, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                    or before.st_nlink != 1 or before.st_mode & 0o022 or before.st_size > limit):
                raise TrustError("trust_file_size_or_type_invalid")
            yield stream, before
            after = os.fstat(stream.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise TrustError("candidate_changed")
    finally:
        os.close(fd)

def _read(directory: Path, name: str, limit: int, *, hash_only: bool = False):
    with _open_controlled(directory, name, limit) as (stream, info):
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
        if set(anchor) != {"boot_id", "boottime_ns", "utc"}:
            return None
        boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
        if anchor["boot_id"] != boot or type(anchor["boottime_ns"]) is not int:
            return None
        sample = config.boot_time_ns()
        if sample is None:
            return None
        elapsed = sample - anchor["boottime_ns"]
        if not 0 <= elapsed <= 600_000_000_000:
            return None
        if not isinstance(anchor["utc"], str) or not anchor["utc"].endswith("Z"):
            return None
        now = datetime.fromisoformat(anchor["utc"][:-1] + "+00:00") + timedelta(microseconds=elapsed // 1000)
        return now, {"clock_boot_id": boot, "clock_sample_ns": sample, "clock_basis": "boottime",
                     "clock_remaining_ns": 600_000_000_000 - elapsed}
    except (OSError, ValueError, TypeError, OverflowError):
        return None


@contextmanager
def _candidate(root_dir, tag, request):
    mode = os.environ.get("POCKETLAB_RELEASE_TRUST_SOURCE", "github")
    if mode not in ("local", "github") or request.get("repository") != "dexter-lab-ctrl/pocket-lab-lite":
        raise TrustError("trusted_repository_mismatch")
    from .release_update_process import _download_to_file, ReleaseProcessFailure
    names = {name: MAX_ARTIFACT if name == "dist.zip" else MAX_BYTES for name in FILES.values()}
    names.update({"pocketlab-lite-capabilities.json": MAX_BYTES, "pocketlab-lite-trust.dsse.json": MAX_BYTES,
                  "pocketlab-lite-provenance.jsonl": 2 * 1024 * 1024})
    if root_dir.is_symlink() or not root_dir.is_dir() or root_dir.stat().st_uid != os.getuid() or root_dir.stat().st_mode & 0o077:
        raise TrustError("unsafe_trust_directory")
    if shutil.disk_usage(root_dir).free < sum(names.values()) + 32 * 1024 * 1024:
        raise TrustError("trust_disk_pressure")
    with tempfile.TemporaryDirectory(prefix="candidate-", dir=root_dir) as temp:
        path = Path(temp)
        total = 0
        deadline_ns = int(request.get("deadline_ns") or (time.monotonic_ns() + 120_000_000_000))
        for name, limit in sorted(names.items(), key=lambda pair: pair[0] == "dist.zip"):
            if time.monotonic_ns() >= deadline_ns:
                raise TrustError("trust_deadline_exceeded")
            if mode == "local":
                with _open_controlled(root_dir / "candidate", name, limit) as (stream, info):
                    with (path / name).open("xb") as out:
                        copied = 0
                        while chunk := stream.read(1024 * 1024):
                            copied += len(chunk)
                            if copied > limit:
                                raise TrustError("trust_file_size_or_type_invalid")
                            out.write(chunk)
                        if copied != info.st_size:
                            raise TrustError("candidate_changed")
            else:
                # Fixed repository, tag and filenames, not metadata-provided URLs.
                url = f"https://github.com/dexter-lab-ctrl/pocket-lab-lite/releases/download/{tag}/{name}"
                try:
                    _download_to_file(url, path / name, timeout=max(1, min(20, (deadline_ns - time.monotonic_ns()) / 1e9)), max_bytes=limit)
                except ReleaseProcessFailure as exc:
                    raise FileNotFoundError("trusted_asset_unavailable") from exc
            (path / name).chmod(0o400)
            total += (path / name).stat().st_size
        yield path, {"bytes_read": total, "files_examined": len(names)}


def _trust_directory():
    from .. import deps
    return deps.settings().state_dir.resolve() / "release-trust"

def _local_inventory():
    from .lite_lifecycle_contract import canonical_bytes
    source = Path(__file__).resolve().parents[4]
    def source_digest(paths):
        paths = sorted(paths)
        if not paths or len(paths) > 512:
            return None
        items = []
        total = 0
        for path in paths:
            size = path.stat().st_size
            total += size
            if size > MAX_BYTES or total > 8 * 1024 * 1024:
                return None
            with path.open("rb") as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) != size:
                return None
            items.append({"path":path.relative_to(source).as_posix(),"sha256":hashlib.sha256(raw).hexdigest()})
        return hashlib.sha256(canonical_bytes(items)).hexdigest()
    return (source_digest((source / "security/policies/opa").rglob("*.rego")),
            source_digest((source / "pocket-lab-final-structure/runtime/api_fastapi/db/schema").glob("*.sql")))

def inspect_candidate(request):
    """Called exclusively inside the existing bounded release subprocess."""
    root_dir = _trust_directory()
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
        clock = _clock(root_dir)
        if clock is None:
            raise TrustError("trusted_time_unavailable")
        now, clock_fields = clock
        if request.get("configuration_state") != "configured" or request.get("configured_root_sha256") != pin:
            raise TrustError("trust_configuration_suspended")
        _expiry(root.expires, now)
        if request.get("highest_trusted_time"):
            previous = datetime.fromisoformat(request["highest_trusted_time"])
            if now < previous:
                raise TrustError("trusted_clock_rollback")
        rotation = {}
        if request.get("pinned_root_sha256") not in (None, "", pin):
            from .lite_release_root_rotation import verify_rotation
            rotation = verify_rotation(_read(root_dir, "previous-root.json", MAX_BYTES), root_bytes,
                _read(root_dir, "root-transition.dsse.json", MAX_BYTES),
                old_pin=request["pinned_root_sha256"], new_pin=pin, now=now)
        with _candidate(root_dir, tag, request) as (candidate, acquisition_metrics):
            observed = {key: _read(candidate, name, MAX_ARTIFACT if name == "dist.zip" else MAX_BYTES, hash_only=True)
                        for key, name in FILES.items()}
            manifest = _read(candidate, "pocketlab-lite-capabilities.json", MAX_BYTES)
            envelope = _read(candidate, "pocketlab-lite-trust.dsse.json", MAX_BYTES)
            floor = int(request.get("highest_version") or 0)
            receipt = verify(envelope, pinned_root=root, trusted_now=now,
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
            from .lite_release_provenance import provenance
            disposition, reason = provenance(candidate, root_dir, commit=receipt["source_commit"], tag=tag)
            from .lite_release_trust import CapabilityManifest
            from .lite_lifecycle_contract import CAPABILITIES, assess, canonical_bytes, registry_revision
            policy, migrations = _local_inventory()
            candidate_caps = _parse(CapabilityManifest, manifest)
            assessment = assess(CAPABILITIES, tuple(candidate_caps.capabilities),
                policy_changed=policy != receipt["policy_sha256"],
                migration_changed=migrations != receipt["migration_inventory_sha256"],
                root_changed=bool(rotation))
            current_schema = int(request.get("current_schema") or 0)
            schema_match = receipt["schema_min"] <= current_schema <= receipt["schema_max"]
            receipt.update(provenance=disposition, provenance_reason=reason, **rotation, **clock_fields,
                root_sha256=pin, attestation_root_sha256=config.configured()[1],
                configuration_revision=request.get("configuration_revision"),
                local_policy_sha256=policy, local_migration_inventory_sha256=migrations,
                impact=assessment.impact.value, assessment=assessment.model_dump(mode="json"),
                schema_range_matches=schema_match, current_schema=current_schema,
                registry_revision=registry_revision(),
                compatibility="unknown" if schema_match else "incompatible")
            return {"state": "historical_evidence" if disposition == "verified" else
                    ("verification_failed" if disposition == "failed" else "metadata_unavailable"),
                    "reason_code": reason, "root_sha256": pin, "receipt": receipt if disposition == "verified" else None,
                    "acquisition_metrics": acquisition_metrics}
    except FileNotFoundError:
        return {"state": "metadata_unavailable", "reason_code": "local_candidate_or_root_missing"}
    except TrustError as exc:
        return {"state": "verification_failed", "reason_code": str(exc)}
    except (TypeError, KeyError, AttributeError):
        return {"state": "verification_failed", "reason_code": "trust_contract_invalid"}
    except (OSError, ValueError, TypeError):
        return {"state": "verification_failed", "reason_code": "candidate_invalid"}


def floor_request(conn):
    floor = conn.execute("SELECT * FROM lite_release_trust_floor WHERE singleton_id=1").fetchone()
    pin = conn.execute("SELECT root_sha256 FROM lite_release_trust_pin WHERE singleton_id=1").fetchone()
    clock = conn.execute("SELECT trusted_at FROM lite_release_trusted_time WHERE singleton_id=1").fetchone()
    setup = config.configuration(conn)
    return {"configuration_revision": setup["revision"] if setup else 0,
            "configuration_state": setup["state"] if setup else "unconfigured",
            "configured_root_sha256": setup["root_sha256"] if setup else "",
            "highest_trusted_time": clock["trusted_at"] if clock else "",
            "highest_version": floor["metadata_version"] if floor else 0,
            "highest_root": floor["root_version"] if floor else 0,
            "highest_tag": floor["release_tag"] if floor else "",
            "highest_digest": floor["metadata_sha256"] if floor else "",
            "pinned_root_sha256": pin["root_sha256"] if pin else ""}


def cached_review(conn, request):
    """Automatic checks may reuse historical evidence; manual checks always verify."""
    from .lite_lifecycle_contract import registry_revision
    row = conn.execute("SELECT * FROM lite_release_trust_observation WHERE singleton_id=1").fetchone()
    if not row or row["state"] != "historical_evidence":
        return False
    try:
        r = json.loads(row["review_json"])
        now = config.prepared_now(conn, r)
        if now is None:
            return False
        checked = datetime.fromisoformat(r["checked_at"])
        if not timedelta(0) <= now - checked < timedelta(hours=24):
            return False
        if any(datetime.fromisoformat(r[key].replace("Z", "+00:00")) <= now for key in ("expires", "root_expires")):
            return False
        local_policy, local_migrations = _local_inventory()
        root_dir = _trust_directory()
        if (not local_policy or not local_migrations
                or local_policy != r.get("local_policy_sha256") or local_migrations != r.get("local_migration_inventory_sha256")
                or _read(root_dir, "root.json", MAX_BYTES, hash_only=True) != r.get("root_sha256")
                or _read(root_dir, "github-trusted-root.jsonl", 2 * 1024 * 1024, hash_only=True) != r.get("attestation_root_sha256")):
            return False
        return (r["provenance"] == "verified" and request["repository"] == "dexter-lab-ctrl/pocket-lab-lite"
                and request["pinned_root_sha256"] == os.environ.get("POCKETLAB_RELEASE_ROOT_SHA256")
                and r["registry_revision"] == registry_revision()
                and all(r.get(k) == request.get(k) for k in ("release_tag", "source_commit", "artifact_sha256", "channel", "current_schema")))
    except (KeyError, TypeError, ValueError, OSError):
        return False


def _semantic_review(state, reason, tag, review):
    return (state, reason, tag, {k: v for k, v in review.items() if k not in {"checked_at", "correlation_id", "clock_sample_ns", "clock_remaining_ns"}})


def persist(tx, observation, tag):
    """Must be called under the current existing release lease transaction."""
    state = observation["state"]
    reason = observation["reason_code"]
    stamp = datetime.now(timezone.utc).isoformat()
    previous = tx.execute("SELECT * FROM lite_release_trust_observation WHERE singleton_id=1").fetchone()
    receipt = observation.get("receipt")
    if receipt is not None:
        old = floor_request(tx)
        version = receipt["metadata_version"]
        root_pin = observation["root_sha256"]
        rotated = (receipt.get("previous_root_sha256") == old["pinned_root_sha256"]
                   and receipt.get("root_transition_sha256") and receipt["root_version"] == old["highest_root"] + 1
                   and version > old["highest_version"])
        if (not config.current_configuration(tx, receipt)
                or config.prepared_now(tx, receipt) is None
                or (old["highest_trusted_time"] and datetime.fromisoformat(receipt["checked_at"]) < datetime.fromisoformat(old["highest_trusted_time"]))
                or (old["pinned_root_sha256"] not in ("", root_pin) and not rotated)
                or version < old["highest_version"]
                or receipt["root_version"] < old["highest_root"]
                or (version == old["highest_version"] and receipt["metadata_sha256"] != old["highest_digest"])
                or (old["highest_tag"] and parse_lite_tag(tag) < parse_lite_tag(old["highest_tag"]))):
            state, reason = "verification_failed", "durable_trust_floor_conflict"
            receipt = None
        elif version > old["highest_version"]:
            tx.execute("""INSERT INTO lite_release_trust_pin VALUES (1,?,?)
                       ON CONFLICT(singleton_id) DO UPDATE SET root_sha256=excluded.root_sha256,root_version=excluded.root_version""",
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
    if receipt is not None:
        tx.execute("""INSERT INTO lite_release_trusted_time VALUES(1,?) ON CONFLICT(singleton_id)
            DO UPDATE SET trusted_at=excluded.trusted_at""", (receipt["checked_at"],))
    tx.execute("""INSERT INTO lite_release_trust_observation(singleton_id,state,reason_code,checked_at,release_tag,review_json)
               VALUES (1,?,?,?,?,?) ON CONFLICT(singleton_id) DO UPDATE SET state=excluded.state,
               reason_code=excluded.reason_code,checked_at=excluded.checked_at,release_tag=excluded.release_tag,
               review_json=excluded.review_json""",
               (state, reason, stamp, tag, json.dumps(receipt or {}, sort_keys=True, separators=(",", ":"))))
    tx.execute("DELETE FROM lite_release_trust_receipts WHERE metadata_version NOT IN (SELECT metadata_version FROM lite_release_trust_receipts ORDER BY metadata_version DESC LIMIT 100)")
    if not previous or _semantic_review(previous["state"], previous["reason_code"], previous["release_tag"],
            json.loads(previous["review_json"])) != _semantic_review(state, reason, tag, receipt or {}):
        tx.execute("INSERT INTO lite_release_trust_transitions(state,reason_code,occurred_at,release_tag) VALUES(?,?,?,?)",
                   (state, reason, stamp, tag))
        tx.execute("DELETE FROM lite_release_trust_transitions WHERE event_id NOT IN (SELECT event_id FROM lite_release_trust_transitions ORDER BY event_id DESC LIMIT 200)")
        from .lite_control_plane_store import _bump_revision
        _bump_revision(tx, "audit", stamp, changed_ids=["trusted-lifecycle"], reason="audit_state_changed")
