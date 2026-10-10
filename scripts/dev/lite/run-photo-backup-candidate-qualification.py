#!/usr/bin/env python3
"""Run exact-SHA Photo Backup qualification in a disposable DEV-PC lane.

The existing phone qualification launcher separates JSON/SQLite state but keeps
the production source tree, PM2 daemon, listeners, Caddy/PWA paths and (when
configured) NATS credentials in scope.  This runner deliberately does not use
that launcher.  It checks out one exact commit into a temporary Git worktree,
starts only a short-lived direct FastAPI process on a free loopback port, and
runs the Photo Backup service/agent tests with all production credentials and
device state removed from the child environment.

This is a candidate-code lane, not Android deployment evidence.  It does not
contact a phone, start PM2/Caddy/NATS, or publish NATS subjects.  Its only
authenticated API calls use a disposable non-Owner harness proof against the
temporary runtime and never reach production services or media.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import importlib.util
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_RE = re.compile(r"^[0-9a-f]{12}$")
DATABASE_NAME = "pocketlab-lite.sqlite3"
PHOTO_BACKUP_TESTS = (
    "tests/backend/test_lite_photo_backup.py",
    "tests/backend/test_lite_photo_backup_reliability.py",
    "tests/backend/test_lite_photo_backup_agent.py",
    "tests/backend/test_lite_photo_backup_candidate_qualification.py",
)
AUTHENTICATED_API_TESTS = (
    "test_photo_backup_api_status_and_internal_endpoints_are_semantic_only",
    "test_photo_backup_api_repeated_start_is_idempotent",
    "test_photo_backup_api_start_queues_only_domain_command",
    "test_photo_backup_api_cancel_idle_and_active_are_truthful",
)
SENSITIVE_ENV_KEYS = {
    "POCKETLAB_API_TOKEN",
    "POCKETLAB_AGENT_TOKEN",
    "POCKETLAB_AGENT_NATS_PASSWORD",
    "POCKETLAB_NATS_AGENT_PASSWORD",
    "POCKETLAB_NATS_PASSWORD",
    "POCKETLAB_NATS_TOKEN",
    "POCKETLAB_NATS_CREDENTIALS_FILE",
    "POCKETLAB_QUALIFICATION_NATS_CREDENTIALS_FILE",
    "POCKETLAB_HARNESS_SESSION",
    "POCKETLAB_HARNESS_PROVISIONING_TOKEN",
    "POCKETLAB_HARNESS_BROWSER_BRIDGE",
}
SENSITIVE_ENV_PREFIXES = (
    "POCKETLAB_NATS_TLS_",
    "POCKETLAB_RELEASE_",
    "POCKETLAB_LITE_RELEASE_",
)


class QualificationError(RuntimeError):
    """Raised when the candidate lane cannot prove its safety contract."""


def _run(
    argv: list[str],
    *,
    cwd: Path = REPO_ROOT,
    env: dict[str, str] | None = None,
    timeout: float = 30.0,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        cwd=str(cwd),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise QualificationError(f"{argv[0]} failed: {detail[-400:]}")
    return result


def _git_output(*args: str, cwd: Path = REPO_ROOT) -> str:
    return _run(["git", *args], cwd=cwd).stdout.strip()


def _validate_sha(value: str) -> str:
    candidate = str(value or "").strip().casefold()
    if not SHA_RE.fullmatch(candidate) or candidate == "0" * 40:
        raise QualificationError("candidate SHA must be a full non-zero commit SHA")
    _run(["git", "cat-file", "-e", f"{candidate}^{{commit}}"])
    return candidate


def _current_candidate_sha() -> str:
    status = _git_output("status", "--porcelain", "--untracked-files=all")
    if status:
        raise QualificationError("DEV-PC worktree must be clean before exact-SHA qualification")
    return _validate_sha(_git_output("rev-parse", "HEAD"))


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _isolated_environment(root: Path, run_id: str, api_port: int) -> dict[str, str]:
    """Build a process environment that cannot inherit production ownership."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in SENSITIVE_ENV_KEYS
        and not any(key.startswith(prefix) for prefix in SENSITIVE_ENV_PREFIXES)
    }
    home = root / "home"
    state = root / "state"
    base = root / "base"
    scratch = root / "scratch"
    for path in (home, state, base, scratch):
        path.mkdir(parents=True, exist_ok=True)

    node_id = f"qualification-photo-backup-{run_id}"
    nats_port = _free_loopback_port()
    env.update(
        {
            "HOME": str(home),
            "TMPDIR": str(scratch / "tmp"),
            "TMP": str(scratch / "tmp"),
            "TEMP": str(scratch / "tmp"),
            "XDG_CONFIG_HOME": str(scratch / "config"),
            "XDG_STATE_HOME": str(scratch / "xdg-state"),
            "XDG_CACHE_HOME": str(scratch / "cache"),
            "POCKETLAB_ENVIRONMENT": "qualification",
            "POCKETLAB_HARNESS_ENABLED": "1",
            "POCKETLAB_HARNESS_DESTRUCTIVE": "0",
            "POCKETLAB_QUALIFICATION_OWNER": "0",
            "POCKETLAB_TEST_AUTH_BYPASS": "0",
            "POCKETLAB_ALLOW_LOCAL_WRITE": "0",
            "POCKETLAB_STATE_DIR": str(state),
            "POCKETLAB_QUALIFICATION_STATE_DIR": str(state),
            "POCKETLAB_LITE_DB_PATH": str(state / DATABASE_NAME),
            "POCKETLAB_BASE_DIR": str(base),
            "POCKET_LAB_BASE_DIR": str(base),
            "POCKETLAB_CADDYFILE": str(base / "caddy" / "Caddyfile"),
            "POCKET_LAB_CADDYFILE": str(base / "caddy" / "Caddyfile"),
            "CADDYFILE": str(base / "caddy" / "Caddyfile"),
            "PWA_DIR": str(base / "pwa"),
            "POCKET_LAB_PWA_DIR": str(base / "pwa"),
            "PM2_HOME": str(root / "pm2"),
            "POCKETLAB_API_HOST": "127.0.0.1",
            "POCKETLAB_API_PORT": str(api_port),
            "API_PORT": str(api_port),
            "DASH_PORT": str(_free_loopback_port()),
            "POCKETLAB_LITE_NATS_PORT": str(nats_port),
            "POCKETLAB_NATS_URL": f"nats://127.0.0.1:{nats_port}",
            "POCKETLAB_NATS_NAME": f"qualification-{run_id}",
            "POCKETLAB_NATS_REQUIRED": "0",
            "POCKETLAB_NATS_REQUIRE_JETSTREAM": "0",
            "POCKETLAB_NATS_INITIAL_CONNECT_DEADLINE": "0.25",
            "POCKETLAB_NATS_RECONNECT_MIN_SECONDS": "60",
            "POCKETLAB_NATS_RECONNECT_MAX_SECONDS": "60",
            "POCKETLAB_NATS_WATCHDOG_SECONDS": "60",
            "POCKETLAB_NODE_ID": node_id,
            "POCKETLAB_NODE_NAME": node_id,
            "POCKETLAB_NODE_ROLE": "compute",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }
    )
    return env


