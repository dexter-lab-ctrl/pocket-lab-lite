from __future__ import annotations

import importlib
import os
from fastapi.testclient import TestClient

os.environ.setdefault("POCKETLAB_API_TOKEN", "pocketlab-test-token")
os.environ.setdefault("POCKETLAB_ALLOW_LOCAL_WRITE", "1")
os.environ.setdefault("POCKETLAB_TEST_AUTH_BYPASS", "1")
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FASTAPI_RUNTIME = REPO_ROOT / "pocket-lab-final-structure" / "runtime"


def ensure_runtime_path() -> None:
    for path in (REPO_ROOT, FASTAPI_RUNTIME):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def load_fastapi_app():
    ensure_runtime_path()

    candidates = [
        "api_fastapi.main",
        "api_fastapi.app",
        "api_fastapi.server",
    ]

    last_error: Exception | None = None

    for module_name in candidates:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            last_error = exc
            continue

        for attr in ("app", "application"):
            app = getattr(module, attr, None)
            if app is not None:
                return app

        for factory in ("create_app", "build_app"):
            fn = getattr(module, factory, None)
            if callable(fn):
                return fn()

    raise ImportError(f"Could not load Pocket Lab FastAPI app. Last error: {last_error!r}")


def isolated_state_dir(tmp_path: Path | None = None) -> Path:
    """
    Return an isolated state directory and set Pocket Lab state env vars.

    Existing performance tests call isolated_state_dir(tmp_path) directly,
    so this helper intentionally returns Path instead of a context manager.
    """
    if tmp_path is None:
        state = Path(tempfile.mkdtemp(prefix="pocketlab-test-state-"))
    else:
        state = Path(tmp_path) / "state"

    state.mkdir(parents=True, exist_ok=True)
    os.environ["POCKETLAB_STATE_DIR"] = str(state)
    os.environ["POCKETLAB_DEV_STATE_DIR"] = str(state)
    return state


def client():
    token = os.environ.get("POCKETLAB_API_TOKEN", "pocketlab-test-token")
    return TestClient(
        load_fastapi_app(),
        headers={
            "Authorization": f"Bearer {token}",
            "X-Pocket-Lab-Token": token,
            "X-Pocket-Lab-Test": "1",
        },
    )
def load_fixture(name: str):
    """Load a JSON fixture from tests/fixtures."""
    import json

    fixture = REPO_ROOT / "tests" / "fixtures" / name
    if not fixture.exists():
        raise FileNotFoundError(f"Missing test fixture: {fixture}")
    return json.loads(fixture.read_text())
