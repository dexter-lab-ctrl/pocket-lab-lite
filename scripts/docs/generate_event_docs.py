#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ASYNCAPI = ROOT / "contracts/asyncapi/pocketlab-nats-jetstream.yaml"
OUT = ROOT / "docs/runtime/nats-jetstream-event-contract.md"
VIEWER = ROOT / "docs/runtime/generated/nats-jetstream-asyncapi/index.html"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    env = os.environ.copy()
    env.setdefault("SUPPRESS_NO_CONFIG_WARNING", "true")
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


def generate_contract() -> None:
    run(["python3", "scripts/docs/generate_asyncapi_contract.py"])


def validate_contract() -> None:
    run(["npx", "asyncapi", "validate", str(ASYNCAPI)])


def build_interactive_viewer() -> None:
    run(["python3", "scripts/docs/generate_asyncapi_viewer.py"])


def load_contract() -> dict[str, Any]:
    if not ASYNCAPI.exists():
        raise SystemExit(f"Missing AsyncAPI contract: {ASYNCAPI}")
    return json.loads(ASYNCAPI.read_text(encoding="utf-8"))


def subject_kind(subject: str) -> str:
    if subject.startswith("pocketlab.commands."):
        return "Command"
    if subject.startswith("pocketlab.audit."):
        return "Audit"
    if subject.startswith("pocketlab.dlq."):
        return "DLQ"
    if subject.startswith("pocketlab.events."):
        return "Event"
    return "Subject"


def subjects_by_prefix(contract: dict[str, Any], prefix: str) -> list[str]:
    channels = contract.get("channels", {})
    if not isinstance(channels, dict):
        return []
    return sorted(subject for subject in channels.keys() if subject.startswith(prefix))


def table(subjects: list[str]) -> str:
    if not subjects:
        return "_None documented._"

    rows = ["| Subject | Type |", "|---|---|"]
    for subject in subjects:
        rows.append(f"| `{subject}` | {subject_kind(subject)} |")
    return "\n".join(rows)


def stream_table(contract: dict[str, Any]) -> str:
    streams = contract.get("x-pocketlab-streams", {})
    if not isinstance(streams, dict) or not streams:
        return "_No stream metadata documented._"

    rows = ["| Stream | Subjects |", "|---|---|"]
    for stream, subjects in streams.items():
        if isinstance(subjects, list):
            subject_text = ", ".join(f"`{s}`" for s in subjects)
        else:
            subject_text = f"`{subjects}`"
        rows.append(f"| `{stream}` | {subject_text} |")
    return "\n".join(rows)


def retry_table(contract: dict[str, Any]) -> str:
    retry = contract.get("x-pocketlab-retry-policy", {})
    if not isinstance(retry, dict) or not retry:
        return "_No retry metadata documented._"

    rows = ["| Setting | Value |", "|---|---|"]
    for key, value in retry.items():
        rows.append(f"| `{key}` | `{value}` |")
    return "\n".join(rows)


def redaction_table(contract: dict[str, Any]) -> str:
    redaction = contract.get("x-pocketlab-redaction", {})
    keys = redaction.get("sensitive_keys", []) if isinstance(redaction, dict) else []
    if not keys:
        return "_No redaction keys documented._"

    rows = ["| Sensitive Key Pattern |", "|---|"]
    for key in keys:
        rows.append(f"| `{key}` |")
    return "\n".join(rows)


def write_markdown() -> None:
    contract = load_contract()

    commands = subjects_by_prefix(contract, "pocketlab.commands.")
    events = subjects_by_prefix(contract, "pocketlab.events.")
    audit = subjects_by_prefix(contract, "pocketlab.audit.")
    dlq = subjects_by_prefix(contract, "pocketlab.dlq.")
    version = contract.get("info", {}).get("version", "unknown") if isinstance(contract.get("info", {}), dict) else "unknown"

    OUT.parent.mkdir(parents=True, exist_ok=True)

    markdown = f'''# NATS / JetStream Event Contract

!!! note "Generated page"
    This page is generated from the AsyncAPI contract. Do not manually edit subject lists here. Update `scripts/docs/generate_asyncapi_contract.py`, then run `task docs:events`.

## Source of Truth

| Item | Value |
|---|---|
| AsyncAPI contract | `contracts/asyncapi/pocketlab-nats-jetstream.yaml` |
| Interactive AsyncAPI viewer | [Open interactive AsyncAPI viewer](generated/nats-jetstream-asyncapi/index.html) |
| Protocol | `nats` |
| Runtime | NATS / JetStream |
| Version | `{version}` |

## Runtime Model

Pocket Lab uses NATS and JetStream as its durable command and event backbone.

```mermaid
flowchart LR
  API[FastAPI] --> Commands[POCKETLAB_COMMANDS]
  Commands --> Worker[Worker]
  Worker --> Events[POCKETLAB_EVENTS]
  Worker --> Audit[POCKETLAB_AUDIT]
  Worker --> DLQ[POCKETLAB_DLQ]
  Events --> UI[UI Event Stream]
```

## Command Subjects

{table(commands)}

## Event Subjects

{table(events)}

## Audit Subjects

{table(audit)}

## Dead Letter Subjects

{table(dlq)}

## JetStream Streams

{stream_table(contract)}

## Retry and DLQ Policy

{retry_table(contract)}

## Redaction Policy

{redaction_table(contract)}

## Payload Envelopes

The AsyncAPI contract defines these common payload envelopes:

| Schema | Purpose |
|---|---|
| `CommandEnvelope` | Durable command submitted by FastAPI and consumed by workers. |
| `EventEnvelope` | Runtime event emitted for UI updates, recovery, auditability, and observability. |
| `DeadLetterEnvelope` | Failed command record after retry exhaustion. |

## Governance Rules

- Every durable write operation must publish a typed command.
- Every worker action must emit operation lifecycle events.
- Sensitive values must be redacted before events, audit records, logs, and DLQ payloads.
- Fleet commands must remain scoped to the intended agent/node.
- Any new command, event, audit, telemetry, or DLQ subject must update the AsyncAPI generator.
- `task docs:events` must pass before event-contract documentation is considered fresh.

## Regenerate

```bash
task docs:events
task docs:build
```
'''

    OUT.write_text(markdown, encoding="utf-8")
    print(f"Wrote {OUT}")


def main() -> None:
    generate_contract()
    validate_contract()
    build_interactive_viewer()
    write_markdown()


if __name__ == "__main__":
    main()