def _assert_isolated_environment(env: dict[str, str], root: Path, run_id: str) -> None:
    required = {
        "POCKETLAB_ENVIRONMENT": "qualification",
        "POCKETLAB_HARNESS_DESTRUCTIVE": "0",
        "POCKETLAB_QUALIFICATION_OWNER": "0",
        "POCKETLAB_TEST_AUTH_BYPASS": "0",
        "POCKETLAB_NATS_REQUIRED": "0",
        "POCKETLAB_NATS_REQUIRE_JETSTREAM": "0",
        "POCKETLAB_NODE_ID": f"qualification-photo-backup-{run_id}",
    }
    for key, expected in required.items():
        if env.get(key) != expected:
            raise QualificationError(f"qualification environment is unsafe: {key}")
    root_resolved = root.resolve()
    for key in (
        "HOME",
        "TMPDIR",
        "XDG_CONFIG_HOME",
        "XDG_STATE_HOME",
        "XDG_CACHE_HOME",
        "POCKETLAB_STATE_DIR",
        "POCKETLAB_QUALIFICATION_STATE_DIR",
        "POCKETLAB_BASE_DIR",
        "PM2_HOME",
    ):
        value = Path(env[key]).resolve()
        try:
            value.relative_to(root_resolved)
        except ValueError as exc:
            raise QualificationError(f"qualification path escaped temporary root: {key}") from exc
    if any(key in env for key in SENSITIVE_ENV_KEYS):
        raise QualificationError("production credential environment leaked into qualification")
    if any(any(key.startswith(prefix) for prefix in SENSITIVE_ENV_PREFIXES) for key in env):
        raise QualificationError("production credential namespace leaked into qualification")


