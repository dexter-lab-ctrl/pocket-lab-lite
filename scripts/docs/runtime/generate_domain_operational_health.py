#!/usr/bin/env python3
"""Generate release-bound Lite operational health and platform capability evidence.

This generator is deliberately read-only with respect to live runtime state. It consumes
only the explicitly promoted, sanitized runtime-verification baseline plus canonical
repository contracts/metadata and writes a deterministic generated projection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime_common import ROOT, atomic_write, canonical_json, read_json, stable_json, validate_json
from runtime_redaction import assert_safe

BASELINE = ROOT / "contracts" / "parity" / "runtime-verification-baseline.json"
PARITY_MODEL = ROOT / "contracts" / "parity" / "parity-model.json"
DOCUMENTATION_PLATFORM = ROOT / "contracts" / "metadata" / "documentation-platform.json"
REASON_CODES = ROOT / "contracts" / "generated" / "reason-codes.json"
SCHEMA = ROOT / "schemas" / "runtime" / "domain-operational-health.schema.json"
OUTPUT = ROOT / "contracts" / "generated" / "runtime" / "domain-operational-health.json"

DOMAIN_ORDER = ("home", "apps", "devices", "security", "recovery", "identity", "rules")
HEALTH_PRECEDENCE = {"healthy": 0, "stale": 1, "degraded": 2, "unavailable": 3, "unvalidated": -1}
IMPLEMENTED = "implemented"
PARTIAL = "partial"


def value_fingerprint(value: Any) -> str:
    """Match the promoted parity sanitizer's deterministic scalar fingerprint."""
    return hashlib.sha256(json.dumps(value).encode("utf-8")).hexdigest()[:16]


def source_fingerprint(*values: Any) -> str:
    payload = [value for value in values]
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def normalize_status(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _comparison_map(domain: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in domain.get("comparisons", []) if item.get("id")}


def _domain_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in payload.get("domains", []) if item.get("id")}


def _semantic_mapping(parity_domain: dict[str, Any], mapping_id: str | None) -> dict[str, Any] | None:
    if not mapping_id:
        return None
    for item in parity_domain.get("semantic_mappings", []):
        if item.get("id") == mapping_id:
            return item
    return None


def _candidate_values(
    signal: dict[str, Any],
    parity_domain: dict[str, Any],
    *,
    known_reasons: set[str] | None = None,
) -> list[Any]:
    values: list[Any] = list(signal.get("candidates", []))
    mapping = _semantic_mapping(parity_domain, signal.get("candidate_mapping_id"))
    if mapping:
        values.extend(mapping.get("mapping", {}).keys())
    if signal.get("candidate_source") == "reason-codes" and known_reasons:
        values.extend(sorted(known_reasons))
    # bool candidates are useful for guard/evidence comparisons but should not be
    # broadened for status decoding unless explicitly supplied.
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        marker = canonical_json(value)
        if marker not in seen:
            seen.add(marker)
            result.append(value)
    return result


def decode_observed_value(
    comparison: dict[str, Any],
    candidates: Iterable[Any] = (),
) -> Any:
    value = comparison.get("backend_value")
    if not isinstance(value, dict):
        return value
    if value.get("type") != "string" or not value.get("present"):
        return None
    fingerprint = value.get("fingerprint")
    matches = [candidate for candidate in candidates if value_fingerprint(candidate) == fingerprint]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise ValueError(f"unable to decode promoted fingerprint for comparison {comparison.get('id')!r}")
    raise ValueError(f"ambiguous promoted fingerprint for comparison {comparison.get('id')!r}")


def _known_reason_codes(reason_payload: dict[str, Any]) -> set[str]:
    body = reason_payload.get("reason_codes", {})
    rows = body.get("reason_codes", []) if isinstance(body, dict) else []
    return {str(row.get("code")) for row in rows if isinstance(row, dict) and row.get("code")}


