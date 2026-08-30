"""Bounded repository-status and changed-files developer operations."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal

from ..runner import ProcessResult, ProcessRunner

ChangedFilesScope = Literal["working_tree", "branch_vs_origin_main"]
CATEGORY_NAMES = (
    "backend",
    "frontend",
    "tests",
    "docs",
    "contracts",
    "tooling",
    "scripts",
    "other",
)


def classify_path(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("./")
    if normalized.startswith("tests/"):
        return "tests"
    if normalized.startswith(("docs/", "engineering/")):
        return "docs"
    if normalized.startswith("contracts/"):
        return "contracts"
    if normalized.startswith(("tools/", ".codex/")):
        return "tooling"
    if normalized.startswith("scripts/"):
        return "scripts"
    if normalized.startswith(("frontend/", "web/", "ui/")):
        return "frontend"
    if normalized.startswith(("runtime/", "pocket-lab-final-structure/runtime/")):
        return "backend"
    return "other"


def _status_name(code: str) -> str:
    if code == "??":
        return "untracked"
    if "A" in code:
        return "added"
    if "D" in code:
        return "deleted"
    if "R" in code:
        return "renamed"
    if "C" in code:
        return "copied"
    if "M" in code:
        return "modified"
    return "changed"


class RepositoryTools:
    def __init__(self, repository_root: Path, runner: ProcessRunner | None = None) -> None:
        self.repository_root = repository_root.resolve()
        self.runner = runner or ProcessRunner(self.repository_root)

    def _git(self, *args: str) -> ProcessResult:
        return self.runner.run(("git", *args), timeout_seconds=30)

    @staticmethod
    def _required(result: ProcessResult, operation: str) -> str:
        if result.timed_out or result.exit_code != 0:
            detail = result.stderr_tail.strip() or result.stdout_tail.strip() or "no diagnostic"
            raise RuntimeError(f"{operation} failed: {detail}")
        # Preserve exact subprocess output here. Machine-readable Git formats
        # such as `status --porcelain=v1 -z` use leading spaces as meaningful
        # status bytes; stripping the whole stream corrupts the first record.
        # Scalar callers trim their own output explicitly.
        return result.stdout_tail

    def repo_status(self) -> dict[str, object]:
        top_level = self._required(
            self._git("rev-parse", "--show-toplevel"),
            "git root",
        ).strip()
        if Path(top_level).resolve() != self.repository_root:
            raise RuntimeError("git root does not match validated Pocket Lab repository root")

        branch = self._required(
            self._git("branch", "--show-current"),
            "git branch",
        ).strip()
        head = self._required(
            self._git("rev-parse", "HEAD"),
            "git HEAD",
        ).strip()
        origin_result = self._git("rev-parse", "--verify", "origin/main")
        origin_main = origin_result.stdout_tail.strip() if origin_result.exit_code == 0 else None
        status_result = self._git("status", "--porcelain=v1", "-z", "--untracked-files=all")
        status_output = self._required(status_result, "git status")
        if status_result.truncated:
            return {
                "repo_root": str(self.repository_root),
                "branch": branch or None,
                "head": head,
                "origin_main": origin_main,
                "clean": None,
                "staged_count": None,
                "unstaged_count": None,
                "untracked_count": None,
                "ahead": None,
                "behind": None,
                "detached_head": not bool(branch),
                "complete": False,
                "truncated": True,
            }
        status_records = [record for record in status_output.split("\0") if record]

        staged_count = 0
        unstaged_count = 0
        untracked_count = 0
        record_index = 0
        while record_index < len(status_records):
            record = status_records[record_index]
            code = record[:2]
            if code == "??":
                untracked_count += 1
            elif code[:1] not in {" ", "?"}:
                staged_count += 1
            if code[1:2] not in {" ", "?"}:
                unstaged_count += 1
            record_index += 2 if "R" in code or "C" in code else 1

        ahead = behind = None
        if origin_main is not None:
            counts = self._required(
                self._git("rev-list", "--left-right", "--count", "HEAD...origin/main"),
                "git ahead/behind",
            ).split()
            if len(counts) == 2:
                ahead, behind = (int(counts[0]), int(counts[1]))

        return {
            "repo_root": str(self.repository_root),
            "branch": branch or None,
            "head": head,
            "origin_main": origin_main,
            "clean": not status_records,
            "staged_count": staged_count,
            "unstaged_count": unstaged_count,
            "untracked_count": untracked_count,
            "ahead": ahead,
            "behind": behind,
            "detached_head": not bool(branch),
            "complete": True,
            "truncated": False,
        }

    def changed_files(self, scope: ChangedFilesScope = "working_tree") -> dict[str, object]:
        if scope == "working_tree":
            result = self._git("status", "--porcelain=v1", "-z", "--untracked-files=all")
            output = self._required(result, "git status")
            if result.truncated:
                return self._incomplete(scope)
            records = [record for record in output.split("\0") if record]
            parsed = []
            index = 0
            while index < len(records):
                record = records[index]
                code, path = record[:2], record[3:]
                parsed.append((code, path))
                index += 1
                if "R" in code or "C" in code:
                    # Porcelain -z supplies destination first, then source.
                    index += 1
        elif scope == "branch_vs_origin_main":
            has_origin = self._git("rev-parse", "--verify", "origin/main")
            if has_origin.exit_code != 0:
                return {
                    "status": "error",
                    "scope": scope,
                    "error": "origin/main is unavailable locally; no network fetch was attempted",
                    "total": 0,
                    "files": [],
                    "categories": {name: 0 for name in CATEGORY_NAMES},
                    "complete": True,
                    "truncated": False,
                }
            result = self._git("diff", "--name-status", "-z", "origin/main...HEAD")
            output = self._required(result, "git branch diff")
            if result.truncated:
                return self._incomplete(scope)
            records = [record for record in output.split("\0") if record]
            parsed = []
            index = 0
            while index < len(records):
                code = records[index]
                index += 1
                if index >= len(records):
                    raise RuntimeError("git branch diff returned an incomplete NUL record")
                path = records[index]
                index += 1
                if code.startswith(("R", "C")):
                    if index >= len(records):
                        raise RuntimeError("git branch diff returned an incomplete rename record")
                    path = records[index]
                    index += 1
                parsed.append((code, path))
        else:
            raise ValueError(f"unsupported changed-files scope: {scope}")

        files = [
            {
                "path": path,
                "status": _status_name(code),
                "category": classify_path(path),
            }
            for code, path in parsed
        ]
        counts = Counter(file["category"] for file in files)
        return {
            "scope": scope,
            "total": len(files),
            "files": files,
            "categories": {name: counts[name] for name in CATEGORY_NAMES},
            "complete": True,
            "truncated": False,
        }

    @staticmethod
    def _incomplete(scope: ChangedFilesScope) -> dict[str, object]:
        return {
            "status": "incomplete",
            "scope": scope,
            "total": None,
            "files": [],
            "categories": {name: None for name in CATEGORY_NAMES},
            "complete": False,
            "truncated": True,
        }
