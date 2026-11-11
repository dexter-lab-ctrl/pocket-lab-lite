from __future__ import annotations

import json
from pathlib import Path
import shutil
import zipfile

import pytest

from scripts.dev.lite import backend_runtime_promotion as promotion


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/db/schema"


def _artifact(tmp_path: Path, source_sha: str = "a" * 40):
    contract = promotion.migration_contract(SCHEMA)
    records = [
        ("runtime/api_fastapi/db/schema/0043_system_health_intelligence.sql", (SCHEMA / "0043_system_health_intelligence.sql").read_bytes(), 0o644),
        ("runtime/api_fastapi/db/schema/0044_system_health_audit.sql", (SCHEMA / "0044_system_health_audit.sql").read_bytes(), 0o644),
        ("bootstrap/scripts/start-dashboard.sh", b"#!/usr/bin/env bash\nexit 0\n", 0o755),
        ("controller/backend_runtime_promotion.py", promotion.CONTROLLER_SOURCE.read_bytes(), 0o755),
    ]
    inner = promotion._artifact_inner_manifest(records, source_sha, contract)
    artifact = tmp_path / "backend.zip"
    manifest = tmp_path / "backend.manifest.json"
    checksums = tmp_path / "backend.checksums.txt"
    promotion._zip_bytes(artifact, records, inner)
    external = {
        **inner,
        "artifact_name": artifact.name,
        "artifact_sha256": promotion._sha256(artifact),
        "artifact_size_bytes": artifact.stat().st_size,
        "manifest_name": manifest.name,
        "checksums_name": checksums.name,
    }
    promotion._atomic_json(manifest, external, mode=0o644)
    checksums.write_text(
        f"{external['artifact_sha256']}  {artifact.name}\n"
        f"{promotion._sha256(manifest)}  {manifest.name}\n",
        encoding="utf-8",
    )
    return artifact, manifest, checksums, external, contract


def _database(tmp_path: Path, contract):
    database = tmp_path / "state" / promotion.DATABASE_NAME
    promotion._make_test_database(database, contract, 42)
    return database


def test_backend_artifact_is_exact_sha_bound_and_rejects_path_traversal(tmp_path: Path):
    artifact, manifest, checksums, _external, _contract = _artifact(tmp_path)

    verified = promotion.verify_artifact(artifact, manifest, checksums)

    assert verified["status"] == "verified"
    assert verified["source_commit"] == "a" * 40
    assert verified["required_schema"] == 44
    assert verified["feature_migrations"] == [43, 44]
    assert promotion._safe_relative("runtime/api_fastapi/pocket.py").as_posix() == "runtime/api_fastapi/pocket.py"
    with pytest.raises(promotion.PromotionError, match="unsafe"):
        promotion._safe_relative("../escape.txt")


def test_backup_restore_and_schema_42_to_44_rehearsal_are_independent(tmp_path: Path):
    artifact, manifest, checksums, external, contract = _artifact(tmp_path)
    database = _database(tmp_path, contract)

    before = promotion.validate_database(database, contract, expected_schema=42)
    backup = promotion.create_backup(
        database=database,
        backup_root=tmp_path / "backup",
        source_sha="c" * 40,
        device_id="pocket-lab-lite-server",
        contract=contract,
    )
    restore = promotion.restore_rehearsal(
        backup_manifest=Path(backup["backup_manifest"]),
        restore_root=tmp_path / "restore",
        contract=contract,
    )
    migration = promotion.migration_rehearsal(
        backup_manifest=Path(backup["backup_manifest"]),
        artifact=artifact,
        artifact_manifest=manifest,
        rehearsal_root=tmp_path / "migration",
        old_schema=42,
    )

    assert before["schema_version"] == 42
    assert restore["status"] == "verified"
    assert migration["status"] == "verified"
    assert migration["source_schema"] == 42
    assert migration["target_schema"] == 44
    assert migration["applied_migrations"] == [43, 44]
    assert migration["old_runtime_code_rollback_compatible"] is False
    assert promotion.validate_database(database, contract, expected_schema=42)["sha256"] == before["sha256"]
    assert external["artifact_sha256"] == promotion.verify_artifact(artifact, manifest, checksums)["artifact_sha256"]


