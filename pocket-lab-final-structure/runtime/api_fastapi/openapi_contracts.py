from __future__ import annotations

from copy import deepcopy
from typing import Any

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
CURSOR_PATTERN = r"^$|^[A-Za-z0-9_-]{2,512}$"
SSE_PATHS = {"/api/lite/events", "/api/lite/security/events"}

_ERROR_SCHEMA_NAME = "PocketLabApiError"
_ERROR_REF = {"$ref": f"#/components/schemas/{_ERROR_SCHEMA_NAME}"}


def _error_response(description: str, *, retry_after: bool = False) -> dict[str, Any]:
    response: dict[str, Any] = {
        "description": description,
        "content": {"application/json": {"schema": deepcopy(_ERROR_REF)}},
    }
    if retry_after:
        response["headers"] = {
            "Retry-After": {
                "description": "Bounded delay in seconds before a safe retry.",
                "schema": {"type": "integer", "minimum": 1, "maximum": 300},
            }
        }
    return response


def _install_components(schema: dict[str, Any]) -> None:
    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas[_ERROR_SCHEMA_NAME] = {
        "type": "object",
        "description": "Sanitized Pocket Lab API error or temporary-unavailability response.",
        "properties": {
            "error": {"type": "string", "maxLength": 240},
            "status": {"type": "string", "maxLength": 80},
            "summary": {"type": "string", "maxLength": 320},
            "message": {"type": "string", "maxLength": 320},
            "detail": {},
            "accepted": {"type": "boolean"},
            "retryable": {"type": "boolean"},
            "sanitized": {"type": "boolean"},
            "reason": {"type": "string", "maxLength": 120},
            "operation": {"type": "string", "maxLength": 120},
        },
        "additionalProperties": True,
    }


def _without_query_null(schema: dict[str, Any]) -> dict[str, Any]:
    """Represent optional query values by omission, never the literal string null.

    OpenAPI 3.1 nullable query schemas can lead generators to serialize Python/JSON
    null as the text ``null``. Query absence already represents None, so null is
    removed from query-only unions while preserving the parameter as optional.
    """
    value = deepcopy(schema)
    for key in ("anyOf", "oneOf"):
        branches = value.get(key)
        if not isinstance(branches, list):
            continue
        kept = [item for item in branches if not (isinstance(item, dict) and item.get("type") == "null")]
        if len(kept) == 1 and isinstance(kept[0], dict):
            title = value.get("title")
            value = deepcopy(kept[0])
            if title and "title" not in value:
                value["title"] = title
        else:
            value[key] = kept
    return value


def _harden_parameters(path: str, operation: dict[str, Any]) -> None:
    for parameter in operation.get("parameters") or []:
        if not isinstance(parameter, dict):
            continue
        location = str(parameter.get("in") or "")
        name = str(parameter.get("name") or "")
        parameter_schema = parameter.get("schema")
        if location == "query" and isinstance(parameter_schema, dict):
            parameter["schema"] = _without_query_null(parameter_schema)
            parameter_schema = parameter["schema"]
        if location == "query" and name == "cursor" and isinstance(parameter_schema, dict):
            parameter_schema["pattern"] = CURSOR_PATTERN
            parameter_schema["maxLength"] = min(int(parameter_schema.get("maxLength") or 512), 512)
            parameter["description"] = (
                "Opaque base64url cursor returned by the previous page. Omit or send an empty value for the first page."
            )
        if location == "query" and name == "token" and (
            path == "/api/join.sh" or path.endswith("/agent/bootstrap.sh")
        ):
            # The compatibility script returns a documented 400 when the token
            # is omitted. Keep the parameter optional in OpenAPI to avoid a
            # breaking contract change while marking it sensitive and bounded.
            if isinstance(parameter_schema, dict):
                parameter_schema["maxLength"] = min(int(parameter_schema.get("maxLength") or 512), 512)
                parameter_schema["writeOnly"] = True
            parameter["description"] = "Single-use invite token. Omission returns a sanitized 400 response."


def _has_path_parameters(operation: dict[str, Any]) -> bool:
    return any(
        isinstance(parameter, dict)
        and parameter.get("in") == "path"
        for parameter in operation.get("parameters") or []
    )


def _has_cursor(operation: dict[str, Any]) -> bool:
    return any(
        isinstance(parameter, dict)
        and parameter.get("in") == "query"
        and parameter.get("name") == "cursor"
        for parameter in operation.get("parameters") or []
    )


def _harden_operation(path: str, method: str, operation: dict[str, Any]) -> None:
    responses = operation.setdefault("responses", {})
    _harden_parameters(path, operation)

    if path in SSE_PATHS and method == "get":
        responses["200"] = {
            "description": "Server-Sent Events stream.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
        operation["x-pocketlab-streaming"] = True

    if path.startswith("/api/lite/"):
        responses.setdefault(
            "503",
            _error_response(
                "Projection warming, maintenance, workload admission, or a temporarily unavailable local dependency.",
                retry_after=True,
            ),
        )

    if method in {"post", "put", "patch", "delete"} and path.startswith("/api/lite/"):
        responses.setdefault("409", _error_response("The requested state transition conflicts with current durable state."))

    if method == "get" and _has_path_parameters(operation):
        responses.setdefault("404", _error_response("The requested resource is not available."))

    if _has_cursor(operation):
        responses.setdefault("400", _error_response("The supplied opaque cursor is invalid or stale."))

    if path == "/api/lite/security/profiles/{profile}" and method == "get":
        responses.setdefault(
            "400",
            _error_response(
                "The selected Security profile requires an app identifier or contains invalid parameters."
            ),
        )

    if path in {"/api/join.sh", "/api/lite/fleet/agent/bootstrap.sh", "/api/fleet/agent/bootstrap"}:
        responses.setdefault("400", _error_response("Bootstrap parameters or invite token are missing or invalid."))
        responses.setdefault("403", _error_response("The invite or bootstrap request is not authorized."))
        responses.setdefault("410", _error_response("The invite has expired, was revoked, or was already used."))

    if path.endswith("/agent/bootstrap.sh") and method == "get":
        responses["200"] = {
            "description": "Token-gated Pocket Lab Lite bootstrap shell script.",
            "content": {"text/x-shellscript": {"schema": {"type": "string"}}},
        }

    # A production API must never normalize an Internal Server Error into its
    # public contract. A 500 remains a conformance failure and a release blocker.
    responses.pop("500", None)


def harden_openapi_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Apply deterministic API-contract fences to a FastAPI OpenAPI document."""
    result = deepcopy(schema)
    _install_components(result)
    for path, path_item in (result.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            _harden_operation(path, method.lower(), operation)
    result.setdefault("info", {})["x-pocketlab-contract-hardening"] = "api-contract-fences-v1"
    return result