def _runtime_observed(domain: dict[str, Any]) -> bool:
    return all(
        str(domain.get(field, "")).lower() == "observed"
        for field in ("live_api_coverage", "live_termux_coverage", "live_ui_coverage")
    )


def _choose_health(current: str, candidate: str) -> str:
    if current == "unvalidated":
        return candidate
    return candidate if HEALTH_PRECEDENCE[candidate] > HEALTH_PRECEDENCE[current] else current


def evaluate_domain_health(
    domain_id: str,
    baseline_domain: dict[str, Any],
    parity_domain: dict[str, Any],
    policy: dict[str, Any] | None,
    known_reasons: set[str],
) -> tuple[str, str | None, float | None, list[dict[str, Any]]]:
    """Pure domain evaluator used by the generator and table-driven tests."""
    implementation = str(baseline_domain.get("implementation_status") or baseline_domain.get("status") or "unknown")
    if implementation != IMPLEMENTED:
        return "unvalidated", None, None, []

    if not _runtime_observed(baseline_domain):
        raise ValueError(f"{domain_id}: implemented domain does not have all promoted runtime lanes observed")
    if not policy:
        raise ValueError(f"{domain_id}: implemented/observed domain has no operational-health policy")

    comparisons = _comparison_map(baseline_domain)
    status_signal = policy.get("status_signal")
    if not status_signal:
        raise ValueError(f"{domain_id}: operational-health policy has no status signal")

    status_id = str(status_signal.get("comparison_id") or "")
    status_comparison = comparisons.get(status_id)
    if not status_comparison:
        raise ValueError(f"{domain_id}: promoted baseline is missing required health signal {status_id}")
    candidates = _candidate_values(status_signal, parity_domain, known_reasons=known_reasons)
    observed_status = decode_observed_value(status_comparison, candidates)
    normalized = normalize_status(observed_status)
    health_map = {normalize_status(key): value for key, value in status_signal.get("health_map", {}).items()}
    health = health_map.get(normalized)
    if health not in HEALTH_PRECEDENCE:
        raise ValueError(f"{domain_id}: observed status has no canonical health mapping")

    reason = None
    reason_by_health = status_signal.get("reason_by_health", {})
    if health != "healthy":
        reason = reason_by_health.get(health)

    evidence: list[dict[str, Any]] = [
        {
            "comparison_id": status_id,
            "observed_value": observed_status,
            "health_effect": health,
            "reason": reason,
        }
    ]

    # A canonical reason signal, when present, is authoritative for a non-healthy state.
    reason_signal = policy.get("reason_signal")
    authoritative_reason = False
    if reason_signal:
        reason_id = str(reason_signal.get("comparison_id") or "")
        reason_comparison = comparisons.get(reason_id)
        if not reason_comparison:
            raise ValueError(f"{domain_id}: promoted baseline is missing reason signal {reason_id}")
        reason_candidates = _candidate_values(reason_signal, parity_domain, known_reasons=known_reasons)
        observed_reason = decode_observed_value(reason_comparison, reason_candidates)
        if observed_reason is not None:
            observed_reason = str(observed_reason)
            if observed_reason not in known_reasons:
                raise ValueError(f"{domain_id}: promoted reason is not a canonical reason code")
            reason = observed_reason
            authoritative_reason = True
        evidence.append(
            {
                "comparison_id": reason_id,
                "observed_value": observed_reason,
                "health_effect": health,
                "reason": reason if health != "healthy" else None,
            }
        )

    for guard in policy.get("guards", []):
        comparison_id = str(guard.get("comparison_id") or "")
        comparison = comparisons.get(comparison_id)
        if not comparison:
            raise ValueError(f"{domain_id}: promoted baseline is missing guard signal {comparison_id}")
        expected = guard.get("expected")
        observed = decode_observed_value(comparison, [expected])
        effect = "healthy"
        effect_reason = None
        if observed != expected:
            effect = str(guard.get("mismatch_health") or "degraded")
            effect_reason = str(guard.get("reason") or "")
            if effect_reason not in known_reasons:
                raise ValueError(f"{domain_id}: guard reason {effect_reason!r} is not canonical")
            previous = health
            health = _choose_health(health, effect)
            if not authoritative_reason and HEALTH_PRECEDENCE[effect] >= HEALTH_PRECEDENCE[previous]:
                reason = effect_reason
        evidence.append(
            {
                "comparison_id": comparison_id,
                "observed_value": observed,
                "health_effect": effect,
                "reason": effect_reason,
            }
        )

    freshness_age_seconds: float | None = None
    freshness_signal = policy.get("freshness_age_signal")
    if freshness_signal:
        comparison_id = str(freshness_signal.get("comparison_id") or "")
        comparison = comparisons.get(comparison_id)
        if not comparison:
            raise ValueError(f"{domain_id}: promoted baseline is missing freshness signal {comparison_id}")
        observed_age = decode_observed_value(comparison)
        if not isinstance(observed_age, (int, float)) or isinstance(observed_age, bool) or observed_age < 0:
            raise ValueError(f"{domain_id}: freshness signal is not a non-negative number")
        unit = str(freshness_signal.get("unit") or "seconds")
        freshness_age_seconds = float(observed_age) / 1000.0 if unit == "milliseconds" else float(observed_age)
        threshold = float(policy.get("freshness_threshold_seconds") or 0)
        effect = "healthy"
        stale_reason = None
        if threshold > 0 and freshness_age_seconds > threshold:
            effect = "stale"
            stale_reason = str(freshness_signal.get("stale_reason") or "")
            if stale_reason not in known_reasons:
                raise ValueError(f"{domain_id}: stale reason {stale_reason!r} is not canonical")
            previous = health
            health = _choose_health(health, "stale")
            if not authoritative_reason and HEALTH_PRECEDENCE["stale"] >= HEALTH_PRECEDENCE[previous]:
                reason = stale_reason
        evidence.append(
            {
                "comparison_id": comparison_id,
                "observed_value": round(freshness_age_seconds, 3),
                "health_effect": effect,
                "reason": stale_reason,
            }
        )

    if health == "healthy":
        reason = None
    elif not reason:
        raise ValueError(f"{domain_id}: non-healthy promoted state has no canonical reason")
    elif reason not in known_reasons:
        raise ValueError(f"{domain_id}: health reason {reason!r} is not canonical")

    return health, reason, freshness_age_seconds, evidence


