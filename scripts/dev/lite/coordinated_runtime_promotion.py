"""Coordinated cutover through the existing native and runtime owners.

The default path remains an offline rehearsal.  A second, explicitly armed
path runs the same transaction against a disposable, run-owned FastAPI/worker/
OPA/Caddy/SQLite runtime.  It is never enabled by a normal environment or by
the frontend, and every mutable path must remain below the qualification root.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time
from urllib.parse import urlsplit
from urllib.request import urlopen


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


def _contained(path, root, *, label):
    candidate = Path(path).expanduser().resolve(strict=False)
    base = Path(root).expanduser().resolve(strict=True)
    if candidate == base:
        raise PermissionError(f"{label}_root_not_allowed")
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise PermissionError(f"{label}_outside_qualification_root") from exc
    return candidate


def _loopback_url(value, *, label):
    parsed = urlsplit(str(value or ""))
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment or not parsed.port
            or not 1024 <= parsed.port <= 65535):
        raise PermissionError(f"{label}_must_be_loopback")
    return str(value).rstrip("/")


def _live_binding(q, database_path):
    """Validate the independent live-owner gate without guessing defaults."""
    if os.environ.get("POCKETLAB_COORDINATED_LIVE_QUALIFICATION") != "1":
        return None
    if os.environ.get("POCKETLAB_ENVIRONMENT", "").casefold() != "qualification":
        raise PermissionError("coordinated_live_requires_qualification_environment")
    q.assert_safe()
    root = q.root()
    state = _contained(os.environ.get("POCKETLAB_STATE_DIR", ""), root, label="coordinated_state")
    database = _contained(database_path, root, label="coordinated_database")
    pm2_home = _contained(os.environ.get("PM2_HOME", ""), root, label="coordinated_pm2")
    runtime_root = _contained(os.environ.get("POCKETLAB_COORDINATED_RUNTIME_ROOT", ""), root, label="coordinated_runtime")
    caddyfile = _contained(os.environ.get("POCKETLAB_CADDYFILE", ""), root, label="coordinated_caddyfile")
    if not caddyfile.is_file() or caddyfile.is_symlink():
        raise PermissionError("coordinated_caddyfile_unavailable")
    api_url = _loopback_url(os.environ.get("POCKETLAB_COORDINATED_API_URL"), label="coordinated_api")
    proxy_url = _loopback_url(os.environ.get("POCKETLAB_COORDINATED_PROXY_URL"), label="coordinated_proxy")
    opa_url = _loopback_url(os.environ.get("POCKETLAB_OPA_URL"), label="coordinated_opa")
    if urlsplit(opa_url).port == 8181:
        raise PermissionError("coordinated_live_qualification_must_not_use_production_opa_port")
    for path in (state, database, pm2_home, runtime_root):
        if path.is_symlink():
            raise PermissionError("coordinated_live_path_must_not_be_symlink")
    return {"root": root, "state": state, "database": database, "pm2_home": pm2_home,
            "caddyfile": caddyfile,
            "runtime_root": runtime_root, "api_url": api_url, "proxy_url": proxy_url,
            "opa_url": opa_url, "run_id": os.environ["POCKETLAB_QUALIFICATION_RUN_ID"]}


def _copy_regular_tree(source, target):
    source = Path(source)
    target = Path(target)
    if not source.is_dir() or source.is_symlink() or target.exists() or target.is_symlink():
        raise PermissionError("coordinated_runtime_tree_invalid")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copytree(source, target, symlinks=False, copy_function=shutil.copy2)
    for path in target.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise PermissionError("coordinated_runtime_tree_contains_unsafe_entry")


def _materialize_runtime_tree(source, target):
    """Build the install layout consumed by the checked-in runtime owners."""
    source = Path(source)
    target = Path(target)
    target.mkdir(mode=0o700, exist_ok=False)
    _copy_regular_tree(source / "pocket-lab-final-structure/runtime", target / "runtime")
    _copy_regular_tree(source / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts", target / "bootstrap/scripts")
    _copy_regular_tree(source / "security/policies", target / "security/policies")
    _copy_regular_tree(source / "scripts/dev/lite", target / "scripts/dev/lite")
    return target


def _copy_handoff_asset(directory, name, destination, trust, *, limit=None):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    maximum = limit if limit is not None else trust.MAX_ARTIFACT if name == "dist.zip" else trust.MAX_BYTES
    with trust._open_controlled(directory, name, maximum) as (stream, info):
        with destination.open("xb") as handle:
            total = 0
            while chunk := stream.read(1024 * 1024):
                total += len(chunk)
                if total > info.st_size:
                    raise PermissionError("coordinated_handoff_asset_changed")
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if total != info.st_size:
            raise PermissionError("coordinated_handoff_asset_changed")
    destination.chmod(0o600)


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
        assets = root / "candidate-assets"
        _copy_handoff_asset(directory, "dist.zip", assets / "dist.zip", trust)
        _copy_handoff_asset(directory, trust.FILES["release_manifest_sha256"],
            assets / "pocketlab-lite-release.json", trust)
        _copy_handoff_asset(directory, "checksums.txt", assets / "checksums.txt", trust)
        _copy_handoff_asset(directory, package.SOURCE_ASSET, assets / package.SOURCE_ASSET,
            trust, limit=package.MAX_SOURCE_BYTES)
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
            "scope":scope,"migration_contract":contract,"checkpoint_sha256":checkpoint_sha,
            "contract_sha256":native._sha256_bytes(native._canonical(contract)),
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


class LiveQualificationServiceAdapter:
    """Existing runtime owners bound to one disposable qualification root."""

    isolated_qualification = True

    def __init__(self, native, binding, scope, assets, runtime_root,
                 *, previous_pwa_target=None, previous_opa_target=None):
        self.native = native
        self.binding = binding
        self.scope = scope
        self.assets = Path(assets)
        self.runtime_root = Path(runtime_root)
        self.events = []
        pwa = binding["root"] / "pwa_dist"
        active_pwa = pwa / "current"
        active_opa = binding["state"] / "opa" / "active"
        self.previous_pwa_target = previous_pwa_target if previous_pwa_target is not None else self._relative_target(active_pwa, pwa)
        self.previous_opa_target = previous_opa_target if previous_opa_target is not None else self._relative_target(active_opa, binding["state"] / "opa")
        self.env = os.environ.copy()
        self.env.update({
            "POCKETLAB_PROFILE": "lite",
            "POCKETLAB_LITE": "1",
            "POCKETLAB_ENVIRONMENT": "qualification",
            "POCKETLAB_HARNESS_ENABLED": "1",
            "POCKETLAB_HARNESS_DESTRUCTIVE": "0",
            "POCKETLAB_QUALIFICATION_OWNER": "0",
            "POCKETLAB_TEST_AUTH_BYPASS": "0",
            "POCKETLAB_RELEASE_COORDINATED_EXECUTION": "1",
            "POCKETLAB_REPO_ROOT": str(self.runtime_root),
            "POCKET_LAB_BASE_DIR": str(binding["root"]),
            "POCKET_LAB_PWA_DIR": str(pwa),
            "PWA_DIR": str(pwa),
            "POCKETLAB_LITE_PWA_CURRENT_LINK": str(pwa / "current"),
            "POCKETLAB_LITE_PWA_RELEASES_DIR": str(pwa / "releases"),
            "POCKETLAB_STATE_DIR": str(binding["state"]),
            "POCKETLAB_LITE_DB_PATH": str(binding["database"]),
            "POCKETLAB_OPA_ACTIVE_POLICY_DIR": str(binding["state"] / "opa" / "active"),
            "POCKETLAB_OPA_POLICY_SOURCE_DIR": str(self.runtime_root / "security/policies/opa/pocketlab"),
            "POCKETLAB_CADDYFILE": str(binding["caddyfile"]),
            "POCKETLAB_OPA_URL": binding["opa_url"],
            "POCKETLAB_LOCAL_DIST_ZIP": str(self.assets / "dist.zip"),
            "POCKETLAB_LOCAL_RELEASE_MANIFEST": str(self.assets / "pocketlab-lite-release.json"),
            "POCKETLAB_LOCAL_RELEASE_CHECKSUMS": str(self.assets / "checksums.txt"),
            "POCKETLAB_LOCAL_RELEASE_TAG": str(scope["release_tag"]),
            "PM2_HOME": str(binding["pm2_home"]),
        })
        self.env["PWA_DIR"] = str(pwa)

    @staticmethod
    def _relative_target(link, parent):
        try:
            if not Path(link).is_symlink():
                return None
            target = Path(link).resolve(strict=True)
            return target.relative_to(Path(parent).resolve(strict=True)).as_posix()
        except (OSError, ValueError):
            return None

    def _restore_pointer(self, link, parent, relative, label):
        if not isinstance(relative, str) or not relative or relative.startswith("/") or ".." in Path(relative).parts:
            raise self.native.PromotionError("recovery_previous_pointer_invalid", f"The prior {label} pointer is unavailable.")
        parent = Path(parent).resolve(strict=True)
        target = (parent / relative).resolve(strict=True)
        try:
            target.relative_to(parent)
        except ValueError as exc:
            raise self.native.PromotionError("recovery_previous_pointer_invalid", f"The prior {label} pointer escaped the qualification root.") from exc
        if not target.is_dir() or target.is_symlink():
            raise self.native.PromotionError("recovery_previous_pointer_invalid", f"The prior {label} target is unavailable.")
        link = Path(link)
        link.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = link.parent / f".{link.name}.recovery.next"
        temporary.unlink(missing_ok=True)
        temporary.symlink_to(os.path.relpath(target, link.parent))
        os.replace(temporary, link)

    def _run(self, command, *, timeout=120, capture=False):
        try:
            result = subprocess.run(command, cwd=str(self.runtime_root), env=self.env,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
                text=True, timeout=timeout, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise self.native.PromotionError("runtime_owner_unavailable", "The isolated runtime owner could not be invoked.") from exc
        if result.returncode != 0:
            raise self.native.PromotionError("runtime_owner_failed", "The isolated runtime owner rejected the candidate.")
        return result

    def _pm2_json(self):
        result = self._run(["pm2", "jlist"], timeout=15, capture=True)
        try:
            payload = json.loads(result.stdout)
        except (TypeError, ValueError) as exc:
            raise self.native.PromotionError("runtime_identity_unavailable", "The isolated PM2 owner returned invalid identity data.") from exc
        return payload if isinstance(payload, list) else []

    def _snapshot(self):
        services = {}
        for item in self._pm2_json():
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
            services[item["name"]] = {
                "status": str(env.get("status") or "unknown").lower(),
                "pid_present": bool(env.get("pid")),
                "version_present": bool(str(env.get("version") or "")),
            }
        return {"available": True, "services": services, "sanitized": True}

    def snapshot(self):
        return self._snapshot()

    def quiesce(self):
        self.events.append("quiesce")
        for name in ("pocket-api", "pocket-worker", "pocket-node-agent",
                     "pocketlab-core-supervisor", "pocketlab-runtime-reconciler"):
            self._run(["pm2", "stop", name], timeout=30)
        snapshot = self._snapshot()
        if any(snapshot["services"].get(name, {}).get("status") == "online"
               for name in ("pocket-api", "pocket-worker", "pocket-node-agent",
                            "pocketlab-core-supervisor", "pocketlab-runtime-reconciler")):
            raise self.native.PromotionError("writer_quiescence_failed", "An isolated writer remained online.")
        return {"status": "quiesced", "services": snapshot, "sanitized": True}

    def _activate_opa(self):
        script = self.runtime_root / "bootstrap/scripts/lite/prepare-opa-policy.sh"
        staged = self._run(["bash", str(script), "stage"], timeout=90, capture=True)
        expected = str(self.scope["policy_baseline"])
        if f"revision={expected}" not in staged.stdout:
            raise self.native.PromotionError("policy_identity_mismatch", "The staged OPA policy did not match the admitted revision.")
        self._run(["bash", str(script), "activate", expected], timeout=30)

    def activate(self, release_root):
        self.events.append("activate")
        reconcile = self.runtime_root / "bootstrap/scripts/lite/reconcile-runtime.sh"
        if Path(release_root).resolve() == self.runtime_root.resolve():
            install = self.runtime_root / "bootstrap/scripts/install-pwa-ui.sh"
            self._run(["bash", str(install)], timeout=180)
            self._activate_opa()
        else:
            self._restore_pointer(self.binding["root"] / "pwa_dist/current",
                self.binding["root"] / "pwa_dist", self.previous_pwa_target, "PWA")
            self._restore_pointer(self.binding["state"] / "opa/active",
                self.binding["state"] / "opa", self.previous_opa_target, "OPA")
        self._run(["bash", str(reconcile), "--repair", "--reason", "coordinated_live_qualification"], timeout=180)
        return {"status": "activated", "service_owner": "runtime-reconciler",
                "release_root": str(release_root), "sanitized": True}

    def _probe(self, base, path):
        try:
            with urlopen(str(base).rstrip("/") + path, timeout=4) as response:
                payload = json.loads(response.read(128 * 1024).decode("utf-8"))
                return int(response.status), payload if isinstance(payload, dict) else {}
        except (OSError, ValueError, TypeError):
            return 0, {}

    def _pwa_matches(self):
        marker = self.binding["root"] / "pwa_dist/installed-release-identity.json"
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        return (payload.get("source_commit") == self.scope["source_commit"]
                and payload.get("artifact_sha256") == self.scope["frontend_sha256"]
                and payload.get("verified") is True)

    def _opa_matches(self):
        status, payload = self._probe(self.binding["opa_url"], "/v1/data/pocketlab/meta/revision")
        return status == 200 and payload.get("result") == self.scope["policy_baseline"]

    def health(self):
        self.events.append("health")
        observations = []
        runtime_identity = False
        for _ in range(3):
            snapshot = self._snapshot()
            required = ("pocket-api", "pocket-worker", "pocket-node-agent",
                        "pocketlab-core-supervisor", "pocketlab-runtime-reconciler",
                        "pocket-nats", "pocket-opa", "caddy-proxy")
            processes = all(snapshot["services"].get(name, {}).get("status") == "online" for name in required)
            health_status, _ = self._probe(self.binding["api_url"], "/health")
            ready_status, _ = self._probe(self.binding["api_url"], "/ready")
            runtime_status, runtime_payload = self._probe(self.binding["api_url"], "/api/lite/runtime")
            proxy_status, _ = self._probe(self.binding["proxy_url"], "/")
            runtime_identity = (runtime_status == 200
                and (runtime_payload.get("runtime_identity", {}).get("status") == "stable"
                     or runtime_payload.get("runtime_identity_status") == "stable"))
            observations.append(processes and health_status == 200 and ready_status == 200
                and proxy_status == 200 and self._pwa_matches() and self._opa_matches()
                and runtime_identity)
            if not observations[-1]:
                break
            time.sleep(1)
        return {"healthy": len(observations) == 3 and all(observations),
                "consecutive_observations": len(observations),
                "runtime_identity_stable": runtime_identity, "sanitized": True}

    def resume(self):
        self.events.append("resume")
        return {"status": "resumed", "sanitized": True}

    def writes_observed(self, database, checkpoint_sha256):
        return self.native._sha256(database) != checkpoint_sha256


def _live_activate(grant_id, *, authorization, promotion_public_key, recovery_authorization,
                   recovery_public_key, confirm_cutover, binding):
    native,execution,trust,preflight,package,q,database_path,read_connection = _runtime()
    if not confirm_cutover:
        raise PermissionError("explicit_isolated_cutover_required")
    root = _workspace(execution, q, grant_id)
    from cryptography.hazmat.primitives import serialization
    pk = _pin(native, promotion_public_key, "POCKETLAB_RELEASE_PROMOTION_KEY_SHA256")
    rk = _pin(native, recovery_public_key, "POCKETLAB_RELEASE_RECOVERY_KEY_SHA256")
    if pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw) == rk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw):
        raise PermissionError("independent_recovery_key_required")
    with native._FileLock(execution.state_root() / "backend-runtime" / "promotion.lock"):
        with read_connection() as conn:
            row, scope = execution.current(conn, grant_id, states=("prepared",))
        doc = native._read_json(root / "preflight.json", label="coordinated checkpoint")
        directory, handoff = execution.read_handoff(grant_id, row["handoff_sha256"])
        if (doc["scope"] != scope or handoff["scope"] != scope
                or doc["handoff_sha256"] != row["handoff_sha256"]
                or doc["source_tree_sha256"] != _tree_digest(root / "source", native)
                or doc["frontend_tree_sha256"] != _tree_digest(root / "frontend", native)):
            raise PermissionError("coordinated_checkpoint_changed")
        device = "qualification-" + os.environ["POCKETLAB_QUALIFICATION_RUN_ID"]
        expected = {"candidate_sha": scope["source_commit"], "current_production_sha": scope["baseline_commit"],
            "target_device_id": device, "target_schema": scope["target_schema"],
            "artifact_sha256": scope["source_sha256"], "backup_receipt_sha256": doc["checkpoint_sha256"],
            "restore_receipt_sha256": doc["checkpoint_sha256"],
            "preflight_sha256": native._sha256(root / "preflight.json")}
        auth = native.verify_authorization(authorization, expected=expected, public_key=promotion_public_key)
        runtime_root = binding["runtime_root"]
        inputs = native.PromotionInputs(execution.state_root(), database_path(), runtime_root,
            scope["source_commit"], scope["baseline_commit"], device, scope["source_sha256"], {}, {}, {},
            expected["preflight_sha256"], root / "candidate-assets" / package.SOURCE_ASSET)
        runtime_root = _materialize_runtime_tree(root / "source", runtime_root)
        adapter = LiveQualificationServiceAdapter(native, binding, scope, root / "candidate-assets", runtime_root)
        controller = native.PromotionController(inputs, adapter)
        recovery_expected = {"candidate_sha": scope["source_commit"], "current_production_sha": scope["baseline_commit"],
            "target_device_id": device, "checkpoint_sha256": doc["checkpoint_sha256"]}
        recovery_digest = controller._verify_recovery(recovery_authorization, recovery_public_key, recovery_expected)
        if native.reconcile_promotions(execution.state_root())["status"] != "stable":
            raise PermissionError("unresolved_promotion_journal")
        os.environ["POCKETLAB_PROCESS_ROLE"] = "coordinated-promotion-controller"
        controller._journal({"phase": "admitted", "status": "running", "mode": "live_isolated_qualification",
            "grant_id": grant_id, "handoff_sha256": row["handoff_sha256"],
            "authorization_digest": auth["authorization_digest"], "recovery_authorization_digest": recovery_digest,
            "candidate_sha": scope["source_commit"], "current_production_sha": scope["baseline_commit"],
            "previous_pwa_target": adapter.previous_pwa_target,
            "previous_opa_target": adapter.previous_opa_target})
        claimed = False
        finalized = False
        try:
            controller._consume_once("promotion", auth["authorization_digest"])
            execution.claim_cutover(grant_id, row["handoff_sha256"], auth["authorization_digest"])
            claimed = True
            from api_fastapi.db.migrations import discover_migrations
            contract = [{"version": m.version, "name": m.name, "checksum": m.checksum}
                        for m in discover_migrations(root / "source" / package.MIGRATION_PREFIX)]
            if native._sha256_bytes(native._canonical(contract)) != doc["contract_sha256"]:
                raise PermissionError("coordinated_migration_contract_changed")
            quiesce = adapter.quiesce()
            if quiesce.get("status") != "quiesced":
                raise PermissionError("writer_quiescence_failed")
            controller._quiesced_database()
            checkpoint = controller.journal_path.parent / "checkpoint.sqlite3"
            native._copy_sqlite_backup(database_path(), checkpoint)
            if native._sha256(checkpoint) != doc["checkpoint_sha256"]:
                raise PermissionError("live_checkpoint_changed")
            target = root / "generation"
            target.mkdir(mode=0o700, exist_ok=False)
            database = target / "database.sqlite3"
            native._copy_sqlite_backup(checkpoint, database)
            migration = _migrate_copy(database, root / "source", contract, scope, native)
            controller._journal({"phase": "database_staged", "status": "running",
                "database_sha256": migration["sha256"], "checkpoint_sha256": doc["checkpoint_sha256"]})
            with read_connection() as conn:
                current, _ = execution.current(conn, grant_id, states=("cutover_claimed",))
                if current["cutover_authorization_sha256"] != auth["authorization_digest"]:
                    raise PermissionError("cutover_authority_changed")
            controller._journal({"phase": "cutover_started", "status": "running",
                "coordinated_generation": f"backend-{scope['source_commit'][:12]}-{scope['frontend_sha256'][:12]}"})
            generation = {"schema_version": 1, "source_commit": scope["source_commit"],
                "frontend_sha256": scope["frontend_sha256"], "policy_revision": scope["policy_baseline"],
                "schema": scope["target_schema"], "database_sha256": migration["sha256"],
                "handoff_sha256": row["handoff_sha256"], "production_execution": False,
                "runtime_convergence": "pending"}
            native._atomic_json(binding["state"] / "backend-runtime" / "active.json", {
                "kind": "artifact", "source_commit": scope["source_commit"],
                "release_root": str(runtime_root), "artifact_sha256": scope["source_sha256"],
                "generation": generation["coordinated_generation"]})
            os.replace(database, database_path())
            native._fsync_directory(Path(database_path()).parent)
            controller._journal({"phase": "pointer_and_database_promoted", "status": "running",
                "database_sha256": native._sha256(database_path())})
            activated = adapter.activate(runtime_root)
            health = adapter.health()
            if health.get("healthy") is not True or int(health.get("consecutive_observations") or 0) < 3:
                raise native.PromotionError("post_activation_health_failed", "The live isolated runtime did not converge.")
            adapter.resume()
            disposition = execution.finish_cutover(grant_id, auth["authorization_digest"], rehearsed=False, verified=True)
            if disposition != "committed":
                raise PermissionError("cutover_authority_changed_at_completion")
            finalized = True
            generation["runtime_convergence"] = "confirmed"
            controller._journal({"phase": "committed", "status": "committed", "runtime_convergence": "confirmed",
                "production_execution": False, "qualification_execution": True,
                "activation": activated, "health": health})
            return {"status": "committed", "generation": generation, "production_execution": False,
                    "qualification_execution": True, "health": health}
        except Exception:
            controller._journal({"phase": "manual_recovery_required", "status": "blocked",
                "failure_code": "coordinated_live_cutover_failed", "runtime_convergence": "uncertain"})
            if claimed and not finalized:
                try:
                    execution.finish_cutover(grant_id, auth["authorization_digest"], rehearsed=False)
                except Exception:
                    controller._journal({"grant_finalization": "reconciliation_required"})
            raise


def recover_live(*, journal, recovery_authorization, recovery_public_key,
                 candidate_sha, current_sha, device_id, binding, confirm_recovery):
    """Run the separately authorized live recovery owner after restart."""
    native, execution, trust, preflight, package, q, database_path, read_connection = _runtime()
    if not confirm_recovery:
        raise PermissionError("recovery_confirmation_required")
    journal = Path(journal).expanduser().resolve(strict=True)
    expected_root = (execution.state_root() / "backend-runtime" / "promotions").resolve(strict=True)
    try:
        journal.relative_to(expected_root)
    except ValueError as exc:
        raise PermissionError("recovery_journal_scope_invalid") from exc
    payload = native._read_json(journal, label="coordinated live recovery journal")
    grant_id = str(payload.get("grant_id") or "")
    root = _workspace(execution, q, grant_id)
    doc = native._read_json(root / "preflight.json", label="coordinated recovery checkpoint")
    scope = doc.get("scope") if isinstance(doc.get("scope"), dict) else {}
    runtime_root = binding["runtime_root"]
    if not runtime_root.is_dir():
        runtime_root = _materialize_runtime_tree(root / "source", runtime_root)
    assets = root / "candidate-assets"
    adapter = LiveQualificationServiceAdapter(native, binding, scope, assets, runtime_root,
        previous_pwa_target=payload.get("previous_pwa_target"),
        previous_opa_target=payload.get("previous_opa_target"))
    contract = [{"version": item["version"], "name": item["name"], "checksum": item["checksum"]}
        for item in (doc.get("migration_contract") or [])]
    inputs = native.PromotionInputs(execution.state_root(), database_path(), runtime_root,
        str(candidate_sha), str(current_sha), str(device_id), str(scope.get("source_sha256") or "0" * 64),
        {}, {}, {"migration_contract": contract}, "0" * 64,
        assets / package.SOURCE_ASSET)
    controller = native.PromotionController.for_existing_journal(inputs, adapter, journal)
    return controller.recover(recovery_authorization=Path(recovery_authorization),
        recovery_public_key=Path(recovery_public_key), confirm_recovery=True)


def recover_live_from_cli(*, journal, recovery_authorization, recovery_public_key,
                          candidate_sha, current_sha, device_id, confirm_recovery):
    _native, _execution, _trust, _preflight, _package, q, database_path, _read_connection = _runtime()
    binding = _live_binding(q, database_path())
    if binding is None:
        raise PermissionError("coordinated_live_qualification_required")
    return recover_live(journal=journal, recovery_authorization=recovery_authorization,
        recovery_public_key=recovery_public_key, candidate_sha=candidate_sha,
        current_sha=current_sha, device_id=device_id, binding=binding,
        confirm_recovery=confirm_recovery)


def activate(grant_id,*,authorization,promotion_public_key,recovery_authorization,recovery_public_key,confirm_cutover):
    native,execution,trust,preflight,package,q,database_path,read_connection = _runtime()
    if not confirm_cutover or not execution.gate():
        raise PermissionError("explicit_isolated_cutover_required")
    live = _live_binding(q, database_path())
    if live is not None:
        return _live_activate(grant_id, authorization=authorization,
            promotion_public_key=promotion_public_key,
            recovery_authorization=recovery_authorization,
            recovery_public_key=recovery_public_key,
            confirm_cutover=confirm_cutover, binding=live)
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
        claimed = False
        finalized = False
        try:
            controller._consume_once("promotion",auth["authorization_digest"])
            execution.claim_cutover(grant_id,row["handoff_sha256"],auth["authorization_digest"])
            claimed = True
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
            disposition = execution.finish_cutover(grant_id,auth["authorization_digest"],rehearsed=True)
            finalized = True
            if disposition != "rehearsed":
                raise PermissionError("cutover_authority_changed_at_completion")
            controller._journal({"phase":"committed","status":"rehearsed","runtime_convergence":"not_exercised"})
            return {"status":"rehearsed","generation":generation,"production_execution":False}
        except Exception:
            # Never overwrite any running database. Retain the immutable
            # checkpoint and partial generation for explicit reconciliation.
            controller._journal({"phase":"manual_recovery_required","status":"blocked",
                "failure_code":"coordinated_offline_cutover_failed"})
            if claimed and not finalized:
                # Keep the original failure and durable blocked journal even
                # if concurrent authority or database changes prevent recording.
                try:
                    execution.finish_cutover(grant_id,auth["authorization_digest"],rehearsed=False)
                except Exception:
                    controller._journal({"grant_finalization":"reconciliation_required"})
            raise
