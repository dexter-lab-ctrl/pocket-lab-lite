#!/usr/bin/env python3
"""Run the platform catalog generator with additive reason-code metadata.

The main documentation-platform metadata remains authoritative. Identity/Rules
may add exact reason-code entries in a small dedicated supplement when the
compact fallback semantics (403, non-terminal) are insufficient. This runner
merges those entries without weakening undocumented-code detection and includes
the supplement in generated source fingerprints.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
GENERATOR_PATH = HERE / "generate_platform_catalogs.py"
SUPPLEMENT_PATH = HERE.parents[2] / "contracts/metadata/identity-rules-reason-code-overrides.json"


def _load_generator():
    spec = importlib.util.spec_from_file_location("pocketlab_generate_platform_catalogs", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    generator = _load_generator()
    base_metadata = generator.metadata
    base_fingerprint = generator.fingerprint

    def merged_metadata() -> dict[str, Any]:
        data = dict(base_metadata())
        supplement = generator.read_json(SUPPLEMENT_PATH, {"reason_codes": []})
        entries = supplement.get("reason_codes", []) if isinstance(supplement, dict) else []
        existing = [dict(item) for item in data.get("reason_codes", [])]
        by_code = {str(item.get("code") or ""): index for index, item in enumerate(existing)}
        for raw in entries:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            code = str(item.get("code") or "").strip()
            if not code:
                continue
            if code in by_code:
                existing[by_code[code]] = item
            else:
                by_code[code] = len(existing)
                existing.append(item)
        data["reason_codes"] = existing
        return data

    def fingerprint_with_supplement(paths: Iterable[Path]):
        values = list(paths)
        if SUPPLEMENT_PATH.exists() and generator.META_PATH in values and SUPPLEMENT_PATH not in values:
            values.append(SUPPLEMENT_PATH)
        return base_fingerprint(values)

    generator.metadata = merged_metadata
    generator.fingerprint = fingerprint_with_supplement
    return int(generator.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
