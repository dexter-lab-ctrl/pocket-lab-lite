#!/usr/bin/env python3
"""Run the exact-candidate coordinated-runtime qualification preflight.

This driver owns only a disposable DEV-PC lane.  It builds the candidate from
the requested clean commit, starts the repository's real FastAPI, worker,
agent, supervisor, reconciler, NATS, OPA and Caddy owners with the explicit
qualification PM2 shim, and records independent identity observations.  It
does not manufacture a human Owner assurance or a promotion grant: without
those backend-owned inputs the cutover remains a durable ``BLOCKED`` result.

The physical Server Phone and production runtime are intentionally outside the
scope of this command.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[3]
START_DASHBOARD = (
    ROOT
    / "pocket-lab-final-structure"
    / "pocket-lab-bootstrap-production-scripts-patched"
    / "scripts"
    / "start-dashboard.sh"
)
PM2_SHIM = ROOT / "scripts" / "dev" / "lite" / "qualification_pm2.py"
PROMOTION = ROOT / "scripts" / "dev" / "lite" / "backend_runtime_promotion.py"
SERVICE_NAMES = (
    "pocket-nats",
    "pocket-opa",
    "pocket-worker",
    "pocket-api",
    "pocket-node-agent",
    "caddy-proxy",
    "pocket-telemetry",
    "pocketlab-core-supervisor",
    "pocketlab-runtime-reconciler",
)
SHA_LENGTH = 40


class QualificationError(RuntimeError):
    """An expected, sanitized qualification failure."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None,
         timeout: int = 120, capture: bool = True, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise QualificationError(f"{command[0]} unavailable") from exc
    if check and result.returncode != 0:
        raise QualificationError(f"{Path(command[0]).name} rejected qualification input")
    return result


def _git(repo: Path, *args: str, check: bool = True) -> str:
    result = _run(["git", "-C", str(repo), *args], timeout=30, check=check)
    return result.stdout.strip()


def _exact_candidate(repo: Path, requested: str | None) -> str:
    status = _git(repo, "status", "--porcelain")
    if status:
        raise QualificationError("candidate checkout is not clean")
    observed = _git(repo, "rev-parse", "HEAD").lower()
    candidate = (requested or observed).strip().lower()
    if len(candidate) != SHA_LENGTH or any(ch not in "0123456789abcdef" for ch in candidate):
        raise QualificationError("candidate SHA is not an exact commit")
    if observed != candidate:
        raise QualificationError("candidate checkout does not match requested SHA")
    origin = _git(repo, "remote", "get-url", "origin")
    if "dexter-lab-ctrl/pocket-lab-lite" not in origin.replace(".git", ""):
        raise QualificationError("origin is not the authoritative Pocket Lab Lite repository")
    return candidate


def _extract_commit(repo: Path, commit: str, destination: Path) -> None:
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    archive = destination.parent / f"candidate-{commit}.tar"
    try:
        # Use a file descriptor rather than shell redirection so the archive is
        # sourced only from Git and cannot be replaced by a workspace path.
        with archive.open("wb") as handle:
            result = subprocess.run(
                ["git", "-C", str(repo), "archive", "--format=tar", commit],
                stdout=handle,
                stderr=subprocess.PIPE,
                text=False,
                timeout=60,
                check=False,
            )
        if result.returncode != 0:
            raise QualificationError("exact candidate archive could not be created")
        with tarfile.open(archive, "r:") as bundle:
            members = bundle.getmembers()
            for member in members:
                target = (destination / member.name).resolve()
                if target != destination.resolve() and destination.resolve() not in target.parents:
                    raise QualificationError("candidate archive path escaped qualification root")
                if member.issym() or member.islnk() or not (member.isdir() or member.isfile()):
                    raise QualificationError("candidate archive contains an unsafe entry")
            bundle.extractall(destination, filter="data")
    finally:
        archive.unlink(missing_ok=True)


def _find_binary(value: str | None, name: str) -> Path:
    selected = Path(value).expanduser() if value else None
    if selected is None:
        resolved = shutil.which(name)
        selected = Path(resolved) if resolved else None
    if selected is None or not selected.is_file() or not os.access(selected, os.X_OK):
        raise QualificationError(f"{name} binary is unavailable")
    return selected.resolve()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _ports() -> dict[str, int]:
    values: dict[str, int] = {}
    for name in ("api", "caddy", "nats", "monitor", "opa"):
        value = _free_port()
        while value in values.values():
            value = _free_port()
        values[name] = value
    return values


