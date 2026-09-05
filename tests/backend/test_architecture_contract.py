from pathlib import Path
import json


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts" / "pocketlab_operations.json"
ROUTER = ROOT / "pocket-lab-final-structure" / "runtime" / "api_fastapi" / "routers" / "lite.py"


def _contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_required_architecture_paths_exist_and_legacy_path_is_retired():
    contract = _contract()
    assert contract["contract"] == "pocket-lab-lite-operations"
    assert not [path for path in contract["required_paths"] if not (ROOT / path).exists()]
    assert all(not (ROOT / path).exists() for path in contract.get("forbidden_paths", []))


def test_lite_control_api_contract_points_at_current_fastapi_routes():
    contract = _contract()
    router = ROUTER.read_text(encoding="utf-8")
    assert contract["boundaries"]["control_api"] == "FastAPI /api/lite/*"
    for endpoint in contract["required_endpoints"]:
        assert endpoint.startswith("/api/lite/")
        route = endpoint.removeprefix("/api/lite")
        assert f'"{route}"' in router
    assert contract["boundaries"]["frontend_direct_nats"] is False
    assert contract["boundaries"]["frontend_shell_execution"] is False
    assert contract["boundaries"]["frontend_backend_secrets"] is False


def test_forbidden_legacy_symbols_absent_from_active_code():
    contract = _contract()
    roots = [
        ROOT / "src",
        ROOT / "pocket-lab-final-structure" / "runtime",
        ROOT / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched",
    ]
    ignored = {".git", "node_modules", "dist", ".venv", ".pocketlab-dev", "__pycache__"}
    violations = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_dir() or any(part in ignored for part in path.parts):
                continue
            if path.suffix.lower() in {
                ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".zip", ".gz", ".tar",
            }:
                continue
            text = path.read_text(errors="ignore")
            for symbol in contract["forbidden_symbols"]:
                if symbol in text:
                    violations.append((str(path.relative_to(ROOT)), symbol))
    assert not violations
