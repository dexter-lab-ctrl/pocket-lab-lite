#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "pocket-lab-final-structure" / "runtime"
OPENAPI_OUT = ROOT / "contracts" / "generated" / "lite-openapi.json"
PREVIOUS = ROOT / "contracts" / "generated" / "lite-openapi.previous.json"
FIXTURE_ROOT = ROOT / "src" / "test" / "fixtures" / "generated"
FIXTURE_INDEX = FIXTURE_ROOT / "lite-fixtures.js"
API_DOC = ROOT / "docs" / "generated" / "development" / "api-contract.md"
COMPAT_DOC = ROOT / "docs" / "generated" / "development" / "api-compatibility.md"
FRONTEND_DOC = ROOT / "docs" / "generated" / "development" / "frontend-api-usage.md"

FORBIDDEN_KEY = re.compile(r"(password|token|secret|credential|authorization|cookie|private_key|api_key|nats_url|restic)", re.I)
FRONTEND_QUOTED_PATH = re.compile(r"([\"'])(/api/lite/[^\"']*)\1")
FRONTEND_TEMPLATE_PATH = re.compile(r"`(/api/lite/[^`]*)`")
JS_TEMPLATE = re.compile(r"\$\{.*?\}")

SCENARIOS: dict[str, list[str]] = {
    "home": ["healthy", "review-recommended", "release-current", "release-available", "release-failed", "offline-saved", "api-unavailable"],
    "devices": ["devices-server-online", "devices-online", "devices-offline", "devices-agent-stopped", "devices-repairing", "devices-remote-not-ready", "devices-protected-host", "devices-capability-verified", "devices-capability-pending", "devices-capability-missing", "devices-invite-ready", "devices-invite-expired", "devices-invite-mismatch", "offline-saved"],
    "apps": ["catalog-ready", "healthy", "app-stopped", "catalog-install-available", "catalog-installing", "app-action-failed", "app-media-not-ready", "app-route-not-ready", "app-projection-stale", "offline-saved"],
    "recovery": ["recovery-ready", "recovery-projection-too-old", "recovery-no-backups", "recovery-verified", "recovery-backup-running", "recovery-backup-failed", "recovery-preview-ready", "recovery-restore-blocked", "recovery-checkpoint-ready", "recovery-no-storage-node", "recovery-repository-unavailable", "offline-saved"],
    "security": ["security-quick-healthy", "security-action-needed", "security-full-running", "security-app-check-healthy", "security-urgent", "security-first-run", "security-profile-stale", "security-progress", "security-scanner-unavailable", "security-unsupported-app-route", "offline-saved"],
    "identity": ["identity-summary", "identity-password-configured", "identity-password-change-required", "slow-response", "api-unavailable", "identity-role-aware-fixture"],
    "rules": ["rules-empty", "rules-present", "rules-enabled", "rules-disabled", "rules-validation-error", "rules-execution-pending", "api-unavailable", "rules-approval-required"],
}

ALIASES = {
    "review-recommended": "lifecycle-attention",
    "release-current": "healthy",
    "release-available": "healthy",
    "release-failed": "nats-down",
    "offline-saved": "nats-down",
    "api-unavailable": "nats-down",
    "devices-offline": "worker-down",
    "devices-agent-stopped": "worker-down",
    "devices-repairing": "worker-down",
    "devices-remote-not-ready": "nats-down",
    "catalog-install-available": "catalog-ready",
    "app-stopped": "lifecycle-attention",
    "app-action-failed": "lifecycle-attention",
    "app-media-not-ready": "lifecycle-attention",
    "app-route-not-ready": "lifecycle-attention",
    "app-projection-stale": "lifecycle-attention",
    "recovery-projection-too-old": "nats-down",
    "recovery-backup-failed": "worker-down",
    "recovery-repository-unavailable": "nats-down",
    "security-quick-healthy": "healthy",
    "security-full-running": "security-partial",
    "security-app-check-healthy": "healthy",
    "security-urgent": "security-action-needed",
    "security-profile-stale": "security-partial",
    "security-progress": "security-partial",
    "security-scanner-unavailable": "worker-down",
    "security-unsupported-app-route": "security-action-needed",
    "slow-response": "healthy",
}


def source_commit() -> str:
    # Committed generated docs use a stable honest marker. CI/release builds pass
    # SOURCE_COMMIT explicitly so rendered evidence records the exact revision.
    return os.environ.get("SOURCE_COMMIT", "").strip() or "uncommitted"


def generated_at() -> str:
    return os.environ.get("SOURCE_GENERATED_AT", "").strip() or "uncommitted"


def contract_source_files() -> list[Path]:
    candidates = [
        Path(__file__).resolve(),
        ROOT / "pocket-lab-final-structure/runtime/api_fastapi/main.py",
        ROOT / "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py",
        ROOT / "src/lib/liteApi.js",
        ROOT / "src/lib/liteQueryClient.js",
        ROOT / "src/mocks/handlers.js",
    ]
    return sorted(path for path in candidates if path.exists())


