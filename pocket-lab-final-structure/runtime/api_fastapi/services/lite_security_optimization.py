from __future__ import annotations

"""Fail-closed low-power planning primitives for Lite Security scans.

This module deliberately owns only deterministic identity, checkpoint, resource,
and budget policy. Scanner execution remains worker-owned in ``lite_security``.
Unknown identity or telemetry never becomes an optimistic cache hit or a made-up
resource signal.
"""

import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .. import deps
from . import lite_security_evidence as evidence
from . import lite_security_policy as policy


TARGET_IDENTITY_SCHEMA = 2
CHECKPOINT_SCHEMA = 1
_MAX_IDENTITY_ENTRIES = 100_000
_MAX_IDENTITY_BYTES = 512 * 1024 * 1024
_COMPLETED_TARGET_STATUSES = frozenset({"checked", "completed", "reused", "resumed"})
_CHECKPOINT_RESUMABLE_STATUSES = frozenset({"running", "paused_at_checkpoint"})
_CHECKPOINT_REUSABLE_STATUSES = frozenset({"succeeded", "completed", "degraded"})
_CACHE_IDENTITY_REQUIRED_FIELDS = (
    "schema",
    "contract_id",
    "compatible_profiles",
    "target_id",
    "target_fingerprint",
    "scanner",
    "scanner_version",
    "scanner_artifact_revision",
    "scanner_db_revision",
    "scanner_db_valid_until",
    "policy_revision",
    "exclusion_revision",
    "scanner_configuration_revision",
    "scanners",
    "secret_mode",
    "sbom_format",
    "sbom_generator",
    "sbom_schema",
)


def digest(value: Any) -> str:
    clean = policy.redact_value(value)
    material = json.dumps(
        clean,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        default=str,
    )
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def cache_identity_is_complete(identity: Mapping[str, Any] | None) -> bool:
    """Require every field that participates in target compatibility."""

    if not isinstance(identity, Mapping):
        return False
    scalar_fields = tuple(
        field
        for field in _CACHE_IDENTITY_REQUIRED_FIELDS
        if field not in {"schema", "compatible_profiles", "secret_mode", "sbom_schema"}
    )
    if any(
        field not in identity
        or not isinstance(identity.get(field), str)
        or not str(identity.get(field) or "").strip()
        for field in scalar_fields
    ):
        return False
    profiles = identity.get("compatible_profiles")
    if not isinstance(profiles, list) or not profiles or not all(
        isinstance(item, str) and item in policy.VALID_SCAN_PROFILES for item in profiles
    ):
        return False
    if not isinstance(identity.get("secret_mode"), bool):
        return False
    if isinstance(identity.get("sbom_schema"), bool) or not isinstance(
        identity.get("sbom_schema"), int
    ):
        return False
    return identity.get("schema") == TARGET_IDENTITY_SCHEMA


def durable_evidence_ref(run_id: str, evidence_ref: Any) -> bool:
    """Confirm a checkpoint reference names an existing run-local evidence file."""

    safe_run = evidence.safe_run_id(run_id)
    reference = str(evidence_ref or "")
    prefix = f"security/evidence/{safe_run}/"
    if not reference.startswith(prefix):
        return False
    filename = reference[len(prefix) :]
    if not filename or filename in {".", ".."} or "/" in filename or "\\" in filename:
        return False
    path = evidence.security_root() / "evidence" / safe_run / filename
    try:
        return path.is_file()
    except OSError:
        return False


def durable_evidence_reference(evidence_ref: Any) -> bool:
    """Validate a sanitized run-local evidence reference without assuming its owner."""

    reference = str(evidence_ref or "")
    parts = reference.split("/")
    if len(parts) != 4 or parts[:2] != ["security", "evidence"]:
        return False
    run_id = parts[2]
    return bool(run_id) and evidence.safe_run_id(run_id) == run_id and durable_evidence_ref(
        run_id, reference
    )


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _optional_float(name: str, minimum: float, maximum: float) -> float | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return max(minimum, min(maximum, value))


