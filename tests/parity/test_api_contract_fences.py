from __future__ import annotations

import importlib
import json
from pathlib import Path

from scripts.test.parity.prepare_schemathesis_schema import _require_loopback_url, compile_schema


def _openapi() -> dict:
    module = importlib.import_module("pocket-lab-final-structure.runtime.api_fastapi.main")
    module.app.openapi_schema = None
    return module.app.openapi()


def test_openapi_hardening_documents_expected_lite_failures_without_normalizing_500() -> None:
    schema = _openapi()
    assert schema["info"]["x-pocketlab-contract-hardening"] == "api-contract-fences-v1"
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"} or not isinstance(operation, dict):
                continue
            assert "500" not in operation.get("responses", {}), (method, path)
            if path.startswith("/api/lite/"):
                assert "503" in operation["responses"], (method, path)
            if method.lower() == "get" and any(
                parameter.get("in") == "path" for parameter in operation.get("parameters", [])
            ):
                assert "404" in operation["responses"], (method, path)
            if any(parameter.get("name") == "cursor" for parameter in operation.get("parameters", [])):
                assert "400" in operation["responses"], (method, path)


def test_openapi_hides_side_effectful_or_internal_get_compatibility_routes() -> None:
    paths = _openapi()["paths"]
    assert "/api/fleet/agent/bootstrap" not in paths
    assert "/api/join.sh" not in paths
    bootstrap = paths["/api/lite/fleet/agent/bootstrap.sh"]["get"]
    assert bootstrap["x-pocketlab-side-effectful-read"] is True
    assert bootstrap["x-pocketlab-sensitive"] is True
    assert set(bootstrap["responses"]["200"]["content"]) == {"text/x-shellscript"}
    assert "/api/opa_interceptor.py" not in paths
    assert "get" not in paths["/api/catalog/refresh"]
    assert "post" in paths["/api/catalog/refresh"]


def test_openapi_streams_are_declared_as_event_streams() -> None:
    paths = _openapi()["paths"]
    for path in ("/api/lite/events", "/api/lite/security/events"):
        operation = paths[path]["get"]
        assert operation["x-pocketlab-streaming"] is True
        content = operation["responses"]["200"]["content"]
        assert set(content) == {"text/event-stream"}


def test_query_null_is_removed_and_cursor_contract_is_bounded() -> None:
    schema = _openapi()
    cursor = next(
        parameter
        for parameter in schema["paths"]["/api/lite/recovery/operations"]["get"]["parameters"]
        if parameter["name"] == "cursor"
    )
    assert cursor["schema"]["pattern"].startswith("^$")
    assert cursor["schema"]["maxLength"] <= 512
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for parameter in operation.get("parameters", []):
                if parameter.get("in") != "query":
                    continue
                branches = parameter.get("schema", {}).get("anyOf", [])
                assert all(branch.get("type") != "null" for branch in branches if isinstance(branch, dict))


def test_focused_schema_compiler_is_deny_by_default() -> None:
    source = _openapi()
    compiled, operations = compile_schema(source, "focused", {"app_id": "photoprism"})
    assert operations
    assert all(item["method"] == "GET" for item in operations)
    assert all(item["path"].startswith("/api/lite/recovery") for item in operations)
    assert all("/maintenance" not in item["path"] for item in operations)
    for path_item in compiled["paths"].values():
        assert all(method == "get" or method not in {"post", "put", "patch", "delete"} for method in path_item)


def test_discovery_schema_excludes_streams_and_state_changing_gets() -> None:
    source = _openapi()
    _compiled, operations = compile_schema(source, "discovery", {})
    selected = {(item["method"], item["path"]) for item in operations}
    assert ("GET", "/api/lite/events") not in selected
    assert ("GET", "/api/lite/security/events") not in selected
    assert ("GET", "/api/fleet/agent/bootstrap") not in selected
    assert all(method == "GET" for method, _path in selected)


def test_latency_probe_is_bounded_and_sanitized() -> None:
    source = Path("scripts/test/parity/probe_read_latency.py").read_text(encoding="utf-8")
    assert "max(2, min(args.samples, 5))" in source
    assert '"base_url": "loopback"' in source
    assert "token" not in source.lower().split("default_paths", 1)[1].split(")", 1)[0]


def test_openapi_baseline_promotion_is_explicit_and_hash_matched() -> None:
    import hashlib

    baseline = Path("contracts/parity/openapi-baseline.json")
    current = Path("contracts/generated/lite-openapi.json")
    promotion = json.loads(Path("contracts/parity/openapi-baseline-promotion.json").read_text(encoding="utf-8"))
    assert promotion["status"] == "promoted"
    assert promotion["security_review"]["documents_500"] is False
    assert promotion["security_review"]["raw_secrets_included"] is False
    baseline_hash = hashlib.sha256(baseline.read_bytes()).hexdigest()
    current_hash = hashlib.sha256(current.read_bytes()).hexdigest()
    assert baseline_hash == current_hash == promotion["promoted_sha256"]



def test_schema_compiler_rejects_non_loopback_sources() -> None:
    import pytest

    _require_loopback_url("http://127.0.0.1:18080/openapi.json", "OpenAPI URL")
    _require_loopback_url("http://localhost:8000", "base URL")
    with pytest.raises(SystemExit):
        _require_loopback_url("https://example.com/openapi.json", "OpenAPI URL")
    with pytest.raises(SystemExit):
        _require_loopback_url("http://user:pass@127.0.0.1:8000/openapi.json", "OpenAPI URL")


def test_schemathesis_wrappers_compile_before_running_and_summarize_evidence() -> None:
    focused = Path("scripts/test/parity/run_schemathesis.sh").read_text(encoding="utf-8")
    discovery = Path("scripts/test/parity/run_schemathesis_discovery.sh").read_text(encoding="utf-8")
    for source, profile in ((focused, "focused"), (discovery, "discovery")):
        assert "prepare_schemathesis_schema.py" in source
        assert f"--profile {profile}" in source
        assert "summarize_schemathesis.py" in source
        assert "--workers 1" in source
        assert "--request-retries 1" in source
        assert "--output-sanitize true" in source
    assert "--mode positive" in focused
    assert "--phases examples,fuzzing" in focused
    assert "--coverage" not in discovery


def test_oasdiff_wrapper_verifies_promotion_and_writes_atomically() -> None:
    source = Path("scripts/test/parity/run_oasdiff.sh").read_text(encoding="utf-8")
    assert "openapi-baseline-promotion.json" in source
    assert "--allow-external-refs=false" in source
    assert "--fail-on ERR" in source
    assert 'TEMP_REPORT="${REPORT}.tmp"' in source
    assert "-m json.tool" in source
    assert "--output" not in source

def test_schemathesis_summary_redacts_loopback_and_sensitive_query_values(tmp_path) -> None:
    import subprocess

    junit = tmp_path / "junit.xml"
    output = tmp_path / "summary.json"
    junit.write_text(
        '<testsuite><testcase name="GET /api/example"><failure>'
        'Undocumented HTTP status code\n'
        'curl http://127.0.0.1:18080/api/example?token=super-secret-value'
        '</failure></testcase></testsuite>',
        encoding="utf-8",
    )
    subprocess.run(
        [
            "python3",
            "scripts/test/parity/summarize_schemathesis.py",
            "--junit",
            str(junit),
            "--output",
            str(output),
            "--profile",
            "discovery",
            "--exit-status",
            "1",
        ],
        check=True,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    encoded = json.dumps(payload)
    assert "super-secret-value" not in encoded
    assert "http://loopback" in encoded
    assert payload["categories"]["undocumented_status"] == 1
