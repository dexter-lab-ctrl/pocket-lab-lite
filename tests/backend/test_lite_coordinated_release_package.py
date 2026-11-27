"""Source package contract fixtures; never use production source or credentials."""
import hashlib
import io
import zipfile

import pytest
from pocket_lab_test_utils import ensure_runtime_path

ensure_runtime_path()
from api_fastapi.services import lite_release_package as package
from api_fastapi.services.lite_lifecycle_contract import canonical_bytes
from api_fastapi.services.lite_release_trust import TrustError


def fixture_files():
    files = {name: b"fixture" for name in package.REQUIRED}
    files[package.MIGRATION_PREFIX + "0001_initial.sql"] = b"SELECT 1;"
    return files


def inventory(files, prefix, suffix):
    return canonical_bytes([{"path": name, "sha256": hashlib.sha256(data).hexdigest()}
                            for name, data in sorted(files.items())
                            if name.startswith(prefix) and name.endswith(suffix)])


def candidate(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return stream, {"source_commit": "a" * 40, "sha256": hashlib.sha256(stream.getvalue()).hexdigest()}


def inspect(files, *, inventories=None):
    stream, declaration = candidate(files)
    original = inventories if inventories is not None else files
    return package.inspect_source(stream, declaration=declaration,
        policy_inventory=inventory(original, package.POLICY_PREFIX, ".rego"),
        migration_inventory=inventory(original, package.MIGRATION_PREFIX, ".sql"))


def test_exact_inventory_review_is_not_execution():
    result = inspect(fixture_files())
    assert result["state"] == "inventory_verified"
    assert result["execution_eligible"] is False


@pytest.mark.parametrize("name", ["../escape", "/absolute", "folder/../escape", "C:/escape", "a\\b", ".git/config"])
def test_traversal_rejected(name):
    files = fixture_files()
    files[name] = b"bad"
    with pytest.raises(TrustError):
        inspect(files)


def test_policy_tamper_and_missing_backend():
    original = fixture_files()
    files = dict(original)
    files[package.POLICY_PREFIX + "pocketlab/pocketlab.rego"] = b"tampered"
    with pytest.raises(TrustError, match="source_inventory_digest_mismatch"):
        inspect(files, inventories=original)
    files = dict(original)
    del files[package.RUNTIME + "api_fastapi/services/release_runtime.py"]
    with pytest.raises(TrustError, match="source_package_incomplete"):
        inspect(files)


def test_additional_policy_module_rejected():
    original = fixture_files()
    files = dict(original)
    files[package.POLICY_PREFIX + "pocketlab/extra.rego"] = b"package extra"
    with pytest.raises(TrustError, match="source_inventory_unexpected_member"):
        inspect(files, inventories=original)


def test_archive_digest_tamper():
    files = fixture_files()
    stream, declaration = candidate(files)
    declaration["sha256"] = "0" * 64
    with pytest.raises(TrustError, match="source_archive_digest_mismatch"):
        package.inspect_source(stream, declaration=declaration,
            policy_inventory=inventory(files, package.POLICY_PREFIX, ".rego"),
            migration_inventory=inventory(files, package.MIGRATION_PREFIX, ".sql"))


def test_legacy_and_fixed_declaration():
    assert package.source_declaration(b"{}", source_commit="a"*40, release_tag="tag") is None
    declaration = {"schema_version": 1, "artifact": package.SOURCE_ASSET,
                   "sha256": "b"*64, "source_commit": "a"*40}
    raw = {"source_commit": "a"*40, "release_tag": "tag", "coordinated_source": declaration}
    assert package.source_declaration(canonical_bytes(raw), source_commit="a"*40, release_tag="tag") == declaration
    declaration["artifact"] = "../source.zip"
    with pytest.raises(TrustError):
        package.source_declaration(canonical_bytes(raw), source_commit="a"*40, release_tag="tag")


def test_append_only_is_review_required_and_applied_change_blocked():
    old = fixture_files()
    new = {**old, package.MIGRATION_PREFIX + "0002_next.sql": b"SELECT 2;"}
    def compare(candidate_files):
        return package.migration_inventory_comparison(
            inventory(old, package.MIGRATION_PREFIX, ".sql"),
            inventory(candidate_files, package.MIGRATION_PREFIX, ".sql"), current_schema=1)
    assert compare(old)["state"] == "unchanged"
    assert compare(new)["pending_versions"] == [2]
    assert compare(new)["state"] == "review_required"
    new[package.MIGRATION_PREFIX + "0001_initial.sql"] = b"SELECT 3;"
    assert compare(new)["state"] == "incompatible"


def test_unbound_policy_data_rejected():
    files = fixture_files()
    files[package.POLICY_PREFIX + "pocketlab/data.json"] = b"{}"
    with pytest.raises(TrustError, match="policy_data_inventory_unsupported"):
        inspect(files)


def test_applied_ledger_checks_actual_recorded_checksum():
    files = fixture_files()
    raw = inventory(files, package.MIGRATION_PREFIX, ".sql")
    rows = [{"version": 1, "name": "initial", "checksum": hashlib.sha256(b"SELECT 1;").hexdigest()}]
    assert package.applied_migration_evidence(raw, raw, rows, current_schema=1)["state"] == "ledger_matches"
    rows[0]["checksum"] = "0" * 64
    assert package.applied_migration_evidence(raw, raw, rows, current_schema=1)["state"] == "incompatible"
    assert package.applied_migration_evidence(raw, raw, [], current_schema=1)["state"] == "unknown"
