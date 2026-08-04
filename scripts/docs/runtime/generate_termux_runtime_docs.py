#!/usr/bin/env python3
"""Generate tracked contracts and MkDocs pages from the promoted sanitized baseline only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from runtime_architecture_verifier import verify_runtime_components
from runtime_common import (
    BASELINE_PATH,
    BASELINE_SCHEMA_PATH,
    ROOT,
    atomic_write,
    read_json,
    stable_json,
    validate_json,
)
from runtime_redaction import assert_safe

GENERATOR = "scripts/docs/runtime/generate_termux_runtime_docs.py"
GENERATED_CONTRACT_ROOT = ROOT / "contracts" / "generated" / "runtime"
DEV_PAGE = ROOT / "docs" / "generated" / "development" / "runtime-verification.md"
PROD_ROOT = ROOT / "docs" / "generated" / "production"
SOURCE_COMMIT = os.environ.get("SOURCE_COMMIT", "").strip() or "uncommitted"
SOURCE_GENERATED_AT = os.environ.get("SOURCE_GENERATED_AT", "").strip() or "uncommitted"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def envelope(kind: str, payload: Any, baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "metadata": {
            "schema_revision": 1,
            "generated": True,
            "generated_at": SOURCE_GENERATED_AT,
            "source_commit": SOURCE_COMMIT,
            "generator": GENERATOR,
            "generator_version": 1,
            "promoted_baseline": BASELINE_PATH.relative_to(ROOT).as_posix(),
            "promoted_baseline_sha256": sha256(BASELINE_PATH),
            "promoted_semantic_fingerprint": baseline["semantic_fingerprint"],
            "validation_state": "generated",
        },
        kind: payload,
    }


def frontmatter(title: str, description: str, audience: str, state: str) -> str:
    status = "verified" if state == "verified" else "unvalidated"
    return (
        "---\n"
        f"title: {json.dumps(title)}\n"
        f"description: {json.dumps(description)}\n"
        f"audience: {audience}\n"
        f"status: {status}\n"
        "generated: true\n"
        f"generated_at: {SOURCE_GENERATED_AT}\n"
        f"source_commit: {SOURCE_COMMIT}\n"
        f"generator: {GENERATOR}\n"
        "generator_version: 1\n"
        "schema_revision: 1\n"
        f"validation_status: {state}\n"
        "---\n\n"
        '<div class="pl-page-meta">'
        '<span class="pl-status pl-status--verified">Source-derived</span>'
        f'<span class="pl-status pl-status--{status}">{state.replace("-", " ").title()}</span>'
        "</div>\n\n"
    )


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    def cell(value: Any) -> str:
        if isinstance(value, bool):
            value = "yes" if value else "no"
        return str(value if value is not None else "—").replace("|", "\\|").replace("\n", "<br>")
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def runtime_state_label(state: str) -> str:
    return {
        "verified": "Promoted runtime verified",
        "mismatch": "Runtime mismatch",
        "partial": "Locally unvalidated or partial",
        "unavailable": "Runtime evidence unavailable",
    }.get(state, "Runtime evidence unavailable")


def build_outputs() -> dict[Path, str]:
    baseline = read_json(BASELINE_PATH)
    validate_json(baseline, BASELINE_SCHEMA_PATH)
    assert_safe(baseline, context="promoted Termux runtime baseline")
    state = baseline["verification"]["runtime_verification_state"]
    services = baseline["services"]
    service_by_id = {item["id"]: item for item in services}
    routes = baseline["routes"]
    route_by_id = {item["id"]: item for item in routes}
    listeners = baseline["listeners"]
    apps = baseline["runtime_apps"]
    messaging = baseline["messaging"]
    remote_access = baseline["remote_access"]
    datastores = baseline["datastores"]
    relationships = baseline["runtime_relationships"]
    architecture = verify_runtime_components()

    outputs: dict[Path, str] = {}
    outputs[GENERATED_CONTRACT_ROOT / "termux-platform.json"] = stable_json(envelope("termux_platform", {
        "host_role": baseline["host_role"],
        "platform": baseline["platform"],
        "verification": baseline["verification"],
    }, baseline))
    outputs[GENERATED_CONTRACT_ROOT / "pm2-topology.json"] = stable_json(envelope("pm2_topology", {
        "services": [item for item in services if item["execution_owner"] in {"PM2", "PM2 / PROot Ubuntu"}],
        "classification": state,
    }, baseline))
    outputs[GENERATED_CONTRACT_ROOT / "caddy-routing.json"] = stable_json(envelope("caddy_routing", {
        "proxy": service_by_id.get("caddy"),
        "routes": routes,
        "classification": state,
    }, baseline))
    outputs[GENERATED_CONTRACT_ROOT / "nats-topology.json"] = stable_json(envelope("nats_topology", {
        "service": service_by_id.get("nats"),
        "listeners": listeners,
        "messaging": messaging,
        "classification": state,
    }, baseline))
    outputs[GENERATED_CONTRACT_ROOT / "remote-access.json"] = stable_json(envelope("remote_access", {
        "daemon": service_by_id.get("tailscaled"),
        "route": route_by_id.get("remote-access"),
        "readiness": remote_access,
        "classification": state,
    }, baseline))
    outputs[GENERATED_CONTRACT_ROOT / "agent-supervisor.json"] = stable_json(envelope("agent_supervisor", {
        "agent": service_by_id.get("node-agent"),
        "core_supervisor": service_by_id.get("core-supervisor"),
        "nats": service_by_id.get("nats"),
        "relationships": relationships,
        "classification": state,
    }, baseline))
    outputs[GENERATED_CONTRACT_ROOT / "sqlite-runtime.json"] = stable_json(envelope("sqlite_runtime", {
        "service": service_by_id.get("sqlite"),
        "datastores": datastores,
        "classification": state,
    }, baseline))
    outputs[GENERATED_CONTRACT_ROOT / "proot-apps.json"] = stable_json(envelope("proot_apps", {
        "container": service_by_id.get("proot-ubuntu"),
        "applications": apps,
        "routes": [item for item in routes if item["route_kind"] == "managed-app"],
        "classification": state,
    }, baseline))
    outputs[GENERATED_CONTRACT_ROOT / "architecture-runtime-verification.json"] = stable_json(
        envelope("architecture_runtime_verification", architecture, baseline)
    )

    service_rows = [
        [item["logical_role"], item["presence"], item["status"], item["runtime_type"], item["expected_source_match"]]
        for item in services
    ]
    route_rows = [
        [item["route_kind"], item["presence"], item["https_owner"], item["https_mode"], item["route_order"], item["upstream_kind"], item["peer_reachability"]]
        for item in routes
    ]
    datastore_rows = [
        [item["role"], item["presence"], item["integrity"], item["journal_mode"], item["expected_tables_present"], item["schema_revision"]]
        for item in datastores
    ]
    relationship_rows = [
        [item["agent_presence"], item["supervisor_presence"], item["worker_command_owner_presence"], item["nats_connectivity"], item["recovery_capability"], item["last_evidence_freshness_bucket"]]
        for item in relationships
    ]
    architecture_rows = [
        [item["component_name"], item["classification"], item["runtime_evidence_state"]]
        for item in architecture["components"] if item["runtime_selector"]
    ]

    outputs[DEV_PAGE] = frontmatter(
        "Termux runtime verification",
        "Development-only WSL2 SSH capture, redaction, promotion, and runtime/source comparison workflow.",
        "development",
        state,
    ) + f"""# Termux runtime verification

