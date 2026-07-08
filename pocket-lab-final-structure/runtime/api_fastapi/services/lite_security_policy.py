from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any


COMMAND_SUBJECT = "pocketlab.commands.lite.security.scan"

SCAN_PROFILE_QUICK = "quick"
SCAN_PROFILE_FULL = "full"
SCAN_PROFILE_APP = "app"
VALID_SCAN_PROFILES = {SCAN_PROFILE_QUICK, SCAN_PROFILE_FULL, SCAN_PROFILE_APP}

def normalize_scan_profile(value: Any = None) -> str:
    profile = str(value or SCAN_PROFILE_QUICK).strip().lower().replace("-", "_")
    if not profile:
        return SCAN_PROFILE_QUICK
    if profile in VALID_SCAN_PROFILES:
        return profile
    raise ValueError(f"Unsupported Security scan profile: {profile}")

SEVERITIES = ("critical", "high", "medium", "low", "info")
SCORE_WEIGHTS = {"critical": 30, "high": 15, "medium": 5, "low": 1, "info": 0}

TIMEOUTS = {
    "lynis": int(os.environ.get("POCKETLAB_LITE_SECURITY_LYNIS_TIMEOUT", "300")),
    "trivy_vuln_misconfig": int(os.environ.get("POCKETLAB_LITE_SECURITY_TRIVY_TIMEOUT", "420")),
    "trivy_secret": int(os.environ.get("POCKETLAB_LITE_SECURITY_TRIVY_SECRET_TIMEOUT", "240")),
    "trivy_sbom": int(os.environ.get("POCKETLAB_LITE_SECURITY_SBOM_TIMEOUT", "240")),
    "overall": int(os.environ.get("POCKETLAB_LITE_SECURITY_OVERALL_TIMEOUT", "900")),
    "full_lynis": int(os.environ.get("POCKETLAB_LITE_SECURITY_FULL_LYNIS_TIMEOUT", "900")),
    "full_trivy_vuln_misconfig": int(os.environ.get("POCKETLAB_LITE_SECURITY_FULL_TRIVY_TIMEOUT", "1200")),
    "full_trivy_secret": int(os.environ.get("POCKETLAB_LITE_SECURITY_FULL_SECRET_TIMEOUT", "900")),
    "full_trivy_sbom": int(os.environ.get("POCKETLAB_LITE_SECURITY_FULL_SBOM_TIMEOUT", "900")),
    "full_overall": int(os.environ.get("POCKETLAB_LITE_SECURITY_FULL_OVERALL_TIMEOUT", "3600")),
    "app_trivy_vuln_misconfig": int(os.environ.get("POCKETLAB_LITE_SECURITY_APP_TRIVY_TIMEOUT", "600")),
    "app_trivy_secret": int(os.environ.get("POCKETLAB_LITE_SECURITY_APP_SECRET_TIMEOUT", "300")),
    "app_trivy_sbom": int(os.environ.get("POCKETLAB_LITE_SECURITY_APP_SBOM_TIMEOUT", "300")),
    "app_overall": int(os.environ.get("POCKETLAB_LITE_SECURITY_APP_OVERALL_TIMEOUT", "900")),
}

EXCLUDED_DIRS = [
    "node_modules",
    ".git",
    "dist",
    "pwa_dist",
    "pwa_dist.previous.*",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".cache",
    ".npm",
    ".pocketlab-dev",
    ".pocket_lab/trivy-cache",
    ".pocket_lab/lynis-tmp",
    ".pm2/logs",
    "go/pkg",
    "pocket-lab-lite-backups",
    "restore-checkpoints",
    "restore-runs",
    "backups",
    "logs",
    "tmp",
    "temp",
    "state/workflows",
    "state/runs",
    "state/operations",
    "state/runner_events",
    "state/security/evidence",
    "vault/data",
    "gitea/data",
    "gitea/log",
    "observability_configs/*_data",
    "proot-distro/containers/ubuntu/rootfs",
    "var/lib/proot-distro/containers/ubuntu/rootfs",
    "mnt/sdcard",
    "sdcard",
    "storage",
    ".pocket_lab/lite/apps/photoprism/import",
    ".pocket_lab/lite/apps/photoprism/originals",
    ".pocket_lab/lite/apps/photoprism/storage/cache",
    ".pocket_lab/lite/apps/photoprism/storage/cache/media",
    ".pocket_lab/lite/apps/photoprism/storage/cache/thumbnails",
    ".pocket_lab/lite/apps/photoprism/storage/sidecar",
    ".pocket_lab/lite/apps/photoprism/logs",
]