def _safe_relative(path: Path, root: Path) -> str | None:
    try:
        return str(path.relative_to(root)).replace("\\", "/") or "."
    except ValueError:
        return None


def path_target_identity(
    target: Path,
    *,
    identity_label: str,
    excluded_patterns: Iterable[str] = (),
    max_entries: int = _MAX_IDENTITY_ENTRIES,
    max_bytes: int = _MAX_IDENTITY_BYTES,
) -> dict[str, Any] | None:
    """Hash a bounded file/tree target without following symbolic links."""

    try:
        if target.is_symlink():
            return None
        root = target.resolve(strict=True)
    except OSError:
        return None
    patterns = tuple(str(item).replace("\\", "/").strip("/") for item in excluded_patterns if str(item).strip())
    hasher = hashlib.sha256()
    entries = 0
    total_bytes = 0

    def excluded(relative: str) -> bool:
        import fnmatch

        normalized = relative.strip("/")
        basename = normalized.rsplit("/", 1)[-1]
        return any(
            fnmatch.fnmatchcase(normalized, pattern)
            or fnmatch.fnmatchcase(basename, pattern)
            or any(
                fnmatch.fnmatchcase("/".join(normalized.split("/")[:index]), pattern)
                for index in range(1, len(normalized.split("/")) + 1)
            )
            for pattern in patterns
        )

    pending = [root]
    try:
        while pending:
            current = pending.pop()
            relative = _safe_relative(current, root)
            if relative is None:
                return None
            if relative != "." and excluded(relative):
                continue
            if current.is_symlink():
                return None
            stat = current.stat()
            entries += 1
            if entries > max(1, int(max_entries)):
                return None
            if current.is_dir():
                hasher.update(f"D:{relative}:{stat.st_mode & 0o7777}\n".encode("utf-8"))
                children = sorted(current.iterdir(), key=lambda item: item.name, reverse=True)
                pending.extend(children)
                continue
            if not current.is_file():
                return None
            total_bytes += int(stat.st_size)
            if total_bytes > max(1, int(max_bytes)):
                return None
            hasher.update(
                f"F:{relative}:{stat.st_mode & 0o7777}:{stat.st_size}\n".encode("utf-8")
            )
            with current.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
    except (OSError, ValueError):
        return None
    return {
        "schema": TARGET_IDENTITY_SCHEMA,
        "kind": "bounded_content_tree" if root.is_dir() else "bounded_content_file",
        "identity_label": str(identity_label)[:120],
        "entries": entries,
        "bytes": total_bytes,
        "content_revision": "sha256:" + hasher.hexdigest(),
    }


