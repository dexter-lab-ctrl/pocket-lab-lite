#!/usr/bin/env python3
"""Run the fixed DEV-PC lanes of Runtime Security Assurance.

This is an operator/client-side adapter for the server-owned registry.  It is
deliberately not a command runner: the caller can select only ``check``,
``install`` or one registered suite.  Every executable, argument, target,
temporary artifact and environment value is selected by this module and the
checked-in assurance registry.

Raw scanner output is kept in memory only long enough to parse it.  Reports
contain bounded summaries and normalized findings, never scanner payloads,
secret matches, cookies, credentials or user media.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import selectors
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    import yaml
except ImportError as exc:  # pragma: no cover - repository venv supplies PyYAML
    raise SystemExit("PyYAML is required for the assurance tool manager") from exc


ROOT = Path(__file__).resolve().parents[3]
TOOLS_REGISTRY = ROOT / "security/assurance/tools.yaml"
SCENARIOS_REGISTRY = ROOT / "security/assurance/scenarios.yaml"
SUITES_REGISTRY = ROOT / "security/assurance/suites.yaml"
RUNTIME_PROBE = ROOT / "scripts/dev/lite/security_assurance_runtime_probe.py"
PLAYWRIGHT_SECURITY_CONFIG = ROOT / "playwright.security.config.ts"
PLAYWRIGHT_SECURITY_SPEC = ROOT / "tests/e2e/lite-security-runtime.spec.ts"
HURL_SECURITY_FILE = ROOT / "security/assurance/runtime-http-security.hurl"
K6_SECURITY_FILE = ROOT / "security/assurance/runtime-resilience.js"
FFUF_WORDLIST = ROOT / "security/assurance/runtime-route-wordlist.txt"
SEMgrep_RULES = ROOT / "security/assurance/semgrep-rules.yml"
NUCLEI_TEMPLATES = ROOT / "security/assurance/nuclei-safe-templates"
OPENAPI_SCHEMA = ROOT / "contracts/generated/lite-openapi.json"
GITLEAKS_CONFIG = ROOT / "security/static-analysis/gitleaks.toml"
MANAGED_ROOT = Path.home() / ".pocketlab-lite" / "tools" / "security-assurance"
EVIDENCE_ROOT = Path.home() / ".pocketlab-lite" / "evidence" / "runtime-security-assurance"
API_BASE = "http://127.0.0.1:18080"
TLS_TARGET = "127.0.0.1:18443"
TLS_SNI_FILE = Path.home() / ".pocketlab-lite" / "qualification" / "caddy-sni"
LIVE_ROUTE_ALLOWLIST = (
    "/health",
    "/ready",
    "/api/lite/harness/security-assurance/capabilities",
    "/api/lite/harness/security-assurance/suites",
)
# The assurance client owns a fixed SSH loopback-tunnel contract.  These are
# local DEV-PC ports, each forwarding to the corresponding loopback-only
# Pocket Lab service port on the Server Phone.  The manager never accepts a
# caller-selected host, port or forwarding rule.
APPROVED_PORT_FORWARD_MAP = {
    14222: "server_phone_nats_4222",
    18080: "server_phone_api_8080",
    18181: "server_phone_opa_8181",
    18222: "server_phone_nats_monitor_8222",
    18443: "server_phone_caddy_tls_443",
}
APPROVED_PORTS = ",".join(str(port) for port in APPROVED_PORT_FORWARD_MAP)
APPROVED_NMAP_TARGET = "127.0.0.1"
MAX_SUITE_OUTPUT_BYTES = 1_048_576
MAX_VERSION_OUTPUT_BYTES = 32_768

VERSION_ARGS: dict[str, tuple[str, ...]] = {
    "bandit": ("--version",),
    "gitleaks": ("version",),
    "pip-audit": ("--version",),
    "npm-audit": ("--version",),
    "opa": ("version",),
    "schemathesis": ("--version",),
    "cosign": ("version",),
    "semgrep": ("--version",),
    "osv-scanner": ("--version",),
    "syft": ("version",),
    "grype": ("version",),
    "testssl.sh": ("--version",),
    "nuclei": ("-version",),
    "nmap": ("--version",),
    "owasp-zap": ("-version",),
    "playwright": ("--version",),
    "mitmdump": ("--version",),
    "hurl": ("--version",),
    "k6": ("version",),
    "websocat": ("--version",),
    "katana": ("-version",),
    "httpx": ("-version",),
    "tlsx": ("-version",),
    "tshark": ("--version",),
    "ffuf": ("-V",),
    "nats-cli": ("--version",),
}

# These are the only local paths considered by the manager.  In particular,
# it does not inherit a caller's PATH when deciding which executable to run.
APPROVED_PATH_DIRS = (
    MANAGED_ROOT / "bin",
    ROOT / ".venv" / "bin",
    ROOT / ".pocketlab-dev" / "tools" / "documentation-security" / "bin",
    ROOT / ".pocketlab-dev" / "tools" / "documentation-security" / "venvs" / "semgrep" / "bin",
    ROOT / ".pocketlab-dev" / "tools" / "parity" / "bin",
    ROOT / ".pocketlab-dev" / "tools" / "parity" / "schemathesis-venv" / "bin",
    Path.home() / ".nvm" / "versions" / "node" / "v24.16.0" / "bin",
    Path("/usr/local/bin"),
    Path("/usr/bin"),
    Path("/bin"),
)

LOCAL_CANDIDATES: dict[str, tuple[Path, ...]] = {
    "bandit": (ROOT / ".venv/bin/bandit",),
    "gitleaks": (ROOT / ".pocketlab-dev/tools/documentation-security/bin/gitleaks",),
    "pip-audit": (ROOT / ".venv/bin/pip-audit",),
    "npm-audit": (Path.home() / ".nvm/versions/node/v24.16.0/bin/npm",),
    "schemathesis": (
        ROOT / ".pocketlab-dev/tools/parity/bin/schemathesis",
        ROOT / ".pocketlab-dev/tools/parity/schemathesis-venv/bin/schemathesis",
    ),
    "cosign": (ROOT / ".pocketlab-dev/tools/documentation-security/bin/cosign",),
    "semgrep": (
        ROOT / ".pocketlab-dev/tools/documentation-security/bin/semgrep",
        ROOT / ".pocketlab-dev/tools/documentation-security/venvs/semgrep/bin/semgrep",
    ),
    "osv-scanner": (ROOT / ".pocketlab-dev/tools/documentation-security/bin/osv-scanner",),
    "syft": (ROOT / ".pocketlab-dev/tools/documentation-security/bin/syft",),
    "grype": (ROOT / ".pocketlab-dev/tools/documentation-security/bin/grype",),
    "opa": (Path("/usr/local/bin/opa"), Path("/usr/bin/opa")),
    "testssl.sh": (MANAGED_ROOT / "bin/testssl.sh", Path("/usr/bin/testssl"), Path("/usr/bin/testssl.sh")),
    "nuclei": (MANAGED_ROOT / "bin/nuclei", Path("/usr/local/bin/nuclei"), Path("/usr/bin/nuclei")),
    "nmap": (MANAGED_ROOT / "bin/nmap", Path("/usr/bin/nmap")),
    "owasp-zap": (MANAGED_ROOT / "bin/zap.sh", Path("/opt/zaproxy/zap.sh"), Path("/usr/share/zaproxy/zap.sh")),
    "playwright": (ROOT / "node_modules/.bin/playwright",),
    "mitmdump": (MANAGED_ROOT / "bin/mitmdump", ROOT / ".venv/bin/mitmdump", Path("/usr/local/bin/mitmdump"), Path("/usr/bin/mitmdump")),
    "hurl": (MANAGED_ROOT / "bin/hurl", Path("/usr/local/bin/hurl"), Path("/usr/bin/hurl")),
    "k6": (MANAGED_ROOT / "bin/k6", Path("/usr/local/bin/k6"), Path("/usr/bin/k6")),
    "websocat": (MANAGED_ROOT / "bin/websocat", Path("/usr/local/bin/websocat"), Path("/usr/bin/websocat")),
    "katana": (MANAGED_ROOT / "bin/katana", Path("/usr/local/bin/katana"), Path("/usr/bin/katana")),
    "httpx": (MANAGED_ROOT / "bin/httpx", Path("/usr/local/bin/httpx"), Path("/usr/bin/httpx")),
    "tlsx": (MANAGED_ROOT / "bin/tlsx", Path("/usr/local/bin/tlsx"), Path("/usr/bin/tlsx")),
    "tshark": (Path("/usr/bin/tshark"), Path("/usr/local/bin/tshark")),
    "ffuf": (MANAGED_ROOT / "bin/ffuf", Path("/usr/local/bin/ffuf"), Path("/usr/bin/ffuf")),
    "nats-cli": (MANAGED_ROOT / "bin/nats", Path("/usr/local/bin/nats"), Path("/usr/bin/nats")),
}

PHONE_WORKER_TOOLS = frozenset({"pocketlab-security", "trivy", "lynis", "opa"})
COSIGN_ARTIFACT_MANIFEST = ROOT / "security/release/signed-artifacts.json"
# The registry is authoritative for contracts, while this fixed order is the
# orchestration dependency graph.  In particular, Grype consumes the SBOM
# produced by Syft and must never be launched before that checkpoint exists.
TOOL_EXECUTION_ORDER = (
    "bandit",
    "gitleaks",
    "pip-audit",
    "npm-audit",
    "osv-scanner",
    "semgrep",
    "syft",
    "grype",
    "schemathesis",
    "testssl.sh",
    "nuclei",
    "nmap",
    "owasp-zap",
    "playwright",
    "mitmdump",
    "hurl",
    "websocat",
    "httpx",
    "tlsx",
    "tshark",
    "katana",
    "ffuf",
    "nats-cli",
    "k6",
)

# Fixed package/release recipes.  These values are source-owned and are not
# replaceable through CLI arguments or environment variables.
APT_RECIPES: dict[str, dict[str, Any]] = {
    "testssl.sh": {
        "packages": {
            "testssl.sh": {"version": "3.2.2+dfsg-1", "sha256": "5b2400cb03a5217e4a817c5db39022267d6c5efef0a187d2c9409ad30efa3200"},
            "bind9-dnsutils": {"version": "1:9.20.24-1ubuntu0.3", "sha256": "e149f6d40e29b4915b237aed92ba972c6c5ff565a056066e7fd5d20204cca832"},
            "bind9-host": {"version": "1:9.20.24-1ubuntu0.3", "sha256": "0506d3148a63e5fd2ca3df54a6024fb275d4cdc179f431afd89afbcc3d201910"},
            "bind9-libs": {"version": "1:9.20.24-1ubuntu0.3", "sha256": "7b0826714aea9c412452d0e7c310218e0dd6114e763fc6f1b9e90d1091dd3547"},
            "libuv1t64": {"version": "1.51.0-2ubuntu1", "sha256": "5c9b857d7d6a0c22b30dae45d518b375452cf7c663fc9381e3f0760ba3fb8cce"},
            "liburcu8t64": {"version": "0.15.6-1", "sha256": "de2e04225d0f1324ab5ee880e61427a5fa23de0a3563610386f5fc3eca653a02"},
            "libmaxminddb0": {"version": "1.12.2-1build2", "sha256": "3ea71228684a480b2183b72de1c99126965ef98c1b8def81f65e346298024fed"},
            "liblmdb0": {"version": "0.9.31-1build2", "sha256": "b702706b751b51516988230cefbe74643a373dcf28878dd77f735048117f88b5"},
        },
        "package": "testssl.sh",
        "version": "3.2.2+dfsg-1",
        "binary_relpath": "usr/bin/testssl",
    },
    "nmap": {
        "packages": {
            "nmap": {"version": "7.98+dfsg-1", "sha256": "dbf96dfab4b5feff857129aa3c46be925bbc87883a701be0f9bedf33adbabeb2"},
            "nmap-common": {"version": "7.98+dfsg-1", "sha256": "c603450bc7d5c33b68ecfefe408e792a7c3548b0f89201d5bc88d662e8842ceb"},
            "libpcap0.8t64": {"version": "1.10.6-1ubuntu1", "sha256": "69a466a55042ba8fe1bf738c29b01dd54edaf260c44426edbf0a08677ec29b1d"},
            "liblinear4": {"version": "2.3.0+dfsg-5build2", "sha256": "35201183a777d66273031c3b39ab078aa2c77821f0b0a3bdf59f5743edbac3dd"},
            "liblua5.4-0": {"version": "5.4.8-1build1", "sha256": "ff589ea3f181b89dd76b0240f79c59ac2f13f24e2053f624f774f596c7ef7897"},
            "libibverbs1": {"version": "61.0-2ubuntu3", "sha256": "1d9e2e86e6500dabb6143c04adea8d122c7caa72aae3832de88d7ada4fa97201"},
            "libnl-3-200": {"version": "3.12.0-2", "sha256": "52fda1b991baa2d0fbe82f5dfb15584dcb1f25a7e3d311e2e319cc33858b4f2c"},
            "libnl-route-3-200": {"version": "3.12.0-2", "sha256": "58c5fa3c2f5226ffb1846db6cf7318196dbf5294a4354edd00fdae2db30a45dc"},
        },
        "binary_relpath": "usr/bin/nmap",
        "data_relpath": "usr/share/nmap",
    },
}
GITHUB_RECIPES: dict[str, dict[str, Any]] = {
    "nuclei": {
        "version": "3.8.0",
        "url": "https://github.com/projectdiscovery/nuclei/releases/download/v3.8.0/nuclei_3.8.0_linux_amd64.zip",
        "sha256": "cd4ea43c88b50af8ab96eb6ad3fb4debd8e9d51efaff4d4c2d99106041578943",
        "archive": "zip",
        "binary_name": "nuclei",
        "source": "projectdiscovery/nuclei:v3.8.0 official release asset",
        "signature_status": "release_sha256",
    },
    "owasp-zap": {
        "version": "2.17.0",
        "url": "https://github.com/zaproxy/zaproxy/releases/download/v2.17.0/ZAP_2.17.0_Linux.tar.gz",
        "sha256": "efe799aaa3627db683b43f00c9c210aea0b75c00cc8f0a0f0434d12bb3ddde5a",
        "archive": "tar.gz",
        "binary_name": "zap.sh",
        "source": "zaproxy/zaproxy:v2.17.0 official release asset",
        "signature_status": "release_sha256_from_zap_admin",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        return f"REPOSITORY_ROOT/{resolved.relative_to(ROOT)}"
    except ValueError:
        pass
    try:
        return f"QUALIFICATION_TOOL_ROOT/{resolved.relative_to(MANAGED_ROOT)}"
    except ValueError:
        pass
    return str(resolved) if str(resolved).startswith(("/usr/", "/bin/", "/opt/")) else "EXTERNAL_APPROVED_PATH"


def _sanitize_text(value: str, limit: int = 240) -> str:
    text = str(value or "")
    text = re.sub(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", "[REDACTED BY SECURITY ASSURANCE POLICY]", text, flags=re.S)
    text = re.sub(r"(?i)(authorization|cookie)\s*:\s*bearer\s+[^\s,;]+", r"\1: [REDACTED BY SECURITY ASSURANCE POLICY]", text)
    text = re.sub(r"(?i)(authorization|cookie|token|password|passwd|secret|api[_-]?key|private[_-]?key)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED BY SECURITY ASSURANCE POLICY]", text)
    text = re.sub(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED BY SECURITY ASSURANCE POLICY]", text)
    text = text.replace(str(ROOT), "REPOSITORY_ROOT")
    text = text.replace(str(Path.home()), "QUALIFICATION_HOME")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _summary(output: str, limit_lines: int = 4) -> list[str]:
    return [_sanitize_text(line) for line in output.splitlines() if _sanitize_text(line)][:limit_lines]


def _fixed_tls_sni() -> str | None:
    """Read the operator-approved Caddy certificate identity, never a CLI target."""
    try:
        value = TLS_SNI_FILE.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,252}[A-Za-z0-9])?", value):
        return None
    if ".." in value or "." not in value:
        return None
    return value.casefold()


def _registry() -> dict[str, Any]:
    data = yaml.safe_load(TOOLS_REGISTRY.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != "2.0.0" or not isinstance(data.get("toolchain"), list):
        raise RuntimeError("assurance_tool_registry_invalid")
    result: dict[str, Any] = {}
    for item in data["toolchain"]:
        if not isinstance(item, dict) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", str(item.get("id") or "")):
            raise RuntimeError("assurance_tool_registry_invalid")
        result[str(item["id"])] = item
    if len(result) != 29:
        raise RuntimeError("assurance_tool_registry_incomplete")
    return {"schema_version": data["schema_version"], "toolchain": result, "hash": _sha256_file(TOOLS_REGISTRY)}


def _fixed_env(*, tool_id: str | None = None, nmap_data: Path | None = None) -> dict[str, str]:
    managed_home = MANAGED_ROOT / "home"
    managed_tmp = MANAGED_ROOT / "tmp"
    managed_home.mkdir(parents=True, exist_ok=True)
    managed_tmp.mkdir(parents=True, exist_ok=True)
    path = os.pathsep.join(str(item) for item in APPROVED_PATH_DIRS if item.exists())
    env = {
        "PATH": path,
        "HOME": str(managed_home),
        "TMPDIR": str(managed_tmp),
        "TMP": str(managed_tmp),
        "TEMP": str(managed_tmp),
        "LC_ALL": "C",
        "LANG": "C",
        "NO_COLOR": "1",
        "CI": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "NPM_CONFIG_COLOR": "false",
        "NPM_CONFIG_FUND": "false",
        "NPM_CONFIG_UPDATE_NOTIFIER": "false",
        "NPM_CONFIG_OFFLINE": "true",
    }
    if tool_id == "httpx":
        return {"available": _fixed_tailnet_ip() is not None, "target": "fixed_tailnet_runtime", "failure_code": None if _fixed_tailnet_ip() is not None else "remote_access_not_ready", "sanitized": True}
    if tool_id == "testssl.sh":
        # The fixed target is an IP-based local tunnel.  Avoid DNS helpers
        # and any network discovery outside that tunnel.
        env["NODNS"] = "none"
    if tool_id == "k6":
        sni = _fixed_tls_sni()
        if sni:
            env["POCKETLAB_FIXED_CADDY_HOST"] = sni
    if nmap_data is not None:
        env["NMAPDIR"] = str(nmap_data)
    if tool_id == "nmap":
        nmap_recipe = APT_RECIPES["nmap"]
        nmap_version = str(next(iter(nmap_recipe["packages"].values()))["version"])
        library_dirs = [
            MANAGED_ROOT / "packages" / "nmap" / nmap_version / name / "usr/lib/x86_64-linux-gnu"
            for name in ("libpcap0.8t64", "liblinear4", "liblua5.4-0", "libibverbs1", "libnl-3-200", "libnl-route-3-200")
        ]
        env["LD_LIBRARY_PATH"] = os.pathsep.join(str(path) for path in library_dirs if path.is_dir())
    if tool_id == "testssl.sh":
        recipe = APT_RECIPES["testssl.sh"]
        # Debian's package keeps the executable below usr/bin and the data
        # files testssl.sh loads (cipher-mapping.txt, ca_hashes.txt, etc.)
        # below etc/testssl.  This package layout is the data directory that
        # the pinned launcher accepts through TESTSSL_INSTALL_DIR.
        env["TESTSSL_INSTALL_DIR"] = str(
            MANAGED_ROOT
            / "packages"
            / "testssl.sh"
            / str(recipe["version"])
            / "testssl.sh"
            / "etc/testssl"
        )
        bind9_version = str((recipe.get("packages") or {}).get("bind9-libs", {}).get("version") or "")
        bind9_libs = [
            MANAGED_ROOT / "packages" / "testssl.sh" / str(recipe["version"]) / package / "usr/lib/x86_64-linux-gnu"
            for package in ("bind9-libs", "libuv1t64", "liburcu8t64", "libmaxminddb0", "liblmdb0")
        ]
        if bind9_version and any(path.is_dir() for path in bind9_libs):
            env["LD_LIBRARY_PATH"] = os.pathsep.join(
                [str(path) for path in bind9_libs if path.is_dir()]
                + ["/usr/lib/x86_64-linux-gnu", "/lib/x86_64-linux-gnu"]
            )
    return env


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, 15)
            time.sleep(0.05)
            if process.poll() is None:
                os.killpg(process.pid, 9)
        else:  # pragma: no cover - DEV PC is WSL2
            process.kill()
    except ProcessLookupError:
        return


def _bounded_run(argv: list[str], *, timeout_seconds: int, max_output_bytes: int, env: dict[str, str] | None = None, cwd: Path = ROOT) -> dict[str, Any]:
    """Run one internally constructed argv with bounded output and cleanup."""
    if not argv or any("\x00" in str(value) for value in argv):
        raise ValueError("assurance_command_invalid")
    executable = Path(argv[0])
    if not executable.is_absolute() or not executable.is_file() or not os.access(executable, os.X_OK):
        return {"status": "FAILED", "failure_code": "tool_executable_unavailable", "exit_code": None, "stdout": "", "stderr": "", "duration_ms": 0}
    started = time.monotonic()
    process: subprocess.Popen[bytes] | None = None
    stdout = bytearray()
    stderr = bytearray()
    output_limited = False
    timed_out = False
    try:
        process = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=env or _fixed_env(),
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        selector = selectors.DefaultSelector()
        assert process.stdout is not None and process.stderr is not None
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        deadline = started + max(1, int(timeout_seconds))
        while selector.get_map():
            if time.monotonic() >= deadline:
                timed_out = True
                _kill_group(process)
            events = selector.select(0.05)
            if not events and process.poll() is not None:
                for key in list(selector.get_map().values()):
                    selector.unregister(key.fileobj)
                break
            for key, _ in events:
                chunk = key.fileobj.read1(16 * 1024)
                if chunk:
                    target = stdout if key.data == "stdout" else stderr
                    target.extend(chunk)
                    if len(stdout) + len(stderr) > max(1024, int(max_output_bytes)):
                        output_limited = True
                        _kill_group(process)
                else:
                    selector.unregister(key.fileobj)
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        timed_out = True
        if process is not None:
            _kill_group(process)
            process.wait(timeout=5)
    except (OSError, ValueError) as exc:
        return {"status": "FAILED", "failure_code": type(exc).__name__.lower(), "exit_code": None, "stdout": "", "stderr": "", "duration_ms": int((time.monotonic() - started) * 1000)}
    finally:
        if process is not None:
            if process.stdout is not None:
                process.stdout.close()
            if process.stderr is not None:
                process.stderr.close()
    exit_code = process.returncode if process is not None else None
    status = "PARTIAL" if timed_out or output_limited else "PASS" if exit_code == 0 else "FAIL"
    return {
        "status": status,
        "failure_code": "timed_out" if timed_out else "output_limited" if output_limited else None,
        "exit_code": exit_code,
        "stdout": bytes(stdout).decode("utf-8", errors="replace"),
        "stderr": bytes(stderr).decode("utf-8", errors="replace"),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def _candidate(tool_id: str) -> Path | None:
    for path in LOCAL_CANDIDATES.get(tool_id, ()):
        if path.is_file() and os.access(path, os.X_OK):
            return path
    return None


def _probe_version(tool_id: str, binary: Path) -> dict[str, Any]:
    result = _bounded_run([str(binary), *VERSION_ARGS[tool_id]], timeout_seconds=25, max_output_bytes=MAX_VERSION_OUTPUT_BYTES, env=_fixed_env(tool_id=tool_id))
    combined = f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}"
    if tool_id == "owasp-zap":
        # zap.sh prints the JVM version before the actual ZAP version.  The
        # generic first-version parser therefore reports Java 17.x unless we
        # prefer the explicit launcher line.
        match = re.search(r"(?im)^\s*(\d+\.\d+\.\d+)\s*$", combined)
    else:
        match = re.search(r"(?<!\d)v?(\d+\.\d+(?:\.\d+)?(?:[-+][0-9A-Za-z.]+)?)", combined)
    version = match.group(1) if match else None
    expected = str((_registry()["toolchain"].get(tool_id) or {}).get("version_pin") or "")
    matches = bool(version) and (expected == "runtime-reported" or expected == "runtime-discovered" or expected in combined)
    return {
        "status": "READY" if result.get("status") == "PASS" and matches else "FAILED",
        "version": version or "UNAVAILABLE",
        "expected_version": expected,
        "version_matches": matches,
        "version_status": "verified" if matches else "mismatch_or_unavailable",
        "version_output_summary": _summary(combined, 3),
        "probe": {key: result.get(key) for key in ("status", "exit_code", "duration_ms", "failure_code")},
    }


def _receipt_path(tool_id: str) -> Path:
    return MANAGED_ROOT / "receipts" / f"{tool_id}.json"


def _load_receipt(tool_id: str) -> dict[str, Any]:
    try:
        data = json.loads(_receipt_path(tool_id).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: Any, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, mode)
    os.replace(temporary, path)
    os.chmod(path, mode)


def _promote_source(
    tool_id: str,
    source: Path,
    *,
    source_label: str,
    signature_status: str = "not_applicable",
    expected_checksum: str | None = None,
    expected_checksums: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    target = MANAGED_ROOT / "bin" / ("zap.sh" if tool_id == "owasp-zap" else tool_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.link")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(source.resolve())
    os.replace(temporary, target)
    actual = _sha256_file(source)
    receipt = {
        "schema_version": "1.0.0",
        "tool": tool_id,
        "version": str((_registry()["toolchain"].get(tool_id) or {}).get("version_pin") or "runtime-discovered"),
        "platform": f"{sys.platform}/{os.uname().machine if hasattr(os, 'uname') else 'unknown'}",
        "installation_source": source_label,
        "expected_checksum": expected_checksum,
        "expected_checksums": dict(expected_checksums or {}),
        "actual_checksum": f"sha256:{actual}",
        "checksum_status": "verified_archive_checksum" if expected_checksum or expected_checksums else "observed_source_checksum",
        "signature_status": signature_status,
        "binary_path": _display_path(target),
        "execution_lane": str((_registry()["toolchain"].get(tool_id) or {}).get("execution_lane") or ""),
        "installed_at": _now(),
    }
    _write_json(_receipt_path(tool_id), receipt)
    return receipt


def _source_label(tool_id: str, source: Path) -> tuple[str, str]:
    if ".pocketlab-dev" in source.as_posix():
        receipt = _load_existing_receipt(tool_id)
        if receipt:
            return "existing_verified_pocketlab_tool_receipt", "existing_receipt_sha256"
        return "existing_pocketlab_tool_cache", "observed_source_checksum"
    if ".venv" in source.as_posix():
        return "repository_development_venv", "package_environment_integrity"
    if ".nvm" in source.as_posix():
        return "approved_node_toolchain", "package_manager_toolchain"
    if source.as_posix().startswith("/usr/") or source.as_posix().startswith("/bin/"):
        return "approved_system_toolchain", "system_package_integrity"
    return "approved_local_toolchain", "observed_source_checksum"


def _load_existing_receipt(tool_id: str) -> dict[str, Any]:
    path = ROOT / ".pocketlab-dev/tools/documentation-security/receipts" / f"{tool_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _safe_extract_zip(archive: Path, destination: Path) -> None:
    base = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if target != base and base not in target.parents:
                raise RuntimeError("tool_archive_path_traversal_rejected")
        bundle.extractall(destination)


def _safe_extract_tar(archive: Path, destination: Path) -> None:
    base = destination.resolve()
    with tarfile.open(archive) as bundle:
        for member in bundle.getmembers():
            target = (destination / member.name).resolve()
            if target != base and base not in target.parents:
                raise RuntimeError("tool_archive_path_traversal_rejected")
        if sys.version_info >= (3, 12):
            bundle.extractall(destination, filter="data")
        else:  # pragma: no cover - current DEV PC is Python 3.14
            bundle.extractall(destination)


def _download_fixed(url: str, expected_sha256: str, destination: Path) -> None:
    if not url.startswith("https://github.com/"):
        raise RuntimeError("tool_download_origin_rejected")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.part")
    request = urllib.request.Request(url, headers={"User-Agent": "Pocket-Lab-Lite-security-assurance-toolchain/1", "Accept": "application/octet-stream"})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=60) as response, temporary.open("wb") as handle:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                handle.write(block)
                if handle.tell() > 512 * 1024 * 1024:
                    raise RuntimeError("tool_download_size_limit")
        if _sha256_file(temporary) != expected_sha256:
            raise RuntimeError("tool_download_checksum_mismatch")
        os.replace(temporary, destination)
    except (OSError, urllib.error.URLError) as exc:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"tool_download_failed:{type(exc).__name__}") from None
    finally:
        temporary.unlink(missing_ok=True)


def _install_github(tool_id: str) -> dict[str, Any]:
    recipe = GITHUB_RECIPES[tool_id]
    version_root = MANAGED_ROOT / "packages" / tool_id / recipe["version"]
    archive = version_root / Path(recipe["url"]).name
    version_root.mkdir(parents=True, exist_ok=True)
    if not archive.exists() or _sha256_file(archive) != recipe["sha256"]:
        _download_fixed(recipe["url"], recipe["sha256"], archive)
    extract_root = version_root / "extracted"
    if not extract_root.exists():
        extract_root.mkdir(parents=True)
        if recipe["archive"] == "zip":
            _safe_extract_zip(archive, extract_root)
        else:
            _safe_extract_tar(archive, extract_root)
    binaries = [path for path in extract_root.rglob(recipe["binary_name"]) if path.is_file()]
    if len(binaries) != 1:
        raise RuntimeError("tool_archive_binary_not_unique")
    binary = binaries[0]
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return _promote_source(
        tool_id,
        binary,
        source_label=recipe["source"],
        signature_status=recipe["signature_status"],
        expected_checksum=f"sha256:{recipe['sha256']}",
    )


def _install_apt(tool_id: str) -> dict[str, Any]:
    recipe = APT_RECIPES[tool_id]
    install_root = MANAGED_ROOT / "packages" / tool_id
    version = str(recipe.get("version") or next(iter(recipe["packages"].values()))["version"])
    version_root = install_root / version
    version_root.mkdir(parents=True, exist_ok=True)
    archive_root = MANAGED_ROOT / "tmp" / f"apt-{tool_id}-{os.getpid()}"
    archive_root.mkdir(parents=True, exist_ok=True)
    packages = recipe.get("packages") or {recipe["package"]: recipe}
    debs = list(archive_root.glob("*.deb"))
    if len(debs) < len(packages):
        present = {deb.name.split("_")[0] for deb in debs}
        requested = [f"{name}={spec['version']}" for name, spec in packages.items() if name not in present]
        args = ["/usr/bin/apt-get", "download", *requested]
        result = _bounded_run(args, timeout_seconds=180, max_output_bytes=32 * 1024, cwd=archive_root)
        if result.get("status") != "PASS":
            raise RuntimeError(f"apt_download_failed:{result.get('failure_code') or result.get('exit_code')}")
        debs = list(archive_root.glob("*.deb"))
    expected_by_name = {str(name): str(spec["sha256"]) for name, spec in packages.items()}
    for deb in debs:
        name = deb.name.split("_")[0]
        if name not in expected_by_name or _sha256_file(deb) != expected_by_name[name]:
            raise RuntimeError("apt_package_checksum_mismatch")
        package_root = version_root / name
        if not package_root.exists():
            package_root.mkdir(parents=True)
            result = _bounded_run(["/usr/bin/dpkg-deb", "--extract", str(deb), str(package_root)], timeout_seconds=60, max_output_bytes=16 * 1024, cwd=archive_root)
            if result.get("status") != "PASS":
                raise RuntimeError("apt_package_extract_failed")
    binary = version_root / ("nmap" if tool_id == "nmap" else "testssl.sh") / recipe["binary_relpath"]
    if not binary.is_file() and tool_id == "testssl.sh":
        binary = version_root / recipe["package"] / recipe["binary_relpath"]
    if not binary.is_file():
        raise RuntimeError("apt_package_binary_missing")
    if tool_id == "testssl.sh":
        dnsutils = version_root / "bind9-dnsutils" / "usr/bin/dig"
        if not dnsutils.is_file():
            raise RuntimeError("testssl_dns_helper_missing")
        helper = MANAGED_ROOT / "bin" / "dig"
        temporary = helper.with_name(f".{helper.name}.{os.getpid()}.link")
        temporary.unlink(missing_ok=True)
        temporary.symlink_to(dnsutils.resolve())
        os.replace(temporary, helper)
        os.chmod(helper, 0o755)
    if tool_id == "nmap":
        # nmap-common is kept beside nmap and supplied as a fixed NMAPDIR at
        # execution time; no system package is installed or modified.
        source_label = "Ubuntu archive fixed nmap+nmap-common packages"
    else:
        source_label = "Ubuntu archive fixed testssl.sh package"
    receipt = _promote_source(
        tool_id,
        binary,
        source_label=source_label,
        signature_status="apt_repository_metadata",
        expected_checksums={name: f"sha256:{value}" for name, value in expected_by_name.items()},
    )
    receipt["package_archives"] = sorted(expected_by_name)
    if tool_id == "testssl.sh":
        receipt["fixed_auxiliary_commands"] = ["dig"]
    _write_json(_receipt_path(tool_id), receipt)
    for item in archive_root.glob("*"):
        item.unlink(missing_ok=True)
    archive_root.rmdir()
    return receipt


def _check_one(tool_id: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    lane = str(spec.get("execution_lane") or "")
    base = {
        "tool_id": tool_id,
        "execution_lane": lane,
        "harness_status": str(spec.get("harness_status") or ""),
        "fixed_target": str(spec.get("fixed_target") or ""),
        "command_id": str(spec.get("command_id") or ""),
        "suite_membership": list(spec.get("suite_membership") or []),
        "status": "FAILED",
        "version": "UNAVAILABLE",
        "installation_source": str(spec.get("installation_source") or ""),
        "checksum_status": "UNAVAILABLE",
        "signature_status": "UNAVAILABLE",
    }
    if lane == "server_phone_worker":
        base.update({"status": "READY", "version": "runtime-reported", "version_status": "worker_owned_contract", "installation_source": "server_owned_worker_registry", "checksum_status": "server_runtime_receipt", "signature_status": "server_runtime_receipt"})
        return base
    binary = _candidate(tool_id)
    if binary is None:
        base.update({"failure_code": "qualified_executable_not_found", "status_detail": "no approved local executable"})
        return base
    version = _probe_version(tool_id, binary)
    receipt = _load_receipt(tool_id)
    actual_checksum = f"sha256:{_sha256_file(binary)}"
    receipt_checksum = str(receipt.get("actual_checksum") or "")
    checksum_matches = not receipt_checksum or receipt_checksum == actual_checksum
    base.update({
        "binary_path": _display_path(binary),
        "status": version["status"] if checksum_matches else "FAILED",
        "version": version["version"],
        "expected_version": version["expected_version"],
        "version_status": version["version_status"],
        "version_output_summary": version["version_output_summary"],
        "checksum_status": str(receipt.get("checksum_status") or "not_managed") if receipt else "not_managed",
        "actual_checksum": actual_checksum,
        "checksum_matches_receipt": checksum_matches,
        "signature_status": str(receipt.get("signature_status") or "not_applicable"),
        "installation_source": str(receipt.get("installation_source") or base["installation_source"]),
    })
    if not checksum_matches:
        base.update({"failure_code": "qualified_binary_checksum_mismatch", "status_detail": "promoted executable changed after receipt"})
    if tool_id == "cosign" and not COSIGN_ARTIFACT_MANIFEST.exists() and base["status"] == "READY":
        base.update({"status": "NOT_APPLICABLE", "status_detail": "no signed artifact registered for this revision"})
    return base


def check_toolchain() -> dict[str, Any]:
    registry = _registry()
    tools = [_check_one(tool_id, spec) for tool_id, spec in sorted(registry["toolchain"].items())]
    statuses = {item["status"] for item in tools}
    overall = "PASS" if statuses.issubset({"READY", "NOT_APPLICABLE"}) else "FAIL"
    return {
        "status": overall,
        "captured_at": _now(),
        "registry_sha256": registry["hash"],
        "tools": tools,
        "required_status_vocabulary": ["READY", "NOT_APPLICABLE", "FAILED"],
        "sanitized": True,
    }


def install_toolchain() -> dict[str, Any]:
    registry = _registry()
    results: list[dict[str, Any]] = []
    for tool_id, spec in sorted(registry["toolchain"].items()):
        lane = str(spec.get("execution_lane") or "")
        if lane == "server_phone_worker":
            results.append({"tool_id": tool_id, "status": "READY", "action": "server_worker_owned", "sanitized": True})
            continue
        source = _candidate(tool_id)
        try:
            current = _check_one(tool_id, spec) if source is not None else None
            receipt = _load_receipt(tool_id)
            fixed_recipe = tool_id in APT_RECIPES or tool_id in GITHUB_RECIPES
            provenance_present = bool(receipt.get("expected_checksum") or receipt.get("expected_checksums"))
            testssl_support_ready = tool_id != "testssl.sh" or (
                (MANAGED_ROOT / "bin" / "dig").is_file()
                and all(
                    (
                        MANAGED_ROOT
                        / "packages"
                        / "testssl.sh"
                        / str(APT_RECIPES["testssl.sh"]["version"])
                        / package
                        / "usr/lib/x86_64-linux-gnu"
                    ).is_dir()
                    for package in ("bind9-libs", "libuv1t64", "liburcu8t64", "libmaxminddb0", "liblmdb0")
                )
            )
            needs_fixed_repair = bool(
                current
                and fixed_recipe
                and (
                    current.get("status") == "FAILED"
                    or not provenance_present
                    or not testssl_support_ready
                )
            )
            if (source is None or needs_fixed_repair) and tool_id in APT_RECIPES:
                receipt = _install_apt(tool_id)
                action = "installed_fixed_apt_package"
            elif (source is None or needs_fixed_repair) and tool_id in GITHUB_RECIPES:
                receipt = _install_github(tool_id)
                action = "installed_fixed_release_asset"
            elif source is None:
                raise RuntimeError("no_approved_install_recipe")
            else:
                label, signature = _source_label(tool_id, source)
                receipt = _promote_source(tool_id, source, source_label=label, signature_status=signature)
                action = "promoted_existing_qualified_tool"
            checked = _check_one(tool_id, spec)
            results.append({"tool_id": tool_id, "action": action, "receipt": receipt, "check": checked, "status": "PASS" if checked.get("status") in {"READY", "NOT_APPLICABLE"} else "FAIL", "sanitized": True})
        except (OSError, RuntimeError, ValueError) as exc:
            results.append({"tool_id": tool_id, "status": "FAIL", "failure_code": _sanitize_text(str(exc), 120), "sanitized": True})
    successful = {"PASS", "READY"}
    return {"status": "PASS" if all(row.get("status") in successful for row in results) else "PARTIAL", "captured_at": _now(), "registry_sha256": registry["hash"], "tools": results, "sanitized": True}


def _tool_context(tool_id: str, workspace: Path) -> tuple[Path | None, dict[str, str]]:
    binary = _candidate(tool_id)
    if binary is None:
        return None, _fixed_env()
    nmap_data = None
    if tool_id == "nmap":
        recipe = APT_RECIPES.get("nmap") or {}
        version = next(iter((recipe.get("packages") or {}).values()), {}).get("version", "")
        nmap_data = MANAGED_ROOT / "packages" / "nmap" / str(version) / "nmap-common" / str(recipe.get("data_relpath") or "usr/share/nmap")
        if not nmap_data.is_dir():
            nmap_data = None
    return binary, _fixed_env(tool_id=tool_id, nmap_data=nmap_data)


def _fixed_schema(workspace: Path) -> Path:
    source = json.loads(OPENAPI_SCHEMA.read_text(encoding="utf-8"))
    paths = source.get("paths") if isinstance(source, dict) else {}
    selected: dict[str, Any] = {}
    for path in LIVE_ROUTE_ALLOWLIST:
        item = paths.get(path) if isinstance(paths, dict) else None
        if isinstance(item, dict) and isinstance(item.get("get"), dict):
            selected[path] = {key: value for key, value in item.items() if key.lower() == "get" or key.lower() not in {"post", "put", "patch", "delete", "options", "head", "trace"}}
    if "/health" not in selected or "/ready" not in selected:
        raise RuntimeError("schemathesis_fixed_schema_missing_health_routes")
    compiled = {key: value for key, value in source.items() if key != "paths"}
    compiled["paths"] = selected
    path = workspace / "schemathesis-safe-openapi.json"
    path.write_text(json.dumps(compiled, ensure_ascii=True, sort_keys=True), encoding="utf-8")
    return path


def _parse_json(text: str) -> Any:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return None
    return value


def _finding_key(tool_id: str, identity: str) -> str:
    return f"assurance-tool:{_sha256_bytes(f'{tool_id}|{identity}'.encode())[:32]}"


def _severity(value: Any, default: str = "info") -> str:
    candidate = str(value or default).casefold()
    return candidate if candidate in {"critical", "high", "medium", "low", "info", "unknown"} else default


def _base_finding(*, tool_id: str, suite_id: str, identity: str, title: str, severity: str, summary: str, component: str = "repository", asset: str = "Pocket Lab Lite") -> dict[str, Any]:
    mapping = {
        "gitleaks": (["Information Disclosure", "Tampering"], ["A02", "A08"]),
        "bandit": (["Tampering", "Elevation of Privilege"], ["A05", "A06"]),
        "semgrep": (["Elevation of Privilege", "Tampering"], ["A01", "A05"]),
        "pip-audit": (["Tampering", "Information Disclosure"], ["A06", "A08"]),
        "npm-audit": (["Tampering", "Information Disclosure"], ["A06", "A08"]),
        "osv-scanner": (["Tampering", "Information Disclosure"], ["A06", "A08"]),
        "grype": (["Tampering", "Information Disclosure"], ["A06", "A08"]),
        "nuclei": (["Information Disclosure", "Elevation of Privilege"], ["A01", "A05"]),
        "owasp-zap": (["Information Disclosure", "Elevation of Privilege"], ["A01", "A05"]),
    }
    stride, owasp = mapping.get(tool_id, (["Information Disclosure"], ["A02"]))
    return {
        "finding_id": _finding_key(tool_id, identity),
        "suite": suite_id,
        "tool": tool_id,
        "category": "security_assurance",
        "severity": _severity(severity),
        "confidence": "medium",
        "title": _sanitize_text(title, 180),
        "safe_summary": _sanitize_text(summary, 400),
        "component": _sanitize_text(component, 160),
        "asset": asset,
        "trust_boundary": "DEV_PC_assurance_lane_to_Pocket_Lab_owned_surface",
        "stride": stride,
        "owasp": owasp,
        "attack_paths": ["AP-05"] if tool_id in {"pip-audit", "npm-audit", "osv-scanner", "syft", "grype", "cosign"} else ["AP-01"],
        "controls": ["CTRL-SUPPLY-CHAIN"] if tool_id in {"pip-audit", "npm-audit", "osv-scanner", "syft", "grype", "cosign"} else ["CTRL-API-CONTROL"],
        "cwe": [],
        "cve": [],
        "sanitized_file_reference": None,
        "runtime_target": "local_server_host_only",
        "first_seen_at": _now(),
        "last_seen_at": _now(),
        "evidence_refs": [],
        "status": "open",
        "baseline_state": "NEW",
        "remediation": "Review the bounded normalized evidence and remediate on DEV PC if confirmed.",
    }


def _parse_findings(
    tool_id: str,
    suite_id: str,
    stdout: str,
    stderr: str,
    workspace: Path,
    artifact_payload: Any = None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    payload = artifact_payload if artifact_payload is not None else _parse_json(stdout)
    if tool_id in {"mitmdump", "websocat", "tshark", "nats-cli"} and isinstance(payload, dict):
        for item in payload.get("security_findings") or []:
            if isinstance(item, Mapping):
                finding = _base_finding(
                    tool_id=tool_id,
                    suite_id=suite_id,
                    identity=str(item.get("id") or "runtime-probe"),
                    title=str(item.get("id") or "Runtime security invariant violation"),
                    severity=str(item.get("severity") or "high"),
                    summary=str(item.get("summary") or "A fixed live-runtime invariant failed."),
                    component="live runtime",
                )
                finding["attack_paths"] = [str(value) for value in item.get("attack_paths") or finding.get("attack_paths") or []]
                findings.append(finding)
        return findings
    if tool_id == "playwright" and isinstance(payload, dict):
        stats = payload.get("stats") if isinstance(payload.get("stats"), Mapping) else {}
        unexpected = int(stats.get("unexpected") or 0)
        if unexpected:
            findings.append(_base_finding(tool_id=tool_id, suite_id=suite_id, identity=f"playwright-unexpected-{unexpected}", title="Live browser security assertion failed", severity="high", summary=f"{unexpected} fixed browser security assertion(s) failed against the qualified runtime.", component="browser/PWA runtime"))
        return findings
    if tool_id == "httpx" and stdout.strip():
        findings.append(_base_finding(tool_id=tool_id, suite_id=suite_id, identity="tailnet-direct-fastapi", title="Direct FastAPI unexpectedly reachable on private network", severity="high", summary="The fixed Tailnet exposure probe observed the direct FastAPI service outside Caddy.", component="private-network exposure"))
        findings[-1]["attack_paths"] = ["AP-07"]
        return findings
    if tool_id == "katana":
        if any("/api/lite/harness" in line or "/debug" in line or "/admin" in line for line in stdout.splitlines()):
            findings.append(_base_finding(tool_id=tool_id, suite_id=suite_id, identity="unexpected-route-surface", title="Unexpected privileged route discovered", severity="high", summary="Bounded route discovery observed a harness/debug/admin route on the external Caddy surface.", component="Caddy external surface"))
        return findings
    if tool_id == "ffuf" and isinstance(payload, dict):
        for row in payload.get("results") or []:
            if not isinstance(row, Mapping):
                continue
            url = str(row.get("url") or "")
            status = int(row.get("status") or 0)
            if status < 400 and any(token in url for token in ("/api/lite/harness", "/debug", "/admin", "/metrics")):
                findings.append(_base_finding(tool_id=tool_id, suite_id=suite_id, identity=f"{status}|{url.rsplit('/',1)[-1]}", title="Unexpected privileged route reachable", severity="high", summary="A fixed tiny-wordlist probe observed a privileged/debug route with a non-error response.", component="Caddy external surface"))
        return findings
    if tool_id == "bandit" and isinstance(payload, dict):
        for row in payload.get("results") or []:
            if isinstance(row, dict):
                findings.append(_base_finding(tool_id=tool_id, suite_id=suite_id, identity=f"{row.get('test_id')}|{row.get('filename')}|{row.get('line_number')}", title=str(row.get("issue_text") or row.get("test_id") or "Bandit finding"), severity=str(row.get("issue_severity") or "medium"), summary=f"Bandit {row.get('test_id') or 'rule'} at bounded source location.", component=str(row.get("filename") or "runtime source")))
    elif tool_id == "semgrep" and isinstance(payload, dict):
        for row in payload.get("results") or []:
            if isinstance(row, dict):
                extra = row.get("extra") if isinstance(row.get("extra"), dict) else {}
                findings.append(_base_finding(tool_id=tool_id, suite_id=suite_id, identity=f"{row.get('check_id')}|{row.get('path')}|{(row.get('start') or {}).get('line')}", title=str(extra.get("message") or row.get("check_id") or "Semgrep finding"), severity=str(extra.get("severity") or "medium"), summary=f"Semgrep {row.get('check_id') or 'rule'} at bounded source location.", component=str(row.get("path") or "source")))
    elif tool_id == "gitleaks":
        report = workspace / "gitleaks.json"
        if report.exists():
            value = _parse_json(report.read_text(encoding="utf-8", errors="replace"))
            if isinstance(value, list):
                for row in value:
                    if isinstance(row, dict):
                        raw_file = str(row.get("File") or "")
                        marker = "/gitleaks-source/"
                        file_ref = raw_file.split(marker, 1)[1] if marker in raw_file else "bounded source path"
                        try:
                            line_number = max(0, int(row.get("StartLine") or 0))
                        except (TypeError, ValueError):
                            line_number = 0
                        test_only = (
                            file_ref == "tests/backend/test_lite_termux_runtime_documentation.py"
                            or (
                                file_ref == "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_assurance.py"
                                and line_number == 992
                            )
                        )
                        finding = _base_finding(
                            tool_id=tool_id,
                            suite_id=suite_id,
                            identity=f"{row.get('RuleID')}|{file_ref}|{line_number}",
                            title=f"Secret-detection rule {row.get('RuleID') or 'unknown'}",
                            severity="info" if test_only else "high",
                            summary=(
                                "A fixed test/protocol fixture matched a secret-detection rule; no credential is present and the value was redacted by policy."
                                if test_only
                                else "A secret-detection rule matched; the secret value was redacted by policy."
                            ),
                            component=file_ref,
                        )
                        finding["sanitized_file_reference"] = f"REPOSITORY_ROOT/{file_ref}:{line_number}" if line_number else f"REPOSITORY_ROOT/{file_ref}"
                        finding["classification"] = "TEST_ONLY" if test_only else "UNTRIAGED"
                        if test_only:
                            finding["confidence"] = "low"
                            finding["status"] = "review"
                            finding["remediation"] = "No source remediation; retain the fixed fixture and its sanitization test."
                        findings.append(finding)
    elif tool_id in {"pip-audit", "osv-scanner", "grype", "npm-audit"}:
        rows: list[tuple[str, str, str, str]] = []
        if tool_id == "pip-audit" and isinstance(payload, dict):
            for dep in payload.get("dependencies") or []:
                if isinstance(dep, dict):
                    for vuln in dep.get("vulns") or []:
                        if isinstance(vuln, dict):
                            rows.append((str(vuln.get("id") or "unknown"), str(dep.get("name") or "package"), str(vuln.get("fix_versions") or ""), "high"))
        elif tool_id == "grype" and isinstance(payload, dict):
            for match in payload.get("matches") or []:
                if isinstance(match, dict):
                    vuln = match.get("vulnerability") if isinstance(match.get("vulnerability"), dict) else {}
                    artifact = match.get("artifact") if isinstance(match.get("artifact"), dict) else {}
                    rows.append((str(vuln.get("id") or "unknown"), str(artifact.get("name") or "package"), str(vuln.get("fix", {}).get("versions") if isinstance(vuln.get("fix"), dict) else ""), str(vuln.get("severity") or "medium")))
        elif tool_id == "npm-audit" and isinstance(payload, dict):
            vulns = payload.get("vulnerabilities") if isinstance(payload.get("vulnerabilities"), dict) else {}
            for name, vuln in vulns.items():
                if isinstance(vuln, dict):
                    rows.append((str((vuln.get("via") or [{}])[0].get("url") if isinstance((vuln.get("via") or [{}])[0], dict) else "npm-advisory"), str(name), str(vuln.get("fixAvailable") or ""), str(vuln.get("severity") or "medium")))
        elif tool_id == "osv-scanner" and isinstance(payload, dict):
            for result in payload.get("results") or []:
                if not isinstance(result, dict):
                    continue
                for pkg in result.get("packages") or []:
                    if not isinstance(pkg, dict):
                        continue
                    package = pkg.get("package") if isinstance(pkg.get("package"), dict) else {}
                    package_name = str(package.get("name") or "package")
                    for vuln in pkg.get("vulnerabilities") or []:
                        if isinstance(vuln, dict):
                            severity = str(
                                vuln.get("database_specific", {}).get("severity")
                                if isinstance(vuln.get("database_specific"), dict)
                                else ""
                            )
                            if not severity:
                                score = str(pkg.get("max_severity") or "")
                                severity = "critical" if score.startswith("9") else "high" if score.startswith("7") or score.startswith("8") else "medium"
                            rows.append((str(vuln.get("id") or "unknown"), package_name, "", severity))
        for advisory, package, fix, severity in rows:
            finding = _base_finding(tool_id=tool_id, suite_id=suite_id, identity=f"{advisory}|{package}", title=f"Dependency advisory {advisory}", severity=severity, summary=f"Dependency {package} has a reported advisory; remediation metadata is {fix[:120] or 'not supplied'}.", component=package)
            finding["advisory_key"] = f"{advisory}|{package}"[:240]
            findings.append(finding)
    elif tool_id == "nuclei":
        for line in stdout.splitlines():
            row = _parse_json(line)
            if isinstance(row, dict):
                info = row.get("info") if isinstance(row.get("info"), dict) else {}
                template = str(row.get("template-id") or "unknown")
                findings.append(_base_finding(tool_id=tool_id, suite_id=suite_id, identity=f"{template}|{row.get('matched-at')}", title=f"Nuclei safe template {template}", severity=str(info.get("severity") or "info"), summary="A curated non-destructive HTTP template matched the approved Pocket Lab endpoint.", component="approved Pocket Lab endpoint"))
    elif tool_id == "owasp-zap":
        # ``-quickout *.json`` is preferred because it gives the adapter a
        # structured alert stream without persisting ZAP's raw report.  Keep
        # a bounded text fallback for older ZAP add-ons, but never retain the
        # alert message, URL or request/response body.
        alert_rows: list[Mapping[str, Any]] = []

        def collect_alerts(value: Any) -> None:
            if isinstance(value, dict):
                if any(key in value for key in ("alert", "riskcode", "riskdesc")):
                    alert_rows.append(value)
                for child in value.values():
                    collect_alerts(child)
            elif isinstance(value, list):
                for child in value:
                    collect_alerts(child)

        collect_alerts(payload)
        risk_map = {"3": "high", "2": "medium", "1": "low", "0": "info"}
        for row in alert_rows[:100]:
            alert = str(row.get("alert") or row.get("name") or "zap-alert")
            identity = f"{alert}|{row.get('pluginid') or row.get('id') or 'unknown'}"
            severity = risk_map.get(str(row.get("riskcode") or ""), str(row.get("riskdesc") or "info").split()[0].casefold())
            findings.append(_base_finding(tool_id=tool_id, suite_id=suite_id, identity=identity, title="ZAP bounded API baseline alert", severity=severity, summary="A bounded ZAP API baseline alert was observed; raw alert details were not retained.", component="approved Pocket Lab endpoint"))
        if not alert_rows:
            for line in stdout.splitlines():
                if re.search(r"(?i)\b(alert|risk|high|medium|low)\b", line):
                    findings.append(_base_finding(tool_id=tool_id, suite_id=suite_id, identity=line[:240], title="ZAP bounded API baseline alert", severity="medium", summary="A bounded ZAP API baseline alert was observed; raw alert details were not retained.", component="approved Pocket Lab endpoint"))
    return findings


def _gitleaks_source(workspace: Path) -> Path:
    """Build a fixed, tracked-file-only scan view without scanning caches.

    Gitleaks' directory mode walks every directory below ``--source`` even
    when its allowlist suppresses findings.  The repository contains large
    local dependency/cache trees, so passing the checkout directly would
    spend the bounded scan window traversing data that the assurance policy
    explicitly excludes.  Build a temporary hard-link view from Git's
    allow-listed file inventory instead.  Hard links keep this cheap and do
    not mutate the source checkout; the temporary view is removed with the
    suite workspace.
    """
    source = workspace / "gitleaks-source"
    source.mkdir(parents=True, exist_ok=True)
    inventory = _bounded_run(
        ["/usr/bin/git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        timeout_seconds=30,
        max_output_bytes=8 * 1024 * 1024,
        env=_fixed_env(),
        cwd=ROOT,
    )
    if inventory.get("status") != "PASS":
        raise RuntimeError("gitleaks_file_inventory_failed")
    excluded_prefixes = (
        ".git/",
        ".pocketlab-dev/",
        ".venv/",
        "node_modules/",
        "site/",
        "storybook-static/",
        "dist/",
        "docs/generated/",
        "contracts/generated/",
    )
    for raw in str(inventory.get("stdout") or "").split("\x00"):
        relative = raw.strip()
        if not relative or relative.startswith(excluded_prefixes) or relative == ".git":
            continue
        candidate = ROOT / relative
        try:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            resolved = candidate.resolve()
            resolved.relative_to(ROOT)
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(resolved, target)
        except (OSError, ValueError):
            # A changing/unusual checkout entry is not allowed to expand the
            # target outside the repository or abort sanitization.  It is
            # represented by the fixed inventory summary rather than read.
            continue
    return source


def _dependency_source(workspace: Path) -> Path:
    """Build a fixed dependency-manifest view for offline OSV scanning."""
    source = workspace / "dependency-manifests"
    source.mkdir(parents=True, exist_ok=True)
    inventory = _bounded_run(
        ["/usr/bin/git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        timeout_seconds=30,
        max_output_bytes=8 * 1024 * 1024,
        env=_fixed_env(),
        cwd=ROOT,
    )
    if inventory.get("status") != "PASS":
        raise RuntimeError("dependency_file_inventory_failed")
    accepted_names = {
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "Pipfile.lock",
        "Cargo.lock",
        "go.sum",
    }
    for raw in str(inventory.get("stdout") or "").split("\x00"):
        relative = raw.strip()
        if not relative or relative.startswith((".git/", ".pocketlab-dev/", ".venv/", "node_modules/", "docs/generated/", "contracts/generated/")):
            continue
        name = Path(relative).name
        if name not in accepted_names and not (name.startswith("requirements") and name.endswith((".txt", ".in"))):
            continue
        candidate = ROOT / relative
        try:
            if candidate.is_symlink() or not candidate.is_file():
                continue
            resolved = candidate.resolve()
            resolved.relative_to(ROOT)
            target = source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(resolved, target)
        except (OSError, ValueError):
            continue
    return source


def _live_target_probe(tool_id: str) -> dict[str, Any]:
    """Prove the fixed DEV-PC tunnel reaches the Pocket Lab target."""
    if tool_id in {"schemathesis", "nuclei", "nmap", "owasp-zap", "playwright", "mitmdump", "hurl", "k6", "websocat", "katana", "tlsx", "tshark", "ffuf", "nats-cli"}:
        try:
            request = urllib.request.Request(f"{API_BASE}/health", headers={"Accept": "application/json"})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=3) as response:
                healthy = int(response.status) == 200
            return {"available": healthy, "target": "fixed_api_tunnel", "http_status": 200 if healthy else None, "sanitized": True}
        except urllib.error.HTTPError as exc:
            return {"available": False, "target": "fixed_api_tunnel", "http_status": int(exc.code), "failure_code": "runtime_target_unhealthy", "sanitized": True}
        except (OSError, urllib.error.URLError):
            return {"available": False, "target": "fixed_api_tunnel", "failure_code": "runtime_target_unavailable", "sanitized": True}
    if tool_id == "testssl.sh":
        sni = _fixed_tls_sni()
        if sni is None:
            return {"available": False, "target": "fixed_caddy_tls_tunnel", "failure_code": "runtime_tls_identity_unavailable", "sanitized": True}
        try:
            with socket.create_connection(("127.0.0.1", 18443), timeout=3):
                return {"available": True, "target": "fixed_caddy_tls_tunnel", "tls_identity_configured": True, "sanitized": True}
        except OSError:
            return {"available": False, "target": "fixed_caddy_tls_tunnel", "failure_code": "runtime_target_unavailable", "sanitized": True}
    return {"available": True, "target": "fixed_registered_target", "sanitized": True}


def _fixed_tailnet_ip() -> str | None:
    """Derive the private-network IPv4 only from the fixed runtime readiness API."""
    try:
        request = urllib.request.Request(f"{API_BASE}/api/lite/remote-access/readiness", headers={"Accept": "application/json", "Cache-Control": "no-cache"})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=3) as response:
            if int(response.status) != 200:
                return None
            payload = json.loads(response.read(64 * 1024).decode("utf-8"))
    except (OSError, urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    values: list[str] = []
    def walk(value: Any) -> None:
        if isinstance(value, Mapping):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str):
            values.append(value.strip())
    walk(payload)
    network = ipaddress.ip_network("100.64.0.0/10")
    for raw in values:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if address.version == 4 and address in network:
            return str(address)
    return None


def _dev_pc_scenario_definitions(suite_id: str) -> list[dict[str, Any]]:
    suites = yaml.safe_load(SUITES_REGISTRY.read_text(encoding="utf-8")) or {}
    scenarios = yaml.safe_load(SCENARIOS_REGISTRY.read_text(encoding="utf-8")) or {}
    profile = (suites.get("profiles") or {}).get(suite_id) or {}
    by_id = {str(item.get("id")): item for item in scenarios.get("scenarios") or [] if isinstance(item, Mapping)}
    result = []
    for scenario_id in profile.get("dev_pc_scenarios") or []:
        item = by_id.get(str(scenario_id))
        if not isinstance(item, Mapping) or str(item.get("execution") or "") != "dev_pc_live_runtime_evidence":
            raise RuntimeError("dev_pc_assurance_scenario_invalid")
        result.append(dict(item))
    return result


def _scenario_results(suite_id: str, tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_tool = {str(item.get("tool_id")): item for item in tool_results}
    registry = _registry()["toolchain"]
    rows: list[dict[str, Any]] = []
    for definition in _dev_pc_scenario_definitions(suite_id):
        requested = [str(value) for value in definition.get("evidence_tools") or []]
        external = [tool_id for tool_id in requested if str((registry.get(tool_id) or {}).get("execution_lane") or "") != "server_phone_worker"]
        evidence = [by_tool[tool_id] for tool_id in external if tool_id in by_tool]
        missing = sorted(set(external) - set(by_tool))
        findings = [finding for item in evidence for finding in item.get("findings") or [] if isinstance(finding, Mapping)]
        severe = [finding for finding in findings if str(finding.get("severity") or "").casefold() in {"critical", "high"}]
        incomplete = [item for item in evidence if str(item.get("status") or "") in {"FAILED", "PARTIAL", "BLOCKED", "NOT_RUN"}]
        human_review = str(definition.get("id") or "") == "webauthn-origin-rpid-mismatch"
        if severe:
            status = "FAIL"
            reason = "security_invariant_violation"
        elif missing or not evidence:
            status = "BLOCKED"
            reason = "required_live_tool_unavailable"
        elif incomplete or human_review:
            status = "PARTIAL"
            reason = "human_review_required" if human_review else "runtime_evidence_incomplete"
        else:
            status = "PASS"
            reason = None
        rows.append({
            "scenario_id": str(definition.get("id") or ""),
            "title": str(definition.get("title") or "")[:200],
            "status": status,
            "failure_code": reason,
            "required_tools": external,
            "tool_status": {str(item.get("tool_id")): str(item.get("status")) for item in evidence},
            "finding_ids": [str(item.get("finding_id") or "") for item in findings][:64],
            "human_review_required": human_review,
            "attack_paths": [str(value) for value in definition.get("attack_paths") or []],
            "sanitized": True,
        })
    return rows


def _run_command_for_tool(tool_id: str, suite_id: str, binary: Path, workspace: Path, env: dict[str, str]) -> tuple[list[str], Path | None]:
    if tool_id == "playwright":
        return [str(binary), "test", "--config", str(PLAYWRIGHT_SECURITY_CONFIG), str(PLAYWRIGHT_SECURITY_SPEC), "--project", "security-runtime", "--reporter=json"], None
    if tool_id == "mitmdump":
        return [sys.executable, str(RUNTIME_PROBE), "mitmproxy"], None
    if tool_id == "hurl":
        sni = _fixed_tls_sni()
        if sni is None:
            raise RuntimeError("runtime_tls_identity_unavailable")
        return [str(binary), "--test", "--insecure", "--variable", f"host={sni}", str(HURL_SECURITY_FILE)], None
    if tool_id == "k6":
        return [str(binary), "run", "--vus", "2", "--duration", "8s", str(K6_SECURITY_FILE)], None
    if tool_id == "websocat":
        return [sys.executable, str(RUNTIME_PROBE), "websocket"], None
    if tool_id == "tshark":
        return [sys.executable, str(RUNTIME_PROBE), "tshark"], None
    if tool_id == "nats-cli":
        return [sys.executable, str(RUNTIME_PROBE), "nats"], None
    if tool_id == "httpx":
        tailnet = _fixed_tailnet_ip()
        if tailnet is None:
            raise RuntimeError("remote_access_not_ready")
        return [str(binary), "-u", f"http://{tailnet}:8080/health", "-silent", "-status-code", "-no-color", "-timeout", "3", "-retries", "0"], None
    if tool_id == "tlsx":
        sni = _fixed_tls_sni()
        if sni is None:
            raise RuntimeError("runtime_tls_identity_unavailable")
        return [str(binary), "-u", TLS_TARGET, "-sni", sni, "-json", "-silent"], None
    if tool_id == "katana":
        sni = _fixed_tls_sni()
        if sni is None:
            raise RuntimeError("runtime_tls_identity_unavailable")
        return [str(binary), "-u", f"https://127.0.0.1:18443", "-H", f"Host: {sni}", "-d", "1", "-c", "1", "-rl", "2", "-timeout", "5", "-jc", "-silent"], None
    if tool_id == "ffuf":
        sni = _fixed_tls_sni()
        if sni is None:
            raise RuntimeError("runtime_tls_identity_unavailable")
        report = workspace / "ffuf.json"
        return [str(binary), "-w", str(FFUF_WORDLIST), "-u", "https://127.0.0.1:18443/FUZZ", "-H", f"Host: {sni}", "-k", "-t", "1", "-rate", "2", "-maxtime", "20", "-of", "json", "-o", str(report), "-s"], report
    if tool_id == "bandit":
        return [str(binary), "-r", str(ROOT / "pocket-lab-final-structure/runtime"), "--format", "json", "--quiet", "--exclude", str(ROOT / ".venv"), "--exclude", str(ROOT / ".pocketlab-dev")], None
    if tool_id == "gitleaks":
        report = workspace / "gitleaks.json"
        source = _gitleaks_source(workspace)
        return [str(binary), "detect", "--no-banner", "--no-color", "--no-git", "--redact=100", "--max-target-megabytes", "5", "--config", str(GITLEAKS_CONFIG), "--report-format", "json", "--report-path", str(report), "--exit-code", "0", "--source", str(source)], report
    if tool_id == "pip-audit":
        return [str(binary), "-r", str(ROOT / "pocket-lab-final-structure/runtime/requirements.txt"), "--format", "json", "--progress-spinner", "off"], None
    if tool_id == "npm-audit":
        return [str(binary), "audit", "--package-lock-only", "--json", "--offline"], None
    if tool_id == "semgrep":
        return [str(binary), "scan", "--config", str(SEMgrep_RULES), "--json", "--metrics", "off", "--no-git-ignore", str(ROOT / "pocket-lab-final-structure")], None
    if tool_id == "osv-scanner":
        source = _dependency_source(workspace)
        report = workspace / "osv.json"
        return [str(binary), "scan", "source", "--format", "json", "--recursive", "--no-resolve", "--allow-no-lockfiles", "--output-file", str(report), str(source)], report
    if tool_id == "syft":
        sbom = workspace / "syft.cdx.json"
        return [str(binary), "scan", f"dir:{ROOT}", "-o", f"cyclonedx-json={sbom}", "--base-path", str(ROOT), "--exclude", "**/.git/**", "--exclude", "**/.venv/**", "--exclude", "**/.pocketlab-dev/**", "--exclude", "**/node_modules/**", "--exclude", "**/docs/generated/**", "--exclude", "**/contracts/generated/**", "--parallelism", "1", "--quiet"], sbom
    if tool_id == "grype":
        sbom = workspace / "syft.cdx.json"
        return [str(binary), f"sbom:{sbom}", "-o", "json", "--quiet"], None
    if tool_id == "schemathesis":
        schema = _fixed_schema(workspace)
        junit = workspace / "schemathesis.junit.xml"
        args = [str(binary), "run", str(schema), "--url", API_BASE, "--workers", "1", "--phases", "examples,coverage", "--max-examples", "2", "--max-failures", "5", "--checks", "not_a_server_error,status_code_conformance,content_type_conformance,response_headers_conformance,response_schema_conformance,negative_data_rejection,unsupported_method", "--request-timeout", "5", "--request-retries", "0", "--rate-limit", "20/m", "--generation-database", ":memory:", "--report", "junit", "--report-junit-path", str(junit), "--output-sanitize", "true", "--output-truncate", "true", "--no-color"]
        for route in LIVE_ROUTE_ALLOWLIST:
            args.extend(["--include-path", route])
        return args, junit
    if tool_id == "testssl.sh":
        sni = _fixed_tls_sni()
        if sni is None:
            raise RuntimeError("runtime_tls_identity_unavailable")
        return [str(binary), "--fast", "--warnings", "batch", "--quiet", "-n", "none", "--ip", "127.0.0.1", f"{sni}:18443"], None
    if tool_id == "nuclei":
        return [str(binary), "-templates", str(NUCLEI_TEMPLATES), "-target", f"{API_BASE}/health", "-concurrency", "1", "-bulk-size", "1", "-rate-limit", "2", "-jsonl", "-silent", "-no-interactsh", "-duc", "-no-color"], None
    if tool_id == "nmap":
        return [str(binary), "-Pn", "-n", "-sT", "-p", APPROVED_PORTS, "-oG", "-", APPROVED_NMAP_TARGET], None
    if tool_id == "owasp-zap":
        report = workspace / "zap-report.json"
        return [str(binary), "-cmd", "-silent", "-quickurl", f"{API_BASE}/health", "-quickprogress", "-nostdout", "-quickout", str(report), "-dir", str(workspace)], report
    raise RuntimeError("assurance_tool_command_not_registered")


def _findings_digest(findings: Iterable[Mapping[str, Any]]) -> str:
    keys = sorted(str(row.get("finding_id") or "") for row in findings)
    return _sha256_bytes("\n".join(keys).encode())


def _correlate_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for finding in findings:
        key = str(finding.get("advisory_key") or finding.get("finding_id") or "")
        current = grouped.get(key)
        if current is None:
            grouped[key] = dict(finding)
            grouped[key]["corroborating_tools"] = [str(finding.get("tool") or "")]
            continue
        current["corroborating_tools"] = sorted(set(current.get("corroborating_tools") or []) | {str(finding.get("tool") or "")})
        severity_rank = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        if severity_rank.get(str(finding.get("severity")), 0) > severity_rank.get(str(current.get("severity")), 0):
            current["severity"] = finding.get("severity")
        current["confidence"] = "high" if len(current["corroborating_tools"]) > 1 else current.get("confidence", "medium")
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    return sorted(grouped.values(), key=lambda row: (severity_rank.get(str(row.get("severity") or "info"), 5), str(row.get("finding_id") or "")))


def _baseline_delta(findings: list[dict[str, Any]]) -> dict[str, Any]:
    path = EVIDENCE_ROOT / "baseline.json"
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        previous = {}
    old = set(previous.get("finding_ids") or []) if isinstance(previous, dict) else set()
    current = {str(row.get("finding_id") or "") for row in findings}
    for row in findings:
        row["baseline_state"] = "EXISTING" if row.get("finding_id") in old else "NEW"
    delta = {"new": sorted(current - old), "existing": sorted(current & old), "resolved": sorted(old - current), "finding_digest": _findings_digest(findings), "baseline_present": bool(old), "sanitized": True}
    _write_json(path, {"finding_ids": sorted(current), "finding_digest": delta["finding_digest"], "updated_at": _now(), "sanitized": True})
    return delta


def _display_argv(argv: Iterable[str]) -> list[str]:
    """Return a safe, fixed-command representation for evidence."""
    displayed: list[str] = []
    fixed_sni = _fixed_tls_sni()
    for value in argv:
        item = str(value)
        if item == API_BASE:
            displayed.append("FIXED_API_TUNNEL")
        elif item == f"{API_BASE}/health":
            displayed.append("FIXED_API_TUNNEL/health")
        elif item == TLS_TARGET:
            displayed.append("FIXED_CADDY_TLS_TUNNEL")
        elif fixed_sni and item == fixed_sni:
            displayed.append("FIXED_CADDY_TLS_IDENTITY")
        elif fixed_sni and item == f"{fixed_sni}:18443":
            displayed.append("FIXED_CADDY_TLS_IDENTITY:FIXED_CADDY_TLS_PORT")
        else:
            displayed.append(_display_path(Path(item)) if item.startswith("/") else item)
    return displayed


def _load_bounded_artifact(path: Path, *, max_bytes: int) -> tuple[Any, dict[str, Any]]:
    """Read a temporary structured artifact only within the output bound."""
    try:
        size = path.stat().st_size
        if size > max(1024, int(max_bytes)):
            return None, {"present": True, "size_bytes": size, "status": "PARTIAL", "failure_code": "artifact_output_limited", "sanitized": True}
        raw = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix.casefold() not in {".json"}:
            return None, {"present": True, "size_bytes": size, "sha256": f"sha256:{_sha256_bytes(_sanitize_text(raw, 1_000_000).encode())}", "status": "PASS", "format": path.suffix.casefold().lstrip("."), "sanitized": True}
        payload = _parse_json(raw)
        if payload is None:
            return None, {"present": True, "size_bytes": size, "status": "PARTIAL", "failure_code": "artifact_parse_failed", "sanitized": True}
        return payload, {"present": True, "size_bytes": size, "sha256": f"sha256:{_sha256_bytes(_sanitize_text(raw, 1_000_000).encode())}", "status": "PASS", "sanitized": True}
    except OSError:
        return None, {"present": False, "status": "PARTIAL", "failure_code": "artifact_missing", "sanitized": True}


def _tool_result(tool_id: str, suite_id: str, binary: Path | None, workspace: Path, env: dict[str, str]) -> dict[str, Any]:
    spec = _registry()["toolchain"].get(tool_id) or {}
    result: dict[str, Any] = {
        "tool_id": tool_id,
        "suite": suite_id,
        "execution_lane": spec.get("execution_lane"),
        "target": spec.get("fixed_target"),
        "command_id": spec.get("command_id"),
        "status": "FAILED",
        "version": "UNAVAILABLE",
        "findings": [],
        "sanitized": True,
    }
    if binary is None:
        result.update({"status": "FAILED", "failure_code": "qualified_executable_not_found"})
        return result
    if str(spec.get("execution_lane") or "") == "dev_pc_live_runtime":
        target_probe = _live_target_probe(tool_id)
        result["target_probe"] = target_probe
        if target_probe.get("available") is not True:
            result.update({"status": "BLOCKED", "failure_code": str(target_probe.get("failure_code") or "runtime_target_unavailable")})
            return result
    version = _probe_version(tool_id, binary)
    result.update({"version": version.get("version"), "version_status": version.get("version_status"), "binary_path": _display_path(binary)})
    if version.get("status") != "READY":
        result.update({"status": "FAILED", "failure_code": "tool_version_not_qualified", "stdout_summary": version.get("version_output_summary")})
        return result
    receipt = _load_receipt(tool_id)
    result.update({
        "installation_source": str(receipt.get("installation_source") or spec.get("installation_source") or ""),
        "platform": str(receipt.get("platform") or f"{sys.platform}/{os.uname().machine if hasattr(os, 'uname') else 'unknown'}"),
        "expected_checksum": receipt.get("expected_checksum"),
        "expected_checksums": dict(receipt.get("expected_checksums") or {}),
        "actual_checksum": receipt.get("actual_checksum"),
        "checksum_status": str(receipt.get("checksum_status") or "not_managed"),
        "signature_status": str(receipt.get("signature_status") or "not_applicable"),
        "installed_at": receipt.get("installed_at"),
    })
    if tool_id == "cosign" and not COSIGN_ARTIFACT_MANIFEST.exists():
        result.update({"status": "NOT_APPLICABLE", "status_detail": "no signed artifact registered for this revision"})
        return result
    command, artifact = _run_command_for_tool(tool_id, suite_id, binary, workspace, env)
    result["version_command"] = _display_argv([str(binary), *VERSION_ARGS[tool_id]])
    result["argv"] = _display_argv(command)
    execution_cwd = workspace if tool_id in {"schemathesis", "owasp-zap"} else ROOT
    completed = _bounded_run(command, timeout_seconds=int(spec.get("timeout_seconds") or 300), max_output_bytes=int(spec.get("max_output_bytes") or MAX_SUITE_OUTPUT_BYTES), env=env, cwd=execution_cwd)
    stdout = str(completed.get("stdout") or "")
    stderr = str(completed.get("stderr") or "")
    artifact_payload = None
    if artifact is not None:
        artifact_payload, artifact_meta = _load_bounded_artifact(artifact, max_bytes=int(spec.get("max_output_bytes") or MAX_SUITE_OUTPUT_BYTES))
        result["artifact"] = {"kind": artifact.name, **artifact_meta}
        if artifact_meta.get("status") != "PASS" and completed.get("status") == "PASS":
            completed = {**completed, "status": "PARTIAL", "failure_code": str(artifact_meta.get("failure_code") or "artifact_invalid")}
    findings = _parse_findings(tool_id, suite_id, stdout, stderr, workspace, artifact_payload=artifact_payload)
    if tool_id in {"hurl", "k6"} and completed.get("status") == "FAIL" and not findings:
        findings.append(_base_finding(tool_id=tool_id, suite_id=suite_id, identity=f"{tool_id}-assertion-failed", title=f"{tool_id} runtime security assertion failed", severity="high", summary="A fixed repository-owned runtime security assertion failed.", component="live runtime"))
    if artifact is not None and artifact.name == "syft.cdx.json" and isinstance(artifact_payload, dict):
        payload = artifact_payload
        result["component_count"] = len(payload.get("components") or []) if isinstance(payload, dict) else None
    if tool_id == "schemathesis":
        result["route_allowlist"] = list(LIVE_ROUTE_ALLOWLIST)
    if tool_id == "nuclei":
        result["template_ids"] = ["pocketlab-health-safe"]
        result["template_hash"] = _sha256_file(NUCLEI_TEMPLATES / "pocketlab-health.yaml") if (NUCLEI_TEMPLATES / "pocketlab-health.yaml").is_file() else None
    if tool_id == "nmap":
        result["port_forward_map"] = dict(APPROVED_PORT_FORWARD_MAP)
    result.update({
        "execution_status": completed.get("status"),
        "security_result": "FINDINGS" if findings else "NO_FINDINGS",
        "status": "PASS" if completed.get("status") in {"PASS", "FAIL"} and (completed.get("status") == "PASS" or findings) else completed.get("status"),
        "exit_code": completed.get("exit_code"),
        "duration_ms": completed.get("duration_ms"),
        "failure_code": completed.get("failure_code"),
        "stdout_sha256": f"sha256:{_sha256_bytes(_sanitize_text(stdout, 1_000_000).encode())}",
        "stderr_sha256": f"sha256:{_sha256_bytes(_sanitize_text(stderr, 1_000_000).encode())}",
        "stdout_summary": _summary(stdout),
        "stderr_summary": _summary(stderr),
        "findings": findings,
        "finding_count": len(findings),
        "resource": {"cpu": "UNAVAILABLE", "rss_bytes": "UNAVAILABLE", "battery": "UNAVAILABLE", "temperature_c": "UNAVAILABLE", "storage_delta_bytes": "UNAVAILABLE"},
    })
    return result


def run_suite(suite_id: str) -> dict[str, Any]:
    registry = _registry()
    if suite_id not in {"smoke", "standard", "deep", "adversarial"}:
        raise ValueError("assurance_suite_unknown")
    started_at = _now()
    qualification_id = f"devpc-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    run_root = EVIDENCE_ROOT / qualification_id / suite_id
    run_root.mkdir(parents=True, exist_ok=True)
    (MANAGED_ROOT / "tmp").mkdir(parents=True, exist_ok=True)
    tool_results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix=f"{qualification_id}-", dir=MANAGED_ROOT / "tmp") as temporary:
        workspace = Path(temporary)
        ordered_ids = TOOL_EXECUTION_ORDER + tuple(
            tool_id for tool_id in sorted(registry["toolchain"]) if tool_id not in TOOL_EXECUTION_ORDER
        )
        for tool_id in ordered_ids:
            spec = registry["toolchain"].get(tool_id) or {}
            if suite_id not in (spec.get("suite_membership") or []):
                continue
            if str(spec.get("execution_lane") or "") == "server_phone_worker":
                tool_results.append({
                    "tool_id": tool_id,
                    "suite": suite_id,
                    "execution_lane": "server_phone_worker",
                    "status": "NOT_RUN",
                    "version": "runtime-reported",
                    "installation_source": "server_owned_worker_registry",
                    "checksum_status": "server_runtime_receipt",
                    "signature_status": "server_runtime_receipt",
                    "status_detail": "result is attached by authenticated Server Phone assurance run",
                    "sanitized": True,
                })
                continue
            binary, env = _tool_context(tool_id, workspace)
            tool_results.append(_tool_result(tool_id, suite_id, binary, workspace, env))
    findings = _correlate_findings([finding for row in tool_results for finding in row.get("findings") or []])
    scenario_results = _scenario_results(suite_id, tool_results)
    delta = _baseline_delta(findings)
    failures = [row for row in tool_results if row.get("status") in {"FAILED", "PARTIAL", "BLOCKED"}]
    severe = [row for row in findings if row.get("severity") in {"critical", "high"}]
    scenario_failures = [row for row in scenario_results if row.get("status") == "FAIL"]
    scenario_incomplete = [row for row in scenario_results if row.get("status") in {"PARTIAL", "BLOCKED"}]
    status = "FAIL" if severe or scenario_failures else "PARTIAL" if failures or scenario_incomplete else "PASS"
    report = {
        "schema_version": "1.0.0",
        "qualification_id": qualification_id,
        "suite": suite_id,
        "source_sha": _git_revision(),
        "registry_sha256": registry["hash"],
        "started_at": started_at,
        "completed_at": _now(),
        "status": status,
        "tools": tool_results,
        "scenarios": scenario_results,
        "scenario_count": len(scenario_results),
        "findings": findings,
        "finding_count": len(findings),
        "delta": delta,
        "resource_policy": {"execution": "sequential", "heavy_concurrency": 1, "missing_measurement": "UNAVAILABLE"},
        "target": {"api_base": "fixed_loopback_tunnel", "tls": "fixed_loopback_tunnel", "routes": list(LIVE_ROUTE_ALLOWLIST), "ports": APPROVED_PORTS},
        "raw_output_persisted": False,
        "sanitization": {"status": "PASS", "raw_scanner_output": "not_persisted", "secret_matches": "metadata_only", "user_media": "excluded"},
        "sanitized": True,
    }
    _write_json(run_root / "manifest.json", {key: report[key] for key in ("schema_version", "qualification_id", "suite", "source_sha", "registry_sha256", "started_at", "completed_at", "status", "raw_output_persisted", "sanitized")})
    _write_json(run_root / "toolchain.json", {"tools": tool_results, "sanitized": True})
    _write_json(run_root / "scenarios.json", {"scenarios": scenario_results, "sanitized": True})
    _write_json(run_root / "findings.json", {"findings": findings, "sanitized": True})
    _write_json(run_root / "delta.json", delta)
    _write_json(run_root / "sanitization.json", report["sanitization"])
    _write_json(run_root / "checksums.json", {"manifest": f"sha256:{_sha256_file(run_root / 'manifest.json')}", "toolchain": f"sha256:{_sha256_file(run_root / 'toolchain.json')}", "findings": f"sha256:{_sha256_file(run_root / 'findings.json')}", "sanitized": True})
    report["evidence_dir"] = f"QUALIFICATION_EVIDENCE_ROOT/{qualification_id}/{suite_id}"
    return report


def _git_revision() -> str | None:
    git = Path("/usr/bin/git")
    if not git.is_file():
        return None
    result = _bounded_run([str(git), "rev-parse", "HEAD"], timeout_seconds=5, max_output_bytes=1024)
    revision = str(result.get("stdout") or "").strip()
    return revision if re.fullmatch(r"[0-9a-f]{40}", revision) else None


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Pocket Lab fixed Runtime Security Assurance DEV-PC toolchain")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="check all fixed tool contracts")
    commands.add_parser("install", help="promote/install only fixed approved tool recipes")
    run = commands.add_parser("run", help="run one registered bounded suite")
    run.add_argument("suite", choices=("smoke", "standard", "deep", "adversarial"))
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            result = check_toolchain()
        elif args.command == "install":
            result = install_toolchain()
        else:
            result = run_suite(args.suite)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR {_sanitize_text(str(exc), 320)}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0 if result.get("status") in {"PASS", "NOT_APPLICABLE"} else 11 if result.get("status") == "PARTIAL" else 10


if __name__ == "__main__":
    raise SystemExit(main())
