#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
META_PATH = ROOT / "contracts/metadata/documentation-platform.json"
EXCEPTIONS_PATH = ROOT / "contracts/metadata/api-compatibility-exceptions.json"
OPENAPI_PATH = ROOT / "contracts/generated/lite-openapi.json"
GENERATED_CONTRACTS = ROOT / "contracts/generated"
DEV = ROOT / "docs/generated/development"
API_REFERENCE = ROOT / "docs/reference/api/lite-api.md"
SCHEMA_DIR = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/db/schema"
STORY_ROOT = ROOT / "src/lite"
SOURCE_GENERATED_AT = os.environ.get("SOURCE_GENERATED_AT", "").strip() or "uncommitted"
SOURCE_COMMIT = os.environ.get("SOURCE_COMMIT", "").strip() or "uncommitted"
GENERATOR = "scripts/docs/lite/generate_platform_catalogs.py"
SCHEMA_REVISION = 1
ABSOLUTE_PATH = re.compile(r"(?:/home/[^/\s]+|/tmp/|/mnt/[a-zA-Z]/|[A-Za-z]:\\Users\\)")
SECRET_VALUE = re.compile(
    r"(?:Bearer\s+[A-Za-z0-9._~+/=-]{8,}|-----BEGIN [^-]+PRIVATE KEY-----|"
    r"nats://[^\s/@:]+:[^\s/@]+@|tskey-[A-Za-z0-9_-]+)", re.I
)
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(paths: Iterable[Path]) -> tuple[dict[str, str], str]:
    values: dict[str, str] = {}
    for path in sorted({p.resolve() for p in paths if p.exists()}):
        values[path.relative_to(ROOT).as_posix()] = sha256_bytes(path.read_bytes())
    digest = hashlib.sha256()
    for name, value in sorted(values.items()):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(value.encode())
        digest.update(b"\n")
    return values, digest.hexdigest()


def json_envelope(kind: str, payload: Any, sources: Iterable[Path], *, baseline: Any = None,
                  validation_state: str = "generated") -> dict[str, Any]:
    source_values, aggregate = fingerprint([Path(__file__), *list(sources)])
    return {
        "metadata": {
            "generated": True,
            "kind": kind,
            "generated_at": SOURCE_GENERATED_AT,
            "source_commit": SOURCE_COMMIT,
            "generator": GENERATOR,
            "generator_version": 1,
            "schema_revision": SCHEMA_REVISION,
            "source_fingerprints": source_values,
            "aggregate_fingerprint": aggregate,
            "baseline_identity": baseline,
            "validation_state": validation_state,
        },
        kind: payload,
    }


def frontmatter(title: str, description: str, sources: Iterable[Path], *, status: str = "verified") -> str:
    _, aggregate = fingerprint(sources)
    return (
        "---\n"
        f"title: {json.dumps(title)}\n"
        f"description: {json.dumps(description)}\n"
        f"status: {status}\n"
        "generated: true\n"
        "audience: development\n"
        f"source_commit: {SOURCE_COMMIT}\n"
        f"generated_at: {SOURCE_GENERATED_AT}\n"
        f"generator: {GENERATOR}\n"
        "generator_version: 1\n"
        f"source_fingerprint: {aggregate}\n"
        "schema_revision: 1\n"
        "validation_status: generated\n"
        "---\n\n"
        '<div class="pl-page-meta" markdown>\n'
        f'<span class="pl-status pl-status--{status}">{status.replace("-", " ").title()}</span>\n'
        '<span class="pl-status pl-status--patch-provided">Source generated</span>\n'
        "</div>\n\n"
    )


def slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "item"


def md_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    def cell(value: Any) -> str:
        if isinstance(value, (list, tuple, set)):
            value = ", ".join(str(item) for item in value)
        if isinstance(value, bool):
            value = "yes" if value else "no"
        text = str(value if value is not None else "")
        return text.replace("|", "\\|").replace("\n", "<br>")
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    output.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(output) + "\n"


def metadata() -> dict[str, Any]:
    data = read_json(META_PATH)
    if not isinstance(data, dict):
        raise RuntimeError(f"Missing documentation metadata: {META_PATH.relative_to(ROOT)}")
    return data


def load_openapi() -> dict[str, Any]:
    if not OPENAPI_PATH.exists():
        raise RuntimeError("Run scripts/docs/lite/generate_contracts.py generate before the platform generators")
    return read_json(OPENAPI_PATH, {})


def schema_summary(schema: Any) -> str:
    if not isinstance(schema, dict):
        return "—"
    if "$ref" in schema:
        return f"`{schema['$ref'].rsplit('/', 1)[-1]}`"
    if "oneOf" in schema:
        return "oneOf(" + ", ".join(schema_summary(item) for item in schema["oneOf"]) + ")"
    if "anyOf" in schema:
        return "anyOf(" + ", ".join(schema_summary(item) for item in schema["anyOf"]) + ")"
    kind = schema.get("type") or "object"
    if kind == "array":
        return f"array[{schema_summary(schema.get('items', {}))}]"
    if schema.get("enum"):
        return f"{kind}: " + ", ".join(f"`{item}`" for item in schema["enum"])
    nullable = " nullable" if schema.get("nullable") or (isinstance(kind, list) and "null" in kind) else ""
    return f"`{kind}`{nullable}"


def openapi_outputs() -> dict[Path, str]:
    schema = load_openapi()
    sources = [OPENAPI_PATH, META_PATH]
    operations: list[dict[str, Any]] = []
    for path, path_item in sorted(schema.get("paths", {}).items()):
        for method, operation in sorted(path_item.items()):
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            parameters = []
            for item in [*(path_item.get("parameters") or []), *(operation.get("parameters") or [])]:
                parameters.append({
                    "name": item.get("name", ""),
                    "in": item.get("in", ""),
                    "required": bool(item.get("required")),
                    "schema": schema_summary(item.get("schema", {})),
                })
            body = operation.get("requestBody") or {}
            body_schemas = {
                content_type: schema_summary(content.get("schema", {}))
                for content_type, content in sorted((body.get("content") or {}).items())
            }
            responses = []
            for status, response in sorted((operation.get("responses") or {}).items()):
                response_schemas = {
                    content_type: schema_summary(content.get("schema", {}))
                    for content_type, content in sorted((response.get("content") or {}).items())
                }
                responses.append({"status": status, "description": response.get("description", ""), "schemas": response_schemas})
            operations.append({
                "path": path,
                "method": method.upper(),
                "operation_id": operation.get("operationId") or "",
                "summary": operation.get("summary") or "",
                "deprecated": bool(operation.get("deprecated")),
                "parameters": parameters,
                "request_required": bool(body.get("required")),
                "request_schemas": body_schemas,
                "responses": responses,
                "tags": operation.get("tags") or [],
            })
    parts = [frontmatter("Lite API reference", "Detailed source-generated FastAPI Lite HTTP operation reference.", sources),
             "# Lite API reference\n\n",
             "FastAPI OpenAPI is authoritative. The browser remains a same-origin client and never executes shell commands or talks directly to NATS.\n\n"]
    for item in operations:
        anchor = slug(f"{item['method']}-{item['path']}")
        parts.append(f'<a id="{anchor}"></a>\n## {item["method"]} `{item["path"]}`\n\n')
        parts.append(f"- Operation ID: `{item['operation_id'] or 'missing'}`\n")
        parts.append(f"- Summary: {item['summary'] or 'Not provided by FastAPI.'}\n")
        parts.append(f"- Deprecated: {'yes' if item['deprecated'] else 'no'}\n")
        parts.append(f"- Tags: {', '.join(f'`{tag}`' for tag in item['tags']) or 'None'}\n\n")
        if item["parameters"]:
            parts.append("### Parameters\n\n")
            parts.append(md_table(["Name", "Location", "Required", "Schema"],
                                  ([p["name"], p["in"], p["required"], p["schema"]] for p in item["parameters"])))
            parts.append("\n")
        if item["request_schemas"]:
            parts.append("### Request body\n\n")
            parts.append(md_table(["Content type", "Schema", "Required"],
                                  ([ct, sc, item["request_required"]] for ct, sc in item["request_schemas"].items())))
            parts.append("\n")
        parts.append("### Responses\n\n")
        parts.append(md_table(["Status", "Description", "Schema"],
                              ([r["status"], r["description"], ", ".join(f"{k}: {v}" for k, v in r["schemas"].items()) or "—"] for r in item["responses"])))
        parts.append("\n")
    return {API_REFERENCE: "".join(parts).rstrip() + "\n"}


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def normalize_frontend_route(raw: str) -> str:
    """Normalize a frontend route expression without inventing backend paths."""
    route = raw.strip()
    route = re.sub(r"\$\{(?:query|query\.toString\(\))\}", "", route)
    route = re.sub(r"\$\{[^}]+\}", "{param}", route)
    route = route.split("?", 1)[0]
    route = re.sub(r"(?:\{param\}){2,}", "{param}", route)
    return route.rstrip("/") or "/"


