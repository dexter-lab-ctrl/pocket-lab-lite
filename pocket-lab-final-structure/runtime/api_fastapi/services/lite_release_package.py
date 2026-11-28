"""T3/T4 authenticated source package review, owned by the release child.

The existing signed release-manifest digest binds the optional source archive
declaration. No new signature format, extraction, installation or authority
is introduced here. A v1 release without the declaration remains reviewable
but cannot be considered a complete coordinated candidate.
"""
from __future__ import annotations

import hashlib
from pathlib import PurePosixPath
import re
import stat
import zipfile

from .lite_lifecycle_contract import canonical_bytes
from .lite_release_trust import TrustError, strict_json

SOURCE_ASSET = "pocketlab-lite-source.zip"
MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_ENTRIES = 12000
MAX_MEMBER_BYTES = 64 * 1024 * 1024
from .lite_release_package_profile import (
    POLICY_PREFIX, MIGRATION_PREFIX, RUNTIME, BOOTSTRAP, RUNTIME_PROFILE,
    INSTALLABLE_RUNTIME_PROFILE, DEPENDENCY_MANIFEST, RUNTIME_PROFILE_ROOTS,
)
REQUIRED = frozenset({
    RUNTIME + "requirements.txt",
    RUNTIME + "api_fastapi/services/lite_policy_opa.py",
    RUNTIME + "api_fastapi/services/release_runtime.py",
    RUNTIME + "api_fastapi/services/release_update_process.py",
    BOOTSTRAP + "start-dashboard.sh",
    BOOTSTRAP + "install-pwa-ui.sh",
    POLICY_PREFIX + "pocketlab/pocketlab.rego",
    "package.json", "package-lock.json",
})
RUNTIME_PROFILE_REQUIRED = REQUIRED | {
    "scripts/dev/lite/backend_runtime_promotion.py",
    "scripts/dev/lite/coordinated_runtime_promotion.py",
    BOOTSTRAP + "lite/reconcile-runtime.sh",
}
RUNTIME_INSTALL_REQUIRED = RUNTIME_PROFILE_REQUIRED | {DEPENDENCY_MANIFEST}

def runtime_profile_member(name: str) -> bool:
    return any(name == root or name.startswith(root + "/") for root in RUNTIME_PROFILE_ROOTS)


DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def source_declaration(manifest_bytes: bytes, *, source_commit: str, release_tag: str):
    """Parse only the already signature-bound manifest, never a caller URL."""
    manifest = strict_json(manifest_bytes)
    if not isinstance(manifest, dict):
        raise TrustError("source_manifest_invalid")
    if "coordinated_source" not in manifest:
        return None
    value = manifest["coordinated_source"]
    fields = {"schema_version", "artifact", "sha256", "source_commit"}
    if not isinstance(value, dict):
        raise TrustError("source_declaration_invalid")
    version = value.get("schema_version")
    if (type(version) is not int
            or not ((version == 1 and set(value) == fields)
                    or (version == 2 and set(value) == fields | {"profile"}
                        and value.get("profile") in {RUNTIME_PROFILE, INSTALLABLE_RUNTIME_PROFILE}))
            or value["artifact"] != SOURCE_ASSET
            or not isinstance(value["sha256"], str) or not DIGEST_PATTERN.fullmatch(value["sha256"])
            or not isinstance(source_commit, str) or not SHA_PATTERN.fullmatch(source_commit)
            or value["source_commit"] != source_commit
            or manifest.get("source_commit") != source_commit
            or manifest.get("release_tag") != release_tag):
        raise TrustError("source_declaration_invalid")
    return value


def _member_name(raw: str) -> str:
    if (not raw or len(raw) > 512 or "\\" in raw or ":" in raw
            or raw.startswith("/") or any(ord(c) < 32 or ord(c) == 127 for c in raw)):
        raise TrustError("source_archive_path_invalid")
    name = raw.removesuffix("/")
    parts = name.split("/")
    if (len(parts) > 32 or any(p in ("", ".", "..") or p.casefold() == ".git" for p in parts)
            or PurePosixPath(name).as_posix() != name):
        raise TrustError("source_archive_path_invalid")
    return name


def _inventory(raw: bytes, *, prefix: str, suffix: str) -> dict[str, str]:
    rows = strict_json(raw)
    if not isinstance(rows, list) or not 1 <= len(rows) <= 512:
        raise TrustError("source_inventory_invalid")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise TrustError("source_inventory_invalid")
        name, digest = row["path"], row["sha256"]
        if (not isinstance(name, str) or _member_name(name) != name
                or not name.startswith(prefix) or not name.endswith(suffix)
                or not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest)
                or name in result):
            raise TrustError("source_inventory_invalid")
        if suffix == ".sql" and "/" in name[len(prefix):]:
            raise TrustError("migration_inventory_invalid")
        result[name] = digest
    return result