**Current classification:** {runtime_state_label(state)}.

Documentation truth combines repository source, an explicitly promoted sanitized runtime baseline, and browser validation. Local live captures under `.pocketlab-dev` never become tracked documentation inputs automatically.

## Three-layer evidence model

| Layer | Location | Tracked | Used by normal checks |
| --- | --- | --- | --- |
| Raw transient capture | `.pocketlab-dev/runtime-captures/<capture-id>/raw/` | no | no |
| Sanitized local projection | `.pocketlab-dev/runtime-captures/<capture-id>/sanitized/` | no | no |
| Explicit promoted baseline | `architecture/runtime-baselines/server-phone.json` | yes | yes |

## Safe workflow

```bash
bash scripts/docs/runtime/setup_termux_ssh.sh --prepare-key
bash scripts/docs/runtime/setup_termux_ssh.sh --check
bash scripts/docs/runtime/capture_termux_runtime.sh
python3 scripts/docs/runtime/promote_termux_runtime.py inspect
python3 scripts/docs/runtime/promote_termux_runtime.py validate
python3 scripts/docs/runtime/promote_termux_runtime.py diff
LITE_RUNTIME_PROMOTE=1 python3 scripts/docs/runtime/promote_termux_runtime.py promote
python3 scripts/docs/runtime/generate_termux_runtime_docs.py generate
```

The streamed phone probe is read-only, allowlisted, bounded, and uses one SSH connection. Each probe has a fixed ID, capability requirement, timeout, output cap, parser, sanitizer, required/optional state, and semantic failure class. It does not install packages, restart processes, read secret files, copy databases, query live rows, collect raw logs, or scan user media.

## Canonical architecture comparison

{md_table(["Canonical component", "Classification", "Runtime evidence"], architecture_rows)}