def lite_api_route_inventory(helper_text: str) -> dict[str, list[dict[str, Any]]]:
    """Extract route ownership from the exported liteApi object."""
    routes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    object_match = re.search(r"export\s+const\s+liteApi\s*=\s*\{", helper_text)
    if not object_match:
        return routes
    body = helper_text[object_match.end():]
    property_matches = list(re.finditer(r"^\s{2}([A-Za-z_$][A-Za-z0-9_$]*)\s*:", body, re.M))
    for index, match in enumerate(property_matches):
        name = match.group(1)
        end = property_matches[index + 1].start() if index + 1 < len(property_matches) else len(body)
        segment = body[match.start():end]
        for route_match in re.finditer(r"([`'\"])(/api/lite/.*?)(?:\1)", segment, re.S):
            route = normalize_frontend_route(route_match.group(2))
            prefix = segment[max(0, route_match.start() - 100):route_match.start()]
            suffix = segment[route_match.end():route_match.end() + 180]
            context = prefix + suffix
            if re.search(r"\bpostJson\s*\(", prefix):
                method = "POST"
            elif re.search(r"\bputJson\s*\(", prefix):
                method = "PUT"
            elif re.search(r"method\s*:\s*['\"]DELETE['\"]", context, re.I):
                method = "DELETE"
            elif re.search(r"method\s*:\s*['\"]PATCH['\"]", context, re.I):
                method = "PATCH"
            else:
                method = "GET"
            routes[name].append({
                "path": route,
                "method": method,
                "line": line_number(helper_text, object_match.end() + match.start()),
            })
    return routes


def frontend_inventory() -> tuple[list[dict[str, Any]], list[str], list[str]]:
    schema = load_openapi()
    backend_paths = sorted(schema.get("paths", {}))
    helper_routes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    helper_file = ROOT / "src/lib/liteApi.js"
    helper_text = helper_file.read_text(encoding="utf-8") if helper_file.exists() else ""
    export_matches = list(re.finditer(r"export\s+(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{", helper_text))
    for index, match in enumerate(export_matches):
        name = match.group(1)
        end = export_matches[index + 1].start() if index + 1 < len(export_matches) else len(helper_text)
        body = helper_text[match.end():end]
        for route_match in re.finditer(r"([`'\"])(/api/lite/.*?)(?:\1)", body, re.S):
            raw = normalize_frontend_route(route_match.group(2))
            window = body[max(0, route_match.start() - 240): route_match.end() + 240]
            method_match = re.search(r"method\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]", window, re.I)
            method = method_match.group(1).upper() if method_match else "GET"
            helper_routes[name].append({"path": raw, "method": method, "line": line_number(helper_text, match.start())})
    object_routes = lite_api_route_inventory(helper_text)
    inventory: list[dict[str, Any]] = []
    source_files = sorted([*ROOT.glob("src/**/*.js"), *ROOT.glob("src/**/*.jsx"), *ROOT.glob("src/**/*.ts"), *ROOT.glob("src/**/*.tsx")])
    for path in source_files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        relative = path.relative_to(ROOT).as_posix()
        if relative.endswith((".test.js", ".test.jsx", ".spec.js", ".spec.jsx", ".test.ts", ".spec.ts")):
            continue
        imported_helpers: set[str] = set()
        imports_lite_api = False
        for import_match in re.finditer(r"import\s*\{([^}]+)\}\s*from\s*['\"][^'\"]*liteApi\.js['\"]", text, re.S):
            names = {part.strip().split(" as ")[0].strip() for part in import_match.group(1).split(",") if part.strip()}
            imported_helpers.update(names)
            imports_lite_api = imports_lite_api or "liteApi" in names
        for helper in sorted(imported_helpers - {"liteApi"}):
            if re.search(rf"\b{re.escape(helper)}\s*\(", text):
                for route in helper_routes.get(helper, []):
                    inventory.append({
                        "source_module": relative,
                        "import_chain": [relative, "src/lib/liteApi.js"],
                        "owner": helper,
                        "route": route["path"],
                        "method": route["method"],
                        "usage": "query" if route["method"] == "GET" else "mutation",
                        "mocked": False,
                        "dynamic": "{param}" in route["path"],
                        "resolved": True,
                    })
        if imports_lite_api:
            for call in sorted(set(re.findall(r"\bliteApi\.([A-Za-z_$][A-Za-z0-9_$]*)\b", text))):
                for route in object_routes.get(call, []):
                    inventory.append({
                        "source_module": relative,
                        "import_chain": [relative, "src/lib/liteApi.js"],
                        "owner": f"liteApi.{call}",
                        "route": route["path"],
                        "method": route["method"],
                        "usage": "query" if route["method"] == "GET" else "mutation",
                        "mocked": False,
                        "dynamic": "{param}" in route["path"],
                        "resolved": True,
                    })
        # Direct route literals count only when they are used by an actual network
        # call or an MSW handler. Snapshot keys, tests, docs, and cache policy
        # constants are intentionally not classified as frontend API calls.
        for match in re.finditer(r"([`'\"])(/api/lite/.*?)(?:\1)", text, re.S):
            if relative == "src/lib/liteApi.js":
                continue
            raw = normalize_frontend_route(match.group(2))
            window = text[max(0, match.start() - 240):match.end() + 240]
            is_mock = relative.endswith("mocks/handlers.js") or bool(re.search(r"\bhttp\.(?:get|post|put|patch|delete)\s*\(", window))
            is_network = bool(re.search(r"\bfetch\s*\(", window))
            if not is_mock and not is_network:
                continue
            method_match = re.search(r"method\s*:\s*['\"](GET|POST|PUT|PATCH|DELETE)['\"]", window, re.I)
            if method_match:
                method = method_match.group(1).upper()
            else:
                handler_match = re.search(r"\bhttp\.(get|post|put|patch|delete)\s*\(", window, re.I)
                method = handler_match.group(1).upper() if handler_match else "GET"
            inventory.append({
                "source_module": relative,
                "import_chain": [relative],
                "owner": "MSW handler" if is_mock else "direct fetch",
                "route": raw,
                "method": method,
                "usage": "mock" if is_mock else ("query" if method == "GET" else "mutation"),
                "mocked": is_mock,
                "dynamic": "{param}" in raw,
                "resolved": True,
            })
    def matches(frontend: str, backend: str) -> bool:
        left = frontend.strip("/").split("/")
        right = backend.strip("/").split("/")
        if len(left) != len(right):
            return False
        return all(a == b or a.startswith("{") or b.startswith("{") for a, b in zip(left, right))
    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for item in inventory:
        key = (item["source_module"], item["method"], item["route"], item["owner"])
        unique[key] = item
    inventory = sorted(unique.values(), key=lambda value: (value["source_module"], value["route"], value["method"]))
    used = {item["route"] for item in inventory if not item["mocked"]}
    unsupported = sorted(route for route in used if not any(matches(route, backend) for backend in backend_paths))
    unused = sorted(route for route in backend_paths if route.startswith("/api/lite/") and not any(matches(frontend, route) for frontend in used))
    return inventory, unsupported, unused


def frontend_outputs() -> dict[Path, str]:
    inventory, unsupported, unused = frontend_inventory()
    sources = [OPENAPI_PATH, ROOT / "src/lib/liteApi.js", ROOT / "src/mocks/handlers.js", META_PATH, *STORY_ROOT.glob("*.jsx")]
    payload = {"modules": inventory, "unsupported_frontend_routes": unsupported, "unused_backend_routes": unused}
    envelope = json_envelope("frontend_api_usage", payload, sources)
    lines = [frontmatter("Frontend API usage", "Module-level frontend to FastAPI Lite route ownership and compatibility.", sources),
             "# Frontend API usage\n\n",
             md_table(["Source module", "Owner", "Method", "Route", "Kind", "Mocked", "Resolution"],
                      ([item["source_module"], item["owner"], item["method"], f'`{item["route"]}`', item["usage"], item["mocked"], "dynamic" if item["dynamic"] else "static"] for item in inventory)),
             "\n## Unsupported frontend route references\n\n",
             "\n".join(f"- `{value}`" for value in unsupported) or "- None",
             "\n\n## Backend Lite routes with no detected frontend consumer\n\n",
             "\n".join(f"- `{value}`" for value in unused) or "- None",
             "\n"]
    return {
        GENERATED_CONTRACTS / "frontend-api-usage.json": stable_json(envelope),
        DEV / "frontend-api-usage.md": "".join(lines),
    }


