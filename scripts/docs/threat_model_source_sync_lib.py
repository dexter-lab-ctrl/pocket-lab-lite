#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]

STRUCTURIZR = ROOT / "architecture/structurizr/workspace.dsl"
OPENAPI = ROOT / "contracts/generated/openapi.json"
ASYNCAPI = ROOT / "contracts/asyncapi/pocketlab-nats-jetstream.yaml"
TYPED_OPERATIONS = ROOT / "contracts/operations/pocketlab-typed-operations.json"
OPERATIONS_DIR = ROOT / "operations"
THREAT_MODEL = ROOT / "threat-model/pocketlab-threat-model.yaml"
SYNC_MANIFEST = ROOT / "threat-model/pocketlab-threat-model-sync-manifest.json"
SYNC_DOC = ROOT / "docs/security/generated/threat-model/source-synchronization.md"

REQUIRED_OPERATION_SECURITY_FIELDS = [
    "data_classification",
    "stride",
    "trust_boundaries",
    "attack_surfaces",
    "mitigations",
    "residual_risks",
    "evidence",
]

REQUIRED_TIER5B_VIEWS = [
    "security-review",
    "nats-command-event-boundaries",
    "audit-and-dlq-paths",
]

MUTATING_METHODS = {"post", "put", "patch", "delete"}

RETIRED_PATTERNS = [
    "legacy" + "_" + "intent",
    "sync" + "_" + "bash",
    "tofu" + "_" + "deploy",
    "/" + "api" + "/" + "action" + "/" + "update",
    "dashboard" + "_" + "api",
]


@dataclass(frozen=True)
class Finding:
    severity: str
    source: str
    code: str
    message: str
    remediation: str


@dataclass(frozen=True)
class FileDigest:
    path: str
    sha256: str
    bytes: int


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_digest(path: Path) -> FileDigest:
    return FileDigest(path=rel(path), sha256=sha256_file(path), bytes=path.stat().st_size)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def normalize_name(value: Any) -> str:
    return str(value or "").strip()


def normalize_method(value: Any) -> str:
    return str(value or "").strip().lower()


def endpoint_key(method: str, path: str) -> str:
    return f"{method.upper()} {path}"


def extract_structurizr_inventory() -> dict[str, Any]:
    text = STRUCTURIZR.read_text(encoding="utf-8")

    elements: list[dict[str, str]] = []
    relationships: list[dict[str, str]] = []
    views: list[str] = []

    element_re = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(softwareSystem|container|component|person)\s+"([^"]+)"')
    relationship_re = re.compile(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*->\s*([A-Za-z_][A-Za-z0-9_]*)\s+"([^"]*)"')
    view_re = re.compile(r'^\s*(systemContext|container|component|deployment|dynamic)\s+[^\s]+\s+"?([A-Za-z0-9_.:-]+)"?')

    for line in text.splitlines():
        element_match = element_re.match(line)
        if element_match:
            element_id, element_type, name = element_match.groups()
            elements.append({"id": element_id, "type": element_type, "name": name})
            continue

        relationship_match = relationship_re.match(line)
        if relationship_match:
            source, target, description = relationship_match.groups()
            relationships.append({"source": source, "target": target, "description": description})
            continue

        view_match = view_re.match(line)
        if view_match:
            _view_type, key = view_match.groups()
            views.append(key)

    return {
        "path": rel(STRUCTURIZR),
        "views": sorted(set(views)),
        "tier5b_views_present": {view: view in text for view in REQUIRED_TIER5B_VIEWS},
        "elements": elements,
        "relationships": relationships,
        "digest": file_digest(STRUCTURIZR).__dict__,
    }