def _authorization_files(tmp_path: Path, *, candidate: str, current: str, device: str, artifact_sha: str, backup: dict, restore: dict, preflight: Path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    recovery_key = Ed25519PrivateKey.generate()
    private = tmp_path / "promotion.key"
    public = tmp_path / "promotion.pub"
    recovery_private = tmp_path / "recovery.key"
    recovery_public = tmp_path / "recovery.pub"
    private.write_bytes(key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
    recovery_private.write_bytes(recovery_key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
    private.chmod(0o600)
    recovery_private.chmod(0o600)
    public.write_text(promotion._b64u(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)) + "\n", encoding="ascii")
    recovery_public.write_text(promotion._b64u(recovery_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)) + "\n", encoding="ascii")
    auth = tmp_path / "authorization.json"
    payload = promotion.authorization_payload(
        candidate_sha=candidate,
        current_sha=current,
        device_id=device,
        target_schema=44,
        artifact_sha256=artifact_sha,
        backup_receipt_sha256=promotion._sha256_bytes(promotion._canonical(backup)),
        restore_receipt_sha256=promotion._sha256_bytes(promotion._canonical(restore)),
        preflight_sha256=promotion._sha256(preflight),
        audit_identity="test-owner",
    )
    promotion.issue_authorization(private_key=private, output=auth, payload=payload)
    return private, public, recovery_private, recovery_public, auth


def test_atomic_lifecycle_commits_and_health_failure_rolls_back(tmp_path: Path):
    artifact, manifest, checksums, external, contract = _artifact(tmp_path, source_sha="b" * 40)
    database = _database(tmp_path, contract)
    backup = promotion.create_backup(database=database, backup_root=tmp_path / "backup", source_sha="c" * 40, device_id="server", contract=contract)
    restore = promotion.restore_rehearsal(backup_manifest=Path(backup["backup_manifest"]), restore_root=tmp_path / "restore", contract=contract)
    migration = promotion.migration_rehearsal(backup_manifest=Path(backup["backup_manifest"]), artifact=artifact, artifact_manifest=manifest, rehearsal_root=tmp_path / "migration", old_schema=42)
    migration_receipt = json.loads(Path(migration["migration_receipt"]).read_text(encoding="utf-8"))
    migration_receipt["migration_contract"] = contract
    preflight = tmp_path / "preflight.json"
    promotion._atomic_json(preflight, {"status": "admissible", "admitted": True})
    _private, public, recovery_private, recovery_public, auth = _authorization_files(
        tmp_path,
        candidate="b" * 40,
        current="c" * 40,
        device="server",
        artifact_sha=external["artifact_sha256"],
        backup=json.loads(Path(backup["backup_receipt"]).read_text(encoding="utf-8")),
        restore=json.loads(Path(restore["restore_receipt"]).read_text(encoding="utf-8")),
        preflight=preflight,
    )
    checkpoint = tmp_path / "checkpoint.sqlite3"
    promotion._copy_sqlite_backup(database, checkpoint)
    recovery = tmp_path / "recovery.json"
    promotion.issue_recovery_authorization(private_key=recovery_private, output=recovery, candidate_sha="b" * 40, current_sha="c" * 40, device_id="server", checkpoint_sha256=promotion._sha256(checkpoint), audit_identity="test-recovery")
    staged = promotion.stage_artifact(artifact=artifact, manifest_path=manifest, checksums_path=checksums, staging_root=tmp_path / "staging", expected_device_id="server", target_device_id="server")
    state = tmp_path / "state"
    (state / "backend-runtime").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(artifact, state / "backend-runtime" / "artifact.zip")
    inputs = promotion.PromotionInputs(
        state_root=state,
        database=database,
        release_root=Path(staged["release_root"]),
        candidate_sha="b" * 40,
        current_sha="c" * 40,
        device_id="server",
        artifact_sha256=external["artifact_sha256"],
        backup_receipt=json.loads(Path(backup["backup_receipt"]).read_text(encoding="utf-8")),
        restore_receipt=json.loads(Path(restore["restore_receipt"]).read_text(encoding="utf-8")),
        migration_receipt=migration_receipt,
        preflight_sha256=promotion._sha256(preflight),
        artifact=artifact,
    )
    committed = promotion.PromotionController(inputs, promotion.SimulationAdapter()).activate(authorization=auth, promotion_public_key=public, recovery_authorization=recovery, recovery_public_key=recovery_public, confirm_cutover=True, isolated=True)
    assert committed["status"] == "committed"
    assert promotion.validate_database(database, contract, expected_schema=44)["schema_version"] == 44
    assert json.loads((state / "backend-runtime/active.json").read_text(encoding="utf-8"))["source_commit"] == "b" * 40
    with pytest.raises(promotion.PromotionError, match="already been consumed"):
        promotion.PromotionController(inputs, promotion.SimulationAdapter()).activate(authorization=auth, promotion_public_key=public, recovery_authorization=recovery, recovery_public_key=recovery_public, confirm_cutover=True, isolated=True)


def test_isolated_failure_modes_and_restart_reconciliation_fail_closed(tmp_path: Path):
    artifact, manifest, checksums, _external, _contract = _artifact(tmp_path, source_sha="d" * 40)
    health_workspace = tmp_path / "health-failure"
    health = promotion.qualify_isolated(artifact=artifact, manifest_path=manifest, checksums_path=checksums, workspace=health_workspace, device_id="server", failure_mode="health-failure")
    assert health["status"] == "PASS"
    assert health["lifecycle"]["reason_code"] == "promotion_rolled_back"
    assert not any((health_workspace / name).exists() for name in ("promotion-key", "recovery-key", "authorization.json", "recovery.json"))

    writes_workspace = tmp_path / "writes-observed"
    writes = promotion.qualify_isolated(artifact=artifact, manifest_path=manifest, checksums_path=checksums, workspace=writes_workspace, device_id="server", failure_mode="writes-observed")
    assert writes["status"] == "PASS"
    assert writes["lifecycle"]["reason_code"] == "post_promotion_writes_observed"
    state_root = writes_workspace / "state"
    reconciled = promotion.reconcile_promotions(state_root)
    assert reconciled["status"] == "recovery_required"
    assert reconciled["destructive_action"] == "none"
    assert all(item["destructive_action"] == "none" for item in reconciled["journals"])


def test_authority_and_final_confirmation_are_separate_gates(tmp_path: Path):
    _artifact(tmp_path)
    with pytest.raises(promotion.PromotionError, match="production promotion authority"):
        promotion.authorization_payload(candidate_sha="a" * 40, current_sha="c" * 40, device_id="server", target_schema=44, artifact_sha256="d" * 64, backup_receipt_sha256="e" * 64, restore_receipt_sha256="f" * 64, preflight_sha256="1" * 64, audit_identity="qualification-owner", authority="qualification-owner")

    adapter = promotion.SimulationAdapter()
    assert adapter.snapshot()["services"]["pocket-worker"] == "online"