def canonical_schema(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: canonical_schema(item) for key, item in sorted(value.items()) if key not in {"title", "description", "example", "examples"}}
    if isinstance(value, list):
        return [canonical_schema(item) for item in value]
    return value



def schema_nullable(schema: Any) -> bool:
    if not isinstance(schema, dict):
        return False
    if schema.get("nullable") is True:
        return True
    value_type = schema.get("type")
    if isinstance(value_type, list) and "null" in value_type:
        return True
    for key in ("anyOf", "oneOf"):
        for option in schema.get(key, []) or []:
            if isinstance(option, dict) and option.get("type") == "null":
                return True
    return False

def compatibility_changes(current: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    current_paths, old_paths = current.get("paths", {}), baseline.get("paths", {})
    for path in sorted(set(current_paths) | set(old_paths)):
        if path not in old_paths:
            changes.append({"classification": "non_breaking", "kind": "path_added", "path": path})
            continue
        if path not in current_paths:
            changes.append({"classification": "breaking", "kind": "path_removed", "path": path})
            continue
        current_methods = {m for m in current_paths[path] if m.lower() in HTTP_METHODS}
        old_methods = {m for m in old_paths[path] if m.lower() in HTTP_METHODS}
        for method in sorted(current_methods - old_methods):
            changes.append({"classification": "non_breaking", "kind": "method_added", "path": path, "method": method.upper()})
        for method in sorted(old_methods - current_methods):
            changes.append({"classification": "breaking", "kind": "method_removed", "path": path, "method": method.upper()})
        for method in sorted(current_methods & old_methods):
            new_op, old_op = current_paths[path][method], old_paths[path][method]
            if bool(new_op.get("deprecated")) != bool(old_op.get("deprecated")):
                changes.append({
                    "classification": "breaking" if new_op.get("deprecated") else "non_breaking",
                    "kind": "deprecation_changed",
                    "path": path,
                    "method": method.upper(),
                    "before": bool(old_op.get("deprecated")),
                    "after": bool(new_op.get("deprecated")),
                })
            if canonical_schema(new_op.get("requestBody")) != canonical_schema(old_op.get("requestBody")):
                changes.append({"classification":"breaking","kind":"request_schema_changed","path":path,"method":method.upper()})
            new_responses = set((new_op.get("responses") or {}))
            old_responses = set((old_op.get("responses") or {}))
            for status in sorted(new_responses - old_responses):
                changes.append({"classification":"non_breaking","kind":"status_added","path":path,"method":method.upper(),"status":status})
            for status in sorted(old_responses - new_responses):
                changes.append({"classification":"breaking","kind":"status_removed","path":path,"method":method.upper(),"status":status})
            for status in sorted(new_responses & old_responses):
                if canonical_schema((new_op.get("responses") or {}).get(status)) != canonical_schema((old_op.get("responses") or {}).get(status)):
                    changes.append({"classification":"breaking","kind":"response_schema_changed","path":path,"method":method.upper(),"status":status})
    current_schemas = current.get("components", {}).get("schemas", {})
    old_schemas = baseline.get("components", {}).get("schemas", {})
    for name in sorted(set(current_schemas) | set(old_schemas)):
        if name not in old_schemas:
            changes.append({"classification":"non_breaking","kind":"schema_added","schema":name})
            continue
        if name not in current_schemas:
            changes.append({"classification":"breaking","kind":"schema_removed","schema":name})
            continue
        new, old = current_schemas[name], old_schemas[name]
        new_props, old_props = new.get("properties", {}), old.get("properties", {})
        new_required, old_required = set(new.get("required", [])), set(old.get("required", []))
        for field in sorted(set(new_props) | set(old_props)):
            if field not in old_props:
                changes.append({"classification":"breaking" if field in new_required else "non_breaking","kind":"field_added","schema":name,"field":field,"required":field in new_required})
            elif field not in new_props:
                changes.append({"classification":"breaking","kind":"field_removed","schema":name,"field":field})
            elif canonical_schema(new_props[field]) != canonical_schema(old_props[field]):
                old_enum = set(old_props[field].get("enum", [])) if isinstance(old_props[field], dict) else set()
                new_enum = set(new_props[field].get("enum", [])) if isinstance(new_props[field], dict) else set()
                if old_enum or new_enum:
                    for item in sorted(new_enum - old_enum, key=str):
                        changes.append({"classification":"non_breaking","kind":"enum_added","schema":name,"field":field,"value":item})
                    for item in sorted(old_enum - new_enum, key=str):
                        changes.append({"classification":"breaking","kind":"enum_removed","schema":name,"field":field,"value":item})
                old_nullable = schema_nullable(old_props[field])
                new_nullable = schema_nullable(new_props[field])
                if old_nullable != new_nullable:
                    changes.append({
                        "classification": "non_breaking" if new_nullable else "breaking",
                        "kind": "nullable_changed",
                        "schema": name,
                        "field": field,
                        "before": old_nullable,
                        "after": new_nullable,
                    })
                old_type = canonical_schema(old_props[field].get("type") if isinstance(old_props[field], dict) else None)
                new_type = canonical_schema(new_props[field].get("type") if isinstance(new_props[field], dict) else None)
                if old_type != new_type:
                    changes.append({"classification":"breaking","kind":"type_changed","schema":name,"field":field,"before":old_type,"after":new_type})
        for field in sorted(new_required - old_required):
            changes.append({"classification":"breaking","kind":"field_became_required","schema":name,"field":field})
        for field in sorted(old_required - new_required):
            changes.append({"classification":"non_breaking","kind":"field_became_optional","schema":name,"field":field})
    return changes


def compatibility_outputs() -> dict[Path, str]:
    current = load_openapi()
    meta = metadata()["api_baseline"]
    baseline_path = ROOT / meta["path"]
    baseline = read_json(baseline_path, None)
    baseline_identity = {
        "source_type": meta["source_type"],
        "path": meta["path"],
        "checksum": sha256_bytes(baseline_path.read_bytes()) if baseline_path.exists() else None,
        "status": "available" if baseline is not None else "missing",
    }
    changes = compatibility_changes(current, baseline) if isinstance(baseline, dict) else []
    exceptions = read_json(EXCEPTIONS_PATH, {"approved_breaking_changes": []})
    approved = {json.dumps(item, sort_keys=True) for item in exceptions.get("approved_breaking_changes", [])}
    for change in changes:
        change["approved"] = json.dumps({k:v for k,v in change.items() if k != "approved"}, sort_keys=True) in approved
    breaking = [item for item in changes if item["classification"] == "breaking" and not item.get("approved")]
    status = "unresolved" if baseline is None else ("breaking" if breaking else "compatible")
    payload = {"status": status, "baseline": baseline_identity, "changes": changes, "unapproved_breaking_changes": breaking}
    sources = [OPENAPI_PATH, META_PATH, EXCEPTIONS_PATH, *( [baseline_path] if baseline_path.exists() else [])]
    envelope = json_envelope("api_compatibility", payload, sources, baseline=baseline_identity, validation_state=status)
    lines = [frontmatter("Lite API compatibility", "Field-level compatibility against the explicitly configured released baseline.", sources, status="unvalidated" if status == "unresolved" else "verified"),
             "# Lite API compatibility\n\n",
             f"- Status: **{status}**\n- Baseline type: `{baseline_identity['source_type']}`\n- Baseline path: `{baseline_identity['path']}`\n- Baseline checksum: `{baseline_identity['checksum'] or 'missing'}`\n\n"]
    if baseline is None:
        lines.append("No released baseline contract is present. Release readiness must not claim compatibility until a verified baseline is supplied.\n")
    else:
        lines.append(md_table(["Classification", "Kind", "Location", "Approved"],
                              ([c["classification"], c["kind"], c.get("path") or c.get("schema") or "", c.get("approved", False)] for c in changes)) if changes else "No contract differences.\n")
    return {GENERATED_CONTRACTS / "api-compatibility.json": stable_json(envelope), DEV / "api-compatibility.md": "".join(lines)}


def subject_inventory() -> list[dict[str, Any]]:
    overrides = metadata().get("event_overrides", {})
    found: dict[str, dict[str, Any]] = {}
    for path in sorted((ROOT / "pocket-lab-final-structure/runtime").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        relative = path.relative_to(ROOT).as_posix()
        for match in re.finditer(r"pocketlab\.(?:commands|events|telemetry|health|agent|lite|workflows)[A-Za-z0-9_.{}:-]*", text):
            subject = match.group(0).rstrip(".,:;")
            window = text[max(0, match.start()-180):match.end()+180].lower()
            direction = "publish" if any(token in window for token in ("publish(", ".publish", "request(")) else "consume" if any(token in window for token in ("subscribe(", "pull_subscribe", "consumer")) else "reference"
            item = found.setdefault(subject, {
                "subject": subject,
                "domain": subject.split(".")[2] if len(subject.split(".")) > 2 else "unknown",
                "publisher": [], "consumer": [], "type": "event" if ".events." in subject else "command" if ".commands." in subject else "telemetry",
                "payload_schema": "incomplete", "retention": "incomplete", "stream": "incomplete", "durable": "incomplete",
                "deduplication_key": "incomplete", "correlation_id": "incomplete", "scope": "node or local workspace where encoded by the payload",
                "delivery": "incomplete", "retry": "incomplete", "security_classification": "internal metadata",
                "redacted_fields": [], "lifecycle_evidence": "incomplete", "sources": [], "completeness": "incomplete",
            })
            if relative not in item["sources"]:
                item["sources"].append(f"{relative}:{line_number(text, match.start())}")
            owner = Path(relative).name
            if direction == "publish" and owner not in item["publisher"]:
                item["publisher"].append(owner)
            if direction == "consume" and owner not in item["consumer"]:
                item["consumer"].append(owner)
    for subject, values in overrides.items():
        item = found.setdefault(subject, {"subject": subject, "sources": []})
        item.update(values)
        item.setdefault("payload_schema", "incomplete")
        item.setdefault("retention", "incomplete")
        item.setdefault("deduplication_key", "incomplete")
        item.setdefault("correlation_id", "incomplete")
        item.setdefault("scope", "local workspace")
        item.setdefault("sources", [])
        item["publisher"] = item.get("publisher") if isinstance(item.get("publisher"), list) else [item.get("publisher")]
        item["consumer"] = item.get("consumer") if isinstance(item.get("consumer"), list) else [item.get("consumer")]
        item["completeness"] = "verified-metadata"
    for item in found.values():
        item["publisher"] = sorted(filter(None, item.get("publisher", [])))
        item["consumer"] = sorted(filter(None, item.get("consumer", [])))
        item["sources"] = sorted(item.get("sources", []))
    return sorted(found.values(), key=lambda item: item["subject"])


def event_outputs() -> dict[Path, str]:
    events = subject_inventory()
    sources = [META_PATH, *list((ROOT / "pocket-lab-final-structure/runtime").rglob("*.py"))]
    channels = {}
    for item in events:
        channels[item["subject"]] = {
            "description": f"{item.get('domain','unknown')} {item.get('type','event')} subject",
            "x-pocketlab-domain": item.get("domain"),
            "x-pocketlab-publisher": item.get("publisher"),
            "x-pocketlab-consumer": item.get("consumer"),
            "x-pocketlab-stream": item.get("stream"),
            "x-pocketlab-durable": item.get("durable"),
            "x-pocketlab-delivery": item.get("delivery"),
            "x-pocketlab-retry": item.get("retry"),
            "x-pocketlab-security-classification": item.get("security_classification"),
            "x-pocketlab-redacted-fields": item.get("redacted_fields"),
            "x-pocketlab-source": item.get("sources"),
        }
    asyncapi = {
        "asyncapi": "2.6.0",
        "info": {"title":"Pocket Lab Lite events","version":"1.0.0","description":"Source-derived Lite-only NATS/JetStream subject catalog."},
        "defaultContentType":"application/json",
        "channels": channels,
        "x-pocketlab-metadata": json_envelope("metadata", {}, sources)["metadata"],
    }
    lines = [frontmatter("Lite NATS and event catalog", "Lite-only source-derived NATS/JetStream subjects, owners, delivery and safety metadata.", sources),
             "# Lite NATS and event catalog\n\n",
             "Missing delivery metadata is explicitly marked `incomplete`; the generator does not invent it.\n\n",
             md_table(["Subject", "Domain", "Type", "Publisher", "Consumer", "Stream / durable", "Completeness", "Source"],
                      ([f'`{e["subject"]}`', e.get("domain"), e.get("type"), e.get("publisher"), e.get("consumer"), f'{e.get("stream", "incomplete")} / {e.get("durable", "incomplete")}', e.get("completeness"), e.get("sources")] for e in events))]
    return {GENERATED_CONTRACTS / "lite-asyncapi.json": stable_json(asyncapi), DEV / "lite-events.md": "".join(lines)}


def capabilities_outputs() -> dict[Path, str]:
    data = metadata()
    sources = [META_PATH, ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_device_capabilities.py"]
    capabilities, roles = data["capabilities"], data["roles"]
    cap_json = json_envelope("device_capabilities", {"canonical_states": data["capability_states"], "capabilities": capabilities}, sources)
    role_json = json_envelope("device_roles", roles, sources)
    cap_md = frontmatter("Device capabilities", "Canonical Lite capability states, evidence, freshness and degraded behavior.", sources) + "# Device capabilities\n\n" + md_table(
        ["Capability", "Verification", "Freshness", "Expiry", "Degraded behavior", "Source"],
        ([f'`{item["name"]}`', item["verification_source"], item["freshness_seconds"], item["expiry_behavior"], item["degraded_behavior"], f'`{item["source"]}`'] for item in capabilities)
    ) + "\nCanonical states: " + ", ".join(f"`{state}`" for state in data["capability_states"]) + ".\n"
    role_md = frontmatter("Device roles", "Canonical Lite device role readiness and capability requirements.", sources) + "# Device roles\n\n" + md_table(
        ["Role", "Required capabilities", "Optional capabilities", "Readiness requirements", "Dependencies"],
        ([f'`{item["role"]}`', item["required_capabilities"], item["optional_capabilities"], item["readiness_requirements"], item["health_dependencies"]] for item in roles)
    )
    return {
        GENERATED_CONTRACTS / "device-capabilities.json": stable_json(cap_json),
        GENERATED_CONTRACTS / "device-roles.json": stable_json(role_json),
        DEV / "device-capabilities.md": cap_md,
        DEV / "device-roles.md": role_md,
    }


def story_inventory() -> list[dict[str, Any]]:
    mock_text = (ROOT / "src/mocks/handlers.js").read_text(encoding="utf-8", errors="ignore")
    mock_routes = sorted(set(re.findall(r"http\.(?:get|post|put|patch|delete)\(['\"]([^'\"]+)", mock_text)))
    result: list[dict[str, Any]] = []
    for path in sorted(STORY_ROOT.glob("*.stories.jsx")):
        text = path.read_text(encoding="utf-8")
        title_match = re.search(r"title:\s*['\"]([^'\"]+)", text)
        title = title_match.group(1) if title_match else path.stem
        for match in re.finditer(r"export const ([A-Za-z0-9_]+)\s*=\s*createLiteStory\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]", text):
            export_name, tab, fixture = match.groups()
            story_id = slug(f"{title}-{export_name}")
            result.append({
                "story_id": story_id,
                "story_title": f"{title}/{export_name}",
                "component": path.stem.replace(".stories", ""),
                "tab": tab,
                "viewport": ["mobile", "desktop"],
                "fixture": fixture,
                "canonical_expected_state": export_name,
                "api_endpoints_mocked": mock_routes,
                "query_keys": [tab],
                "xstate_state": "fixture-defined where the flow uses XState",
                "zustand_slice": "Lite UI-only store",
                "accessibility_result": "validated by Storybook/Playwright gate, not generated from source",
                "visual_baseline_result": "validated by explicit visual gate, not generated from source",
                "screenshot_path": f"docs/generated/ui/screenshots/{story_id}-{{viewport}}.png",
                "responsive_support": True,
                "offline_support": "fixture-dependent",
                "source": path.relative_to(ROOT).as_posix(),
            })
    return result


def ui_outputs() -> dict[Path, str]:
    stories = story_inventory()
    sources = [ROOT / "src/mocks/handlers.js", *STORY_ROOT.glob("*.stories.jsx"), ROOT / "scripts/docs/lite/capture-storybook.mjs"]
    payload = {"stories": stories, "screenshot_generation": {"command":"task lite:docs:ui:screenshots","deterministic":True,"status":"external-browser-gate"}}
    envelope = json_envelope("ui_state_catalog", payload, sources)
    md = frontmatter("UI state catalog", "Canonical Storybook-backed Lite product states and browser evidence hooks.", sources) + "# UI state catalog\n\n" + md_table(
        ["Story", "Tab", "Fixture", "Viewports", "Screenshot", "Offline"],
        ([f'`{s["story_id"]}`', s["tab"], f'`{s["fixture"]}`', s["viewport"], f'`{s["screenshot_path"]}`', s["offline_support"]] for s in stories)
    ) + "\nScreenshot files are produced by the existing WSL2-aware external Chrome resolver. A missing screenshot is not reported as PASS.\n"
    return {GENERATED_CONTRACTS / "ui-state-catalog.json": stable_json(envelope), DEV / "ui-state-catalog.md": md}


def recovery_outputs() -> dict[Path, str]:
    schema = load_openapi()
    endpoints = sorted(path for path in schema.get("paths", {}) if "/recovery" in path)
    source_files = [
        ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_backup.py",
        ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_restore_planner.py",
        ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_restore_transaction.py",
        ROOT / "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py",
        OPENAPI_PATH,
    ]
    lifecycle = {
        "backup": ["queued","running","succeeded","degraded","failed"],
        "verification": ["not_run","running","verified","failed"],
        "restore_preview": ["not_ready","running","ready","blocked","failed"],
        "checkpoint": ["not_created","creating","created","failed"],
        "restore": ["queued","running","validating","succeeded","rolled_back","failed"],
        "confirmation_required": ["restore_latest","destructive replacement"],
        "api_ownership": "FastAPI validates and publishes commands",
        "worker_ownership": "workers own backup, verification, checkpoint, restore, validation, and rollback",
        "endpoints": endpoints,
        "evidence": ["backup manifest","verification receipt","restore preview","checkpoint receipt","restore run","health result"],
        "projection_freshness": "prepared Recovery summary revision and stale metadata",
    }
    contract = json_envelope("recovery_contract", lifecycle, source_files)
    md = frontmatter("Recovery contract", "Authoritative source-derived Backup and Restore lifecycle and ownership contract.", source_files) + "# Recovery contract\n\n" + md_table(
        ["Lifecycle", "Canonical states"], ([name.replace("_", " ").title(), states] for name, states in lifecycle.items() if isinstance(states, list))
    ) + "\n## Ownership\n\n- API: FastAPI validates and admits requests.\n- Execution: workers own backup, verification, checkpoint, restore, post-restore health, and rollback.\n- Browser: display and confirmation only.\n"
    sm = frontmatter("Recovery state machine", "Generated Recovery lifecycle cross-reference for the Graphviz state-machine diagram.", source_files) + "# Recovery state machine\n\n![Recovery state machine](../../assets/diagrams/recovery-state-machine.light.svg#only-light)\n![Recovery state machine](../../assets/diagrams/recovery-state-machine.dark.svg#only-dark)\n"
    return {GENERATED_CONTRACTS / "recovery-contract.json": stable_json(contract), DEV / "recovery-contract.md": md, DEV / "recovery-state-machine.md": sm}


def security_outputs() -> dict[Path, str]:
    profiles = metadata()["security_profiles"]
    source = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_policy.py"
    sources = [META_PATH, source, ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security.py"]
    summary_semantics = {
        "main_summary": "latest completed Security posture with active-progress overlay where present",
        "saved_state": "read-only safe snapshot explicitly marked saved/stale",
        "partial_degraded": "coverage gaps and scanner availability remain explicit",
        "source": "security compact summary and canonical SQLite run state",
    }
    payload = {"profiles": profiles, "severity_model": ["critical","high","medium","low","info"], "summary_semantics": summary_semantics}
    envelope = json_envelope("security_profiles", payload, sources)
    md = frontmatter("Security profiles", "Canonical Quick, Full and App Check scope, tools, exclusions, ownership and stale behavior.", sources) + "# Security profiles\n\n" + md_table(
        ["Profile", "Default", "Tools", "Targets checked", "Targets skipped", "Freshness", "Unsupported behavior"],
        ([f'`{p["id"]}` — {p["label"]}', p["default"], p["tools"], p["targets_checked"], p["targets_skipped"], p["freshness_seconds"], p.get("unsupported_app_behavior", "not applicable")] for p in profiles)
    ) + "\n## Main summary semantics\n\n" + "\n".join(f"- **{key.replace('_',' ')}:** {value}" for key, value in summary_semantics.items()) + "\n"
    return {GENERATED_CONTRACTS / "security-profiles.json": stable_json(envelope), DEV / "security-profiles.md": md}


def sql_statements(text: str) -> Iterable[str]:
    buffer = ""
    for line in text.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            buffer = ""
            if statement:
                yield statement
    if buffer.strip():
        raise RuntimeError("Incomplete SQLite migration statement")


def build_empty_database(path: Path) -> list[Path]:
    migrations = sorted(SCHEMA_DIR.glob("*.sql"))
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        for migration in migrations:
            for statement in sql_statements(migration.read_text(encoding="utf-8")):
                try:
                    conn.execute(statement)
                except sqlite3.OperationalError as exc:
                    raise RuntimeError(f"Migration failed: {migration.name}: {exc}") from exc
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        for table in tables:
            conn.execute(f'DELETE FROM "{table.replace(chr(34), chr(34)*2)}"')
        conn.commit()
        for table in tables:
            count = conn.execute(f'SELECT COUNT(*) FROM "{table.replace(chr(34), chr(34)*2)}"').fetchone()[0]
            if count:
                raise RuntimeError(f"Temporary schema database is not data-free: {table}")
    finally:
        conn.close()
    return migrations


def inferred_sqlite_semantic(name: str, column_names: list[str]) -> dict[str, Any]:
    if name.startswith(("device_", "enrolled_")):
        domain, writer, readers = "devices", "device lifecycle and projection services", ["/api/lite/fleet", "/api/lite/devices/{device_id}"]
    elif name.startswith("app_"):
        domain, writer, readers = "apps", "App Catalog lifecycle and action services", ["/api/lite/catalog", "/api/lite/apps/{app_id}/actions"]
    elif name.startswith(("recovery_", "backup_")):
        domain, writer, readers = "recovery", "Recovery services and worker completion handlers", ["/api/lite/recovery", "/api/lite/recovery/details"]
    elif name.startswith("security_"):
        domain, writer, readers = "security", "Security store and scanner completion services", ["/api/lite/security/summary", "/api/lite/security/profiles/{profile}"]
    elif name.startswith(("projection_", "domain_revision")):
        domain, writer, readers = "projections", "prepared projection scheduler", ["/api/lite/diagnostics/runtime", "/api/lite/revisions"]
    elif name.startswith(("release_", "lite_installed_release")):
        domain, writer, readers = "release", "release runtime and identity services", ["/api/lite/release"]
    elif name.startswith("workflow_"):
        domain, writer, readers = "workflow", "workflow projection services", []
    elif name.startswith("audit_"):
        domain, writer, readers = "audit", "audit evidence indexing services", []
    elif name.startswith("phase3b_"):
        domain, writer, readers = "prepared_state", "prepared state projection services", ["/api/lite/status"]
    elif name == "schema_migrations":
        domain, writer, readers = "database", "SQLite migration runner", []
    else:
        domain, writer, readers = "control_plane", "source-defined control-plane service", []
    sensitive = sorted(
        column for column in column_names
        if re.search(r"(?:token|password|secret|credential|private|hash|invite|evidence|payload|command|path)", column, re.I)
    )
    projected = any(token in name for token in ("current", "projection", "revision", "snapshot", "index", "state"))
    return {
        "purpose": f"Source-derived {domain.replace('_', ' ')} persistence object; detailed ownership is conservatively inferred from its migration-defined name.",
        "domain": domain,
        "writer": writer,
        "readers": readers,
        "retention": "domain-owned bounded retention or explicit lifecycle policy; verify the owning service before destructive maintenance",
        "sensitive_fields": sensitive,
        "classification": "restricted operational metadata" if sensitive else "internal operational metadata",
        "projection_owner": domain if projected else "not a prepared projection",
        "semantic_status": "inferred",
    }


def sqlite_inventory() -> tuple[dict[str, Any], list[Path]]:
    semantics = metadata().get("sqlite_semantics", {})
    with tempfile.TemporaryDirectory(prefix="pocketlab-docs-schema-") as temp:
        db = Path(temp) / "lite-schema.sqlite3"
        migrations = build_empty_database(db)
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        try:
            items = []
            for row in conn.execute("SELECT name, type, sql FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type, name"):
                name = row["name"]
                columns = []
                for col in conn.execute(f'PRAGMA table_info("{name}")'):
                    columns.append({"name":col[1],"declared_type":col[2],"nullable":not bool(col[3]),"default":col[4],"primary_key_position":col[5]})
                foreign_keys = [{"id":fk[0],"sequence":fk[1],"parent_table":fk[2],"from":fk[3],"to":fk[4],"on_update":fk[5],"on_delete":fk[6]} for fk in conn.execute(f'PRAGMA foreign_key_list("{name}")')]
                indexes = []
                for idx in conn.execute(f'PRAGMA index_list("{name}")'):
                    idx_name = idx[1]
                    indexes.append({"name":idx_name,"unique":bool(idx[2]),"origin":idx[3],"partial":bool(idx[4]),"columns":[info[2] for info in conn.execute(f'PRAGMA index_info("{idx_name}")')]})
                migration_sources = [m.relative_to(ROOT).as_posix() for m in migrations if re.search(rf"\b{re.escape(name)}\b", m.read_text(encoding="utf-8", errors="ignore"), re.I)]
                inferred = inferred_sqlite_semantic(name, [column["name"] for column in columns])
                declared = semantics.get(name, {})
                semantic = {**inferred, **declared}
                semantic["semantic_status"] = declared.get("semantic_status", "verified" if declared else "inferred")
                items.append({"name":name,"type":row["type"],"columns":columns,"foreign_keys":foreign_keys,"indexes":indexes,"checks":re.findall(r"CHECK\s*\((.*?)\)", row["sql"] or "", re.I|re.S),"sql":row["sql"],"migration_sources":migration_sources,**semantic})
            return {"database":"temporary data-free SQLite","row_count_enforced":0,"objects":items,"migration_count":len(migrations)}, migrations
        finally:
            conn.close()


def sqlite_outputs() -> dict[Path, str]:
    inventory, migrations = sqlite_inventory()
    sources = [META_PATH, *migrations]
    envelope = json_envelope("lite_sqlite_schema", inventory, sources)
    rows = []
    for item in inventory["objects"]:
        rows.append([f'`{item["name"]}`', item["type"], len(item["columns"]), len(item["foreign_keys"]), len(item["indexes"]), item["domain"], item["writer"], item["classification"], item["semantic_status"], item["migration_sources"]])
    md = frontmatter("Lite SQLite schema", "Data-free migration-derived SQLite tables, views, columns, relationships, owners and classifications.", sources) + "# Lite SQLite schema\n\nThe generator applies migrations to a temporary database, deletes all seed rows, verifies every table has zero rows, introspects the schema, then securely removes the database. It never opens a live Pocket Lab database.\n\n[Open the normalized SchemaSpy HTML reference](../schemaspy/index.html).\n\nSemantic rows marked **inferred** are conservative source-derived ownership hints and are not promoted to verified runtime truth.\n\n" + md_table(
        ["Object", "Type", "Columns", "FKs", "Indexes", "Domain", "Writer", "Classification", "Semantic status", "Migration source"], rows)
    for item in inventory["objects"]:
        md += f"\n<a id=\"{slug(item['name'])}\"></a>\n## `{item['name']}`\n\n{item['purpose']}\n\n"
        md += md_table(["Column", "Type", "Nullable", "Default", "Primary key"], ([f'`{c["name"]}`', c["declared_type"], c["nullable"], c["default"] or "—", c["primary_key_position"]] for c in item["columns"]))
    return {GENERATED_CONTRACTS / "lite-sqlite-schema.json": stable_json(envelope), DEV / "lite-sqlite-schema.md": md}


def projection_outputs() -> dict[Path, str]:
    projections = metadata()["projections"]
    sources = [META_PATH, ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/projection_scheduler.py", ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_core_projections.py"]
    envelope = json_envelope("projection_catalog", projections, sources)
    md = frontmatter("Prepared projection catalog", "Canonical sources, prepared storage, freshness, invalidation, pressure and cache ownership.", sources) + "# Prepared projection catalog\n\n" + md_table(
        ["Domain", "Canonical source", "Storage", "Reader", "Frontend", "Fresh/stale", "Degraded behavior", "Diagnostics"],
        ([f'`{p["domain"]}`', p["canonical_source"], p["storage_owner"], f'`{p["reader_endpoint"]}`', f'`{p["frontend_consumer"]}`', f'{p["freshness_seconds"]}/{p["stale_seconds"]}s', p["degraded_behavior"], p["diagnostics"]] for p in projections)
    ) + "\n![Prepared projection flow](../../assets/diagrams/projection-flow.light.svg#only-light)\n![Prepared projection flow](../../assets/diagrams/projection-flow.dark.svg#only-dark)\n"
    return {GENERATED_CONTRACTS / "projection-catalog.json": stable_json(envelope), DEV / "projection-catalog.md": md}


def discovered_reason_codes() -> set[str]:
    values: set[str] = set()
    for path in (ROOT / "pocket-lab-final-structure/runtime/api_fastapi").rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if isinstance(key, ast.Constant) and key.value in {"reason_code", "failure_code", "reason"} and isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value and " " not in value.value:
                        values.add(value.value)
                    if isinstance(key, ast.Constant) and key.value == "reason_codes" and isinstance(value, (ast.List, ast.Tuple)):
                        for item in value.elts:
                            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                                values.add(item.value)
    return values


def reason_outputs() -> dict[Path, str]:
    registry = metadata()["reason_codes"]
    sources = [META_PATH, *list((ROOT / "pocket-lab-final-structure/runtime/api_fastapi").rglob("*.py"))]
    codes = {item["code"] for item in registry}
    discovered = discovered_reason_codes()
    missing = sorted(discovered - codes)
    payload = {"reason_codes": registry, "discovered_structured_codes": sorted(discovered), "undocumented_structured_codes": missing}
    envelope = json_envelope("reason_codes", payload, sources, validation_state="failed" if missing else "generated")
    md = frontmatter("Reason-code registry", "Canonical cross-domain Lite reason codes and user/audit mappings.", sources, status="unvalidated" if missing else "verified") + "# Reason-code registry\n\n" + md_table(
        ["Code", "Domain", "Meaning", "Retryable", "Terminal", "HTTP", "Severity", "Source"],
        ([f'`{r["code"]}`', r["domain"], r["meaning"], r["retryable"], r["terminal"], r["http_status"], r["audit_severity"], r["source"]] for r in registry)
    )
    if missing:
        md += "\n## Undocumented structured codes\n\n" + "\n".join(f"- `{value}`" for value in missing) + "\n"
    return {GENERATED_CONTRACTS / "reason-codes.json": stable_json(envelope), DEV / "reason-codes.md": md}


def env_inventory() -> list[dict[str, Any]]:
    pattern = re.compile(r"\b(?:POCKETLAB|POCKET_LAB|LITE|NATS|PLAYWRIGHT|CHROME|CHROMIUM|EDGE|SOURCE)_[A-Z0-9_]+\b")
    source_files = [*list((ROOT / "scripts").rglob("*.sh")), *list((ROOT / "scripts").rglob("*.py")), *list((ROOT / "pocket-lab-final-structure").rglob("*.py")), *list((ROOT / "pocket-lab-final-structure").rglob("*.sh")), ROOT / "Taskfile.yml", ROOT / "playwright.config.ts"]
    found: dict[str, set[str]] = defaultdict(set)
    defaults: dict[str, set[str]] = defaultdict(set)
    for path in source_files:
        if not path.exists() or path.is_dir():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in pattern.finditer(text):
            found[match.group(0)].add(path.relative_to(ROOT).as_posix())
        for match in re.finditer(r"(?:os\.environ\.get\(|\$\{)([A-Z][A-Z0-9_]+)[^\n]{0,80}?(?:,\s*['\"]([^'\"]*)['\"]|:-([^}]*))", text):
            name = match.group(1)
            if pattern.fullmatch(name):
                value = (match.group(2) or match.group(3) or "").strip()
                if value and not re.search(r"password|token|secret|key", name, re.I):
                    # Never reproduce machine-specific defaults such as Android,
                    # WSL2, home, temporary, or repository paths in generated docs.
                    # Preserve only compact scalar defaults that are safe to publish.
                    if value.startswith(("/", "~", "$HOME", "${HOME}", "%USERPROFILE%")) or re.match(r"^[A-Za-z]:[\\/]", value):
                        value = "path supplied by the owning component"
                    elif any(marker in value for marker in ("/data/data/", "/home/", "/mnt/", "/tmp/")):
                        value = "path supplied by the owning component"
                    defaults[name].add(value[:120])
    items = []
    for name, files in sorted(found.items()):
        secret = bool(re.search(r"PASSWORD|TOKEN|SECRET|PRIVATE_KEY|API_KEY|CREDENTIAL", name))
        items.append({
            "name": name,
            "component": sorted({Path(file).parts[0] for file in files}),
            "required": False,
            "safe_default": "not documented for secret variables" if secret else (sorted(defaults[name])[0] if defaults[name] else "source-defined or empty"),
            "secret_classification": "secret" if secret else "configuration",
            "allowed_values": "source-defined",
            "android_termux": True,
            "wsl2": True,
            "production": not name.startswith(("PLAYWRIGHT_","CHROME_","CHROMIUM_","EDGE_","SOURCE_")),
            "restart_required": "component-dependent",
            "runtime_readers": sorted(files),
            "deprecated_aliases": [],
        })
    return items


def configuration_outputs() -> dict[Path, str]:
    items = env_inventory()
    sources = [META_PATH, *list((ROOT / "scripts").rglob("*.sh")), *list((ROOT / "pocket-lab-final-structure").rglob("*.py"))]
    envelope = json_envelope("configuration_reference", items, sources)
    md = frontmatter("Configuration reference", "Sanitized environment-variable inventory derived from verified source use without values.", sources) + "# Configuration reference\n\nNo current environment values are read or emitted. Secret-like names are classified and their defaults are suppressed.\n\n" + md_table(
        ["Variable", "Classification", "Safe default", "Production", "Restart", "Readers"],
        ([f'`{i["name"]}`', i["secret_classification"], i["safe_default"], i["production"], i["restart_required"], i["runtime_readers"]] for i in items)
    )
    return {GENERATED_CONTRACTS / "configuration-reference.json": stable_json(envelope), DEV / "configuration-reference.md": md}


def service_outputs() -> dict[Path, str]:
    services = metadata()["services"]
    sources = [META_PATH, ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh", ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-fleet-agent.sh"]
    envelope = json_envelope("service_catalog", services, sources)
    md = frontmatter("Service catalog", "Approved Lite PM2 process patterns, owners, recovery, health and secret restrictions.", sources) + "# Service catalog\n\n" + md_table(
        ["Process", "Owner / purpose", "Platform", "Restart policy", "Health", "NATS", "Recovery"],
        ([f'`{s["pattern"]}`', f'{s["owner"]}: {s["purpose"]}', s["platform"], s["restart_policy"], s["health_evidence"], s["nats_dependency"], s["recovery"]] for s in services)
    )
    return {GENERATED_CONTRACTS / "service-catalog.json": stable_json(envelope), DEV / "service-catalog.md": md}


def bootstrap_inventory() -> list[dict[str, Any]]:
    path = ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/bootstrap.sh"
    text = path.read_text(encoding="utf-8")
    records = []
    for match in re.finditer(r'^\s*"(\d+)\|([^|]+)\|([^|]+)\|([^\"]+)"', text, re.M):
        index, stage, script, description = match.groups()
        stage_path = path.parent / script
        stage_text = stage_path.read_text(encoding="utf-8", errors="ignore") if stage_path.exists() else ""
        records.append({
            "index": int(index), "stage": stage, "owning_script": stage_path.relative_to(ROOT).as_posix(), "description": description,
            "side_effects": "source-defined system/runtime changes; generation does not execute the stage",
            "idempotency": "completion marker and stage-owned checks",
            "required_environment": sorted(set(re.findall(r"POCKETLAB_[A-Z0-9_]+", stage_text))),
            "supported_platform": "Android/Termux; selected syntax and dry-run checks on Ubuntu/WSL2",
            "android_termux": True, "wsl2": "validation only unless explicitly allowed",
            "safe_retry": True, "rollback": "stage-specific manual recovery; do not clear evidence",
            "expected_output": f"Completed stage {index}/{stage}", "evidence_generated": ["bootstrap stage marker and logs"],
            "services_affected": sorted(set(re.findall(r"pm2_(?:start_or_restart|delete)\s+([A-Za-z0-9_-]+)|--name\s+['\"]?([A-Za-z0-9_-]+)", stage_text))),
            "files_written": "source-defined; no paths executed during documentation generation",
            "secrets_handled": bool(re.search(r"PASSWORD|TOKEN|SECRET|KEY", stage_text)),
            "failure_behavior": "fail closed; later stages do not run",
        })
    return records


def bootstrap_outputs() -> dict[Path, str]:
    stages = bootstrap_inventory()
    source = ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/bootstrap.sh"
    sources = [source, *[ROOT / item["owning_script"] for item in stages]]
    envelope = json_envelope("bootstrap_stages", stages, sources)
    md = frontmatter("Bootstrap stages", "Source-inspected Day-0 stage graph, side-effect boundaries, retry and failure behavior.", sources) + "# Bootstrap stages\n\nDocumentation generation inspects stage definitions only and never executes bootstrap stages.\n\n" + md_table(
        ["#", "Stage", "Script", "Description", "Safe retry", "Failure behavior"],
        ([s["index"], f'`{s["stage"]}`', f'`{s["owning_script"]}`', s["description"], s["safe_retry"], s["failure_behavior"]] for s in stages)
    )
    return {GENERATED_CONTRACTS / "bootstrap-stages.json": stable_json(envelope), DEV / "bootstrap-stages.md": md}


def release_outputs() -> dict[Path, str]:
    candidates = sorted([*ROOT.glob("**/pocketlab-lite-release.json"), *ROOT.glob("**/lite-release-manifest.json")])
    candidates = [path for path in candidates if not any(part in {"node_modules", ".venv", ".git", "site"} for part in path.parts)]
    releases = []
    outputs: dict[Path, str] = {}
    for path in candidates:
        data = read_json(path, {})
        tag = str(data.get("release_tag") or data.get("tag") or "").strip()
        if not re.fullmatch(r"lite-\d{4}\.\d{2}\.\d{2}\.\d+", tag):
            continue
        record = {
            "release_tag": tag, "source_commit": data.get("source_commit"), "repository": data.get("repository"),
            "dist_zip_checksum": data.get("dist_zip_sha256") or data.get("artifacts", {}).get("dist.zip"),
            "checksum_file_checksum": data.get("checksums_sha256"), "release_manifest_checksum": sha256_bytes(path.read_bytes()),
            "supported_architecture": data.get("supported_architecture") or ["ARM64"], "pwa_build_identity": data.get("pwa_build_identity"),
            "migration_version": data.get("migration_version"), "installed_release_compatibility": data.get("installed_release_compatibility"),
            "last_known_good_compatibility": data.get("last_known_good_compatibility"), "artifact_inventory": data.get("artifacts", {}),
            "exclusions": data.get("exclusions", []), "validation_evidence": data.get("validation_evidence", []),
            "release_url_metadata": data.get("release_url") or "not embedded", "source_manifest": path.relative_to(ROOT).as_posix(),
        }
        releases.append(record)
        envelope = json_envelope("release", record, [path])
        outputs[GENERATED_CONTRACTS / "releases" / f"{tag}.json"] = stable_json(envelope)
        outputs[ROOT / "docs/releases" / f"{tag}.md"] = frontmatter(f"Release {tag}", "Verified Lite release manifest and artifact inventory.", [path]) + f"# Release `{tag}`\n\n" + md_table(["Field","Value"], ([key.replace('_',' ').title(), value] for key,value in record.items()))
    index_sources = candidates or [META_PATH]
    status = "verified" if releases else "unvalidated"
    index_payload = {"releases": releases, "status":"verified manifests found" if releases else "no verified release manifest present in the repository"}
    outputs[GENERATED_CONTRACTS / "releases" / "index.json"] = stable_json(json_envelope("release_inventory", index_payload, index_sources, validation_state=status))
    outputs[DEV / "release-inventory.md"] = frontmatter("Release inventory", "Verified Lite release manifests only; no release identity is invented.", index_sources, status=status) + "# Release inventory\n\n" + (md_table(["Tag","Commit","dist.zip checksum","Manifest"], ([r["release_tag"], r["source_commit"], r["dist_zip_checksum"], r["source_manifest"]] for r in releases)) if releases else "No verified release manifest is committed. Release readiness remains unvalidated.\n")
    return outputs


def validation_outputs() -> dict[Path, str]:
    validation_root = ROOT / ".pocketlab-dev/validation"
    records = []
    if validation_root.exists():
        for path in sorted(validation_root.rglob("*.json"))[:200]:
            try:
                data = read_json(path, {})
            except Exception:
                continue
            records.append({"gate":data.get("gate") or data.get("name") or path.stem,"command":data.get("command"),"commit":data.get("commit") or data.get("source_commit"),"platform":data.get("platform"),"browser":data.get("browser"),"started_at":data.get("started_at"),"completed_at":data.get("completed_at"),"duration":data.get("duration_seconds"),"result":data.get("result") or data.get("status"),"artifact":path.relative_to(ROOT).as_posix(),"checksum":sha256_bytes(path.read_bytes()),"failure_reason":data.get("failure_reason"),"current":(data.get("commit") or data.get("source_commit")) in {None,"",SOURCE_COMMIT}})
    payload = {"commit":SOURCE_COMMIT,"gates":records,"status":"recorded evidence" if records else "no recorded local evidence; no PASS claimed"}
    sources = list(validation_root.rglob("*.json")) if validation_root.exists() else [META_PATH]
    envelope = json_envelope("lite_readiness", payload, sources, validation_state="recorded" if records else "unvalidated")
    md = frontmatter("Lite readiness evidence", "Bounded recorded validation evidence; PASS is never synthesized.", sources, status="verified" if records else "unvalidated") + "# Lite readiness evidence\n\n" + (md_table(["Gate","Command","Commit","Platform","Result","Current","Artifact"], ([r["gate"],r["command"],r["commit"],r["platform"],r["result"],r["current"],r["artifact"]] for r in records)) if records else "No recorded validation evidence is present in this repository checkout. No PASS is claimed.\n")
    return {ROOT / "validation/lite-readiness.json": stable_json(envelope), DEV / "lite-readiness.md": md}


def redaction_outputs() -> dict[Path, str]:
    redaction = metadata()["redaction"]
    sources = [META_PATH, *[ROOT / value for value in redaction["coverage_sources"] if (ROOT / value).exists()]]
    coverage = {
        **redaction,
        "redacted_api_fields": "derived from response sanitizers and tests",
        "redacted_event_fields": "event catalog redacted_fields metadata",
        "log_redaction_tests": [value for value in redaction["coverage_sources"] if "test" in value],
        "har_redaction_tests": [value for value in redaction["coverage_sources"] if "har" in value],
        "schema_spy_no_data_check": "temporary database row count is zero before SchemaSpy",
        "generated_document_secret_scan": "platform check scans generated Markdown, JSON, HTML, DOT and SVG",
        "unresolved_coverage_gaps": ["runtime-only third-party output remains subject to the existing redaction gate"],
    }
    envelope = json_envelope("redaction_coverage", coverage, sources)
    md = frontmatter("Redaction coverage", "Consolidated source-owned redaction and generated-artifact secret-safety coverage.", sources) + "# Redaction coverage\n\n" + md_table(["Area","Coverage"], ([key.replace('_',' ').title(), value] for key,value in coverage.items()))
    return {GENERATED_CONTRACTS / "redaction-coverage.json": stable_json(envelope), DEV / "redaction-coverage.md": md}


def link_registry_outputs(current_outputs: dict[Path, str] | None = None) -> dict[Path, str]:
    entities: dict[str, Any] = {}
    schema = load_openapi()
    for path, item in sorted(schema.get("paths", {}).items()):
        for method in sorted(key for key in item if key.lower() in HTTP_METHODS):
            key = f"endpoint:{method.upper()}:{path}"
            entities[key] = {"title":f"{method.upper()} {path}","url":f"../../docs/reference/api/lite-api.md#{slug(f'{method}-{path}')}"}
    sqlite_data, _ = sqlite_inventory()
    for item in sqlite_data["objects"]:
        entities[f"table:{item['name']}"] = {"title":item["name"],"schema_url":f"../../docs/generated/schemaspy/tables/{item['name']}.html","catalog_url":f"../../docs/generated/development/lite-sqlite-schema.md#{slug(item['name'])}"}
    for projection in metadata()["projections"]:
        entities[f"projection:{projection['domain']}"] = {"title":projection["domain"],"url":f"../../docs/generated/development/projection-catalog.md#{slug(projection['domain'])}"}
    for code in metadata()["reason_codes"]:
        entities[f"reason:{code['code']}"] = {"title":code["code"],"url":f"../../docs/generated/development/reason-codes.md#{slug(code['code'])}"}
    for service in metadata()["services"]:
        entities[f"service:{service['pattern']}"] = {"title":service["pattern"],"url":f"../../docs/generated/development/service-catalog.md#{slug(service['pattern'])}"}
    for stage in bootstrap_inventory():
        entities[f"bootstrap:{stage['stage']}"] = {"title":stage["stage"],"url":f"../../docs/generated/development/bootstrap-stages.md#{slug(stage['stage'])}"}
    for subject in subject_inventory():
        entities[f"event:{subject['subject']}"] = {"title":subject["subject"],"url":f"../../docs/generated/development/lite-events.md#{slug(subject['subject'])}"}
    sources = [OPENAPI_PATH, META_PATH, *SCHEMA_DIR.glob("*.sql")]
    envelope = json_envelope("documentation_links", {"entities":entities}, sources)
    return {GENERATED_CONTRACTS / "documentation-links.json": stable_json(envelope)}


SECTION_BUILDERS = {
    "openapi": openapi_outputs,
    "frontend-api": lambda: {**frontend_outputs(), **compatibility_outputs()},
    "events": event_outputs,
    "capabilities": capabilities_outputs,
    "ui": ui_outputs,
    "recovery": recovery_outputs,
    "security": security_outputs,
    "sqlite": sqlite_outputs,
    "projections": projection_outputs,
    "reason-codes": reason_outputs,
    "configuration": configuration_outputs,
    "services": service_outputs,
    "bootstrap": bootstrap_outputs,
    "release": release_outputs,
    "validation": validation_outputs,
    "redaction": redaction_outputs,
}


def build_outputs(section: str) -> dict[Path, str]:
    if section == "all":
        outputs: dict[Path, str] = {}
        for name in SECTION_BUILDERS:
            outputs.update(SECTION_BUILDERS[name]())
        outputs.update(link_registry_outputs(outputs))
        return outputs
    if section == "links":
        return link_registry_outputs()
    return SECTION_BUILDERS[section]()


def validate_output_safety(outputs: dict[Path, str]) -> list[str]:
    errors: list[str] = []
    for path, content in outputs.items():
        if SECRET_VALUE.search(content):
            errors.append(f"secret-like value in {path.relative_to(ROOT)}")
        if ABSOLUTE_PATH.search(content):
            errors.append(f"absolute machine path in {path.relative_to(ROOT)}")
        if "<PATCH_FILE>" in content:
            errors.append(f"unresolved placeholder in {path.relative_to(ROOT)}")
    return errors


def write_outputs(outputs: dict[Path, str]) -> None:
    errors = validate_output_safety(outputs)
    if errors:
        raise RuntimeError("\n".join(errors))
    for path, content in sorted(outputs.items(), key=lambda item: item[0].as_posix()):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)


def check_outputs(outputs: dict[Path, str]) -> int:
    errors = validate_output_safety(outputs)
    drift = []
    for path, expected in sorted(outputs.items(), key=lambda item: item[0].as_posix()):
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            drift.append(path.relative_to(ROOT).as_posix())
    reason_payload = outputs.get(GENERATED_CONTRACTS / "reason-codes.json")
    if reason_payload:
        undocumented = json.loads(reason_payload)["reason_codes"]["undocumented_structured_codes"]
        if undocumented:
            errors.append("undocumented reason codes: " + ", ".join(undocumented))
    frontend_payload = outputs.get(GENERATED_CONTRACTS / "frontend-api-usage.json")
    if frontend_payload:
        unsupported = json.loads(frontend_payload)["frontend_api_usage"]["unsupported_frontend_routes"]
        if unsupported:
            errors.append("unsupported frontend routes: " + ", ".join(unsupported))
    if drift:
        print("Generated documentation drift:")
        for item in drift:
            print(f" - {item}")
    if errors:
        print("Documentation validation errors:")
        for item in errors:
            print(f" - {item}")
    if drift or errors:
        return 1
    print(f"PASS {len(outputs)} source-derived documentation platform artifacts are current and safe")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "check"])
    parser.add_argument("--section", choices=[*SECTION_BUILDERS, "links", "all"], default="all")
    args = parser.parse_args()
    outputs = build_outputs(args.section)
    if args.command == "generate":
        write_outputs(outputs)
        print(f"Generated {len(outputs)} artifacts for section {args.section}")
        return 0
    return check_outputs(outputs)


if __name__ == "__main__":
    raise SystemExit(main())