def normalize_target_dag(nodes: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return deterministic targets and annotate exact/nested overlap.

    Target definitions are backend-owned. Dependencies are derived from the
    resolved paths instead of being trusted from the input, which keeps an
    arbitrary cyclic dependency list from becoming an executable graph.
    """

    normalized: list[dict[str, Any]] = []
    seen_target_ids: set[str] = set()
    for raw in nodes:
        if not isinstance(raw, Mapping):
            continue
        node = policy.redact_value(dict(raw))
        target_id = str(node.get("target_id") or "").strip()
        contract_id = str(node.get("contract_id") or "").strip()
        raw_path = str(node.get("path") or "").strip()
        if not target_id or target_id in seen_target_ids or not contract_id or not raw_path:
            continue
        try:
            resolved = str(Path(raw_path).expanduser().resolve(strict=False))
        except (OSError, ValueError):
            continue
        node["path"] = resolved
        # Dependencies are always recomputed below. Never execute an
        # arbitrary caller-supplied dependency graph.
        node["depends_on"] = []
        normalized.append(node)
        seen_target_ids.add(target_id)

    roots: dict[tuple[str, str, str], dict[str, Any]] = {}
    for index, node in enumerate(normalized):
        contract_id = str(node.get("contract_id") or "")
        scanners = str(node.get("scanners") or "")
        candidate_path = Path(str(node["path"]))
        key = (str(candidate_path), contract_id, scanners)
        duplicate_of = roots.get(key)
        if duplicate_of:
            node.update(
                {
                    "state": "reused",
                    "overlap": "exact",
                    "depends_on": [str(duplicate_of.get("target_id") or "")],
                }
            )
            continue

        ancestors: list[tuple[int, dict[str, Any]]] = []
        for prior_index, prior in enumerate(normalized):
            if prior_index == index:
                continue
            if str(prior.get("contract_id") or "") != contract_id:
                continue
            if str(prior.get("scanners") or "") != scanners:
                continue
            try:
                prior_path = Path(str(prior["path"]))
            except (KeyError, TypeError, ValueError):
                continue
            if prior_path != candidate_path and prior_path in candidate_path.parents:
                ancestors.append((prior_index, prior))
        if ancestors:
            _, ancestor = min(
                ancestors,
                key=lambda item: (len(Path(str(item[1]["path"])).parts), item[0]),
            )
            node.update(
                {
                    "state": "reused",
                    "overlap": "nested",
                    "depends_on": [str(ancestor.get("target_id") or "")],
                }
            )
        else:
            node["state"] = "pending"
            node["overlap"] = None
        roots[key] = node
    return normalized


def _read_meminfo() -> tuple[float | None, int | None]:
    try:
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition(":")
            if separator:
                values[key] = int(value.strip().split()[0])
        total_kib = int(values.get("MemTotal") or 0)
        available_kib = int(values.get("MemAvailable") or values.get("MemFree") or 0)
        if total_kib <= 0:
            return None, None
        return round(available_kib / total_kib * 100.0, 2), available_kib * 1024
    except (OSError, ValueError, IndexError):
        return None, None


def _battery_snapshot() -> dict[str, Any]:
    command = shutil.which("termux-battery-status")
    if not command:
        return {
            "battery_percent": None,
            "charging": None,
            "temperature_c": None,
            "telemetry_source": "unavailable",
        }
    try:
        result = subprocess.run(
            [command],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if result.returncode != 0 or len(result.stdout) > 32 * 1024:
            raise ValueError("battery probe unavailable")
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict):
            raise ValueError("battery payload unavailable")
        percentage = payload.get("percentage", payload.get("level"))
        temperature = payload.get("temperature")
        percent_value = float(percentage) if percentage is not None else None
        temperature_value = float(temperature) if temperature is not None else None
        plugged = str(payload.get("plugged") or "").strip().upper()
        status = str(payload.get("status") or "").strip().upper()
        return {
            "battery_percent": round(percent_value, 2) if percent_value is not None and 0 <= percent_value <= 100 else None,
            "charging": plugged not in {"", "UNPLUGGED", "UNKNOWN"} or status == "CHARGING",
            "temperature_c": round(temperature_value, 2) if temperature_value is not None and -20 <= temperature_value <= 120 else None,
            "telemetry_source": "termux-battery-status",
        }
    except (OSError, subprocess.SubprocessError, TypeError, ValueError, json.JSONDecodeError):
        return {
            "battery_percent": None,
            "charging": None,
            "temperature_c": None,
            "telemetry_source": "unavailable",
        }


def resource_snapshot(*, storage_path: Path | None = None) -> dict[str, Any]:
    """Return sanitized nullable facts; unavailable signals remain unknown."""

    captured = time.time()
    memory_percent, memory_bytes = _read_meminfo()
    try:
        usage = shutil.disk_usage(storage_path or deps.settings().state_dir)
        free_storage_bytes: int | None = int(usage.free)
    except OSError:
        free_storage_bytes = None
    try:
        load_ratio: float | None = round(float(os.getloadavg()[0]) / max(1, int(os.cpu_count() or 1)), 3)
    except (AttributeError, OSError, ValueError):
        load_ratio = None
    battery = _battery_snapshot()
    return policy.redact_value(
        {
            **battery,
            "available_memory": memory_bytes,
            "available_memory_percent": memory_percent,
            "free_storage": free_storage_bytes,
            "system_load_ratio": load_ratio,
            "telemetry_age_ms": max(0, int((time.time() - captured) * 1000)),
            "captured_at": datetime.fromtimestamp(captured, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "sanitized": True,
        }
    )


def scan_budget_policy(profile: str) -> dict[str, Any]:
    normalized = policy.normalize_scan_profile(profile)
    overall_key = "full_overall" if normalized == policy.SCAN_PROFILE_FULL else "app_overall" if normalized == policy.SCAN_PROFILE_APP else "overall"
    return {
        "profile": normalized,
        "hard_elapsed_seconds": int(policy.TIMEOUTS[overall_key]),
        "minimum_memory_available_percent": _optional_float(
            "POCKETLAB_SECURITY_MIN_MEMORY_AVAILABLE_PERCENT", 1.0, 50.0
        ),
        "minimum_free_storage_bytes": (
            _bounded_int(
                "POCKETLAB_SECURITY_MIN_FREE_STORAGE_MB", 512, 64, 102_400
            )
            * 1024
            * 1024
        ),
        "battery_pause_percent": _optional_float(
            "POCKETLAB_SECURITY_BATTERY_PAUSE_PERCENT", 1.0, 95.0
        ),
        "thermal_pause_c": _optional_float(
            "POCKETLAB_SECURITY_THERMAL_PAUSE_C", 25.0, 100.0
        ),
        "max_atomic_targets": _bounded_int(
            "POCKETLAB_SECURITY_MAX_ATOMIC_TARGETS", 10_000, 1, 10_000
        ),
        "telemetry_max_age_seconds": _bounded_int(
            "POCKETLAB_SECURITY_TELEMETRY_MAX_AGE_SECONDS", 30, 1, 900
        ),
    }


def completed_atomic_target_count(
    target_statuses: Iterable[Mapping[str, Any]] | None,
) -> int:
    """Count distinct completed target/tool units in the current run."""

    completed: set[tuple[str, str]] = set()
    for item in target_statuses or ():
        if not isinstance(item, Mapping):
            continue
        if str(item.get("status") or "") not in _COMPLETED_TARGET_STATUSES:
            continue
        target_id = str(item.get("target_id") or "").strip()
        tool = str(item.get("tool") or "").strip()
        if target_id and tool:
            completed.add((target_id, tool))
    return len(completed)


def _telemetry_number(facts: Mapping[str, Any], key: str) -> float | None:
    raw = facts.get(key)
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _telemetry_age_ms(facts: Mapping[str, Any]) -> int | None:
    reported_age = _telemetry_number(facts, "telemetry_age_ms")
    if reported_age is not None and reported_age < 0:
        return None

    timestamp_age: int | None = None
    if "captured_at" in facts:
        captured_at = facts.get("captured_at")
        if not isinstance(captured_at, str) or not captured_at.strip():
            return None
        try:
            timestamp_text = captured_at.strip()
            if timestamp_text.endswith("Z"):
                timestamp_text = timestamp_text[:-1] + "+00:00"
            captured = datetime.fromisoformat(timestamp_text)
            if captured.tzinfo is None:
                captured = captured.replace(tzinfo=timezone.utc)
            delta_ms = int((time.time() - captured.timestamp()) * 1000)
        except (TypeError, ValueError, OverflowError):
            return None
        if delta_ms < 0:
            return None
        timestamp_age = delta_ms

    if reported_age is None:
        return timestamp_age
    if timestamp_age is None and "captured_at" in facts:
        return None
    return max(int(reported_age), timestamp_age or 0)


def scan_budget_decision(
    *,
    profile: str,
    started_monotonic: float,
    completed_atomic_targets: int,
    telemetry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    facts = dict(telemetry or resource_snapshot())
    configured = scan_budget_policy(profile)
    elapsed = max(0.0, time.monotonic() - float(started_monotonic))
    telemetry_age_ms = _telemetry_age_ms(facts)
    telemetry_max_age_ms = int(configured["telemetry_max_age_seconds"]) * 1000
    if telemetry_age_ms is None:
        telemetry_freshness = "unknown"
    elif telemetry_age_ms > telemetry_max_age_ms:
        telemetry_freshness = "stale"
    else:
        telemetry_freshness = "fresh"
    reason = ""
    outcome = "continue"
    if elapsed >= int(configured["hard_elapsed_seconds"]):
        outcome, reason = "partial_budget_exhausted", "elapsed_budget_exhausted"
    elif completed_atomic_targets >= int(configured["max_atomic_targets"]):
        outcome, reason = "pause_at_checkpoint", "configured_target_budget"
    elif telemetry_freshness == "unknown":
        outcome, reason = "pause_at_checkpoint", "telemetry_age_unknown"
    elif telemetry_freshness == "stale":
        outcome, reason = "pause_at_checkpoint", "telemetry_stale"
    else:
        memory_threshold = configured.get("minimum_memory_available_percent")
        memory_value = _telemetry_number(facts, "available_memory_percent")
        if memory_threshold is not None and memory_value is not None and memory_value < float(memory_threshold):
            outcome, reason = "pause_at_checkpoint", "memory_pressure"
        storage_threshold = int(configured["minimum_free_storage_bytes"])
        storage_value = _telemetry_number(facts, "free_storage")
        if outcome == "continue" and storage_value is not None and storage_value < storage_threshold:
            outcome, reason = "pause_at_checkpoint", "storage_pressure"
        battery_threshold = configured.get("battery_pause_percent")
        battery_value = _telemetry_number(facts, "battery_percent")
        if (
            outcome == "continue"
            and battery_threshold is not None
            and battery_value is not None
            and facts.get("charging") is False
            and float(battery_value) <= float(battery_threshold)
        ):
            outcome, reason = "pause_at_checkpoint", "battery_policy_threshold"
        thermal_threshold = configured.get("thermal_pause_c")
        thermal_value = _telemetry_number(facts, "temperature_c")
        if outcome == "continue" and thermal_threshold is not None and thermal_value is not None and thermal_value >= float(thermal_threshold):
            outcome, reason = "pause_at_checkpoint", "thermal_policy_threshold"
    return policy.redact_value(
        {
            "outcome": outcome,
            "reason": reason or "within_budget",
            "resume_available": outcome in {"pause_at_checkpoint", "partial_budget_exhausted"},
            "completed_atomic_targets": max(0, int(completed_atomic_targets)),
            "elapsed_seconds": round(elapsed, 3),
            "policy": configured,
            "telemetry": facts,
            "telemetry_freshness": {
                "status": telemetry_freshness,
                "age_ms": telemetry_age_ms,
                "max_age_ms": telemetry_max_age_ms,
            },
            "sanitized": True,
        }
    )


@dataclass(slots=True)
class FullCheckpointLedger:
    run_id: str
    source_revision: str
    scanner_intelligence: Mapping[str, Any]
    _path: Path = field(init=False, repr=False)
    _payload: dict[str, Any] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        safe_run = evidence.safe_run_id(self.run_id)
        self._path = evidence.security_root() / "checkpoints" / "full" / f"{safe_run}.json"
        existing = evidence.read_json(self._path, None)
        if self._path.is_file():
            if not isinstance(existing, dict):
                raise RuntimeError("Full checkpoint is unreadable")
            if (
                existing.get("schema") != CHECKPOINT_SCHEMA
                or existing.get("run_id") != safe_run
                or existing.get("profile") != policy.SCAN_PROFILE_FULL
                or not isinstance(existing.get("targets"), list)
                or not all(isinstance(item, dict) for item in existing["targets"])
            ):
                raise RuntimeError("Full checkpoint is incompatible")
            existing_status = str(existing.get("status") or "unknown")
            if existing_status not in _CHECKPOINT_RESUMABLE_STATUSES:
                raise RuntimeError("Full checkpoint is terminal and cannot be restarted")
            # A worker restart must not erase target records already committed
            # by the interrupted run. Keep the prior ledger metadata and only
            # advance its observation timestamp.
            self._payload = policy.redact_value(existing)
            self._payload["updated_at"] = deps.now_utc_iso()
            self._payload["sanitized"] = True
            self._persist()
            return
        self._payload: dict[str, Any] = {
            "schema": CHECKPOINT_SCHEMA,
            "run_id": safe_run,
            "profile": policy.SCAN_PROFILE_FULL,
            "source_revision": str(self.source_revision or "")[:128],
            "scanner_intelligence": policy.redact_value(dict(self.scanner_intelligence)),
            "status": "running",
            "resume_available": False,
            "created_at": deps.now_utc_iso(),
            "updated_at": deps.now_utc_iso(),
            "targets": [],
            "sanitized": True,
        }
        self._persist()

    @property
    def path(self) -> Path:
        return self._path

    def _persist(self) -> None:
        evidence.write_json(self._path, self._payload)

    def record(
        self,
        target_status: Mapping[str, Any],
        *,
        compatibility_identity: Mapping[str, Any] | None = None,
        resume_eligible: bool = False,
    ) -> None:
        status = policy.redact_value(dict(target_status))
        compatibility = policy.redact_value(dict(compatibility_identity or {}))
        record = {
            "target_id": str(status.get("target_id") or "")[:120],
            "tool": str(status.get("tool") or "")[:80],
            "status": str(status.get("status") or "unknown")[:80],
            "finding_count": max(0, int(status.get("finding_count") or 0)),
            "evidence_ref": str(status.get("evidence_ref") or "")[:500] or None,
            "completed_at": deps.now_utc_iso(),
            "resume_eligible": bool(
                resume_eligible
                and compatibility_identity
                and cache_identity_is_complete(compatibility_identity)
                and str(status.get("status") or "unknown")[:80]
                in _COMPLETED_TARGET_STATUSES
                and durable_evidence_ref(self.run_id, status.get("evidence_ref"))
            ),
            "compatibility_digest": digest(compatibility_identity) if compatibility_identity else None,
            "compatibility": {
                key: compatibility.get(key)
                for key in (
                    "schema",
                    "contract_id",
                    "target_fingerprint",
                    "scanner",
                    "scanner_version",
                    "scanner_artifact_revision",
                    "scanner_db_revision",
                    "policy_revision",
                    "exclusion_revision",
                    "scanner_configuration_revision",
                    "secret_mode",
                    "sbom_format",
                    "sbom_generator",
                    "sbom_schema",
                )
                if compatibility.get(key) is not None
            },
            "provenance": str(status.get("provenance") or "executed")[:80],
        }
        targets = [
            item
            for item in self._payload.get("targets", [])
            if not (
                item.get("target_id") == record["target_id"]
                and item.get("tool") == record["tool"]
            )
        ]
        targets.append(record)
        self._payload["targets"] = targets
        self._payload["resume_available"] = any(
            bool(item.get("resume_eligible")) for item in targets
        )
        self._payload["updated_at"] = deps.now_utc_iso()
        self._persist()

    def finish(self, *, status: str, resume_available: bool) -> None:
        self._payload["status"] = str(status or "unknown")[:80]
        self._payload["resume_available"] = bool(resume_available)
        self._payload["updated_at"] = deps.now_utc_iso()
        self._persist()


def checkpoint_run_state(run_id: str) -> dict[str, Any] | None:
    safe_run = evidence.safe_run_id(run_id)
    path = evidence.security_root() / "checkpoints" / "full" / f"{safe_run}.json"
    payload = evidence.read_json(path, None)
    if not isinstance(payload, dict):
        return None
    if (
        payload.get("schema") != CHECKPOINT_SCHEMA
        or payload.get("run_id") != safe_run
        or payload.get("profile") != policy.SCAN_PROFILE_FULL
        or not isinstance(payload.get("targets"), list)
        or not all(isinstance(item, dict) for item in payload["targets"])
    ):
        return None
    return payload


def cache_provenance(
    entry: Mapping[str, Any],
    *,
    current_profile: str,
    source_run: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    identity = entry.get("identity") if isinstance(entry.get("identity"), Mapping) else {}
    checkpoint = entry.get("checkpoint") if isinstance(entry.get("checkpoint"), Mapping) else {}
    identity_digest = str(entry.get("identity_digest") or "")
    target_payload = entry.get("target") if isinstance(entry.get("target"), Mapping) else {}
    target_id = str(identity.get("target_id") or "")
    scanner_db_revision = str(identity.get("scanner_db_revision") or "")
    if (
        not identity
        or not identity_digest
        or identity_digest != digest(identity)
        or identity.get("schema") != TARGET_IDENTITY_SCHEMA
        or not target_id
        or target_payload.get("target_id") != target_id
        or target_payload.get("tool") != "trivy"
        or not scanner_db_revision
        or scanner_db_revision.lower() in {"unknown", "none", "null"}
        or checkpoint.get("compatibility_digest") != identity_digest
        or checkpoint.get("resume_eligible") is not True
    ):
        return None
    source_profile_value = checkpoint.get("source_profile")
    if not isinstance(source_profile_value, str) or not source_profile_value.strip():
        return None
    try:
        normalized_current = policy.normalize_scan_profile(current_profile)
        normalized_producer = policy.normalize_scan_profile(source_profile_value)
    except ValueError:
        return None
    compatible_profiles = identity.get("compatible_profiles")
    if not isinstance(compatible_profiles, list) or normalized_current not in compatible_profiles:
        return None
    producer_run_id = str(checkpoint.get("source_run_id") or "")
    if (
        not producer_run_id
        or evidence.safe_run_id(producer_run_id) != producer_run_id
        or not isinstance(checkpoint.get("completed_at"), str)
        or not checkpoint.get("completed_at").strip()
        or not cache_identity_is_complete(identity)
        or not durable_evidence_reference(target_payload.get("evidence_ref"))
    ):
        return None
    producer_profile = normalized_producer
    checkpoint_path = evidence.security_root() / "checkpoints" / "full" / f"{producer_run_id}.json"
    ledger = checkpoint_run_state(producer_run_id) if producer_run_id else None
    if checkpoint_path.is_file() and ledger is None:
        return None
    if ledger:
        if (
            ledger.get("profile") != policy.SCAN_PROFILE_FULL
            or producer_profile != policy.SCAN_PROFILE_FULL
        ):
            return None
        target_tool = str(target_payload.get("tool") or "")
        matching = [
            item
            for item in ledger.get("targets", [])
            if item.get("target_id") == target_id and item.get("tool") == target_tool
        ]
        if len(matching) != 1:
            return None
        target = matching[0]
        if (
            target.get("status") not in _COMPLETED_TARGET_STATUSES
            or target.get("resume_eligible") is not True
            or target.get("compatibility_digest") != identity_digest
            or not target.get("evidence_ref")
            or not durable_evidence_ref(producer_run_id, target.get("evidence_ref"))
        ):
            return None
        ledger_status = str(ledger.get("status") or "unknown")
        if ledger_status in _CHECKPOINT_RESUMABLE_STATUSES:
            kind = "resumed"
        elif ledger_status in _CHECKPOINT_REUSABLE_STATUSES:
            kind = "reused"
        else:
            return None
    else:
        if producer_profile == policy.SCAN_PROFILE_FULL:
            return None
        if not isinstance(source_run, Mapping):
            return None
        source_status = str(source_run.get("status") or "unknown")
        if source_status not in _CHECKPOINT_REUSABLE_STATUSES:
            return None
        source_profile = source_run.get("scan_profile") or source_run.get("profile")
        if not source_profile:
            return None
        try:
            if policy.normalize_scan_profile(source_profile) != producer_profile:
                return None
        except ValueError:
            return None
        kind = "reused"
    return {
        "kind": kind,
        "source_run_id": producer_run_id or None,
        "source_profile": producer_profile or None,
        "cross_profile": bool(producer_profile and producer_profile != normalized_current),
        "checkpoint_compatible": True,
    }