def extract_openapi_inventory() -> dict[str, Any]:
    data = read_json(OPENAPI)
    endpoints: list[dict[str, Any]] = []

    for path, path_item in sorted((data.get("paths") or {}).items()):
        if not isinstance(path_item, dict):
            continue
        for method, operation in sorted(path_item.items()):
            method_l = normalize_method(method)
            if method_l not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            operation = operation or {}
            endpoints.append(
                {
                    "key": endpoint_key(method_l, path),
                    "method": method_l.upper(),
                    "path": path,
                    "operationId": operation.get("operationId", ""),
                    "summary": operation.get("summary", ""),
                    "tags": operation.get("tags", []),
                    "mutating": method_l in MUTATING_METHODS,
                    "security_defined": bool(operation.get("security") or data.get("security")),
                }
            )

    return {
        "path": rel(OPENAPI),
        "title": data.get("info", {}).get("title", ""),
        "version": data.get("info", {}).get("version", ""),
        "endpoint_count": len(endpoints),
        "mutating_endpoint_count": sum(1 for item in endpoints if item["mutating"]),
        "endpoints": endpoints,
        "digest": file_digest(OPENAPI).__dict__,
    }


def channel_action(channel: dict[str, Any]) -> list[str]:
    actions = []
    for key in ["publish", "subscribe"]:
        if key in channel:
            actions.append(key)
    return actions


def extract_asyncapi_inventory() -> dict[str, Any]:
    data = read_yaml(ASYNCAPI)
    channels: list[dict[str, Any]] = []

    for name, channel in sorted((data.get("channels") or {}).items()):
        channel = channel or {}
        channels.append(
            {
                "name": str(name),
                "actions": channel_action(channel),
                "description": channel.get("description", ""),
                "has_publish": "publish" in channel,
                "has_subscribe": "subscribe" in channel,
            }
        )

    return {
        "path": rel(ASYNCAPI),
        "title": data.get("info", {}).get("title", ""),
        "version": data.get("info", {}).get("version", ""),
        "channel_count": len(channels),
        "channels": channels,
        "digest": file_digest(ASYNCAPI).__dict__,
    }


