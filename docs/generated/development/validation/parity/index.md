---
title: "Backend-to-Frontend Parity"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Backend-to-Frontend Parity
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Pocket Lab Lite verifies projection parity at three independent boundaries so a failure can be attributed to persistence, API projection, frontend selection, or rendering. The framework never compares rendered UI directly with raw SQLite.

## Navigation

- [Architecture and Method](architecture.md)
- [Home](home.md)
- [Apps](apps.md)
- [Devices](devices.md)
- [Security](security.md)
- [Identity](identity.md)
- [Rules](rules.md)
- [Backup & Restore](backup-restore.md)
- [Runtime drift report](runtime-drift-report.md)
- [Accepted limitations](accepted-limitations.md)
- [Domain catalog](domain-catalog.md)
- [Coverage and gaps](coverage-gaps.md)
- [Release readiness](release-readiness.md)

## Current release statement

The canonical parity model now covers all seven Lite tabs. Repository contracts and deterministic mocked evidence remain distinct from explicitly promoted semantic runtime evidence. The currently tracked legacy runtime baseline is coverage-only; it must not be interpreted as field-level semantic verification.
