---
title: "Sanitization and Data Exposure Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Sanitization and Data Exposure Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Maximum evidence size: **262144 bytes**.

## Rejected classes

- credentials
- bearer tokens
- passwords
- private keys
- certificates
- IPv4
- IPv6
- Tailnet names
- hostnames
- usernames
- Android private paths
- WSL user paths
- SSH key paths
- credential URLs
- media paths
- environment dumps
- raw logs
- raw SQLite rows
- raw manifests
- full PM2 environments
- NATS credentials

All generated artifacts are allowlisted and scanned by the existing repository redaction checker plus parity-specific checks.
