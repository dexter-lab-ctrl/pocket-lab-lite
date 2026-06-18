#!/usr/bin/env python3
"""Generate Pocket Lab deployment evidence deployment evidence from repository sources.

This script is documentation-only. It inspects existing Ansible, bootstrap,
platform, Taskfile, Docker, and environment files and emits a deterministic
manifest consumed by deployment evidence generated docs and freshness checks.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:  # pragma: no cover
    print(f"PyYAML is required for deployment evidence deployment docs: {exc}", file=sys.stderr)
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/platform/generated/deployment-evidence-manifest.json"
GENERATED_BY = "scripts/docs/generate_deployment_evidence.py"

ANSIBLE_BASES = [
    Path("pocket-lab-final-structure/pocket-lab-iac-api-compatible"),
    Path("pocket_lab_iac"),
    Path("pocket-lab-final-structure/pocket_lab_iac"),
    Path("pocket-lab-final-structure/runtime/core/ansible"),
]
SCRIPT_DIRS = [Path("scripts/dev"), Path("scripts/windows")]
PLATFORM_DOC_DIRS = [Path("docs/platform"), Path("docs/architecture")]
EXCLUDE_PARTS = {".git", ".venv", "node_modules", "site", "dist", "playwright-report"}
FORBIDDEN_ACTIVE_TOKENS = [
    "frontend direct NATS",
]
DOCS_EXCLUSION_MARKERS = ("docs/history", "docs/adr", "pocketlab_missing_reference")
TIER11_GENERATED_OUTPUTS = {
    "docs/platform/deployment-guide.md",
    "docs/platform/platform-guide.md",
    "docs/platform/generated/ansible-playbooks-reference.md",
    "docs/platform/generated/ansible-roles-reference.md",
    "docs/platform/generated/bootstrap-scripts-reference.md",
    "docs/platform/generated/environment-reference.md",
    "docs/platform/generated/deployment-evidence-manifest.json",
    "docs/architecture/runtime-blueprint.md",
}


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def yaml_load(path: Path) -> Any:
    try:
        return yaml.safe_load(read_text(path))
    except Exception as exc:
        return {"__yaml_error__": str(exc)}


def source_record(path: Path, kind: str) -> dict[str, Any]:
    return {
        "path": rel(path),
        "kind": kind,
        "sha256": sha256(path),
        "size_bytes": path.stat().st_size,
    }


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    return bool(parts & EXCLUDE_PARTS)


def all_existing_files(base: Path, patterns: tuple[str, ...]) -> list[Path]:
    root = ROOT / base
    if not root.exists():
        return []
    found: list[Path] = []
    for pattern in patterns:
        for path in root.rglob(pattern):
            if path.is_file() and not should_skip(path):
                found.append(path)
    return sorted(set(found), key=lambda p: rel(p))


def first_line_comment_or_name(path: Path) -> str:
    text = read_text(path)
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") and len(stripped.lstrip("#").strip()) > 4:
            return stripped.lstrip("#").strip()
    return path.name


def task_names_from_taskfile() -> list[dict[str, str]]:
    path = ROOT / "Taskfile.yml"
    if not path.exists():
        return []
    data = yaml_load(path)
    tasks = (data or {}).get("tasks", {}) if isinstance(data, dict) else {}
    rows = []
    for name, body in sorted(tasks.items()):
        text = json.dumps(body, default=str).lower()
        if any(token in name.lower() or token in text for token in ["deploy", "dev", "docker", "windows", "wsl", "docs:deployment", "iac", "bootstrap", "release"]):
            rows.append({"name": str(name), "description": str((body or {}).get("desc", "")) if isinstance(body, dict) else ""})
    return rows


def summarize_ansible_task(task: Any) -> dict[str, Any]:
    if not isinstance(task, dict):
        return {"name": str(task), "module": "unknown"}
    reserved = {"name", "tags", "when", "register", "vars", "become", "notify", "loop", "with_items", "delegate_to", "environment"}
    module = next((k for k in task.keys() if k not in reserved and not k.startswith("ansible.builtin.")), "unknown")
    if module == "unknown":
        module = next((k for k in task.keys() if k.startswith("ansible.builtin.")), "unknown")
    return {
        "name": str(task.get("name", "unnamed task")),
        "module": str(module),
        "tags": task.get("tags", []),
        "uses_shell_or_command": module in {"shell", "command", "raw", "ansible.builtin.shell", "ansible.builtin.command", "ansible.builtin.raw"},
        "manages_service": module in {"service", "systemd", "ansible.builtin.service", "ansible.builtin.systemd"},
        "installs_package": module in {"package", "apt", "pip", "npm", "ansible.builtin.package", "ansible.builtin.apt", "ansible.builtin.pip"},
    }


def inspect_playbook(path: Path) -> dict[str, Any]:
    data = yaml_load(path)
    plays = data if isinstance(data, list) else []
    role_names: list[str] = []
    task_rows: list[dict[str, Any]] = []
    hosts: list[str] = []
    become = False
    vars_keys: set[str] = set()
    vars_files: list[str] = []
    tags: set[str] = set()
    yaml_error = data.get("__yaml_error__") if isinstance(data, dict) else None
    for play in plays:
        if not isinstance(play, dict):
            continue
        if play.get("hosts") is not None:
            hosts.append(str(play.get("hosts")))
        become = become or bool(play.get("become"))
        if isinstance(play.get("vars"), dict):
            vars_keys.update(str(k) for k in play["vars"].keys())
        vf = play.get("vars_files", [])
        if isinstance(vf, str):
            vars_files.append(vf)
        elif isinstance(vf, list):
            vars_files.extend(str(x) for x in vf)
        roles = play.get("roles", [])
        if isinstance(roles, list):
            for role in roles:
                if isinstance(role, str):
                    role_names.append(role)
                elif isinstance(role, dict):
                    role_names.append(str(role.get("role", role.get("name", "unknown"))))
                    if role.get("tags"):
                        role_tags = role.get("tags")
                        if isinstance(role_tags, list):
                            tags.update(str(t) for t in role_tags)
                        else:
                            tags.add(str(role_tags))
        for block_name in ["pre_tasks", "tasks", "post_tasks", "handlers"]:
            for task in play.get(block_name, []) or []:
                row = summarize_ansible_task(task)
                row["section"] = block_name
                task_rows.append(row)
                task_tags = row.get("tags", [])
                if isinstance(task_tags, list):
                    tags.update(str(t) for t in task_tags)
                elif task_tags:
                    tags.add(str(task_tags))
    return {
        **source_record(path, "ansible_playbook"),
        "name": path.stem,
        "hosts": sorted(set(hosts)),
        "become": become,
        "vars": sorted(vars_keys),
        "vars_files": sorted(set(vars_files)),
        "roles": sorted(set(role_names)),
        "tasks": task_rows,
        "tags": sorted(tags),
        "yaml_error": yaml_error,
    }


def inspect_role(role_dir: Path) -> dict[str, Any]:
    task_files = sorted((role_dir / "tasks").glob("*.yml")) + sorted((role_dir / "tasks").glob("*.yaml")) if (role_dir / "tasks").exists() else []
    handler_files = sorted((role_dir / "handlers").glob("*.yml")) + sorted((role_dir / "handlers").glob("*.yaml")) if (role_dir / "handlers").exists() else []
    default_files = sorted((role_dir / "defaults").glob("*.yml")) + sorted((role_dir / "defaults").glob("*.yaml")) if (role_dir / "defaults").exists() else []
    template_files = sorted((role_dir / "templates").rglob("*")) if (role_dir / "templates").exists() else []
    file_files = sorted((role_dir / "files").rglob("*")) if (role_dir / "files").exists() else []
    all_tasks: list[dict[str, Any]] = []
    modules: set[str] = set()
    shell_tasks: list[str] = []
    service_tasks: list[str] = []
    package_tasks: list[str] = []
    yaml_errors: list[dict[str, str]] = []
    for path in task_files + handler_files:
        data = yaml_load(path)
        if isinstance(data, dict) and data.get("__yaml_error__"):
            yaml_errors.append({"path": rel(path), "error": data["__yaml_error__"]})
            continue
        if not isinstance(data, list):
            continue
        for task in data:
            row = summarize_ansible_task(task)
            row["source_file"] = rel(path)
            all_tasks.append(row)
            modules.add(row["module"])
            if row["uses_shell_or_command"]:
                shell_tasks.append(row["name"])
            if row["manages_service"]:
                service_tasks.append(row["name"])
            if row["installs_package"]:
                package_tasks.append(row["name"])
    return {
        "role": role_dir.name,
        "path": rel(role_dir),
        "task_files": [rel(p) for p in task_files],
        "handler_files": [rel(p) for p in handler_files],
        "default_files": [rel(p) for p in default_files],
        "templates": [rel(p) for p in template_files if p.is_file()],
        "files": [rel(p) for p in file_files if p.is_file()],
        "task_count": len(all_tasks),
        "modules": sorted(modules),
        "shell_or_command_tasks": shell_tasks,
        "service_tasks": service_tasks,
        "package_tasks": package_tasks,
        "tasks": all_tasks[:80],
        "yaml_errors": yaml_errors,
        "sha256": hashlib.sha256("\n".join([sha256(p) for p in task_files + handler_files + default_files if p.exists()]).encode()).hexdigest() if (task_files or handler_files or default_files) else "",
    }


def inspect_ansible() -> dict[str, Any]:
    playbooks: list[dict[str, Any]] = []
    roles: list[dict[str, Any]] = []
    inventories: list[dict[str, Any]] = []
    collections: list[dict[str, Any]] = []
    catalog: list[dict[str, Any]] = []
    for base in ANSIBLE_BASES:
        root = ROOT / base
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.yml")) + sorted(root.rglob("*.yaml")):
            if should_skip(path):
                continue
            relp = rel(path)
            if "/playbooks/" in f"/{relp}" or path.name in {"site.yml", "playbook.yml", "maintenance.yml"}:
                data = yaml_load(path)
                if isinstance(data, list):
                    playbooks.append(inspect_playbook(path))
                elif "iac-catalog" in relp:
                    catalog.append({**source_record(path, "iac_catalog_yaml"), "yaml_error": data.get("__yaml_error__") if isinstance(data, dict) else None})
            elif "/inventory/" in f"/{relp}" or path.name in {"hosts.yml", "requirements.yml"}:
                inventories.append({**source_record(path, "ansible_inventory_or_vars"), "yaml_error": (yaml_load(path).get("__yaml_error__") if isinstance(yaml_load(path), dict) else None)})
            elif path.name == "requirements.yml":
                collections.append({**source_record(path, "ansible_requirements")})
        for roles_dir in sorted(root.rglob("roles")):
            if not roles_dir.is_dir() or should_skip(roles_dir):
                continue
            for role_dir in sorted([p for p in roles_dir.iterdir() if p.is_dir()]):
                if (role_dir / "tasks").exists() or (role_dir / "defaults").exists() or (role_dir / "handlers").exists():
                    roles.append(inspect_role(role_dir))
    dedup_roles = {r["path"]: r for r in roles}
    return {
        "bases": [base.as_posix() for base in ANSIBLE_BASES if (ROOT / base).exists()],
        "playbooks": sorted(playbooks, key=lambda x: x["path"]),
        "roles": [dedup_roles[k] for k in sorted(dedup_roles)],
        "inventories_and_vars": sorted(inventories, key=lambda x: x["path"]),
        "collections": sorted(collections, key=lambda x: x["path"]),
        "iac_catalog": sorted(catalog, key=lambda x: x["path"]),
    }


def inspect_scripts() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    env_vars: dict[str, set[str]] = {}
    env_pattern = re.compile(r"\b(POCKETLAB_[A-Z0-9_]+|CHROME_PATH|LHCI_CHROME_PATH|NATS_[A-Z0-9_]+|ANSIBLE_[A-Z0-9_]+)\b")
    for base in SCRIPT_DIRS:
        root = ROOT / base
        if not root.exists():
            continue
        for path in sorted(root.iterdir()):
            if not path.is_file() or path.suffix.lower() not in {".sh", ".ps1", ".py"}:
                continue
            text = read_text(path)
            kind = "windows_powershell" if path.suffix.lower() == ".ps1" else "ubuntu_shell" if path.suffix.lower() == ".sh" else "python_script"
            platform = "Windows host" if kind == "windows_powershell" else "Ubuntu / WSL2 / Linux / Termux where compatible"
            if "termux" in path.name.lower() or "ANDROID" in text or "Termux" in text:
                platform = "Android / Termux / ARM64"
            if "wsl" in path.name.lower() or "WSL" in text:
                platform = "Windows WSL2 Ubuntu"
            vars_found = sorted(set(env_pattern.findall(text)))
            for var in vars_found:
                env_vars.setdefault(var, set()).add(rel(path))
            rows.append({
                **source_record(path, kind),
                "summary": first_line_comment_or_name(path),
                "platform": platform,
                "environment_variables": vars_found,
            })
    return {"scripts": rows, "environment_variables": {k: sorted(v) for k, v in sorted(env_vars.items())}}


def inspect_platform_docs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for base in PLATFORM_DOC_DIRS:
        root = ROOT / base
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            relp = rel(path)
            if relp in TIER11_GENERATED_OUTPUTS:
                continue
            if "/generated/" in f"/{relp}/":
                continue
            text = read_text(path)
            if "GENERATED FILE" in text[:300]:
                continue
            if any(token in text.lower() or token in path.name.lower() for token in ["deploy", "platform", "wsl", "windows", "termux", "runtime", "docker", "ansible"]):
                rows.append({**source_record(path, "platform_or_architecture_doc"), "title": next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("#")), path.stem)})
    return rows

def inspect_env_files() -> list[dict[str, Any]]:
    patterns = [".env", ".env.*", "*.env", "*.env.example", "docker-compose*.yml", "docker-compose*.yaml", "requirements*.txt", "package.json"]
    rows: list[dict[str, Any]] = []
    for pattern in patterns:
        for path in sorted(ROOT.glob(pattern)):
            if path.is_file() and not should_skip(path):
                rows.append(source_record(path, "environment_or_runtime_template"))
    return sorted({r["path"]: r for r in rows}.values(), key=lambda x: x["path"])


def scan_forbidden_tokens() -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    active_roots = [ROOT / "scripts/dev", ROOT / "scripts/windows", ROOT / "pocket-lab-final-structure/pocket-lab-iac-api-compatible", ROOT / "pocket_lab_iac", ROOT / "docker-compose.dev.yml", ROOT / "Taskfile.yml"]
    for root in active_roots:
        paths = [root] if root.is_file() else list(root.rglob("*")) if root.exists() else []
        for path in paths:
            if not path.is_file() or should_skip(path):
                continue
            relp = rel(path)
            if any(marker in relp for marker in DOCS_EXCLUSION_MARKERS) or relp.endswith(".bak") or "/migrations/" in relp or relp.startswith("scripts/docs/"):
                continue
            if path.suffix.lower() not in {".yml", ".yaml", ".sh", ".ps1", ".py", ""} and path.name not in {"Taskfile.yml"}:
                continue
            text = read_text(path)
            for token in FORBIDDEN_ACTIVE_TOKENS:
                if token in text:
                    findings.append({"path": relp, "token": token})
    return findings


def main() -> int:
    ansible = inspect_ansible()
    scripts = inspect_scripts()
    manifest = {
        "schema_version": "pocketlab.deployment_evidence.v1",
        "generated_by": GENERATED_BY,
        "repo_root_name": ROOT.name,
        "source_summary": {
            "ansible_bases": ansible["bases"],
            "playbook_count": len(ansible["playbooks"]),
            "role_count": len(ansible["roles"]),
            "inventory_or_vars_count": len(ansible["inventories_and_vars"]),
            "iac_catalog_count": len(ansible["iac_catalog"]),
            "bootstrap_script_count": len(scripts["scripts"]),
            "platform_doc_count": len(inspect_platform_docs()),
            "environment_file_count": len(inspect_env_files()),
        },
        "ansible": ansible,
        "bootstrap_and_platform_scripts": scripts["scripts"],
        "environment_variables": scripts["environment_variables"],
        "taskfile_deployment_related_tasks": task_names_from_taskfile(),
        "platform_source_docs": inspect_platform_docs(),
        "environment_and_runtime_files": inspect_env_files(),
        "compatibility_evidence": {
            "android_termux_arm64": [r for r in scripts["scripts"] + inspect_platform_docs() if "termux" in json.dumps(r).lower() or "android" in json.dumps(r).lower()],
            "ubuntu_wsl2": [r for r in scripts["scripts"] + inspect_platform_docs() if "wsl" in json.dumps(r).lower() or "ubuntu" in json.dumps(r).lower()],
        },
        "forbidden_active_token_findings": scan_forbidden_tokens(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print("Deployment evidence summary: " + json.dumps(manifest["source_summary"], sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