EXCLUDED_FILES = [
    "*.pyc",
    "index.db",
    "photoprism/index.db",
]

QUICK_EXCLUDED_GROUPS = [
    "Photo library/media",
    "Backup payloads and restore checkpoints",
    "PROot Ubuntu full filesystem",
    "Go/npm/cache folders",
    "Old PWA builds",
    "Large runtime histories",
    "Scanner caches and generated logs",
]

QUICK_SKIPPED_TARGETS = [
    "PhotoPrism media and originals",
    "Android shared storage",
    "Pocket Lab backup payloads",
    "PROot Ubuntu full rootfs",
    "Go module cache",
    "npm cache",
    "Trivy cache",
    "Lynis temp files",
    "Old PWA build folders",
    "Large runtime histories",
]

FULL_EXCLUDED_GROUPS = [
    "Photo library/media",
    "Android shared storage",
    "Backup payloads and restic repository contents",
    "Restore checkpoints and large restore runs",
    "Logs and generated runtime histories",
    "Go/npm/tool caches",
    "Scanner caches and temp files",
    "Old PWA builds",
    "PhotoPrism thumbnails, sidecars, import, originals, and media index",
]

FULL_SKIPPED_TARGETS = [
    "Photo library/media",
    "Android shared storage",
    "PhotoPrism originals/import/media/cache/sidecars",
    "PhotoPrism index database",
    "Backup payloads",
    "Restic repository contents",
    "Restore checkpoints",
    "PM2 logs",
    "Go module cache",
    "npm cache",
    "Trivy cache",
    "Lynis temp files",
    "Old PWA build folders",
    "Large runtime histories",
]

FULL_EXTRA_EXCLUDED_DIRS = [
    "rootfs/mnt/sdcard",
    "rootfs/sdcard",
    "rootfs/storage",
    "rootfs/storage/emulated",
    "rootfs/tmp/photoprism*.tar.gz",
    "rootfs/tmp/photoprism_*",
    "rootfs/var/cache",
    "rootfs/var/log",
    "rootfs/var/tmp",
    "rootfs/home/*/.cache",
    "var/cache",
    "var/log",
    "var/tmp",
    "home/*/.cache",
    ".pocket_lab/lite/apps/photoprism/storage/index.db",
    ".pocket_lab/lite/apps/photoprism/storage/sidecar",
    ".pocket_lab/lite/apps/photoprism/storage/cache",
    ".pocket_lab/lite/apps/photoprism/storage/cache/media",
    ".pocket_lab/lite/apps/photoprism/storage/cache/thumbnails",
]

APP_EXCLUDED_GROUPS = [
    "Photo library/media",
    "PhotoPrism originals/import folder",
    "PhotoPrism thumbnails, cache, sidecars, and database",
    "Backup payloads and restic repository contents",
    "Android shared storage",
    "Logs and large caches",
    "Full PROot Ubuntu filesystem outside selected app paths",
    "Go/npm/tool caches",
    "Scanner caches and temp files",
]

APP_SKIPPED_TARGETS = [
    "Photo library/media",
    "PhotoPrism originals/import folder",
    "PhotoPrism thumbnails/cache/sidecars",
    "PhotoPrism database",
    "Backup payloads",
    "Android shared storage",
    "Logs and large caches",
    "Full PROot Ubuntu rootfs",
    "Go/npm/tool caches",
    "Trivy cache",
    "Lynis temp files",
]

