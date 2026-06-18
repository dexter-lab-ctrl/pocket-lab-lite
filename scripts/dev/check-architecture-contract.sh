#!/usr/bin/env bash
set -Eeuo pipefail

python3 - <<'PY'
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(".")

CONTRACT_PATHS = [
    Path("architecture/contract/architecture-contract.json"),
    Path("contracts/architecture/architecture-contract.json"),
    Path("contracts/architecture-contract.json"),
]

# Active implementation paths only.
# Contracts, docs, history, generated references, and tests may legitimately
# mention retired symbols as policy, audit, or negative-test evidence.
ACTIVE_SCAN_ROOTS = [
    Path("src"),
    Path("runbooks"),
    Path("architecture/structurizr"),
    Path("pocket-lab-final-structure/runtime"),
    Path("pocket-lab-final-structure/pocket-lab-iac-api-compatible"),
]

ACTIVE_SCRIPT_ALLOWLIST = [
    Path("scripts/dev/release-dry-run.sh"),
    Path("scripts/dev/check-backend.sh"),
    Path("scripts/dev/check-bootstrap.sh"),
    Path("scripts/dev/check-iac.sh"),
    Path("scripts/dev/check-supply-chain.sh"),
    Path("scripts/dev/test-nats-stack.sh"),
    Path("scripts/dev/check-faults.sh"),
    Path("scripts/dev/report-flakes.sh"),
    Path("scripts/dev/run-validation-gate.sh"),
]

EXCLUDED_PATH_PARTS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "site",
    "storybook-static",
    ".pocketlab-dev",
    "__pycache__",
    "migrations",
    "archive",
    "dev-migrations",
}

EXCLUDED_SUFFIXES = {
    ".bak",
    ".orig",
    ".rej",
    ".patch",
    ".zip",
    ".tar",
    ".gz",
    ".tgz",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".pyc",
}

TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".yaml",
    ".yml",
    ".md",
    ".mdx",
    ".sh",
    ".ps1",
    ".toml",
    ".ini",
    ".cfg",
    ".txt",
    ".html",
    ".css",
    ".scss",
    ".dsl",
    ".rego",
}


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def is_text_file(path: Path) -> bool:
    return not path.suffix or path.suffix in TEXT_SUFFIXES


def is_excluded(path: Path) -> bool:
    parts = set(path.parts)

    if parts & EXCLUDED_PATH_PARTS:
        return True

    if path.suffix in EXCLUDED_SUFFIXES:
        return True

    if not is_text_file(path):
        return True

    return False


def load_contract() -> dict:
    for path in CONTRACT_PATHS:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

    # Fallback is intentionally built from fragments so this scanner does not
    # become a finding against itself.
    return {
        "forbidden_symbols": [
            "_".join(["legacy", "intent"]),
            "_".join(["sync", "bash"]),
            "_".join(["tofu", "deploy"]),
            "submit" + "Legacy" + "Operation",
            "/" + "api" + "/" + "action" + "/" + "update",
            "POCKETLAB" + "_API" + "_RUNTIME",
            "pocket" + "_lab" + "_api" + "_server",
            "Base" + "HTTPRequestHandler",
            "HTTP" + "Server",
            "runtime" + "/" + "api" + "/",
        ]
    }


def iter_active_files() -> list[Path]:
    files: set[Path] = set()

    for root in ACTIVE_SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and not is_excluded(path):
                files.add(path)

    for path in ACTIVE_SCRIPT_ALLOWLIST:
        if path.exists() and path.is_file() and not is_excluded(path):
            files.add(path)

    return sorted(files)


def main() -> int:
    contract = load_contract()
    forbidden_symbols = contract.get("forbidden_symbols", [])

    if not isinstance(forbidden_symbols, list):
        raise SystemExit("architecture contract forbidden_symbols must be a list")

    findings: list[str] = []

    for path in iter_active_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for symbol in forbidden_symbols:
            if symbol and symbol in text:
                findings.append(f"{symbol} in {rel(path)}")

    if findings:
        for finding in findings:
            print(finding)
        raise SystemExit(1)

    print("Architecture contract forbidden-symbol scan passed")
    print(f"Active files scanned: {len(iter_active_files())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