def walk_values(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from walk_values(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_values(item)


def operation_name_from_record(record: dict[str, Any]) -> str:
    for key in ["operation", "name", "id", "operationId"]:
        if record.get(key):
            return normalize_name(record.get(key))
    metadata = record.get("metadata") or {}
    if isinstance(metadata, dict):
        for key in ["name", "id"]:
            if metadata.get(key):
                return normalize_name(metadata.get(key))
    return ""


def listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def extract_api_entrypoints(record: dict[str, Any]) -> list[str]:
    values: list[Any] = []
    for key in ["api_entrypoints", "apiEntrypoints", "api", "endpoints"]:
        values.extend(listify(record.get(key)))
    spec = record.get("spec") or {}
    if isinstance(spec, dict):
        for key in ["api_entrypoints", "apiEntrypoints", "api", "endpoints"]:
            values.extend(listify(spec.get(key)))
    result = []
    for item in values:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            method = item.get("method") or item.get("verb")
            path = item.get("path") or item.get("url")
            if method and path:
                result.append(endpoint_key(str(method), str(path)))
            elif path:
                result.append(str(path))
    return sorted(set(result))


def extract_nats_subject(record: dict[str, Any]) -> str:
    for key in ["nats_subject", "natsSubject", "subject", "channel"]:
        if record.get(key):
            return normalize_name(record.get(key))
    spec = record.get("spec") or {}
    if isinstance(spec, dict):
        for key in ["nats_subject", "natsSubject", "subject", "channel"]:
            if spec.get(key):
                return normalize_name(spec.get(key))
    return ""


def extract_typed_operations_inventory() -> dict[str, Any]:
    data = read_json(TYPED_OPERATIONS)
    records: dict[str, dict[str, Any]] = {}

    candidate_lists: list[Any] = []
    if isinstance(data.get("operations"), list):
        candidate_lists.append(data.get("operations"))
    if isinstance(data.get("operations"), dict):
        candidate_lists.append(list(data.get("operations", {}).values()))

    for value in walk_values(data):
        if isinstance(value, list):
            possible = [item for item in value if isinstance(item, dict) and operation_name_from_record(item)]
            if possible:
                candidate_lists.append(possible)

    for candidate_list in candidate_lists:
        for item in candidate_list or []:
            if not isinstance(item, dict):
                continue
            name = operation_name_from_record(item)
            if not name:
                continue
            records[name] = {
                "name": name,
                "nats_subject": extract_nats_subject(item),
                "api_entrypoints": extract_api_entrypoints(item),
                "raw_keys": sorted(item.keys()),
            }

    return {
        "path": rel(TYPED_OPERATIONS),
        "operation_count": len(records),
        "operations": [records[key] for key in sorted(records)],
        "digest": file_digest(TYPED_OPERATIONS).__dict__,
    }


def extract_operation_metadata_inventory() -> dict[str, Any]:
    operations: list[dict[str, Any]] = []

    for path in sorted(OPERATIONS_DIR.glob("*.yaml")):
        data = read_yaml(path)
        metadata = data.get("metadata") or {}
        spec = data.get("spec") or {}
        security = data.get("security") or {}
        name = normalize_name(metadata.get("name") or path.stem)
        operations.append(
            {
                "name": name,
                "path": rel(path),
                "title": metadata.get("title", name),
                "tags": metadata.get("tags", []),
                "nats_subject": extract_nats_subject({"spec": spec}) or extract_nats_subject(data),
                "api_entrypoints": extract_api_entrypoints({"spec": spec}) or extract_api_entrypoints(data),
                "security_fields_present": sorted(key for key in REQUIRED_OPERATION_SECURITY_FIELDS if security.get(key)),
                "security_fields_missing": sorted(key for key in REQUIRED_OPERATION_SECURITY_FIELDS if not security.get(key)),
                "data_classification": security.get("data_classification", ""),
                "stride": security.get("stride", []),
                "trust_boundaries": security.get("trust_boundaries", []),
                "attack_surfaces": security.get("attack_surfaces", []),
                "mitigations": security.get("mitigations", []),
                "residual_risks": security.get("residual_risks", []),
                "evidence": security.get("evidence", []),
                "digest": file_digest(path).__dict__,
            }
        )

    return {
        "path": rel(OPERATIONS_DIR),
        "operation_metadata_count": len(operations),
        "operations": operations,
    }


def subject_matches(declared: str, channel: str) -> bool:
    if not declared:
        return False
    if declared == channel:
        return True
    # Lightweight NATS wildcard handling for generated checks.
    pattern = re.escape(declared).replace(r"\*", r"[^.]+")
    pattern = pattern.replace(r"\>", r".*")
    return re.fullmatch(pattern, channel) is not None


def endpoint_matches(declared: str, endpoint: dict[str, Any]) -> bool:
    if not declared:
        return False
    declared = declared.strip()
    if declared == endpoint["key"] or declared == endpoint["path"]:
        return True
    parts = declared.split(maxsplit=1)
    if len(parts) == 2:
        return parts[0].upper() == endpoint["method"] and parts[1] == endpoint["path"]
    return False


def build_findings(
    structurizr: dict[str, Any],
    openapi: dict[str, Any],
    asyncapi: dict[str, Any],
    typed_operations: dict[str, Any],
    operation_metadata: dict[str, Any],
) -> list[Finding]:
    findings: list[Finding] = []

    for view, present in structurizr["tier5b_views_present"].items():
        if not present:
            findings.append(
                Finding(
                    severity="error",
                    source="structurizr",
                    code="TIER5B_VIEW_MISSING",
                    message=f"Structurizr enterprise security-review view is missing: {view}",
                    remediation="Restore enterprise security-review Structurizr security views before regenerating threat model sync evidence.",
                )
            )

    metadata_by_name = {item["name"]: item for item in operation_metadata["operations"]}
    typed_by_name = {item["name"]: item for item in typed_operations["operations"]}

    for name in sorted(set(typed_by_name) - set(metadata_by_name)):
        findings.append(
            Finding(
                severity="error",
                source="typed_operations",
                code="TYPED_OPERATION_METADATA_MISSING",
                message=f"Typed operation has no operations/*.yaml metadata: {name}",
                remediation=f"Create operations/{name}.yaml with operation security metadata, then run task docs:threat-model:sync.",
            )
        )

    for op in operation_metadata["operations"]:
        if op["security_fields_missing"]:
            findings.append(
                Finding(
                    severity="error",
                    source="operations",
                    code="OPERATION_SECURITY_METADATA_INCOMPLETE",
                    message=f"Operation {op['name']} is missing security fields: {', '.join(op['security_fields_missing'])}",
                    remediation="Run task docs:operations:security:enrich, then manually review generated metadata for correctness.",
                )
            )

    channels = asyncapi["channels"]
    channel_names = [item["name"] for item in channels]
    endpoints = openapi["endpoints"]

    for op in operation_metadata["operations"]:
        declared_subject = op.get("nats_subject") or typed_by_name.get(op["name"], {}).get("nats_subject", "")
        if declared_subject and channel_names and not any(subject_matches(declared_subject, channel) for channel in channel_names):
            findings.append(
                Finding(
                    severity="warning",
                    source="asyncapi",
                    code="DECLARED_NATS_SUBJECT_NOT_IN_ASYNCAPI",
                    message=f"Operation {op['name']} declares NATS subject {declared_subject}, but it was not found in AsyncAPI channels.",
                    remediation="Regenerate AsyncAPI or correct the operation's natsSubject metadata.",
                )
            )

        declared_endpoints = op.get("api_entrypoints") or typed_by_name.get(op["name"], {}).get("api_entrypoints", [])
        for declared in declared_endpoints:
            if endpoints and not any(endpoint_matches(str(declared), endpoint) for endpoint in endpoints):
                findings.append(
                    Finding(
                        severity="warning",
                        source="openapi",
                        code="DECLARED_API_ENTRYPOINT_NOT_IN_OPENAPI",
                        message=f"Operation {op['name']} declares API entrypoint {declared}, but it was not found in OpenAPI paths.",
                        remediation="Regenerate OpenAPI or correct the operation's apiEntrypoints metadata.",
                    )
                )

    mapped_endpoint_keys = set()
    for op in operation_metadata["operations"]:
        declared_endpoints = op.get("api_entrypoints") or typed_by_name.get(op["name"], {}).get("api_entrypoints", [])
        for declared in declared_endpoints:
            for endpoint in endpoints:
                if endpoint_matches(str(declared), endpoint):
                    mapped_endpoint_keys.add(endpoint["key"])

    for endpoint in endpoints:
        if endpoint["mutating"] and endpoint["key"] not in mapped_endpoint_keys:
            findings.append(
                Finding(
                    severity="info",
                    source="openapi",
                    code="MUTATING_API_ENDPOINT_NOT_EXPLICITLY_MAPPED",
                    message=f"Mutating OpenAPI endpoint is not explicitly mapped to operation metadata: {endpoint['key']}",
                    remediation="Add apiEntrypoints to the relevant operations/*.yaml file if this endpoint triggers a typed operation.",
                )
            )

    mapped_subjects = set()
    for op in operation_metadata["operations"]:
        declared_subject = op.get("nats_subject") or typed_by_name.get(op["name"], {}).get("nats_subject", "")
        if not declared_subject:
            continue
        for channel in channel_names:
            if subject_matches(declared_subject, channel):
                mapped_subjects.add(channel)

    for channel in channel_names:
        if channel not in mapped_subjects:
            findings.append(
                Finding(
                    severity="info",
                    source="asyncapi",
                    code="ASYNCAPI_CHANNEL_NOT_EXPLICITLY_MAPPED",
                    message=f"AsyncAPI channel is not explicitly mapped to operation metadata: {channel}",
                    remediation="Add natsSubject to the relevant operations/*.yaml file if this channel is operation-owned.",
                )
            )

    return findings


def build_operation_source_links(
    openapi: dict[str, Any],
    asyncapi: dict[str, Any],
    typed_operations: dict[str, Any],
    operation_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    typed_by_name = {item["name"]: item for item in typed_operations["operations"]}
    endpoints = openapi["endpoints"]
    channels = asyncapi["channels"]
    channel_names = [item["name"] for item in channels]

    links: list[dict[str, Any]] = []
    for op in operation_metadata["operations"]:
        typed = typed_by_name.get(op["name"], {})
        declared_subject = op.get("nats_subject") or typed.get("nats_subject", "")
        declared_endpoints = op.get("api_entrypoints") or typed.get("api_entrypoints", [])

        linked_endpoints = [
            endpoint["key"]
            for endpoint in endpoints
            if any(endpoint_matches(str(declared), endpoint) for declared in declared_endpoints)
        ]
        linked_channels = [channel for channel in channel_names if declared_subject and subject_matches(declared_subject, channel)]

        links.append(
            {
                "operation": op["name"],
                "metadata_file": op["path"],
                "typed_operation_present": op["name"] in typed_by_name,
                "declared_api_entrypoints": declared_endpoints,
                "openapi_matches": linked_endpoints,
                "declared_nats_subject": declared_subject,
                "asyncapi_matches": linked_channels,
                "security_classification": op.get("data_classification", ""),
                "stride": op.get("stride", []),
            }
        )
    return links


def source_fingerprint(paths: list[Path]) -> str:
    payload = json.dumps([file_digest(path).__dict__ for path in paths], sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_sync_manifest() -> dict[str, Any]:
    for path in [STRUCTURIZR, OPENAPI, ASYNCAPI, TYPED_OPERATIONS, THREAT_MODEL]:
        if not path.exists():
            raise FileNotFoundError(f"Missing required source: {rel(path)}")

    structurizr = extract_structurizr_inventory()
    openapi = extract_openapi_inventory()
    asyncapi = extract_asyncapi_inventory()
    typed_operations = extract_typed_operations_inventory()
    operation_metadata = extract_operation_metadata_inventory()

    findings = build_findings(structurizr, openapi, asyncapi, typed_operations, operation_metadata)
    operation_links = build_operation_source_links(openapi, asyncapi, typed_operations, operation_metadata)

    source_paths = [STRUCTURIZR, OPENAPI, ASYNCAPI, TYPED_OPERATIONS, *sorted(OPERATIONS_DIR.glob("*.yaml"))]

    manifest: dict[str, Any] = {
        "apiVersion": "pocketlab.io/v1alpha1",
        "kind": "ThreatModelSourceSyncManifest",
        "metadata": {
            "name": "pocketlab-threat-model-source-sync",
            "tier": "6.9A",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "description": "Synchronizes threat-model evidence from Structurizr, OpenAPI, AsyncAPI, Typed Operations, and operation metadata.",
        },
        "source_fingerprint": source_fingerprint(source_paths),
        "sources": {
            "structurizr": structurizr,
            "openapi": openapi,
            "asyncapi": asyncapi,
            "typed_operations": typed_operations,
            "operation_metadata": operation_metadata,
        },
        "operation_source_links": operation_links,
        "findings": [finding.__dict__ for finding in findings],
        "finding_summary": {
            "error": sum(1 for finding in findings if finding.severity == "error"),
            "warning": sum(1 for finding in findings if finding.severity == "warning"),
            "info": sum(1 for finding in findings if finding.severity == "info"),
        },
        "validation_commands": [
            "task docs:threat-model:sync:check",
            "task docs:threat-model:check",
            "task docs:threat-model:drift",
            "mkdocs build --strict",
        ],
        "remediation_commands": [
            "task docs:api",
            "task docs:events",
            "task docs:operations",
            "task docs:architecture",
            "task docs:operations:security:enrich",
            "task docs:threat-model",
            "task docs:threat-model:sync",
        ],
    }

    rendered = json.dumps(manifest, sort_keys=True)
    found = [pattern for pattern in RETIRED_PATTERNS if pattern in rendered]
    if found:
        raise SystemExit("Source synchronization manifest contains retired identifiers.")

    return manifest
