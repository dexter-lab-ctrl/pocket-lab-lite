from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from contracts import utc_now_iso, slugify


@dataclass
class IngestResult:
    source: str
    ref: str
    path: str
    metadata: Dict[str, Any]


class SourceIngestor:
    def __init__(self, workspace: Path):
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def ingest(
        self, source: str, destination_name: Optional[str] = None
    ) -> Dict[str, Any]:
        source = (source or "").strip()
        destination_name = slugify(
            destination_name or source.split("://", 1)[-1].split("/", 1)[0] or "source"
        )
        dest = self.workspace / destination_name
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)

        meta: Dict[str, Any] = {
            "source": source,
            "ingested_at": utc_now_iso(),
            "destination": str(dest),
        }
        if source.startswith(("http://", "https://")) and source.lower().endswith(
            ".zip"
        ):
            self._download_zip(source, dest)
            meta["kind"] = "zip"
        elif source.startswith(("http://", "https://")) and (
            "github.com" in source or "gitlab.com" in source or source.endswith(".git")
        ):
            self._ingest_git_like(source, dest, meta)
        elif source.startswith("file://"):
            self._copy_local(Path(urllib.parse.urlparse(source).path), dest)
            meta["kind"] = "local"
        elif os.path.isdir(source):
            self._copy_local(Path(source), dest)
            meta["kind"] = "directory"
        else:
            # best-effort go-getter style handling
            self._try_go_getter(source, dest, meta)
        meta["digest"] = self._digest_tree(dest)
        (dest / "metadata.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return meta

    def _try_go_getter(self, source: str, dest: Path, meta: Dict[str, Any]) -> None:
        getter = shutil.which("go-getter")
        if getter:
            subprocess.run(
                [getter, source, str(dest)], check=False, capture_output=True, text=True
            )
            meta["kind"] = "go-getter"
            return
        # fall back to direct URL fetch for simple file/zip inputs
        if source.lower().endswith(".zip"):
            self._download_zip(source, dest)
            meta["kind"] = "zip"
            return
        if source.startswith(("http://", "https://")):
            target = dest / Path(urllib.parse.urlparse(source).path).name
            with urllib.request.urlopen(source, timeout=60) as response:
                target.write_bytes(response.read())
            meta["kind"] = "http"
            return
        raise RuntimeError(f"Unsupported source: {source}")

    def _ingest_git_like(self, source: str, dest: Path, meta: Dict[str, Any]) -> None:
        getter = shutil.which("go-getter")
        if getter:
            subprocess.run(
                [getter, source, str(dest)], check=False, capture_output=True, text=True
            )
            meta["kind"] = "git"
            return
        # offline fallback: store source descriptor only
        (dest / "SOURCE.txt").write_text(source, encoding="utf-8")
        meta["kind"] = "source-descriptor"

    def _copy_local(self, src: Path, dest: Path) -> None:
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        elif src.exists():
            shutil.copy2(src, dest / src.name)
        else:
            raise FileNotFoundError(src)

    def _download_zip(self, source: str, dest: Path) -> None:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            with urllib.request.urlopen(source, timeout=60) as response:
                tmp.write(response.read())
            tmp_path = Path(tmp.name)
        try:
            with zipfile.ZipFile(tmp_path) as zf:
                zf.extractall(dest)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _digest_tree(self, path: Path) -> str:
        digest = hashlib.sha256()
        for item in sorted(path.rglob("*")):
            if item.is_file():
                digest.update(str(item.relative_to(path)).encode("utf-8"))
                digest.update(item.read_bytes())
        return digest.hexdigest()
