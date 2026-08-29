#!/usr/bin/env python3
"""Explicit WSL2/CI supply-chain automation for Pocket Lab Lite.

This program is intentionally not invoked by MkDocs or lite:docs:check.

Lifecycle:
  capture  -> transient raw output under .pocketlab-dev
  promote  -> bounded normalized/CycloneDX contracts under contracts/generated
  check    -> validate already-promoted canonical contracts only

Runtime evidence is never collected here. The runtime SBOM projection is derived solely from the
already-promoted sanitized runtime baseline. Termux Trivy remains owned by the existing bounded
Security profiles and may later contribute only through promoted sanitized evidence.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[3]
META = ROOT / "contracts/metadata/documentation-security-tools.json"
RUNTIME = ROOT / "contracts/parity/runtime-verification-baseline.json"
OUT = ROOT / "contracts/generated/supply-chain"
DEFAULT_RUN_ROOT = ROOT / ".pocketlab-dev/documentation-security/runs"
TOOL_ROOT = ROOT / ".pocketlab-dev/tools/documentation-security/bin"
CAPTURE_SCHEMA_VERSION = "2.1.0"
ACCEPTED_STEP_STATES = {"completed", "findings-or-tool-nonzero"}
ACTIVE_STEP_STATES = {"starting", "running"}
SCANCODE_DEFAULT_PROCESSES = 2
SCANCODE_MIN_PROCESSES = 1
SCANCODE_MAX_PROCESSES = 4
RESOURCE_GUARDRAIL_EXIT = 125
DEFAULT_TIMEOUTS = {
    "syft-dev": 900,
    "syft-release": 900,
    "trivy-source": 1800,
    "trivy-sbom-dev": 900,
    "osv-source": 1200,
    "osv-sbom-dev": 1200,
    "grype-sbom-dev": 1200,
    "gitleaks-worktree": 1200,
    "gitleaks-history": 1800,
    "gitleaks-release": 1200,
    "semgrep": 1800,
    "scancode": 3600,
    "scorecard": 1800,
}
STEP_ALIASES = {
    "syft": {"syft-dev", "syft-release"},
    "trivy": {"trivy-source", "trivy-sbom-dev"},
    "osv": {"osv-source", "osv-sbom-dev"},
    "osv-scanner": {"osv-source", "osv-sbom-dev"},
    "grype": {"grype-sbom-dev"},
    "gitleaks": {"gitleaks-worktree", "gitleaks-history", "gitleaks-release"},
    "semgrep": {"semgrep"},
    "scancode": {"scancode"},
    "scorecard": {"scorecard"},
}
SCORECARD_COMPATIBLE_CHECKS = (
    "Pinned-Dependencies",
    "Dangerous-Workflow",
    "Token-Permissions",
)
SCORECARD_PROVIDER_UNAVAILABLE_CHECKS = (
    "Branch-Protection",
    "Signed-Releases",
    "Maintained",
)
SCORECARD_PROVIDER_UNAVAILABLE_REASON = "scorecard-provider-unsupported-request-type"
SCORECARD_TOKEN_ENV_KEYS = (
    "GITHUB_AUTH_TOKEN",
    "GITHUB_TOKEN",
    "GH_AUTH_TOKEN",
    "GH_TOKEN",
)
CANONICAL_FILES = {
    "sbom_dev": "sbom-dev.cdx.json",
    "sbom_release": "sbom-release.cdx.json",
    "sbom_runtime": "sbom-runtime.cdx.json",
    "vulnerabilities": "vulnerability-correlation.json",
    "licenses": "license-inventory.json",
    "security": "security-analysis.json",
    "scorecard": "scorecard-checks.json",
    "summary": "automation-summary.json",
}
PRIVATE = re.compile(r"(?:/home/[^/\s]+|/data/data/com\.termux/files/(?:home|usr)|[A-Za-z]:\\Users\\|nats://[^\s]+@)", re.I)
PRIVATE_PATH_REPLACEMENTS = (
    (re.compile(r"/home/[^/\s\"'<>]+", re.I), "<home>"),
    (re.compile(r"/data/data/com\.termux/files/home", re.I), "<termux-home>"),
    (re.compile(r"/data/data/com\.termux/files/usr", re.I), "<termux-prefix>"),
    (re.compile(r"[A-Za-z]:\\Users\\[^\\/\s\"'<>]+", re.I), "<windows-home>"),
)
SECRET = re.compile(r"(?:BEGIN [A-Z ]*PRIVATE KEY|[\"']?(?:password|passwd|token|secret|api[_-]?key|credential|authorization)[\"']?\s*[=:]\s*[\"']?[^\s,}\]\"']{6,})", re.I)


def stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, separators=(",", ": ")) + "\n"


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def fail(message: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)


def is_termux() -> bool:
    return bool(os.environ.get("TERMUX_VERSION")) or "com.termux" in os.environ.get("PREFIX", "") or platform.system().lower() == "android"


def sanitize_private_paths(value: Any) -> Any:
    """Redact host-specific filesystem roots while preserving canonical structure.

    Secret-like values are intentionally not rewritten here; ``safe_text`` still
    rejects them fail-closed.  This sanitizer exists only for machine-local path
    material that scanners may embed in otherwise useful normalized evidence.
    """
    if isinstance(value, str):
        text = value
        for pattern, replacement in PRIVATE_PATH_REPLACEMENTS:
            text = pattern.sub(replacement, text)
        return text
    if isinstance(value, list):
        return [sanitize_private_paths(item) for item in value]
    if isinstance(value, dict):
        return {key: sanitize_private_paths(item) for key, item in value.items()}
    return value


def safe_text(label: str, value: str) -> None:
    if PRIVATE.search(value):
        fail(f"{label}: private path detected in canonical output")
    if SECRET.search(value):
        fail(f"{label}: secret-like value detected in canonical output")


def tool_path(name: str) -> str:
    local = TOOL_ROOT / name
    if local.exists():
        return str(local)
    found = shutil.which(name)
    if not found:
        fail(f"required development tool is missing: {name}; run task lite:docs:security-tools:setup")
    return found


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        fail(f"{name} must be an integer")
    if value < minimum or value > maximum:
        fail(f"{name} must be between {minimum} and {maximum}")
    return value


def timeout_for(step_id: str) -> int:
    key = "POCKETLAB_SUPPLY_CHAIN_TIMEOUT_" + re.sub(r"[^A-Za-z0-9]", "_", step_id).upper()
    return env_int(key, DEFAULT_TIMEOUTS[step_id], minimum=30, maximum=7200)


def progress_interval() -> int:
    return env_int("POCKETLAB_SUPPLY_CHAIN_PROGRESS_SECONDS", 30, minimum=5, maximum=300)


def scancode_processes() -> int:
    return env_int(
        "POCKETLAB_SCANCODE_PROCESSES",
        SCANCODE_DEFAULT_PROCESSES,
        minimum=SCANCODE_MIN_PROCESSES,
        maximum=SCANCODE_MAX_PROCESSES,
    )


def scancode_preflight_mem_mib(processes: int | None = None) -> int:
    # Observed ScanCode 32.5.0 workers can approach ~1 GiB RSS each under WSL2.
    # Reserve one additional GiB for the parent/tooling and surrounding dev services.
    count = scancode_processes() if processes is None else processes
    return 1024 * (count + 1)


def scancode_runtime_mem_floor_mib() -> int:
    return env_int(
        "POCKETLAB_SCANCODE_MIN_RUNTIME_MEM_MIB",
        1536,
        minimum=512,
        maximum=8192,
    )


def scancode_runtime_swap_floor_mib() -> int:
    return env_int(
        "POCKETLAB_SCANCODE_MIN_RUNTIME_SWAP_MIB",
        256,
        minimum=0,
        maximum=8192,
    )


def meminfo() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            token = value.strip().split()[0]
            if token.isdigit():
                values[key] = int(token) * 1024
    except OSError:
        pass
    return values


def resource_snapshot() -> dict[str, Any]:
    tmp = Path(tempfile.gettempdir()).resolve()
    usage = shutil.disk_usage(tmp)
    memory = meminfo()
    return {
        "temp_root": str(tmp),
        "temp_free_bytes": usage.free,
        "mem_available_bytes": memory.get("MemAvailable"),
        "swap_total_bytes": memory.get("SwapTotal"),
        "swap_free_bytes": memory.get("SwapFree"),
    }


def configured_scratch_root() -> Path:
    raw = os.environ.get("POCKETLAB_DEV_TMPDIR")
    if not raw:
        fail(
            "POCKETLAB_DEV_TMPDIR is required for heavy supply-chain capture; "
            "run through scripts/dev/lite/dev-scratch.sh run security-tools -- ..."
        )
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate.resolve()


def ensure_capture_resources(*, step_id: str | None = None) -> dict[str, Any]:
    scratch = configured_scratch_root()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if scratch != temp_root and scratch not in temp_root.parents:
        fail(
            f"temporary directory escaped Pocket Lab dev scratch: {temp_root}; "
            f"expected a descendant of {scratch}"
        )
    minimum_gib = env_int("POCKETLAB_SUPPLY_CHAIN_MIN_SCRATCH_GIB", 5, minimum=1, maximum=100)
    snapshot = resource_snapshot()
    if int(snapshot["temp_free_bytes"]) < minimum_gib * 1024**3:
        fail(
            f"insufficient supply-chain scratch capacity: {snapshot['temp_free_bytes']} bytes free; "
            f"require at least {minimum_gib} GiB"
        )
    if step_id == "scancode":
        process_count = scancode_processes()
        worker_floor = scancode_preflight_mem_mib(process_count)
        minimum_mem_mib = env_int(
            "POCKETLAB_SUPPLY_CHAIN_MIN_MEM_MIB_SCANCODE",
            worker_floor,
            minimum=worker_floor,
            maximum=32768,
        )
    else:
        minimum_mem_mib = env_int(
            "POCKETLAB_SUPPLY_CHAIN_MIN_MEM_MIB",
            768,
            minimum=256,
            maximum=32768,
        )
    available = snapshot.get("mem_available_bytes")
    if isinstance(available, int) and available < minimum_mem_mib * 1024**2:
        fail(
            f"insufficient available memory before {step_id or 'capture'}: {available} bytes; "
            f"require at least {minimum_mem_mib} MiB"
        )
    if step_id == "scancode":
        swap_total = snapshot.get("swap_total_bytes")
        swap_free = snapshot.get("swap_free_bytes")
        minimum_swap_mib = env_int(
            "POCKETLAB_SUPPLY_CHAIN_MIN_SWAP_FREE_MIB_SCANCODE",
            512,
            minimum=256,
            maximum=8192,
        )
        if isinstance(swap_total, int) and swap_total > 0 and isinstance(swap_free, int):
            if swap_free < minimum_swap_mib * 1024**2:
                fail(
                    f"insufficient free swap before scancode: {swap_free} bytes; "
                    f"require at least {minimum_swap_mib} MiB when swap is configured"
                )
    return snapshot


def git_identity() -> dict[str, Any]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "-z"], cwd=ROOT
    )
    return {
        "source_commit": commit,
        "worktree_clean": not bool(status),
        "worktree_status_sha256": digest_bytes(status),
    }


def scorecard_repository_slug() -> str:
    try:
        origin = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except subprocess.CalledProcessError:
        fail("Scorecard requires a configured GitHub origin remote", 3)
    patterns = (
        re.compile(r"^https://github\.com/(?P<slug>[^/\s]+/[^/\s]+?)(?:\.git)?$", re.I),
        re.compile(r"^git@github\.com:(?P<slug>[^/\s]+/[^/\s]+?)(?:\.git)?$", re.I),
        re.compile(r"^ssh://git@github\.com/(?P<slug>[^/\s]+/[^/\s]+?)(?:\.git)?$", re.I),
    )
    for pattern in patterns:
        match = pattern.match(origin)
        if match:
            return f"github.com/{match.group('slug')}"
    fail("Scorecard repository posture requires a GitHub origin remote", 3)


def scorecard_auth_env() -> dict[str, str]:
    for key in SCORECARD_TOKEN_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            return {"GITHUB_AUTH_TOKEN": value}
    gh = shutil.which("gh")
    if gh:
        proc = subprocess.run(
            [gh, "auth", "token"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        token = proc.stdout.strip()
        if proc.returncode == 0 and token:
            return {"GITHUB_AUTH_TOKEN": token}
    fail(
        "Scorecard repository posture requires GitHub authentication via "
        "GITHUB_AUTH_TOKEN/GITHUB_TOKEN/GH_AUTH_TOKEN/GH_TOKEN or an authenticated gh CLI; "
        "credentials are never written to capture evidence",
        3,
    )


def ensure_release_qualification_environment(identity: dict[str, Any]) -> None:
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("CI") != "true":
        fail("--release-qualification is reserved for the canonical GitHub Actions qualification workflow", 3)
    if not identity.get("worktree_clean"):
        fail("release qualification requires a clean checkout", 3)
    github_sha = os.environ.get("GITHUB_SHA")
    if github_sha and github_sha != identity.get("source_commit"):
        fail("GITHUB_SHA does not match checked-out HEAD", 3)


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(stable(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def validate_json_artifact(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    if path.stat().st_size == 0:
        return False, "empty"
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False, "invalid-json"
    return True, "valid-json"


def process_start_time_ticks(pid: int) -> int | None:
    try:
        stat = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
        # /proc/<pid>/stat field 2 is parenthesized and may contain spaces.
        # Parse from the final ')' so field 22 (starttime) remains stable.
        tail = stat.rsplit(")", 1)[1].strip().split()
        return int(tail[19])
    except (OSError, ValueError, IndexError):
        return None


def process_identity_alive(step: dict[str, Any]) -> bool:
    pid = step.get("child_pid")
    expected_ticks = step.get("child_start_time_ticks")
    if not isinstance(pid, int) or pid <= 0:
        return False
    actual_ticks = process_start_time_ticks(pid)
    if actual_ticks is None:
        return False
    return expected_ticks is None or actual_ticks == expected_ticks


def process_family_snapshot(root_pid: int) -> dict[str, float | int]:
    try:
        text = subprocess.check_output(
            ["ps", "-e", "-o", "pid=,ppid=,rss=,%cpu="],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return {"process_count": 0, "rss_bytes": 0, "cpu_percent": 0.0}
    rows: dict[int, tuple[int, int, float]] = {}
    children: dict[int, list[int]] = defaultdict(list)
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        try:
            pid, ppid, rss_kib = (int(parts[0]), int(parts[1]), int(parts[2]))
            cpu = float(parts[3])
        except ValueError:
            continue
        rows[pid] = (ppid, rss_kib, cpu)
        children[ppid].append(pid)
    pending = [root_pid]
    family: set[int] = set()
    while pending:
        pid = pending.pop()
        if pid in family:
            continue
        family.add(pid)
        pending.extend(children.get(pid, []))
    rss_kib = sum(rows.get(pid, (0, 0, 0.0))[1] for pid in family)
    cpu = sum(rows.get(pid, (0, 0, 0.0))[2] for pid in family)
    return {
        "process_count": len([pid for pid in family if pid in rows]),
        "rss_bytes": rss_kib * 1024,
        "cpu_percent": round(cpu, 1),
    }


def output_size(path: Path | None) -> int:
    if path is None:
        return 0
    try:
        return path.stat().st_size
    except OSError:
        return 0


def scancode_runtime_guardrail(snapshot: dict[str, Any]) -> str | None:
    available = snapshot.get("mem_available_bytes")
    minimum_mem = scancode_runtime_mem_floor_mib() * 1024**2
    if isinstance(available, int) and available < minimum_mem:
        return f"mem_available_below_{scancode_runtime_mem_floor_mib()}_mib"
    swap_total = snapshot.get("swap_total_bytes")
    swap_free = snapshot.get("swap_free_bytes")
    minimum_swap = scancode_runtime_swap_floor_mib() * 1024**2
    if (
        minimum_swap > 0
        and isinstance(swap_total, int)
        and swap_total > 0
        and isinstance(swap_free, int)
        and swap_free < minimum_swap
    ):
        return f"swap_free_below_{scancode_runtime_swap_floor_mib()}_mib"
    return None


def terminate_process_group(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
        return
    except (ProcessLookupError, subprocess.TimeoutExpired):
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    proc.wait(timeout=5)


def run_tool(
    step_id: str,
    name: str,
    argv: list[str],
    output: Path | None,
    *,
    expected_output: Path | None = None,
    allow_nonzero: bool = True,
    run_dir: Path,
    preflight_snapshot: dict[str, Any] | None = None,
    on_started: Callable[[dict[str, Any]], None] | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    binary = tool_path(name)
    command = [binary, *argv]
    timeout = timeout_for(step_id)
    interval = progress_interval()
    poll_interval = min(5, interval) if step_id == "scancode" else interval
    logs = run_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stderr_path = logs / f"{step_id}.stderr.log"
    stdout_path = logs / f"{step_id}.stdout.log"
    required_artifact = expected_output or output
    started_wall = utc_now()
    started = time.monotonic()
    before = preflight_snapshot or ensure_capture_resources(step_id=step_id)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        stdout_handle = output.open("wb")
    else:
        stdout_handle = stdout_path.open("wb")
    stderr_handle = stderr_path.open("wb")

    print(f"START {step_id} tool={name} timeout={timeout}s", flush=True)
    proc: subprocess.Popen[Any] | None = None
    child_pid: int | None = None
    child_start_ticks: int | None = None
    timed_out = False
    guardrail_reason: str | None = None
    interrupted_signal: int | None = None
    peak_family_rss = 0
    min_mem_available = before.get("mem_available_bytes") if isinstance(before.get("mem_available_bytes"), int) else None
    min_swap_free = before.get("swap_free_bytes") if isinstance(before.get("swap_free_bytes"), int) else None
    max_output_bytes = output_size(required_artifact)
    next_progress = started + interval
    previous_handlers: dict[int, Any] = {}

    def _signal_handler(signum: int, _frame: Any) -> None:
        nonlocal interrupted_signal
        interrupted_signal = signum
        if proc is not None:
            terminate_process_group(proc)

    try:
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            try:
                previous_handlers[signum] = signal.getsignal(signum)
                signal.signal(signum, _signal_handler)
            except (ValueError, OSError):
                pass
        child_env = None
        if extra_env:
            child_env = os.environ.copy()
            child_env.update(extra_env)
        proc = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
            env=child_env,
        )
        child_pid = proc.pid
        child_start_ticks = process_start_time_ticks(proc.pid)
        process_info = {
            "child_pid": child_pid,
            "child_start_time_ticks": child_start_ticks,
        }
        if on_started is not None:
            on_started(process_info)
        deadline = started + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                terminate_process_group(proc)
                break
            try:
                proc.wait(timeout=min(poll_interval, remaining))
                break
            except subprocess.TimeoutExpired:
                now = time.monotonic()
                snap = resource_snapshot()
                family = process_family_snapshot(proc.pid)
                peak_family_rss = max(peak_family_rss, int(family.get("rss_bytes") or 0))
                available = snap.get("mem_available_bytes")
                if isinstance(available, int):
                    min_mem_available = available if min_mem_available is None else min(min_mem_available, available)
                swap_free = snap.get("swap_free_bytes")
                if isinstance(swap_free, int):
                    min_swap_free = swap_free if min_swap_free is None else min(min_swap_free, swap_free)
                max_output_bytes = max(max_output_bytes, output_size(required_artifact))
                if step_id == "scancode":
                    guardrail_reason = scancode_runtime_guardrail(snap)
                    if guardrail_reason:
                        print(
                            f"ERROR scancode resource guardrail triggered reason={guardrail_reason} "
                            f"family_rss_mib={int(family.get('rss_bytes') or 0) / 1024**2:.0f} "
                            f"mem_available_mib={((available or 0) / 1024**2):.0f} "
                            f"swap_free_mib={((swap_free or 0) / 1024**2):.0f}",
                            flush=True,
                        )
                        terminate_process_group(proc)
                        break
                if now >= next_progress:
                    elapsed = int(now - started)
                    print(
                        f"PROGRESS {step_id} elapsed={elapsed}s "
                        f"scratch_free_gib={int(snap['temp_free_bytes']) / 1024**3:.1f} "
                        f"mem_available_mib={((available or 0) / 1024**2):.0f} "
                        f"swap_free_mib={((swap_free or 0) / 1024**2):.0f} "
                        f"family_processes={int(family.get('process_count') or 0)} "
                        f"family_rss_mib={int(family.get('rss_bytes') or 0) / 1024**2:.0f} "
                        f"family_cpu_pct={float(family.get('cpu_percent') or 0):.1f} "
                        f"output_bytes={max_output_bytes}",
                        flush=True,
                    )
                    next_progress = now + interval
    finally:
        for signum, handler in previous_handlers.items():
            try:
                signal.signal(signum, handler)
            except (ValueError, OSError):
                pass
        stdout_handle.close()
        stderr_handle.close()

    duration = round(time.monotonic() - started, 3)
    if interrupted_signal is not None:
        code = 128 + interrupted_signal
        state = "interrupted"
    elif guardrail_reason is not None:
        code = RESOURCE_GUARDRAIL_EXIT
        state = "resource-guardrail"
    elif timed_out:
        code = 124
        state = "timed-out"
    else:
        code = int(proc.returncode if proc is not None and proc.returncode is not None else 1)
        state = "completed" if code == 0 else "findings-or-tool-nonzero" if allow_nonzero else "failed"
    validation = None
    if required_artifact is not None:
        valid, validation = validate_json_artifact(required_artifact)
        if not valid and state not in {"timed-out", "interrupted", "resource-guardrail"}:
            state = "failed-invalid-output"
    after = resource_snapshot()
    stderr_digest = digest_file(stderr_path) if stderr_path.exists() else "unavailable"
    result = {
        "step_id": step_id,
        "tool": name,
        "command_shape": [name, *argv],
        "exit_code": code,
        "status": state,
        "timeout_seconds": timeout,
        "duration_seconds": duration,
        "started_at": started_wall,
        "completed_at": utc_now(),
        "stderr_sha256": stderr_digest,
        "raw_output": str(required_artifact.relative_to(run_dir)) if required_artifact and required_artifact.exists() else None,
        "output_validation": validation,
        "resources_before": before,
        "resources_after": after,
        "peak_family_rss_bytes": peak_family_rss,
        "min_mem_available_bytes": min_mem_available,
        "min_swap_free_bytes": min_swap_free,
        "max_output_bytes": max_output_bytes,
        "resource_guardrail_reason": guardrail_reason,
        "interrupted_signal": interrupted_signal,
        "child_pid": child_pid,
        "child_start_time_ticks": child_start_ticks,
    }
    if state == "timed-out":
        print(f"ERROR {step_id} timed out after {timeout}s; checkpoint preserved in {run_dir}", flush=True)
    elif state == "resource-guardrail":
        print(f"ERROR {step_id} stopped by resource guardrail ({guardrail_reason}); checkpoint preserved in {run_dir}", flush=True)
    elif state == "interrupted":
        print(f"ERROR {step_id} interrupted by signal {interrupted_signal}; checkpoint preserved in {run_dir}", flush=True)
    elif state == "failed-invalid-output":
        print(f"ERROR {step_id} produced {validation}; checkpoint preserved in {run_dir}", flush=True)
    elif state == "failed":
        print(f"ERROR {step_id} failed exit={code}; checkpoint preserved in {run_dir}", flush=True)
    elif state == "findings-or-tool-nonzero":
        print(f"WARN {step_id} exit={code} with valid JSON evidence duration={duration}s", flush=True)
    else:
        print(f"PASS {step_id} duration={duration}s", flush=True)
    return result

def safe_unzip(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        base = destination.resolve()
        for item in zf.infolist():
            target = (destination / item.filename).resolve()
            if base not in target.parents and target != base:
                fail(f"release archive path traversal rejected: {item.filename}")
        zf.extractall(destination)


def new_run_dir() -> Path:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = hashlib.sha256(f"{now}:{os.getpid()}".encode()).hexdigest()[:8]
    return DEFAULT_RUN_ROOT / f"{now}-{suffix}"


def selected_steps(
    include_history: bool,
    has_release: bool,
    only: str | None,
    *,
    enable_scancode: bool = False,
) -> set[str]:
    active = {
        "syft-dev",
        "trivy-source",
        "trivy-sbom-dev",
        "osv-source",
        "osv-sbom-dev",
        "grype-sbom-dev",
        "gitleaks-worktree",
        "semgrep",
        "scorecard",
    }
    if enable_scancode:
        active.add("scancode")
    if include_history:
        active.add("gitleaks-history")
    if has_release:
        active.update({"syft-release", "gitleaks-release"})
    if not only:
        return active
    requested: set[str] = set()
    for token in (part.strip() for part in only.split(",")):
        if not token:
            continue
        if token in STEP_ALIASES:
            requested.update(STEP_ALIASES[token])
        elif token in DEFAULT_TIMEOUTS:
            requested.add(token)
        else:
            fail(f"unknown scanner/step for --only: {token}")
    requested &= active
    if requested & {"trivy-sbom-dev", "osv-sbom-dev", "grype-sbom-dev"}:
        requested.add("syft-dev")
    if not requested:
        fail("--only selected no steps available for this capture configuration")
    return requested


def ensure_scancode_execution_allowed(*, enable_scancode: bool, release_qualification: bool) -> None:
    if not enable_scancode:
        return
    if release_qualification:
        return
    if os.environ.get("POCKETLAB_ALLOW_LOCAL_SCANCODE") == "1":
        return
    fail(
        "local ScanCode execution is disabled by default after host-instability evidence; "
        "prefer CI, or set POCKETLAB_ALLOW_LOCAL_SCANCODE=1 for an explicit local deep-license diagnostic",
        3,
    )


def save_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = utc_now()
    atomic_write_json(run_dir / "capture-manifest.json", manifest)


def manifest_step(manifest: dict[str, Any], step_id: str) -> dict[str, Any] | None:
    for item in manifest.get("tools", []):
        if isinstance(item, dict) and item.get("step_id") == step_id:
            return item
    return None


def step_can_resume(manifest: dict[str, Any], step_id: str, expected: Path | None) -> bool:
    prior = manifest_step(manifest, step_id)
    if not prior or prior.get("status") not in ACCEPTED_STEP_STATES:
        return False
    if expected is None:
        return True
    valid, _ = validate_json_artifact(expected)
    return valid


def record_step(run_dir: Path, manifest: dict[str, Any], result: dict[str, Any]) -> None:
    manifest["tools"] = [
        item for item in manifest.get("tools", [])
        if not (isinstance(item, dict) and item.get("step_id") == result.get("step_id"))
    ]
    manifest["tools"].append(result)
    save_manifest(run_dir, manifest)


def starting_step_is_stale(step: dict[str, Any], *, grace_seconds: int = 120) -> bool:
    raw = step.get("started_at")
    if not isinstance(raw, str) or not raw:
        return True
    try:
        started = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return True
    age = (dt.datetime.now(dt.timezone.utc) - started).total_seconds()
    return age >= grace_seconds


def reconcile_interrupted_steps(run_dir: Path, manifest: dict[str, Any]) -> bool:
    changed = False
    interrupted: dict[str, Any] | None = None
    for item in manifest.get("tools", []):
        if not isinstance(item, dict) or item.get("status") not in ACTIVE_STEP_STATES:
            continue
        if item.get("status") == "running" and process_identity_alive(item):
            continue
        if item.get("status") == "starting" and not starting_step_is_stale(item):
            continue
        item["status"] = "interrupted"
        item["completed_at"] = utc_now()
        item["exit_code"] = None
        item["interruption_reason"] = "recorded-process-not-running"
        interrupted = item
        changed = True
    if changed:
        manifest["capture_complete"] = False
        if interrupted is not None:
            if bool(interrupted.get("required", True)):
                manifest["failure"] = {
                    "step_id": interrupted.get("step_id"),
                    "status": "interrupted",
                    "exit_code": None,
                }
            else:
                optional_failures = manifest.setdefault("optional_failures", [])
                optional_failures[:] = [
                    item for item in optional_failures
                    if not (isinstance(item, dict) and item.get("step_id") == interrupted.get("step_id"))
                ]
                optional_failures.append(
                    {
                        "step_id": interrupted.get("step_id"),
                        "status": "interrupted",
                        "exit_code": None,
                    }
                )
                manifest.pop("failure", None)
        save_manifest(run_dir, manifest)
    return changed


def run_capture_step(
    run_dir: Path,
    manifest: dict[str, Any],
    *,
    resume: bool,
    selected: set[str],
    step_id: str,
    tool: str,
    argv: list[str],
    stdout_output: Path | None,
    expected_output: Path | None = None,
    allow_nonzero: bool = True,
    scanner_config: dict[str, Any] | None = None,
    required: bool = True,
    extra_env: dict[str, str] | None = None,
) -> None:
    if step_id not in selected:
        return
    expected = expected_output or stdout_output
    if resume and step_can_resume(manifest, step_id, expected):
        print(f"SKIP {step_id} checkpoint already valid", flush=True)
        return

    preflight = ensure_capture_resources(step_id=step_id)
    prior = manifest_step(manifest, step_id)
    attempt = int(prior.get("attempt") or 0) + 1 if prior else 1
    lifecycle: dict[str, Any] = {
        "step_id": step_id,
        "tool": tool,
        "status": "starting",
        "exit_code": None,
        "attempt": attempt,
        "started_at": utc_now(),
        "timeout_seconds": timeout_for(step_id),
        "scanner_config": scanner_config or {},
        "required": required,
        "resources_before": preflight,
    }
    record_step(run_dir, manifest, lifecycle)

    def on_started(process_info: dict[str, Any]) -> None:
        lifecycle.update(process_info)
        lifecycle["status"] = "running"
        record_step(run_dir, manifest, lifecycle)

    result = run_tool(
        step_id,
        tool,
        argv,
        stdout_output,
        expected_output=expected_output,
        allow_nonzero=allow_nonzero,
        run_dir=run_dir,
        preflight_snapshot=preflight,
        on_started=on_started,
        extra_env=extra_env,
    )
    result["attempt"] = attempt
    result["scanner_config"] = scanner_config or {}
    record_step(run_dir, manifest, result)
    if result["status"] not in ACCEPTED_STEP_STATES:
        if not required:
            optional_failures = manifest.setdefault("optional_failures", [])
            optional_failures[:] = [
                item for item in optional_failures
                if not (isinstance(item, dict) and item.get("step_id") == step_id)
            ]
            optional_failures.append(
                {
                    "step_id": step_id,
                    "status": result["status"],
                    "exit_code": result["exit_code"],
                }
            )
            save_manifest(run_dir, manifest)
            print(
                f"WARN optional {step_id} unavailable ({result['status']}); "
                "required qualification continues without deep-source license coverage",
                flush=True,
            )
            return
        manifest["capture_complete"] = False
        manifest["failure"] = {
            "step_id": step_id,
            "status": result["status"],
            "exit_code": result["exit_code"],
        }
        save_manifest(run_dir, manifest)
        fail(
            f"capture stopped at {step_id} ({result['status']}); "
            f"resume with --run-dir {run_dir} --resume after correcting the cause"
        )

def prepare_release_staging() -> tuple[tempfile.TemporaryDirectory[str], Path]:
    holder = tempfile.TemporaryDirectory(prefix="pocketlab-release-scan-")
    staging = Path(holder.name)
    safe_unzip(ROOT / "dist.zip", staging)
    return holder, staging


def capture(
    run_dir: Path,
    include_history: bool,
    *,
    resume: bool = False,
    only: str | None = None,
    release_qualification: bool = False,
    enable_scancode: bool = False,
) -> int:
    if is_termux():
        fail("heavy supply-chain automation is WSL2/CI-only; use existing bounded Termux Security profiles for runtime scanning", 3)
    preflight = ensure_capture_resources()
    identity = git_identity()
    if release_qualification:
        ensure_release_qualification_environment(identity)
    ensure_scancode_execution_allowed(
        enable_scancode=enable_scancode,
        release_qualification=release_qualification,
    )

    run_dir = run_dir.resolve()
    raw = run_dir / "raw"
    manifest_path = run_dir / "capture-manifest.json"
    has_release = (ROOT / "dist.zip").exists()
    selected = selected_steps(
        include_history,
        has_release,
        only,
        enable_scancode=enable_scancode,
    )
    required_selection = selected_steps(
        include_history,
        has_release,
        None,
        enable_scancode=False,
    )

    if resume:
        if not manifest_path.exists() or not raw.is_dir():
            fail("--resume requires an existing run directory with capture-manifest.json and raw/")
        manifest = read_json(manifest_path, {})
        if manifest.get("schema_version") != CAPTURE_SCHEMA_VERSION:
            fail("capture checkpoint schema is incompatible with resume")
        reconcile_interrupted_steps(run_dir, manifest)
        for key in ("source_commit", "worktree_status_sha256"):
            if manifest.get(key) != identity.get(key):
                fail(f"resume rejected because {key} changed since capture began")
        if bool(manifest.get("include_git_history")) != include_history:
            fail("resume rejected because --include-git-history changed")
        if bool(manifest.get("release_qualification")) != release_qualification:
            fail("resume rejected because release qualification mode changed")
        if bool(manifest.get("scancode_requested")) != enable_scancode:
            fail("resume rejected because ScanCode opt-in mode changed")
        manifest["resume_count"] = int(manifest.get("resume_count") or 0) + 1
        manifest.pop("failure", None)
        print(f"RESUME supply-chain capture {run_dir.name}", flush=True)
    else:
        if run_dir.exists():
            fail(f"run directory already exists; use --resume explicitly: {run_dir}")
        raw.mkdir(parents=True, exist_ok=False)
        manifest = {
            "schema_version": CAPTURE_SCHEMA_VERSION,
            "mode": "transient-capture",
            "canonical": False,
            "runtime_capture_performed": False,
            "runtime_promotion_performed": False,
            "run_id": run_dir.name,
            **identity,
            "tools": [],
            "release_artifact": "present" if has_release else "missing",
            "include_git_history": include_history,
            "release_qualification": release_qualification,
            "scancode_requested": enable_scancode,
            "scancode_required": False,
            "license_authority": {
                "package_license": {"required": True, "sources": ["syft", "trivy"]},
                "deep_source_license": {"required": False, "provider": "scancode"},
            },
            "qualification_surface": "github-actions-release" if release_qualification else "local-or-ci-diagnostic",
            "max_parallel_scanners": 1,
            "selected_steps": sorted(selected),
            "capture_complete": False,
            "resume_count": 0,
            "preflight": preflight,
        }
        save_manifest(run_dir, manifest)

    manifest["selected_steps"] = sorted(selected)
    manifest["capture_complete"] = False
    save_manifest(run_dir, manifest)

    # Keep execution sequential by design. These tools are CPU/memory/filesystem heavy;
    # max_parallel_scanners=1 is the bounded default for WSL2 and CI reliability.
    run_capture_step(run_dir, manifest, resume=resume, selected=selected, step_id="syft-dev", tool="syft", argv=["dir:.", "-o", "cyclonedx-json"], stdout_output=raw / "syft-dev.cdx.json", allow_nonzero=False)

    release_holder: tempfile.TemporaryDirectory[str] | None = None
    release_staging: Path | None = None
    try:
        if has_release and selected & {"syft-release", "gitleaks-release"}:
            release_holder, release_staging = prepare_release_staging()
        if release_staging is not None:
            run_capture_step(run_dir, manifest, resume=resume, selected=selected, step_id="syft-release", tool="syft", argv=[f"dir:{release_staging}", "-o", "cyclonedx-json"], stdout_output=raw / "syft-release.cdx.json", allow_nonzero=False)

        run_capture_step(run_dir, manifest, resume=resume, selected=selected, step_id="trivy-source", tool="trivy", argv=["fs", "--format", "json", "--scanners", "vuln,misconfig,secret,license", "--skip-dirs", ".git", "--skip-dirs", "node_modules", "--skip-dirs", ".venv", "--skip-dirs", ".pocketlab-dev", "--skip-dirs", "docs/generated", "--skip-dirs", "contracts/generated", "."], stdout_output=raw / "trivy-source.json")
        run_capture_step(run_dir, manifest, resume=resume, selected=selected, step_id="trivy-sbom-dev", tool="trivy", argv=["sbom", "--format", "json", str(raw / "syft-dev.cdx.json")], stdout_output=raw / "trivy-sbom-dev.json")
        run_capture_step(run_dir, manifest, resume=resume, selected=selected, step_id="osv-source", tool="osv-scanner", argv=["scan", "source", "--format", "json", "--recursive", "."], stdout_output=raw / "osv-source.json")
        run_capture_step(run_dir, manifest, resume=resume, selected=selected, step_id="osv-sbom-dev", tool="osv-scanner", argv=["scan", "source", "--format", "json", "--lockfile", str(raw / "syft-dev.cdx.json")], stdout_output=raw / "osv-sbom-dev.json")
        run_capture_step(run_dir, manifest, resume=resume, selected=selected, step_id="grype-sbom-dev", tool="grype", argv=[f"sbom:{raw / 'syft-dev.cdx.json'}", "-o", "json"], stdout_output=raw / "grype-sbom-dev.json")

        worktree_report = raw / "gitleaks-worktree.json"
        run_capture_step(run_dir, manifest, resume=resume, selected=selected, step_id="gitleaks-worktree", tool="gitleaks", argv=["dir", "--redact=100", "--report-format", "json", "--report-path", str(worktree_report), "."], stdout_output=None, expected_output=worktree_report)
        if include_history:
            history_report = raw / "gitleaks-history.json"
            run_capture_step(run_dir, manifest, resume=resume, selected=selected, step_id="gitleaks-history", tool="gitleaks", argv=["git", "--redact=100", "--report-format", "json", "--report-path", str(history_report), "."], stdout_output=None, expected_output=history_report)
        if release_staging is not None:
            release_report = raw / "gitleaks-release.json"
            run_capture_step(run_dir, manifest, resume=resume, selected=selected, step_id="gitleaks-release", tool="gitleaks", argv=["dir", "--redact=100", "--report-format", "json", "--report-path", str(release_report), str(release_staging)], stdout_output=None, expected_output=release_report)

        semgrep_report = raw / "semgrep.json"
        run_capture_step(run_dir, manifest, resume=resume, selected=selected, step_id="semgrep", tool="semgrep", argv=["--metrics=off", "--config", "security/static-analysis/pocketlab-architecture.yml", "--json", "--output", str(semgrep_report), "."], stdout_output=None, expected_output=semgrep_report)

        scancode_targets = ["package.json", "requirements-dev.txt", "requirements-docs.txt", "pocket-lab-final-structure/runtime/requirements.txt", "operations", "runbooks", "scripts", "src"]
        scancode_targets = [x for x in scancode_targets if (ROOT / x).exists()]
        scancode_report = raw / "scancode.json"
        scancode_workers = scancode_processes()
        run_capture_step(
            run_dir,
            manifest,
            resume=resume,
            selected=selected,
            step_id="scancode",
            tool="scancode",
            argv=[
                "--license",
                "--package",
                "--copyright",
                "--processes",
                str(scancode_workers),
                "--json-pp",
                str(scancode_report),
                *scancode_targets,
            ],
            stdout_output=None,
            expected_output=scancode_report,
            scanner_config={
                "processes": scancode_workers,
                "process_policy": "bounded",
                "process_min": SCANCODE_MIN_PROCESSES,
                "process_max": SCANCODE_MAX_PROCESSES,
                "license_role": "optional-deep-source-enrichment",
            },
            required=False,
        )

        scorecard_repo = scorecard_repository_slug()
        scorecard_checks = ",".join(SCORECARD_COMPATIBLE_CHECKS)
        run_capture_step(
            run_dir,
            manifest,
            resume=resume,
            selected=selected,
            step_id="scorecard",
            tool="scorecard",
            argv=[
                "--repo",
                scorecard_repo,
                "--commit",
                str(identity["source_commit"]),
                "--format",
                "json",
                "--checks",
                scorecard_checks,
            ],
            stdout_output=raw / "scorecard.json",
            allow_nonzero=False,
            scanner_config={
                "mode": "github-repository",
                "repository": scorecard_repo,
                "source_commit": str(identity["source_commit"]),
                "compatible_checks": list(SCORECARD_COMPATIBLE_CHECKS),
                "provider_unavailable_checks": list(SCORECARD_PROVIDER_UNAVAILABLE_CHECKS),
                "provider_unavailable_reason": SCORECARD_PROVIDER_UNAVAILABLE_REASON,
                "authentication": "child-process-environment",
            },
            extra_env=scorecard_auth_env(),
        )
    finally:
        if release_holder is not None:
            release_holder.cleanup()

    # A focused --only run is intentionally diagnostic and never promotable until a
    # subsequent full --resume completes every step for the same source identity.
    completed = {item.get("step_id") for item in manifest.get("tools", []) if isinstance(item, dict) and item.get("status") in ACCEPTED_STEP_STATES}
    manifest["capture_complete"] = required_selection <= completed
    manifest["capture_scope"] = "full" if manifest["capture_complete"] else "partial-diagnostic"
    manifest["raw_files"] = [
        {"path": str(p.relative_to(run_dir)), "sha256": digest_file(p), "bytes": p.stat().st_size}
        for p in sorted(raw.glob("*")) if p.is_file()
    ]
    save_manifest(run_dir, manifest)
    if not manifest["capture_complete"]:
        print(f"PASS partial diagnostic capture checkpoint: {run_dir}")
        print("Run the same directory with --resume and no --only before promotion.")
        return 0
    print(f"PASS transient WSL2/CI supply-chain capture: {run_dir}")
    print("Raw scanner output remains transient and is not documentation truth. Run promote explicitly after review.")
    return 0


def capture_diagnostics(manifest: dict[str, Any]) -> dict[str, Any]:
    steps = []
    for item in manifest.get("tools", []):
        if not isinstance(item, dict):
            continue
        steps.append(
            {
                "step_id": item.get("step_id"),
                "tool": item.get("tool"),
                "status": item.get("status"),
                "exit_code": item.get("exit_code"),
                "duration_seconds": item.get("duration_seconds"),
                "output_validation": item.get("output_validation"),
                "attempt": item.get("attempt"),
                "scanner_config": item.get("scanner_config") if isinstance(item.get("scanner_config"), dict) else {},
                "required": bool(item.get("required", True)),
                "interruption_reason": item.get("interruption_reason"),
                "resource_guardrail_reason": item.get("resource_guardrail_reason"),
                "peak_family_rss_mib": round(int(item.get("peak_family_rss_bytes") or 0) / 1024**2, 1),
                "min_mem_available_mib": round(int(item.get("min_mem_available_bytes") or 0) / 1024**2, 1),
                "min_swap_free_mib": round(int(item.get("min_swap_free_bytes") or 0) / 1024**2, 1),
                "max_output_bytes": int(item.get("max_output_bytes") or 0),
            }
        )
    failure = manifest.get("failure") if isinstance(manifest.get("failure"), dict) else None
    return {
        "schema_version": "1.0.0",
        "run_id": manifest.get("run_id"),
        "source_commit": manifest.get("source_commit"),
        "qualification_surface": manifest.get("qualification_surface"),
        "capture_complete": bool(manifest.get("capture_complete")),
        "resume_count": int(manifest.get("resume_count") or 0),
        "max_parallel_scanners": manifest.get("max_parallel_scanners", 1),
        "steps": steps,
        "optional_failures": manifest.get("optional_failures", []),
        "license_authority": manifest.get("license_authority", {}),
        "failure": {
            "step_id": failure.get("step_id"),
            "status": failure.get("status"),
            "exit_code": failure.get("exit_code"),
        } if failure else None,
        "raw_scanner_output_included": False,
        "stderr_included": False,
        "command_arguments_included": False,
    }


def capture_status(run_dir: Path, *, json_output: Path | None = None) -> int:
    manifest = read_json(run_dir / "capture-manifest.json", {})
    if not manifest:
        fail("capture status requires a valid capture-manifest.json")
    reconcile_interrupted_steps(run_dir, manifest)
    diagnostics = capture_diagnostics(manifest)
    safe_text("capture diagnostics", stable(diagnostics))
    if json_output is not None:
        atomic_write_json(json_output, diagnostics)
    print(f"run_id={diagnostics.get('run_id')}")
    print(f"source_commit={diagnostics.get('source_commit')}")
    print(f"qualification_surface={diagnostics.get('qualification_surface')}")
    print(f"capture_complete={diagnostics.get('capture_complete')}")
    print(f"resume_count={diagnostics.get('resume_count', 0)}")
    for item in diagnostics.get("steps", []):
        print(
            f"{item.get('step_id','unknown'):22} "
            f"{item.get('status','unknown'):24} "
            f"exit={item.get('exit_code')} duration={item.get('duration_seconds')}s"
        )
    failure = diagnostics.get("failure")
    if isinstance(failure, dict):
        print(f"failure={failure.get('step_id')}:{failure.get('status')}")
    return 0

def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def normalized_component(item: dict[str, Any]) -> dict[str, Any] | None:
    name = str(sanitize_private_paths(str(item.get("name") or ""))).strip()
    version = str(sanitize_private_paths(str(item.get("version") or ""))).strip()
    if not name:
        return None
    licenses: list[dict[str, Any]] = []
    for entry in item.get("licenses") or []:
        if not isinstance(entry, dict):
            continue
        lic = entry.get("license") if isinstance(entry.get("license"), dict) else entry
        lid = lic.get("id") or lic.get("name") if isinstance(lic, dict) else None
        if lid:
            licenses.append({"license": {"id": str(lid)}})
    result = {"type": item.get("type") or "library", "name": name}
    if version:
        result["version"] = version
    if item.get("purl"):
        purl = str(item["purl"])
        # A package URL carrying a local filesystem root is host-specific and can
        # become syntactically invalid if the path is textually redacted.  Omit
        # that optional locator instead; package name/version remain canonical.
        if not PRIVATE.search(purl) and not SECRET.search(purl):
            result["purl"] = purl
    if licenses:
        result["licenses"] = licenses
    return result


def canonical_cdx(source: dict[str, Any] | None, *, target: str, evidence_status: str, source_digest: str | None, release_binding: str | None = None) -> dict[str, Any]:
    components: list[dict[str, Any]] = []
    if isinstance(source, dict):
        for item in source.get("components") or []:
            if isinstance(item, dict):
                normalized = normalized_component(item)
                if normalized:
                    components.append(normalized)
    components.sort(key=lambda x: (str(x.get("purl", "")), x["name"], str(x.get("version", ""))))
    dedup: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in components:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key); dedup.append(item)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {"type": "application", "name": f"pocket-lab-lite-{target}"},
            "properties": [
                {"name": "pocketlab:evidence-status", "value": evidence_status},
                {"name": "pocketlab:source-generator", "value": "Syft" if source else "Pocket Lab promoted runtime projection" if target == "runtime" else "missing"},
                {"name": "pocketlab:source-digest", "value": source_digest or "unavailable"},
                {"name": "pocketlab:sanitized", "value": "true"},
                {"name": "pocketlab:release-binding", "value": release_binding or "not-applicable"},
            ],
        },
        "components": dedup,
    }


def runtime_components() -> list[dict[str, Any]]:
    baseline = read_json(RUNTIME, {})
    found: dict[tuple[str, str], dict[str, Any]] = {}
    allowed_name_keys = {"name", "service", "component", "package", "tool", "app"}
    version_keys = {"version", "runtime_version", "app_version", "service_version"}
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            name = next((value.get(k) for k in allowed_name_keys if isinstance(value.get(k), str)), None)
            version = next((value.get(k) for k in version_keys if isinstance(value.get(k), (str, int, float))), None)
            if name and version:
                clean_name = re.sub(r"[^A-Za-z0-9_.+/-]", "-", str(name))[:120]
                clean_version = re.sub(r"[^A-Za-z0-9_.+~-]", "-", str(version))[:80]
                if clean_name and clean_version:
                    found[(clean_name, clean_version)] = {"type": "application", "name": clean_name, "version": clean_version}
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(baseline)
    return [found[k] for k in sorted(found)]


def vulnerabilities_from_trivy(data: Any) -> list[dict[str, Any]]:
    out=[]
    if not isinstance(data, dict): return out
    for result in data.get("Results") or []:
        if not isinstance(result, dict): continue
        for finding in result.get("Vulnerabilities") or []:
            if not isinstance(finding, dict): continue
            out.append({"id": finding.get("VulnerabilityID") or "unknown", "package": finding.get("PkgName") or "unknown", "installed": finding.get("InstalledVersion") or "unknown", "fixed": finding.get("FixedVersion") or None, "severity": finding.get("Severity") or "UNKNOWN", "source": "trivy"})
    return out


def vulnerabilities_from_grype(data: Any) -> list[dict[str, Any]]:
    out=[]
    if not isinstance(data, dict): return out
    for match in data.get("matches") or []:
        if not isinstance(match, dict): continue
        vuln=match.get("vulnerability") or {}; artifact=match.get("artifact") or {}
        out.append({"id": vuln.get("id") or "unknown", "package": artifact.get("name") or "unknown", "installed": artifact.get("version") or "unknown", "fixed": ",".join(vuln.get("fix",{}).get("versions") or []) or None, "severity": vuln.get("severity") or "UNKNOWN", "source": "grype"})
    return out


def vulnerabilities_from_osv(data: Any) -> list[dict[str, Any]]:
    out=[]
    if not isinstance(data, dict): return out
    for result in data.get("results") or []:
        if not isinstance(result, dict): continue
        packages = result.get("packages") or []
        for package in packages:
            if not isinstance(package, dict): continue
            pkg = package.get("package") if isinstance(package.get("package"), dict) else package
            name = pkg.get("name") or "unknown"
            version = pkg.get("version") or "unknown"
            for vuln in package.get("vulnerabilities") or []:
                if isinstance(vuln, dict):
                    out.append({"id": vuln.get("id") or "unknown", "package": name, "installed": version, "fixed": None, "severity": "UNRATED", "source": "osv-scanner"})
    return out


def correlate_vulnerabilities(raw: Path) -> dict[str, Any]:
    findings = (
        vulnerabilities_from_trivy(read_json(raw / "trivy-sbom-dev.json", {}))
        + vulnerabilities_from_grype(read_json(raw / "grype-sbom-dev.json", {}))
        + vulnerabilities_from_osv(read_json(raw / "osv-source.json", {}))
        + vulnerabilities_from_osv(read_json(raw / "osv-sbom-dev.json", {}))
    )
    grouped: dict[tuple[str,str], list[dict[str,Any]]] = defaultdict(list)
    for finding in findings:
        grouped[(str(finding["id"]), str(finding["package"]))].append(finding)
    items=[]
    for (vid,pkg), group in sorted(grouped.items()):
        sources=sorted({x["source"] for x in group})
        severities=sorted({str(x.get("severity") or "UNKNOWN") for x in group})
        items.append({"id":vid,"package":pkg,"sources":sources,"correlation":"corroborated" if len(sources)>1 else "single-source","severities":severities,"installed_versions":sorted({str(x.get("installed") or "unknown") for x in group}),"fixed_versions":sorted({str(x["fixed"]) for x in group if x.get("fixed")})})
    return {"schema_version":"1.0.0","evidence_status":"observed" if items else "no-findings-observed-or-no-tool-results","scanner_disagreement_is_failure":False,"items":items,"counts":{"unique_vulnerabilities":len(items),"corroborated":sum(1 for x in items if x["correlation"]=="corroborated"),"single_source":sum(1 for x in items if x["correlation"]=="single-source")}}


def classify_license_expression(expression: str) -> str:
    value = expression.upper().strip()
    if not value or value in {"UNKNOWN", "NOASSERTION", "NONE"}:
        return "unknown"
    strong = ("GPL-", "AGPL-", "SSPL-")
    weak = ("LGPL-", "MPL-", "EPL-", "CDDL-")
    permissive = ("MIT", "BSD", "APACHE-", "ISC", "ZLIB", "UNLICENSE", "0BSD", "BSL-1.0")
    if any(token in value for token in strong) and not any(token in value for token in weak):
        return "strong-copyleft"
    if any(token in value for token in weak):
        return "weak-copyleft"
    if any(token in value for token in permissive):
        return "permissive"
    return "manual-review"


def trivy_license_findings(data: Any) -> list[dict[str, Any]]:
    findings: Counter[tuple[str, str, str, str]] = Counter()
    if not isinstance(data, dict):
        return []
    for result in data.get("Results") or []:
        if not isinstance(result, dict):
            continue
        for item in result.get("Licenses") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("Name") or item.get("License") or "").strip()
            if not name:
                continue
            package = str(item.get("PkgName") or "unpackaged-or-file-level")
            category = str(item.get("Category") or "unknown")
            severity = str(item.get("Severity") or "UNKNOWN")
            findings[(name, package, category, severity)] += 1
    return [
        {
            "license": license_name,
            "package": package,
            "trivy_category": category,
            "severity": severity,
            "occurrences": count,
            "classification": classify_license_expression(license_name),
            "source": "trivy",
        }
        for (license_name, package, category, severity), count in sorted(findings.items())
    ]


def license_inventory(
    sbom: dict[str, Any],
    trivy: Any,
    scancode: Any,
    *,
    scancode_requested: bool,
    scancode_status: str | None,
) -> dict[str, Any]:
    rows=[]
    for comp in sbom.get("components") or []:
        licenses=[]
        for item in comp.get("licenses") or []:
            lic=item.get("license") if isinstance(item,dict) else None
            if isinstance(lic,dict) and (lic.get("id") or lic.get("name")): licenses.append(str(lic.get("id") or lic.get("name")))
        classifications=sorted({classify_license_expression(x) for x in licenses}) or ["unknown"]
        rows.append({"package":comp.get("name"),"version":comp.get("version"),"licenses":sorted(set(licenses)),"classification":classifications[0] if len(classifications)==1 else "manual-review","classification_evidence":classifications})
    detected=Counter()
    if isinstance(scancode,dict):
        for file in scancode.get("files") or []:
            if not isinstance(file,dict): continue
            for det in file.get("license_detections") or []:
                if isinstance(det,dict):
                    expr=det.get("license_expression") or det.get("license_expression_spdx")
                    if expr: detected[str(expr)] += 1
    detected_rows=[{"expression":k,"files":v,"classification":classify_license_expression(k)} for k,v in sorted(detected.items())]
    trivy_rows = trivy_license_findings(trivy)
    deep_observed = scancode_status in ACCEPTED_STEP_STATES and bool(scancode)
    if deep_observed:
        deep_status = "observed"
    elif scancode_requested:
        deep_status = "unavailable"
    else:
        deep_status = "not-run"
    return {
        "schema_version": "1.1.0",
        "implementation_status": "implemented",
        "classification_vocabulary": ["permissive", "weak-copyleft", "strong-copyleft", "unknown", "manual-review"],
        "package_license_coverage": {
            "status": "observed",
            "required": True,
            "authority": "syft+trivy",
            "sources": ["syft", "trivy"],
            "syft_component_count": len(rows),
            "trivy_license_scanner": "executed-standard",
            "trivy_license_finding_count": sum(int(item.get("occurrences") or 0) for item in trivy_rows),
            "note": "Trivy standard license scanning is required; zero license findings do not imply that every file contained recognizable license evidence.",
        },
        "deep_source_license_coverage": {
            "status": deep_status,
            "required": False,
            "provider": "scancode",
            "requested": scancode_requested,
            "provider_status": scancode_status or "not-run",
            "claim": "deep source-level license/copyright analysis was observed" if deep_observed else "deep source-level license/copyright analysis is not claimed",
        },
        "items": rows,
        "trivy_detected_licenses": trivy_rows,
        "scancode_detected_expressions": detected_rows if deep_observed else [],
        "policy": "Syft plus Trivy are the required package-license authority. ScanCode is optional deep-source enrichment; absence or failure never fabricates deep coverage and never blocks required qualification.",
    }


def scorecard_summary(data: Any) -> dict[str, Any]:
    observed_by_name: dict[str, dict[str, Any]] = {}
    if isinstance(data, dict):
        for item in data.get("checks") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "")
            if name not in SCORECARD_COMPATIBLE_CHECKS:
                continue
            observed_by_name[name] = {
                "name": name,
                "status": "observed",
                "score": item.get("score"),
                "reason": "recorded-by-scorecard",
                "provider": "openssf-scorecard",
            }
    checks: list[dict[str, Any]] = []
    for name in SCORECARD_COMPATIBLE_CHECKS:
        checks.append(
            observed_by_name.get(
                name,
                {
                    "name": name,
                    "status": "unobserved",
                    "score": None,
                    "reason": "scorecard-compatible-check-not-returned",
                    "provider": "openssf-scorecard",
                },
            )
        )
    for name in SCORECARD_PROVIDER_UNAVAILABLE_CHECKS:
        checks.append(
            {
                "name": name,
                "status": "provider-unavailable",
                "score": None,
                "reason": SCORECARD_PROVIDER_UNAVAILABLE_REASON,
                "provider": "openssf-scorecard",
                "blocking": False,
                "claim": "control posture is not inferred from unavailable Scorecard evidence",
            }
        )
    compatible_observed = all(
        observed_by_name.get(name, {}).get("status") == "observed"
        for name in SCORECARD_COMPATIBLE_CHECKS
    )
    return {
        "schema_version": "1.1.0",
        "status": "observed-with-provider-limitations" if compatible_observed else "partial",
        "provider": "openssf-scorecard",
        "provider_mode": "github-repository",
        "compatible_checks": list(SCORECARD_COMPATIBLE_CHECKS),
        "provider_unavailable_checks": list(SCORECARD_PROVIDER_UNAVAILABLE_CHECKS),
        "provider_unavailable_reason": SCORECARD_PROVIDER_UNAVAILABLE_REASON,
        "checks": sorted(checks, key=lambda item: str(item["name"])),
        "policy": (
            "Compatible Scorecard repository checks are required evidence. Provider-unavailable checks remain "
            "first-class controls but are non-blocking and never receive fabricated scores or pass claims."
        ),
    }


def security_summary(raw: Path) -> dict[str, Any]:
    gitleaks_reports = []
    for report in sorted(raw.glob("gitleaks-*.json")):
        data = read_json(report, [])
        if isinstance(data, list):
            gitleaks_reports.extend(data)
    semgrep=read_json(raw/"semgrep.json",{}); trivy=read_json(raw/"trivy-source.json",{})
    trivy_counts=Counter()
    if isinstance(trivy,dict):
        for result in trivy.get("Results") or []:
            if not isinstance(result,dict): continue
            for f in result.get("Vulnerabilities") or []:
                if isinstance(f,dict): trivy_counts[str(f.get("Severity") or "UNKNOWN")]+=1
            for key in ("Misconfigurations","Secrets"):
                if isinstance(result.get(key),list): trivy_counts[key.lower()]+=len(result[key])
    return {"schema_version":"1.0.0","raw_findings_included":False,"gitleaks":{"finding_count":len(gitleaks_reports),"redacted":True,"coverage":[p.name for p in sorted(raw.glob("gitleaks-*.json"))]},"semgrep":{"finding_count":len(semgrep.get("results") or []) if isinstance(semgrep,dict) else 0,"rule_ids":sorted({str(x.get("check_id")) for x in (semgrep.get("results") or []) if isinstance(x,dict) and x.get("check_id")})},"trivy":{"counts":dict(sorted(trivy_counts.items()))}}


def write_canonical(path: Path, payload: Any) -> None:
    payload = sanitize_private_paths(payload)
    text=stable(payload)
    safe_text(str(path.relative_to(ROOT)),text)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=f".{path.name}.",dir=path.parent)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def promote(run_dir: Path, *, require_release_qualification: bool = False) -> int:
    if is_termux(): fail("supply-chain promotion is a developer/CI operation, not a Termux operation",3)
    raw=run_dir/"raw"; manifest=read_json(run_dir/"capture-manifest.json",{})
    if not raw.is_dir() or not manifest: fail("run directory has no valid transient capture manifest")
    if manifest.get("schema_version") != CAPTURE_SCHEMA_VERSION: fail("capture manifest schema is not promotable")
    if manifest.get("runtime_capture_performed") is not False: fail("capture manifest violates the no-live-runtime rule")
    if manifest.get("capture_complete") is not True: fail("partial/incomplete capture cannot be promoted; resume the run first")
    if require_release_qualification and manifest.get("qualification_surface") != "github-actions-release":
        fail("release qualification promotion requires a GitHub Actions release capture", 3)
    dev_raw=raw/"syft-dev.cdx.json"; release_raw=raw/"syft-release.cdx.json"
    if not dev_raw.exists(): fail("Syft development CycloneDX output is required before promotion")
    dev_source=read_json(dev_raw,{})
    release_manifest=read_json(ROOT/"pocketlab-lite-release.json",{}) or {}
    release_binding=str(release_manifest.get("release_tag") or "unobserved") if release_manifest else None
    dev=canonical_cdx(dev_source,target="development",evidence_status="observed-syft",source_digest=digest_file(dev_raw))
    if release_raw.exists():
        release=canonical_cdx(read_json(release_raw,{}),target="release",evidence_status="observed-syft",source_digest=digest_file(release_raw),release_binding=release_binding)
    else:
        release=canonical_cdx(None,target="release",evidence_status="missing-dist.zip-at-capture",source_digest=None,release_binding=release_binding)
    runtime_baseline=read_json(RUNTIME,{}) or {}
    runtime_binding=str(runtime_baseline.get("release_tag") or runtime_baseline.get("release") or "unobserved") if runtime_baseline else None
    runtime=canonical_cdx(None,target="runtime",evidence_status="release-promoted-runtime-baseline" if RUNTIME.exists() else "missing-promoted-runtime-baseline",source_digest=digest_file(RUNTIME) if RUNTIME.exists() else None,release_binding=runtime_binding)
    runtime["components"]=runtime_components()
    vuln=correlate_vulnerabilities(raw)
    scancode_step = manifest_step(manifest, "scancode")
    scancode_status = str(scancode_step.get("status")) if isinstance(scancode_step, dict) else None
    licenses=license_inventory(
        dev,
        read_json(raw/"trivy-source.json",{}),
        read_json(raw/"scancode.json",{}),
        scancode_requested=bool(manifest.get("scancode_requested")),
        scancode_status=scancode_status,
    )
    security=security_summary(raw)
    scorecard=scorecard_summary(read_json(raw/"scorecard.json",{}))
    summary={"schema_version":"1.2.0","implementation_status":"implemented","run_id":run_dir.name,"source_commit":manifest.get("source_commit"),"qualification_surface":manifest.get("qualification_surface"),"release_qualification":bool(manifest.get("release_qualification")),"capture_complete":True,"max_parallel_scanners":manifest.get("max_parallel_scanners",1),"capture_manifest_sha256":digest_file(run_dir/"capture-manifest.json"),"raw_output_canonical":False,"runtime_capture_performed":False,"runtime_source":"contracts/parity/runtime-verification-baseline.json","license_authority":{"package_license_coverage":licenses.get("package_license_coverage"),"deep_source_license_coverage":licenses.get("deep_source_license_coverage")},"artifacts":{},"tool_statuses":[{"step_id":x.get("step_id"),"tool":x.get("tool"),"status":x.get("status"),"exit_code":x.get("exit_code"),"duration_seconds":x.get("duration_seconds")} for x in manifest.get("tools",[]) if isinstance(x,dict)]}
    payloads={CANONICAL_FILES["sbom_dev"]:dev,CANONICAL_FILES["sbom_release"]:release,CANONICAL_FILES["sbom_runtime"]:runtime,CANONICAL_FILES["vulnerabilities"]:vuln,CANONICAL_FILES["licenses"]:licenses,CANONICAL_FILES["security"]:security,CANONICAL_FILES["scorecard"]:scorecard}
    for name,payload in payloads.items():
        write_canonical(OUT/name,payload); summary["artifacts"][name]=digest_file(OUT/name)
    write_canonical(OUT/CANONICAL_FILES["summary"],summary)
    print(f"PASS promoted sanitized supply-chain evidence from {run_dir.name}")
    print("No live runtime capture or runtime promotion was performed.")
    return 0


def check() -> int:
    missing=[name for name in CANONICAL_FILES.values() if not (OUT/name).exists()]
    if missing:
        fail("canonical supply-chain artifacts missing: "+", ".join(missing))
    for name in CANONICAL_FILES.values():
        path=OUT/name; data=read_json(path,None)
        if data is None: fail(f"invalid JSON: {path.relative_to(ROOT)}")
        safe_text(str(path.relative_to(ROOT)),stable(data))
    for key in ("sbom-dev.cdx.json","sbom-release.cdx.json","sbom-runtime.cdx.json"):
        data=read_json(OUT/key,{})
        if data.get("bomFormat")!="CycloneDX" or data.get("specVersion")!="1.6" or not isinstance(data.get("components"),list):
            fail(f"{key} is not a canonical CycloneDX 1.6 JSON document")
    licenses = read_json(OUT / "license-inventory.json", {})
    package_coverage = licenses.get("package_license_coverage") if isinstance(licenses, dict) else None
    deep_coverage = licenses.get("deep_source_license_coverage") if isinstance(licenses, dict) else None
    if isinstance(package_coverage, dict) or isinstance(deep_coverage, dict):
        if not isinstance(package_coverage, dict) or package_coverage.get("required") is not True:
            fail("license-inventory.json must declare required package-license coverage")
        if package_coverage.get("status") != "observed" or package_coverage.get("authority") != "syft+trivy":
            fail("license-inventory.json package-license authority must be observed Syft+Trivy evidence")
        if not isinstance(deep_coverage, dict) or deep_coverage.get("required") is not False:
            fail("license-inventory.json must represent deep-source license analysis as optional")
        if deep_coverage.get("status") == "observed" and deep_coverage.get("provider") != "scancode":
            fail("observed deep-source license coverage must name its provider")
    elif str(licenses.get("schema_version") or "") != "1.0.0":
        fail("license-inventory.json has neither the decoupled coverage contract nor the supported legacy schema")
    else:
        print("WARN legacy license-inventory.json schema; next explicit promotion will add decoupled package/deep-source coverage")

    scorecard = read_json(OUT / "scorecard-checks.json", {})
    if str(scorecard.get("schema_version") or "") == "1.1.0":
        checks = {
            str(item.get("name")): item
            for item in scorecard.get("checks") or []
            if isinstance(item, dict) and item.get("name")
        }
        for name in SCORECARD_COMPATIBLE_CHECKS:
            item = checks.get(name)
            if not isinstance(item, dict) or item.get("status") != "observed":
                fail(f"scorecard-checks.json must contain observed compatible check: {name}")
        for name in SCORECARD_PROVIDER_UNAVAILABLE_CHECKS:
            item = checks.get(name)
            if not isinstance(item, dict):
                fail(f"scorecard-checks.json must retain provider-unavailable control: {name}")
            if item.get("status") != "provider-unavailable" or item.get("score") is not None:
                fail(f"scorecard-checks.json must not fabricate a score for provider-unavailable control: {name}")
            if item.get("blocking") is not False or item.get("reason") != SCORECARD_PROVIDER_UNAVAILABLE_REASON:
                fail(f"scorecard-checks.json provider-unavailable contract is invalid for: {name}")
    elif str(scorecard.get("schema_version") or "") != "1.0.0":
        fail("scorecard-checks.json has neither the provider-limitation contract nor the supported legacy schema")
    else:
        print("WARN legacy scorecard-checks.json schema; next explicit promotion will add provider-limitation evidence")

    release_manifest=read_json(ROOT/"pocketlab-lite-release.json",{}) or {}
    if release_manifest.get("release_tag"):
        release=read_json(OUT/"sbom-release.cdx.json",{})
        props={x.get("name"):x.get("value") for x in ((release.get("metadata") or {}).get("properties") or []) if isinstance(x,dict)}
        if props.get("pocketlab:release-binding") != str(release_manifest["release_tag"]):
            fail("sbom-release.cdx.json release binding does not match pocketlab-lite-release.json")
    print("PASS canonical supply-chain evidence is present, sanitized, release-bound where applicable, and CycloneDX 1.6-backed")
    return 0


def dependency_track_export(destination: Path) -> int:
    destination.mkdir(parents=True,exist_ok=True)
    for name in ("sbom-dev.cdx.json","sbom-release.cdx.json","sbom-runtime.cdx.json"):
        src=OUT/name
        if not src.exists(): fail(f"run supply-chain promotion first; missing {name}")
        shutil.copy2(src,destination/name)
    (destination/"README.txt").write_text("These CycloneDX files may be imported into an optional Dependency-Track instance. Pocket Lab documentation never depends on a live Dependency-Track service.\n",encoding="utf-8")
    print(f"PASS Dependency-Track import bundle staged at {destination}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("capture")
    p.add_argument("--run-dir")
    p.add_argument("--include-git-history", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--only", help="Comma-separated scanner aliases or step IDs for focused diagnostics")
    p.add_argument("--release-qualification", action="store_true", help="Require clean GitHub Actions release-qualification context")
    p.add_argument("--enable-scancode", action="store_true", help="Opt into optional deep source-license/copyright analysis; local execution also requires POCKETLAB_ALLOW_LOCAL_SCANCODE=1")
    p = sub.add_parser("status")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--json-output")
    p = sub.add_parser("promote")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--require-release-qualification", action="store_true")
    sub.add_parser("check")
    p = sub.add_parser("dependency-track-export")
    p.add_argument("--output", default=str(ROOT / ".pocketlab-dev/documentation-security/dependency-track-import"))
    args = ap.parse_args()
    if args.mode == "capture":
        return capture(
            Path(args.run_dir).resolve() if args.run_dir else new_run_dir(),
            args.include_git_history,
            resume=args.resume,
            only=args.only,
            release_qualification=args.release_qualification,
            enable_scancode=args.enable_scancode,
        )
    if args.mode == "status":
        return capture_status(
            Path(args.run_dir).resolve(),
            json_output=Path(args.json_output).resolve() if args.json_output else None,
        )
    if args.mode == "promote":
        return promote(Path(args.run_dir).resolve(), require_release_qualification=args.require_release_qualification)
    if args.mode == "check":
        return check()
    if args.mode == "dependency-track-export":
        return dependency_track_export(Path(args.output).resolve())
    return 2

if __name__=="__main__": raise SystemExit(main())
