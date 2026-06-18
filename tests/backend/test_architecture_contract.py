from pathlib import Path
import json


def test_required_architecture_paths_exist():
    contract = json.loads(Path("contracts/pocketlab_operations.json").read_text())
    assert not [path for path in contract["required_paths"] if not Path(path).exists()]


def test_forbidden_legacy_symbols_absent_from_active_code():
    contract = json.loads(Path("contracts/pocketlab_operations.json").read_text())
    roots = [
        Path("src"),
        Path("pocket-lab-final-structure/runtime"),
        Path(
            "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched"
        ),
        Path("pocket-lab-final-structure/pocket-lab-iac-api-compatible"),
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
                ".png",
                ".jpg",
                ".jpeg",
                ".gif",
                ".webp",
                ".ico",
                ".zip",
                ".gz",
                ".tar",
            }:
                continue
            text = path.read_text(errors="ignore")
            for symbol in contract["forbidden_symbols"]:
                if symbol in text:
                    violations.append((str(path), symbol))
    assert not violations
