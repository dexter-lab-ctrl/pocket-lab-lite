#!/usr/bin/env python3
"""Pocket Lab Lite Documentation IA with Security Assurance correlation extension.

The established IA implementation is preserved in documentation_ia_core.py. This adapter
adds deterministic Security Assurance correlation outputs generated only from canonical
repository registries and already-published sanitized report JSON, then re-runs the existing
IA inventory/search/link validation over the combined projection.
"""
from __future__ import annotations

import documentation_ia_core as _core
from security_assurance_correlation import build_projection as _build_security_assurance_projection

# Preserve the complete existing module API, including underscore-prefixed helpers used by
# repository tests. Only build()/main() are extended below.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

_SECURITY_SEARCH = {
    "security assurance report": {
        "aliases": ["assurance report", "security qualification", "qualification evidence", "latest security qualification"],
        "destinations": [
            "generated/enterprise/hubs/security-assurance/reports/index.md",
            "generated/enterprise/hubs/security-assurance/model-and-evidence.md",
        ],
    },
    "model assurance evidence": {
        "aliases": ["threat model evidence", "attack path evidence", "model to evidence", "security evidence correlation"],
        "destinations": [
            "generated/enterprise/hubs/security-assurance/model-assurance-evidence.md",
            "generated/enterprise/threat-model/assurance-evidence.md",
        ],
    },
    "security human review": {
        "aliases": ["human review required", "residual security review", "automated pass human review"],
        "destinations": [
            "generated/enterprise/hubs/security-assurance/how-to-read.md",
            "generated/enterprise/threat-model/evidence.md",
        ],
    },
    "stride qualification evidence": {
        "aliases": ["stride evidence", "stride assurance", "threat category qualification"],
        "destinations": ["generated/enterprise/hubs/security-assurance/stride-evidence.md"],
    },
    "owasp qualification evidence": {
        "aliases": ["owasp evidence", "owasp assurance", "owasp top 10 qualification"],
        "destinations": ["generated/enterprise/hubs/security-assurance/owasp-evidence.md"],
    },
}


def _extend_search(search: dict) -> dict:
    result = dict(search)
    entries = [dict(row) for row in result.get("entries", [])]
    by_name = {str(row.get("canonical")): row for row in entries}
    for canonical, spec in _SECURITY_SEARCH.items():
        by_name[canonical] = {
            "canonical": canonical,
            "aliases": sorted(set(spec["aliases"])),
            "destinations": list(spec["destinations"]),
            "intent_priority": "canonical-reference",
        }
    result["entries"] = [by_name[key] for key in sorted(by_name)]
    return result


def _security_page_links(correlation: dict) -> list[dict]:
    """Emit page-to-page IA links only; AP/control/scenario joins stay in the correlation contract."""
    base = "generated/enterprise/hubs/security-assurance"
    rows = [
        ("reports", f"{base}/reports/index.md", "qualification-evidence"),
        ("model-and-evidence", f"{base}/model-and-evidence.md", "explains-truth-layers"),
        ("scenario-walkthroughs", f"{base}/scenario-walkthroughs.md", "walks-model-evidence"),
        ("stride-evidence", f"{base}/stride-evidence.md", "classifies-stride-evidence"),
        ("owasp-evidence", f"{base}/owasp-evidence.md", "classifies-owasp-evidence"),
        ("model-assurance-evidence", f"{base}/model-assurance-evidence.md", "correlates-model-evidence"),
        ("scenario-model", f"{base}/scenario-model.md", "correlates-scenario-model"),
        ("how-to-read", f"{base}/how-to-read.md", "explains-security-docs"),
        ("threat-model-assurance", "generated/enterprise/threat-model/assurance-evidence.md", "reverse-model-evidence-link"),
    ]
    source = _core.page_id("generated/enterprise/hubs/security-assurance.md")
    return [
        {
            "id": f"link:hub:security-assurance:correlation:{key}",
            "source": source,
            "relation_type": relation,
            "target": _core.page_id(target),
            "target_type": "page",
            "label": key.replace("-", " ").title(),
            "evidence": [
                "scripts/docs/enterprise/security_assurance_correlation.py",
                "contracts/generated/documentation-enterprise/security-assurance-correlation.json",
            ],
        }
        for key, target, relation in rows
    ]