APP_EXTRA_EXCLUDED_DIRS = [
    ".pocket_lab/lite/apps/photoprism/originals",
    ".pocket_lab/lite/apps/photoprism/import",
    ".pocket_lab/lite/apps/photoprism/storage/cache",
    ".pocket_lab/lite/apps/photoprism/storage/cache/media",
    ".pocket_lab/lite/apps/photoprism/storage/cache/thumbnails",
    ".pocket_lab/lite/apps/photoprism/storage/sidecar",
    ".pocket_lab/lite/apps/photoprism/logs",
    ".pocket_lab/lite/apps/photoprism/storage/index.db",
    "mnt/sdcard",
    "sdcard",
    "storage",
    "rootfs/mnt/sdcard",
    "rootfs/sdcard",
    "rootfs/storage",
    "rootfs/var/cache",
    "rootfs/var/log",
    "rootfs/var/tmp",
]

SUPPORTED_APP_CHECK_TARGETS = {
    "photoprism": {
        "app_id": "photoprism",
        "app_label": "PhotoPrism",
        "route": "/apps/photoprism/",
        "health_path": "/apps/photoprism/api/v1/status",
        "expected_health": {"status": "operational"},
        "process_name": "pocketlab-app-photoprism",
        "proot_app_path": "opt/photoprism",
        "proot_binary_path": "usr/local/bin/photoprism",
    }
}

SENSITIVE_KEY_RE = re.compile(
    r"(token|password|passwd|pwd|secret|api[_-]?key|authorization|bearer|vault|unseal|nats|invite|tailscale[_-]?auth|private[_-]?key)",
    re.IGNORECASE,
)


ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
LEADING_E_RE = re.compile(r"^\s*-e\s+")
STATUS_PADDING_RE = re.compile(r"\s{2,}")

LYNIS_NOISE_PATTERNS = (
    re.compile(r"^$", re.IGNORECASE),
    re.compile(r"^warnings?\s*\(\d+\):?", re.IGNORECASE),
    re.compile(r"^suggestions?\s*\(\d+\):?", re.IGNORECASE),
    re.compile(r"^\[\+\]", re.IGNORECASE),
    re.compile(r"^hardening index\b", re.IGNORECASE),
    re.compile(r"^auditing, system hardening, and compliance", re.IGNORECASE),
    re.compile(r"^\*\s*article:\s*", re.IGNORECASE),
    re.compile(r"pid file exists", re.IGNORECASE),
    re.compile(r"had a long execution", re.IGNORECASE),
    re.compile(r"cannot open /proc/net/dev.*permission denied.*limited output", re.IGNORECASE),
)

LYNIS_DEDUPE_PATTERNS = (
    (re.compile(r"consider hardening ssh configuration", re.IGNORECASE), "ssh-hardening"),
)

PROTECTED_RUNTIME_SECRET_TARGETS = (
    "gitea/conf/app.runtime.ini",
    ".pocket_lab/lite/apps/photoprism/config/photoprism.env",
    "photoprism.env",
)