def source_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in contract_source_files():
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
        digest.update(b"\n")
    return digest.hexdigest()


def generated_frontmatter(audience: str, commit: str, title: str, description: str, status: str = "verified") -> str:
    return (
        "---\n"
        f"title: {json.dumps(title)}\n"
        f"description: {json.dumps(description)}\n"
        f"status: {status}\n"
        "generated: true\n"
        f"audience: {audience.lower()}\n"
        f"source_commit: {commit}\n"
        f"generated_at: {generated_at()}\n"
        "generator: scripts/docs/lite/generate_contracts.py\n"
        f"source_fingerprint: {source_fingerprint()}\n"
        "schema_revision: 1\n"
        "validation_status: generated\n"
        "---\n\n"
    )


def export_openapi() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    module_name = "pocket-lab-final-structure.runtime.api_fastapi.main"
    try:
        from importlib import import_module
        app = import_module(module_name).app
    except Exception:
        sys.path.insert(0, str(RUNTIME))
        from api_fastapi.main import app  # type: ignore
    schema = app.openapi()
    schema["paths"] = {
        path: value
        for path, value in sorted(schema.get("paths", {}).items())
        if path.startswith("/api/lite/") or path in {"/health", "/ready"}
    }
    schema.setdefault("info", {})["x-pocketlab-audience"] = "development-contract"
    schema["info"]["x-pocketlab-source-commit"] = source_commit()
    return schema


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def normalize_path(path: str) -> str:
    path = path.split("?", 1)[0]
    path = JS_TEMPLATE.sub("{param}", path)
    return re.sub(r"//+", "/", path)


def frontend_paths() -> set[str]:
    paths: set[str] = set()
    for file in [ROOT / "src/lib/liteApi.js", ROOT / "src/lib/liteQueryClient.js"]:
        text = file.read_text(encoding="utf-8")
        for _, match in FRONTEND_QUOTED_PATH.findall(text):
            paths.add(normalize_path(match))
        for match in FRONTEND_TEMPLATE_PATH.findall(text):
            paths.add(normalize_path(match))
    return paths


def path_matches(frontend: str, backend: str) -> bool:
    def parts(value: str) -> list[str]:
        return [part for part in value.strip("/").split("/") if part]
    left, right = parts(frontend), parts(backend)
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if a.startswith("{") or b.startswith("{"):
            continue
        if a != b:
            return False
    return True


def fixture_payload(domain: str, scenario: str, commit: str) -> dict[str, Any]:
    status = "partial" if domain in {"identity", "rules"} else "verified-fixture"
    reason_codes = []
    if "projection-too-old" in scenario:
        reason_codes.append("projection_too_old")
    if "unavailable" in scenario:
        reason_codes.append("service_unavailable")
    if "mismatch" in scenario:
        reason_codes.append("identity_mismatch")
    return {
        "metadata": {
            "generated": True,
            "source_commit": commit,
            "generator": "scripts/docs/lite/generate_contracts.py",
            "generated_at": generated_at(),
            "source_fingerprint": source_fingerprint(),
            "validation_status": "generated",
            "schema_revision": 1,
            "scenario": scenario,
            "domain": domain,
            "implementation_status": status,
            "msw_scenario": ALIASES.get(scenario, scenario if scenario in {"healthy", "catalog-ready", "catalog-installing", "security-action-needed", "security-first-run"} else "healthy"),
        },
        "contract": {
            "safe_read_only": True,
            "reason_codes": reason_codes,
            "notes": "Canonical sanitized documentation/test fixture. It never represents a successful write action.",
        },
    }