def inspect_source(stream, *, declaration, policy_inventory: bytes, migration_inventory: bytes):
    """Hash and inspect the exact open descriptor. Never extract or execute it.

    The caller owns a private, no-follow regular-file descriptor and checks
    mutation after return. The archive itself is signed indirectly through the
    existing signed release-manifest hash; independent provenance is separate.
    """
    stream.seek(0)
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_SOURCE_BYTES:
            raise TrustError("source_archive_size_limit")
        digest.update(chunk)
    if digest.hexdigest() != declaration["sha256"]:
        raise TrustError("source_archive_digest_mismatch")
    policy = _inventory(policy_inventory, prefix=POLICY_PREFIX, suffix=".rego")
    migrations = _inventory(migration_inventory, prefix=MIGRATION_PREFIX, suffix=".sql")
    expected = {**policy, **migrations}
    found = {}
    seen = set()
    files = set()
    expanded = 0
    dependency_raw = None
    try:
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            if not entries or len(entries) > MAX_ENTRIES:
                raise TrustError("source_archive_entry_limit")
            for item in entries:
                name = _member_name(item.filename)
                key = name.casefold()
                mode = (item.external_attr >> 16) & 0o170000
                if key in seen or mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise TrustError("source_archive_duplicate_or_special")
                seen.add(key)
                if item.is_dir():
                    if mode == stat.S_IFREG or item.file_size:
                        raise TrustError("source_archive_entry_invalid")
                    continue
                if mode == stat.S_IFDIR or item.flag_bits & 1:
                    raise TrustError("source_archive_entry_invalid")
                if declaration.get("profile") in {RUNTIME_PROFILE, INSTALLABLE_RUNTIME_PROFILE} and not runtime_profile_member(name):
                    raise TrustError("source_runtime_profile_member_unexpected")
                files.add(name)
                expanded += item.file_size
                if item.file_size > MAX_MEMBER_BYTES or expanded > MAX_EXPANDED_BYTES:
                    raise TrustError("source_archive_expansion_limit")
                is_policy = name.startswith(POLICY_PREFIX) and name.endswith(".rego")
                is_migration = name.startswith(MIGRATION_PREFIX) and name.endswith(".sql")
                if name.startswith(POLICY_PREFIX) and not is_policy:
                    raise TrustError("policy_data_inventory_unsupported")
                if is_policy or is_migration:
                    if name not in expected:
                        raise TrustError("source_inventory_unexpected_member")
                    if item.file_size > 256 * 1024:
                        raise TrustError("source_inventory_member_limit")
                    with archive.open(item) as member:
                        data = member.read(256 * 1024 + 1)
                    if len(data) != item.file_size or hashlib.sha256(data).hexdigest() != expected[name]:
                        raise TrustError("source_inventory_digest_mismatch")
                    found[name] = expected[name]
                if name == DEPENDENCY_MANIFEST:
                    with archive.open(item) as member:
                        dependency_raw = member.read(256 * 1024 + 1)
            # Reject a regular file that aliases an ancestor directory.
            folded_files = {name.casefold() for name in files}
            for name in seen:
                parts = name.split("/")
                if any("/".join(parts[:i]) in folded_files for i in range(1, len(parts))):
                    raise TrustError("source_archive_path_collision")
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, OSError) as exc:
        raise TrustError("source_archive_invalid") from exc
    profile = declaration.get("profile")
    required = (RUNTIME_INSTALL_REQUIRED if profile == INSTALLABLE_RUNTIME_PROFILE
                else RUNTIME_PROFILE_REQUIRED if profile == RUNTIME_PROFILE else REQUIRED)
    if set(found) != set(expected) or not required.issubset(files):
        raise TrustError("source_package_incomplete")
    if profile == INSTALLABLE_RUNTIME_PROFILE:
        try:
            dependency = strict_json(dependency_raw or b"")
        except (KeyError, ValueError, RuntimeError, OSError) as exc:
            raise TrustError("runtime_dependency_manifest_invalid") from exc
        if (not isinstance(dependency, dict)
                or dependency.get("schema_version") != 1
                or dependency.get("profile") != INSTALLABLE_RUNTIME_PROFILE
                or dependency.get("frontend_artifact") != "signed-dist.zip"
                or dependency.get("python_requirements") != RUNTIME + "requirements.txt"
                or dependency.get("node_lockfile") != "package-lock.json"
                or dependency.get("migration_root") != MIGRATION_PREFIX
                or dependency.get("policy_root") != POLICY_PREFIX):
            raise TrustError("runtime_dependency_manifest_invalid")
    return {"state": "inventory_verified", "profile": declaration.get("profile", "tracked-tree-v1"), "source_commit": declaration["source_commit"],
            "sha256": declaration["sha256"], "archive_bytes": size,
            "expanded_bytes": expanded, "file_count": len(files),
            "policy_module_count": len(policy), "migration_count": len(migrations),
            "policy_inventory_sha256": hashlib.sha256(policy_inventory).hexdigest(),
            "migration_inventory_sha256": hashlib.sha256(migration_inventory).hexdigest(),
            "execution_eligible": False}


