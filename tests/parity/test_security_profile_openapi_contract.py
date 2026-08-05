from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(
    "pocket-lab-final-structure/runtime/api_fastapi/openapi_contracts.py"
)


def _load_hardener():
    spec = importlib.util.spec_from_file_location(
        "pocketlab_openapi_contracts_security_profile",
        MODULE_PATH,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.harden_openapi_schema


def test_security_profile_documents_conditional_bad_request() -> None:
    harden_openapi_schema = _load_hardener()
    schema = harden_openapi_schema(
        {
            "openapi": "3.1.0",
            "info": {"title": "test", "version": "1"},
            "paths": {
                "/api/lite/security/profiles/{profile}": {
                    "get": {
                        "parameters": [
                            {
                                "name": "profile",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                            },
                            {
                                "name": "app_id",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "string"},
                            },
                        ],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
    )
    responses = schema["paths"]["/api/lite/security/profiles/{profile}"]["get"]["responses"]

    assert "400" in responses
    response = responses["400"]
    assert response["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PocketLabApiError"
    }
    assert "app identifier" in response["description"].lower()
    assert "500" not in responses
