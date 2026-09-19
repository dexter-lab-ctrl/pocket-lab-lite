#!/usr/bin/env python3
"""Pocket Lab Lite desired-state runtime reconciler.

The reconciler is intentionally narrower than bootstrap:
- it never installs packages, upgrades binaries, initializes databases, or
  downloads applications;
- it reconstructs missing Lite PM2 definitions through the repository-owned
  reconcile script;
- it records sanitized evidence and uses a bounded repair budget;
- transient network loss is evidence, not a reason to restart the control plane.

PM2 itself is supervised outside PM2 by the Termux boot/runtime guardian.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any, Iterable

from pocketlab_runtime_registry import (
    CONTROL_PLANE_SERVICES,
    LEGACY_LITE_SERVICES,
    REPAIRABLE_PM2_STATUSES,
)

_STOP = False
VERSION = "1.0.0-lite-desired-state"
DEFAULT_INTERVAL_SECONDS = 45
DEFAULT_COOLDOWN_SECONDS = 120
DEFAULT_WINDOW_SECONDS = 1800
DEFAULT_MAX_REPAIRS = 3


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _run(args: list[str], timeout: float = 15.0, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout, env=env)


def load_pm2_processes() -> list[dict[str, Any]]:
    try:
        result = _run(["pm2", "jlist"], timeout=10)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        payload = json.loads(result.stdout)
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def pm2_statuses(processes: Iterable[dict[str, Any]]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in processes:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
        values[name] = str(env.get("status") or item.get("status") or "unknown").strip().lower()
    return values


def repair_reasons(statuses: dict[str, str]) -> list[str]:
    """Return only reconstruction-class drift.

    Health-level recovery remains owned by the existing core supervisor. This
    avoids a second restart loop and intentionally ignores transient states such
    as "waiting restart" when the process definition still exists.
    """
    reasons: list[str] = []
    for spec in CONTROL_PLANE_SERVICES:
        status = str(statuses.get(spec.name) or "missing").lower()
        if status in REPAIRABLE_PM2_STATUSES:
            reasons.append(f"pm2_definition_or_process:{spec.name}:{status}")
    return reasons


def tailscale_state() -> dict[str, bool]:
    cli = ""
    for candidate in ("tailscale-cli", "tailscale"):
        try:
            if _run(["sh", "-lc", f"command -v {candidate}"], timeout=3).returncode == 0:
                cli = candidate
                break
        except Exception:
            pass
    daemon_running = False
    try:
        daemon_running = _run(["sh", "-lc", "pgrep -f tailscaled >/dev/null 2>&1"], timeout=3).returncode == 0
    except Exception:
        daemon_running = False

    ipv4_ready = False
    if daemon_running and cli:
        try:
            result = _run([cli, "ip", "-4"], timeout=5)
            ipv4_ready = result.returncode == 0 and bool(result.stdout.strip())
        except Exception:
            ipv4_ready = False
    return {
        "installed": bool(cli),
        "daemon_running": daemon_running,
        "ipv4_ready": ipv4_ready,
    }


def remote_reconcile_reasons(current: dict[str, bool], previous: dict[str, Any] | None) -> list[str]:
    """Distinguish network loss from repairable remote-access drift.

    A running Tailscale daemon with no current IPv4 may simply reflect Wi-Fi or
    upstream loss. That state is observable but must not restart Pocket Lab.
    """
    reasons: list[str] = []
    if current.get("installed") and not current.get("daemon_running"):
        reasons.append("tailscaled_missing")
        return reasons
    prior = previous if isinstance(previous, dict) else {}
    if (
        current.get("daemon_running")
        and current.get("ipv4_ready")
        and prior.get("ipv4_ready") is False
    ):
        reasons.append("tailscale_ready_transition")
    return reasons


def photoprism_expected() -> bool:
    root = Path(os.environ.get("POCKETLAB_PHOTOPRISM_ROOT", Path.home() / ".pocket_lab/lite/apps/photoprism")).expanduser()
    return (root / "config" / "photoprism.env").is_file() or (root / "config" / "install-manifest.json").is_file()


def proot_ubuntu_ready() -> bool:
    try:
        return _run(["proot-distro", "login", "ubuntu", "--", "true"], timeout=8).returncode == 0
    except Exception:
        return False


def photoprism_reconcile_reasons(statuses: dict[str, str]) -> list[str]:
    if not photoprism_expected():
        return []
    if not proot_ubuntu_ready():
        return ["proot_ubuntu_unavailable"]
    status = str(statuses.get("pocketlab-app-photoprism") or "missing").lower()
    if status in REPAIRABLE_PM2_STATUSES:
        return [f"photoprism_process:{status}"]
    return []


class RuntimeReconciler:
    def __init__(self) -> None:
        self.interval = max(10, int(os.environ.get("POCKETLAB_RUNTIME_RECONCILE_SECONDS", DEFAULT_INTERVAL_SECONDS)))
        self.cooldown = max(30, int(os.environ.get("POCKETLAB_RUNTIME_RECONCILE_COOLDOWN_SECONDS", DEFAULT_COOLDOWN_SECONDS)))
        self.window = max(300, int(os.environ.get("POCKETLAB_RUNTIME_RECONCILE_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS)))
        self.max_repairs = max(1, min(10, int(os.environ.get("POCKETLAB_RUNTIME_RECONCILE_MAX_REPAIRS", DEFAULT_MAX_REPAIRS))))
        base = Path(os.environ.get("POCKETLAB_STATE_DIR", Path.home() / "pocket-lab-lite" / "state")).expanduser()
        self.state_dir = base / "runtime-reconciler"
        self.state_file = self.state_dir / "state.json"
        self.events_file = self.state_dir / "events.jsonl"
        self.repair_history: list[float] = []
        self.last_repair_at = 0.0
        self.repo_root = Path(__file__).resolve().parents[3]
        self.reconcile_script = (
            self.repo_root
            / "pocket-lab-final-structure"
            / "pocket-lab-bootstrap-production-scripts-patched"
            / "scripts"
            / "lite"
            / "reconcile-runtime.sh"
        )

    def _load_previous(self) -> dict[str, Any]:
        try:
            value = json.loads(self.state_file.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _write_json(self, payload: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.state_file)

    def _event(self, payload: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        safe = {
            "event": str(payload.get("event") or "runtime_reconcile"),
            "reason": str(payload.get("reason") or "")[:160],
            "acted": bool(payload.get("acted")),
            "result": str(payload.get("result") or "")[:80],
            "at": _now_iso(),
        }
        with self.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe, sort_keys=True) + "\n")

    def _admit_repair(self) -> tuple[bool, str]:
        now = time.time()
        self.repair_history = [value for value in self.repair_history if now - value <= self.window]
        if now - self.last_repair_at < self.cooldown:
            return False, "cooldown"
        if len(self.repair_history) >= self.max_repairs:
            return False, "repair_budget"
        return True, ""

    def _repair(self, reasons: list[str]) -> dict[str, Any]:
        allowed, blocked = self._admit_repair()
        reason = reasons[0] if reasons else "desired_state_drift"
        if not allowed:
            event = {"event": "runtime_reconcile_suppressed", "reason": blocked, "acted": False, "result": reason}
            self._event(event)
            return event
        if not self.reconcile_script.is_file():
            event = {"event": "runtime_reconcile_unavailable", "reason": "reconcile_script_missing", "acted": False, "result": "missing"}
            self._event(event)
            return event
        env = os.environ.copy()
        env["POCKETLAB_PROFILE"] = "lite"
        env["POCKETLAB_LITE"] = "1"
        env["POCKETLAB_RECONCILER_CHILD"] = "1"
        try:
            result = _run(["bash", str(self.reconcile_script), "--repair", "--reason", reason], timeout=240, env=env)
            acted = result.returncode == 0
        except Exception:
            acted = False
        now = time.time()
        if acted:
            self.last_repair_at = now
            self.repair_history.append(now)
        event = {
            "event": "runtime_reconcile_attempted",
            "reason": reason,
            "acted": acted,
            "result": "converged" if acted else "failed",
        }
        self._event(event)
        return event

    def tick(self) -> dict[str, Any]:
        previous = self._load_previous()
        statuses = pm2_statuses(load_pm2_processes())
        remote = tailscale_state()
        reasons = repair_reasons(statuses)
        reasons.extend(remote_reconcile_reasons(remote, previous.get("remote_access")))
        reasons.extend(photoprism_reconcile_reasons(statuses))
        actions: list[dict[str, Any]] = []
        if reasons:
            actions.append(self._repair(reasons))
            statuses = pm2_statuses(load_pm2_processes())
            remote = tailscale_state()
        legacy_present = sorted(name for name in statuses if name in LEGACY_LITE_SERVICES)
        payload = {
            "reconciler": "pocketlab-runtime-reconciler",
            "version": VERSION,
            "status": "degraded" if reasons else "healthy",
            "services": {spec.name: statuses.get(spec.name, "missing") for spec in CONTROL_PLANE_SERVICES},
            "remote_access": remote,
            "drift_reasons": reasons,
            "actions": actions,
            "legacy_lite_services_present": legacy_present,
            "legacy_lite_services_allowed": False,
            "checked_at": _now_iso(),
            "sanitized": True,
        }
        self._write_json(payload)
        return payload

    def run(self) -> None:
        while not _STOP:
            try:
                self.tick()
            except Exception as exc:
                self._event(
                    {
                        "event": "runtime_reconcile_check_failed",
                        "reason": type(exc).__name__,
                        "acted": False,
                        "result": "degraded",
                    }
                )
            time.sleep(self.interval)


def _stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def main() -> int:
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    RuntimeReconciler().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