def migration_inventory_comparison(installed: bytes, candidate: bytes, *, current_schema: int):
    """Conservative append-only comparison, not proof of migration safety.

    Applied migration contents cannot change. Registered order is consecutive.
    Changed schema is held until owner integration and recovery qualification.
    """
    old = _inventory(installed, prefix=MIGRATION_PREFIX, suffix=".sql")
    new = _inventory(candidate, prefix=MIGRATION_PREFIX, suffix=".sql")

    def versions(rows):
        result = {}
        for path, digest in rows.items():
            match = re.fullmatch(r"(\d{4})_[a-zA-Z0-9_-]+\.sql", PurePosixPath(path).name)
            if not match:
                raise TrustError("migration_inventory_invalid")
            version = int(match.group(1))
            if version < 1 or version in result:
                raise TrustError("migration_inventory_invalid")
            result[version] = (path, digest)
        return result

    before, after = versions(old), versions(new)
    if (type(current_schema) is not int or current_schema < 1
            or sorted(before) != list(range(1, max(before) + 1))
            or sorted(after) != list(range(1, max(after) + 1))
            or max(before) != current_schema):
        return {"state": "unknown", "reason_code": "migration_baseline_unconfirmed"}
    if any(after.get(version) != entry for version, entry in before.items()):
        return {"state": "incompatible", "reason_code": "applied_migration_changed"}
    if before == after:
        return {"state": "unchanged", "target_schema": current_schema}
    return {"state": "review_required", "reason_code": "migration_qualification_required",
            "target_schema": max(after), "pending_versions": list(range(current_schema + 1, max(after) + 1))}


def applied_migration_evidence(installed: bytes, candidate: bytes, rows, *, current_schema: int):
    """Compare durable applied names/checksums against both exact inventories.

    The ledger proves recorded application, not data compatibility or a
    successful rollback. No migration is executed by this review.
    """
    local = _inventory(installed, prefix=MIGRATION_PREFIX, suffix=".sql")
    remote = _inventory(candidate, prefix=MIGRATION_PREFIX, suffix=".sql")
    if type(current_schema) is not int or not 1 <= current_schema <= 512:
        return {"state": "unknown", "reason_code": "applied_schema_unconfirmed"}
    if len(rows) != current_schema or len(rows) > 512:
        return {"state": "unknown", "reason_code": "applied_schema_ledger_incomplete"}
    for version, row in enumerate(rows, 1):
        name, checksum = row["name"], row["checksum"]
        if (row["version"] != version or not isinstance(name, str)
                or not re.fullmatch(r"[a-z0-9_-]+", name)
                or not isinstance(checksum, str) or not DIGEST_PATTERN.fullmatch(checksum)):
            return {"state": "unknown", "reason_code": "applied_schema_ledger_invalid"}
        path = MIGRATION_PREFIX + f"{version:04d}_{name}.sql"
        if local.get(path) != checksum:
            return {"state": "incompatible", "reason_code": "installed_migration_checksum_mismatch"}
        if remote.get(path) != checksum:
            return {"state": "incompatible", "reason_code": "candidate_applied_migration_checksum_mismatch"}
    return {"state": "ledger_matches", "applied_count": current_schema,
            "ledger_sha256": hashlib.sha256(canonical_bytes([
                {"version": row["version"], "name": row["name"], "checksum": row["checksum"]}
                for row in rows])).hexdigest(), "execution_eligible": False}


def observe_applied_migrations(installed: bytes, candidate: bytes, *, current_schema: int):
    from ..db.connection import fast_read_connection
    try:
        with fast_read_connection(timeout_ms=250) as conn:
            rows = conn.execute("SELECT version,name,checksum FROM schema_migrations ORDER BY version LIMIT 513").fetchall()
        return applied_migration_evidence(installed, candidate, rows, current_schema=current_schema)
    except Exception:
        return {"state": "unknown", "reason_code": "applied_schema_ledger_unavailable"}
