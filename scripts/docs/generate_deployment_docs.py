#!/usr/bin/env python3
"""Generate deployment evidence Pocket Lab deployment documentation from evidence manifest."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/platform/generated/deployment-evidence-manifest.json"
GEN = "<!-- GENERATED FILE: do not edit by hand. Regenerate with `task docs:deployment`. -->\n\n"


def load_manifest() -> dict[str, Any]:
    if not MANIFEST.exists():
        raise SystemExit("Missing deployment evidence manifest. Run scripts/docs/generate_deployment_evidence.py first.")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def write(path: str, body: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(GEN + body.rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {path}")


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(value: Any) -> str:
        text = "" if value is None else str(value)
        text = text.replace("\n", "<br>").replace("|", "\\|")
        return text
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(cell(v) for v in row) + " |")
    return "\n".join(out) + "\n"


def short_list(values: list[Any], limit: int = 8) -> str:
    if not values:
        return "—"
    shown = [str(v) for v in values[:limit]]
    if len(values) > limit:
        shown.append(f"+{len(values) - limit} more")
    return ", ".join(shown)


def deployment_guide(m: dict[str, Any]) -> str:
    s = m["source_summary"]
    return f"""# Pocket Lab Deployment Guide

This deployment evidence page is generated from repository deployment evidence. It documents what exists in this repository; it does not add a new deployment platform or change runtime behavior.

## Deployment model

Pocket Lab remains an edge-first, self-hostable control-plane platform. The runtime flow is preserved:

```text
React / Vite PWA
→ FastAPI Control API
→ NATS / JetStream
→ Workers
→ Events
→ FastAPI
→ UI
```

The deployment automation inspected by deployment evidence is source evidence for installing, validating, and operating that runtime. Frontend code does not execute shell commands and does not talk directly to NATS.

## Source evidence summary

{md_table(["Evidence area", "Count"], [["Ansible / IaC bases", len(s["ansible_bases"])], ["Ansible playbooks", s["playbook_count"]], ["Ansible roles", s["role_count"]], ["Inventory / group vars files", s["inventory_or_vars_count"]], ["IaC catalog entries", s["iac_catalog_count"]], ["Bootstrap / platform scripts", s["bootstrap_script_count"]], ["Platform source docs", s["platform_doc_count"]], ["Environment/runtime files", s["environment_file_count"]]])}

## Recommended deployment documentation workflow

```bash
task docs:deployment
task docs:deployment:check
mkdocs build --strict
```

## Operator deployment flow

1. Prepare the platform using the documented Android / Termux, Ubuntu, WSL2, or host-specific bootstrap scripts.
2. Start and validate Docker/NATS where applicable.
3. Apply Ansible playbooks from the repository-native IaC tree when targeting a managed host.
4. Validate the FastAPI control API, NATS / JetStream, workers, typed operation contracts, runbook docs, security docs, and MkDocs site.
5. Use generated evidence manifests for review and audit.

## Source-controlled references

- Ansible playbooks: `docs/platform/generated/ansible-playbooks-reference.md`
- Ansible roles and tasks: `docs/platform/generated/ansible-roles-reference.md`
- Bootstrap scripts: `docs/platform/generated/bootstrap-scripts-reference.md`
- Environment variables: `docs/platform/generated/environment-reference.md`
- Runtime blueprint: `docs/architecture/runtime-blueprint.md`
- Evidence manifest: `docs/platform/generated/deployment-evidence-manifest.json`
"""


def platform_guide(m: dict[str, Any]) -> str:
    docs = m.get("platform_source_docs", [])
    compat = m.get("compatibility_evidence", {})
    rows = [[d["title"], d["path"], d["sha256"][:12]] for d in docs]
    return f"""# Pocket Lab Platform Guide

This generated page links the platform-specific deployment and development evidence that already exists in the repository.

## Platform source documents

{md_table(["Document", "Path", "SHA-256"], rows or [["No platform docs found", "—", "—"]])}

## Android / Termux / ARM64 evidence