def qualification_manifest(candidate_sha: str, run_id: str, env: dict[str, str]) -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "status": "prepared",
        "candidate_sha": candidate_sha,
        "run_id": run_id,
        "qualification_surface": "devpc_exact_candidate_worktree",
        "source_tree": "temporary_git_worktree",
        "state": "temporary_private_root",
        "credentials": "production_credentials_removed",
        "synthetic_identity": "security-assurance-runner; key-bound and ephemeral",
        "pm2": "not_started",
        "caddy": "not_started",
        "nats": "not_started; no subjects published",
        "phones_contacted": False,
        "api_bind": f"127.0.0.1:{env['POCKETLAB_API_PORT']}",
        "node_id": env["POCKETLAB_NODE_ID"],
        "sanitized": True,
    }


def _wait_http(url: str, *, timeout: float = 20.0) -> bytes:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return response.read(128 * 1024)
                last_error = RuntimeError(f"HTTP {response.status}")
        except (OSError, urllib.error.URLError, RuntimeError) as exc:
            last_error = exc
        time.sleep(0.15)
    raise QualificationError(f"isolated candidate API did not become ready: {type(last_error).__name__}")


@contextlib.contextmanager
def _candidate_api(worktree: Path, env: dict[str, str]) -> Iterator[dict[str, object]]:
    runtime_root = worktree / "pocket-lab-final-structure"
    log_path = worktree.parent / "candidate-api.log"
    child_env = dict(env)
    child_env["PYTHONPATH"] = os.pathsep.join(
        [str(worktree), str(runtime_root / "runtime"), child_env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    api_port = env["POCKETLAB_API_PORT"]
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "runtime.api_fastapi.pocket_lab_fastapi_server:app",
                "--host",
                "127.0.0.1",
                "--port",
                api_port,
                "--lifespan",
                "off",
                "--log-level",
                "warning",
            ],
            cwd=str(runtime_root),
            env=child_env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    try:
        try:
            health = _wait_http(f"http://127.0.0.1:{api_port}/health")
        except QualificationError as exc:
            log_tail = ""
            try:
                log_tail = "\n".join(log_path.read_text(encoding="utf-8").splitlines()[-20:])
            except OSError:
                pass
            detail = f"{exc}; process_returncode={process.poll()}"
            if log_tail:
                detail += f"; api_log_tail={log_tail[-2400:]}"
            raise QualificationError(detail) from exc
        with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/openapi.json", timeout=3.0) as response:
            openapi = json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
        paths = set(openapi.get("paths") or {})
        required = {
            "/api/lite/media-backup",
            "/api/lite/devices/{node_id}/photo-backup",
            "/api/lite/devices/{node_id}/photo-backup/cancel",
        }
        missing = sorted(required - paths)
        if missing:
            raise QualificationError(f"candidate OpenAPI contract is missing: {','.join(missing)}")
        yield {"health_bytes": len(health), "openapi_paths": len(paths), "process_pid": process.pid}
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if process.poll() is None:
            raise QualificationError("isolated candidate API process did not stop")


def _run_candidate_tests(worktree: Path, env: dict[str, str], timeout: float) -> str:
    child_env = dict(env)
    runtime_root = worktree / "pocket-lab-final-structure" / "runtime"
    child_env["PYTHONPATH"] = os.pathsep.join(
        [str(worktree), str(runtime_root), child_env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    excluded = " and ".join(f"not {name}" for name in AUTHENTICATED_API_TESTS)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            *PHOTO_BACKUP_TESTS,
            "-k",
            excluded,
        ],
        cwd=str(worktree),
        env=child_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stdout or "").splitlines()[-80:])
        raise QualificationError(f"exact candidate P0/P1 tests failed:\n{tail}")
    return result.stdout or ""


