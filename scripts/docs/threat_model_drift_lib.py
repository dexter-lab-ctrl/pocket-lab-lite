#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

SOURCE_PATTERNS = [
    "architecture/structurizr/workspace.dsl",
    "contracts/generated/openapi.json",
    "contracts/asyncapi/pocketlab-nats-jetstream.yaml",
    "contracts/operations/pocketlab-typed-operations.json",
    "operations/*.yaml",
]

GENERATED_OUTPUTS = [
    "threat-model/pocketlab-threat-model.yaml",
    "docs/security/security-architecture-threat-model.md",
    "docs/security/generated/threat-model/pocketlab-threat-model.json",
    "docs/security/generated/threat-model/index.md",
]

MANIFEST = ROOT / "threat-model/pocketlab-threat-model-drift-manifest.json"
DRIFT_DOC = ROOT / "docs/security/generated/threat-model/drift-detection.md"


@dataclass(frozen=True)
class FileFingerprint:
    path: str
    sha256: str
    bytes: int


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def expand_patterns(patterns: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        matches = sorted(ROOT.glob(pattern))
        files.extend(path for path in matches if path.is_file())
    unique: dict[str, Path] = {rel(path): path for path in files}
    return [unique[key] for key in sorted(unique)]


def fingerprint_files(paths: list[Path]) -> list[FileFingerprint]:
    results: list[FileFingerprint] = []
    for path in paths:
        results.append(
            FileFingerprint(
                path=rel(path),
                sha256=sha256_file(path),
                bytes=path.stat().st_size,
            )
        )
    return results


def combined_fingerprint(items: list[FileFingerprint]) -> str:
    payload = json.dumps(
        [item.__dict__ for item in items],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_fingerprints() -> list[FileFingerprint]:
    return fingerprint_files(expand_patterns(SOURCE_PATTERNS))


def output_fingerprints() -> list[FileFingerprint]:
    paths = [ROOT / item for item in GENERATED_OUTPUTS if (ROOT / item).exists()]
    return fingerprint_files(paths)


def current_manifest_payload() -> dict[str, Any]:
    sources = source_fingerprints()
    outputs = output_fingerprints()
    return {
        "apiVersion": "pocketlab.io/v1alpha1",
        "kind": "ThreatModelDriftManifest",
        "metadata": {
            "name": "pocketlab-threat-model-drift-manifest",
            "tier": "6.8",
            "description": "Detects stale threat-model artifacts when architecture, contracts, or operation metadata change.",
        },
        "source_patterns": SOURCE_PATTERNS,
        "generated_outputs": GENERATED_OUTPUTS,
        "source_files": [item.__dict__ for item in sources],
        "generated_output_files": [item.__dict__ for item in outputs],
        "source_fingerprint": combined_fingerprint(sources),
        "generated_output_fingerprint": combined_fingerprint(outputs),
        "validation_commands": [
            "task docs:threat-model:drift",
            "task docs:threat-model:check",
            "mkdocs build --strict",
        ],
        "remediation_commands": [
            "task docs:threat-model",
            "task docs:threat-model:drift:seal",
            "task docs:threat-model:drift",
        ],
    }


def load_manifest() -> dict[str, Any]:
    if not MANIFEST.exists():
        raise FileNotFoundError(f"Missing drift manifest: {rel(MANIFEST)}")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def by_path(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["path"]): item for item in items}


def compare_files(recorded: list[dict[str, Any]], current: list[FileFingerprint]) -> dict[str, list[str]]:
    recorded_by_path = by_path(recorded)
    current_by_path = {item.path: item.__dict__ for item in current}

    missing = sorted(set(recorded_by_path) - set(current_by_path))
    added = sorted(set(current_by_path) - set(recorded_by_path))
    changed = sorted(
        path
        for path in set(recorded_by_path) & set(current_by_path)
        if recorded_by_path[path].get("sha256") != current_by_path[path].get("sha256")
    )

    return {"missing": missing, "added": added, "changed": changed}