def build(root=ROOT, overrides=None):
    # First obtain the established projection. Security-specific search destinations are not
    # introduced until the corresponding planned pages are in the combined output set, so the
    # existing core validator never sees dangling destinations.
    outputs, ia_contract, cross_contract, search = _core.build(root, overrides=overrides)
    security_outputs, correlation = _build_security_assurance_projection(root)
    outputs.update(security_outputs)

    # Add Security Assurance page relations and static lexical search aliases, then rebuild
    # the page inventory over the exact combined planned output set.
    merged_relations = list(cross_contract.get("relations", [])) + _security_page_links(correlation)
    dedup = {str(row["id"]): row for row in merged_relations}
    cross_contract = dict(cross_contract)
    cross_contract["relations"] = [dedup[key] for key in sorted(dedup)]
    search = _extend_search(search)

    ia_contract = dict(ia_contract)
    extensions = dict(ia_contract.get("extensions") or {})
    extensions["security_assurance_correlation"] = {
        "status": "generated",
        "contract": "contracts/generated/documentation-enterprise/security-assurance-correlation.json",
        "hub": "generated/enterprise/hubs/security-assurance.md",
        "report_index": "generated/enterprise/hubs/security-assurance/reports/index.md",
        "published_report_count": correlation.get("published_report_count", 0),
        "latest_suite_runtime_shas": correlation.get("latest_suite_runtime_shas", []),
        "latest_suite_set_same_runtime_sha": correlation.get("latest_suite_set_same_runtime_sha", False),
        "live_runtime": False,
    }
    ia_contract["extensions"] = extensions
    ia_contract["pages"] = _core.build_page_inventory(root, outputs)
    ia_contract["page_count"] = len(ia_contract["pages"])
    ia_contract["cross_link_count"] = len(cross_contract["relations"])
    ia_contract["source_fingerprint"] = _core.digest({
        "pages": ia_contract["pages"],
        "journeys": ia_contract["feature_journeys"],
        "top_level": ia_contract["top_level"],
        "security_assurance": correlation,
    })

    # Documentation Platform self-pages expose final counts/search metadata, so re-render them
    # after correlation integration and inventory once more before serializing contracts.
    outputs.update(_core.render_documentation_platform_pages(
        ia_contract,
        cross_contract["relations"],
        search,
    ))
    ia_contract["pages"] = _core.build_page_inventory(root, outputs)
    ia_contract["page_count"] = len(ia_contract["pages"])
    ia_contract["source_fingerprint"] = _core.digest({
        "pages": ia_contract["pages"],
        "journeys": ia_contract["feature_journeys"],
        "top_level": ia_contract["top_level"],
        "security_assurance": correlation,
    })

    outputs[root / "contracts/generated/documentation-enterprise/information-architecture.json"] = _core.stable(ia_contract)
    outputs[root / "contracts/generated/documentation-enterprise/documentation-cross-links.json"] = _core.stable(cross_contract)
    outputs[root / "contracts/generated/documentation-enterprise/documentation-search.json"] = _core.stable(search)

    errors = _core.validate(root, outputs, ia_contract, cross_contract, search, overrides=overrides)
    if errors:
        raise ValueError("Documentation IA validation failed:\n" + "\n".join(f"- {item}" for item in errors))
    return outputs, ia_contract, cross_contract, search


def main() -> int:
    parser = _core.argparse.ArgumentParser()
    parser.add_argument("mode", choices=["generate", "check"])
    args = parser.parse_args()
    try:
        outputs, contract, cross, search = build(ROOT)
    except ValueError as exc:
        print(f"FAIL documentation IA validation\n{exc}")
        return 1
    if args.mode == "generate":
        changed = _core.write(outputs)
        print(
            f"PASS documentation IA generated: {len(outputs)} artifacts ({changed} changed), "
            f"{len(contract['pages'])} pages, {len(cross['relations'])} relations"
        )
        return 0
    errors = _core.check(outputs)
    if errors:
        print("FAIL documentation IA check")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS documentation IA check: {len(outputs)} deterministic artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