def _prepare_worktree(parent: Path, candidate_sha: str) -> Path:
    worktree = parent / "candidate"
    _run(["git", "worktree", "add", "--detach", str(worktree), candidate_sha], timeout=60)
    observed = _validate_sha(_git_output("rev-parse", "HEAD", cwd=worktree))
    if observed != candidate_sha:
        raise QualificationError("candidate worktree SHA changed during checkout")
    return worktree


def _remove_worktree(worktree: Path) -> None:
    if not worktree.exists():
        return
    _run(["git", "worktree", "remove", "--force", str(worktree)], timeout=60)


def run(candidate_sha: str | None, *, test_timeout: float) -> dict[str, object]:
    selected_sha = _validate_sha(candidate_sha) if candidate_sha else _current_candidate_sha()
    run_id = f"{int(time.time()):x}"[-4:] + os.urandom(4).hex()
    if not RUN_ID_RE.fullmatch(run_id):
        raise QualificationError("qualification run id generation failed")
    api_port = _free_loopback_port()
    with tempfile.TemporaryDirectory(prefix="pocketlab-photo-backup-candidate-") as temporary:
        root = Path(temporary)
        env = _isolated_environment(root, run_id, api_port)
        _assert_isolated_environment(env, root, run_id)
        worktree = _prepare_worktree(root, selected_sha)
        try:
            manifest = qualification_manifest(selected_sha, run_id, env)
            with _candidate_api(worktree, env) as api_evidence:
                test_output = _run_candidate_tests(worktree, env, test_timeout)
            summary = {
                **manifest,
                "status": "PASS",
                "candidate_worktree_sha": _git_output("rev-parse", "HEAD", cwd=worktree),
                "api": {**api_evidence, "status": "PASS"},
                "service_agent_tests": {
                    "status": "PASS",
                    "output_tail": "\n".join(test_output.splitlines()[-4:]),
                },
                "authenticated_api_tests": {
                    "status": "PASS",
                    "profile": "security-assurance-runner",
                    "owner_authority": False,
                    "test_auth_bypass": False,
                    "tests": ["test_harness_backed_photo_backup_api_contract"],
                    "excluded_legacy_tests": list(AUTHENTICATED_API_TESTS),
                },
                "android_candidate": {
                    "status": "BLOCKED",
                    "reason": "no safe exact-candidate deployment/isolation lane on Android",
                },
            }
            return summary
        finally:
            _remove_worktree(worktree)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", default="", help="full commit SHA; defaults to the clean current HEAD")
    parser.add_argument("--test-timeout-seconds", type=float, default=900.0)
    parser.add_argument("--nats-server-bin", default="", help="explicit approved nats-server executable for the full lane")
    parser.add_argument("--opa-bin", default="", help="explicit approved OPA executable for the full lane")
    parser.add_argument(
        "--full",
        action="store_true",
        help="compose the disposable API-only lane with the full isolated NATS/WebDAV/agent lane",
    )
    args = parser.parse_args(argv)
    if args.test_timeout_seconds < 30 or args.test_timeout_seconds > 3600:
        parser.error("--test-timeout-seconds must be between 30 and 3600")
    if args.full:
        module_path = SCRIPT_DIR / "run-isolated-runtime-qualification.py"
        spec = importlib.util.spec_from_file_location("isolated_runtime_qualification", module_path)
        if spec is None or spec.loader is None:
            print(json.dumps({"status": "FAIL", "reason": "full qualification controller unavailable", "sanitized": True}, sort_keys=True))
            return 1
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        forwarded = ["--candidate-sha", args.candidate_sha or _current_candidate_sha(), "--python", sys.executable]
        if args.nats_server_bin:
            forwarded.extend(["--nats-server-bin", args.nats_server_bin])
        if args.opa_bin:
            forwarded.extend(["--opa-bin", args.opa_bin])
        return int(module.main(forwarded))
    try:
        result = run(args.candidate_sha or None, test_timeout=args.test_timeout_seconds)
    except (OSError, QualificationError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)[:1200], "sanitized": True}, sort_keys=True))
        return 1
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
