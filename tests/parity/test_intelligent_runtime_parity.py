from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "contracts" / "parity" / "parity-model.json"
OBS_SCHEMA = ROOT / "schemas" / "parity" / "parity-runtime-observation.schema.json"
CMP_SCHEMA = ROOT / "schemas" / "parity" / "parity-runtime-comparison.schema.json"
GENERATOR = ROOT / "scripts" / "docs" / "parity" / "generate_parity.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


semantic = load_module(ROOT / "scripts" / "test" / "parity" / "semantic_compare.py", "semantic_compare_all_tabs")
comparison = load_module(ROOT / "scripts" / "test" / "parity" / "compare_runtime_parity.py", "compare_runtime_all_tabs")
capture = load_module(ROOT / "scripts" / "test" / "parity" / "capture_runtime_parity.py", "capture_runtime_all_tabs")
generator = load_module(GENERATOR, "generate_parity_all_tabs")


def model() -> dict:
    return json.loads(MODEL.read_text(encoding="utf-8"))


def observation(domain: str, kind: str = "backend", *, status: str = "observed", project: str = "", values=None) -> dict:
    payload = {
        "schema_version": "2.0.0",
        "evidence_kind": kind,
        "domain": domain,
        "status": status,
        "sanitized": True,
        "captured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_commit": "a" * 40,
        "release_tag": "lite-2026.08.06.1",
        "observations": values or {},
        "error_code": "",
    }
    if kind == "frontend":
        payload["browser_project"] = project
    return payload


def test_model_has_exact_current_tabs_and_complete_semantic_contracts():
    payload = model()
    assert [item["id"] for item in payload["domains"]] == [
        "home", "apps", "devices", "security", "identity", "rules", "recovery"
    ]
    operators = {item["id"] for item in payload["comparator_registry"]}
    assert operators == semantic.ALLOWED_OPERATORS
    mapping_ids = []
    for domain in payload["domains"]:
        for key in (
            "backend_authorities", "api_routes", "selectors", "query_keys", "frontend_screens",
            "live_observation_contract", "semantic_mappings", "accepted_limitations",
            "unsupported_operations", "known_gaps",
        ):
            assert key in domain
        assert domain["semantic_mappings"]
        mapping_ids.extend(item["id"] for item in domain["semantic_mappings"])
        expected = {item["expected_runtime_parity"] for item in payload["runtime_scenarios"] if item["domain"] == domain["id"]}
        assert {"verified-with-mapped-presentation", "drift-detected"} <= expected
    assert len(mapping_ids) == len(set(mapping_ids))


