#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts/operations/pocketlab-typed-operations.json"
OUT = ROOT / "docs/runtime/typed-operations-catalog.md"


README_NOTE = """# generate_operations_docs.py package

Copy this package into the Pocket Lab repository root.

Expected files after unzip:

```text
scripts/docs/generate_operations_docs.py
```

Run:

```bash
chmod +x scripts/docs/generate_operations_docs.py
python3 -m py_compile scripts/docs/generate_operations_docs.py
task docs:operations
mkdocs build --strict
```
"""


def run(cmd: list[str]) -> None:
    """Run a command from the Pocket Lab repository root."""
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def generate_contract() -> None:
    """Generate the machine-readable typed operations contract."""
    run(["python3", "scripts/docs/generate_operations_contract.py"])


def generate_viewer() -> None:
    """Generate the interactive typed operations HTML viewer."""
    run(["python3", "scripts/docs/generate_operations_viewer.py"])


def load_contract() -> dict[str, Any]:
    """Load the generated typed operations contract."""
    if not CONTRACT.exists():
        raise SystemExit(
            f"Missing operations contract: {CONTRACT}. "
            "Run scripts/docs/generate_operations_contract.py first."
        )

    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def operation_table(operations: list[dict[str, Any]]) -> str:
    """Render the operation index table for MkDocs."""
    rows = [
        "| Operation | Professional Label | Simple Label | NATS Subject |",
        "|---|---|---|---|",
    ]

    for op in sorted(operations, key=lambda item: item["operation"]):
        rows.append(
            "| "
            f"`{op['operation']}` | "
            f"{op.get('professional_label', '')} | "
            f"{op.get('simple_label', '')} | "
            f"`{op.get('nats_subject', '')}` |"
        )

    return "\n".join(rows)


def screen_mapping(operations: list[dict[str, Any]]) -> str:
    """Render UI screen/tab to operation mapping."""
    mapping: dict[str, list[str]] = {}

    for op in operations:
        for screen in op.get("ui_entrypoints", []):
            mapping.setdefault(screen, []).append(op["operation"])

    rows = ["| Screen / Tab | Operations |", "|---|---|"]

    for screen in sorted(mapping):
        ops = ", ".join(f"`{operation}`" for operation in sorted(mapping[screen]))
        rows.append(f"| {screen} | {ops} |")

    return "\n".join(rows)


def api_mapping(operations: list[dict[str, Any]]) -> str:
    """Render API path to operation mapping."""
    mapping: dict[str, list[str]] = {}

    for op in operations:
        for path in op.get("api_entrypoints", []):
            mapping.setdefault(path, []).append(op["operation"])

    rows = ["| API Path | Operations |", "|---|---|"]

    for path in sorted(mapping):
        ops = ", ".join(f"`{operation}`" for operation in sorted(mapping[path]))
        rows.append(f"| `{path}` | {ops} |")

    return "\n".join(rows)


def nats_mapping(operations: list[dict[str, Any]]) -> str:
    """Render NATS subject to operation mapping."""
    mapping: dict[str, list[str]] = {}

    for op in operations:
        subject = op.get("nats_subject", "")
        if subject:
            mapping.setdefault(subject, []).append(op["operation"])

    rows = ["| NATS Subject | Operations |", "|---|---|"]

    for subject in sorted(mapping):
        ops = ", ".join(f"`{operation}`" for operation in sorted(mapping[subject]))
        rows.append(f"| `{subject}` | {ops} |")

    return "\n".join(rows)


def safety_table(operations: list[dict[str, Any]]) -> str:
    """Render safety behavior for each operation."""
    rows = ["| Operation | Safety Behavior |", "|---|---|"]

    for op in sorted(operations, key=lambda item: item["operation"]):
        safety = str(op.get("safety", "")).replace("\n", " ")
        rows.append(f"| `{op['operation']}` | {safety} |")

    return "\n".join(rows)


def forbidden_patterns(contract: dict[str, Any]) -> str:
    """Render retired / forbidden architecture patterns."""
    patterns = contract.get("forbidden_patterns", [])
    if not patterns:
        return "_No forbidden patterns documented._"

    return "\n".join(f"- `{pattern}`" for pattern in patterns)


def write_markdown() -> None:
    """Write the generated MkDocs typed operations catalog page."""
    contract = load_contract()
    operations = contract.get("operations", [])
    architecture = contract.get(
        "architecture",
        "Pocket Lab FastAPI + NATS / JetStream + Worker architecture",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)

    content = f"""# Typed Operations Catalog

!!! note "Generated page"
    This page is generated from the Pocket Lab typed operations contract. Do not manually edit operation lists here. Update `scripts/docs/generate_operations_contract.py`, then run `task docs:operations`.

## Source of Truth

| Item | Value |
|---|---|
| Operations contract | `contracts/operations/pocketlab-typed-operations.json` |
| Interactive viewer | [Open interactive operations catalog](generated/typed-operations-catalog/index.html) |
| Operation count | `{len(operations)}` |
| Architecture | {architecture} |

## Runtime Model

Pocket Lab uses typed operations as the safe boundary between the UI, FastAPI, NATS / JetStream, workers, runtime tools, event sourcing, and audit trails.

```mermaid
flowchart LR
  UI[UI Button / Tab Action] --> API[FastAPI Route]
  API --> Validate[Validate Typed Operation]
  Validate --> NATS[NATS / JetStream Command]
  NATS --> Worker[Worker Handler]
  Worker --> Events[Operation Events]
  Worker --> Audit[Audit / DLQ]
  Events --> UI
```

## Operation Index

{operation_table(operations)}

## Screen-to-Operation Mapping

{screen_mapping(operations)}

## API-to-Operation Mapping

{api_mapping(operations)}

## NATS Subject Mapping

{nats_mapping(operations)}

## Safety Behavior

{safety_table(operations)}

## Forbidden / Retired Patterns

These patterns must not be reintroduced:

{forbidden_patterns(contract)}

## Operation Governance Rules

- Every UI write action must map to a typed operation.
- Every typed operation must have a documented UI entry point.
- Every typed operation must have an API entry point.
- Every durable operation must map to a NATS command subject.
- Every operation must document success and failure events.
- Sensitive operations must document redaction and fail-closed behavior.
- Retired compatibility operations must not reappear.
- `task docs:operations` must pass before operation docs are considered fresh.

## Regenerate

```bash
task docs:operations
task docs:build
```
"""

    OUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUT}")


def main() -> None:
    generate_contract()
    generate_viewer()
    write_markdown()


if __name__ == "__main__":
    main()
