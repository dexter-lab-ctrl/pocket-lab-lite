from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional

from contracts import slugify, utc_now_iso
from .models import OperationRun


class JsonStore:
    def __init__(self, path: Path, default: Any):
        self.path = Path(path)
        self.default = default
        self._lock = Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> Any:
        if not self.path.exists():
            return self._clone_default()
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return self._clone_default()

    def write(self, data: Any) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            fd, tmp_path = tempfile.mkstemp(
                prefix=self.path.name + ".", dir=str(self.path.parent)
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, indent=2, ensure_ascii=False)
                os.replace(tmp_path, self.path)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass

    def update(self, mutator):
        with self._lock:
            data = self.read()
            new_data = mutator(data)
            self.write(new_data)
            return new_data

    def _clone_default(self) -> Any:
        return json.loads(json.dumps(self.default))


class OperationStateStore:
    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.operations_dir = self.state_dir / "operations"
        self.runs_dir = self.state_dir / "runs"
        self.runner_events_dir = self.state_dir / "runner_events"
        self.artifacts_dir = self.state_dir / "artifacts"
        self.operations_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.runner_events_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self._runs = JsonStore(self.state_dir / "operation_runs.json", {"runs": []})

    def create_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        record = OperationRun.from_mapping(run).asdict()
        data = self._runs.read()
        runs = data.setdefault("runs", [])
        runs.insert(0, record)
        self._runs.write(data)
        self._write_run_file(record)
        return record

    def update_run(self, job_id: str, mutator):
        data = self._runs.read()
        runs = data.get("runs", [])
        for idx, run in enumerate(runs):
            if run.get("job_id") == job_id:
                updated = mutator(run)
                runs[idx] = updated
                self._runs.write(data)
                self._write_run_file(updated)
                return updated
        return None

    def get_run(self, job_id: str) -> Optional[Dict[str, Any]]:
        data = self._runs.read()
        for run in data.get("runs", []):
            if run.get("job_id") == job_id:
                return run
        for file_path in (
            self.operations_dir / f"{slugify(job_id)}.json",
            self.runs_dir / f"{slugify(job_id)}.json",
        ):
            if file_path.exists():
                try:
                    return json.loads(file_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
        return None

    def list_runs(self, limit: int = 50) -> List[Dict[str, Any]]:
        data = self._runs.read()
        return list(data.get("runs", []))[:limit]

    def append_event(self, job_id: str, event: Dict[str, Any]) -> None:
        record = self.get_run(job_id)
        if not record:
            return
        record.setdefault("events", []).append(event)
        record.setdefault("runner_events", []).append(event)
        record["updated_at"] = utc_now_iso()
        self.update_run(job_id, lambda _: record)
        event_file = self.runner_events_dir / f"{slugify(job_id)}.jsonl"
        with event_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def list_events(self, job_id: str) -> List[Dict[str, Any]]:
        path = self.runner_events_dir / f"{slugify(job_id)}.jsonl"
        if not path.exists():
            return []
        events: List[Dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
        return events

    def _write_run_file(self, run: Dict[str, Any]) -> None:
        file_name = f"{slugify(run.get('job_id', 'run'))}.json"
        payload = json.dumps(run, indent=2, ensure_ascii=False)
        for folder in (self.operations_dir, self.runs_dir):
            (folder / file_name).write_text(payload, encoding="utf-8")


class CatalogStateStore:
    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.catalog_dir = self.state_dir / "catalog"
        self.catalog_dir.mkdir(parents=True, exist_ok=True)
        self.sources = JsonStore(
            self.catalog_dir / "source_registry.json", {"sources": []}
        )
        self.artifacts = JsonStore(
            self.catalog_dir / "artifact_index.json", {"artifacts": []}
        )
        self.repos = JsonStore(self.catalog_dir / "repo_snapshot.json", {"repos": []})
        self.blueprint_digests = JsonStore(
            self.catalog_dir / "blueprint_digests.json", {"digests": []}
        )
        self.rollback_pointers = JsonStore(
            self.catalog_dir / "rollback_pointers.json", {"pointers": []}
        )
        self.drift_snapshots = JsonStore(
            self.state_dir / "drift_snapshots.json", {"snapshots": []}
        )

    def upsert_source(self, source: Dict[str, Any]) -> Dict[str, Any]:
        data = self.sources.read()
        items = data.setdefault("sources", [])
        ref = source.get("ref") or source.get("url") or source.get("name")
        source = dict(source)
        source.setdefault("updated_at", utc_now_iso())
        for idx, item in enumerate(items):
            if (item.get("ref") or item.get("url") or item.get("name")) == ref:
                items[idx] = source
                self.sources.write(data)
                return source
        items.insert(0, source)
        self.sources.write(data)
        return source

    def list_sources(self) -> List[Dict[str, Any]]:
        return list(self.sources.read().get("sources", []))

    def upsert_artifact(self, artifact: Dict[str, Any]) -> Dict[str, Any]:
        data = self.artifacts.read()
        items = data.setdefault("artifacts", [])
        key = artifact.get("ref") or artifact.get("digest") or artifact.get("name")
        artifact = dict(artifact)
        artifact.setdefault("updated_at", utc_now_iso())
        for idx, item in enumerate(items):
            if (item.get("ref") or item.get("digest") or item.get("name")) == key:
                items[idx] = artifact
                self.artifacts.write(data)
                return artifact
        items.insert(0, artifact)
        self.artifacts.write(data)
        return artifact

    def list_artifacts(self) -> List[Dict[str, Any]]:
        return list(self.artifacts.read().get("artifacts", []))

    def set_repos(self, repos: Iterable[Dict[str, Any]]) -> None:
        self.repos.write({"repos": list(repos), "updated_at": utc_now_iso()})

    def list_repos(self) -> List[Dict[str, Any]]:
        return list(self.repos.read().get("repos", []))

    def record_blueprint_digest(self, digest: Dict[str, Any]) -> Dict[str, Any]:
        data = self.blueprint_digests.read()
        items = data.setdefault("digests", [])
        digest = dict(digest)
        digest.setdefault("created_at", utc_now_iso())
        key = digest.get("ref") or digest.get("digest")
        for idx, item in enumerate(items):
            if (item.get("ref") or item.get("digest")) == key:
                items[idx] = digest
                self.blueprint_digests.write(data)
                return digest
        items.insert(0, digest)
        self.blueprint_digests.write(data)
        return digest

    def list_blueprint_digests(self) -> List[Dict[str, Any]]:
        return list(self.blueprint_digests.read().get("digests", []))

    def set_rollback_pointer(
        self, name: str, pointer: Dict[str, Any]
    ) -> Dict[str, Any]:
        data = self.rollback_pointers.read()
        items = data.setdefault("pointers", [])
        record = {"name": name, **pointer, "updated_at": utc_now_iso()}
        for idx, item in enumerate(items):
            if item.get("name") == name:
                items[idx] = record
                self.rollback_pointers.write(data)
                return record
        items.insert(0, record)
        self.rollback_pointers.write(data)
        return record

    def list_rollback_pointers(self) -> List[Dict[str, Any]]:
        return list(self.rollback_pointers.read().get("pointers", []))

    def record_drift_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        data = self.drift_snapshots.read()
        items = data.setdefault("snapshots", [])
        record = dict(snapshot)
        record.setdefault("created_at", utc_now_iso())
        items.insert(0, record)
        self.drift_snapshots.write(data)
        return record

    def list_drift_snapshots(self) -> List[Dict[str, Any]]:
        return list(self.drift_snapshots.read().get("snapshots", []))
