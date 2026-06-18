#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "contracts/generated/openapi.json"


HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "options",
    "head",
}


COMMON_ERROR_SCHEMAS: dict[str, Any] = {
    "ErrorResponse": {
        "type": "object",
        "properties": {
            "detail": {
                "description": "Human-readable error detail.",
                "oneOf": [
                    {"type": "string"},
                    {"type": "array"},
                    {"type": "object"},
                ],
            }
        },
        "required": ["detail"],
    }
}


READ_RESPONSES = {
    "400": {"description": "Bad request"},
    "401": {"description": "Unauthorized"},
    "403": {"description": "Forbidden"},
    "404": {"description": "Not found"},
    "503": {"description": "Control plane unavailable or degraded"},
}

WRITE_RESPONSES = {
    "400": {"description": "Bad request"},
    "401": {"description": "Unauthorized"},
    "403": {"description": "Forbidden or write operation blocked"},
    "409": {"description": "Operation conflict or invalid current state"},
    "422": {"description": "Validation error"},
    "503": {"description": "Control plane unavailable or degraded"},
}

HEALTH_RESPONSES = {
    "404": {"description": "Health endpoint not found"},
    "503": {"description": "Service unavailable or not ready"},
}


def response_with_schema(description: str) -> dict[str, Any]:
    return {
        "description": description,
        "content": {
            "application/json": {
                "schema": {
                    "$ref": "#/components/schemas/ErrorResponse"
                }
            }
        },
    }


def classify_responses(path: str, method: str) -> dict[str, dict[str, str]]:
    if path in {"/health", "/healthz", "/ready"}:
        return HEALTH_RESPONSES

    if method.lower() in {"post", "put", "patch", "delete"}:
        return WRITE_RESPONSES

    return READ_RESPONSES


def enhance(schema: dict[str, Any]) -> dict[str, Any]:
    schema.setdefault(
        "servers",
        [
            {
                "url": "http://127.0.0.1:8000",
                "description": "Local Pocket Lab FastAPI runtime",
            }
        ],
    )

    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    for name, spec in COMMON_ERROR_SCHEMAS.items():
        schemas.setdefault(name, spec)

    paths = schema.get("paths", {})

    added = 0

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue

        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS:
                continue

            if not isinstance(operation, dict):
                continue

            responses = operation.setdefault("responses", {})

            for code, spec in classify_responses(path, method).items():
                if code not in responses:
                    responses[code] = response_with_schema(spec["description"])
                    added += 1

            if not operation.get("summary"):
                operation["summary"] = operation.get("operationId", f"{method.upper()} {path}")

    print(f"Enhanced OpenAPI responses added: {added}")
    return schema


def main() -> None:
    if not OPENAPI.exists():
        raise SystemExit(f"Missing OpenAPI file: {OPENAPI}")

    schema = json.loads(OPENAPI.read_text(encoding="utf-8"))
    schema = enhance(schema)

    OPENAPI.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"Updated: {OPENAPI}")


if __name__ == "__main__":
    main()
