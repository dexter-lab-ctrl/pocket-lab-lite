#!/usr/bin/env python3
"""Pocket Lab Lite Documentation IA with Security Assurance correlation extension.

The established IA implementation is preserved in documentation_ia_core.py. This thin
extension adds deterministic Security Assurance correlation outputs generated only from
canonical repository registries and already-published sanitized report JSON.
"""
from __future__ import annotations

import documentation_ia_core as _core
from security_assurance_correlation import build_projection as _build_security_assurance_projection

# Preserve the complete existing module API, including underscore-prefixed helpers used by
# repository tests. Only build() is extended below.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)


def build(root=ROOT, overrides=None):
    outputs, ia_contract, cross_links, search = _core.build(root, overrides=overrides)
    security_outputs, correlation = _build_security_assurance_projection(root)
    outputs.update(security_outputs)
    ia_contract = dict(ia_contract)
    items = dict(ia_contract.get("extensions") or {})
    items["security_assurance_correlation"] = {
        "status": "generated",
        "contract": "contracts/generated/documentation-enterprise/security-assurance-correlation.json",
        "hub": "generated/enterprise/hubs/security-assurance.md",
        "published_report_count": correlation.get("published_report_count", 0),
        "latest_suite_runtime_shas": correlation.get("latest_suite_runtime_shas", []),
        "latest_suite_set_same_runtime_sha": correlation.get("latest_suite_set_same_runtime_sha", False),
    }
    ia_contract["extensions"] = items
    return outputs, ia_contract, cross_links, search
