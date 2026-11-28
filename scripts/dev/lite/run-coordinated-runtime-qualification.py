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
        build_env["PATH"] = os.pathsep.join((str(npm.parent), build_env.get("PATH", "")))
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


def _environment(root: Path, run_id: str, commit: str, ports: dict[str, int], binaries: dict[str, Path]) -> dict[str, str]:
    source = root / "candidate"
    base = root / "base"
    state = root / "state"
    runtime_root = root / "runtime"
    allow = ",".join(SERVICE_NAMES)
    node = os.environ.get("POCKETLAB_NATIVE_NODE") or shutil.which("node") or ""
    if not node:
        raise QualificationError("node binary is unavailable")
    path_parts = [str(root / "bin"), str(binaries["nats"].parent), str(binaries["caddy"].parent), str(binaries["opa"].parent)]
    path_parts.extend(item for item in os.environ.get("PATH", "").split(os.pathsep) if item)
    return {
        **os.environ,
        "PATH": os.pathsep.join(dict.fromkeys(path_parts)),
        "HOME": str(root / "home"),
        "POCKET_LAB_ALLOW_NON_TERMUX": "1",
        "POCKETLAB_ENVIRONMENT": "qualification",
        "POCKETLAB_HARNESS_ENABLED": "1",
        "POCKETLAB_HARNESS_DESTRUCTIVE": "0",
        "POCKETLAB_QUALIFICATION_OWNER": "0",
        "POCKETLAB_TEST_AUTH_BYPASS": "0",
        "POCKETLAB_QUALIFICATION_CONTEXT": "isolated-runtime-v1",
        "POCKETLAB_QUALIFICATION_CONTEXT_TOKEN": "qualification-context-" + run_id,
        "POCKETLAB_QUALIFICATION_ROOT": str(root),
        "POCKETLAB_QUALIFICATION_RUN_ID": run_id,
        "POCKETLAB_REPO_ROOT": str(source),
        "POCKET_LAB_BASE_DIR": str(base),
        "POCKET_LAB_PWA_DIR": str(base / "pwa"),
        "POCKET_LAB_API_DIR": str(base / "api"),
        "POCKET_LAB_CADDYFILE": str(base / "caddy" / "Caddyfile"),
        "POCKETLAB_CADDYFILE": str(base / "caddy" / "Caddyfile"),
        "PWA_DIR": str(base / "pwa"),
        "CADDYFILE": str(base / "caddy" / "Caddyfile"),
        "DASH_PORT": str(ports["caddy"]),
        "API_PORT": str(ports["api"]),
        "POCKETLAB_CADDY_PORT": str(ports["caddy"]),
        "POCKETLAB_API_PORT": str(ports["api"]),
        "POCKETLAB_NATS_LISTEN_HOST": "127.0.0.1",
        "POCKETLAB_LITE_NATS_PORT": str(ports["nats"]),
        "POCKETLAB_LITE_NATS_MONITOR_PORT": str(ports["monitor"]),
        "POCKETLAB_OPA_URL": f"http://127.0.0.1:{ports['opa']}",
        "POCKETLAB_NATIVE_BASH": "/bin/bash",
        "POCKETLAB_NATIVE_NODE": node,
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
        "PYTHONPATH": os.pathsep.join((str(source / "pocket-lab-final-structure" / "runtime"), str(source / "pocket-lab-final-structure" / "runtime" / "supervisors"), os.environ.get("PYTHONPATH", ""))),
        "POCKETLAB_CANDIDATE_SOURCE_COMMIT": commit,
    }


def _copy_binaries(root: Path, binaries: dict[str, Path]) -> dict[str, Path]:
    destination = root / "bin"
    destination.mkdir(mode=0o700, parents=True)
    copied: dict[str, Path] = {}
    for name, path in binaries.items():
        target = destination / name
        shutil.copy2(path, target)
        target.chmod(0o700)
        copied[name] = target
    pm2 = destination / "pm2"
    shutil.copy2(PM2_SHIM, pm2)
    pm2.chmod(0o700)
    copied["pm2"] = pm2
    return copied


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
        marker = False
        if pid > 0:
            try:
                marker = f"POCKETLAB_QUALIFICATION_RUN_ID={expected}" in Path(f"/proc/{pid}/environ").read_bytes().replace(b"\x00", b"\n").decode("utf-8", "ignore")
            except (FileNotFoundError, OSError, UnicodeError):
                marker = False
        services[name] = {
            "status": str(pm2_env.get("status") or "unknown"),
            "pid_present": pid > 0,
            "run_marker": marker,
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
        source = root / "candidate"
        _extract_commit(repo, candidate, source)
        assets = _release_assets(source, candidate, root, npm)
        package = _promotion_artifact(repo, candidate, root)
        copied = _copy_binaries(root, binaries)
        _copy_runtime_tree(source, root)
        ports = _ports()
        env = _environment(root, run_id, candidate, ports, copied)
        env.update({
            "POCKETLAB_LOCAL_DIST_ZIP": assets["archive"],
            "POCKETLAB_LOCAL_RELEASE_MANIFEST": assets["manifest"],
            "POCKETLAB_LOCAL_RELEASE_CHECKSUMS": assets["checksums"],
            "POCKETLAB_LOCAL_RELEASE_TAG": assets["tag"],
        })
        Path(env["HOME"]).mkdir(mode=0o700, parents=True, exist_ok=True)
        start = _run([
            "bash",
            str(source / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched" / "scripts" / "start-dashboard.sh"),
            "--lite",
            "--reconcile-only",
        ], cwd=source, env=env, timeout=300, check=False)
        if start.returncode != 0:
            raise QualificationError("isolated runtime owners did not converge")
        observation = _observe(env, run_id)
        status, runtime = _http_json(env["POCKETLAB_COORDINATED_API_URL"] + "/api/lite/runtime")
        health, _ = _http_json(env["POCKETLAB_COORDINATED_API_URL"] + "/health")
        ready, _ = _http_json(env["POCKETLAB_COORDINATED_API_URL"] + "/ready")
        identity_status = runtime.get("runtime_identity", {}).get("status") if isinstance(runtime.get("runtime_identity"), dict) else runtime.get("runtime_identity_status")
        payload.update({
            "status": "PASS" if observation["all_required_online"] and status == 200 and health == 200 and ready == 200 and identity_status == "stable" else "FAIL",
            "package": {"status": "PASS", "backend": package["verified"], "pwa": {"source_commit": candidate, "artifact_sha256": assets["digest"], "release_tag": assets["tag"]}},
            "runtime_identity": {"status": "PASS" if identity_status == "stable" else "FAIL", "api_status": status, "identity_status": identity_status, "service_observation": observation},
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
