#!/usr/bin/env python3
"""Install/check pinned Documentation Platform security tools on WSL2/CI.

Safety properties:
- refuses Android/Termux;
- installs under .pocketlab-dev by default, never system-wide;
- never upgrades a working mismatched tool unless --update is explicit;
- validates GitHub release downloads with SHA-256 from official release metadata/checksum assets;
- validates the top-level PyPI artifact digest for Python-package installs;
- supports a cache-only offline mode after an artifact has been verified once;
- never prints GITHUB_TOKEN or other credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
import venv
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
META = ROOT / "contracts/metadata/documentation-security-tools.json"
DEFAULT_INSTALL_ROOT = Path(os.environ.get("POCKETLAB_DOC_SECURITY_TOOL_ROOT", str(ROOT / ".pocketlab-dev/tools/documentation-security")))
DEFAULT_CACHE_ROOT = Path(os.environ.get("POCKETLAB_DOC_SECURITY_CACHE_ROOT", str(Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "pocket-lab-lite/documentation-security")))


def fail(message: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(code)





def disk_temp_root(cache_root: Path) -> Path:
    """Return a disk-backed temp root for heavyweight documentation tooling.

    WSL commonly mounts /tmp as a small tmpfs. Heavy tools such as ScanCode can
    exhaust that RAM-backed filesystem even when the Linux root filesystem has
    ample capacity. Keep transient download/extraction work under the Pocket Lab
    cache filesystem by default, with an explicit environment override.
    """
    configured = os.environ.get("POCKETLAB_DOC_SECURITY_TMP_ROOT")
    common = os.environ.get("POCKETLAB_DEV_TMPDIR")

    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        root = candidate.resolve()
    elif common:
        candidate = Path(common).expanduser()
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        root = (candidate / "security-tools").resolve()
    else:
        root = (ROOT / ".pocketlab-dev" / "tmp" / "security-tools").resolve()

    root.mkdir(parents=True, exist_ok=True)
    return root


def tool_subprocess_env(cache_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    tmp_root = disk_temp_root(cache_root)
    # pip/tempfile honour these variables. Set all three for cross-tool
    # consistency without mutating the parent shell environment.
    for key in ("TMPDIR", "TMP", "TEMP"):
        env[key] = str(tmp_root)
    return env


def ensure_temp_headroom(cache_root: Path, tool_id: str) -> None:
    tmp_root = disk_temp_root(cache_root)
    # ScanCode's resolved wheelhouse plus pip's transient/unpacked files are
    # materially larger than its top-level wheel. Fail early with a useful
    # diagnostic rather than an opaque ENOSPC traceback. Other PyPI tools use a
    # smaller but still conservative floor. Both are overrideable for CI.
    default_required = 2 * 1024**3 if tool_id == "scancode" else 1 * 1024**3
    required = int(os.environ.get("POCKETLAB_DOC_SECURITY_MIN_TMP_BYTES", str(default_required)))
    free = shutil.disk_usage(tmp_root).free
    if free < required:
        fail(
            f"{tool_id}: insufficient disk-backed temp space at {tmp_root}: "
            f"need at least {required // (1024**2)} MiB, have {free // (1024**2)} MiB. "
            "Set POCKETLAB_DOC_SECURITY_TMP_ROOT to a filesystem with more free space.",
            5,
        )


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{dst.name}.", dir=dst.parent)
    os.close(fd)
    try:
        shutil.copy2(src, tmp)
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def is_termux() -> bool:
    prefix = os.environ.get("PREFIX", "")
    return bool(os.environ.get("TERMUX_VERSION")) or "com.termux" in prefix or platform.system().lower() == "android"


def arch_id() -> str:
    value = platform.machine().lower()
    if value in {"x86_64", "amd64"}:
        return "amd64"
    if value in {"aarch64", "arm64"}:
        return "arm64"
    fail(f"unsupported developer architecture: {value}", 3)


def load_meta() -> dict[str, Any]:
    data = json.loads(META.read_text(encoding="utf-8"))
    if data.get("schema_version") != "2.0.0":
        fail("documentation security tool metadata schema must be 2.0.0")
    return data


def request_headers(url: str) -> dict[str, str]:
    headers = {"User-Agent": "Pocket-Lab-Lite-documentation-security-tools/2"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and (url.startswith("https://api.github.com/") or url.startswith("https://github.com/")):
        headers["Authorization"] = f"Bearer {token}"
    return headers


def request(url: str, *, offline: bool = False) -> bytes:
    if offline:
        fail(f"offline mode cannot fetch {url}", 4)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=request_headers(url)), timeout=45) as response:
            return response.read()
    except urllib.error.URLError as exc:
        fail(f"download failed safely for {url}: {type(exc).__name__}", 4)


def download_file(url: str, target: Path, *, offline: bool = False) -> None:
    """Download to a cache file with safe best-effort HTTP Range resume."""
    if offline:
        fail(f"offline mode cannot fetch {url}", 4)
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    start = partial.stat().st_size if partial.exists() else 0
    headers = request_headers(url)
    if start:
        headers["Range"] = f"bytes={start}-"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=45) as response:
            status = getattr(response, "status", None) or response.getcode()
            append = bool(start and status == 206)
            if start and not append:
                start = 0
            mode = "ab" if append else "wb"
            with partial.open(mode) as fh:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)
                fh.flush()
                os.fsync(fh.fileno())
        os.replace(partial, target)
    except (urllib.error.URLError, OSError) as exc:
        # Keep the partial cache for a later explicit retry; never promote it as verified.
        fail(f"download failed safely for {url}: {type(exc).__name__}", 4)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_extract_tar(archive: Path, dest: Path) -> None:
    with tarfile.open(archive) as tf:
        base = dest.resolve()
        for member in tf.getmembers():
            target = (dest / member.name).resolve()
            if base not in target.parents and target != base:
                fail(f"archive path traversal rejected: {member.name}")
        if sys.version_info >= (3, 12):
            tf.extractall(dest, filter="data")
        else:
            tf.extractall(dest)


def safe_extract_zip(archive: Path, dest: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        base = dest.resolve()
        for member in zf.infolist():
            target = (dest / member.filename).resolve()
            if base not in target.parents and target != base:
                fail(f"archive path traversal rejected: {member.filename}")
        zf.extractall(dest)


def run_capture(argv: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        proc = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""
    return proc.returncode, ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()


def local_binary(tool: dict[str, Any], install_root: Path) -> Path | None:
    local = install_root / "bin" / str(tool["binary"])
    if local.is_file() and os.access(local, os.X_OK):
        return local
    return None


def locate_binary(tool: dict[str, Any], install_root: Path) -> Path | None:
    local = local_binary(tool, install_root)
    if local is not None:
        return local
    found = shutil.which(str(tool["binary"]))
    return Path(found) if found else None


def version_matches(tool: dict[str, Any], binary: Path) -> tuple[bool, str]:
    command = list(tool.get("validation_command") or [])
    if not command:
        return True, "validation not required"
    command[0] = str(binary)
    code, output = run_capture(command)
    first = output.splitlines()[0] if output else "no version output"
    expected = str(tool["version"])
    return code == 0 and expected in output, first[:180]


def github_release(tool: dict[str, Any], cache_root: Path, arch: str, offline: bool) -> tuple[Path, str]:
    spec = tool["install"]
    supported = spec.get("supported_arches")
    if supported and arch not in supported:
        raise RuntimeError(f"not-applicable:{spec.get('not_applicable_note', 'unsupported architecture')}")
    pattern = (spec.get("asset_regex") or {}).get(arch)
    if not pattern:
        raise RuntimeError(f"not-applicable:no reviewed {arch} asset")
    cache_dir = cache_root / tool["id"] / tool["version"] / arch
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = cache_dir / "verified.json"
    if offline and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifact = cache_dir / manifest["asset_name"]
        if artifact.exists() and sha256(artifact) == manifest["sha256"]:
            return artifact, manifest["sha256"]
        fail(f"offline cache integrity check failed for {tool['id']}", 4)
    if offline:
        fail(f"no verified offline cache for {tool['id']} {tool['version']} {arch}", 4)

    api = f"https://api.github.com/repos/{spec['repository']}/releases/tags/{spec['tag']}"
    release = json.loads(request(api).decode("utf-8"))
    assets = release.get("assets") or []
    matches = [a for a in assets if re.fullmatch(pattern, str(a.get("name", "")))]
    if len(matches) != 1:
        fail(f"{tool['id']}: expected exactly one release asset matching {pattern!r}; found {len(matches)}", 5)
    asset = matches[0]
    asset_name = asset["name"]
    artifact = cache_dir / asset_name
    download_file(asset["browser_download_url"], artifact)

    expected = ""
    digest = str(asset.get("digest") or "")
    if digest.startswith("sha256:"):
        expected = digest.split(":", 1)[1].lower()
    if not expected:
        checksum_assets = [a for a in assets if re.search(r"(?i)(sha256|checksums?)", str(a.get("name", "")))]
        for checksum_asset in checksum_assets:
            text = request(checksum_asset["browser_download_url"]).decode("utf-8", errors="replace")
            for line in text.splitlines():
                stripped = line.strip()
                m = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+?)\s*$", stripped)
                if m and Path(m.group(2)).name == asset_name:
                    expected = m.group(1).lower()
                    break
                # Some projects publish one checksum per sidecar file. Accept a
                # bare SHA-256 only when that checksum asset is clearly bound to
                # the selected release artifact by name.
                bare = re.fullmatch(r"([0-9a-fA-F]{64})", stripped)
                checksum_name = str(checksum_asset.get("name", ""))
                if bare and checksum_name.startswith(asset_name):
                    expected = bare.group(1).lower()
                    break
            if expected:
                break
    if not expected:
        artifact.unlink(missing_ok=True)
        fail(f"{tool['id']}: official release supplied no usable SHA-256 digest/checksum for {asset_name}", 5)
    observed = sha256(artifact)
    if observed != expected:
        artifact.unlink(missing_ok=True)
        fail(f"{tool['id']}: SHA-256 mismatch for {asset_name}", 5)
    atomic_write_text(manifest_path, json.dumps({"asset_name": asset_name, "sha256": expected, "release_tag": spec["tag"]}, sort_keys=True, indent=2) + "\n")
    return artifact, expected


def install_github(tool: dict[str, Any], install_root: Path, cache_root: Path, arch: str, offline: bool) -> Path:
    artifact, digest = github_release(tool, cache_root, arch, offline)
    spec = tool["install"]
    target_bin = install_root / "bin" / tool["binary"]
    target_bin.parent.mkdir(parents=True, exist_ok=True)
    archive_type = spec.get("archive")
    if archive_type == "binary":
        atomic_copy(artifact, target_bin)
    else:
        with tempfile.TemporaryDirectory(prefix=f"pocketlab-{tool['id']}-", dir=disk_temp_root(cache_root)) as tmp:
            tmpdir = Path(tmp)
            if archive_type in {"tar.gz", "tar.xz"}:
                safe_extract_tar(artifact, tmpdir)
            elif archive_type == "zip":
                safe_extract_zip(artifact, tmpdir)
            else:
                fail(f"unsupported archive type for {tool['id']}: {archive_type}")
            regex = re.compile(spec.get("binary_path_regex") or f"(^|/){re.escape(tool['binary'])}$")
            candidates = [p for p in tmpdir.rglob("*") if p.is_file() and regex.search(p.as_posix())]
            if len(candidates) != 1:
                fail(f"{tool['id']}: expected one extracted binary, found {len(candidates)}")
            atomic_copy(candidates[0], target_bin)
    target_bin.chmod(target_bin.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    receipt = install_root / "receipts" / f"{tool['id']}.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        receipt,
        json.dumps(
            {"tool": tool["id"], "version": tool["version"], "sha256": digest, "source": spec["repository"], "architecture": arch},
            sort_keys=True,
            indent=2,
        ) + "\n",
    )
    return target_bin


def _wheelhouse_manifest(wheelhouse: Path) -> list[dict[str, str]]:
    return [{"name": p.name, "sha256": sha256(p)} for p in sorted(wheelhouse.iterdir()) if p.is_file()]


def _verify_wheelhouse(wheelhouse: Path, expected: list[dict[str, str]]) -> bool:
    if not wheelhouse.is_dir() or not expected:
        return False
    actual = {p.name: sha256(p) for p in wheelhouse.iterdir() if p.is_file()}
    return all(actual.get(row.get("name", "")) == row.get("sha256") for row in expected)


def install_pypi(tool: dict[str, Any], install_root: Path, cache_root: Path, arch: str, offline: bool) -> Path:
    """Install a pinned PyPI tool from a content-verified local wheelhouse.

    Online runs resolve the pinned package once and cache every wheel/sdist with SHA-256.
    Offline runs install only from that previously verified wheelhouse, so an offline re-run
    never silently resolves new dependency versions from an index.
    """
    spec = tool["install"]
    supported = spec.get("supported_arches") or []
    if supported and arch not in supported:
        raise RuntimeError("not-applicable:unsupported architecture")
    package = spec["package"]
    version = spec["version"]
    cache_dir = cache_root / tool["id"] / version / arch
    wheelhouse = cache_dir / "wheelhouse"
    manifest_path = cache_dir / "verified.json"
    cache_dir.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}

    if offline:
        if not _verify_wheelhouse(wheelhouse, list(manifest.get("wheelhouse") or [])):
            fail(f"no verified offline PyPI wheelhouse for {tool['id']} {version} {arch}", 4)
    else:
        # Verify the pinned top-level release exists and record its official PyPI digest.
        payload = json.loads(request(f"https://pypi.org/pypi/{package}/{version}/json").decode("utf-8"))
        published = payload.get("urls", [])
        if not published:
            fail(f"{tool['id']}: PyPI returned no files for pinned {package}=={version}", 5)
        top_level = sorted(
            [
                {"filename": str(x.get("filename")), "sha256": str((x.get("digests") or {}).get("sha256") or "")}
                for x in published
                if x.get("filename") and (x.get("digests") or {}).get("sha256")
            ],
            key=lambda x: x["filename"],
        )
        if not top_level:
            fail(f"{tool['id']}: PyPI supplied no SHA-256 metadata for pinned release", 5)

        # Resolve/download dependencies into a temporary wheelhouse and atomically replace the cache.
        candidate = cache_dir / f".wheelhouse-{os.getpid()}"
        if candidate.exists():
            shutil.rmtree(candidate)
        candidate.mkdir(parents=True, exist_ok=True)
        ensure_temp_headroom(cache_root, tool["id"])
        with tempfile.TemporaryDirectory(prefix=f"pocketlab-{tool['id']}-download-", dir=disk_temp_root(cache_root)) as tmp:
            bootstrap = Path(tmp) / "venv"
            venv.EnvBuilder(with_pip=True, clear=True).create(bootstrap)
            pip = bootstrap / "bin" / "pip"
            try:
                subprocess.run(
                    [str(pip), "download", "--disable-pip-version-check", "--no-input", "--dest", str(candidate), f"{package}=={version}"],
                    check=True,
                    cwd=ROOT,
                    env=tool_subprocess_env(cache_root),
                )
            except subprocess.CalledProcessError:
                shutil.rmtree(candidate, ignore_errors=True)
                fail(f"{tool['id']}: failed to build the pinned dependency wheelhouse", 5)
        resolved = _wheelhouse_manifest(candidate)
        if not resolved:
            shutil.rmtree(candidate, ignore_errors=True)
            fail(f"{tool['id']}: dependency wheelhouse is empty", 5)
        if wheelhouse.exists():
            shutil.rmtree(wheelhouse)
        os.replace(candidate, wheelhouse)
        manifest = {
            "package": package,
            "version": version,
            "architecture": arch,
            "pypi_release_files": top_level,
            "wheelhouse": resolved,
            "integrity": "every cached dependency artifact is SHA-256 recorded; installation uses --no-index",
        }
        atomic_write_text(manifest_path, json.dumps(manifest, sort_keys=True, indent=2) + "\n")

    if not _verify_wheelhouse(wheelhouse, list(manifest.get("wheelhouse") or [])):
        fail(f"{tool['id']}: cached PyPI wheelhouse integrity verification failed", 5)

    venv_dir = install_root / "venvs" / tool["id"]
    venv_dir.parent.mkdir(parents=True, exist_ok=True)

    # Python virtual environments are intentionally NOT built at a temporary
    # path and renamed into place. Console scripts created by pip contain an
    # absolute shebang pointing at the environment interpreter; moving the
    # populated venv leaves commands such as semgrep/scancode pointing at the
    # deleted staging interpreter. Rebuild directly at the stable final path.
    # This also repairs environments created by the older candidate-rename
    # implementation. The wheelhouse has already been integrity-verified, so a
    # failed rebuild remains fail-closed and can be retried without re-download.
    if venv_dir.exists() or venv_dir.is_symlink():
        if venv_dir.is_symlink() or venv_dir.is_file():
            venv_dir.unlink()
        else:
            shutil.rmtree(venv_dir)
    venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    pip = venv_dir / "bin" / "pip"
    try:
        subprocess.run(
            [str(pip), "install", "--disable-pip-version-check", "--no-input", "--no-index", "--find-links", str(wheelhouse), f"{package}=={version}"],
            check=True,
            cwd=ROOT,
            env=tool_subprocess_env(cache_root),
        )
    except subprocess.CalledProcessError:
        fail(f"{tool['id']}: verified wheelhouse could not install the pinned package", 5)

    source_binary = venv_dir / "bin" / tool["binary"]
    if not source_binary.exists():
        fail(f"{tool['id']}: installed package did not provide {tool['binary']}")

    # Validate the command before publishing/updating the stable bin link. This
    # catches broken shebangs and package/runtime failures immediately. Capture
    # both stdout and stderr through version_matches/run_capture.
    version_ok, version_detail = version_matches(tool, source_binary)
    if not version_ok:
        fail(f"{tool['id']}: install completed but version validation failed: {version_detail}", 5)
    target_bin = install_root / "bin" / tool["binary"]
    target_bin.parent.mkdir(parents=True, exist_ok=True)
    tmp_link = target_bin.parent / f".{target_bin.name}.link-{os.getpid()}"
    tmp_link.unlink(missing_ok=True)
    tmp_link.symlink_to(source_binary)
    os.replace(tmp_link, target_bin)
    receipt = install_root / "receipts" / f"{tool['id']}.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        receipt,
        json.dumps(
            {
                "tool": tool["id"],
                "version": version,
                "sha256": sha_bytes(json.dumps(manifest.get("wheelhouse") or [], sort_keys=True).encode()),
                "source": "PyPI pinned release + verified local dependency wheelhouse",
                "architecture": arch,
                "dependency_integrity": "offline-capable after first verified download; install uses --no-index",
            },
            sort_keys=True,
            indent=2,
        )
        + "\n",
    )
    return target_bin


def smoke_test(tool: dict[str, Any], binary: Path) -> tuple[bool, str]:
    """Run a bounded post-install command-shape check without scanning the repository."""
    smoke = list(tool.get("smoke_command") or [])
    if not smoke:
        return True, "version-validation-only"
    smoke[0] = str(binary)
    code, output = run_capture(smoke, timeout=30)
    return code == 0, (output.splitlines()[0] if output else f"exit={code}")[:180]


def install_docker(tool: dict[str, Any], arch: str, include_optional: bool) -> str:
    if not include_optional:
        return "SKIP optional"
    docker = shutil.which("docker")
    if not docker:
        fail("Threat Dragon requested but Docker is unavailable")
    image = tool["install"]["images"].get(arch)
    if not image:
        return "NOT_APPLICABLE unsupported architecture"
    subprocess.run([docker, "pull", image], check=True, cwd=ROOT)
    inspect = subprocess.check_output([docker, "image", "inspect", image, "--format", "{{index .RepoDigests 0}}"], text=True).strip()
    if "@sha256:" not in inspect:
        fail("Threat Dragon image pull produced no immutable repo digest")
    return f"OK {image} {inspect.split('@sha256:', 1)[1][:12]}…"


def check_tool(tool: dict[str, Any], install_root: Path, arch: str) -> tuple[str, bool]:
    spec = tool.get("install") or {}
    platform_label = f"{platform.system()}/{arch}"
    supported = spec.get("supported_arches")
    if supported and arch not in supported:
        return f"NOT_APPLICABLE tool={tool['id']} expected={tool['version']} platform={platform_label} status=not-applicable reason={spec.get('not_applicable_note', 'unsupported architecture')}", True
    if tool["binary"] == "optional":
        return f"OPTIONAL tool={tool['id']} expected={tool['version']} platform={platform_label} status=external-optional", True
    if spec.get("method") == "docker-image":
        return f"OPTIONAL tool={tool['id']} expected={tool['version']} platform={platform_label} status=review-ui-not-required", True
    binary = locate_binary(tool, install_root)
    if not binary:
        return f"MISSING tool={tool['id']} expected={tool['version']} path=unavailable checksum=unavailable platform={platform_label} status=missing", not bool(tool.get("required"))
    good, detail = version_matches(tool, binary)
    if good:
        smoke_ok, smoke_detail = smoke_test(tool, binary)
        if not smoke_ok:
            good = False
            detail = f"{detail}; functional-self-test={smoke_detail}"
    receipt_path = install_root / "receipts" / f"{tool['id']}.json"
    local = local_binary(tool, install_root)
    checksum = "external-system-copy-not-managed-by-pocket-lab"
    if local is not None:
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            receipt = {}
        if receipt.get("tool") == tool["id"] and receipt.get("version") == tool["version"] and receipt.get("sha256"):
            checksum = f"verified-download-sha256:{receipt['sha256']}"
        else:
            checksum = "missing-or-invalid-install-receipt"
            good = False
    state = "verified" if good else "version-or-integrity-mismatch"
    prefix = "OK" if good else "VERSION_MISMATCH"
    return f"{prefix} tool={tool['id']} expected={tool['version']} actual={detail} path={binary} checksum={checksum} platform={platform_label} status={state}", good


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["plan", "check", "install"])
    parser.add_argument("--install-root", default=str(DEFAULT_INSTALL_ROOT))
    parser.add_argument("--cache-root", default=str(DEFAULT_CACHE_ROOT))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--update", action="store_true", help="Explicitly replace mismatched installed versions")
    parser.add_argument("--include-optional", action="store_true")
    parser.add_argument("--only", action="append", default=[], help="Limit action to one or more tool ids; may be repeated")
    args = parser.parse_args()
    if is_termux():
        fail("heavy Documentation Platform tooling belongs on WSL2/CI; Termux remains lightweight", 3)
    install_root = Path(args.install_root).expanduser().resolve()
    cache_root = Path(args.cache_root).expanduser().resolve()
    arch = arch_id()
    meta = load_meta()
    selected = [x for x in meta["tools"] if x.get("required") or args.include_optional]
    if args.only:
        requested = {item.strip() for raw in args.only for item in raw.split(",") if item.strip()}
        known = {x["id"] for x in meta["tools"]}
        unknown = sorted(requested - known)
        if unknown:
            fail(f"unknown tool id(s): {', '.join(unknown)}", 2)
        selected = [x for x in meta["tools"] if x["id"] in requested]
        if not selected:
            fail("--only selected no tools", 2)

    if args.mode == "plan":
        print(f"Platform: {platform.system()} {arch}")
        print(f"Install root: {install_root}")
        print(f"Cache root: {cache_root}")
        print(f"Temp root: {disk_temp_root(cache_root)}")
        for tool in selected:
            method = (tool.get("install") or {}).get("method", "none")
            supported = (tool.get("install") or {}).get("supported_arches")
            state = "not-applicable" if supported and arch not in supported else "planned"
            print(f"{state.upper()} {tool['id']} {tool['version']} via {method}")
        return 0

    if args.mode == "check":
        ok = True
        for tool in selected:
            message, passed = check_tool(tool, install_root, arch)
            print(message)
            ok = ok and passed
        return 0 if ok else 1

    install_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)
    for tool in selected:
        spec = tool.get("install") or {}
        method = spec.get("method")
        supported = spec.get("supported_arches")
        if supported and arch not in supported:
            print(f"NOT_APPLICABLE {tool['id']}: {spec.get('not_applicable_note', 'unsupported architecture')}")
            continue
        if method in {"external-optional", None}:
            print(f"OPTIONAL {tool['id']}: no local install required")
            continue
        if method == "docker-image":
            print(install_docker(tool, arch, args.include_optional))
            continue
        current_local = local_binary(tool, install_root)
        if current_local:
            good, detail = version_matches(tool, current_local)
            if good:
                print(f"KEEP {tool['id']} {tool['version']}: repo-local pinned copy already working")
                continue

            # A same-version PyPI venv with a valid Pocket Lab receipt may be
            # rebuilt automatically. This is a repair, not an upgrade: it fixes
            # broken console-script shebangs created by the historical
            # candidate-venv rename implementation while preserving the pinned
            # version and verified wheelhouse. Other mismatches still require
            # the explicit --update safety gate.
            repair_same_pin = False
            if method == "pypi-venv":
                receipt_path = install_root / "receipts" / f"{tool['id']}.json"
                try:
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    receipt = {}
                repair_same_pin = (
                    receipt.get("tool") == tool["id"]
                    and receipt.get("version") == tool["version"]
                    and bool(receipt.get("sha256"))
                )
            if repair_same_pin:
                print(f"REPAIR {tool['id']} {tool['version']}: rebuilding the same pinned repo-local Python environment ({detail})")
            elif not args.update:
                fail(f"repo-local {tool['id']} exists but does not match pinned {tool['version']}; rerun with --update to replace only the repo-local copy. Observed: {detail}", 6)
        else:
            system = shutil.which(str(tool["binary"]))
            if system:
                good, detail = version_matches(tool, Path(system))
                if good:
                    print(f"KEEP {tool['id']} {tool['version']}: matching system copy already working at {system}")
                    continue
                print(f"PRESERVE {tool['id']}: system copy differs ({detail}); installing pinned isolated repo-local copy without modifying the system tool")
        if method == "github-release":
            installed = install_github(tool, install_root, cache_root, arch, args.offline)
        elif method == "pypi-venv":
            installed = install_pypi(tool, install_root, cache_root, arch, args.offline)
        else:
            fail(f"unknown install method for {tool['id']}: {method}")
        good, detail = version_matches(tool, installed)
        if not good:
            fail(f"{tool['id']} install completed but version validation failed: {detail}")
        smoke_ok, smoke_detail = smoke_test(tool, installed)
        if not smoke_ok:
            fail(f"{tool['id']} install completed but functional self-test failed: {smoke_detail}")
        print(f"INSTALLED {tool['id']} {tool['version']} -> {installed} ({smoke_detail})")
    print(f"Add to PATH for this shell: export PATH=\"{install_root / 'bin'}:$PATH\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
