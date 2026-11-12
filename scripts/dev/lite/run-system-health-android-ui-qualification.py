#!/usr/bin/env python3
"""Run the narrow physical Android System Health UI-to-candidate qualifier.

The existing System Health Android lane proves the exact candidate API with an
isolated phone-side runtime.  This companion lane keeps that runtime alive,
serves the exact frontend through the checked-in candidate server, and lets
Android Chrome consume it through the existing standard-user CDP relay.  The
candidate server forwards only loopback HTTPS API traffic and the diagnosis
write; repair and preflight writes remain blocked.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from urllib import request as urllib_request
from urllib.error import HTTPError, URLError


REPO_ROOT = Path(__file__).resolve().parents[3]
HEALTH_SCRIPT = Path(__file__).with_name("run-system-health-android-qualification.py")
CANDIDATE_SERVER = Path(__file__).with_name("ui_performance_candidate_server.py")
UI_QUALIFIER = Path(__file__).with_name("qualify-system-health-android-ui.mjs")
ANDROID_CANDIDATE_HELPER = Path(__file__).with_name("prepare-ui-performance-android-candidate.ps1")
WSL_RELAY = Path(__file__).with_name("wsl-cdp-reverse-relay.py")
WINDOWS_RELAY = Path(__file__).with_name("windows-cdp-wsl-relay.ps1")
CDP_LOCAL_URL = "http://127.0.0.1:19222"
CANDIDATE_URL = "http://127.0.0.1:18765"


def _load_health_module():
    spec = importlib.util.spec_from_file_location("pocketlab_system_health_android", HEALTH_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("System Health Android qualifier could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


health = _load_health_module()


def _safe_text(value: object, limit: int = 320) -> str:
    return str(value or "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _run(argv: list[str], *, timeout: float = 30.0, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(REPO_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _json_url(url: str, *, timeout: float = 5.0) -> dict:
    try:
        with urllib_request.urlopen(url, timeout=timeout) as response:
            raw = response.read(128 * 1024)
    except (OSError, HTTPError, URLError) as exc:
        raise health.QualificationError(f"qualification endpoint unavailable: {type(exc).__name__}") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise health.QualificationError("qualification endpoint returned malformed JSON") from exc
    if not isinstance(payload, dict):
        raise health.QualificationError("qualification endpoint returned a non-object")
    return payload


def _windows_cdp_probe() -> dict[str, str]:
    """Check the Windows-local endpoint before starting any relay."""
    command = (
        '$ErrorActionPreference="Stop"; '
        '$p=Invoke-RestMethod -Uri "http://127.0.0.1:9222/json/version" -TimeoutSec 5; '
        'if ($p."Android-Package" -ne "com.android.chrome") { throw "not Android Chrome" }; '
        'if ($p."Protocol-Version" -ne "1.3") { throw "unexpected CDP protocol" }; '
        '[pscustomobject]@{Browser=$p.Browser;ProtocolVersion=$p."Protocol-Version";AndroidPackage=$p."Android-Package";WebSocketPath="/devtools/browser"} | ConvertTo-Json -Compress'
    )
    result = _run(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command], timeout=15)
    if result.returncode != 0:
        raise health.QualificationError("Windows standard-user Android Chrome CDP preflight failed")
    try:
        payload = json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise health.QualificationError("Windows Android Chrome CDP preflight was malformed") from exc
    if payload.get("AndroidPackage") != "com.android.chrome" or payload.get("ProtocolVersion") != "1.3":
        raise health.QualificationError("Windows CDP endpoint is not the expected Android Chrome Protocol 1.3 target")
    return {key: _safe_text(value, 128) for key, value in payload.items() if key in {"Browser", "ProtocolVersion", "AndroidPackage", "WebSocketPath"}}


def _private_wsl_ip() -> str:
    host = _run(["ip", "route"], timeout=5).stdout
    windows_host = next((line.split()[2] for line in host.splitlines() if line.startswith("default ") and len(line.split()) > 2), "")
    if not windows_host:
        raise health.QualificationError("Windows WSL gateway could not be identified")
    result = _run(["ip", "-4", "route", "get", windows_host], timeout=5)
    fields = result.stdout.split()
    try:
        wsl_ip = fields[fields.index("src") + 1]
    except (ValueError, IndexError) as exc:
        raise health.QualificationError("private WSL relay address could not be identified") from exc
    if not wsl_ip.startswith("172.19."):
        raise health.QualificationError("CDP relay address was not on the private WSL interface")
    return wsl_ip


def _local_cdp_probe() -> dict[str, str] | None:
    try:
        payload = _json_url(f"{CDP_LOCAL_URL}/json/version", timeout=2)
    except health.QualificationError:
        return None
    websocket = str(payload.get("webSocketDebuggerUrl") or "")
    if payload.get("Android-Package") != "com.android.chrome" or payload.get("Protocol-Version") != "1.3":
        raise health.QualificationError("WSL CDP relay exposed a non-Android-Chrome target")
    if websocket and not websocket.startswith("ws://127.0.0.1:19222/"):
        raise health.QualificationError("WSL CDP relay websocket was not looped back on port 19222")
    return {"browser": _safe_text(payload.get("Browser"), 128), "protocol_version": "1.3", "package": "com.android.chrome", "websocket_loopback": True}


class StandardUserCdpRelay:
    def __init__(self, evidence_dir: Path):
        self.evidence_dir = evidence_dir
        self.wsl_process: subprocess.Popen[str] | None = None
        self.windows_process: subprocess.Popen[str] | None = None
        self.owned = False
        self.metadata: dict[str, str] = {}

    def start(self) -> dict[str, str]:
        windows = _windows_cdp_probe()
        existing = _local_cdp_probe()
        if existing:
            self.metadata = {**windows, **existing, "relay_owned": "false", "standard_user": "true"}
            return self.metadata
        wsl_ip = _private_wsl_ip()
        wsl_log = (self.evidence_dir / "cdp-wsl-relay.log").open("w", encoding="utf-8")
        windows_log = (self.evidence_dir / "cdp-windows-relay.log").open("w", encoding="utf-8")
        self.wsl_process = subprocess.Popen(
            [sys.executable, str(WSL_RELAY), "--listen-host", wsl_ip],
            cwd=str(REPO_ROOT), stdin=subprocess.DEVNULL, stdout=wsl_log, stderr=subprocess.STDOUT,
            text=True, start_new_session=True,
        )
        self.windows_process = subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(WINDOWS_RELAY), "-WslAddress", wsl_ip],
            cwd=str(REPO_ROOT), stdin=subprocess.DEVNULL, stdout=windows_log, stderr=subprocess.STDOUT,
            text=True, start_new_session=True,
        )
        self.owned = True
        for _ in range(40):
            current = _local_cdp_probe()
            if current:
                self.metadata = {**windows, **current, "relay_owned": "true", "standard_user": "true"}
                return self.metadata
            if self.wsl_process.poll() is not None or self.windows_process.poll() is not None:
                raise health.QualificationError("standard-user WSL CDP relay exited before readiness")
            time.sleep(0.25)
        raise health.QualificationError("standard-user WSL CDP relay did not expose Android Chrome")

    def stop(self) -> None:
        if not self.owned:
            return
        for process in (self.windows_process, self.wsl_process):
            if process is None or process.poll() is not None:
                continue
            with contextlib.suppress(OSError):
                process.terminate()
            with contextlib.suppress(subprocess.TimeoutExpired, OSError):
                process.wait(timeout=3)


def _candidate_server(run: health.SystemHealthAndroidQualification, dist_dir: Path, output_dir: Path) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env.update({
        "POCKETLAB_CANDIDATE_API_LOCAL_PORT": str(run.local_api_port),
        "POCKETLAB_CANDIDATE_API_SCHEME": "https",
        "POCKETLAB_CANDIDATE_API_CA_FILE": str(run.ca_path),
        "LITE_PERF_SOURCE_COMMIT": run.candidate_sha,
    })
    log = (output_dir / "candidate-server.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(CANDIDATE_SERVER), "--candidate-api", "--dist-dir", str(dist_dir), "--source-commit", run.candidate_sha],
        cwd=str(REPO_ROOT), env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
        text=True, start_new_session=True,
    )
    for _ in range(120):
        try:
            manifest = _json_url(f"{CANDIDATE_URL}/__pocketlab_qualification__/candidate.json", timeout=2)
            if manifest.get("source_commit") == run.candidate_sha and manifest.get("runtime_transport") == "ssh_loopback_to_isolated_phone_candidate":
                return process
        except health.QualificationError:
            pass
        if process.poll() is not None:
            raise health.QualificationError("isolated candidate static server exited before readiness")
        time.sleep(0.25)
    raise health.QualificationError("isolated candidate static server did not become ready")


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    with contextlib.suppress(OSError):
        process.send_signal(signal.SIGTERM)
    with contextlib.suppress(subprocess.TimeoutExpired, OSError):
        process.wait(timeout=5)
    if process.poll() is None:
        with contextlib.suppress(OSError):
            process.kill()


def _prepare_android_candidate(device_serial: str) -> None:
    result = _run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(ANDROID_CANDIDATE_HELPER), "-DeviceSerial", device_serial, "-OpenCandidate"],
        timeout=30,
    )
    if result.returncode != 0:
        raise health.QualificationError("Android candidate reverse preparation failed")


def _candidate_state_exists() -> bool:
    result = _run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command",
            '$path=Join-Path $env:LOCALAPPDATA "PocketLab\\ui-performance-android-candidate.json"; Test-Path $path -PathType Leaf',
        ],
        timeout=15,
    )
    return result.returncode == 0 and result.stdout.strip().casefold() == "true"


def _cleanup_android_candidate() -> None:
    _run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(ANDROID_CANDIDATE_HELPER), "-Cleanup"],
        timeout=30,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--base-sha", default="origin/main")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--nats-server-bin", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--dist-dir", type=Path, default=REPO_ROOT / "dist")
    parser.add_argument("--device-serial", required=True, help="Explicit Windows ADB serial selected by the operator")
    args = parser.parse_args(argv)
    base_result = _run(["git", "rev-parse", "--verify", f"{args.base_sha}^{{commit}}"], timeout=15)
    if base_result.returncode != 0:
        print(json.dumps({"status": "BLOCKED", "reason": "base SHA could not be resolved", "sanitized": True}, sort_keys=True))
        return 2
    base_sha = base_result.stdout.strip().casefold()
    evidence_dir = (args.evidence_dir or (REPO_ROOT / ".pocketlab-dev" / "validation")) / f"pr649-system-health-android-ui-{str(args.candidate_sha)[:12]}"
    evidence_dir = evidence_dir.absolute()
    evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not args.dist_dir.is_dir() or not (args.dist_dir / "index.html").is_file():
        print(json.dumps({"status": "BLOCKED", "reason": "candidate dist is unavailable", "sanitized": True}, sort_keys=True))
        return 2

    run = health.SystemHealthAndroidQualification(
        repo=REPO_ROOT, candidate_sha=args.candidate_sha, base_sha=base_sha, python=args.python,
        nats_binary=args.nats_server_bin, evidence_dir=evidence_dir, browser_ui=True,
    )
    candidate_server: subprocess.Popen[str] | None = None
    relay = StandardUserCdpRelay(evidence_dir)
    candidate_owned = False
    status = "BLOCKED"
    failure = ""
    ui_evidence: dict = {}
    try:
        if run.base_sha == run.candidate_sha:
            raise health.QualificationError("base and candidate SHA must differ for rollback proof")
        run._discover_remote()
        run._local_fixture()
        run._start_local_nats()
        run._stage_remote()
        before = run._remote_probe(expected=42)
        run.results.setdefault("isolated_sqlite", {})["phone_before_migration"] = before
        run._start_transport_and_candidate()
        after = run._remote_probe(expected=44)
        if after.get("marker_revision") != 7 or after.get("status") != "PASS":
            raise health.QualificationError("phone candidate migration did not preserve the isolated fixture")
        run.results.setdefault("isolated_sqlite", {})["phone_after_migration"] = after
        run._run_projection_driver()
        run._bootstrap()
        run._qualify_api()
        run._concurrency()
        run._measure()

        candidate_server = _candidate_server(run, args.dist_dir.absolute(), evidence_dir)
        if _candidate_state_exists():
            raise health.QualificationError("an existing Android candidate reverse is owned by another session")
        # The state file check above establishes that the following helper
        # invocation is ours to clean up, even if it fails after creating the
        # reverse mapping.
        candidate_owned = True
        _prepare_android_candidate(args.device_serial)
        cdp = relay.start()
        run.results["android_cdp"] = {
            "status": "PASS", "standard_user": True, "windows_probe": cdp,
            "device_selection": "explicit_windows_adb_serial_verified", "source_serial_published": False,
        }
        node = shutil.which("node")
        if not node:
            raise health.QualificationError("repository Node.js toolchain is unavailable")
        node_env = os.environ.copy()
        node_env.update({
            "LITE_ANDROID_CDP_URL": CDP_LOCAL_URL, "LITE_BASE_URL": CANDIDATE_URL,
            "LITE_PERF_SOURCE_COMMIT": run.candidate_sha,
            "POCKETLAB_HARNESS_BROWSER_BRIDGE": run.browser_bridge,
            "LITE_SYSTEM_HEALTH_ANDROID_OUTPUT_DIR": str(evidence_dir),
        })
        node_result = _run([node, str(UI_QUALIFIER)], timeout=180, env=node_env)
        (evidence_dir / "ui-qualifier.log").write_text(_safe_text(node_result.stdout, 6000) + "\n" + _safe_text(node_result.stderr, 6000) + "\n", encoding="utf-8")
        if node_result.returncode != 0:
            raise health.QualificationError("physical Android System Health UI qualifier failed")
        ui_json = evidence_dir / f"pr649-system-health-android-ui-{run.candidate_sha[:12]}.json"
        if not ui_json.is_file():
            raise health.QualificationError("physical Android UI evidence was not written")
        ui_evidence = json.loads(ui_json.read_text(encoding="utf-8"))
        if ui_evidence.get("status") != "PASS" or ui_evidence.get("candidate_sha") != run.candidate_sha:
            raise health.QualificationError("physical Android UI evidence was not exact-SHA bound")
        run.results["android_system_health_ui"] = ui_evidence
        repeat = run._remote_probe(expected=44)
        run.results.setdefault("isolated_sqlite", {})["after_ui_gets"] = repeat
        run.results["status"] = "PASS"
        status = "PASS"
    except health.QualificationError as exc:
        failure = _safe_text(exc)
        run.results["failure"] = {"type": "qualification", "message": failure, "sanitized": True}
    except Exception as exc:  # pragma: no cover - bounded command wrapper
        failure = f"{type(exc).__name__}: {_safe_text(exc)}"
        run.results["failure"] = {"type": type(exc).__name__, "message": _safe_text(exc), "sanitized": True}
    finally:
        _stop_process(candidate_server)
        relay.stop()
        if candidate_owned:
            _cleanup_android_candidate()
        run._cleanup()
        run.results["finished_at"] = health._now()
        run.results["status"] = status
        final = evidence_dir / f"pr649-system-health-android-ui-final-{run.candidate_sha[:12]}.json"
        final.write_text(json.dumps(health.sanitize(run.results), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        final.chmod(0o600)
    print(json.dumps({"status": status, "candidate_sha": run.candidate_sha, "base_sha": base_sha, "evidence": str(final), "failure": failure}, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