deployment evidence found {len(compat.get('android_termux_arm64', []))} Android / Termux / ARM64-related evidence entries. Use the existing Android / Termux operations guide and smoke scripts where present; this generator only links and fingerprints existing sources.

## Ubuntu / WSL2 evidence

deployment evidence found {len(compat.get('ubuntu_wsl2', []))} Ubuntu / WSL2-related evidence entries. Daily development and validation should run from the Linux filesystem repo, not from a Windows-mounted path.

## Governance wording

Deployment docs should preserve Personal, Professional, and Enterprise modes. Personal Mode may remain friendly and non-blocking, while Enterprise Mode remains opt-in and stricter for approval and audit workflows.
"""


def ansible_playbooks_reference(m: dict[str, Any]) -> str:
    rows = []
    for p in m["ansible"]["playbooks"]:
        shell = sum(1 for t in p.get("tasks", []) if t.get("uses_shell_or_command"))
        rows.append([p["path"], short_list(p.get("hosts", [])), "yes" if p.get("become") else "no", short_list(p.get("roles", [])), len(p.get("tasks", [])), shell, p["sha256"][:12]])
    details = []
    for p in m["ansible"]["playbooks"]:
        details.append(f"### `{p['path']}`\n")
        details.append(md_table(["Field", "Value"], [["Hosts", short_list(p.get("hosts", []))], ["Become", "yes" if p.get("become") else "no"], ["Roles", short_list(p.get("roles", []), 20)], ["Vars", short_list(p.get("vars", []), 20)], ["Vars files", short_list(p.get("vars_files", []), 20)], ["Tags", short_list(p.get("tags", []), 20)], ["SHA-256", p["sha256"]]]))
        tasks = p.get("tasks", [])[:40]
        if tasks:
            details.append(md_table(["Section", "Task", "Module", "Shell/command"], [[t.get("section"), t.get("name"), t.get("module"), "yes" if t.get("uses_shell_or_command") else "no"] for t in tasks]))
    return f"""# Ansible Playbooks Reference

This page is generated from repository Ansible YAML. Optional `ansible-playbook --syntax-check` validation may be run locally when Ansible is installed.

## Playbook index

{md_table(["Playbook", "Hosts", "Become", "Roles", "Tasks", "Shell/command tasks", "SHA-256"], rows or [["No playbooks found", "—", "—", "—", "0", "0", "—"]])}

## Playbook details

{''.join(details) if details else 'No playbook details found.'}
"""


def ansible_roles_reference(m: dict[str, Any]) -> str:
    rows = []
    for r in m["ansible"]["roles"]:
        rows.append([r["role"], r["path"], r.get("task_count", 0), short_list(r.get("modules", []), 10), len(r.get("shell_or_command_tasks", [])), len(r.get("templates", [])), len(r.get("files", [])), r.get("sha256", "")[:12]])
    details = []
    for r in m["ansible"]["roles"]:
        details.append(f"### `{r['role']}`\n")
        details.append(md_table(["Field", "Value"], [["Path", r["path"]], ["Task files", short_list(r.get("task_files", []), 20)], ["Handler files", short_list(r.get("handler_files", []), 20)], ["Default files", short_list(r.get("default_files", []), 20)], ["Templates", short_list(r.get("templates", []), 20)], ["Files", short_list(r.get("files", []), 20)], ["Shell/command tasks", short_list(r.get("shell_or_command_tasks", []), 20)], ["Service tasks", short_list(r.get("service_tasks", []), 20)], ["Package tasks", short_list(r.get("package_tasks", []), 20)]]))
        tasks = r.get("tasks", [])[:30]
        if tasks:
            details.append(md_table(["Task", "Module", "Source"], [[t.get("name"), t.get("module"), t.get("source_file")] for t in tasks]))
    return f"""# Ansible Roles / Tasks Reference

This page is generated from role task, handler, defaults, template, and file sources.

## Role index

{md_table(["Role", "Path", "Tasks", "Modules", "Shell/command", "Templates", "Files", "SHA-256"], rows or [["No roles found", "—", "0", "—", "0", "0", "0", "—"]])}

