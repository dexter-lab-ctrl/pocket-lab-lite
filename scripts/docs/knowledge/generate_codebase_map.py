#!/usr/bin/env python3
"""Generate the deterministic Pocket Lab Lite Documentation Platform Codebase Map.

The generator is deliberately repository/static only. Git owns physical structure;
source parsers add deterministic facts; existing Knowledge and Architecture contracts
add semantics. It never probes runtime services, calls remote APIs, or mutates runtime.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict, deque
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = "scripts/docs/knowledge/generate_codebase_map.py"
SCHEMA_VERSION = "1.0.0"
GENERATOR_VERSION = 1
SOURCE_COMMIT = os.environ.get("SOURCE_COMMIT", "").strip() or "uncommitted"
SCHEMA = ROOT / "schemas/knowledge/repository-codebase-map.schema.json"
OUT = ROOT / "contracts/generated/knowledge/repository-codebase-map.json"
DELTA_OUT = ROOT / "contracts/generated/knowledge/repository-codebase-delta.json"
BROWSER_OUT = ROOT / "docs/generated/assets/knowledge/repository-codebase-map.json"
PAGE_OUT = ROOT / "docs/generated/development/knowledge/codebase-map.md"
SELF_OUTPUT_PATHS = {
    "contracts/generated/knowledge/repository-codebase-map.json",
    "contracts/generated/knowledge/repository-codebase-delta.json",
    "docs/generated/assets/knowledge/repository-codebase-map.json",
    "docs/generated/development/knowledge/codebase-map.md",
}
KNOWLEDGE = ROOT / "contracts/generated/knowledge/index.json"
REPOSITORY_MAP = ROOT / "contracts/generated/knowledge/repository-map.json"
ARCH = ROOT / "architecture/metadata/pocket-lab-architecture.json"
TASKFILES = (ROOT / "Taskfile.yml", *sorted((ROOT / "tasks").glob("Taskfile*.yml")))

PRIVATE_PATH = re.compile(r"(?:^|[\s\"\'])((?:/home/[^/\s]+|/data/data/com\.termux/files/(?:home|usr)|/mnt/[a-zA-Z]/|[A-Za-z]:\\Users\\))")
SECRET = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|Bearer\s+[A-Za-z0-9._~+/-]{12,}|"
    r"(?:password|passwd|token|secret|api[_-]?key|credential|authorization)\s*[=:]\s*[^\s,}\]]{6,}|"
    r"nats://[^\s/@]+:[^\s/@]+@)", re.I,
)
ENV_NAME = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".mjs", ".ts", ".tsx", ".json", ".yaml", ".yml", ".md", ".markdown",
    ".sh", ".bash", ".html", ".css", ".scss", ".toml", ".ini", ".cfg", ".txt", ".ps1",
}
LANGUAGE_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JSX", ".mjs": "JavaScript", ".ts": "TypeScript", ".tsx": "TSX",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".md": "Markdown", ".markdown": "Markdown",
    ".sh": "Shell", ".bash": "Shell", ".html": "HTML", ".css": "CSS", ".scss": "SCSS",
    ".toml": "TOML", ".ini": "INI", ".cfg": "Config", ".ps1": "PowerShell",
}
RELATION_TYPES = {
    "CONTAINS", "DEFINES", "IMPORTS", "TESTED_BY", "GENERATED_BY", "GENERATES", "CONFIGURED_BY",
    "DOCUMENTED_BY", "DEPENDS_ON", "USED_BY", "MAPS_TO_KNOWLEDGE", "MAPS_TO_ARCHITECTURE",
    "MAPS_TO_TRUST_BOUNDARY", "INVOKED_BY_TASK",
}
CRITICAL_PREFIXES = (
    "src/", "pocket-lab-final-structure/", "architecture/", "contracts/", "scripts/", ".github/workflows/", "tasks/",
)
MAX_PARSE_BYTES = 1_000_000
MAX_PURPOSE = 280
MAX_SYMBOLS_PER_FILE = 200


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, separators=(",", ": ")) + "\n"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_json(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def safe_text(label: str, text: str) -> None:
    if PRIVATE_PATH.search(text):
        raise ValueError(f"{label}: private host path leaked")
    if SECRET.search(text):
        raise ValueError(f"{label}: secret-like content leaked")


def run_git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip().splitlines()[-1:]}")
    return proc.stdout


def tracked_paths() -> list[str]:
    raw = run_git("ls-files", "-z")
    paths = sorted(p for p in raw.split("\0") if p)
    if not paths:
        raise RuntimeError("git ls-files returned no tracked files")
    for path in paths:
        normalize_repo_path(path)
    return paths


def normalize_repo_path(value: str) -> str:
    value = value.replace("\\", "/").strip()
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"unsafe repository path: {value!r}")
    parts = PurePosixPath(value).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"unsafe repository path: {value!r}")
    normalized = str(PurePosixPath(*parts))
    if PRIVATE_PATH.search(normalized):
        raise ValueError(f"private path leaked: {normalized}")
    return normalized


def path_id(path: str) -> str:
    return "path:." if path == "." else f"path:{path}"


def rel_id(kind: str, source: str, target: str) -> str:
    return "rel:" + hashlib.sha256(f"{kind}\0{source}\0{target}".encode()).hexdigest()[:20]


def symbol_id(language: str, path: str, identity: str) -> str:
    safe_identity = re.sub(r"\s+", " ", identity.strip())
    return f"symbol:{language.lower()}:{path}:{safe_identity}"


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def content_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def infer_language(path: str) -> str | None:
    name = PurePosixPath(path).name
    if name in {"Taskfile.yml", "Taskfile.yaml"} or name.startswith("Taskfile."):
        return "Taskfile YAML"
    if path.startswith(".github/workflows/") and PurePosixPath(path).suffix in {".yml", ".yaml"}:
        return "GitHub Actions YAML"
    return LANGUAGE_BY_EXT.get(PurePosixPath(path).suffix.lower())


def classify(path: str, language: str | None) -> tuple[str, list[str]]:
    p = path.lower()
    facets: set[str] = set()
    if PurePosixPath(path).name in {".gitignore", ".gitattributes", ".editorconfig", ".pre-commit-config.yaml"}:
        role = "Configuration"; facets |= {"development-only"}
    elif p.startswith("tests/") or "/tests/" in p or p.startswith("src/__tests__/") or re.search(r"(^|/)test[^/]*\.", p):
        role = "Test"; facets |= {"test", "development-only"}
    elif p.startswith(".github/workflows/"):
        role = "CI/CD"; facets |= {"ci-only", "development-only"}
    elif p.startswith("architecture/"):
        role = "Architecture"; facets |= {"documentation-only", "architecture"}
    elif p.startswith("schemas/"):
        role = "Schema"; facets |= {"contract", "documentation-only"}
    elif p.startswith("contracts/generated/"):
        role = "Generated contract"; facets |= {"generated", "contract", "documentation-only"}
    elif p.startswith("contracts/"):
        role = "Contract"; facets |= {"contract", "documentation-only"}
    elif p.startswith("docs/generated/"):
        role = "Generated documentation"; facets |= {"generated", "documentation-only"}
    elif p.startswith("docs/"):
        role = "Documentation"; facets |= {"documentation-only"}
    elif p.startswith("scripts/docs/"):
        role = "Build tooling"; facets |= {"development-only", "documentation-only"}
    elif p.startswith("scripts/dev/") or p.startswith("scripts/windows/"):
        role = "Development tooling"; facets |= {"development-only"}
    elif p.startswith("tasks/") or PurePosixPath(path).name == "Taskfile.yml":
        role = "Build tooling"; facets |= {"development-only"}
    elif p.startswith("security/"):
        role = "Security"; facets |= {"security-sensitive"}
    elif p.startswith("runbooks/"):
        role = "Runbook"; facets |= {"runtime", "security-sensitive"}
    elif p.startswith("operations/"):
        role = "Configuration"; facets |= {"runtime"}
    elif p.startswith("src/") or (language in {"HTML", "CSS"} and not p.startswith(("docs/", "tests/"))):
        role = "Frontend"; facets |= {"source", "runtime"}
    elif "/runtime/api_fastapi/" in p:
        role = "FastAPI"; facets |= {"source", "runtime", "production", "arm64-relevant", "termux-relevant"}
    elif "/runtime/workers/" in p or p.endswith("pocketlab_worker.py"):
        role = "Worker"; facets |= {"source", "runtime", "production", "arm64-relevant", "termux-relevant"}
    elif "/runtime/agents/" in p and "supervisor" in p:
        role = "Supervisor"; facets |= {"source", "runtime", "production", "arm64-relevant", "termux-relevant"}
    elif "/runtime/agents/" in p:
        role = "Node Agent"; facets |= {"source", "runtime", "production", "arm64-relevant", "termux-relevant"}
    elif p.startswith("pocket-lab-final-structure/"):
        role = "Application source"; facets |= {"source", "runtime", "production", "arm64-relevant", "termux-relevant"}
    elif PurePosixPath(path).name in {"package.json", "package-lock.json", "requirements-dev.txt", "requirements-docs.txt"} or "requirements" in PurePosixPath(path).name:
        role = "Dependency manifest"; facets |= {"development-only"}
    elif language in {"JSON", "YAML", "Taskfile YAML", "GitHub Actions YAML", "TOML", "INI", "Config"}:
        role = "Configuration"; facets.add("development-only")
    elif language == "Markdown":
        role = "Documentation"; facets.add("documentation-only")
    elif language in {"Python", "JavaScript", "JSX", "TypeScript", "TSX", "Shell", "PowerShell"}:
        role = "Application source"; facets.add("source")
    elif PurePosixPath(path).suffix.lower() in {".svg", ".png", ".jpg", ".jpeg", ".ico", ".woff", ".woff2"}:
        role = "Asset"; facets.add("asset")
    else:
        role = "Unknown"; facets.add("unvalidated")
    if p.startswith(".github/") or p.startswith("scripts/") or p.startswith("tasks/") or p.startswith("tests/"):
        facets.add("excluded-from-dist")
    elif p.startswith(("src/", "public/", "pocket-lab-final-structure/", "operations/", "runbooks/")):
        facets.add("included-in-dist")
    return role, sorted(facets)


def execution_owner(path: str, role: str) -> str:
    p = path.lower()
    if role == "Frontend": return "Browser"
    if role == "FastAPI": return "FastAPI"
    if role == "Worker": return "Worker"
    if role == "Node Agent": return "Node Agent"
    if role == "Supervisor": return "Supervisor"
    if "caddy" in p and role in {"Configuration", "Application source"}: return "Caddy"
    if role in {"Generated documentation", "Documentation", "Architecture", "Schema", "Generated contract", "Contract"}: return "Documentation-only"
    if role == "CI/CD": return "CI-only"
    if role == "Test": return "Test-only"
    if role in {"Build tooling", "Development tooling", "Dependency manifest"}: return "Build-only"
    if role == "Runbook": return "Worker"
    if role == "Asset": return "No runtime execution"
    if role == "Configuration": return "No runtime execution"
    return "Unknown"


def resolve_python_import(module: str, tracked: set[str]) -> str | None:
    candidate = module.replace(".", "/")
    for path in (f"{candidate}.py", f"{candidate}/__init__.py", f"pocket-lab-final-structure/runtime/{candidate}.py"):
        if path in tracked: return path
    return None


def resolve_relative_import(source: str, spec: str, tracked: set[str]) -> str | None:
    if not spec.startswith("."):
        return None
    base = PurePosixPath(source).parent
    joined = str(PurePosixPath(base, spec))
    joined = str(PurePosixPath(joined))
    candidates = [joined, *(joined + ext for ext in (".js", ".jsx", ".mjs", ".ts", ".tsx", ".json")), *(f"{joined}/index{ext}" for ext in (".js", ".jsx", ".ts", ".tsx"))]
    for candidate in candidates:
        normalized = str(PurePosixPath(candidate))
        if normalized in tracked: return normalized
    return None


def parse_python(path: str, text: str, tracked: set[str]) -> dict[str, Any]:
    tree = ast.parse(text)
    classes, functions, imports, symbols, routes = [], [], [], [], []
    docstring = ast.get_docstring(tree) or ""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name); symbols.append({"id": symbol_id("Python", path, node.name), "name": node.name, "qualified_name": node.name, "kind": "class", "definition": {"line": node.lineno}, "confidence": "source-derived"})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name; functions.append(name); symbols.append({"id": symbol_id("Python", path, name), "name": name, "qualified_name": name, "kind": "function", "definition": {"line": node.lineno}, "confidence": "source-derived"})
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute) and dec.func.attr in {"get", "post", "put", "patch", "delete"} and dec.args and isinstance(dec.args[0], ast.Constant) and isinstance(dec.args[0].value, str):
                    routes.append({"method": dec.func.attr.upper(), "route": dec.args[0].value, "function": name, "line": node.lineno})
        elif isinstance(node, ast.Import):
            for alias in node.names:
                resolved = resolve_python_import(alias.name, tracked)
                imports.append({"module": alias.name, "path": resolved})
        elif isinstance(node, ast.ImportFrom) and node.module:
            resolved = resolve_python_import(node.module, tracked)
            imports.append({"module": node.module, "path": resolved})
    return {"docstring": docstring[:400], "classes": sorted(set(classes)), "functions": sorted(set(functions)), "imports": imports, "routes": routes, "symbols": symbols[:MAX_SYMBOLS_PER_FILE]}


JS_IMPORT = re.compile(r"(?:import\s+(?:[^;]+?\s+from\s+)?|require\s*\()\s*['\"]([^'\"]+)['\"]")
JS_EXPORT = re.compile(r"\bexport\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+([A-Za-z_$][\w$]*)")
JS_FUNC = re.compile(r"\b(?:function\s+([A-Za-z_$][\w$]*)\s*\(|(?:const|let)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)")
JS_CLASS = re.compile(r"\bclass\s+([A-Za-z_$][\w$]*)")


def parse_javascript(path: str, text: str, tracked: set[str], language: str) -> dict[str, Any]:
    imports = []
    for spec in JS_IMPORT.findall(text):
        imports.append({"module": spec, "path": resolve_relative_import(path, spec, tracked)})
    exports = sorted(set(JS_EXPORT.findall(text)))
    names = set(exports)
    for a, b in JS_FUNC.findall(text): names.add(a or b)
    names.update(JS_CLASS.findall(text))
    symbols = []
    for name in sorted(x for x in names if x):
        match = re.search(rf"\b{re.escape(name)}\b", text)
        line = text[: match.start()].count("\n") + 1 if match else 1
        kind = "component" if name[:1].isupper() and language in {"JSX", "TSX"} else ("hook" if name.startswith("use") else "symbol")
        symbols.append({"id": symbol_id(language, path, name), "name": name, "qualified_name": name, "kind": kind, "definition": {"line": line}, "confidence": "source-derived"})
    technologies = []
    for needle, label in (("useQuery", "TanStack Query"), ("create(", "Zustand"), ("createMachine", "XState"), ("Dexie", "Dexie"), ("react", "React")):
        if needle in text: technologies.append(label)
    return {"exports": exports, "imports": imports, "symbols": symbols[:MAX_SYMBOLS_PER_FILE], "technologies": sorted(set(technologies))}


def parse_yaml(path: str, text: str) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(text) or {}
    except yaml.constructor.ConstructorError:
        # MkDocs legitimately uses repository-owned Python-name tags; BaseLoader keeps
        # the introspection deterministic without executing constructors.
        payload = yaml.load(text, Loader=yaml.BaseLoader) or {}
    result: dict[str, Any] = {"top_level_keys": sorted(map(str, payload.keys())) if isinstance(payload, dict) else []}
    if isinstance(payload, dict) and "tasks" in payload and isinstance(payload["tasks"], dict):
        result["tasks"] = sorted(str(x) for x in payload["tasks"])
    if path.startswith(".github/workflows/") and isinstance(payload, dict):
        result["workflow_name"] = str(payload.get("name") or "")[:200]
        result["jobs"] = sorted(map(str, (payload.get("jobs") or {}).keys())) if isinstance(payload.get("jobs"), dict) else []
    return result


def parse_markdown(text: str) -> dict[str, Any]:
    frontmatter: dict[str, str] = {}
    body = text
    if text.startswith("---\n") and "\n---\n" in text[4:]:
        raw, body = text[4:].split("\n---\n", 1)
        try:
            parsed = yaml.safe_load(raw) or {}
            if isinstance(parsed, dict):
                for key in ("title", "description", "audience", "generator", "generated", "confidence"):
                    if key in parsed: frontmatter[key] = str(parsed[key])[:400]
        except yaml.YAMLError:
            pass
    h1 = next((line[2:].strip() for line in body.splitlines() if line.startswith("# ")), "")
    return {"frontmatter": frontmatter, "title": h1[:300]}


def parse_shell(text: str) -> dict[str, Any]:
    functions = sorted(set(re.findall(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{", text)))
    env_names = sorted({name for name in ENV_NAME.findall(text) if any(prefix in name for prefix in ("POCKET", "LITE", "NATS", "TAIL", "CADDY", "PM2", "SOURCE_"))})
    return {"functions": functions[:200], "environment_names": env_names[:200]}


def analyze_file(path: str, tracked: set[str]) -> dict[str, Any]:
    absolute = ROOT / path
    language = infer_language(path)
    generated_projection = path.startswith(("contracts/generated/", "docs/generated/"))
    if path in SELF_OUTPUT_PATHS:
        return {
            "language": language, "size_bytes": None, "content_sha256": None, "loc": None,
            "classes": [], "functions": [], "exports": [], "imports": [], "entry_point": False,
            "generated": True, "analysis_status": "generated-self",
            "analysis_reason": "self_referential_generated_output_excluded_from_content_fingerprint",
        }
    stat = absolute.stat()
    facts: dict[str, Any] = {
        "language": language, "size_bytes": stat.st_size, "content_sha256": content_sha(absolute), "loc": None,
        "classes": [], "functions": [], "exports": [], "imports": [], "entry_point": False, "generated": False,
        "analysis_status": "not-applicable" if language is None else "ok", "analysis_reason": None,
    }
    if generated_projection:
        # Generated projections are inventory nodes, not canonical source inputs.
        # Their rendered bytes intentionally do not participate in the Codebase Map
        # fingerprint, preventing deterministic generator-order cycles while keeping
        # every Git-tracked generated path visible and attributable to its producer.
        facts.update({
            "size_bytes": None, "content_sha256": None, "loc": None, "generated": True,
            "analysis_status": "generated-projection",
            "analysis_reason": "generated_projection_content_excluded_from_source_fingerprint",
        })
        if language in {"JSON", "Markdown"} and stat.st_size <= MAX_PARSE_BYTES:
            try:
                text = absolute.read_text(encoding="utf-8", errors="strict")
                if language == "JSON":
                    data = json.loads(text)
                    if isinstance(data, dict) and data.get("generator"):
                        facts["generator"] = str(data["generator"])[:400]
                else:
                    meta = parse_markdown(text)
                    generator = (meta.get("frontmatter") or {}).get("generator")
                    if generator:
                        facts["frontmatter"] = {"generator": str(generator)[:400], "generated": "true"}
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                pass
        return facts
    if language in {"Markdown", "JSON"}:
        lower = path.lower()
        facts["generated"] = lower.startswith(("docs/generated/", "contracts/generated/"))
    if language is None or absolute.suffix.lower() not in TEXT_EXTENSIONS and language not in {"Taskfile YAML", "GitHub Actions YAML"}:
        return facts
    if stat.st_size > MAX_PARSE_BYTES:
        facts["analysis_status"] = "skipped"
        facts["analysis_reason"] = "file_too_large_for_bounded_introspection"
        return facts
    try:
        text = absolute.read_text(encoding="utf-8", errors="strict")
        facts["loc"] = len(text.splitlines())
        safe_text(f"source:{path}", "")  # source is never emitted; only validate generated values below.
        extra: dict[str, Any] = {}
        if language == "Python": extra = parse_python(path, text, tracked)
        elif language in {"JavaScript", "JSX", "TypeScript", "TSX"}: extra = parse_javascript(path, text, tracked, language)
        elif language in {"YAML", "Taskfile YAML", "GitHub Actions YAML"}: extra = parse_yaml(path, text)
        elif language == "JSON":
            data = json.loads(text)
            extra = {"top_level_keys": sorted(map(str, data.keys())) if isinstance(data, dict) else [], "schema_version": str(data.get("schema_version")) if isinstance(data, dict) and data.get("schema_version") is not None else None, "generator": str(data.get("generator")) if isinstance(data, dict) and data.get("generator") else None}
        elif language == "Markdown": extra = parse_markdown(text)
        elif language in {"Shell", "PowerShell"}: extra = parse_shell(text)
        facts.update(extra)
        facts["classes"] = facts.get("classes", [])
        facts["functions"] = facts.get("functions", [])
        facts["exports"] = facts.get("exports", [])
        facts["imports"] = facts.get("imports", [])
        facts["entry_point"] = "__main__" in text if language == "Python" else False
        # Generated ownership is trusted only from repository-owned metadata/frontmatter.
        if language == "JSON" and facts.get("generator"): facts["generated"] = True
        if language == "Markdown" and facts.get("frontmatter", {}).get("generated", "").lower() == "true": facts["generated"] = True
    except (UnicodeDecodeError, SyntaxError, json.JSONDecodeError, yaml.YAMLError, ValueError) as exc:
        facts["analysis_status"] = "failed"
        facts["analysis_reason"] = type(exc).__name__.lower()
    return facts


def semantic_inputs() -> tuple[dict[str, Any], dict[str, Any], dict[str, list[str]]]:
    knowledge = read_json(KNOWLEDGE, {"entities": [], "relations": []})
    arch = read_json(ARCH, {"components": {}, "boundaries": {}})
    repo_map_raw = read_json(REPOSITORY_MAP, {"items": []})
    repo_map: dict[str, list[str]] = {}
    for item in repo_map_raw.get("items", []):
        source = str(item.get("source") or "")
        if source:
            repo_map[source] = sorted(set(map(str, item.get("entities") or [])))
    return knowledge, arch, repo_map


def architecture_paths(arch: dict[str, Any]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    paths: dict[str, list[str]] = defaultdict(list)
    boundaries: dict[str, list[str]] = defaultdict(list)
    for component_id, component in sorted((arch.get("components") or {}).items()):
        for item in component.get("source_verification") or []:
            if item.get("kind") != "path": continue
            value = str(item.get("value") or "")
            if not value or value.startswith("/"): continue
            try: value = normalize_repo_path(value)
            except ValueError: continue
            paths[value].append(component_id)
            boundary = component.get("security_boundary")
            if boundary: boundaries[value].append(str(boundary))
    return {k: sorted(set(v)) for k, v in paths.items()}, {k: sorted(set(v)) for k, v in boundaries.items()}


def knowledge_sources(knowledge: dict[str, Any], repo_map: dict[str, list[str]]) -> dict[str, list[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    for path, ids in repo_map.items():
        result[path].update(ids)
    for entity in knowledge.get("entities", []):
        eid = str(entity.get("id") or "")
        for source in entity.get("source_refs") or []:
            source = str(source)
            if source and not source.startswith("/") and (ROOT / source).exists():
                result[source].add(eid)
    return {k: sorted(v) for k, v in result.items()}


def evidence_for_path(path: str, facts: dict[str, Any], knowledge_by_id: dict[str, dict[str, Any]], knowledge_ids: list[str], arch: dict[str, Any], arch_ids: list[str], role: str) -> tuple[dict[str, Any], str]:
    refs: list[str] = [path]
    purpose = ""
    responsibility = ""
    architectural_role = ""
    confidence = "path-derived"
    for cid in arch_ids:
        component = (arch.get("components") or {}).get(cid, {})
        if component.get("responsibility"):
            purpose = str(component.get("responsibility")); responsibility = purpose
            architectural_role = str(component.get("name") or cid)
            confidence = "contract-derived"
            refs += ["architecture/metadata/pocket-lab-architecture.json", f"architecture:{cid}"]
            break
    if not purpose:
        for eid in knowledge_ids:
            entity = knowledge_by_id.get(eid, {})
            description = entity.get("description") or entity.get("responsibility")
            if description:
                purpose = str(description); responsibility = str(entity.get("name") or description)
                confidence = "source-derived"
                refs += ["contracts/generated/knowledge/index.json", eid]
                break
    if not purpose:
        lang = facts.get("language") or "non-source"
        purpose = f"Tracked {lang} file classified as {role}; no stronger semantic purpose is currently proven by repository contracts."
        responsibility = "Repository-tracked file; deeper responsibility remains unvalidated."
        architectural_role = "Unvalidated"
    purpose = re.sub(r"\s+", " ", purpose).strip()[:MAX_PURPOSE]
    if not responsibility:
        responsibility = "Repository-tracked file; deeper responsibility remains unvalidated."
    if not architectural_role:
        architectural_role = "Unvalidated"
    evidence_payload: dict[str, Any] = {"path": path, "content_sha256": facts.get("content_sha256"), "knowledge": [], "architecture": []}
    for eid in knowledge_ids:
        entity = knowledge_by_id.get(eid)
        if entity: evidence_payload["knowledge"].append({"id": eid, "source_refs": entity.get("source_refs", []), "confidence": entity.get("confidence")})
    for cid in arch_ids:
        component = (arch.get("components") or {}).get(cid)
        if component: evidence_payload["architecture"].append({"id": cid, "responsibility": component.get("responsibility"), "verification_status": component.get("verification_status")})
    explanation = {
        "purpose": purpose, "responsibility": responsibility[:MAX_PURPOSE], "architectural_role": architectural_role[:160],
        "confidence": confidence, "status": "verified" if confidence in {"contract-derived", "source-derived"} else "source-derived",
        "evidence_refs": sorted(set(refs)), "evidence_hash": "sha256:" + digest(evidence_payload), "freshness_status": "current",
    }
    return explanation, confidence


def parse_tasks(tracked: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    tasks: dict[str, dict[str, Any]] = {}
    path_to_tasks: dict[str, set[str]] = defaultdict(set)
    for taskfile in TASKFILES:
        if not taskfile.exists(): continue
        try: payload = yaml.safe_load(taskfile.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError: continue
        for name, spec in sorted((payload.get("tasks") or {}).items()):
            if not isinstance(spec, dict): continue
            commands: list[str] = []
            for item in spec.get("cmds") or []:
                if isinstance(item, str): commands.append(item)
                elif isinstance(item, dict): commands.append(str(item.get("cmd") or item.get("task") or ""))
            joined = "\n".join(commands)
            task_id = f"task:{name}"
            tasks[task_id] = {"id": task_id, "name": str(name), "source": str(taskfile.relative_to(ROOT)), "description": str(spec.get("desc") or "")[:300]}
            for path in tracked:
                if path in joined: path_to_tasks[path].add(task_id)
    return tasks, {k: sorted(v) for k, v in path_to_tasks.items()}


def generated_producer(path: str, facts: dict[str, Any], tracked: set[str]) -> str | None:
    gen = facts.get("generator")
    if isinstance(gen, str) and gen in tracked: return gen
    fm = facts.get("frontmatter") or {}
    gen = fm.get("generator") if isinstance(fm, dict) else None
    if isinstance(gen, str) and gen in tracked: return gen
    return None


def build_model() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    files = tracked_paths()
    tracked = set(files)
    knowledge, arch, repo_map = semantic_inputs()
    knowledge_by_id = {str(x.get("id")): x for x in knowledge.get("entities", []) if x.get("id")}
    knowledge_paths = knowledge_sources(knowledge, repo_map)
    arch_paths, boundary_paths = architecture_paths(arch)
    tasks, path_tasks = parse_tasks(tracked)

    nodes_by_id: dict[str, dict[str, Any]] = {}
    relations: dict[str, dict[str, Any]] = {}
    external_entities: dict[str, dict[str, Any]] = {}
    parsed_files = parser_failures = 0

    def add_relation(kind: str, source: str, target: str, evidence: Iterable[str] = (), confidence: str = "source-derived") -> None:
        if kind not in RELATION_TYPES: raise ValueError(f"unsupported relationship {kind}")
        rid = rel_id(kind, source, target)
        relations[rid] = {"id": rid, "type": kind, "source": source, "target": target, "evidence_refs": sorted(set(evidence)), "confidence": confidence}

    # Root and inferred directories are part of the physical Git tree projection.
    all_dirs: set[str] = {"."}
    for file_path in files:
        parent = PurePosixPath(file_path).parent
        while str(parent) not in {".", ""}:
            all_dirs.add(str(parent)); parent = parent.parent
    for directory in sorted(all_dirs, key=lambda p: (p.count("/"), p)):
        parent = None if directory == "." else ("." if str(PurePosixPath(directory).parent) == "." else str(PurePosixPath(directory).parent))
        nodes_by_id[path_id(directory)] = {
            "id": path_id(directory), "path": directory, "parent_id": path_id(parent) if parent else None, "kind": "directory",
            "role": "Repository" if directory == "." else "Directory", "facets": [], "execution_owner": "No runtime execution",
            "facts": {"file_count": 0, "descendant_count": 0, "child_count": 0},
            "explanation": {"purpose": "Repository root." if directory == "." else "Tracked directory inferred from Git-tracked paths.", "responsibility": "Contains repository-tracked descendants.", "architectural_role": "Repository structure", "confidence": "path-derived", "status": "source-derived", "evidence_refs": ["git ls-files"], "evidence_hash": "sha256:" + digest({"directory": directory}), "freshness_status": "current"},
            "architecture_refs": [], "trust_boundaries": [], "knowledge_refs": [], "critical": any(directory == x.rstrip("/") or directory.startswith(x) for x in CRITICAL_PREFIXES),
        }

    for path in files:
        facts = analyze_file(path, tracked)
        if facts.get("analysis_status") == "ok": parsed_files += 1
        if facts.get("analysis_status") == "failed": parser_failures += 1
        role, facets = classify(path, facts.get("language"))
        arch_ids = arch_paths.get(path, [])
        boundary_ids = boundary_paths.get(path, [])
        knowledge_ids = knowledge_paths.get(path, [])
        explanation, confidence = evidence_for_path(path, facts, knowledge_by_id, knowledge_ids, arch, arch_ids, role)
        parent = "." if str(PurePosixPath(path).parent) == "." else str(PurePosixPath(path).parent)
        node = {
            "id": path_id(path), "path": path, "parent_id": path_id(parent), "kind": "file", "role": role, "facets": facets,
            "execution_owner": execution_owner(path, role), "facts": facts, "explanation": explanation,
            "architecture_refs": [f"architecture:{x}" for x in arch_ids], "trust_boundaries": [f"boundary:{x}" for x in boundary_ids],
            "knowledge_refs": knowledge_ids, "critical": path.startswith(CRITICAL_PREFIXES),
        }
        nodes_by_id[node["id"]] = node
        add_relation("CONTAINS", node["parent_id"], node["id"], ["git ls-files"], "verified")
        for kid in knowledge_ids:
            external_entities[kid] = {"id": kid, "kind": "knowledge", "name": str(knowledge_by_id.get(kid, {}).get("name") or kid)}
            add_relation("MAPS_TO_KNOWLEDGE", node["id"], kid, ["contracts/generated/knowledge/index.json", path], confidence)
        for cid in arch_ids:
            eid = f"architecture:{cid}"; component = (arch.get("components") or {}).get(cid, {})
            external_entities[eid] = {"id": eid, "kind": "architecture", "name": str(component.get("name") or cid)}
            add_relation("MAPS_TO_ARCHITECTURE", node["id"], eid, ["architecture/metadata/pocket-lab-architecture.json", path], "contract-derived")
        for bid in boundary_ids:
            eid = f"boundary:{bid}"; boundary = (arch.get("boundaries") or {}).get(bid, {})
            external_entities[eid] = {"id": eid, "kind": "trust-boundary", "name": str(boundary.get("name") or bid)}
            add_relation("MAPS_TO_TRUST_BOUNDARY", node["id"], eid, ["architecture/metadata/pocket-lab-architecture.json"], "contract-derived")
        for task_id in path_tasks.get(path, []):
            external_entities[task_id] = {**tasks[task_id], "kind": "task"}
            add_relation("INVOKED_BY_TASK", node["id"], task_id, [tasks[task_id]["source"]], "source-derived")
        producer = generated_producer(path, facts, tracked)
        if producer:
            add_relation("GENERATED_BY", node["id"], path_id(producer), [path, producer], "source-derived")
            add_relation("GENERATES", path_id(producer), node["id"], [path, producer], "source-derived")
        for imp in facts.get("imports") or []:
            target = imp.get("path") if isinstance(imp, dict) else None
            if target in tracked:
                add_relation("IMPORTS", node["id"], path_id(target), [path], "source-derived")

        for symbol in facts.get("symbols") or []:
            external_entities[symbol["id"]] = {"id": symbol["id"], "kind": "symbol", "name": symbol["name"], "file_id": node["id"], "definition": symbol.get("definition"), "symbol_kind": symbol.get("kind"), "confidence": symbol.get("confidence")}
            add_relation("DEFINES", node["id"], symbol["id"], [path], "source-derived")
        # Symbol details live in the normalized semantic entity table; facts keep
        # deterministic file summaries only to avoid duplicating thousands of rows.
        facts.pop("symbols", None)

    # Directory containments and aggregates.
    for directory in sorted(all_dirs - {"."}):
        node = nodes_by_id[path_id(directory)]
        add_relation("CONTAINS", node["parent_id"], node["id"], ["git ls-files"], "verified")
    children: dict[str, list[str]] = defaultdict(list)
    for node in nodes_by_id.values():
        if node.get("parent_id"): children[node["parent_id"]].append(node["id"])
    for node in nodes_by_id.values():
        if node["kind"] != "directory": continue
        prefix = "" if node["path"] == "." else node["path"] + "/"
        descendants = [x for x in nodes_by_id.values() if x["id"] != node["id"] and (node["path"] == "." or x["path"].startswith(prefix))]
        node["facts"]["file_count"] = sum(1 for x in descendants if x["kind"] == "file")
        node["facts"]["descendant_count"] = len(descendants)
        node["facts"]["child_count"] = len(children.get(node["id"], []))
        roles = Counter(x["role"] for x in descendants if x["kind"] == "file")
        node["facts"]["roles"] = dict(sorted(roles.items()))
        node["explanation"]["purpose"] = ("Repository root containing all Git-tracked files." if node["path"] == "." else f"Tracked directory containing {node['facts']['file_count']} Git-tracked files; semantics are aggregated from descendants, not inferred from the directory name.")
        node["explanation"]["evidence_hash"] = "sha256:" + digest({"path": node["path"], "children": sorted(children.get(node["id"], [])), "roles": node["facts"]["roles"]})

    # Existing Knowledge cross-reference test ownership -> source files.
    cross = read_json(ROOT / "contracts/generated/knowledge/cross-references.json", {"items": {}})
    cross_items = cross.get("items", {}) if isinstance(cross, dict) else {}
    outgoing = cross_items.get("outgoing", {}) if isinstance(cross_items, dict) else {}
    for source_path, entity_ids in knowledge_paths.items():
        if source_path not in tracked: continue
        for eid in entity_ids:
            for edge in outgoing.get(eid, []) if isinstance(outgoing, dict) else []:
                if edge.get("type") != "verified_by": continue
                target_id = str(edge.get("target") or "")
                test_path = target_id.removeprefix("test:")
                if test_path in tracked:
                    add_relation("TESTED_BY", path_id(source_path), path_id(test_path), ["contracts/generated/knowledge/cross-references.json", eid], "contract-derived")

    nodes = sorted(nodes_by_id.values(), key=lambda x: (x["path"] != ".", x["path"]))
    relation_list = sorted(relations.values(), key=lambda x: (x["type"], x["source"], x["target"], x["id"]))

    by_role: dict[str, list[str]] = defaultdict(list); by_language: dict[str, list[str]] = defaultdict(list); by_owner: dict[str, list[str]] = defaultdict(list); by_conf: dict[str, list[str]] = defaultdict(list)
    rel_from: dict[str, list[str]] = defaultdict(list); rel_to: dict[str, list[str]] = defaultdict(list); symbols_by_file: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        by_role[node["role"]].append(node["id"]); by_owner[node["execution_owner"]].append(node["id"]); by_conf[node["explanation"]["confidence"]].append(node["id"])
        lang = node.get("facts", {}).get("language")
        if lang: by_language[lang].append(node["id"])
    for relation in relation_list:
        rel_from[relation["source"]].append(relation["id"]); rel_to[relation["target"]].append(relation["id"])
        if relation["type"] == "DEFINES": symbols_by_file[relation["source"]].append(relation["target"])

    file_nodes = [x for x in nodes if x["kind"] == "file"]
    explained = [x for x in file_nodes if x["explanation"]["confidence"] != "unvalidated"]
    critical = [x for x in file_nodes if x["critical"]]
    critical_explained = [x for x in critical if x["explanation"]["confidence"] != "unvalidated"]
    mapped_arch = [x for x in file_nodes if x["architecture_refs"]]
    tested = {r["source"] for r in relation_list if r["type"] == "TESTED_BY"}
    relationship_sources = {r["source"] for r in relation_list if r["source"].startswith("path:") and r["type"] != "CONTAINS"}
    health = {
        "tracked_files": len(file_nodes), "directories": sum(1 for x in nodes if x["kind"] == "directory"),
        "classified_paths": sum(1 for x in file_nodes if x["role"] != "Unknown"),
        "classified_percent": round(100 * sum(1 for x in file_nodes if x["role"] != "Unknown") / max(1, len(file_nodes)), 2),
        "explained_paths": len(explained), "explained_percent": round(100 * len(explained) / max(1, len(file_nodes)), 2),
        "critical_paths": len(critical), "critical_explained": len(critical_explained),
        "critical_explained_percent": round(100 * len(critical_explained) / max(1, len(critical)), 2),
        "parser_failures": parser_failures, "unvalidated_explanations": sum(1 for x in file_nodes if x["explanation"]["confidence"] == "unvalidated"),
        "relationship_coverage_percent": round(100 * len(relationship_sources) / max(1, len(file_nodes)), 2),
        "architecture_mapping_percent": round(100 * len(mapped_arch) / max(1, len(file_nodes)), 2),
        "test_mapping_percent": round(100 * len(tested) / max(1, len(file_nodes)), 2),
    }
    role_counts = dict(sorted(Counter(x["role"] for x in file_nodes).items()))
    language_counts = dict(sorted(Counter(x["facts"].get("language") or "Other" for x in file_nodes).items()))
    source_fingerprint = digest({x["path"]: x["facts"]["content_sha256"] for x in file_nodes})
    model = {
        "schema_version": SCHEMA_VERSION, "generator": GENERATOR, "generator_version": GENERATOR_VERSION,
        "source_commit": SOURCE_COMMIT, "source_tree": "sha256:" + source_fingerprint, "source_fingerprint": source_fingerprint,
        "statistics": {"tracked_files": len(file_nodes), "directories": health["directories"], "nodes": len(nodes), "relationships": len(relation_list), "symbols": len(symbols_by_file) and sum(map(len, symbols_by_file.values())) or 0, "parsed_files": parsed_files, "roles": role_counts, "languages": language_counts},
        "documentation_health": health,
        "topology": {"root_id": path_id("."), "architecture_source": "architecture/metadata/pocket-lab-architecture.json", "knowledge_source": "contracts/generated/knowledge/index.json", "repository_inventory": "git ls-files", "external_entities": dict(sorted(external_entities.items()))},
        "nodes": nodes, "relationships": relation_list,
        "indexes": {"by_path": {x["path"]: x["id"] for x in nodes}, "children_by_parent": {k: sorted(v) for k, v in sorted(children.items())}, "relationships_from": {k: sorted(v) for k, v in sorted(rel_from.items())}, "relationships_to": {k: sorted(v) for k, v in sorted(rel_to.items())}, "by_role": {k: sorted(v) for k, v in sorted(by_role.items())}, "by_language": {k: sorted(v) for k, v in sorted(by_language.items())}, "by_execution_owner": {k: sorted(v) for k, v in sorted(by_owner.items())}, "by_confidence": {k: sorted(v) for k, v in sorted(by_conf.items())}, "symbols_by_file": {k: sorted(v) for k, v in sorted(symbols_by_file.items())}},
        "delta": {"status": "clean", "added_paths": [], "removed_paths": [], "changed_paths": [], "classification_changes": [], "relationship_changes": []},
        "capabilities": {"tree": "verified", "search": "verified", "deep_links": "verified", "uses_used_by": "verified", "impact_analysis": "bounded-static", "symbol_navigation": "basic-native", "git_hotspots": "unavailable", "scip": {"status": "unavailable", "semantic_precision": "basic", "required": False}, "live_runtime": False},
    }
    validate_model(model, tracked)
    browser = build_browser_projection(model)
    elapsed = time.perf_counter() - started
    report = {"tracked_files": len(file_nodes), "parsed_files": parsed_files, "relationships": len(relation_list), "duration_seconds": round(elapsed, 3), "browser_bytes": len((canonical_json(browser) + "\n").encode("utf-8"))}
    return model, browser, report


def validate_model(model: dict[str, Any], tracked: set[str]) -> None:
    jsonschema.Draft202012Validator(read_json(SCHEMA)).validate(model)
    nodes = model["nodes"]; node_ids = {x["id"] for x in nodes}; by_path = model["indexes"]["by_path"]
    files = {x["path"] for x in nodes if x["kind"] == "file"}
    if files != tracked:
        missing = sorted(tracked - files)[:20]; extra = sorted(files - tracked)[:20]
        raise ValueError(f"tracked file/model mismatch missing={missing} extra={extra}")
    if len(node_ids) != len(nodes): raise ValueError("duplicate node IDs")
    if len(by_path) != len(nodes): raise ValueError("duplicate paths")
    external = set(model["topology"]["external_entities"])
    for node in nodes:
        if node["path"] != ".": normalize_repo_path(node["path"])
        if node.get("parent_id") and node["parent_id"] not in node_ids: raise ValueError(f"orphan node {node['id']}")
        safe_text(node["id"], canonical_json(node))
    for rel in model["relationships"]:
        if rel["source"] not in node_ids and rel["source"] not in external: raise ValueError(f"missing relation source {rel['id']}")
        if rel["target"] not in node_ids and rel["target"] not in external: raise ValueError(f"missing relation target {rel['id']}")
    if model["documentation_health"]["critical_explained"] != model["documentation_health"]["critical_paths"]:
        raise ValueError("critical Codebase Map paths must not be unexplained")
    for parent, children in model["indexes"]["children_by_parent"].items():
        if parent not in node_ids: raise ValueError(f"unknown parent index {parent}")
        for child in children:
            if child not in node_ids: raise ValueError(f"unknown child index {child}")
    safe_text("canonical codebase map", canonical_json(model))


def build_browser_projection(model: dict[str, Any]) -> dict[str, Any]:
    external = model["topology"]["external_entities"]
    nodes = []
    for node in model["nodes"]:
        facts = node["facts"]
        symbols = []
        for sid in model["indexes"]["symbols_by_file"].get(node["id"], []):
            item = external.get(sid, {})
            symbols.append({"id": sid, "name": item.get("name"), "kind": item.get("symbol_kind"), "line": (item.get("definition") or {}).get("line")})
        nodes.append({
            "id": node["id"], "p": node["path"], "parent": node.get("parent_id"), "k": node["kind"], "r": node["role"], "f": node["facets"],
            "l": facts.get("language"), "o": node["execution_owner"], "c": node["explanation"]["confidence"], "s": node["explanation"]["freshness_status"],
            "purpose": node["explanation"]["purpose"], "arch": node["architecture_refs"], "boundaries": node["trust_boundaries"], "knowledge": node["knowledge_refs"],
            "symbols": symbols, "generated": bool(facts.get("generated")), "critical": bool(node.get("critical")), "loc": facts.get("loc"), "size": facts.get("size_bytes"),
        })
    # Browser relationships stay compact but retain external label metadata.
    rels = [{"id": r["id"], "t": r["type"], "a": r["source"], "b": r["target"], "c": r["confidence"]} for r in model["relationships"] if r["type"] != "DEFINES"]
    search = {}
    for node in nodes:
        external_terms = []
        for ref in node["arch"] + node["boundaries"] + node["knowledge"]:
            external_terms.append(str(external.get(ref, {}).get("name") or ref))
        symbol_terms = [str(x.get("name") or "") for x in node["symbols"]]
        tokens = " ".join([node["p"], PurePosixPath(node["p"]).name, node["purpose"], node["r"], node["l"] or "", node["o"], node["c"], *external_terms, *symbol_terms]).lower()
        search[node["id"]] = re.sub(r"[^a-z0-9_./:@ -]+", " ", tokens)[:900]
    projection = {
        "schema_version": "1.0.0", "source_fingerprint": model["source_fingerprint"], "root_id": model["topology"]["root_id"], "live_runtime": False,
        "statistics": model["statistics"], "documentation_health": model["documentation_health"], "nodes": nodes, "relationships": rels,
        "external": {k: {"kind": v.get("kind"), "name": v.get("name"), "source": v.get("source")} for k, v in external.items() if v.get("kind") != "symbol"},
        "indexes": {"by_path": model["indexes"]["by_path"], "children_by_parent": model["indexes"]["children_by_parent"], "relationships_from": model["indexes"]["relationships_from"], "relationships_to": model["indexes"]["relationships_to"], "search": search},
        "capabilities": model["capabilities"],
    }
    safe_text("browser codebase map", canonical_json(projection))
    return projection


def render_page(model: dict[str, Any]) -> str:
    health = model["documentation_health"]; stats = model["statistics"]
    def esc(v: Any) -> str: return html.escape(str(v))
    return (
        "---\n"
        'title: "Codebase Map"\n'
        'description: "Evidence-backed Git-tracked repository structure, ownership, relationships, symbols, and bounded impact analysis."\n'
        "generated: true\n"
        "audience: development\n"
        "confidence: source-derived\n"
        f"source_commit: {SOURCE_COMMIT}\n"
        f"generator: {GENERATOR}\n"
        "---\n\n"
        "# Codebase Map\n\n"
        '<div class="pl-page-lede"><strong>Understand what exists in Pocket Lab Lite, why it exists, and what is structurally connected to it.</strong><p>This is a static projection of Git-tracked repository structure plus deterministic source facts and existing Knowledge/Architecture contracts. It never scans the browser filesystem, probes runtime, calls GitHub, or invents missing semantics.</p></div>\n\n'
        '<div class="pl-kpi-grid pl-codebase-kpis" role="group" aria-label="Codebase documentation health">'
        f'<div class="pl-kpi"><span>Tracked files</span><strong>{stats["tracked_files"]}</strong><small>Git-owned inventory</small></div>'
        f'<div class="pl-kpi"><span>Folders</span><strong>{stats["directories"]}</strong><small>inferred from tracked paths</small></div>'
        f'<div class="pl-kpi"><span>Explained</span><strong>{health["explained_percent"]}%</strong><small>{health["unvalidated_explanations"]} unvalidated</small></div>'
        f'<div class="pl-kpi"><span>Critical coverage</span><strong>{health["critical_explained_percent"]}%</strong><small>{health["critical_paths"]} critical files</small></div>'
        "</div>\n\n"
        '<section class="pl-codebase-map" data-pl-codebase-map="true" '
        f'data-file-count="{stats["tracked_files"]}" data-node-count="{stats["nodes"]}" data-relationship-count="{stats["relationships"]}">'
        '<div class="pl-codebase-controls">'
        '<label class="pl-codebase-search">Search codebase<input type="search" data-cb-search autocomplete="off" placeholder="Path, purpose, role, symbol, task…"></label>'
        '<label>Role<select data-cb-role><option value="">All roles</option></select></label>'
        '<label>Language<select data-cb-language><option value="">All languages</option></select></label>'
        '<label>Owner<select data-cb-owner><option value="">All owners</option></select></label>'
        '<label>Confidence<select data-cb-confidence><option value="">All confidence</option></select></label>'
        '<button type="button" class="md-button" data-cb-collapse>Collapse all</button>'
        '</div>'
        '<div class="pl-codebase-layout">'
        '<div class="pl-codebase-tree" data-cb-tree role="tree" aria-label="Repository tree"><div class="pl-empty-state"><strong>Loading repository model</strong><p>Reading one same-origin generated asset.</p></div></div>'
        '<aside class="pl-codebase-inspector" data-cb-inspector aria-live="polite"><span class="pl-card-kicker">Inspector</span><strong>Select a file or folder</strong><p>Purpose, ownership, uses, used-by, tests, generated outputs, architecture, symbols, and bounded impact appear here.</p></aside>'
        '</div></section>\n\n'
        "## Documentation health\n\n"
        "| Metric | Value |\n| --- | ---: |\n"
        f'| Classified paths | {health["classified_percent"]}% |\n'
        f'| Relationship coverage | {health["relationship_coverage_percent"]}% |\n'
        f'| Architecture mapping | {health["architecture_mapping_percent"]}% |\n'
        f'| Test mapping | {health["test_mapping_percent"]}% |\n'
        f'| Parser failures | {health["parser_failures"]} |\n\n'
        "## Model boundaries\n\n"
        "- **Physical structure:** `git ls-files`; untracked/local runtime material is excluded.\n"
        "- **Facts:** deterministic parsers only; parser failures are explicit.\n"
        "- **Explanations:** existing Knowledge/Architecture evidence first; otherwise clearly path-derived.\n"
        "- **Impact:** bounded static dependency traversal; it does not claim runtime consequences.\n"
        "- **SCIP:** optional and currently unavailable; the core model does not depend on it.\n"
        "- **Git hotspots:** optional and currently unavailable; missing history is not treated as risk.\n\n"
        "## Related authoritative views\n\n"
        "- [Repository Map](repository-map.md) — reverse source→Knowledge lookup.\n"
        "- [Knowledge Graph](../../enterprise/knowledgebase/knowledge-graph.md) — semantic relationships.\n"
        "- [Architecture](../../production/architecture/index.md) — runtime/system operation.\n"
        "- [Change Impact Advisor](../../enterprise/reference/change-advisor.md) — deterministic change consequence advisor.\n"
    )


def clean_delta(model: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": "1.0.0", "generator": GENERATOR, "source_fingerprint": model["source_fingerprint"], "status": "clean", "added_paths": [], "removed_paths": [], "changed_paths": [], "classification_changes": [], "relationship_changes": [], "note": "Generated state matches the current Git-tracked repository model. Check mode computes drift against this tracked baseline before failing."}


def outputs_for(model: dict[str, Any], browser: dict[str, Any]) -> dict[Path, str]:
    return {OUT: canonical_json(model) + "\n", DELTA_OUT: stable_json(clean_delta(model)), BROWSER_OUT: canonical_json(browser) + "\n", PAGE_OUT: render_page(model).rstrip() + "\n"}


def write_outputs(outputs: dict[Path, str]) -> None:
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")


def structural_delta(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_nodes = {x["path"]: x for x in old.get("nodes", []) if x.get("kind") == "file"}
    new_nodes = {x["path"]: x for x in new.get("nodes", []) if x.get("kind") == "file"}
    added = sorted(set(new_nodes) - set(old_nodes)); removed = sorted(set(old_nodes) - set(new_nodes))
    changed = sorted(p for p in set(new_nodes) & set(old_nodes) if new_nodes[p].get("facts", {}).get("content_sha256") != old_nodes[p].get("facts", {}).get("content_sha256"))
    classification = sorted(p for p in set(new_nodes) & set(old_nodes) if (new_nodes[p].get("role"), new_nodes[p].get("execution_owner")) != (old_nodes[p].get("role"), old_nodes[p].get("execution_owner")))
    old_rel = {(r["type"], r["source"], r["target"]) for r in old.get("relationships", [])}; new_rel = {(r["type"], r["source"], r["target"]) for r in new.get("relationships", [])}
    return {"added_paths": added, "removed_paths": removed, "changed_paths": changed, "classification_changes": classification, "relationship_changes": {"added": len(new_rel-old_rel), "removed": len(old_rel-new_rel)}}


def check_outputs(outputs: dict[Path, str], current_model: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    baseline = None
    if OUT.exists():
        try: baseline = read_json(OUT)
        except Exception: baseline = None
    for path, expected in outputs.items():
        if not path.exists(): errors.append(f"missing {path.relative_to(ROOT)}")
        elif path.read_text(encoding="utf-8") != expected: errors.append(f"drift {path.relative_to(ROOT)}")
    if errors and baseline:
        delta = structural_delta(baseline, current_model)
        if delta["added_paths"]: errors.append("added paths: " + ", ".join(delta["added_paths"][:12]))
        if delta["removed_paths"]: errors.append("removed paths: " + ", ".join(delta["removed_paths"][:12]))
        if delta["changed_paths"]: errors.append("changed paths: " + ", ".join(delta["changed_paths"][:12]))
        if delta["classification_changes"]: errors.append("classification changes: " + ", ".join(delta["classification_changes"][:12]))
        rel = delta["relationship_changes"]
        if rel["added"] or rel["removed"]: errors.append(f"relationship graph changed: +{rel['added']} -{rel['removed']}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "check"))
    args = parser.parse_args()
    model, browser, report = build_model()
    outputs = outputs_for(model, browser)
    if args.mode == "generate":
        write_outputs(outputs)
        print(f"generated Codebase Map: {report['tracked_files']} tracked files, {report['parsed_files']} parsed, {report['relationships']} relationships, browser={report['browser_bytes']} bytes, {report['duration_seconds']}s")
        return 0
    errors = check_outputs(outputs, model)
    if errors:
        print("FAIL repository codebase map drift")
        for error in errors: print(f" - {error}")
        print("Run: task lite:docs:codebase-map:generate")
        return 1
    print(f"PASS Codebase Map: {report['tracked_files']} tracked files, {report['relationships']} relationships, browser={report['browser_bytes']} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
