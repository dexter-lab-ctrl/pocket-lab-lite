"""Bounded read-only developer diagnostics backed by fixed local evidence."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from ..policy import diagnostic_target_metadata, get_diagnostic_target
from ..runner import ProcessRunner

MAX_FACTS = 12
MAX_SOURCES = 6


class DiagnosticTools:
    """Expose only fixed diagnostics; callers cannot select files or commands."""

    def __init__(self, repository_root: Path, runner: ProcessRunner | None = None) -> None:
        self.repository_root = repository_root.resolve()
        self.runner = runner or ProcessRunner(self.repository_root)

    def diagnostic_targets(self) -> dict[str, object]:
        return {"targets": diagnostic_target_metadata()}

    def diagnostic_summary(self, target: str) -> dict[str, object]:
        definition = get_diagnostic_target(target)
        handlers = {
            "docs_health": self._docs_health,
            "generated_drift": self._generated_drift,
            "runtime_capture": self._runtime_capture,
            "pm2_status": self._pm2_status,
            "nats_health": self._nats_health,
            "openapi_routes": self._openapi_routes,
            "security_summary": self._security_summary,
        }
        try:
            return handlers[definition.identifier]()
        except (OSError, ValueError, json.JSONDecodeError, TypeError, KeyError):
            return self._response(definition.identifier, "unavailable", "Canonical diagnostic evidence is unreadable.", [], [], False)

    def _path(self, relative: str) -> Path:
        return self.repository_root / relative

    def _json(self, relative: str) -> Any:
        with self._path(relative).open(encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _response(target: str, status: str, summary: str, facts: list[dict[str, object]], sources: list[str], complete: bool) -> dict[str, object]:
        truncated = len(facts) > MAX_FACTS or len(sources) > MAX_SOURCES
        return {
            "target": target,
            "status": status,
            "summary": summary,
            "facts": facts[:MAX_FACTS],
            "sources": sources[:MAX_SOURCES],
            "complete": complete and not truncated,
            "truncated": truncated,
        }

    @staticmethod
    def _fact(name: str, value: object) -> dict[str, object]:
        return {"name": name, "value": value}

    def _docs_health(self) -> dict[str, object]:
        source = "contracts/generated/knowledge/operational-health.json"
        document = self._json(source)
        items = document.get("items")
        if not isinstance(items, list):
            raise ValueError("operational-health items missing")
        metadata = document.get("metadata", {})
        return self._response("docs_health", "ok", "Generated documentation operational-health evidence is readable.", [
            self._fact("item_count", len(items)),
            self._fact("generated_at", metadata.get("generated_at")),
            self._fact("source_commit", metadata.get("source_commit")),
        ], [source], True)

    def _generated_drift(self) -> dict[str, object]:
        result = self.runner.run(("git", "status", "--porcelain=v1", "--", "docs/generated", "contracts/generated"), timeout_seconds=30)
        if result.timed_out or result.exit_code != 0 or result.truncated:
            return self._response("generated_drift", "unavailable", "Read-only generated-artifact status is unavailable.", [], [], False)
        paths = [line[3:] for line in result.stdout_tail.splitlines() if len(line) >= 4]
        status = "warning" if paths else "ok"
        return self._response("generated_drift", status, "Generated-artifact working-tree drift detected." if paths else "No generated-artifact working-tree drift detected.", [
            self._fact("state", "drift detected" if paths else "current"),
            self._fact("changed_generated_files", len(paths)),
        ], paths, True)

    def _runtime_capture(self) -> dict[str, object]:
        source = "contracts/generated/runtime/domain-operational-health.json"
        document = self._json(source)
        domains = document.get("domains")
        if not isinstance(domains, dict):
            raise ValueError("runtime domains missing")
        status = "ok" if document.get("sanitized") is True else "warning"
        return self._response("runtime_capture", status, "Existing promoted runtime evidence was read without capture or promotion.", [
            self._fact("release_tag", document.get("release_tag")),
            self._fact("promoted_at", document.get("promoted_at")),
            self._fact("runtime_baseline_status", document.get("runtime_baseline_status")),
            self._fact("domain_count", len(domains)),
            self._fact("sanitized", document.get("sanitized")),
        ], [source], True)

    def _pm2_status(self) -> dict[str, object]:
        result = self.runner.run(("pm2", "jlist"), timeout_seconds=15)
        if result.timed_out or result.exit_code != 0:
            return self._response("pm2_status", "unavailable", "Local PM2 is unavailable; no process was changed.", [], [], False)
        try:
            processes = json.loads(result.stdout_tail)
        except json.JSONDecodeError:
            return self._response("pm2_status", "unavailable", "Local PM2 returned unreadable process data.", [], [], False)
        if not isinstance(processes, list):
            raise ValueError("PM2 process list missing")
        facts = [self._fact("process_count", len(processes))]
        for process in processes:
            if not isinstance(process, dict):
                continue
            environment = process.get("pm2_env") if isinstance(process.get("pm2_env"), dict) else {}
            facts.append(self._fact("process", {
                "name": process.get("name"), "status": environment.get("status"), "pid": process.get("pid"),
                "restart_count": environment.get("restart_time"), "started_at": environment.get("pm_uptime"),
            }))
        return self._response("pm2_status", "ok", "Local PM2 process state was projected without environment or command data.", facts, [], not result.truncated)

    def _nats_health(self) -> dict[str, object]:
        source = "contracts/generated/runtime/domain-operational-health.json"
        document = self._json(source)
        domains = document.get("domains", {})
        if not isinstance(domains, dict):
            raise ValueError("runtime domains missing")
        matching = {key: value for key, value in domains.items() if "nats" in key.lower()}
        if not matching:
            return self._response("nats_health", "unavailable", "No verified read-only local NATS health mechanism exists in canonical evidence.", [], [source], False)
        return self._response("nats_health", "ok", "Generated NATS readiness evidence is available.", [self._fact("nats_entries", len(matching))], [source], True)

    def _openapi_routes(self) -> dict[str, object]:
        source = "contracts/generated/lite-openapi.json"
        document = self._json(source)
        paths = document.get("paths")
        if not isinstance(paths, dict):
            raise ValueError("OpenAPI paths missing")
        methods = Counter(method.upper() for item in paths.values() if isinstance(item, dict) for method in item if method.lower() in {"get", "post", "put", "patch", "delete", "head", "options"})
        facts = [self._fact("openapi_version", document.get("openapi")), self._fact("route_count", len(paths)), self._fact("lite_route_count", sum(path.startswith("/api/lite/") for path in paths)), self._fact("schema_count", len(document.get("components", {}).get("schemas", {})))]
        facts.extend(self._fact(f"method_{method.lower()}_count", count) for method, count in sorted(methods.items()))
        return self._response("openapi_routes", "ok", "Local generated Lite OpenAPI contract is readable.", facts, [source], True)

    def _security_summary(self) -> dict[str, object]:
        sources = ["contracts/generated/documentation-enterprise/supply-chain.json", "contracts/generated/documentation-enterprise/security-controls.json", "contracts/generated/documentation-intelligence/dependency-health.json"]
        supply, controls, dependencies = (self._json(source) for source in sources)
        items = controls.get("items", [])
        dependency_items = dependencies.get("items", [])
        if not isinstance(items, list) or not isinstance(dependency_items, list):
            raise ValueError("security evidence items missing")
        return self._response("security_summary", "ok", "Generated security and supply-chain evidence is readable; scanners were not run.", [
            self._fact("supply_chain_status", supply.get("status")),
            self._fact("normalized_artifact_count", len(supply.get("normalized_artifacts", []))),
            self._fact("security_control_count", len(items)),
            self._fact("dependency_health_item_count", len(dependency_items)),
        ], sources, True)
