from __future__ import annotations

import hashlib
import json
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from contracts import OperationRequest, OperationTarget, utc_now_iso
from state.models import BlueprintDigest, OperationRun, RunnerEvent
from state.repositories import CatalogStateStore, OperationStateStore
from git.dulwich_repo import DulwichRepository
from sources.getter import SourceIngestor
from artifacts.oras_store import OciArtifactStore
from ansible.runner_service import AnsibleRunnerService
from operations.taskfile import TaskDefinition, TaskfileRegistry
from operations.registry import OperationRegistry


class OperationService:
    def __init__(
        self,
        *,
        state_dir: Path,
        workspace_dir: Path,
        iac_dir: Path,
        policies_dir: Path,
        taskfile_paths: list[Path],
    ):
        self.state = OperationStateStore(state_dir)
        self.catalog = CatalogStateStore(state_dir)
        self.registry = OperationRegistry()
        self.tasks = TaskfileRegistry(*taskfile_paths)
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.iac_dir = Path(iac_dir)
        self.policies_dir = Path(policies_dir)
        self.oras = OciArtifactStore(
            state_dir / "oci", state_dir / "artifact_index.json"
        )
        self.sources = SourceIngestor(self.workspace_dir / "sources")
        self.ansible = AnsibleRunnerService(
            state_dir / "runner", state_dir / "runner_events"
        )
        self._threads: dict[str, threading.Thread] = {}
        self._event_publisher: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_event_publisher(
        self, publisher: Optional[Callable[[Dict[str, Any]], None]]
    ) -> None:
        """Attach a best-effort live event publisher for runner events.

        The core operation service remains framework-agnostic so FastAPI,
        NATS workers, and test harnesses use the same execution semantics.
        can attach a callback that republishes every runner event to the
        Pocket Lab event bus as ``pocketlab.events.operation.log``. Publisher
        failures are intentionally swallowed; local operation state remains the
        source of truth.
        """
        self._event_publisher = publisher

    def _apply_task_defaults(
        self, request: OperationRequest, task: TaskDefinition
    ) -> OperationRequest:
        params = dict(task.defaults or {})
        params.update(dict(request.params or {}))
        operation = request.operation or task.operation
        return OperationRequest(
            operation=task.operation or operation,
            target=request.target,
            params=params,
            dry_run=request.dry_run,
            source=request.source,
        )

    def _create_queued_run(
        self, request: OperationRequest, *, job_id: Optional[str] = None
    ) -> tuple[str, OperationRequest, TaskDefinition]:
        task = self.tasks.resolve_operation(request.operation)
        effective_request = self._apply_task_defaults(request, task)

        job_id = job_id or uuid.uuid4().hex
        now = utc_now_iso()
        run = OperationRun(
            job_id=job_id,
            operation=effective_request.operation,
            task_id=task.name,
            status="queued",
            target={
                "type": effective_request.target.type,
                "ref": effective_request.target.ref,
            },
            params=effective_request.params,
            dry_run=effective_request.dry_run,
            created_at=now,
            updated_at=now,
        ).asdict()
        run["runner_events"] = []
        run["worker_execution"] = False
        self.state.create_run(run)
        return job_id, effective_request, task

    def submit(self, request: OperationRequest) -> Dict[str, Any]:
        job_id, effective_request, task = self._create_queued_run(request)
        thread = threading.Thread(
            target=self._run_job, args=(job_id, effective_request, task), daemon=True
        )
        self._threads[job_id] = thread
        thread.start()
        return {
            "job_id": job_id,
            "task_id": task.name,
            "operation": effective_request.operation,
            "status": "queued",
        }

    def submit_queued(
        self, request: OperationRequest, *, job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an operation run without starting a local thread.

        Phase 3 workers use this to make FastAPI a command publisher while the
        separate worker process owns execution.  It deliberately preserves the
        same run shape as submit() so existing status endpoints and frontend
        polling continue to work.
        """
        job_id, effective_request, task = self._create_queued_run(
            request, job_id=job_id
        )
        return {
            "job_id": job_id,
            "task_id": task.name,
            "operation": effective_request.operation,
            "status": "queued",
            "worker_execution": True,
        }

    def run_existing(self, job_id: str) -> Dict[str, Any]:
        """Execute a queued run synchronously in the current worker process."""
        run = self.get(job_id)
        if not run:
            raise KeyError(f"Operation job not found: {job_id}")
        if run.get("status") not in {"queued", "retrying"}:
            return run
        target = run.get("target") or {}
        request = OperationRequest(
            operation=str(run.get("operation") or ""),
            target=OperationTarget(
                type=str(target.get("type") or "repo"), ref=str(target.get("ref") or "")
            ),
            params=dict(run.get("params") or {}),
            dry_run=bool(run.get("dry_run", False)),
            source=run.get("source"),
        )
        task_id = str(run.get("task_id") or request.operation)
        task = self.tasks.tasks.get(task_id) or self.tasks.resolve_operation(
            request.operation
        )
        self.state.update_run(
            job_id,
            lambda current: {
                **current,
                "worker_execution": True,
                "worker_claimed_at": utc_now_iso(),
                "updated_at": utc_now_iso(),
            },
        )
        self._run_job(job_id, request, task)
        return self.get(job_id) or run

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        run = self.state.get_run(job_id)
        if not run:
            return None
        run.setdefault("runner_events", list(run.get("events") or []))
        run.setdefault("task_id", run.get("task_id") or run.get("operation"))
        return run

    def list(self, limit: int = 50) -> list[Dict[str, Any]]:
        return self.state.list_runs(limit=limit)

    def preview(self, request: OperationRequest) -> Dict[str, Any]:
        task = self.tasks.resolve_operation(request.operation)
        effective_request = self._apply_task_defaults(request, task)
        return {
            "status": "preview",
            "operation": effective_request.operation,
            "task_id": task.name,
            "target": {
                "type": effective_request.target.type,
                "ref": effective_request.target.ref,
            },
            "params": effective_request.params,
            "task_defaults": dict(task.defaults or {}),
            "estimated_effect": self._estimate_effect(effective_request),
        }

    def _emit(
        self, job_id: str, level: str, message: str, stream: str = "stdout", **data: Any
    ) -> None:
        event = RunnerEvent(
            timestamp=utc_now_iso(),
            level=level,
            message=message,
            stream=stream,
            data=data,
        ).asdict()
        self.state.append_event(job_id, event)
        publisher = self._event_publisher
        if publisher is not None:
            try:
                run = self.state.get_run(job_id) or {}
                publisher(
                    {
                        "job_id": job_id,
                        "operation": run.get("operation"),
                        "task_id": data.get("task") or run.get("task_id"),
                        "status": run.get("status"),
                        "level": level,
                        "message": message,
                        "stream": stream,
                        "timestamp": event.get("timestamp"),
                        "event": event,
                        **data,
                    }
                )
            except Exception:
                pass

    def _emit_ansible_event(
        self, job_id: str, task: TaskDefinition, event: Dict[str, Any]
    ) -> None:
        event_name = str(event.get("event") or "ansible_event")
        task_name = str(
            event.get("task") or event.get("event_data", {}).get("task") or task.name
        )
        stdout = str(event.get("stdout") or "").strip()
        message = stdout or event_name.replace("_", " ")
        level = (
            "error" if "failed" in event_name or "unreachable" in event_name else "info"
        )
        self._emit(
            job_id,
            level,
            message,
            stream="ansible",
            task=task.name,
            step="ansible",
            runner_event=event_name,
            ansible_task=task_name,
            host=event.get("host") or event.get("event_data", {}).get("host"),
            counter=event.get("counter"),
            uuid=event.get("uuid"),
        )

    def _finish(
        self,
        job_id: str,
        status: str,
        exit_code: int = 0,
        stdout: str = "",
        stderr: str = "",
        artifacts: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        def mutator(run: Dict[str, Any]):
            run = dict(run)
            run["status"] = status
            run["updated_at"] = utc_now_iso()
            run["finished_at"] = utc_now_iso()
            run["exit_code"] = exit_code
            run["stdout"] = stdout
            run["stderr"] = stderr
            run["artifacts"] = artifacts or run.get("artifacts") or {}
            run["error"] = error
            run["runner_events"] = list(
                run.get("runner_events") or run.get("events") or []
            )
            return run

        self.state.update_run(job_id, mutator)

    def _update(self, job_id: str, **fields: Any) -> None:
        def mutator(run: Dict[str, Any]):
            run = dict(run)
            run.update(fields)
            run["updated_at"] = utc_now_iso()
            return run

        self.state.update_run(job_id, mutator)

    def _run_job(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> None:
        try:
            self._update(
                job_id, status="running", started_at=utc_now_iso(), task_id=task.name
            )
            self._emit(
                job_id,
                "info",
                f"Operation started: {request.operation}",
                task=task.name,
            )
            result = self._dispatch(job_id, request, task)
            stdout = result.get("stdout", "")
            stderr = result.get("stderr", "")
            artifacts = result.get("artifacts", {})
            exit_code = int(result.get("exit_code", 0) or 0)
            self._finish(
                job_id,
                "succeeded" if exit_code == 0 else "failed",
                exit_code,
                stdout,
                stderr,
                artifacts,
                (
                    None
                    if exit_code == 0
                    else result.get("error") or stderr or "operation failed"
                ),
            )
            self._emit(
                job_id,
                "info",
                f"Operation completed: {request.operation}",
                task=task.name,
                exit_code=exit_code,
            )
        except Exception as exc:
            self._finish(job_id, "failed", 1, "", str(exc), {}, str(exc))
            self._emit(
                job_id,
                "error",
                f"Operation failed: {exc}",
                stream="stderr",
                error=str(exc),
                task=task.name,
            )

    def _dispatch(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> Dict[str, Any]:
        op = task.operation or request.operation
        if op == "git_sync":
            return self._op_git_sync(job_id, request, task)
        if op == "drift_scan":
            return self._op_drift_scan(job_id, request, task)
        if op == "deploy_blueprint":
            return self._op_deploy_blueprint(job_id, request, task)
        if op == "backup_now":
            return self._op_backup_now(job_id, request, task)
        if op == "restore_backup":
            return self._op_restore_backup(job_id, request, task)
        if op == "rotate_secret":
            return self._op_rotate_secret(job_id, request, task)
        if op == "fleet_join":
            return self._op_fleet_join(job_id, request, task)
        if op == "policy_deploy":
            return self._op_policy_deploy(job_id, request, task)
        if op == "secret_read_dynamic":
            return self._op_dynamic_secret(job_id, request, task)
        if op == "backup_verify":
            return self._op_backup_verify(job_id, request, task)
        raise ValueError(f"Unsupported operation: {request.operation}")

    def _resolve_oci_artifact(self, ref: str) -> Optional[Dict[str, Any]]:
        artifact = self.oras.find(ref)
        if artifact is not None:
            return artifact
        ref_norm = str(ref).replace("oci://", "").strip()
        for item in self.catalog.list_artifacts():
            candidates = {
                str(item.get("ref") or ""),
                str(item.get("name") or ""),
                str(item.get("digest") or ""),
                str(item.get("path") or ""),
                str(item.get("metadata", {}).get("source_ref") or ""),
                str(item.get("metadata", {}).get("backup_ref") or ""),
            }
            if ref in candidates or ref_norm in candidates:
                return item
            name = str(item.get("name") or "")
            version = str(item.get("version") or "")
            if name and version and ref_norm.endswith(f"/{name}:{version}"):
                return item
        return None

    def _snapshot_state(self) -> Dict[str, Any]:
        return {
            "operation_runs": self.state._runs.read(),
            "catalog": {
                "sources": self.catalog.sources.read(),
                "artifacts": self.catalog.artifacts.read(),
                "repos": self.catalog.repos.read(),
                "blueprint_digests": self.catalog.blueprint_digests.read(),
                "rollback_pointers": self.catalog.rollback_pointers.read(),
                "drift_snapshots": self.catalog.drift_snapshots.read(),
            },
            "files": {
                "fleet.json": self._read_json(
                    self.state.state_dir / "fleet.json", {"nodes": []}
                ),
                "drift.json": self._read_json(
                    self.state.state_dir / "drift.json",
                    {"summary": {}, "metrics": {}, "jobs": []},
                ),
                "secrets.json": self._read_json(
                    self.state.state_dir / "secrets.json", {}
                ),
                "opa.json": self._read_json(self.state.state_dir / "opa.json", {}),
                "opa_evaluations.json": self._read_json(
                    self.state.state_dir / "opa_evaluations.json", []
                ),
            },
        }

    def _restore_state(self, snapshot: Dict[str, Any]) -> list[str]:
        restored: list[str] = []
        catalog = snapshot.get("catalog") or {}
        if catalog:
            if isinstance(catalog.get("sources"), dict):
                self.catalog.sources.write(catalog["sources"])
                restored.append("catalog/source_registry.json")
            if isinstance(catalog.get("artifacts"), dict):
                self.catalog.artifacts.write(catalog["artifacts"])
                restored.append("catalog/artifact_index.json")
            if isinstance(catalog.get("repos"), dict):
                self.catalog.repos.write(catalog["repos"])
                restored.append("catalog/repo_snapshot.json")
            if isinstance(catalog.get("blueprint_digests"), dict):
                self.catalog.blueprint_digests.write(catalog["blueprint_digests"])
                restored.append("catalog/blueprint_digests.json")
            if isinstance(catalog.get("rollback_pointers"), dict):
                self.catalog.rollback_pointers.write(catalog["rollback_pointers"])
                restored.append("catalog/rollback_pointers.json")
            if isinstance(catalog.get("drift_snapshots"), dict):
                self.catalog.drift_snapshots.write(catalog["drift_snapshots"])
                restored.append("catalog/drift_snapshots.json")

        # Preserve the live restore job record while applying the rest of the snapshot.
        # Operation history can be restored separately by a dedicated maintenance task if needed.
        files = snapshot.get("files") or {}
        for filename, payload in files.items():
            if payload is None:
                continue
            target = self.state.state_dir / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            restored.append(filename)
        return restored

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write_json(self, path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _resolve_backup_artifact(self, backup_ref: str) -> Optional[Dict[str, Any]]:
        ref = str(backup_ref or "").strip()
        artifacts = list(self.catalog.list_artifacts())

        def _artifact_sort_key(item: Dict[str, Any]) -> tuple[str, str]:
            return (str(item.get("created_at") or ""), str(item.get("version") or ""))

        if not ref or ref.lower() in {"latest", "newest", "last"}:
            backup_artifacts = [
                item
                for item in artifacts
                if str(item.get("ref") or "").startswith("backup://")
            ]
            if backup_artifacts:
                return sorted(backup_artifacts, key=_artifact_sort_key, reverse=True)[0]
            backup_dir = self.state.state_dir / "backups"
            if backup_dir.exists():
                candidates = sorted(
                    backup_dir.glob("backup-*.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if candidates:
                    latest_path = candidates[0]
                    job_id = latest_path.stem.replace("backup-", "", 1)
                    return {
                        "ref": f"backup://{job_id}",
                        "path": str(latest_path),
                        "name": "backup",
                        "version": job_id,
                        "source": "local-backup",
                        "created_at": utc_now_iso(),
                        "metadata": {"path": str(latest_path)},
                    }

        for item in artifacts:
            candidates = {
                str(item.get("ref") or ""),
                str(item.get("name") or ""),
                str(item.get("path") or ""),
                str(item.get("metadata", {}).get("path") or ""),
                str(item.get("metadata", {}).get("backup_ref") or ""),
                str(item.get("metadata", {}).get("source_ref") or ""),
            }
            if ref in candidates:
                return item

        if ref.startswith("backup://"):
            job_id = ref.split("backup://", 1)[-1]
            local_path = self.state.state_dir / "backups" / f"backup-{job_id}.json"
            if local_path.exists():
                return {
                    "ref": ref,
                    "path": str(local_path),
                    "name": "backup",
                    "version": job_id,
                    "source": "local-backup",
                    "created_at": utc_now_iso(),
                    "metadata": {"path": str(local_path)},
                }
        if Path(ref).exists():
            return {
                "ref": ref,
                "path": ref,
                "name": Path(ref).stem,
                "version": Path(ref).stem,
                "source": "filesystem",
                "created_at": utc_now_iso(),
                "metadata": {"path": ref},
            }
        return None

    def _load_backup_snapshot(self, artifact: Dict[str, Any]) -> Dict[str, Any]:
        path = (
            artifact.get("path")
            or artifact.get("metadata", {}).get("path")
            or artifact.get("layout")
        )
        if not path:
            raise FileNotFoundError(
                str(artifact.get("ref") or artifact.get("name") or "backup")
            )
        backup_path = Path(str(path))
        if backup_path.is_dir():
            backup_path = backup_path / "backup.json"
        if not backup_path.exists():
            raise FileNotFoundError(str(backup_path))
        data = json.loads(backup_path.read_text(encoding="utf-8"))
        return data.get("snapshot") or data.get("state") or data

    def _op_git_sync(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> Dict[str, Any]:
        repo_path = Path(
            request.target.ref or request.params.get("repo_path") or self.iac_dir
        )
        repo_path.mkdir(parents=True, exist_ok=True)
        repo = DulwichRepository(repo_path)
        relative_path = (
            request.params.get("path") or request.params.get("filename") or "README.md"
        )
        content = request.params.get("content")
        if content is None:
            content = json.dumps(
                {
                    "operation": request.operation,
                    "task": task.name,
                    "target": {"type": request.target.type, "ref": request.target.ref},
                    "params": request.params,
                    "updated_at": utc_now_iso(),
                },
                indent=2,
                ensure_ascii=False,
            )
        message = request.params.get("message") or f"Pocket Lab sync: {relative_path}"
        branch = request.params.get("branch") or "main"
        self._emit(
            job_id, "info", f"Writing {relative_path} into {repo_path}", task=task.name
        )
        commit_result = repo.commit_file(relative_path, content, message, branch=branch)
        status = repo.status()
        payload = {
            "repo": str(repo_path),
            "branch": status.branch,
            "dirty": status.dirty,
            "exists": status.exists,
            "last_commit": status.last_commit,
            "commit_result": commit_result,
        }
        self.catalog.set_repos(
            [
                {
                    "name": repo_path.name,
                    "ref": str(repo_path),
                    "description": "Git-backed Pocket Lab repository",
                    "branch": status.branch,
                    "last_commit": status.last_commit,
                    "updated_at": utc_now_iso(),
                }
            ]
        )
        return {
            "stdout": json.dumps(payload, indent=2, ensure_ascii=False),
            "stderr": "",
            "artifacts": payload,
        }

    def _op_drift_scan(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> Dict[str, Any]:
        runs = self.state.list_runs(limit=25)
        healthy = sum(1 for run in runs if run.get("status") == "succeeded")
        failed = sum(1 for run in runs if run.get("status") == "failed")
        pending = sum(1 for run in runs if run.get("status") == "queued")
        total = max(1, len(runs))
        snapshot = {
            "summary": {
                "healthy": healthy,
                "drifted": failed,
                "unknown": max(0, total - healthy - failed - pending),
                "open_jobs": pending,
                "last_successful_reconcile_at": utc_now_iso(),
            },
            "metrics": {
                "total_targets": len(runs),
                "healthy": healthy,
                "drifted": failed,
                "unknown": max(0, len(runs) - healthy - failed - pending),
                "open_jobs": pending,
                "last_successful_reconcile_at": utc_now_iso(),
            },
            "jobs": runs,
        }
        self.catalog.record_drift_snapshot(
            {
                "job_id": job_id,
                "summary": snapshot["summary"],
                "metrics": snapshot["metrics"],
                "metadata": {
                    "operation": "drift_scan",
                    "scope": request.params.get("scope", "all"),
                },
            }
        )
        return {
            "stdout": json.dumps(snapshot, indent=2, ensure_ascii=False),
            "stderr": "",
            "artifacts": snapshot,
        }

    def _op_deploy_blueprint(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> Dict[str, Any]:
        source_ref = (
            request.target.ref
            or request.params.get("ref")
            or request.params.get("source")
        )
        source_type = (
            request.params.get("source_type") or request.target.type or "repo"
        ).strip().lower() or "repo"
        self._emit(
            job_id,
            "info",
            f"Preparing blueprint source: {source_ref or request.params.get('name') or 'default'}",
            task=task.name,
            step="source",
            source_type=source_type,
        )
        metadata: Dict[str, Any] = {
            "source_type": source_type,
            "source_ref": source_ref,
            "params": request.params,
        }
        repo_commit = None
        if source_type == "oci" or str(source_ref).startswith("oci://"):
            dest = self.workspace_dir / "blueprints" / "oci"
            artifact = self._resolve_oci_artifact(str(source_ref))
            if artifact is None:
                raise FileNotFoundError(f"OCI artifact not found: {source_ref}")
            self._emit(
                job_id,
                "info",
                f"Pulling blueprint artifact {source_ref}",
                task=task.name,
                step="artifact",
                artifact_ref=str(source_ref),
            )
            pulled = self.oras.materialize(artifact, dest)
            metadata["pulled"] = pulled
            artifact_record = dict(artifact)
            artifact_record.setdefault("ref", str(source_ref))
            artifact_record.setdefault(
                "name",
                request.params.get("name")
                or artifact_record.get("name")
                or Path(str(source_ref).split(":")[-1]).stem,
            )
            artifact_record.setdefault(
                "version",
                request.params.get("version")
                or artifact_record.get("version")
                or (
                    str(source_ref).rsplit(":", 1)[-1]
                    if ":" in str(source_ref)
                    else "latest"
                ),
            )
            artifact_record["updated_at"] = utc_now_iso()
            self.catalog.upsert_artifact(artifact_record)
        elif source_type in {"git", "repo", "source", "zip", "http"} and source_ref:
            self._emit(
                job_id,
                "info",
                f"Ingesting blueprint source {source_ref}",
                task=task.name,
                step="source",
                source_ref=str(source_ref),
            )
            ingested = self.sources.ingest(
                str(source_ref), destination_name=request.params.get("name")
            )
            metadata["ingested"] = ingested
            self.catalog.upsert_source(
                {
                    "ref": source_ref,
                    "kind": source_type,
                    "name": request.params.get("name")
                    or Path(str(source_ref)).name
                    or "source",
                    "description": request.params.get(
                        "description", "Blueprint source"
                    ),
                    "ingested_at": utc_now_iso(),
                    "digest": ingested.get("digest"),
                    "source_type": source_type,
                }
            )
        if source_type in {"repo", "git"} and self.iac_dir.exists():
            try:
                repo_commit = DulwichRepository(self.iac_dir).last_commit()
            except Exception:
                repo_commit = None
            if repo_commit:
                metadata["repo_commit"] = repo_commit
        playbook = request.params.get("playbook") or "site.yml"
        self._emit(
            job_id,
            "info",
            f"Running Ansible playbook {playbook}",
            task=task.name,
            step="ansible",
            playbook=playbook,
        )
        runner_result = self.ansible.run_playbook(
            playbook,
            inventory=request.params.get("inventory"),
            extravars=request.params.get("extravars"),
            tags=request.params.get("tags"),
            event_handler=lambda event: self._emit_ansible_event(job_id, task, event),
        )
        self._emit(
            job_id,
            "info",
            f"Ansible playbook finished with rc={runner_result.get('rc', 0)}",
            task=task.name,
            step="ansible",
            playbook=playbook,
            exit_code=runner_result.get("rc", 0),
        )
        metadata["runner"] = runner_result
        if repo_commit:
            metadata["commit_sha"] = repo_commit.get("commit")
        digest = hashlib.sha256(
            json.dumps(
                metadata, sort_keys=True, ensure_ascii=False, default=str
            ).encode("utf-8")
        ).hexdigest()
        blueprint_record = BlueprintDigest(
            ref=str(source_ref or request.params.get("name") or "blueprint"),
            digest=digest,
            source=source_type,
            created_at=utc_now_iso(),
            metadata={
                "playbook": playbook,
                "task_id": task.name,
                "commit_sha": metadata.get("commit_sha"),
            },
        ).asdict()
        self.catalog.record_blueprint_digest(blueprint_record)
        self._emit(
            job_id,
            "info",
            f"Blueprint deployment queued via {playbook}",
            task=task.name,
        )
        return {
            "stdout": json.dumps(metadata, indent=2, ensure_ascii=False),
            "stderr": "",
            "artifacts": {**metadata, "blueprint_digest": blueprint_record},
        }

    def _op_backup_now(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> Dict[str, Any]:
        backup_dir = self.state.state_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        archive = backup_dir / f"backup-{job_id}.json"
        snapshot = self._snapshot_state()
        payload = {
            "created_at": utc_now_iso(),
            "job_id": job_id,
            "task_id": task.name,
            "request": {
                "operation": request.operation,
                "target": {"type": request.target.type, "ref": request.target.ref},
                "params": request.params,
                "dry_run": request.dry_run,
                "source": request.source,
            },
            "snapshot": snapshot,
        }
        archive.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        artifact_record = {
            "ref": f"backup://{job_id}",
            "name": request.params.get("name") or "backup",
            "version": job_id,
            "digest": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "source": "local-backup",
            "created_at": utc_now_iso(),
            "path": str(archive),
            "metadata": {
                "backup_path": str(archive),
                "snapshot_keys": list(snapshot.keys()),
                "job_id": job_id,
                "task_id": task.name,
            },
        }
        self.catalog.upsert_artifact(artifact_record)
        self._emit(
            job_id, "info", f"Backup snapshot created: {archive.name}", task=task.name
        )
        return {
            "stdout": archive.read_text(encoding="utf-8"),
            "stderr": "",
            "artifacts": {
                "backup": str(archive),
                "backup_ref": artifact_record["ref"],
                **payload,
            },
        }

    def _op_restore_backup(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> Dict[str, Any]:
        backup_ref = (
            request.params.get("backup_ref")
            or request.params.get("path")
            or request.target.ref
        )
        artifact = self._resolve_backup_artifact(str(backup_ref))
        if artifact is None:
            raise FileNotFoundError(str(backup_ref))
        snapshot = self._load_backup_snapshot(artifact)
        restored_paths = self._restore_state(snapshot)
        pointer = self.catalog.set_rollback_pointer(
            str(request.params.get("name") or request.target.ref or "backup"),
            {
                "backup_ref": backup_ref,
                "restored_at": utc_now_iso(),
                "job_id": job_id,
                "task_id": task.name,
                "restored": True,
                "restore_path": artifact.get("path")
                or artifact.get("metadata", {}).get("path")
                or artifact.get("layout"),
                "restored_paths": restored_paths,
            },
        )
        self._emit(job_id, "info", f"Restored backup {backup_ref}", task=task.name)
        return {
            "stdout": json.dumps(
                {
                    "restored": True,
                    "backup_ref": backup_ref,
                    "rollback_pointer": pointer,
                    "restored_paths": restored_paths,
                },
                indent=2,
                ensure_ascii=False,
            ),
            "stderr": "",
            "artifacts": {
                "backup_ref": backup_ref,
                "rollback_pointer": pointer,
                "restored": True,
                "restored_paths": restored_paths,
            },
        }

    def _op_rotate_secret(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> Dict[str, Any]:
        secret_name = (
            str(request.params.get("target") or request.target.ref or "secret").strip()
            or "secret"
        )
        value = str(request.params.get("value") or f"rot-{uuid.uuid4().hex[:24]}")
        secrets = self._read_json(self.state.state_dir / "secrets.json", {})
        current = dict(secrets.get(secret_name) or {})
        version = int(current.get("version") or 0) + 1
        rotated_at = utc_now_iso()
        lease_duration = str(
            request.params.get("lease_duration") or request.params.get("ttl") or "1h"
        )
        artifact = {
            "secret": secret_name,
            "value": value,
            "rotated_at": rotated_at,
            "version": version,
            "lease_duration": lease_duration,
        }
        secrets[secret_name] = artifact
        self._write_json(self.state.state_dir / "secrets.json", secrets)
        if secret_name == "tailscale":
            self.state.update_run(
                job_id,
                lambda run: {
                    **run,
                    "artifacts": {
                        **(run.get("artifacts") or {}),
                        "tailscale_api_key": value,
                        "secret_version": version,
                        "rotated_at": rotated_at,
                        "lease_duration": lease_duration,
                    },
                    "updated_at": utc_now_iso(),
                },
            )
        self._emit(job_id, "info", f"Rotated secret {secret_name}", task=task.name)
        return {
            "stdout": json.dumps(
                {
                    "identity": {
                        "username": "admin",
                        "password": value,
                        "lastRotated": rotated_at,
                    },
                    "secret": {
                        "name": secret_name,
                        "version": version,
                        "rotated_at": rotated_at,
                        "lease_duration": lease_duration,
                    },
                },
                indent=2,
                ensure_ascii=False,
            ),
            "stderr": "",
            "artifacts": artifact,
        }

    def _op_fleet_join(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> Dict[str, Any]:
        role = str(request.params.get("role") or "compute").strip() or "compute"
        node_name = (
            str(request.params.get("hostname") or f"pocket-{role}").strip()
            or f"pocket-{role}"
        )
        token = f"tskey-{uuid.uuid4().hex[:16]}"
        script = f"#!/bin/sh\necho 'Join {node_name} with token {token}\n"
        pending_nodes = self._read_json(
            self.state.state_dir / "fleet_pending.json", {"nodes": []}
        )
        nodes = [
            n
            for n in list(pending_nodes.get("nodes", []))
            if str(n.get("name")) != node_name
        ]
        record = {
            "id": f"pending-{job_id}",
            "name": node_name,
            "role": f"{role.title()} Node",
            "ip": "",
            "status": "pending",
            "enrollment_state": "awaiting_heartbeat",
            "join_token": token,
            "requested_at": utc_now_iso(),
            "operation_job_id": job_id,
            "isCurrent": False,
        }
        nodes.insert(0, record)
        pending_nodes["nodes"] = nodes
        self._write_json(self.state.state_dir / "fleet_pending.json", pending_nodes)
        self._emit(
            job_id,
            "info",
            f"Generated fleet join payload for {node_name}",
            task=task.name,
        )
        return {
            "stdout": script,
            "stderr": "",
            "artifacts": {
                "role": role,
                "token": token,
                "hostname": node_name,
                "pending_state": record,
            },
        }

    def _op_policy_deploy(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> Dict[str, Any]:
        result = self.ansible.run_playbook(
            request.params.get("playbook") or "40_opa.yml",
            inventory=request.params.get("inventory"),
            extravars=request.params.get("extravars"),
            tags=request.params.get("tags"),
        )
        self._emit(job_id, "info", "Policy deployment executed", task=task.name)
        self.catalog.record_drift_snapshot(
            {
                "job_id": job_id,
                "summary": {
                    "healthy": 1,
                    "drifted": 0,
                    "unknown": 0,
                    "pending_approval": 0,
                    "failed": 0,
                },
                "metrics": {
                    "total_targets": 1,
                    "healthy": 1,
                    "drifted": 0,
                    "unknown": 0,
                    "open_jobs": 0,
                },
                "metadata": {"operation": "policy_deploy"},
            }
        )
        return {
            "stdout": json.dumps(result, indent=2, ensure_ascii=False),
            "stderr": "",
            "artifacts": {"runner": result},
        }

    def _op_dynamic_secret(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> Dict[str, Any]:
        username = f"v-user-{uuid.uuid4().hex[:8]}"
        password = uuid.uuid4().hex + uuid.uuid4().hex[:8]
        lease = {
            "leaseId": f"lease/{uuid.uuid4().hex[:12]}",
            "username": username,
            "password": password,
            "issuedAt": utc_now_iso(),
            "ttl": "1h 0m",
        }
        self._emit(
            job_id,
            "info",
            f"Issued dynamic secret for {request.params.get('target') or 'default'}",
            task=task.name,
        )
        return {
            "stdout": json.dumps({"lease": lease}, indent=2),
            "stderr": "",
            "artifacts": {"lease": lease},
        }

    def _op_backup_verify(
        self, job_id: str, request: OperationRequest, task: TaskDefinition
    ) -> Dict[str, Any]:
        backup_ref = (
            request.params.get("backup_ref")
            or request.params.get("path")
            or request.target.ref
            or "latest"
        )
        artifact = self._resolve_backup_artifact(str(backup_ref))
        if artifact is None:
            raise FileNotFoundError(str(backup_ref))
        snapshot = self._load_backup_snapshot(artifact)
        serialized = json.dumps(
            snapshot, sort_keys=True, ensure_ascii=False, default=str
        ).encode("utf-8")
        checksum = hashlib.sha256(serialized).hexdigest()
        verified = {
            "verified": True,
            "ref": artifact.get("ref"),
            "name": artifact.get("name"),
            "version": artifact.get("version"),
            "checksum_sha256": checksum,
            "snapshot_keys": (
                sorted(list(snapshot.keys())) if isinstance(snapshot, dict) else []
            ),
            "backup_path": artifact.get("path")
            or artifact.get("metadata", {}).get("path")
            or artifact.get("layout"),
            "verified_at": utc_now_iso(),
        }
        self._emit(job_id, "info", f"Verified backup {backup_ref}", task=task.name)
        return {
            "stdout": json.dumps(verified, indent=2, ensure_ascii=False),
            "stderr": "",
            "artifacts": verified,
        }

    def _estimate_effect(self, request: OperationRequest) -> Dict[str, Any]:
        return {
            "kind": request.operation,
            "scope": request.target.type,
            "ref": request.target.ref,
        }
