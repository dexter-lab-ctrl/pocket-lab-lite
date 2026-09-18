# 4. Toolchain installation and receipts

The tool manager is a server-owned contract, not a general package runner.
The caller selects only `install`, `check`, or a registered suite. It resolves
fixed binaries, fixed arguments, fixed targets, parsers, sanitizers, timeouts,
resource classes, retry policy, and suite membership from
`security/assurance/tools.yaml`.

## Commands

**[DEV PC]** Install or promote missing fixed tools outside Git:

```bash
task lite:security:assurance:tools:install
```

Check every registered entry:

```bash
task lite:security:assurance:tools:check
```

Run the fixed DEV-PC lane for a suite:

```bash
task lite:security:assurance:tools:run SUITE=standard
task lite:security:assurance:tools:run SUITE=deep
```

The result records a qualification ID, registry digest, receipt/tool
versions, execution lane, target identity, bounded summaries, findings, and
sanitized evidence paths. Temporary downloads and extraction directories are
not repository artifacts. The manager verifies fixed checksums where the
recipe supports them and refuses unregistered downloads or arbitrary caller
arguments.

## Installation model

The managed root is outside Git under the operator's Pocket Lab tool directory
(the current implementation uses the `~/.pocketlab-lite/tools/security-assurance`
model). Existing repository virtual environments and approved system paths are
considered only through the fixed discovery list. A qualified binary path is
preferred over ambient `PATH` lookup.

Do not commit third-party binaries, receipts containing secrets, scanner
databases, archives, or raw tool output. Retain normal cached Trivy/SBOM data
only where the existing Security lifecycle intentionally owns it.

## Lanes

| Lane | Tools | Target |
| --- | --- | --- |
| `server_phone_worker` | Pocket Lab Security, Trivy, Lynis, OPA | existing worker-owned local runtime path |
| `dev_pc_static` | Bandit, Gitleaks, pip-audit, npm audit, Semgrep, OSV-Scanner, Syft, Grype, Cosign | checked-in source, lockfiles, managed SBOM, registered release artifact |
| `dev_pc_live_runtime` | Schemathesis, testssl.sh, Nuclei, nmap, OWASP ZAP, Playwright, mitmdump, Hurl, k6, websocat, Katana, httpx, tlsx, tshark, ffuf, NATS CLI, plus the repository-owned runtime adapters | fixed approved local tunnel to Pocket Lab endpoints |

The lane is part of the evidence identity. DEV-PC live-runtime results are
not phone-native execution; they are DEV-PC tools testing the actual approved
Server Phone runtime. Phone-native tools are still worker-owned and preserve
the existing Quick/Full Security cache/SBOM/resource behavior.

## Installer ownership model

Every registered tool has one deterministic provisioning class. The installer
does not accept package names, URLs, versions, targets, argv, or NATS subjects
from the caller.

- `pocketlab-runtime-360` and `playwright-runtime` are repository-owned
  adapters. They are checked in place and are never promoted as third-party
  scanner binaries.
- `playwright` is a repository dependency. Its qualified identity is the
  `package-lock.json` Playwright 1.60.0 dependency set. The assurance installer
  does not run `playwright install` and does not download Chromium/browser
  payloads.
- `mitmdump` is installed into a dedicated managed Python virtual environment
  from the exact mitmproxy 12.2.3 wheel URL with a fixed wheel SHA-256. The
  repository virtual environment is not modified.
- Hurl 8.0.1, k6 2.2.0, websocat 1.14.1, Katana 1.7.0, httpx 1.12.0,
  tlsx 1.4.0, ffuf 2.3.0, and NATS CLI 0.5.0 use fixed official release
  assets and fixed SHA-256 values. Archives are path-checked and only the
  unique expected executable is extracted.
- `tshark` remains a host-owned Wireshark dependency. A qualified existing
  host binary is used when present. If it is absent, the tool is explicitly
  `NOT_APPLICABLE`; the installer does not use privileged package operations,
  alter capture capabilities, or mutate the global Wireshark installation.
- Existing pre-qualified DEV-PC tools retain their approved promotion path.
  Fixed APT recipes continue to use unprivileged `apt-get download` plus
  `dpkg-deb --extract`; they do not install system packages.

Healthy managed tools are idempotent: a matching version, binary checksum, and
source-owned provenance receipt yields `already_qualified`. Missing or invalid
fixed-recipe provenance is repaired from the fixed recipe. Downloads and
managed tool state remain outside Git under the managed tool root.

## Tool receipt contract

Each active entry defines:

- pinned or runtime-reported version and installation source;
- fixed command ID, target, argv/rules/template policy, parser, sanitizer;
- timeout, maximum output, resource class, and exclusive-heavy scheduling;
- retry/resume/checkpoint metadata and maximum attempts;
- checksum/signature policy;
- suite membership and required harness capability.

See the [tool matrix](../reference/tool-matrix.md) for the current 31-entry
registry. `Cosign` is a valid `NOT_APPLICABLE` outcome when no signed artifact
is registered; that is different from an unavailable Cosign binary.
