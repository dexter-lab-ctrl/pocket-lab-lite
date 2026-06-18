#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "contracts/generated/openapi.json"


CANDIDATE_MODULES = [
    "api_fastapi.main",
    "api_fastapi.app",
    "api_fastapi.server",
    "runtime.api_fastapi.main",
    "runtime.api_fastapi.app",
    "runtime.api_fastapi.server",
]


def add_runtime_paths() -> None:
    candidates = [
        ROOT,
        ROOT / "pocket-lab-final-structure",
        ROOT / "pocket-lab-final-structure/runtime",
        ROOT / "pocket-lab-final-structure/runtime/api_fastapi",
        ROOT / "runtime",
        ROOT / "runtime/api_fastapi",
    ]

    for candidate in candidates:
        if candidate.exists():
            sys.path.insert(0, str(candidate))


def load_app() -> Any:
    add_runtime_paths()

    errors: list[str] = []

    for module_name in CANDIDATE_MODULES:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            errors.append(f"{module_name}: import failed: {exc}")
            continue

        for attr in ("app", "application"):
            app = getattr(module, attr, None)
            if app is not None:
                return app

        for factory in ("create_app", "build_app"):
            fn = getattr(module, factory, None)
            if callable(fn):
                return fn()

        errors.append(f"{module_name}: no app/application/create_app/build_app found")

    joined = "\n".join(errors)
    raise RuntimeError(f"Could not load FastAPI app. Tried:\n{joined}")


def main() -> None:
    os.environ.setdefault("POCKETLAB_TEST_MODE", "1")
    os.environ.setdefault("POCKETLAB_NATS_REQUIRED", "false")
    os.environ.setdefault("POCKETLAB_NATS_REQUIRE_JETSTREAM", "false")
    os.environ.setdefault("POCKETLAB_STATE_DIR", str(ROOT / ".pocketlab-dev/docs-openapi-state"))

    app = load_app()

    if not hasattr(app, "openapi"):
        raise TypeError("Loaded object does not look like a FastAPI app; missing .openapi()")

    schema = app.openapi()

    schema.setdefault("servers", [
        {
            "url": "http://127.0.0.1:8000",
            "description": "Local Pocket Lab FastAPI runtime"
        }
    ])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    title = schema.get("info", {}).get("title", "Unknown")
    version = schema.get("info", {}).get("version", "Unknown")
    path_count = len(schema.get("paths", {}))

    print(f"Exported OpenAPI: {OUT}")
    print(f"Title: {title}")
    print(f"Version: {version}")
    print(f"Paths: {path_count}")


if __name__ == "__main__":
    main()