## Role details

{''.join(details) if details else 'No role details found.'}
"""


def bootstrap_reference(m: dict[str, Any]) -> str:
    scripts = m.get("bootstrap_and_platform_scripts", [])
    rows = [[s["path"], s["kind"], s["platform"], s["summary"], short_list(s.get("environment_variables", []), 8), s["sha256"][:12]] for s in scripts]
    return f"""# Bootstrap Scripts Reference

This generated page documents repository-native bootstrap, validation, runtime, and Windows/WSL helper scripts.

{md_table(["Script", "Kind", "Platform", "Summary", "Environment variables", "SHA-256"], rows or [["No scripts found", "—", "—", "—", "—", "—"]])}

## Notes

- Windows PowerShell scripts are host-side orchestration only.
- Ubuntu/WSL2 shell scripts validate and operate the Linux development/runtime environment.
- Android / Termux scripts are documented only when source evidence exists.
- Deployment scripts must not bypass FastAPI → NATS / JetStream → Worker execution for app operations.
"""


def environment_reference(m: dict[str, Any]) -> str:
    env_rows = [[k, short_list(v, 12)] for k, v in m.get("environment_variables", {}).items()]
    file_rows = [[f["path"], f["kind"], f["sha256"][:12]] for f in m.get("environment_and_runtime_files", [])]
    task_rows = [[t["name"], t.get("description", "")] for t in m.get("taskfile_deployment_related_tasks", [])]
    return f"""# Environment Variables Reference

This generated page documents environment variables and runtime/dependency files discovered from deployment scripts and repository templates.

## Environment variables found in scripts

{md_table(["Variable", "Referenced by"], env_rows or [["No deployment environment variables found", "—"]])}

## Environment and runtime files

{md_table(["File", "Kind", "SHA-256"], file_rows or [["No environment/runtime files found", "—", "—"]])}

## Deployment-related Taskfile targets

{md_table(["Task", "Description"], task_rows or [["No deployment-related Taskfile targets found", "—"]])}
"""


def runtime_blueprint(m: dict[str, Any]) -> str:
    s = m["source_summary"]
    return f"""# Pocket Lab Runtime Blueprint

This deployment evidence runtime blueprint is generated from deployment evidence and preserves the existing Pocket Lab runtime architecture.

## Runtime flow

```text
React / Vite PWA
→ FastAPI Control API
→ NATS / JetStream
→ Workers
→ Events
→ FastAPI
→ UI
```

## Deployment evidence feeding this blueprint

{md_table(["Evidence", "Count"], [["Ansible bases", len(s["ansible_bases"])], ["Playbooks", s["playbook_count"]], ["Roles", s["role_count"]], ["Bootstrap scripts", s["bootstrap_script_count"]], ["Platform docs", s["platform_doc_count"]], ["Environment/runtime files", s["environment_file_count"]]])}

## Boundaries

- React/Vite is the user interface and never talks directly to NATS.
- FastAPI remains the control API.
- NATS / JetStream remains the command and event backbone.
- Workers own execution and resume.
- Typed Operations remain the execution contract.
- Runbooks orchestrate typed operations and keep approval, rejection, resume, auto-approval, and audit evidence explicit.

## Platform compatibility

deployment evidence links existing Android / Termux / ARM64 and Ubuntu / WSL2 evidence where present. It does not claim a platform is implemented unless a source file exists in the evidence manifest.
"""


def main() -> int:
    m = load_manifest()
    write("docs/platform/deployment-guide.md", deployment_guide(m))
    write("docs/platform/platform-guide.md", platform_guide(m))
    write("docs/platform/generated/ansible-playbooks-reference.md", ansible_playbooks_reference(m))
    write("docs/platform/generated/ansible-roles-reference.md", ansible_roles_reference(m))
    write("docs/platform/generated/bootstrap-scripts-reference.md", bootstrap_reference(m))
    write("docs/platform/generated/environment-reference.md", environment_reference(m))
    write("docs/architecture/runtime-blueprint.md", runtime_blueprint(m))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