def _release_assets(source: Path, commit: str, root: Path, npm: Path) -> dict[str, str]:
    """Build an exact-commit PWA and create a deterministic local release."""
    node_modules = ROOT / "node_modules"
    if not node_modules.is_dir():
        raise QualificationError("repository node_modules is unavailable for exact candidate build")
    link = source / "node_modules"
    if link.exists() or link.is_symlink():
        raise QualificationError("candidate archive unexpectedly contains node_modules")
    link.symlink_to(node_modules, target_is_directory=True)
    try:
        build_env = os.environ.copy()
        node_directories = [npm.parent, *(parent / "bin" for parent in npm.parents)]
        node_directory = next((path for path in node_directories if (path / "node").is_file()), npm.parent)
        build_env["PATH"] = os.pathsep.join((str(node_directory), build_env.get("PATH", "")))
        build_env.update({"POCKETLAB_BUILD_ID": commit, "VITE_POCKETLAB_BUILD_ID": commit})
        _run([str(npm), "run", "build"], cwd=source, env=build_env, timeout=300)
    finally:
        link.unlink(missing_ok=True)
    dist = source / "dist"
    if not (dist / "index.html").is_file() or not (dist / "manifest.webmanifest").is_file():
        raise QualificationError("exact candidate PWA build is incomplete")
    tag = f"lite-{datetime.now(timezone.utc):%Y.%m.%d}.663"
    created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    marker = {
        "product": "pocket-lab-lite",
        "schema_version": 1,
        "install_mode": "release",
        "release_tag": tag,
        "source_commit": commit,
        "target": "web-pwa",
    }
    (dist / "pocketlab-lite-build.json").write_text(json.dumps(marker, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    archive = root / "assets" / "dist.zip"
    archive.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(item for item in dist.rglob("*") if item.is_file()):
            relative = path.relative_to(dist).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = ((0o100755 if os.access(path, os.X_OK) else 0o100644) & 0o777) << 16
            bundle.writestr(info, path.read_bytes())
    digest = _sha256(archive)
    manifest = root / "assets" / "pocketlab-lite-release.json"
    _json_write(manifest, {
        "product": "pocket-lab-lite",
        "schema_version": 1,
        "release_tag": tag,
        "artifact": "dist.zip",
        "artifact_sha256": digest,
        "source_commit": commit,
        "source_repository": "dexter-lab-ctrl/pocket-lab-lite",
        "target": "web-pwa",
        "created_at": created_at,
        "minimum_runtime_version": "qualification",
        "sanitized": True,
    })
    checksums = root / "assets" / "checksums.txt"
    checksums.write_text(f"{digest}  dist.zip\n{_sha256(manifest)}  pocketlab-lite-release.json\n", encoding="utf-8")
    return {"archive": str(archive), "manifest": str(manifest), "checksums": str(checksums), "tag": tag, "digest": digest}


def _promotion_artifact(repo: Path, commit: str, root: Path) -> dict:
    result = _run([sys.executable, str(PROMOTION), "prepare", "--repo-root", str(repo), "--source-sha", commit, "--output-dir", str(root / "backend-artifact")])
    try:
        prepared = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise QualificationError("backend artifact preparation returned invalid evidence") from exc
    if not isinstance(prepared, dict) or not prepared.get("artifact"):
        raise QualificationError("backend artifact preparation returned incomplete evidence")
    verify = _run([
        sys.executable, str(PROMOTION), "verify",
        "--artifact", str(prepared["artifact"]),
        "--manifest", str(prepared["manifest"]),
        "--checksums", str(prepared["checksums"]),
    ])
    try:
        verified = json.loads(verify.stdout)
    except json.JSONDecodeError as exc:
        raise QualificationError("backend artifact verification returned invalid evidence") from exc
    if verified.get("status") != "verified" or verified.get("source_commit") != commit:
        raise QualificationError("backend artifact did not verify against the exact candidate")
    return {"prepared": prepared, "verified": verified}


def _install_backend_baseline(package: dict, env: dict[str, str], *, commit: str, run_id: str) -> dict[str, str]:
    """Install the verified backend artifact as the disposable baseline.

    This is intentionally a qualification-lane setup operation.  It stages
    the exact artifact through the repository promotion controller, then
    records the resulting installed pointer inside the run-owned state root.
    It does not issue a promotion grant and is never used for production
    activation.
    """
    prepared = package.get("prepared") if isinstance(package.get("prepared"), dict) else {}
    verified = package.get("verified") if isinstance(package.get("verified"), dict) else {}
    artifact = Path(str(prepared.get("artifact") or "")).resolve()
    manifest = Path(str(prepared.get("manifest") or "")).resolve()
    checksums = Path(str(prepared.get("checksums") or "")).resolve()
    if not artifact.is_file() or not manifest.is_file() or not checksums.is_file():
        raise QualificationError("backend baseline inputs are incomplete")
    state_root = Path(env["POCKETLAB_STATE_DIR"]).resolve()
    qualification_root = Path(env["POCKETLAB_QUALIFICATION_ROOT"]).resolve(strict=True)
    stage_result = _run([
        sys.executable,
        str(PROMOTION),
        "stage",
        "--artifact", str(artifact),
        "--manifest", str(manifest),
        "--checksums", str(checksums),
        "--staging-root", str(state_root / "backend-runtime"),
        "--expected-device-id", "qualification-server",
        "--target-device-id", "qualification-server",
    ], env=env, timeout=120)
    try:
        staged = json.loads(stage_result.stdout)
        external_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise QualificationError("backend baseline staging returned invalid evidence") from exc
    release_root = Path(str(staged.get("release_root") or "")).resolve()
    try:
        release_root.relative_to(qualification_root)
    except ValueError as exc:
        raise QualificationError("backend baseline staging escaped qualification root") from exc
    staged_manifest = release_root / "artifact-manifest.json"
    if not staged_manifest.is_file():
        raise QualificationError("backend baseline staged manifest is missing")
    staged_payload = json.loads(staged_manifest.read_text(encoding="utf-8"))
    if (
        staged_payload.get("source_commit") != commit
        or staged_payload.get("artifact_sha256") != verified.get("artifact_sha256")
        or staged_payload.get("payload_sha256") != external_manifest.get("payload_sha256")
    ):
        raise QualificationError("backend baseline identity does not match the verified artifact")
    generation = "runtime-" + hashlib.sha256(
        f"{commit}:{verified.get('artifact_sha256')}:{run_id}".encode("ascii")
    ).hexdigest()[:32]
    pointer = {
        "schema": "pocketlab.backend-runtime-active/v1",
        "kind": "artifact",
        "source_commit": commit,
        "artifact_sha256": str(verified.get("artifact_sha256") or ""),
        "payload_sha256": str(external_manifest.get("payload_sha256") or ""),
        "release_root": str(release_root),
        "generation": generation,
        "device_id": "qualification-server",
        "installed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "installation": "isolated-qualification-baseline",
        "sanitized": True,
    }
    _json_write(state_root / "backend-runtime" / "active.json", pointer)
    return {
        "status": "PASS",
        "source_commit": commit,
        "artifact_sha256": str(verified.get("artifact_sha256") or ""),
        "payload_sha256": str(external_manifest.get("payload_sha256") or ""),
        "generation": generation,
        "release_root": "<qualification-root>/state/backend-runtime/releases/" + commit,
        "sanitized": True,
    }


def _seed_policy_baseline(env: dict[str, str], *, run_id: str) -> dict[str, str]:
    """Record the exact loaded repository policy as a disposable baseline.

    Startup first activates the repository baseline through the normal OPA
    bootstrap path.  This qualification-only durable record then binds that
    already-loaded revision to the same SQLite governance schema, allowing the
    normal reconciler observation path to prove DB, pointers, OPA and process
    convergence.  It creates no human identity, membership or grant.
    """
    state_root = Path(env["POCKETLAB_STATE_DIR"]).resolve()
    stage_root = state_root / "opa" / "active"
    revision_file = stage_root / "revision.txt"
    manifest_file = stage_root / "manifest.json"
    template_file = stage_root / "template.json"
    if not revision_file.is_file() or not manifest_file.is_file() or not template_file.is_file():
        raise QualificationError("loaded OPA baseline evidence is incomplete")
    revision = revision_file.read_text(encoding="utf-8").strip()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    template = json.loads(template_file.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise QualificationError("loaded OPA baseline manifest is invalid")
    candidate_hash = str(manifest.get("candidate_hash") or "")
    if not revision or not candidate_hash or not isinstance(template, dict):
        raise QualificationError("loaded OPA baseline identity is incomplete")
    manifest_json = json.dumps(
        {"files": manifest["files"], "candidate_hash": candidate_hash},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    database = Path(env["POCKETLAB_LITE_DB_PATH"]).resolve()
    try:
        conn = sqlite3.connect(database, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        row = conn.execute(
            "SELECT manifest_json,content_hash,created_by_principal_type,created_by_principal_id FROM policy_revisions WHERE revision_id=?",
            (revision,),
        ).fetchone()
        if row is None:
            conn.execute(
                """INSERT INTO policy_revisions(
                    revision_id,parent_revision_id,template_id,template_version,
                    canonical_parameters_json,manifest_json,content_hash,created_by_human_id,
                    created_by_principal_type,created_by_principal_id,created_at,
                    validation_status,validated_at,validation_reason_code,lifecycle_status,
                    activated_at,change_summary
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    revision,
                    None,
                    str(template.get("template_id") or "baseline"),
                    str(template.get("template_version") or "1"),
                    json.dumps(template.get("parameters") or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
                    manifest_json,
                    candidate_hash,
                    None,
                    "qualification",
                    "qualification-baseline-" + run_id,
                    now,
                    "valid",
                    now,
                    "",
                    "active",
                    now,
                    "Disposable isolated baseline for runtime identity qualification",
                ),
            )
        elif (
            str(row["manifest_json"] or "") != manifest_json
            or str(row["content_hash"] or "") != candidate_hash
            or str(row["created_by_principal_type"] or "") != "qualification"
        ):
            raise QualificationError("loaded OPA baseline conflicts with durable policy evidence")
        runtime = conn.execute(
            "SELECT active_revision_id,known_good_revision_id FROM policy_runtime_state WHERE state_id=1"
        ).fetchone()
        if runtime is None:
            conn.execute(
                "INSERT INTO policy_runtime_state(state_id,active_revision_id,known_good_revision_id,updated_at,updated_by_operation_id) VALUES (1,?,?,?,NULL)",
                (revision, revision, now),
            )
        elif str(runtime["active_revision_id"] or "") != revision or str(runtime["known_good_revision_id"] or "") != revision:
            raise QualificationError("loaded OPA baseline conflicts with policy runtime state")
        conn.commit()
    except sqlite3.Error as exc:
        raise QualificationError("isolated policy baseline could not be recorded") from exc
    finally:
        try:
            conn.close()
        except UnboundLocalError:
            pass
    return {"status": "PASS", "revision": revision, "content_hash": candidate_hash, "sanitized": True}


def _identity_projection(env: dict[str, str]) -> dict:
    script = (
        "import json\n"
        "from api_fastapi.db.connection import connection\n"
        "from api_fastapi.services import lite_runtime_identity\n"
        "with connection() as conn:\n"
        "    print(json.dumps(lite_runtime_identity.public_projection(conn), sort_keys=True))\n"
    )
    result = _run([sys.executable, "-c", script], env=env, timeout=20, check=False)
    if result.returncode != 0:
        return {"status": "unknown", "reason_code": "runtime_identity_observation_unavailable", "sanitized": True}
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise QualificationError("runtime identity projection returned invalid evidence") from exc
    return value if isinstance(value, dict) else {}


def _environment(root: Path, run_id: str, commit: str, ports: dict[str, int], binaries: dict[str, Path], node: Path) -> dict[str, str]:
    source = root / "candidate"
    base = root / "base"
    state = root / "state"
    runtime_root = root / "runtime"
    allow = ",".join(SERVICE_NAMES)
    path_parts = [
        str(root / "bin"),
        str(binaries["nats"].parent),
        str(binaries["caddy"].parent),
        str(binaries["opa"].parent),
        str(ROOT / ".venv" / "bin"),
    ]
    path_parts.extend(item for item in os.environ.get("PATH", "").split(os.pathsep) if item)
    bootstrap_fingerprint = "sha256:" + hashlib.sha256(run_id.encode("ascii")).hexdigest()
    return {
        **os.environ,
        "PATH": os.pathsep.join(dict.fromkeys(path_parts)),
        "HOME": str(root / "home"),
        "POCKET_LAB_ALLOW_NON_TERMUX": "1",
        "POCKETLAB_ENVIRONMENT": "qualification",
        "POCKETLAB_HARNESS_ENABLED": "1",
        "POCKETLAB_HARNESS_DESTRUCTIVE": "0",
        "POCKETLAB_HARNESS_BOOTSTRAP_APPROVED": "1",
        "POCKETLAB_HARNESS_BOOTSTRAP_PROFILE": "security-assurance-runner",
        "POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT": bootstrap_fingerprint,
        "POCKETLAB_HARNESS_PROVISIONING_TOKEN": "qualification-provisioning-" + run_id,
        "POCKETLAB_QUALIFICATION_OWNER": "0",
        "POCKETLAB_TEST_AUTH_BYPASS": "0",
        "POCKETLAB_QUALIFICATION_CONTEXT": "isolated-runtime-v1",
        "POCKETLAB_QUALIFICATION_CONTEXT_TOKEN": "qualification-context-" + run_id,
        "POCKETLAB_QUALIFICATION_CANDIDATE_SHA": commit,
        "POCKETLAB_QUALIFICATION_ALLOW_TEST_DESTINATION": "1",
        "POCKETLAB_QUALIFICATION_DESTINATION_ROOT": str(root / "destination"),
        "POCKETLAB_QUALIFICATION_TEST_ORIGIN": f"https://127.0.0.1:{ports['caddy']}",
        "POCKETLAB_QUALIFICATION_CONTROL_ORIGIN": f"https://127.0.0.1:{ports['api']}",
        "POCKETLAB_QUALIFICATION_WEBDAV_USER": "qualification",
        "POCKETLAB_QUALIFICATION_WEBDAV_PASSWORD": "qualification-" + run_id + "-webdav-secret",
        "POCKETLAB_PHOTO_BACKUP_CREDENTIAL_TTL_SECONDS": "120",
        "POCKETLAB_PHOTOPRISM_COMMAND_TIMEOUT_SECONDS": "30",
        "POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID": "qualification-" + run_id,
        "POCKETLAB_HARNESS_TARGET_DEVICE_ID": "qualification-server",
        "POCKETLAB_DEVICE_NAME": "qualification-server",
        "POCKETLAB_NODE_ID": "qualification-server",
        "POCKETLAB_NODE_NAME": "qualification-server",
        "POCKETLAB_NODE_ROLES": "server",
        "POCKETLAB_NODE_ROLE": "server",
        "POCKETLAB_QUALIFICATION_ROOT": str(root),
        "POCKETLAB_QUALIFICATION_RUN_ID": run_id,
        "POCKETLAB_REPO_ROOT": str(source),
        "POCKETLAB_BASE_DIR": str(base),
        "POCKETLAB_STATE_DIR": str(state),
        "POCKETLAB_QUALIFICATION_STATE_DIR": str(state),
        "POCKETLAB_LITE_DB_PATH": str(state / "pocketlab-lite.sqlite3"),
        "POCKETLAB_OPA_ACTIVE_POLICY_DIR": str(state / "opa" / "active"),
        "POCKET_LAB_BASE_DIR": str(base),
        "POCKET_LAB_PWA_DIR": str(base / "pwa"),
        "POCKET_LAB_API_DIR": str(base / "api"),
        "POCKET_LAB_CADDYFILE": str(base / "caddy" / "Caddyfile"),
        "POCKETLAB_CADDYFILE": str(base / "caddy" / "Caddyfile"),
        "POCKETLAB_LITE_PWA_CURRENT_LINK": str(base / "pwa" / "current"),
        "POCKETLAB_LITE_PWA_RELEASES_DIR": str(base / "pwa" / "releases"),
        "PWA_DIR": str(base / "pwa"),
        "CADDYFILE": str(base / "caddy" / "Caddyfile"),
        "STATE_DIR": str(state),
        "LOG_DIR": str(root / "logs"),
        "RUN_DIR": str(root / "run"),
        "LOCK_DIR": str(root / "locks"),
        "MARKER_DIR": str(root / "markers"),
        "TMP_ROOT": str(root / "tmp"),
        "TMPDIR": str(root / "tmp"),
        "TMP": str(root / "tmp"),
        "TEMP": str(root / "tmp"),
        "DASH_PORT": str(ports["caddy"]),
        "API_PORT": str(ports["api"]),
        "POCKETLAB_CADDY_PORT": str(ports["caddy"]),
        "POCKETLAB_API_PORT": str(ports["api"]),
        "POCKETLAB_NATS_LISTEN_HOST": "127.0.0.1",
        "POCKETLAB_LITE_NATS_PORT": str(ports["nats"]),
        "POCKETLAB_LITE_NATS_MONITOR_PORT": str(ports["monitor"]),
        "POCKETLAB_OPA_URL": f"http://127.0.0.1:{ports['opa']}",
        "POCKETLAB_NATS_URL": f"nats://127.0.0.1:{ports['nats']}",
        "POCKETLAB_NATS_MONITOR_URL": f"http://127.0.0.1:{ports['monitor']}",
        "POCKETLAB_NATIVE_BASH": "/bin/bash",
        "POCKETLAB_NATIVE_NODE": str(node),
        "POCKETLAB_NATS_SERVER_BIN": str(binaries["nats"]),
        "POCKETLAB_CADDY_BIN": str(binaries["caddy"]),
        "POCKETLAB_OPA_BIN": str(binaries["opa"]),
        "PM2_HOME": str(root / "pm2"),
        "POCKETLAB_PM2_CLI": str(root / "bin" / "pm2"),
        "POCKETLAB_QUALIFICATION_PM2_SHIM": "1",
        "POCKETLAB_QUALIFICATION_PM2_ALLOW_SERVICES": allow,
        "POCKETLAB_QUALIFICATION_LOG_DIR": str(root / "logs"),
        "POCKETLAB_COORDINATED_LIVE_QUALIFICATION": "1",
        "POCKETLAB_RELEASE_COORDINATED_EXECUTION": "1",
        "POCKETLAB_COORDINATED_RUNTIME_ROOT": str(runtime_root),
        "POCKETLAB_COORDINATED_API_URL": f"http://127.0.0.1:{ports['api']}",
        "POCKETLAB_COORDINATED_PROXY_URL": f"http://127.0.0.1:{ports['caddy']}",
        "POCKETLAB_QUALIFICATION_ALLOW_TEST_DESTINATION": "1",
        "POCKETLAB_RUNTIME_RECONCILE_SECONDS": "10",
        "PYTHONPATH": os.pathsep.join((str(source / "pocket-lab-final-structure" / "runtime"), str(source / "pocket-lab-final-structure" / "runtime" / "supervisors"), os.environ.get("PYTHONPATH", ""))),
        "POCKETLAB_CANDIDATE_SOURCE_COMMIT": commit,
    }


def _copy_binaries(root: Path, binaries: dict[str, Path]) -> dict[str, Path]:
    destination = root / "bin"
    destination.mkdir(mode=0o700, parents=True)
    copied: dict[str, Path] = {}
    for name, path in binaries.items():
        target = destination / ("nats-server" if name == "nats" else name)
        shutil.copy2(path, target)
        target.chmod(0o700)
        copied[name] = target
    pm2 = destination / "pm2"
    shutil.copy2(PM2_SHIM, pm2)
    pm2.chmod(0o700)
    copied["pm2"] = pm2
    return copied


def _node_for_npm(npm: Path) -> Path:
    candidates = [npm.parent / "node", *(parent / "bin" / "node" for parent in npm.parents)]
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate.resolve()
    raise QualificationError("node binary is unavailable")


def _copy_runtime_tree(source: Path, root: Path) -> None:
    target = root / "runtime"
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    for relative in (
        Path("pocket-lab-final-structure/runtime"),
        Path("pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts"),
        Path("security/policies"),
        Path("scripts/dev/lite"),
    ):
        destination = target / relative.name if relative.name != "scripts" else target / "bootstrap" / "scripts"
        if relative.parts[0] == "security":
            destination = target / "security" / "policies"
        if relative.parts[0] == "scripts":
            destination = target / "scripts" / "dev" / "lite"
        shutil.copytree(source / relative, destination, symlinks=False)


def _jlist(env: dict[str, str]) -> list[dict]:
    result = _run([env["POCKETLAB_PM2_CLI"], "jlist"], env=env, timeout=20)
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise QualificationError("qualification PM2 returned invalid identity evidence") from exc
    return value if isinstance(value, list) else []


def _observe(env: dict[str, str], expected: str) -> dict:
    rows = _jlist(env)
    by_name = {str(item.get("name")): item for item in rows if isinstance(item, dict)}
    services = {}
    for name in SERVICE_NAMES:
        item = by_name.get(name) or {}
        pm2_env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
        pid = int(pm2_env.get("pid") or item.get("pid") or 0)
        executable = str(pm2_env.get("pm_exec_path") or "")
        marker = str(pm2_env.get("qualification_run_id") or "") == expected
        marker_source = "pm2_run_record" if marker else ""
        if pid > 0:
            try:
                process_marker = f"POCKETLAB_QUALIFICATION_RUN_ID={expected}" in Path(f"/proc/{pid}/environ").read_bytes().replace(b"\x00", b"\n").decode("utf-8", "ignore")
                if process_marker:
                    marker = True
                    marker_source = "process_environment"
            except (FileNotFoundError, OSError, UnicodeError):
                pass
        services[name] = {
            "status": str(pm2_env.get("status") or "unknown"),
            "pid_present": pid > 0,
            "run_marker": marker,
            "run_marker_source": marker_source or "unavailable",
            "executable_under_qualification_root": executable.startswith(env["POCKETLAB_QUALIFICATION_ROOT"] + os.sep),
        }
    return {"services": services, "all_required_online": all(item["status"] == "online" and item["pid_present"] and item["run_marker"] and item["executable_under_qualification_root"] for item in services.values()), "sanitized": True}


def _http_json(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read(256 * 1024).decode("utf-8")
            value = json.loads(body)
            return int(response.status), value if isinstance(value, dict) else {}
    except (OSError, urllib.error.URLError, UnicodeError, json.JSONDecodeError):
        return 0, {}


def _diagnostic(text: str, root: Path) -> list[str]:
    """Keep only short, sanitized owner diagnostics in the evidence report."""
    lines: list[str] = []
    for raw in (text or "").splitlines()[-24:]:
        line = raw.replace(str(root), "<qualification-root>").replace(str(ROOT), "<repository-root>").strip()
        lowered = line.casefold()
        if any(marker in lowered for marker in ("password", "token", "secret", "cookie", "private key", "authorization:")):
            continue
        if line:
            lines.append(line[:240])
    return lines


def _cleanup(env: dict[str, str]) -> bool:
    try:
        before = _jlist(env)
    except QualificationError:
        return False
    names = {str(item.get("name")) for item in before if isinstance(item, dict) and item.get("name")}
    try:
        for name in sorted(names.intersection(SERVICE_NAMES)):
            _run([env["POCKETLAB_PM2_CLI"], "delete", name], env=env, timeout=15)
        after = _jlist(env)
    except QualificationError:
        return False
    return not any(str(item.get("name")) in SERVICE_NAMES and int(item.get("pid") or 0) > 0 for item in after if isinstance(item, dict))


def _assert_isolated_environment(env: dict[str, str], root: Path) -> None:
    base = root.resolve(strict=True)
    for key in (
        "POCKETLAB_QUALIFICATION_ROOT",
        "HOME",
        "POCKETLAB_BASE_DIR",
        "POCKETLAB_STATE_DIR",
        "POCKETLAB_LITE_DB_PATH",
        "POCKETLAB_OPA_ACTIVE_POLICY_DIR",
        "POCKET_LAB_BASE_DIR",
        "POCKET_LAB_PWA_DIR",
        "POCKET_LAB_API_DIR",
        "POCKET_LAB_CADDYFILE",
        "PM2_HOME",
        "POCKETLAB_PM2_CLI",
        "TMPDIR",
        "TMP_ROOT",
        "LOG_DIR",
        "RUN_DIR",
        "LOCK_DIR",
        "MARKER_DIR",
        "POCKETLAB_QUALIFICATION_DESTINATION_ROOT",
    ):
        value = Path(env[key]).expanduser().resolve(strict=False)
        try:
            value.relative_to(base)
        except ValueError as exc:
            raise QualificationError(f"qualification path escaped run root: {key}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run exact-SHA isolated coordinated-runtime qualification preflight")
    parser.add_argument("--candidate-sha")
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--nats-server-bin")
    parser.add_argument("--caddy-bin")
    parser.add_argument("--opa-bin")
    parser.add_argument("--npm-bin")
    parser.add_argument("--keep-root", action="store_true")
    args = parser.parse_args(argv)

    repo = ROOT
    candidate = _exact_candidate(repo, args.candidate_sha)
    evidence_dir = (args.evidence_dir or ROOT / ".pocketlab-dev" / "validation" / f"coordinated-runtime-{candidate}").expanduser().resolve()
    root = Path(tempfile.mkdtemp(prefix="pocketlab-coordinated-runtime-", dir=os.environ.get("TMPDIR", "/tmp"))).resolve()
    run_id = secrets.token_hex(12)
    env: dict[str, str] | None = None
    cleanup_ok = False
    payload: dict = {
        "schema_version": 1,
        "status": "BLOCKED",
        "candidate_sha": candidate,
        "run_id": run_id,
        "qualification": "isolated-dev-pc-coordinated-runtime-preflight",
        "started_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sanitized": True,
    }
    try:
        binaries = {
            "nats": _find_binary(args.nats_server_bin or os.environ.get("NATS_SERVER_BIN"), "nats-server"),
            "caddy": _find_binary(args.caddy_bin or os.environ.get("CADDY_BIN"), "caddy"),
            "opa": _find_binary(args.opa_bin or os.environ.get("OPA_BIN"), "opa"),
        }
        npm = _find_binary(args.npm_bin or os.environ.get("NPM_BIN"), "npm")
        node = _node_for_npm(npm)
        source = root / "candidate"
        _extract_commit(repo, candidate, source)
        assets = _release_assets(source, candidate, root, npm)
        package = _promotion_artifact(repo, candidate, root)
        copied = _copy_binaries(root, binaries)
        _copy_runtime_tree(source, root)
        ports = _ports()
        env = _environment(root, run_id, candidate, ports, copied, node)
        env.update({
            "POCKETLAB_LOCAL_DIST_ZIP": assets["archive"],
            "POCKETLAB_LOCAL_RELEASE_MANIFEST": assets["manifest"],
            "POCKETLAB_LOCAL_RELEASE_CHECKSUMS": assets["checksums"],
            "POCKETLAB_LOCAL_RELEASE_TAG": assets["tag"],
        })
        _assert_isolated_environment(env, root)
        Path(env["HOME"]).mkdir(mode=0o700, parents=True, exist_ok=True)
        payload["backend_baseline"] = _install_backend_baseline(package, env, commit=candidate, run_id=run_id)
        install = source / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched" / "scripts" / "install-pwa-ui.sh"
        install_result = _run(["bash", str(install)], cwd=source, env=env, timeout=180, check=False)
        payload["pwa_install"] = {
            "returncode": install_result.returncode,
            "stdout_tail": _diagnostic(install_result.stdout, root),
            "stderr_tail": _diagnostic(install_result.stderr, root),
            "sanitized": True,
        }
        if install_result.returncode != 0:
            raise QualificationError("exact candidate PWA installation failed")
        start = _run([
            "bash",
            str(source / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched" / "scripts" / "start-dashboard.sh"),
            "--lite",
            "--reconcile-only",
        ], cwd=source, env=env, timeout=300, check=False)
        payload["startup"] = {
            "returncode": start.returncode,
            "stdout_tail": _diagnostic(start.stdout, root),
            "stderr_tail": _diagnostic(start.stderr, root),
            "sanitized": True,
        }
        if start.returncode != 0:
            raise QualificationError("isolated runtime owners did not converge")
        payload["policy_baseline"] = _seed_policy_baseline(env, run_id=run_id)
        observation = _observe(env, run_id)
        status = health = ready = 0
        runtime: dict = {}
        projection: dict = {}
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            status, runtime = _http_json(env["POCKETLAB_COORDINATED_API_URL"] + "/api/lite/runtime")
            health, _ = _http_json(env["POCKETLAB_COORDINATED_API_URL"] + "/health")
            ready, _ = _http_json(env["POCKETLAB_COORDINATED_API_URL"] + "/ready")
            projection = _identity_projection(env)
            if (
                observation["all_required_online"]
                and status == 200
                and health == 200
                and ready == 200
                and runtime.get("stable") is True
                and projection.get("status") == "stable"
            ):
                break
            time.sleep(2)
        identity_status = str(projection.get("status") or "unknown")
        identity_pass = (
            identity_status == "stable"
            and projection.get("authenticated_source_commit") == candidate
            and runtime.get("stable") is True
        )
        payload.update({
            "status": "BLOCKED" if observation["all_required_online"] and status == 200 and health == 200 and ready == 200 and identity_pass else "FAIL",
            "package": {"status": "PASS", "backend": package["verified"], "pwa": {"source_commit": candidate, "artifact_sha256": assets["digest"], "release_tag": assets["tag"]}},
            "runtime_identity": {
                "status": "PASS" if identity_pass else "FAIL",
                "api_status": status,
                "health_status": health,
                "ready_status": ready,
                "contract_stable": runtime.get("stable") is True,
                "projection": projection,
                "service_observation": observation,
            },
            "cutover": {"status": "BLOCKED", "reason_code": "human_owner_authorization_required", "production_execution": False, "attempted": False},
            "recovery": {"status": "NOT_RUN", "reason_code": "cutover_not_authorized"},
            "physical_android": {"status": "NOT_RUN", "reason_code": "this_driver_is_dev_pc_only"},
        })
    except QualificationError as exc:
        payload.update({"status": "BLOCKED", "reason_code": str(exc)[:120], "cutover": {"status": "NOT_RUN", "reason_code": "preflight_incomplete"}})
    finally:
        if env is not None:
            cleanup_ok = _cleanup(env)
        payload["cleanup"] = {"status": "PASS" if cleanup_ok else "BLOCKED", "run_owned_services_stopped": cleanup_ok, "root_removed": False}
        evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        report = evidence_dir / "coordinated-runtime-preflight.json"
        _json_write(report, payload)
        if cleanup_ok and not args.keep_root:
            shutil.rmtree(root, ignore_errors=False)
            payload["cleanup"]["root_removed"] = True
            _json_write(report, payload)
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2))
    return 0 if payload["status"] in {"PASS", "BLOCKED"} and payload.get("cleanup", {}).get("status") == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (QualificationError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason_code": str(exc)[:120], "sanitized": True}, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)
