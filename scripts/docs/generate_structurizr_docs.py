#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "architecture/structurizr/workspace.dsl"
OUT = ROOT / "docs/architecture/structurizr-architecture.md"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def generate_workspace() -> None:
    run(["python3", "scripts/docs/generate_structurizr_workspace.py"])


def write_markdown() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)

    OUT.write_text(
        """# Structurizr Architecture

!!! note "Generated architecture-as-code page"
    This page is generated from `architecture/structurizr/workspace.dsl`. Update `scripts/docs/generate_structurizr_workspace.py`, then run `task docs:architecture`.

## Source of Truth

| Item | Value |
|---|---|
| Structurizr workspace | `architecture/structurizr/workspace.dsl` |
| Architecture model | C4 model |
| Runtime architecture | FastAPI + NATS / JetStream + Worker + Event-Sourced Workflow Engine |
| Deployment targets | Android / Termux edge device, Ubuntu developer workstation |

## Views Defined

| View | Purpose |
|---|---|
| `system-context` | Shows Pocket Lab and external systems. |
| `container-view` | Shows major runtime containers. |
| `event-driven-runtime` | Shows FastAPI, NATS, worker, event journal, docs, and typed operation registry. |
| `domain-services` | Shows app catalog, GitOps, drift, fleet, vault, security, telemetry, release, and DR domains. |
| `security-review` | Shows Security / Policy Guardrails, Vault/OpenBao, OPA, typed operation validation, and audit evidence relationships. |
| `nats-command-event-boundaries` | Shows frontend/API/NATS/worker command and event boundaries. |
| `audit-and-dlq-paths` | Shows retry exhaustion, DLQ subjects, audit evidence, workflow state, and recovery paths. |
| `android-termux-deployment` | Shows Android/Termux deployment topology. |
| `developer-workstation-deployment` | Shows local dev stack topology. |
| `typed-operation-flow` | Dynamic view of UI → API → NATS → Worker → Events. |

## View Locally with Structurizr

Use Structurizr Local against the workspace directory. Structurizr Local loads `workspace.dsl` from its data directory and provides a browser UI for diagrams and documentation.

```bash
docker run --rm -it -p 8080:8080 \\
  --user "$(id -u):$(id -g)" \\
  -v "$PWD/architecture/structurizr:/usr/local/structurizr" \\
  structurizr/structurizr local
```

Then open:

```text
http://localhost:8080
```

## Export Options

The Structurizr CLI can export workspace views to static site or diagram formats.

Examples:

```bash
structurizr-cli export \\
  -workspace architecture/structurizr/workspace.dsl \\
  -format static \\
  -output docs/architecture/generated/structurizr
```

or:

```bash
structurizr-cli export \\
  -workspace architecture/structurizr/workspace.dsl \\
  -format mermaid \\
  -output docs/architecture/generated/structurizr
```

## Governance

- All major runtime components must be represented in the DSL.
- Every new major domain service must update the `container-view` and `domain-services` view.
- Every major runtime flow must have a dynamic view.
- Security, policy, secret-management, audit, retry, and DLQ changes must update the enterprise security-review views.
- Deployment topology changes must update deployment views.
- Architecture docs should stay aligned with OpenAPI, AsyncAPI, and Typed Operations tiers.

## Regenerate

```bash
task docs:architecture
task docs:build
```
""",
        encoding="utf-8",
    )

    print(f"Wrote {OUT}")


def main() -> None:
    generate_workspace()
    write_markdown()


if __name__ == "__main__":
    main()
