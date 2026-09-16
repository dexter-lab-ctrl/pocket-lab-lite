#!/usr/bin/env python3
"""Check the source-owned Security Assurance Playbook contract.

This check is intentionally static. It reads the checked-in registries,
routers, CLI parsers, Taskfiles, report/task wrappers, and playbooks; it never
starts a service, contacts the Server Phone, installs a tool, or executes a
scanner.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

try:
    import yaml
except ImportError as exc:  # pragma: no cover - the repository venv supplies PyYAML
    raise SystemExit("PyYAML is required for the Security Assurance Playbook check") from exc


ROOT = Path(__file__).resolve().parents[2]
DOC_ROOT = ROOT / "docs/validation"
ASSURANCE_ROOT = ROOT / "security/assurance"
REPORT_INDEX = ROOT / "docs/generated/security-assurance/reports/index.md"

PLAYBOOKS = (
    "README.md",
    "security-assurance/README.md",
    "security-assurance/01-architecture.md",
    "security-assurance/02-getting-started.md",
    "security-assurance/03-environment-prerequisites.md",
    "security-assurance/04-toolchain-installation.md",
    "security-assurance/05-harness-bootstrap-auth.md",
    "security-assurance/06-preflight.md",
    "security-assurance/07-smoke-playbook.md",
    "security-assurance/08-standard-playbook.md",
    "security-assurance/09-adversarial-playbook.md",
    "security-assurance/10-deep-playbook.md",
    "security-assurance/11-fault-recovery-playbook.md",
    "security-assurance/12-tool-specific-playbooks.md",
    "security-assurance/13-stride-owasp-attack-paths.md",
    "security-assurance/14-findings-remediation.md",
    "security-assurance/15-evidence-reporting.md",
    "security-assurance/16-cleanup-default-off.md",
    "security-assurance/17-troubleshooting.md",
    "security-assurance/18-exact-head-release-qualification.md",
    "security-assurance/19-human-review-playbook.md",
    "security-assurance/20-adding-scenario.md",
    "security-assurance/21-adding-tool.md",
    "security-assurance/22-server-phone-task-runtime.md",
    "security-assurance/23-report-publication.md",
    "reference/command-catalog.md",
    "reference/api-reference.md",
    "reference/task-reference.md",
    "reference/tool-matrix.md",
    "reference/scenario-catalog.md",
    "reference/fault-control-catalog.md",
    "reference/result-status-reference.md",
    "reference/evidence-artifact-reference.md",
    "reference/command-completeness.md",
    "evidence-history/runtime-security-assurance-qualification.md",
)

REQUIRED_SOURCES = (
    "security/assurance/tools.yaml",
    "security/assurance/suites.yaml",
    "security/assurance/scenarios.yaml",
    "security/assurance/faults.yaml",
    "security/threat-model-scenarios.json",
    "scripts/dev/lite/harness.py",
    "scripts/dev/lite/security_assurance.py",
    "scripts/dev/lite/security_assurance_report.py",
    "scripts/dev/lite/security_assurance_toolchain.py",
    "scripts/dev/lite/task_runtime.py",
    "scripts/dev/lite/start-qualification.sh",
    "pocket-lab-final-structure/runtime/api_fastapi/routers/harness.py",
    "pocket-lab-final-structure/runtime/api_fastapi/routers/security_assurance.py",
    "pocket-lab-final-structure/runtime/api_fastapi/services/lite_harness.py",
    "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_assurance.py",
    "pocket-lab-final-structure/runtime/api_fastapi/services/lite_assurance_faults.py",
    "tasks/Taskfile.lite.yml",
    "tasks/Taskfile.docs.yml",
    "mkdocs.yml",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _registry(name: str) -> dict:
    value = yaml.safe_load(_read(ASSURANCE_ROOT / name))
    if not isinstance(value, dict):
        raise ValueError(f"{name} is not a mapping")
    return value


def _task_ids() -> set[str]:
    result: set[str] = set()
    pattern = re.compile(r"^  (lite:(?:harness|qualification|security:assurance)(?::[a-z0-9-]+)*)\s*:", re.MULTILINE)
    for path in (ROOT / "tasks/Taskfile.lite.yml", ROOT / "tasks/Taskfile.docs.yml"):
        result.update(pattern.findall(_read(path)))
    return result


def _cli_commands(path: Path) -> set[str]:
    return set(re.findall(r'add_parser\(\s*["\']([^"\']+)["\']', _read(path)))


def _api_routes(path: Path, prefix: str) -> set[str]:
    text = _read(path)
    result: set[str] = set()
    for method, route in re.findall(r"@router\.(get|post|put|patch|delete)\(\s*[\"']([^\"']+)", text, re.IGNORECASE):
        result.add(f"{method.upper()} {prefix}{route}")
    return result


def _route_reference(text: str) -> set[str]:
    return {
        f"{method.upper()} {route}"
        for method, route in re.findall(
            r"\b(GET|POST|PUT|PATCH|DELETE)\s+`?(/api/lite/harness[^`\s]+)`?",
            text,
        )
    }


def _source_paths_from_catalog(text: str) -> Iterable[str]:
    for line in text.splitlines():
        if "Implementation source" not in line:
            continue
        yield from re.findall(r"`([^`]+)`", line)


def collect_errors(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    doc_root = root / "docs/validation"
    assurance_root = root / "security/assurance"

    for relative in PLAYBOOKS:
        if not (doc_root / relative).is_file():
            errors.append(f"missing required playbook: docs/validation/{relative}")
    for relative in REQUIRED_SOURCES:
        if not (root / relative).exists():
            errors.append(f"missing implementation source: {relative}")
    if not (root / REPORT_INDEX.relative_to(ROOT)).is_file():
        errors.append("missing generated Security Assurance report index")
    if errors:
        return errors

    tools = _registry("tools.yaml")
    suites = _registry("suites.yaml")
    scenarios = _registry("scenarios.yaml")
    faults = _registry("faults.yaml")
    tool_ids = {str(item.get("id")) for item in tools.get("toolchain", []) if isinstance(item, dict)}
    suite_ids = {str(item) for item in (suites.get("profiles") or {}).keys()}
    scenario_ids = {str(item.get("id")) for item in scenarios.get("scenarios", []) if isinstance(item, dict)}
    fault_ids = {str(item.get("id")) for item in faults.get("faults", []) if isinstance(item, dict)}

    matrix = _read(doc_root / "reference/tool-matrix.md")
    scenario_catalog = _read(doc_root / "reference/scenario-catalog.md")
    fault_catalog = _read(doc_root / "reference/fault-control-catalog.md")
    task_catalog = _read(doc_root / "reference/task-reference.md")
    api_catalog = _read(doc_root / "reference/api-reference.md")
    command_catalog = _read(doc_root / "reference/command-catalog.md")
    completeness = _read(doc_root / "reference/command-completeness.md")
    all_playbook_text = "\n".join(_read(doc_root / relative) for relative in PLAYBOOKS if (doc_root / relative).is_file())

    for identifier in sorted(tool_ids):
        if f"`{identifier}`" not in matrix:
            errors.append(f"tool is absent from tool matrix: {identifier}")
        if f"`{identifier}`" not in all_playbook_text:
            errors.append(f"tool is absent from playbook text: {identifier}")
    for identifier in sorted(suite_ids):
        if f"`{identifier}`" not in all_playbook_text:
            errors.append(f"suite is absent from playbook text: {identifier}")
    for identifier in sorted(scenario_ids):
        if f"`{identifier}`" not in scenario_catalog:
            errors.append(f"scenario is absent from scenario catalog: {identifier}")
    for identifier in sorted(fault_ids):
        if f"`{identifier}`" not in fault_catalog:
            errors.append(f"fault is absent from fault catalog: {identifier}")

    task_ids = _task_ids()
    for identifier in sorted(task_ids):
        if f"`{identifier}`" not in task_catalog:
            errors.append(f"task is absent from task reference: {identifier}")

    cli_ids = _cli_commands(root / "scripts/dev/lite/security_assurance.py") | _cli_commands(root / "scripts/dev/lite/harness.py")
    for identifier in sorted(cli_ids):
        if f"`{identifier}`" not in command_catalog:
            errors.append(f"CLI command is absent from command catalog: {identifier}")

    harness_routes = _api_routes(root / "pocket-lab-final-structure/runtime/api_fastapi/routers/harness.py", "/api/lite/harness")
    assurance_routes = _api_routes(root / "pocket-lab-final-structure/runtime/api_fastapi/routers/security_assurance.py", "/api/lite/harness/security-assurance")
    documented_routes = _route_reference(api_catalog)
    for route in sorted(harness_routes | assurance_routes):
        if route not in documented_routes:
            errors.append(f"API route is absent from API reference: {route}")

    command_headings = re.findall(r"^### (SA-[A-Z0-9-]+)\s*$", command_catalog, re.MULTILINE)
    if not command_headings:
        errors.append("command catalog has no stable command records")
    elif len(command_headings) != len(set(command_headings)):
        errors.append("command catalog contains duplicate command IDs")
    allowed_statuses = {"SUPPORTED", "SUPERSEDED", "HISTORICAL", "PROHIBITED"}
    statuses = set(re.findall(r"^Status:\s*\*\*([A-Z_]+)\*\*\s*$", command_catalog, re.MULTILINE))
    if not statuses <= allowed_statuses:
        errors.append(f"command catalog has invalid statuses: {sorted(statuses - allowed_statuses)}")
    for source_path in _source_paths_from_catalog(command_catalog):
        if source_path.startswith(("http://", "https://", "<", "~")):
            continue
        if not (root / source_path).exists():
            errors.append(f"command catalog implementation source missing: {source_path}")

    if "UNRESOLVED" in completeness or "| UNMAPPED |" in completeness:
        errors.append("command completeness mapping contains unresolved entries")
    for source_name in (
        "lite-validation.md",
        "qualification-maintenance-harness.md",
        "runtime-security-assurance-harness.md",
        "runtime-security-assurance-qualification.md",
    ):
        if source_name not in completeness:
            errors.append(f"command completeness mapping omits original dossier: {source_name}")

    required_markers = (
        "The Runtime Security Assurance Harness is not a generic remote shell.",
        "Server Phone is a consumer/qualification target, never the development workspace",
        "PASS",
        "FAIL",
        "PARTIAL",
        "BLOCKED",
        "HUMAN_REVIEW_REQUIRED",
        "STRIDE",
        "OWASP Top 10 2021",
        "AP-14",
        "[REDACTED BY SECURITY ASSURANCE POLICY]",
        "scenario",
        "normalized",
        "report:publish",
    )
    for marker in required_markers:
        if marker not in all_playbook_text:
            errors.append(f"required safety/coverage marker absent from playbooks: {marker}")

    unsafe_patterns = (
        r"export\s+POCKETLAB_HARNESS_PROVISIONING_TOKEN\s*=",
        r"COMMAND\s*=\s*[\"'].*arbitrary",
        r"POCKETLAB_TEST_AUTH_BYPASS\s*=\s*1",
        r"nmap\s+[^\n]*-p-",
    )
    for pattern in unsafe_patterns:
        if re.search(pattern, all_playbook_text, re.IGNORECASE):
            errors.append(f"unsafe documentation pattern found: {pattern}")

    mkdocs = _read(root / "mkdocs.yml")
    for path in (
        "validation/security-assurance/20-adding-scenario.md",
        "validation/security-assurance/21-adding-tool.md",
        "validation/security-assurance/22-server-phone-task-runtime.md",
        "validation/security-assurance/23-report-publication.md",
        "generated/security-assurance/reports/index.md",
    ):
        if path not in mkdocs:
            errors.append(f"Security Assurance MkDocs navigation omits: {path}")

    return errors


def main() -> int:
    errors = collect_errors()
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    tools = _registry("tools.yaml")
    suites = _registry("suites.yaml")
    scenarios = _registry("scenarios.yaml")
    faults = _registry("faults.yaml")
    print(
        "Security Assurance Playbook check passed: "
        f"tools={len(tools.get('toolchain', []))} "
        f"suites={len(suites.get('profiles', {}))} "
        f"scenarios={len(scenarios.get('scenarios', []))} "
        f"faults={len(faults.get('faults', []))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
