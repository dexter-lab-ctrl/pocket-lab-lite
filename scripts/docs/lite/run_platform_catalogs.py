#!/usr/bin/env python3
"""Supplement-aware entry point for Pocket Lab Lite platform catalogs.

The source generator remains responsible for every catalog. This module applies
small exact Identity/Rules reason-code overrides before exposing the generator's
public API or CLI, so Taskfile execution and deterministic regression tests use
the same canonical metadata view.
"""
from __future__ import annotations

import importlib.util
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


def _configure(generator):
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
    return generator


_generator = _configure(_load_generator())

# Expose the source generator's public API so tests and callers can use this
# entry point exactly as they used generate_platform_catalogs.py. Private
# helpers remain available through normal module attribute fallback below.
for _name in dir(_generator):
    if not _name.startswith("_") and _name not in globals():
        globals()[_name] = getattr(_generator, _name)


def __getattr__(name: str):
    return getattr(_generator, name)


def main() -> int:
    return int(_generator.main() or 0)


if __name__ == "__main__":
    raise SystemExit(main())