Browser-state libraries remain source/browser verified: TanStack Query owns live safe FastAPI cache, Dexie owns safe fallback snapshots, Zustand owns harmless UI coordination, and XState owns guided workflow state. Termux runtime evidence is not authoritative for browser IndexedDB or UI state.
"""

    outputs[PROD_ROOT / "android-termux-runtime.md"] = frontmatter(
        "Android and Termux runtime verification",
        "Sanitized promoted evidence for the Pocket Lab Lite Android/Termux server runtime.",
        "production",
        state,
    ) + f"""# Android and Termux runtime verification

**Current classification:** {runtime_state_label(state)}.

The canonical architecture remains authoritative for what Pocket Lab Lite is designed to contain. Promoted runtime evidence verifies current claims when available; an unavailable phone does not imply that a canonical component is missing.

## Platform

| Field | Classification |
| --- | --- |
| Platform | {baseline['platform']['platform']} |
| Android release | {baseline['platform']['android_release_major']} |
| Architecture | {baseline['platform']['architecture_family']} |
| ABI | {baseline['platform']['abi_family']} |
| Termux prefix | {baseline['platform']['termux_prefix_type']} |

## Runtime services

{md_table(["Role", "Presence", "Status", "Runtime", "Source match"], service_rows)}

## SQLite runtime metadata

{md_table(["Role", "Presence", "Integrity", "Journal", "Expected tables", "Schema revision"], datastore_rows)}

## Agent and supervisor relationship

{md_table(["Agent", "Supervisor", "Command owner", "NATS", "Recovery", "Evidence freshness"], relationship_rows)}

No hostname, username, private address, Tailnet name, certificate path, PID, exact memory, uptime, restart timestamp, database row, media filename, or user path is retained in this page.
"""

    outputs[PROD_ROOT / "services-pm2-runtime.md"] = frontmatter(
        "Services and PM2 runtime verification",
        "Sanitized process-presence and ownership evidence for Pocket Lab Lite services.",
        "production",
        state,
    ) + f"""# Services and PM2 runtime verification

**Current classification:** {runtime_state_label(state)}.

PM2 evidence is normalized to logical role, presence, status, runtime type, execution owner, restart bucket, memory bucket, and repository expectation match. Full command lines and PM2 environments are never retained.

{md_table(["Role", "Presence", "Status", "Runtime", "Source match"], service_rows)}

A stopped, disconnected, repairing, and unavailable service are distinct states. Runtime evidence does not authorize automatic restart or repair from documentation tooling.
"""

    outputs[PROD_ROOT / "remote-access-runtime.md"] = frontmatter(
        "Remote access runtime verification",
        "Sanitized Tailscale, Caddy, NATS, and app-route runtime evidence.",
        "production",
        state,
    ) + f"""# Remote access runtime verification

**Current classification:** {runtime_state_label(state)}.

{md_table(["Route", "Presence", "HTTPS owner", "HTTPS mode", "Order", "Upstream kind", "Peer reachability"], route_rows)}

| Runtime check | Classification |
| --- | --- |
| Tailscale command variant | {remote_access['command_variant']} |
| Daemon running | {remote_access['daemon_running']} |
| Tailnet IPv4 ready | {remote_access['ipv4_ready']} |
| Private connectivity ready | {remote_access['private_connectivity_ready']} |
| Peer reachability | {remote_access['peer_reachability']} |
| NATS listener | {messaging['client_listener_presence']} |
| NATS bind scope | {messaging['bind_scope']} |
| JetStream | {messaging['jetstream_state']} |

Remote access evidence stores readiness classifications only. It never stores a Tailscale IP, LAN IP, FQDN, Tailnet name, peer name, login, node key, control URL, certificate path, or certificate content.

When evidence is unavailable, the product and documentation use **Remote access not ready** or **runtime evidence unavailable** rather than inferring that Tailscale, Caddy, or the managed app is absent from the canonical architecture.
"""

    for path, content in outputs.items():
        assert_safe(content, context=f"generated runtime artifact {path.relative_to(ROOT)}")
    return outputs


def write_outputs(outputs: dict[Path, str]) -> None:
    for path, content in sorted(outputs.items(), key=lambda item: item[0].as_posix()):
        atomic_write(path, content, mode=0o644)


def check_outputs(outputs: dict[Path, str]) -> int:
    drift = []
    for path, content in sorted(outputs.items(), key=lambda item: item[0].as_posix()):
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            drift.append(path.relative_to(ROOT).as_posix())
    if drift:
        print("Generated Termux runtime documentation drift:")
        for item in drift:
            print(f" - {item}")
        return 1
    print(f"PASS {len(outputs)} promoted-runtime documentation artifacts are current and safe")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "check"])
    args = parser.parse_args()
    outputs = build_outputs()
    if args.command == "generate":
        write_outputs(outputs)
        print(f"Generated {len(outputs)} Termux runtime documentation artifacts")
        return 0
    return check_outputs(outputs)


if __name__ == "__main__":
    raise SystemExit(main())