SECRET_VALUE_REPLACEMENTS = [
    re.compile(r"(Authorization\s*:\s*)(Bearer\s+)?[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"(token\s*[=:]\s*)[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"(password\s*[=:]\s*)[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*[=:]\s*)[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"(secret\s*[=:]\s*)[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.IGNORECASE | re.DOTALL),
    re.compile(r"tskey-[A-Za-z0-9_-]+", re.IGNORECASE),
    re.compile(r"s\.[A-Za-z0-9]{20,}")
]


@dataclass(frozen=True)
class ComponentRule:
    component: str
    checks: tuple[str, ...]
    matchers: tuple[str, ...]


COMPONENT_RULES = (
    ComponentRule("Lite API", ("dependency scan", "runtime health", "config exposure"), ("api_fastapi", "fastapi", "lite api")),
    ComponentRule("React/Vite PWA bundle", ("dependency scan", "frontend bundle metadata"), ("src/", "package", "vite", "react")),
    ComponentRule("Caddy config", ("config exposure", "listener posture"), ("caddy", "caddyfile")),
    ComponentRule("NATS config", ("config exposure", "network exposure"), ("nats", "jetstream")),
    ComponentRule("PM2 process definitions", ("runtime process posture",), ("pm2", "process")),
    ComponentRule("Lite worker", ("command execution boundary", "runtime health"), ("worker", "workers")),
    ComponentRule("Lite node agent", ("device command boundary", "runtime health"), ("node_agent", "agent")),
    ComponentRule("Lite supervisor", ("agent recovery", "runtime health"), ("supervisor",)),
    ComponentRule("Bootstrap scripts", ("script posture", "secret exposure"), ("bootstrap", "scripts/")),
    ComponentRule("Recovery state/evidence", ("backup evidence", "secret exclusion"), ("recovery", "backup", "restore")),
    ComponentRule("Device invite state", ("invite exposure", "identity guard"), ("invite", "fleet")),
    ComponentRule("App catalog metadata", ("catalog metadata", "dependency scan"), ("catalog",)),
    ComponentRule("Rules/protection state", ("policy state", "misconfiguration"), ("policy", "opa", "rules")),
)

GUIDANCE = [
]


def repo_root() -> Path:
    configured = os.environ.get("POCKETLAB_LITE_SCAN_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[4]


def default_scan_roots(root: Path | None = None) -> list[Path]:
    base = (root or repo_root()).resolve()
    candidates = [
        base,
        base / "pocket-lab-final-structure",
        base / "scripts",
        base / "src",
        base / "package-lock.json",
        base / "package.json",
        base / "requirements.txt",
        base / "requirements-dev.txt",
        base / "Taskfile.yml",
        base / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched" / "scripts"
    ]
    return [item for item in candidates if item.exists()]


def allowed_scan_root(value: str | Path | None = None) -> Path:
    base = repo_root().resolve()
    if value is None or not str(value).strip() or str(value).strip() == "local":
        return base
    candidate = Path(value).expanduser().resolve()
    allowed = [base, *[p.resolve() for p in default_scan_roots(base) if p.is_dir()]]
    if any(candidate == root or root in candidate.parents for root in allowed):
        return candidate
    return base


def _quick_target(root: Path, label: str, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    return {
        "label": label,
        "relative": relative,
        "present": path.exists(),
        "kind": "directory" if path.is_dir() else "file",
    }


def quick_scan_excludes() -> dict[str, Any]:
    return {
        "skip_dirs": list(EXCLUDED_DIRS),
        "skip_files": list(EXCLUDED_FILES),
        "excluded_groups": list(QUICK_EXCLUDED_GROUPS),
        "skipped_targets": list(QUICK_SKIPPED_TARGETS),
    }


def full_scan_excludes() -> dict[str, Any]:
    return {
        "skip_dirs": sorted(set([*EXCLUDED_DIRS, *FULL_EXTRA_EXCLUDED_DIRS])),
        "skip_files": sorted(set([*EXCLUDED_FILES, "*.log", "*.sqlite", "*.sqlite3", "*.db", "*.tar.gz", "*.tgz"])),
        "excluded_groups": list(FULL_EXCLUDED_GROUPS),
        "skipped_targets": list(FULL_SKIPPED_TARGETS),
    }


def app_scan_excludes() -> dict[str, Any]:
    return {
        "skip_dirs": sorted(set([*EXCLUDED_DIRS, *APP_EXTRA_EXCLUDED_DIRS])),
        "skip_files": sorted(set([*EXCLUDED_FILES, "*.log", "*.sqlite", "*.sqlite3", "*.db", "*.tar.gz", "*.tgz"])),
        "excluded_groups": list(APP_EXCLUDED_GROUPS),
        "skipped_targets": list(APP_SKIPPED_TARGETS),
    }


def scan_excludes_for_profile(profile: Any = None) -> dict[str, Any]:
    normalized = normalize_scan_profile(profile)
    if normalized == SCAN_PROFILE_FULL:
        return full_scan_excludes()
    if normalized == SCAN_PROFILE_APP:
        return app_scan_excludes()
    return quick_scan_excludes()


def trivy_skip_args(root: Path, excludes: dict[str, Any] | None = None) -> list[str]:
    _ = root  # kept for future profile-specific absolute allowlist support
    plan = excludes or quick_scan_excludes()
    args: list[str] = []
    for item in plan.get("skip_dirs") or []:
        args.extend(["--skip-dirs", str(item)])
    for item in plan.get("skip_files") or []:
        args.extend(["--skip-files", str(item)])
    return args


def trivy_skip_args_for_profile(root: Path, profile: Any = None) -> list[str]:
    return trivy_skip_args(root, scan_excludes_for_profile(profile))


def build_quick_scan_plan(root: Path | None = None) -> dict[str, Any]:
    base = (root or repo_root()).resolve()
    source_targets = [
        _quick_target(base, "package.json", "package.json"),
        _quick_target(base, "package-lock.json", "package-lock.json"),
        _quick_target(base, "Python dev requirements", "requirements-dev.txt"),
        _quick_target(base, "Lite API runtime requirements", "pocket-lab-final-structure/runtime/requirements.txt"),
        _quick_target(base, "Lite API dev requirements", "pocket-lab-final-structure/runtime/requirements-dev.txt"),
        _quick_target(base, "React/Vite source", "src"),
        _quick_target(base, "Scripts", "scripts"),
        _quick_target(base, "Lite API runtime", "pocket-lab-final-structure/runtime"),
        _quick_target(base, "Bootstrap scripts", "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts"),
        _quick_target(base, "Caddy route config", "caddy/Caddyfile"),
        _quick_target(base, "Security policies", "security/policies"),
        _quick_target(base, "Operations metadata", "operations"),
        _quick_target(base, "Runbooks", "runbooks"),
        _quick_target(base, "Contracts", "contracts"),
    ]
    excludes = quick_scan_excludes()
    return {
        "profile": SCAN_PROFILE_QUICK,
        "scan_root_label": "Pocket Lab Lite repo",
        "target_groups": [
            "Termux host posture",
            "Pocket Lab Lite source/runtime config",
            "Runtime config posture",
        ],
        "source_targets": source_targets,
        "checked_targets": [
            "Termux host posture",
            "Pocket Lab Lite files",
            "Caddy route config",
            "NATS config posture",
            "Services summary",
            "Security evidence state",
        ],
        "skipped_targets": excludes["skipped_targets"],
        "excluded_groups": excludes["excluded_groups"],
        "skip_dirs": excludes["skip_dirs"],
        "skip_files": excludes["skip_files"],
    }


def _termux_home() -> Path:
    return Path(os.environ.get("HOME") or str(Path.home())).expanduser()


def _termux_prefix() -> Path:
    return Path(os.environ.get("PREFIX") or "/data/data/com.termux/files/usr").expanduser()


def proot_ubuntu_rootfs_candidates(root: Path | None = None) -> list[Path]:
    base = (root or repo_root()).resolve()
    home = _termux_home()
    prefix = _termux_prefix()
    candidates = [
        prefix / "var/lib/proot-distro/containers/ubuntu/rootfs",
        home / ".local/var/lib/proot-distro/containers/ubuntu/rootfs",
        base / "var/lib/proot-distro/containers/ubuntu/rootfs",
        base / "rootfs",
    ]
    seen: set[str] = set()
    unique: list[Path] = []
    for candidate in candidates:
        text = str(candidate)
        if text in seen:
            continue
        seen.add(text)
        unique.append(candidate)
    return unique


def discover_proot_ubuntu_rootfs(root: Path | None = None) -> Path | None:
    for candidate in proot_ubuntu_rootfs_candidates(root):
        try:
            if candidate.exists() and candidate.is_dir():
                return candidate.resolve()
        except OSError:
            continue
    return None


def photoprism_config_dir() -> Path:
    return _termux_home() / ".pocket_lab/lite/apps/photoprism/config"


def backup_metadata_candidates(root: Path | None = None) -> list[Path]:
    base = (root or repo_root()).resolve()
    home = _termux_home()
    backup_root = Path(os.environ.get("POCKETLAB_LITE_BACKUP_ROOT") or str(home / "pocket-lab-lite-backups")).expanduser()
    candidates = [
        base / "state/recovery",
        base / "state/backups",
        base / "state/lite/recovery",
        base / "state/lite/apps/photoprism/backups",
        backup_root / "manifests",
        backup_root / "receipts",
        backup_root / "app_backups",
        backup_root / "apps/photoprism",
        home / ".pocket_lab/lite/recovery",
        home / ".pocket_lab/lite/backups/manifests",
        home / ".pocket_lab/lite/apps/photoprism/backups",
    ]
    return candidates


def _full_target(root: Path, target_id: str, label: str, relative: str, *, optional: bool = False) -> dict[str, Any]:
    payload = _quick_target(root, label, relative)
    payload["target_id"] = target_id
    payload["optional"] = optional
    return payload


def build_full_scan_plan(root: Path | None = None) -> dict[str, Any]:
    base = (root or repo_root()).resolve()
    source_targets = [
        _full_target(base, "package_json", "package.json", "package.json"),
        _full_target(base, "package_lock", "package-lock.json", "package-lock.json"),
        _full_target(base, "python_dev_requirements", "Python dev requirements", "requirements-dev.txt"),
        _full_target(base, "runtime_requirements", "Lite API runtime requirements", "pocket-lab-final-structure/runtime/requirements.txt"),
        _full_target(base, "runtime_dev_requirements", "Lite API dev requirements", "pocket-lab-final-structure/runtime/requirements-dev.txt"),
        _full_target(base, "src", "React/Vite source", "src"),
        _full_target(base, "scripts", "Scripts", "scripts"),
        _full_target(base, "runtime", "Lite API runtime", "pocket-lab-final-structure/runtime"),
        _full_target(base, "bootstrap_scripts", "Bootstrap scripts", "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts"),
        _full_target(base, "caddyfile", "Caddy route config", "caddy/Caddyfile", optional=True),
        _full_target(base, "security_policies", "Security policies", "security/policies", optional=True),
        _full_target(base, "operations", "Operations metadata", "operations", optional=True),
        _full_target(base, "runbooks", "Runbooks", "runbooks", optional=True),
        _full_target(base, "contracts", "Contracts", "contracts", optional=True),
    ]
    rootfs = discover_proot_ubuntu_rootfs(base)
    photoprism_config = photoprism_config_dir()
    backup_candidates = backup_metadata_candidates(base)
    backup_present = any(candidate.exists() for candidate in backup_candidates)
    excludes = full_scan_excludes()
    selected_targets = [
        {"target_id": "termux_host", "label": "Termux host", "present": True, "kind": "runtime_metadata"},
        {"target_id": "pocketlab_source", "label": "Pocket Lab Lite", "present": base.exists(), "kind": "repo"},
        {"target_id": "runtime_config", "label": "Runtime config", "present": True, "kind": "metadata"},
        {"target_id": "proot_ubuntu", "label": "PROot Ubuntu", "present": bool(rootfs), "kind": "selected_rootfs", "optional": True},
        {"target_id": "photoprism", "label": "PhotoPrism", "present": bool(rootfs or photoprism_config.exists()), "kind": "app_metadata", "optional": True},
        {"target_id": "backup_metadata", "label": "Backup metadata", "present": backup_present, "kind": "metadata", "optional": True},
    ]
    return {
        "profile": SCAN_PROFILE_FULL,
        "scan_root_label": "Pocket Lab Lite local device",
        "target_groups": [
            "Termux host posture",
            "Pocket Lab Lite source/runtime config",
            "Runtime config posture",
            "Selected PROot Ubuntu metadata/runtime areas",
            "PhotoPrism app/config/runtime",
            "Backup/recovery metadata",
        ],
        "source_targets": source_targets,
        "selected_targets": selected_targets,
        "checked_targets": [
            "Termux host",
            "Pocket Lab Lite",
            "Runtime config",
            "PROot Ubuntu",
            "PhotoPrism",
            "Backup metadata",
        ],
        "skipped_targets": excludes["skipped_targets"],
        "excluded_groups": excludes["excluded_groups"],
        "skip_dirs": excludes["skip_dirs"],
        "skip_files": excludes["skip_files"],
    }



def normalize_app_id(value: Any = None) -> str:
    app_id = str(value or "").strip().lower().replace("_", "-")
    if app_id in SUPPORTED_APP_CHECK_TARGETS:
        return app_id
    raise ValueError("Unsupported app for App Check")


def app_check_target(app_id: Any = None) -> dict[str, Any]:
    normalized = normalize_app_id(app_id)
    return dict(SUPPORTED_APP_CHECK_TARGETS[normalized])


def build_app_scan_plan(app_id: Any = None, root: Path | None = None) -> dict[str, Any]:
    target = app_check_target(app_id)
    base = (root or repo_root()).resolve()
    rootfs = discover_proot_ubuntu_rootfs(base)
    photoprism_config = photoprism_config_dir()
    backup_candidates = backup_metadata_candidates(base)
    backup_present = any(candidate.exists() for candidate in backup_candidates)
    app_path = rootfs / str(target["proot_app_path"]) if rootfs else None
    app_binary = rootfs / str(target["proot_binary_path"]) if rootfs else None
    excludes = app_scan_excludes()
    source_targets = [
        {
            "target_id": "photoprism_route",
            "label": "PhotoPrism route",
            "relative": str(target.get("route") or "/apps/photoprism/"),
            "present": True,
            "kind": "same_origin_route",
        },
        {
            "target_id": "photoprism_app_files",
            "label": "PhotoPrism app files",
            "relative": "/opt/photoprism",
            "present": bool(app_path and app_path.exists()),
            "kind": "proot_app_path",
            "optional": True,
        },
        {
            "target_id": "photoprism_app_binary",
            "label": "PhotoPrism app binary",
            "relative": "/usr/local/bin/photoprism",
            "present": bool(app_binary and app_binary.exists()),
            "kind": "proot_app_binary",
            "optional": True,
        },
        {
            "target_id": "photoprism_settings",
            "label": "PhotoPrism settings",
            "relative": "~/.pocket_lab/lite/apps/photoprism/config",
            "present": photoprism_config.exists(),
            "kind": "app_config",
            "optional": True,
        },
    ]
    selected_targets = [
        {"target_id": "photoprism_route", "label": "PhotoPrism route", "present": True, "kind": "route_posture"},
        {"target_id": "photoprism_app_files", "label": "PhotoPrism app files", "present": bool(app_path and app_path.exists()), "kind": "selected_app_files", "optional": True},
        {"target_id": "photoprism_settings", "label": "PhotoPrism settings", "present": photoprism_config.exists(), "kind": "app_config", "optional": True},
        {"target_id": "photoprism_backup_metadata", "label": "PhotoPrism backup metadata", "present": backup_present, "kind": "metadata", "optional": True},
        {"target_id": "photoprism_action_state", "label": "PhotoPrism action state", "present": True, "kind": "app_action_state"},
    ]
    return {
        "profile": SCAN_PROFILE_APP,
        "app_id": target["app_id"],
        "app_label": target["app_label"],
        "scan_root_label": f"{target['app_label']} app target",
        "target_groups": [
            "PhotoPrism route posture",
            "PhotoPrism selected app files",
            "PhotoPrism settings",
            "PhotoPrism backup metadata",
            "PhotoPrism action state",
        ],
        "source_targets": source_targets,
        "selected_targets": selected_targets,
        "checked_targets": [
            "PhotoPrism route",
            "PhotoPrism app files",
            "PhotoPrism settings",
            "PhotoPrism backup metadata",
            "PhotoPrism action state",
        ],
        "skipped_targets": excludes["skipped_targets"],
        "excluded_groups": excludes["excluded_groups"],
        "skip_dirs": excludes["skip_dirs"],
        "skip_files": excludes["skip_files"],
    }


def build_scan_plan(profile: Any = None, root: Path | None = None, app_id: Any = None) -> dict[str, Any]:
    normalized = normalize_scan_profile(profile)
    if normalized == SCAN_PROFILE_FULL:
        return build_full_scan_plan(root)
    if normalized == SCAN_PROFILE_APP:
        return build_app_scan_plan(app_id or "photoprism", root)
    return build_quick_scan_plan(root)


def redact_text(value: str) -> str:
    redacted = str(value)
    for pattern in SECRET_VALUE_REPLACEMENTS:
        redacted = pattern.sub(lambda match: (match.group(1) if match.groups() else "") + "***REDACTED***", redacted)
    return redacted


SAFE_SCANNER_METADATA_KEYS = {
    "returncode",
    "return_code",
    "exit_code",
    "vuln_returncode",
    "vulnerability_returncode",
    "misconfig_returncode",
    "secret_returncode",
    "lynis_returncode",
}


def is_safe_scanner_metadata_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return normalized in SAFE_SCANNER_METADATA_KEYS or normalized.endswith("_returncode")


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)) and not is_safe_scanner_metadata_key(key):
                clean[str(key)] = "***REDACTED***"
            else:
                clean[str(key)] = redact_value(item)
        return clean
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def normalize_severity(value: Any) -> str:
    raw = str(value or "info").strip().lower()
    if raw in {"negligible", "unknown", "none"}:
        return "info"
    if raw in SEVERITIES:
        return raw
    return "info"


def score_for_counts(counts: dict[str, int]) -> int:
    score = 100
    for severity, weight in SCORE_WEIGHTS.items():
        score -= int(counts.get(severity, 0)) * weight
    return max(0, min(100, score))


def status_for_score(score: int, counts: dict[str, int]) -> tuple[str, str]:
    if int(counts.get("critical", 0)) > 0 or score <= 39:
        return "danger", "Urgent safety issue"
    if score <= 69:
        return "degraded", "Needs attention"
    if score <= 89:
        return "review", "Needs review"
    return "healthy", "Looks safe"


def clean_security_text(value: Any) -> str:
    cleaned = ANSI_ESCAPE_RE.sub("", str(value or ""))
    cleaned = LEADING_E_RE.sub("", cleaned).strip()
    cleaned = STATUS_PADDING_RE.sub(" ", cleaned)
    return redact_text(cleaned).strip()


def should_skip_lynis_text(value: str) -> bool:
    cleaned = clean_security_text(value)
    return any(pattern.search(cleaned) for pattern in LYNIS_NOISE_PATTERNS)


def lynis_dedupe_key(value: str) -> str:
    cleaned = clean_security_text(value).lower()
    for pattern, key in LYNIS_DEDUPE_PATTERNS:
        if pattern.search(cleaned):
            return key
    return cleaned


def _safe_mode(path: Path) -> int | None:
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return None


def is_protected_runtime_secret(target: str, root: Path | None = None) -> bool:
    raw_target = str(target or "").replace("\\", "/").lstrip("/")
    if raw_target.endswith("photoprism.env") or "photoprism/config/photoprism.env" in raw_target:
        return True
    if raw_target not in PROTECTED_RUNTIME_SECRET_TARGETS:
        return False
    base = (root or repo_root()).resolve()
    candidate = (base / raw_target).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return False
    file_mode = _safe_mode(candidate)
    parent_mode = _safe_mode(candidate.parent)
    if file_mode is None or parent_mode is None:
        return False
    file_locked = (file_mode & 0o077) == 0
    parent_locked = (parent_mode & 0o077) == 0
    return file_locked and parent_locked
