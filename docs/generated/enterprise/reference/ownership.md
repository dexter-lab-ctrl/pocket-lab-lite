---
title: "Ownership & Responsibility Map"
description: "Source/runtime/recovery/control/presentation/evidence ownership with architecture, threat and test cross-links."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Ownership & Responsibility Map

| Capability | Source | Runtime | Recovery | Control | Presentation | Evidence | Architecture | Threats | Tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Control API | FastAPI routers/services | pocket-api | core supervisor/operator | FastAPI | React/Vite PWA | API/runtime projections | Architecture → Control plane | control-api | tests/backend/test_lite_api.py, tests/parity/ |
| Messaging and command execution | NATS bus/domain commands | NATS/JetStream + worker | worker consumer supervision/core supervisor | FastAPI | FastAPI projection to UI | events/audit/command state | Architecture → Event and execution | messaging-execution | tests/backend/test_nats_required.py, tests/backend/test_lite_worker_recovery.py |
| Managed devices | fleet/device services | node agent | agent supervisor | FastAPI | Devices UI | heartbeats/fleet/recovery evidence | Architecture → Device runtime | managed-device | tests/backend/test_lite_api.py |
| Security | Security policy/services | worker + bounded Lynis/Trivy profiles | worker consumer recovery/supervisor | FastAPI | Security UI | sanitized Security projection | Architecture → Security boundaries | server-host, managed-device, application-container | tests/backend/test_lite_security.py, tests/backend/test_lite_api.py |
| Recovery | Recovery/backup services | worker/restic | Recovery workflow/operator | FastAPI | Recovery UI | backup/verify/preview/checkpoint receipts | Architecture → Durable state | durable-state | tests/backend/test_lite_recovery.py, tests/parity/test_backup_recovery_parity.py |
| Documentation Platform | canonical metadata/generators | none | developer/CI regeneration | deterministic generators | MkDocs | source + canonical/promoted evidence | Documentation Platform → Generation pipeline | external-release | tests/docs/ |
| Supply-chain automation | tool metadata + automation scripts | WSL2/CI only | developer/CI rerun from verified cache | explicit capture/promote tasks | generated Supply Chain/Release docs | sanitized canonical supply-chain contracts | Architecture → External release, Documentation Platform → Evidence model | external-release | tests/docs/test_enterprise_completion.py |
