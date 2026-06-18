#!/usr/bin/env python3
"""Check deployment evidence generated deployment docs freshness and MkDocs nav coverage."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATED_FILES = [
    Path("docs/platform/deployment-guide.md"),
    Path("docs/platform/platform-guide.md"),
    Path("docs/platform/generated/ansible-playbooks-reference.md"),
    Path("docs/platform/generated/ansible-roles-reference.md"),
    Path("docs/platform/generated/bootstrap-scripts-reference.md"),
    Path("docs/platform/generated/environment-reference.md"),
    Path("docs/architecture/runtime-blueprint.md"),
]
REQUIRED_NAV_TOKENS = [
    "platform/deployment-guide.md",
    "platform/platform-guide.md",
    "platform/generated/ansible-playbooks-reference.md",
    "platform/generated/ansible-roles-reference.md",
    "platform/generated/bootstrap-scripts-reference.md",
    "platform/generated/environment-reference.md",
    "architecture/runtime-blueprint.md",
]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main() -> int:
    errors: list[str] = []
    for path in GENERATED_FILES:
        full = ROOT / path
        if not full.exists():
            errors.append(f"missing generated doc: {path}")
        elif "GENERATED FILE" not in full.read_text(encoding="utf-8", errors="replace")[:200]:
            errors.append(f"generated marker missing from {path}")
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8", errors="replace") if (ROOT / "mkdocs.yml").exists() else ""
    for token in REQUIRED_NAV_TOKENS:
        if token not in mkdocs:
            errors.append(f"mkdocs.yml nav missing {token}")
    before = {str(p): (ROOT / p).read_text(encoding="utf-8") for p in GENERATED_FILES if (ROOT / p).exists()}
    result = run([sys.executable, "scripts/docs/generate_deployment_docs.py"])
    if result.returncode != 0:
        errors.append("deployment docs regeneration failed: " + result.stderr.strip())
    else:
        for path in GENERATED_FILES:
            full = ROOT / path
            if full.exists() and before.get(str(path)) is not None and before[str(path)] != full.read_text(encoding="utf-8"):
                errors.append(f"stale generated doc: {path}")
    if errors:
        print("Deployment docs check failed:", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 1
    print("Deployment docs check passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
