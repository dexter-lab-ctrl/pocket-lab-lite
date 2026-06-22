from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import deps


SENSITIVE_NAME_PARTS = (
    "token",
    "password",
    "passwd",
    "secret",
    "private_key",
    "id_rsa",
    "id_ed25519",
    "unseal",
    "root_token",
    "vault",
    "nats_password",
    "api_key",
    "credential",
)

DEFAULT_STATE_FILES = (
    "fleet_agents.json",
    "fleet_invites.json",
    "fleet_device_events.json",
    "fleet_device_audit.json",
    "fleet_agent_commands.json",
    "catalog.json",
    "artifact_index.json",
    "opa.json",
    "operations.json",
    "operation_runs.json",
    "release_state.json",
    "recovery.json",
    "backup_state.json",
)

DEFAULT_STATE_DIRS = (
    "events",
    "workflows",
    "commands",
    "runner_events",
)

EXCLUDED_SENSITIVE_CLASSES = (
    "raw API tokens",
    "raw invite tokens",
    "NATS passwords",
    "Vault root token",
    "Vault unseal keys",
    "private SSH keys",
    "backend secret values",
    "PM2 runtime cache",
)

EXCLUDED_RUNTIME_CLASSES = (
    "node_modules",
    ".venv",
    "cache folders",
    "temporary logs",
    "generated frontend dist",
    "backup repository internals",
)


@dataclass(frozen=True)
class LiteBackupLayout:
    root: Path
    repository: Path
    manifests: Path
    receipts: Path
    restore_previews: Path
    restore_checkpoints: Path
    restore_runs: Path
    staging: Path
    password_file: Path

    def ensure(self) -> None:
        for path in (
            self.root,
            self.repository,
            self.manifests,
            self.receipts,
            self.restore_previews,
            self.restore_checkpoints,
            self.restore_runs,
            self.staging,
            self.password_file.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


def backup_root() -> Path:
    configured = os.environ.get("POCKETLAB_LITE_BACKUP_ROOT")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "pocket-lab-lite-backups"


def backup_layout() -> LiteBackupLayout:
    root = backup_root()
    return LiteBackupLayout(
        root=root,
        repository=root / "restic-repo",
        manifests=root / "manifests",
        receipts=root / "receipts",
        restore_previews=root / "restore-previews",
        restore_checkpoints=root / "restore-checkpoints",
        restore_runs=root / "restore-runs",
        staging=root / ".staging",
        password_file=root / ".secrets" / "restic-password",
    )


def public_repository_label(layout: LiteBackupLayout | None = None) -> str:
    layout = layout or backup_layout()
    return str(layout.root)


def is_sensitive_path(path: Path) -> bool:
    lowered = "/".join(path.parts).lower()
    if any(part in lowered for part in SENSITIVE_NAME_PARTS):
        return True
    if "/.ssh/" in f"/{lowered}/" or lowered.endswith("/.ssh"):
        return True
    if "/pm2/" in f"/{lowered}/" or "/.pm2/" in f"/{lowered}/":
        return True
    return False


def _safe_relative(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return path.name


def discover_state_sources() -> list[dict[str, Any]]:
    state_dir = deps.settings().state_dir
    sources: list[dict[str, Any]] = []

    for name in DEFAULT_STATE_FILES:
        candidate = state_dir / name
        if candidate.exists() and candidate.is_file() and not is_sensitive_path(candidate):
            sources.append(
                {
                    "path": candidate,
                    "relative_path": f"state/{name}",
                    "set": "Lite runtime state",
                    "kind": "file",
                }
            )

    for dirname in DEFAULT_STATE_DIRS:
        directory = state_dir / dirname
        if not directory.exists() or not directory.is_dir() or is_sensitive_path(directory):
            continue
        for candidate in sorted(directory.rglob("*")):
            if not candidate.is_file() or is_sensitive_path(candidate):
                continue
            rel = _safe_relative(candidate, state_dir)
            sources.append(
                {
                    "path": candidate,
                    "relative_path": f"state/{rel}",
                    "set": "Lite runtime state",
                    "kind": "file",
                }
            )

    return sources


def backup_scope(include_app_data: bool = False) -> dict[str, Any]:
    included = [
        "Lite runtime state",
        "Device records and heartbeats",
        "Device invite lifecycle records",
        "Device audit and command evidence",
        "Rules/protection state",
        "App catalog/install metadata",
        "Recovery metadata",
        "Backup manifests and receipts",
    ]
    conditional = [
        {
            "name": "MariaDB logical dump",
            "enabled": False,
            "reason": "Not implemented in this increment; add when MariaDB detection and dump validation are present.",
        },
        {
            "name": "Gitea repository/config snapshot",
            "enabled": False,
            "reason": "Not implemented in this increment; add after service-specific dump/restore checks.",
        },
        {
            "name": "Registered app data paths",
            "enabled": bool(include_app_data),
            "reason": "Only included when explicitly requested and when app paths are registered.",
        },
        {
            "name": "Encrypted secret recovery bundle",
            "enabled": False,
            "reason": "Secrets are excluded by default; encrypted secret recovery is a later explicit opt-in flow.",
        },
    ]
    return {
        "included": included,
        "conditional": conditional,
        "excluded_sensitive": list(EXCLUDED_SENSITIVE_CLASSES),
        "excluded_runtime": list(EXCLUDED_RUNTIME_CLASSES),
    }
