"""Offline coordinated cutover, called by the existing native promotion controller.

All candidate files and the database copy stay in a disposable qualification
workspace. This exercises durable multi-component installation and independent
recovery authority without claiming PM2/OPA process convergence or touching
the configured running database or its PWA symlink.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
from pathlib import Path
import shutil
import sqlite3
import time


def _runtime():
    # The already-installed controller supplies its own runtime; never import
    # code from the newly extracted source archive.
    import sys
    from scripts.dev.lite import backend_runtime_promotion as native
    sys.path.insert(0,str(native.RUNTIME_SOURCE))
    from api_fastapi.services import lite_lifecycle_release_execution as execution
    from api_fastapi.services import lite_release_trust_runtime as trust
    from api_fastapi.services import lite_release_coordinated_preflight as preflight
    from api_fastapi.services import lite_release_package as package
    from api_fastapi.services import qualification_context as qualification
    from api_fastapi.db.connection import database_path, read_connection
    return native,execution,trust,preflight,package,qualification,database_path,read_connection


def _tree_digest(root, native):
    rows = []
    size = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise native.PromotionError("coordinated_tree_unsafe","Unexpected staged file type.")
        if path.is_file():
            size += path.stat().st_size
            if size>512*1024*1024 or len(rows)>=12000:
                raise native.PromotionError("coordinated_tree_limit","Staged tree exceeded its bound.")
            rows.append({"path":path.relative_to(root).as_posix(),"sha256":native._sha256(path)})
    return native._sha256_bytes(native._canonical(rows))


def _workspace(execution,qualification,grant_id):
    execution.handoff_directory(grant_id)  # fixed validated identifier
    parent = qualification.root()/"coordinated-cutover"
    qualification._resolved_without_symlink_escape(parent,qualification.root())
    parent.mkdir(mode=0o700,exist_ok=True)
    if parent.stat().st_mode & 0o077:
        raise PermissionError("unsafe_coordinated_workspace")
    return parent/grant_id


def prepare(grant_id):
    native,execution,trust,preflight,package,q,database_path,read_connection = _runtime()
    if not execution.gate():
        raise PermissionError("coordinated_qualification_required")
    with native._FileLock(execution.state_root()/"backend-runtime"/"promotion.lock"):
        with read_connection() as conn:
            row,scope = execution.current(conn,grant_id,states=("prepared",))
            receipt = execution._receipt(conn)
        if receipt.get("policy_review",{}).get("state")!="source_unchanged":
            raise PermissionError("coordinated_policy_switch_requires_runtime_owner")
        # Re-read the exact retained assets, and the currently authenticated
        # review; no caller can supply artifact paths or a different schema.
        directory,doc = execution.read_handoff(grant_id,row["handoff_sha256"])
        execution._verify_asset_binding(doc,receipt)
        if doc["scope"]!=scope or doc["binding_sha256"]!=row["binding_sha256"]:
            raise PermissionError("coordinated_handoff_binding_changed")
        root = _workspace(execution,q,grant_id)
        root.mkdir(mode=0o700,exist_ok=False)
        deadline = time.monotonic_ns()+240*10**9
        policy = trust._read(directory,trust.FILES["policy_sha256"],trust.MAX_BYTES)
        migrations = trust._read(directory,trust.FILES["migration_inventory_sha256"],trust.MAX_BYTES)
        declaration = package.source_declaration(trust._read(directory,trust.FILES["release_manifest_sha256"],trust.MAX_BYTES),
            source_commit=scope["source_commit"],release_tag=scope["release_tag"])
        with trust._open_controlled(directory,package.SOURCE_ASSET,package.MAX_SOURCE_BYTES) as (stream,_):
            staged = preflight._stage_source(stream,root/"source",declaration=declaration,policy_document=policy,
                migration_document=migrations,deadline_ns=deadline)
        with trust._open_controlled(directory,"dist.zip",trust.MAX_ARTIFACT) as (stream,_):
            frontend = preflight._frontend(stream,root/"frontend",receipt,deadline)
        checkpoint = root/"checkpoint.sqlite3"
        checkpoint_info = preflight._checkpoint(checkpoint,expected_schema=scope["current_schema"],deadline_ns=deadline)
        os.chmod(checkpoint,0o600)
        from api_fastapi.db.migrations import discover_migrations
        contract = [{"version":m.version,"name":m.name,"checksum":m.checksum}
                    for m in discover_migrations(root/"source"/package.MIGRATION_PREFIX)]
        if native._target_schema(contract)!=scope["target_schema"]:
            raise PermissionError("coordinated_migration_contract_changed")
        validation = native.validate_database(checkpoint,contract,expected_schema=scope["current_schema"])
        checkpoint_sha = validation["sha256"]
        # The offline copy is not the running device and cannot revive a
        # grant. Its independently approved checkpoint is the recovery target.
        summary = {"schema_version":1,"grant_id":grant_id,"handoff_sha256":row["handoff_sha256"],
            "scope":scope,"checkpoint_sha256":checkpoint_sha,"contract_sha256":native._sha256_bytes(native._canonical(contract)),
            "source_tree_sha256":_tree_digest(root/"source",native),"frontend_tree_sha256":_tree_digest(root/"frontend",native),
            "source_evidence":staged,"frontend_evidence":frontend,"checkpoint":checkpoint_info,
            "mode":"offline_qualification","production_execution":False}
        native._atomic_json(root/"preflight.json",summary,redact=False)
        return {**summary,"status":"checkpoint_ready","preflight_sha256":native._sha256(root/"preflight.json")}


def _pin(native,key,environment_name):
    expected = os.environ.get(environment_name,"")
    if native._safe_digest(expected,label="independent key pin")!=native._sha256(key):
        raise PermissionError("independent_authority_key_mismatch")
    return native._load_public_key(key)


def _migrate_copy(path,source,contract,scope,native):
    from api_fastapi.db.migrations import discover_migrations,_statements
    from api_fastapi.services.lite_release_migration_rehearsal import _authorizer,MAX_STATEMENTS
    from api_fastapi.services import lite_release_package as package
    deadline = time.monotonic_ns()+120*10**9
    with contextlib.closing(sqlite3.connect(path,isolation_level=None)) as conn:
        conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA trusted_schema=OFF")
        conn.set_progress_handler(lambda:int(time.monotonic_ns()>=deadline),1000)
        conn.execute("BEGIN IMMEDIATE")
        for m in discover_migrations(source/package.MIGRATION_PREFIX)[scope["current_schema"]:]:
            conn.set_authorizer(_authorizer)
            try:
                for i,statement in enumerate(_statements(m.sql)):
                    if i>=MAX_STATEMENTS or time.monotonic_ns()>=deadline:
                        raise PermissionError("coordinated_migration_budget")
                    conn.execute(statement)
            finally:
                conn.set_authorizer(None)
            conn.execute("INSERT INTO schema_migrations(version,name,applied_at,checksum) VALUES(?,?,?,?)",
                (m.version,m.name,native._utc(),m.checksum))
        # The offline clone must not carry executable authority into a new
        # generation. No standing permission is transferred by installation.
        conn.execute("UPDATE lite_lifecycle_workspace SET authority_epoch=authority_epoch+1")
        conn.execute("UPDATE lite_lifecycle_grants SET revoked_at=? WHERE revoked_at IS NULL",(native._utc(),))
        conn.execute("UPDATE lite_lifecycle_release_execution SET state='revoked',revoked_at=? WHERE state IN ('pending','claimed','prepared','cutover_claimed')",(native._utc(),))
        conn.execute("UPDATE lite_lifecycle_policy_execution SET revoked_at=? WHERE revoked_at IS NULL",(native._utc(),))
        conn.execute("COMMIT")
    return native.validate_database(path,contract,expected_schema=scope["target_schema"])


def activate(grant_id,*,authorization,promotion_public_key,recovery_authorization,recovery_public_key,confirm_cutover):
    native,execution,trust,preflight,package,q,database_path,read_connection = _runtime()
    if not confirm_cutover or not execution.gate():
        raise PermissionError("explicit_isolated_cutover_required")
    from cryptography.hazmat.primitives import serialization
    pk = _pin(native,promotion_public_key,"POCKETLAB_RELEASE_PROMOTION_KEY_SHA256")
    rk = _pin(native,recovery_public_key,"POCKETLAB_RELEASE_RECOVERY_KEY_SHA256")
    if pk.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)==rk.public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw):
        raise PermissionError("independent_recovery_key_required")
    root = _workspace(execution,q,grant_id)
    with native._FileLock(execution.state_root()/"backend-runtime"/"promotion.lock"):
        with read_connection() as conn:
            row,scope = execution.current(conn,grant_id,states=("prepared",))
        doc = native._read_json(root/"preflight.json",label="coordinated checkpoint")
        directory, handoff = execution.read_handoff(grant_id,row["handoff_sha256"])
        if (doc["scope"]!=scope or doc["handoff_sha256"]!=row["handoff_sha256"]
                or handoff["scope"]!=scope or doc["grant_id"]!=grant_id
                or doc["checkpoint_sha256"]!=native._sha256(root/"checkpoint.sqlite3")
                or doc["source_tree_sha256"]!=_tree_digest(root/"source",native)
                or doc["frontend_tree_sha256"]!=_tree_digest(root/"frontend",native)):
            raise PermissionError("coordinated_checkpoint_changed")
        # This signed contract is a rehearsal-only external authorization,
        # bound to exact handoff, checkpoint, source and frontend tree.
        device = "qualification-"+os.environ["POCKETLAB_QUALIFICATION_RUN_ID"]
        expected = {"candidate_sha":scope["source_commit"],"current_production_sha":scope["baseline_commit"],
            "target_device_id":device,"target_schema":scope["target_schema"],"artifact_sha256":scope["source_sha256"],
            "backup_receipt_sha256":doc["checkpoint_sha256"],"restore_receipt_sha256":doc["checkpoint_sha256"],
            "preflight_sha256":native._sha256(root/"preflight.json")}
        auth = native.verify_authorization(authorization,expected=expected,public_key=promotion_public_key)
        inputs = native.PromotionInputs(execution.state_root(),database_path(),root/"source",scope["source_commit"],
            scope["baseline_commit"],device,scope["source_sha256"],{}, {}, {},expected["preflight_sha256"])
        controller = native.PromotionController(inputs,native.SimulationAdapter())
        recovery_expected = {"candidate_sha":scope["source_commit"],"current_production_sha":scope["baseline_commit"],
            "target_device_id":device,"checkpoint_sha256":doc["checkpoint_sha256"]}
        recovery_digest = controller._verify_recovery(recovery_authorization,recovery_public_key,recovery_expected)
        if native.reconcile_promotions(execution.state_root())["status"]!="stable":
            raise PermissionError("unresolved_promotion_journal")
        from api_fastapi.services.lite_lifecycle_policy_execution import prove_loaded
        if not prove_loaded(scope["policy_baseline"]):
            raise PermissionError("loaded_policy_identity_unproved")
        os.environ["POCKETLAB_PROCESS_ROLE"]="coordinated-promotion-controller"
        controller._journal({"phase":"admitted","status":"running","mode":"offline_qualification",
            "grant_id":grant_id,"handoff_sha256":row["handoff_sha256"],"checkpoint_sha256":doc["checkpoint_sha256"],
            "authorization_digest":auth["authorization_digest"],"recovery_authorization_digest":recovery_digest,
            "candidate_sha":scope["source_commit"],"current_production_sha":scope["baseline_commit"]})
        controller._consume_once("promotion",auth["authorization_digest"])
        execution.claim_cutover(grant_id,row["handoff_sha256"],auth["authorization_digest"])
        try:
            from api_fastapi.db.migrations import discover_migrations
            contract = [{"version":m.version,"name":m.name,"checksum":m.checksum}
                        for m in discover_migrations(root/"source"/package.MIGRATION_PREFIX)]
            if native._sha256_bytes(native._canonical(contract))!=doc["contract_sha256"]:
                raise PermissionError("coordinated_migration_contract_changed")
            target = root/"generation"
            target.mkdir(mode=0o700,exist_ok=False)
            database = target/"database.sqlite3"
            native._copy_sqlite_backup(root/"checkpoint.sqlite3",database)
            migration = _migrate_copy(database,root/"source",contract,scope,native)
            controller._journal({"phase":"database_staged","status":"running","database_sha256":migration["sha256"]})
            # One atomic generation manifest makes the coordinated offline
            # state visible. The production pointers are never changed.
            generation = {"schema_version":1,"source_commit":scope["source_commit"],
                "frontend_sha256":scope["frontend_sha256"],"native_tree_sha256":doc["source_tree_sha256"],
                "policy_revision":scope["policy_baseline"],"schema":scope["target_schema"],
                "database_sha256":migration["sha256"],"handoff_sha256":row["handoff_sha256"],
                "production_execution":False,"runtime_convergence":"not_exercised"}
            with read_connection() as conn:
                current,_ = execution.current(conn,grant_id,states=("cutover_claimed",))
                if current["cutover_authorization_sha256"]!=auth["authorization_digest"]:
                    raise PermissionError("cutover_authority_changed")
            controller._journal({"phase":"cutover_started","status":"running"})
            native._atomic_json(root/"active-generation.json",generation,redact=False)
            if native._read_json(root/"active-generation.json",label="offline generation")!=generation:
                raise PermissionError("coordinated_generation_unproved")
            execution.finish_cutover(grant_id,auth["authorization_digest"],rehearsed=True)
            controller._journal({"phase":"committed","status":"rehearsed","runtime_convergence":"not_exercised"})
            return {"status":"rehearsed","generation":generation,"production_execution":False}
        except Exception:
            # Never overwrite any running database. Retain the immutable
            # checkpoint and partial generation for explicit reconciliation.
            controller._journal({"phase":"manual_recovery_required","status":"blocked",
                "failure_code":"coordinated_offline_cutover_failed"})
            execution.finish_cutover(grant_id,auth["authorization_digest"],rehearsed=False)
            raise
