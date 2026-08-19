---
title: "Sanitization and Data Exposure Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 8a90a66c46a250cebfd7e62993f9c541fa1c293fd7e4dd880cc399353b42bff4
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