def test_strict_schemas_reject_unknown_comparator_and_invalid_observation_identity():
    payload = model()
    payload["domains"][0]["semantic_mappings"][0]["operator"] = "invented-comparator"
    schema = json.loads((ROOT / "schemas" / "parity" / "parity-model.schema.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(payload)

    observation_schema = json.loads(OBS_SCHEMA.read_text())
    missing_project = observation("home", "frontend", values={"screen_text": "Ready"})
    missing_project.pop("browser_project", None)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(observation_schema).validate(missing_project)

    non_browser_project = observation("home", "backend", values={"status": "healthy"})
    non_browser_project["browser_project"] = "live-desktop"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(observation_schema).validate(non_browser_project)


def test_runtime_scenario_fixtures_execute_as_declared():
    payload = model()
    by_domain = {item["id"]: item for item in payload["domains"]}
    for scenario in payload["runtime_scenarios"]:
        domain = by_domain[scenario["domain"]]
        mapping = next(item for item in domain["semantic_mappings"] if item["id"] == scenario["mapping_id"])
        result = semantic.compare_values(
            mapping["operator"],
            semantic.get_path(scenario["backend_observations"], mapping.get("backend_path", "$")),
            semantic.get_path(scenario["frontend_observations"], mapping.get("frontend_path", "$")),
            mapping,
        )
        expected = scenario["expected_runtime_parity"]
        if expected == "verified-with-mapped-presentation":
            assert result["result"] == "mapped", scenario["id"]
        else:
            assert expected == "drift-detected"
            assert result["result"] == "mismatch", scenario["id"]


def test_semantic_contains_uses_token_boundaries():
    assert semantic.compare_values("text-contains", "Safe", "Safe and protected")["result"] == "match"
    assert semantic.compare_values("text-contains", "Safe", "Safety check failed")["result"] == "mismatch"


def test_comparator_registry_covers_exact_mapped_drift_and_unknown_operator():
    assert semantic.compare_values("exact", "ready", "ready")["result"] == "match"
    mapped = semantic.compare_values(
        "intentional-presentation-map", "healthy", "Workspace ready",
        {"mapping": {"healthy": ["workspace ready"]}},
    )
    assert mapped["result"] == "mapped"
    assert semantic.compare_values("exact", "online", "offline")["result"] == "mismatch"
    with pytest.raises(ValueError, match="unknown comparator"):
        semantic.compare_values("invented", 1, 1)


def test_boolean_and_formatted_quantity_comparators_are_semantic():
    assert semantic.compare_values("boolean-equivalence", False, "false")["result"] == "mapped"
    assert semantic.compare_values("boolean-equivalence", False, "true")["result"] == "mismatch"
    assert semantic.compare_values("byte-format", 1_048_576, "1 MiB", {"tolerance": 1})["result"] == "mapped"
    assert semantic.compare_values("duration-format", 90, "1 min 30 sec", {"tolerance": 0.01})["result"] == "mapped"


def test_comparison_evidence_never_carries_raw_observed_strings():
    result = semantic.compare_values("exact", "private-host-name", "different-private-host-name")
    encoded = json.dumps(result, sort_keys=True)
    assert "private-host-name" not in encoded
    assert "different-private-host-name" not in encoded
    assert result["backend_value"]["type"] == "string"
    assert len(result["backend_value"]["fingerprint"]) == 16


def test_safe_redaction_rejects_secret_and_private_path():
    assert semantic.compare_values("safe-redaction", {}, "No secrets here")["result"] == "match"
    assert semantic.compare_values("safe-redaction", {}, "password=do-not-store")["result"] == "mismatch"
    assert semantic.compare_values("safe-redaction", {}, "/data/data/com.termux/files/home/private")["result"] == "mismatch"


def test_runtime_observation_schema_rejects_sensitive_property_names():
    payload = observation("identity", values={"token": "not-allowed"})
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(json.loads(OBS_SCHEMA.read_text())).validate(payload)


def test_termux_ssh_capture_is_loopback_only_and_classifies_connectivity(monkeypatch):
    assert capture.validate_remote_base_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"
    with pytest.raises(ValueError, match="loopback"):
        capture.validate_remote_base_url("http://192.168.1.10:8080")
    with pytest.raises(ValueError, match="credentials"):
        capture.validate_api_base_url("https://user:password@example.invalid")

    class Result:
        returncode = 255
        stdout = ""
        stderr = "connection unavailable"

    monkeypatch.setattr(capture.subprocess, "run", lambda *args, **kwargs: Result())
    with pytest.raises(capture.RuntimeUnavailable, match="ssh_unavailable"):
        capture.fetch_json_ssh("pocketlab-termux", "http://127.0.0.1:8080", "/api/lite/status", 5)


def test_runtime_capture_extractors_are_bounded_and_allowlisted():
    payloads = {
        "primary": {
            "items": [
                {"id": "server", "status": "online", "protected": True},
                {"id": "device", "status": "offline", "protected": False},
            ],
            "summary": {"status": "healthy"},
        }
    }
    assert capture.extract(payloads, {"route": "primary", "extract": "path", "path": "summary.status"}) == "healthy"
    assert capture.extract(payloads, {"route": "primary", "extract": "count", "path": "items"}) == 2
    assert capture.extract(payloads, {"route": "primary", "extract": "presence", "path": "summary.status"}) is True
    assert capture.extract(payloads, {"route": "primary", "extract": "count_where", "list_path": "items", "where": {"status": "online"}}) == 1
    assert capture.extract(payloads, {"route": "primary", "extract": "any", "list_path": "items", "where": {"protected": True}}) is True
    assert capture.extract(payloads, {"route": "primary", "extract": "find", "list_path": "items", "where": {"id": "server"}, "value_path": "status"}) == "online"
    assert capture.bounded("x" * 1000) == "x" * 240


def test_runtime_capture_failure_writes_safe_classification(tmp_path):
    domain = next(item for item in model()["domains"] if item["id"] == "home")

    def unavailable(_path: str):
        raise capture.RuntimeUnavailable("ssh_unavailable")

    payload = capture.capture_domain(domain, unavailable, "termux", "a" * 40, "lite-2026.08.06.1")
    assert payload["status"] == "runtime-unavailable"
    assert payload["error_code"] == "ssh_unavailable"
    assert payload["observations"] == {}
    capture.atomic_write(tmp_path / "unavailable.json", payload)


def test_runtime_capture_atomic_write_validates_schema_and_rejects_secrets(tmp_path):
    malformed = observation("home", values={"status": 42})
    malformed["source_commit"] = "not-a-commit"
    with pytest.raises(jsonschema.ValidationError):
        capture.atomic_write(tmp_path / "malformed.json", malformed)
    bad = observation("home", values={"status": "password=do-not-store"})
    with pytest.raises(AssertionError):
        capture.atomic_write(tmp_path / "bad.json", bad)
    good = observation("home", values={"status": "healthy"})
    target = tmp_path / "good.json"
    capture.atomic_write(target, good)
    assert json.loads(target.read_text())["observations"]["status"] == "healthy"


def test_runtime_comparison_uses_normalized_layer_by_default():
    assert comparison.NORMALIZED_ROOT == comparison.PARITY_ROOT / "normalized"
    source = (ROOT / "scripts" / "test" / "parity" / "promote_runtime_verification.py").read_text(encoding="utf-8")
    assert 'PARITY_ROOT / "normalized" / "runtime-comparison.json"' in source


def test_live_browser_capture_redacts_runtime_identities_and_uses_exact_tailscale_signal():
    source = (ROOT / "tests" / "e2e" / "lite-live.spec.ts").read_text(encoding="utf-8")
    assert "runtimePrivacyContext" in source
    assert "collectSensitiveValues" in source
    assert "sanitizeBooleanMap" in source
    assert "payload?.remote_access?.ip" in source
    assert "tailscale_ip_visible: privacy.tailscale_ip_visible" in source
    assert "home_cpu_note: text(resource?.querySelector('em'))" in source
    assert "serverIdentityVisible(" not in source


def test_stale_observation_is_not_drift(monkeypatch):
    payload = observation("home")
    payload["captured_at"] = (datetime.now(timezone.utc) - timedelta(days=3)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    monkeypatch.setenv("LITE_PARITY_MAX_EVIDENCE_AGE_SECONDS", "60")
    stale = comparison.mark_stale(payload)
    assert stale["status"] == "stale-evidence"
    runtime, status = comparison.semantic_status([], ["stale-evidence"])
    assert (runtime, status) == ("stale-evidence", "partial")


def test_coverage_status_preserves_failure_classification():
    assert comparison.coverage_status(["observed", "observed"]) == "observed"
    assert comparison.coverage_status(["observed", "stale-evidence"]) == "stale-evidence"
    assert comparison.coverage_status(["observed", "capture-failed"]) == "capture-failed"
    assert comparison.coverage_status(["observed", "runtime-unavailable"]) == "runtime-unavailable"


def test_missing_semantic_field_is_partial_not_verified():
    results = [
        {"result": "match", "boundary": "live-api-live-ui"},
        {"result": "not-observed", "boundary": "live-api-live-ui"},
    ]
    assert comparison.semantic_status(results, ["observed", "observed", "observed"]) == ("partial", "partial")


def test_capture_failure_and_runtime_unavailable_are_not_drift():
    assert comparison.semantic_status([], ["capture-failed"]) == ("capture-failed", "partial")
    assert comparison.semantic_status([], ["runtime-unavailable"]) == ("runtime-unavailable", "partial")


def test_live_api_to_termux_comparison_is_semantic_and_can_detect_drift():
    domain = next(item for item in model()["domains"] if item["id"] == "rules")
    backend = observation("rules", values={"status": "healthy", "protection_enabled": True})
    termux = observation("rules", "termux", values={"status": "healthy", "protection_enabled": False})
    results = comparison.termux_agreement(domain, backend, termux)
    assert any(item["id"] == "rules-termux-protection_enabled" and item["result"] == "mismatch" for item in results)
    assert all(item["boundary"] == "live-api-live-termux" and item["project"] == "termux" for item in results)


def test_cross_viewport_match_cannot_hide_missing_semantic_observations():
    cross_only = [{"result": "match", "boundary": "desktop-mobile"}]
    assert comparison.semantic_status(cross_only, ["observed", "observed", "observed"]) == ("partial", "partial")


def test_cross_viewport_evidence_is_fingerprinted_not_raw_text():
    desktop = observation(
        "home", "frontend", project="live-desktop",
        values={"headings": ["Private server name"], "button_names": ["Manage"], "status_labels": ["Ready"]},
    )
    mobile = observation(
        "home", "frontend", project="live-mobile",
        values={"headings": ["Private server name"], "button_names": ["Manage"], "status_labels": ["Ready"]},
    )
    result = comparison.viewport_agreement(desktop, mobile)
    encoded = json.dumps(result, sort_keys=True)
    assert "Private server name" not in encoded
    assert result["backend_value"]["type"] == "object"
    assert result["result"] == "match"


def test_unsupported_and_accepted_limitation_remain_distinct():
    unsupported = [{"result": "unsupported", "boundary": "live-api-live-ui"}]
    assert comparison.semantic_status(unsupported, ["observed", "observed", "observed"]) == ("unsupported", "partial")
    accepted = [{"result": "mismatch", "boundary": "live-api-live-ui", "accepted_limitation": True}]
    assert comparison.semantic_status(accepted, ["observed", "observed", "observed"]) == ("accepted-limitation", "verified")


def test_mismatch_is_valid_needs_review_evidence():
    results = [{"result": "mismatch"}]
    assert comparison.semantic_status(results, ["observed", "observed", "observed"]) == ("drift-detected", "needs-review")


def test_pairwise_generation_is_bounded_deterministic_and_honors_exclusions():
    first = generator.generate_pairwise_cases(model())
    second = generator.generate_pairwise_cases(model())
    assert first == second
    assert 1 <= len(first) <= 24
    for item in first:
        values = item["values"]
        assert not (values["action_progress"] == "running" and values["backend_availability"] == "unavailable")
        assert not (
            values["action_progress"] == "running"
            and values["backend_availability"] == "available"
            and values["projection_freshness"] == "fresh"
            and values["saved_snapshot"] == "present"
        )


def test_legacy_baseline_remains_coverage_only():
    payload = model()
    merged = generator.apply_runtime_baseline(payload, {
        "schema_version": "1.0.0", "sanitized": True, "status": "verified",
        "source_commit": "a" * 40, "release_tag": "lite-2026.08.05.2",
        "domains": [{"id": "recovery", "live_api_coverage": "verified", "live_termux_coverage": "verified", "status": "verified"}],
    })
    recovery = next(item for item in merged["domains"] if item["id"] == "recovery")
    assert recovery["live_api_coverage"] == "verified"
    assert recovery["runtime_parity"] == "unvalidated"
    assert recovery["status"] != "verified"


def test_v2_baseline_preserves_drift_in_generated_model():
    payload = model()
    domains = []
    for domain in payload["domains"]:
        domains.append({
            "id": domain["id"], "label": domain["label"],
            "live_api_coverage": "observed", "live_ui_coverage": "observed", "live_termux_coverage": "observed",
            "runtime_parity": "drift-detected" if domain["id"] == "rules" else "verified",
            "status": "needs-review" if domain["id"] == "rules" else "verified",
            "comparison_summary": {"match": 1, "mapped": 0, "mismatch": 1 if domain["id"] == "rules" else 0, "unsupported": 0, "not_observed": 0},
            "comparisons": [{
                "id": "rules-test", "boundary": "live-api-live-ui", "severity": "high", "operator": "exact",
                "result": "mismatch", "backend_value": True, "frontend_value": False,
                "explanation": "deliberate test mismatch", "project": "live-desktop",
            }] if domain["id"] == "rules" else [],
            "observation_fingerprints": {"backend": "a" * 64, "termux": "b" * 64, "live_desktop": "c" * 64, "live_mobile": "d" * 64},
        })
    baseline = {
        "schema_version": "2.0.0", "sanitized": True, "generated_at": "2026-08-06T10:00:00Z",
        "source_commit": "a" * 40, "release_tag": "lite-2026.08.06.1", "status": "needs-review",
        "browser_projects": ["live-desktop", "live-mobile"], "domains": domains,
    }
    merged = generator.apply_runtime_baseline(payload, baseline)
    rules = next(item for item in merged["domains"] if item["id"] == "rules")
    assert rules["runtime_parity"] == "drift-detected"
    assert rules["status"] == "needs-review"


def _set_path(payload: dict, path: str, value):
    if path in {'', '$'}:
        return
    current = payload
    parts = path.split('.')
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _canonical_runtime_values(domain: dict) -> tuple[dict, dict]:
    backend: dict = {}
    frontend: dict = {}
    screen_fragments: list[str] = []

    backend_fields = ((domain.get("live_observation_contract") or {}).get("backend") or {}).get("fields") or []
    for field in backend_fields:
        operator = field.get("authority_operator", "exact")
        if operator == "boolean-equivalence":
            backend[field["id"]] = True
        elif operator in {"numeric-tolerance", "percentage-format", "byte-format", "duration-format"}:
            backend[field["id"]] = 42
        else:
            backend[field["id"]] = "canonical-value"

    for mapping in domain['semantic_mappings']:
        path = mapping.get('backend_path', '$')
        if path == '$':
            continue
        operator = mapping['operator']
        if operator == 'boolean-equivalence':
            value = True
        elif operator == 'percentage-format':
            value = 42
        elif operator in {'identity-match', 'exact', 'normalized-string', 'case-insensitive'}:
            value = 'canonical-value'
        elif operator == 'text-contains':
            value = 'Canonical summary'
        elif operator in {'enum-map', 'state-machine-map', 'status-family', 'capability-map', 'intentional-presentation-map'}:
            raw = next(iter(mapping['mapping']))
            value = True if raw == 'true' else False if raw == 'false' else raw
        else:
            value = 'present'
        _set_path(backend, path, value)

    for mapping in domain['semantic_mappings']:
        operator = mapping['operator']
        backend_value = semantic.get_path(backend, mapping.get('backend_path', '$'))
        frontend_path = mapping.get('frontend_path', '$')
        if operator == 'safe-redaction':
            value = 'Sanitized user-facing summary'
        elif operator == 'presence':
            value = ['Available action']
        elif operator == 'boolean-equivalence':
            value = bool(backend_value)
        elif operator == 'percentage-format':
            value = f'CPU {backend_value}%'
        elif operator in {'identity-match', 'exact', 'normalized-string', 'case-insensitive'}:
            value = backend_value
        elif operator == 'text-contains':
            value = f'{backend_value} is ready'
        elif operator in {'enum-map', 'state-machine-map', 'status-family', 'capability-map', 'intentional-presentation-map'}:
            mapping_values = mapping['mapping']
            candidates = [str(backend_value), str(backend_value).casefold()]
            if isinstance(backend_value, bool):
                candidates.extend(['true' if backend_value else 'false', '1' if backend_value else '0'])
            expected = next(mapping_values[item] for item in candidates if item in mapping_values)
            value = expected[0] if isinstance(expected, list) else expected
        else:
            value = backend_value
        if frontend_path == 'screen_text':
            screen_fragments.append(str(value))
        else:
            _set_path(frontend, frontend_path, value)

    frontend['screen_text'] = ' · '.join(screen_fragments) or 'Sanitized user-facing summary'
    frontend.setdefault('headings', [domain['label']])
    frontend.setdefault('button_names', ['Manage'])
    frontend.setdefault('status_labels', ['Ready'])
    return backend, frontend


def test_compare_command_end_to_end_reports_partial_domains_truthfully(tmp_path):
    payload = model()
    input_root = tmp_path / 'parity'
    source = 'a' * 40
    release = 'lite-2026.08.06.1'
    for domain in payload['domains']:
        backend_values, frontend_values = _canonical_runtime_values(domain)
        for kind, values in [('backend', backend_values), ('termux', backend_values)]:
            target = input_root / kind / f"{domain['id']}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            item = observation(domain['id'], kind, values=values)
            item['source_commit'] = source
            item['release_tag'] = release
            target.write_text(json.dumps(item), encoding='utf-8')
        for project in ('live-desktop', 'live-mobile'):
            target = input_root / 'browser' / f"{domain['id']}-{project}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            item = observation(domain['id'], 'frontend', project=project, values=frontend_values)
            item['source_commit'] = source
            item['release_tag'] = release
            target.write_text(json.dumps(item), encoding='utf-8')

    output = tmp_path / 'runtime-comparison.json'
    completed = subprocess.run(
        [
            'python3', str(ROOT / 'scripts' / 'test' / 'parity' / 'compare_runtime_parity.py'),
            '--input-root', str(input_root), '--output', str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, 'TERM': 'xterm'},
    )
    assert completed.returncode == 2, completed.stdout + completed.stderr
    assert (
        "PASS runtime semantic comparison: "
        "7 domains, status=partial"
    ) in completed.stdout

    comparison = json.loads(
        output.read_text(encoding="utf-8")
    )

    assert comparison["status"] == "partial"
    assert len(comparison["domains"]) == 7

    domains = {
        domain["id"]: domain
        for domain in comparison["domains"]
    }

    assert set(domains) == {
        "home",
        "apps",
        "devices",
        "security",
        "identity",
        "rules",
        "recovery",
    }

    assert (
        domains["identity"]["implementation_status"]
        == "partial"
    )
    assert domains["identity"]["status"] == "partial"
    assert domains["identity"]["runtime_parity"] == "partial"

    assert (
        domains["rules"]["implementation_status"]
        == "partial"
    )
    assert domains["rules"]["status"] == "partial"
    assert domains["rules"]["runtime_parity"] == "partial"

    for domain_id in {
        "home",
        "apps",
        "devices",
        "security",
    }:
        assert (
            domains[domain_id]["implementation_status"]
            == "implemented"
        )
        assert domains[domain_id]["status"] == "verified"

    assert (
        domains["recovery"]["implementation_status"]
        == "implemented"
    )
    assert domains["recovery"]["status"] == "verified"
    assert domains["recovery"]["runtime_parity"] == "verified-with-mapped-presentation"
    jsonschema.Draft202012Validator(
        json.loads(CMP_SCHEMA.read_text())
    ).validate(comparison)
    assert len(comparison["domains"]) == 7
    implemented_domains = {
        "home",
        "apps",
        "devices",
        "security",
    }

    for domain_id in implemented_domains:
        assert domains[domain_id]["runtime_parity"] in {
            "verified",
            "verified-with-mapped-presentation",
        }

    for domain_id in {
        "identity",
        "rules",
    }:
        assert domains[domain_id]["runtime_parity"] == "partial"

    encoded = json.dumps(comparison, sort_keys=True)
    assert 'Canonical summary' not in encoded
    assert 'Sanitized user-facing summary' not in encoded

def test_domain_fingerprint_changes_only_for_modified_domain():
    original = model()
    changed = deepcopy(original)
    target = next(item for item in changed["domains"] if item["id"] == "devices")
    target["known_gaps"] = [*target["known_gaps"], "deterministic fingerprint test gap"]

    def fingerprints(payload: dict) -> dict[str, str]:
        outputs = generator.all_outputs(payload)
        return {
            domain["id"]: json.loads(
                outputs[ROOT / "contracts" / "generated" / "parity" / f"domain-{domain['id']}.json"]
            )["items"][0]["fingerprint"]
            for domain in payload["domains"]
        }

    before = fingerprints(original)
    after = fingerprints(changed)
    assert before["devices"] != after["devices"]
    assert {domain_id for domain_id in before if before[domain_id] != after[domain_id]} == {"devices"}


def test_generated_all_tab_docs_and_contracts_exist():
    subprocess.run(["python3", str(GENERATOR), "generate"], cwd=ROOT, check=True)
    required_sections = [
        "## 1. Current status",
        "## 9. Live API observation",
        "## 10. Live UI observation",
        "## 11. Live Termux observation",
        "## 12. Field-level semantic comparisons",
        "## 14. Detected drift",
        "## 18. Evidence hashes",
        "## 21. Failure attribution guidance",
        "## 22. Last promoted runtime result",
    ]
    for name in ("home", "apps", "devices", "security", "identity", "rules", "backup-restore"):
        path = ROOT / "docs" / "generated" / "development" / "validation" / "parity" / f"{name}.md"
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert all(section in text for section in required_sections)
    for name in ("comparator-registry", "runtime-scenario-registry", "pairwise-scenario-registry", "runtime-drift", "accepted-limitations"):
        assert (ROOT / "contracts" / "generated" / "parity" / f"{name}.json").exists()
    matrix = (ROOT / "docs" / "generated" / "development" / "validation" / "parity" / "runtime-verification-matrix.md").read_text(encoding="utf-8")
    assert all(label in matrix for label in ("Home", "Apps", "Devices", "Security", "Identity", "Rules", "Backup & Restore"))
    recovery_row = next(
        line
        for line in matrix.splitlines()
        if line.startswith("| Backup & Restore |")
    )
    assert "| verified | verified | verified |" in recovery_row
    assert (
        "| verified-with-mapped-presentation | verified |"
        in recovery_row
    )
    subprocess.run(["python3", str(GENERATOR), "check"], cwd=ROOT, check=True)