def _domain_record(
    domain_id: str,
    baseline_domain: dict[str, Any],
    parity_domain: dict[str, Any],
    policy: dict[str, Any] | None,
    known_reasons: set[str],
    observed_at: str | None,
) -> dict[str, Any]:
    implementation = str(baseline_domain.get("implementation_status") or baseline_domain.get("status") or "unknown")
    observed = _runtime_observed(baseline_domain)
    runtime_status = "observed" if observed else "partial"
    semantic_parity = str(baseline_domain.get("runtime_parity") or "unvalidated")

    if implementation == IMPLEMENTED:
        health, reason, age, evidence = evaluate_domain_health(
            domain_id, baseline_domain, parity_domain, policy, known_reasons
        )
        confidence = "release-promoted"
        evidence_status = "release-promoted"
        threshold = int((policy or {}).get("freshness_threshold_seconds") or 0) or None
        freshness = (
            "stale"
            if age is not None and threshold is not None and age > threshold
            else "promoted-observation"
        )
        readiness = {
            "healthy": "ready-with-guardrails",
            "stale": "degraded",
            "degraded": "degraded",
            "unavailable": "unavailable",
            "unvalidated": "unvalidated",
        }[health]
        configured_write = str((policy or {}).get("write_safety") or "unvalidated")
        write_safety = configured_write if health == "healthy" or configured_write == "not-applicable" else "blocked"
        dependencies = list((policy or {}).get("dependencies", []))
    else:
        health, reason, age, evidence = "unvalidated", None, None, []
        confidence = "partial" if implementation == PARTIAL else "unvalidated"
        evidence_status = "release-promoted" if observed else "unvalidated"
        threshold = None
        freshness = "promoted-observation" if observed else "unvalidated"
        readiness = "partial" if implementation == PARTIAL else "unvalidated"
        write_safety = "unvalidated"
        # Partial domains retain their canonical dependency model without promoting an
        # aggregate health conclusion from incomplete implementation/runtime coverage.
        dependencies = list((policy or {}).get("dependencies", []))

    comparison_ids = [item["comparison_id"] for item in evidence]
    return {
        "implementation_status": implementation,
        "runtime_status": runtime_status,
        "operational_health": health,
        "reason": reason,
        "severity": "unknown",  # populated by the caller from canonical policy vocabulary
        "freshness": freshness,
        "freshness_age_seconds": age,
        "freshness_threshold_seconds": threshold,
        "observed_at": observed_at if observed else None,
        "evidence_status": evidence_status,
        "confidence": confidence,
        "write_safety": write_safety,
        "readiness": readiness,
        "semantic_parity": semantic_parity,
        "dependencies": dependencies,
        "source": {
            "runtime_baseline": "contracts/parity/runtime-verification-baseline.json",
            "parity_model": "contracts/parity/parity-model.json",
            "policy": "contracts/metadata/documentation-platform.json",
            "evidence_comparisons": comparison_ids,
        },
        "evidence": evidence,
    }