def ensure_safe(value: Any, trail: str = "root") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if FORBIDDEN_KEY.search(str(key)):
                raise ValueError(f"forbidden fixture key at {trail}.{key}")
            ensure_safe(item, f"{trail}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            ensure_safe(item, f"{trail}[{index}]")
    elif isinstance(value, str):
        if re.search(r"(Bearer\s+|nats://[^\s]+@|-----BEGIN .*PRIVATE KEY-----)", value, re.I):
            raise ValueError(f"forbidden fixture content at {trail}")


def fixture_outputs(commit: str) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    alias_map: dict[str, str] = {}
    inventory: list[dict[str, str]] = []
    for domain, scenarios in SCENARIOS.items():
        for scenario in scenarios:
            payload = fixture_payload(domain, scenario, commit)
            ensure_safe(payload)
            path = FIXTURE_ROOT / domain / f"{scenario}.json"
            outputs[path] = stable_json(payload)
            alias_map[scenario] = payload["metadata"]["msw_scenario"]
            inventory.append({"domain": domain, "scenario": scenario, "path": path.relative_to(ROOT).as_posix()})
    index_payload = {
        "metadata": {
            "generated": True,
            "source_commit": commit,
            "generated_at": generated_at(),
            "generator": "scripts/docs/lite/generate_contracts.py",
            "source_fingerprint": source_fingerprint(),
            "schema_revision": 1,
            "validation_status": "generated",
        },
        "aliases": alias_map,
        "inventory": inventory,
    }
    outputs[FIXTURE_ROOT / "manifest.json"] = stable_json(index_payload)
    outputs[FIXTURE_INDEX] = (
        "// Generated by scripts/docs/lite/generate_contracts.py. Do not edit.\n"
        f"export const generatedLiteFixtureManifest = {json.dumps(index_payload, indent=2, sort_keys=True)};\n"
        "export function resolveGeneratedLiteScenario(value = 'healthy') {\n"
        "  const key = String(value || 'healthy');\n"
        "  return generatedLiteFixtureManifest.aliases[key] || key;\n"
        "}\n"
    )
    return outputs


def contract_docs(schema: dict[str, Any], commit: str) -> dict[Path, str]:
    backend = set(schema.get("paths", {}))
    frontend = frontend_paths()
    unsupported = sorted(path for path in frontend if not any(path_matches(path, route) for route in backend))
    unused = sorted(path for path in backend if path.startswith("/api/lite/") and not any(path_matches(route, path) for route in frontend))
    operations = sum(
        len([method for method in value if method.lower() in {"get", "post", "put", "patch", "delete"}])
        for value in schema.get("paths", {}).values()
    )
    api = generated_frontmatter("development", commit, "Lite HTTP API contract", "Canonical FastAPI Lite OpenAPI contract and validation summary.") + f"""# Lite HTTP API contract

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

FastAPI OpenAPI is the canonical HTTP contract. This generated Lite view contains **{len(backend)} paths** and **{operations} operations**.

- Source: `pocket-lab-final-structure/runtime/api_fastapi/main.py`
- Contract: `contracts/generated/lite-openapi.json`
- Validation: Redocly plus frontend route usage comparison

Write actions remain FastAPI-owned. Browser tests do not invoke internal Python services directly.
"""
    if PREVIOUS.exists():
        old = json.loads(PREVIOUS.read_text())
        old_paths = set(old.get("paths", {}))
        added, removed = sorted(backend - old_paths), sorted(old_paths - backend)
        baseline = "A previous released contract is present."
    else:
        added, removed, baseline = sorted(backend), [], "No previous released Lite contract is committed; this run establishes the current baseline."
    compat = generated_frontmatter("development", commit, "Lite API compatibility", "Added and removed Lite API paths compared with the released baseline.") + f"""# Lite API compatibility

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

{baseline}

## Added paths
{chr(10).join(f'- `{path}`' for path in added) or '- None'}

## Removed paths
{chr(10).join(f'- `{path}`' for path in removed) or '- None'}

Removal, required-field, nullable, and enum changes must be reviewed before replacing `lite-openapi.previous.json`.
"""
    usage = generated_frontmatter("development", commit, "Frontend API usage", "Frontend Lite route usage compared with the generated FastAPI contract.") + f"""# Frontend API usage

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

## Unsupported frontend route references
{chr(10).join(f'- `{path}`' for path in unsupported) or '- None'}

## Backend Lite routes with no detected frontend consumer
{chr(10).join(f'- `{path}`' for path in unused[:120]) or '- None'}

The second list is informational: worker callbacks, diagnostics, compatibility aliases, and user-only endpoints may intentionally have no normal UI consumer.
"""
    # Detailed frontend ownership and field-level compatibility are generated by
    # generate_platform_catalogs.py. Keep this generator authoritative for the
    # OpenAPI contract, fixtures, and the existing API summary only.
    return {API_DOC: api}


def build_outputs() -> dict[Path, str]:
    commit = source_commit()
    schema = export_openapi()
    outputs = {OPENAPI_OUT: stable_json(schema)}
    outputs.update(fixture_outputs(commit))
    outputs.update(contract_docs(schema, commit))
    return outputs


def apply_outputs(outputs: dict[Path, str]) -> None:
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_outputs(outputs: dict[Path, str]) -> int:
    drift: list[str] = []
    for path, content in outputs.items():
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            drift.append(path.relative_to(ROOT).as_posix())
    if drift:
        print("Generated Lite contract drift detected:")
        for item in drift:
            print(f" - {item}")
        return 1
    schema = json.loads(outputs[OPENAPI_OUT])
    backend = set(schema.get("paths", {}))
    unsupported = sorted(path for path in frontend_paths() if not any(path_matches(path, route) for route in backend))
    if unsupported:
        print("Unsupported frontend Lite API references:")
        for path in unsupported:
            print(f" - {path}")
        return 1
    print(f"PASS Lite OpenAPI, {sum(len(v) for v in SCENARIOS.values())} fixtures, and frontend route usage are current")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "check"])
    args = parser.parse_args()
    outputs = build_outputs()
    if args.command == "generate":
        apply_outputs(outputs)
        print(f"Generated {len(outputs)} Lite contract/fixture artifacts")
        return 0
    return check_outputs(outputs)


if __name__ == "__main__":
    raise SystemExit(main())
