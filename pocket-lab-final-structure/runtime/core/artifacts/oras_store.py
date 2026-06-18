from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from contracts import utc_now_iso, slugify


class OciArtifactStore:
    def __init__(self, artifact_dir: Path, index_path: Path):
        self.artifact_dir = Path(artifact_dir)
        self.index_path = Path(index_path)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_index(self) -> Dict[str, Any]:
        if not self.index_path.exists():
            return {"artifacts": []}
        try:
            return json.loads(self.index_path.read_text(encoding="utf-8"))
        except Exception:
            return {"artifacts": []}

    def _write_index(self, data: Dict[str, Any]) -> None:
        self.index_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _artifact_path(self, name: str, version: str) -> Path:
        return self.artifact_dir / slugify(name) / slugify(version)

    def _normalise_ref(self, ref: str) -> str:
        return ref.replace("oci://", "").strip()

    def publish_blueprint(
        self,
        name: str,
        version: str,
        source_dir: Path,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        package_dir = self._artifact_path(name, version)
        package_dir.mkdir(parents=True, exist_ok=True)
        if source_dir.exists() and source_dir.is_dir():
            shutil.copytree(source_dir, package_dir / "content", dirs_exist_ok=True)
        payload = {
            "name": name,
            "version": version,
            "ref": f"oci://local/{slugify(name)}:{slugify(version)}",
            "created_at": utc_now_iso(),
            "metadata": metadata or {},
            "layout": str(package_dir),
            "content_path": str(package_dir / "content"),
        }
        (package_dir / "artifact.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        data = self._read_index()
        data.setdefault("artifacts", [])
        data["artifacts"] = [
            a for a in data["artifacts"] if a.get("ref") != payload["ref"]
        ]
        data["artifacts"].insert(0, payload)
        self._write_index(data)
        return payload

    def list_artifacts(self) -> list[Dict[str, Any]]:
        return list(self._read_index().get("artifacts", []))

    def find(self, ref: str) -> Optional[Dict[str, Any]]:
        ref_norm = self._normalise_ref(ref)
        for artifact in self.list_artifacts():
            candidates = {
                str(artifact.get("ref") or ""),
                self._normalise_ref(str(artifact.get("ref") or "")),
                str(artifact.get("name") or ""),
                str(artifact.get("metadata", {}).get("source_ref") or ""),
                self._normalise_ref(
                    str(artifact.get("metadata", {}).get("source_ref") or "")
                ),
            }
            if ref in candidates or ref_norm in candidates:
                return artifact
            name = str(artifact.get("name") or "")
            version = str(artifact.get("version") or "")
            if (
                ref_norm.endswith(f"/{slugify(name)}:{slugify(version)}")
                or ref_norm == f"local/{slugify(name)}:{slugify(version)}"
            ):
                return artifact
        return None

    def materialize(
        self, artifact: Dict[str, Any], destination: Path
    ) -> Dict[str, Any]:
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        source_paths = [
            artifact.get("content_path"),
            artifact.get("layout"),
            artifact.get("path"),
            artifact.get("metadata", {}).get("content_path"),
            artifact.get("metadata", {}).get("path"),
        ]
        for raw_path in source_paths:
            if not raw_path:
                continue
            source_path = Path(str(raw_path))
            if source_path.is_dir():
                shutil.copytree(source_path, destination, dirs_exist_ok=True)
                return {
                    "ref": artifact.get("ref"),
                    "destination": str(destination),
                    "artifact": artifact,
                    "source_path": str(source_path),
                }
            if source_path.is_file():
                shutil.copy2(source_path, destination / source_path.name)
                return {
                    "ref": artifact.get("ref"),
                    "destination": str(destination),
                    "artifact": artifact,
                    "source_path": str(source_path),
                }
        raise FileNotFoundError(
            str(artifact.get("ref") or artifact.get("name") or "artifact")
        )

    def pull_blueprint(self, ref: str, destination: Path) -> Dict[str, Any]:
        artifact = self.find(ref)
        if artifact is None:
            raise FileNotFoundError(ref)
        return self.materialize(artifact, destination)

    def rollback(self, name: str, version: str) -> Dict[str, Any]:
        ref = f"oci://local/{slugify(name)}:{slugify(version)}"
        artifact = self.find(ref)
        if artifact is None:
            raise FileNotFoundError(ref)
        return {"status": "rolled_back", "ref": ref, "artifact": artifact}