def _comparison_matches(
    comparison: dict[str, Any],
    expected: Any,
) -> bool:
    value = comparison.get("backend_value")
    if isinstance(value, dict) and value.get("type") == "string" and value.get("present"):
        return value.get("fingerprint") == value_fingerprint(expected)
    return value == expected


def _platform_capabilities(
    baseline_domains: dict[str, dict[str, Any]],
    domain_records: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    capabilities = {item["name"]: item for item in metadata.get("capabilities", [])}
    platforms = {item["name"]: item for item in metadata.get("platforms", [])}
    bindings = {
        (item["capability"], item["platform"]): item
        for item in metadata.get("platform_capability_bindings", [])
    }
    rows: list[dict[str, Any]] = []

    for capability_name in sorted(capabilities):
        capability = capabilities[capability_name]
        for platform_name in sorted(platforms):
            platform = platforms[platform_name]
            binding = bindings.get((capability_name, platform_name))
            role = str(platform.get("role") or "not-applicable")
            source_refs = [
                "contracts/metadata/documentation-platform.json",
                str(capability.get("source")),
                str(platform.get("source")),
            ]
            source_refs = list(dict.fromkeys(ref for ref in source_refs if ref and ref != "None"))

            if role in {"control-client", "development"}:
                status = "not-applicable"
                evidence_status = "not-applicable"
                source_domain = None
                evidence_ids: list[str] = []
                rationale = (
                    "This platform is a control/development surface; Pocket Lab capabilities "
                    "remain backend/runtime-owned and are not executed here."
                )
            elif not binding:
                status = "unvalidated"
                evidence_status = "unvalidated"
                source_domain = None
                evidence_ids = []
                rationale = "No canonical repository binding currently claims this capability on this platform."
            else:
                source_domain = str(binding.get("source_domain") or "") or None
                expected_map = dict(binding.get("evidence_comparisons", {}))
                evidence_ids = sorted(expected_map)
                rationale = str(binding.get("rationale") or "Canonical source-derived capability binding.")
                status = str(binding.get("source_status") or "implemented")
                evidence_status = "source-derived"
                role = str(binding.get("role") or role)

                if expected_map:
                    if not source_domain or source_domain not in baseline_domains:
                        raise ValueError(
                            f"platform capability {capability_name}/{platform_name}: promoted evidence has no source domain"
                        )
                    comparisons = _comparison_map(baseline_domains[source_domain])
                    matched = True
                    for comparison_id, expected in expected_map.items():
                        comparison = comparisons.get(comparison_id)
                        if not comparison:
                            raise ValueError(
                                f"platform capability {capability_name}/{platform_name}: "
                                f"missing promoted comparison {comparison_id}"
                            )
                        matched = matched and _comparison_matches(comparison, expected)
                    source_refs.append("contracts/parity/runtime-verification-baseline.json")
                    source_health = domain_records[source_domain]["operational_health"]
                    source_runtime = domain_records[source_domain]["runtime_status"]
                    if matched and source_health == "healthy" and source_runtime == "observed":
                        status = "verified"
                    elif source_runtime == "observed":
                        status = "observed"
                    else:
                        status = "implemented"
                    evidence_status = "release-promoted" if source_runtime == "observed" else "source-derived"

            rows.append(
                {
                    "capability": capability_name,
                    "capability_name": str(capability.get("label") or capability_name),
                    "platform": platform_name,
                    "role": role,
                    "status": status,
                    "evidence_status": evidence_status,
                    "source_domain": source_domain,
                    "evidence_comparisons": evidence_ids,
                    "rationale": rationale,
                    "source_refs": list(dict.fromkeys(source_refs)),
                }
            )
    return rows


def build_projection() -> dict[str, Any]:
    baseline = read_json(BASELINE)
    parity_model = read_json(PARITY_MODEL)
    metadata = read_json(DOCUMENTATION_PLATFORM)
    reason_payload = read_json(REASON_CODES)

    if baseline.get("sanitized") is not True:
        raise ValueError("runtime verification baseline is not marked sanitized")
    release_tag = baseline.get("release_tag")
    source_commit = baseline.get("source_commit")
    promoted_at = baseline.get("promoted_at")
    if not release_tag or not source_commit or not promoted_at:
        raise ValueError("runtime verification baseline is not explicitly release/source/promotion bound")

    baseline_domains = _domain_map(baseline)
    parity_domains = _domain_map(parity_model)
    known_reasons = _known_reason_codes(reason_payload)
    health_policy = metadata.get("operational_health", {})
    policies = health_policy.get("domains", {})
    severity_map = health_policy.get("severity_by_health", {})

    missing = [domain_id for domain_id in DOMAIN_ORDER if domain_id not in baseline_domains or domain_id not in parity_domains]
    if missing:
        raise ValueError("promoted parity inputs are missing required domains: " + ", ".join(missing))

    domain_records: dict[str, dict[str, Any]] = {}
    for domain_id in DOMAIN_ORDER:
        record = _domain_record(
            domain_id,
            baseline_domains[domain_id],
            parity_domains[domain_id],
            policies.get(domain_id),
            known_reasons,
            baseline.get("generated_at"),
        )
        record["severity"] = str(severity_map.get(record["operational_health"], "unknown"))
        domain_records[domain_id] = record

    projection = {
        "schema_version": "1.0.0",
        "schema_revision": 1,
        "release_tag": release_tag,
        "source_commit": source_commit,
        "promoted_at": promoted_at,
        "observed_at": baseline.get("generated_at"),
        "sanitized": True,
        "runtime_baseline_status": str(baseline.get("status") or "unknown"),
        "source_fingerprint": source_fingerprint(
            baseline,
            parity_model,
            metadata.get("operational_health", {}),
            metadata.get("capabilities", []),
            metadata.get("platforms", []),
            metadata.get("platform_capability_bindings", []),
            reason_payload.get("metadata", {}),
            sorted(known_reasons),
        ),
        "domains": domain_records,
        "platform_capabilities": _platform_capabilities(baseline_domains, domain_records, metadata),
    }
    validate_projection(projection, known_reasons=known_reasons)
    return projection


def validate_projection(payload: dict[str, Any], *, known_reasons: set[str] | None = None) -> None:
    validate_json(payload, SCHEMA)
    assert_safe(payload, context="domain operational-health artifact")

    baseline = read_json(BASELINE)
    for field in ("release_tag", "source_commit", "promoted_at"):
        if payload.get(field) != baseline.get(field):
            raise ValueError(f"operational-health artifact {field} does not match promoted baseline")
    if payload.get("sanitized") is not True or baseline.get("sanitized") is not True:
        raise ValueError("operational-health release binding must remain sanitized")

    if known_reasons is None:
        known_reasons = _known_reason_codes(read_json(REASON_CODES))

    for domain_id, record in payload.get("domains", {}).items():
        if (
            record.get("implementation_status") == IMPLEMENTED
            and record.get("runtime_status") == "observed"
            and record.get("evidence_status") == "release-promoted"
            and record.get("operational_health") == "unvalidated"
        ):
            raise ValueError(f"{domain_id}: implemented + observed + promoted must not silently become unvalidated")
        health = record.get("operational_health")
        reason = record.get("reason")
        if health in {"stale", "degraded", "unavailable"}:
            if not reason:
                raise ValueError(f"{domain_id}: {health} state requires a reason")
            if reason not in known_reasons:
                raise ValueError(f"{domain_id}: {health} reason is not canonical")

    # Regression guard for the architecture principle: semantic parity and health are independent.
    recovery = payload.get("domains", {}).get("recovery", {})
    if recovery.get("semantic_parity") == "verified-with-mapped-presentation":
        if recovery.get("operational_health") == "unvalidated":
            raise ValueError("Recovery verified semantic parity must retain an independently evaluated health state")

    capabilities = read_json(DOCUMENTATION_PLATFORM).get("capabilities", [])
    platforms = read_json(DOCUMENTATION_PLATFORM).get("platforms", [])
    rows = payload.get("platform_capabilities", [])
    expected_count = len(capabilities) * len(platforms)
    if len(rows) != expected_count:
        raise ValueError(f"platform capability matrix is incomplete: {len(rows)} != {expected_count}")

    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (str(row.get("capability")), str(row.get("platform")))
        if key in seen:
            raise ValueError(f"duplicate platform capability row: {key}")
        seen.add(key)
        if row.get("status") == "verified":
            if row.get("evidence_status") != "release-promoted" or not row.get("evidence_comparisons"):
                raise ValueError(f"verified platform capability lacks promoted evidence: {key}")
        if row.get("role") in {"control-client", "development"} and row.get("status") == "verified":
            raise ValueError(f"control/development surface must not claim runtime capability verification: {key}")
        if row.get("status") == "not-applicable" and not str(row.get("rationale") or "").strip():
            raise ValueError(f"not-applicable platform capability lacks rationale: {key}")


def generate() -> None:
    payload = build_projection()
    content = stable_json(payload)
    current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else None
    if current != content:
        atomic_write(OUTPUT, content)
    print(
        "PASS operational health generate: "
        f"{len(payload['domains'])} domains, {len(payload['platform_capabilities'])} platform capability rows, "
        f"release={payload['release_tag']}"
    )


def check() -> None:
    expected = stable_json(build_projection())
    if not OUTPUT.exists():
        raise SystemExit(f"FAIL operational health check: missing {OUTPUT.relative_to(ROOT)}")
    actual = OUTPUT.read_text(encoding="utf-8")
    if actual != expected:
        raise SystemExit("FAIL operational health check: generated artifact is stale")
    validate_projection(json.loads(actual))
    print(
        "PASS operational health check: "
        f"{len(json.loads(actual)['domains'])} domains, "
        f"{len(json.loads(actual)['platform_capabilities'])} platform capability rows"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "check"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode == "generate":
        generate()
    else:
        check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
