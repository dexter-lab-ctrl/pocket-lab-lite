---
title: "Backend-to-Frontend Parity"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Backend-to-Frontend Parity
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Pocket Lab Lite verifies projection parity at three independent boundaries so a failure can be attributed to persistence, API projection, frontend selection, or rendering. The framework never compares rendered UI directly with raw SQLite.

## Navigation

- [Architecture and Method](architecture.md)
- [Backup & Restore](backup-restore.md)
- [Domain catalog](domain-catalog.md)
- [Coverage and gaps](coverage-gaps.md)
- [Release readiness](release-readiness.md)

## Current release statement

Backup & Restore is the first complete source-and-test vertical slice. Live WSL2-to-Termux and live browser checks remain optional and **unvalidated** until explicitly run.
