from __future__ import annotations

import os
import pathlib
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from dulwich import porcelain  # type: ignore
    from dulwich.repo import Repo  # type: ignore

    DULWICH_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    porcelain = None
    Repo = None
    DULWICH_AVAILABLE = False


@dataclass
class RepoStatus:
    branch: Optional[str]
    last_commit: Optional[Dict[str, Any]]
    dirty: bool
    exists: bool


class DulwichRepository:
    def __init__(self, path: pathlib.Path):
        self.path = pathlib.Path(path)

    def _run_git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env.setdefault("GIT_AUTHOR_NAME", "Pocket Lab")
        env.setdefault("GIT_AUTHOR_EMAIL", "pocketlab@example.com")
        env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
        env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
        return subprocess.run(
            ["git", *args],
            cwd=str(self.path),
            env=env,
            check=check,
            capture_output=True,
            text=True,
        )

    def exists(self) -> bool:
        if (self.path / ".git").exists():
            return True
        try:
            result = self._run_git("rev-parse", "--git-dir", check=False)
            return result.returncode == 0
        except Exception:
            return False

    def open(self):
        if not self.exists() or not DULWICH_AVAILABLE:
            return None
        return Repo(str(self.path))

    def _git_branch(self) -> Optional[str]:
        try:
            result = self._run_git("rev-parse", "--abbrev-ref", "HEAD", check=False)
            if result.returncode == 0:
                branch = result.stdout.strip()
                return branch or None
        except Exception:
            pass
        return None

    def current_branch(self) -> Optional[str]:
        if self.exists() and DULWICH_AVAILABLE:
            head = self.path / ".git" / "HEAD"
            if head.exists():
                try:
                    raw = head.read_text(encoding="utf-8").strip()
                    if raw.startswith("ref:"):
                        return raw.rsplit("/", 1)[-1]
                    return "detached"
                except Exception:
                    pass
        return self._git_branch()

    def list_branches(self) -> List[str]:
        try:
            result = self._run_git("branch", "--format=%(refname:short)", check=False)
            if result.returncode == 0:
                branches = [
                    line.strip() for line in result.stdout.splitlines() if line.strip()
                ]
                return sorted(dict.fromkeys(branches))
        except Exception:
            pass
        repo = self.open()
        if repo is None or not DULWICH_AVAILABLE:
            return []
        try:
            return sorted(
                branch.decode("utf-8", errors="replace").split("/", 2)[-1]
                for branch in porcelain.branch_list(repo)  # type: ignore[attr-defined]
            )
        except Exception:
            return []

    def last_commit(self) -> Optional[Dict[str, Any]]:
        try:
            result = self._run_git(
                "log",
                "-1",
                "--pretty=format:%H%x1f%an%x1f%ae%x1f%ad%x1f%s",
                "--date=iso-strict",
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                commit, author, email, timestamp, message = result.stdout.split("", 4)
                return {
                    "commit": commit,
                    "author": author,
                    "email": email,
                    "message": message,
                    "timestamp": timestamp,
                }
        except Exception:
            pass
        repo = self.open()
        if repo is None or not DULWICH_AVAILABLE:
            return None
        try:
            log = porcelain.log(self.path, max_entries=1)  # type: ignore[attr-defined]
            if not log:
                return None
            entry = log[0]
            return {
                "commit": (
                    getattr(entry, "commit", None).decode()
                    if getattr(entry, "commit", None)
                    else None
                ),
                "author": (
                    getattr(entry, "author", None).decode(errors="replace")
                    if getattr(entry, "author", None)
                    else None
                ),
                "message": getattr(entry, "message", b"")
                .decode(errors="replace")
                .strip(),
                "timestamp": getattr(entry, "commit_time", None),
            }
        except Exception:
            return None

    def status(self) -> RepoStatus:
        dirty = False
        if self.exists():
            try:
                result = self._run_git("status", "--porcelain", check=False)
                if result.returncode == 0:
                    dirty = bool(result.stdout.strip())
            except Exception:
                dirty = False
        elif DULWICH_AVAILABLE:
            try:
                status = porcelain.status(self.path)  # type: ignore[attr-defined]
                dirty = bool(status.staged or status.unstaged or status.untracked)
            except Exception:
                dirty = False
        return RepoStatus(
            branch=self.current_branch(),
            last_commit=self.last_commit(),
            dirty=dirty,
            exists=self.exists(),
        )

    def clone(self, source: str, bare: bool = False) -> Dict[str, Any]:
        if DULWICH_AVAILABLE:
            porcelain.clone(source, str(self.path), bare=bare)  # type: ignore[attr-defined]
            return {
                "cloned": True,
                "path": str(self.path),
                "source": source,
                "backend": "dulwich",
            }
        args = ["clone"]
        if bare:
            args.append("--bare")
        args.extend([source, str(self.path)])
        subprocess.run(args, check=True, capture_output=True, text=True)
        return {
            "cloned": True,
            "path": str(self.path),
            "source": source,
            "backend": "git",
        }

    def fetch(self) -> Dict[str, Any]:
        if DULWICH_AVAILABLE:
            repo = self.open()
            if repo is None:
                raise RuntimeError("Repository not available")
            porcelain.fetch(repo, "origin")  # type: ignore[attr-defined]
            return {"fetched": True, "path": str(self.path), "backend": "dulwich"}
        result = self._run_git("fetch", "origin", check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git fetch failed")
        return {"fetched": True, "path": str(self.path), "backend": "git"}

    def ensure_initialized(self) -> None:
        if self.exists():
            return
        self.path.mkdir(parents=True, exist_ok=True)
        if DULWICH_AVAILABLE:
            porcelain.init(self.path)  # type: ignore[attr-defined]
        else:
            self._run_git("init", check=True)

    def _ensure_git_identity(self) -> None:
        try:
            self._run_git("config", "user.name", "Pocket Lab", check=False)
            self._run_git("config", "user.email", "pocketlab@example.com", check=False)
        except Exception:
            pass

    def commit_file(
        self,
        relative_path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        repo_existed = self.exists()
        file_path = self.path / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        self.ensure_initialized()
        self._ensure_git_identity()
        has_history = self.last_commit() is not None
        if branch:
            if DULWICH_AVAILABLE:
                try:
                    porcelain.branch_create(self.path, branch, force=True)  # type: ignore[attr-defined]
                    if has_history:
                        porcelain.checkout(self.path, branch)  # type: ignore[attr-defined]
                except Exception:
                    pass
            else:
                if has_history:
                    self._run_git("checkout", "-B", branch, check=True)
                elif not repo_existed:
                    # Fresh repositories do not have a commit to branch from yet.
                    # Create an orphan branch so the initial sync path can complete.
                    self._run_git("checkout", "--orphan", branch, check=True)
        if DULWICH_AVAILABLE:
            porcelain.add(self.path, [relative_path])  # type: ignore[attr-defined]
            try:
                porcelain.commit(self.path, message.encode("utf-8"))  # type: ignore[attr-defined]
            except Exception:
                pass
            return {
                "committed": True,
                "path": relative_path,
                "message": message,
                "branch": branch or self.current_branch(),
                "backend": "dulwich",
            }
        self._run_git("add", relative_path, check=True)
        commit_result = self._run_git("commit", "-m", message, check=False)
        if commit_result.returncode != 0:
            if (
                "nothing to commit"
                not in (commit_result.stdout + commit_result.stderr).lower()
            ):
                raise RuntimeError(
                    commit_result.stderr.strip()
                    or commit_result.stdout.strip()
                    or "git commit failed"
                )
        return {
            "committed": True,
            "path": relative_path,
            "message": message,
            "branch": branch or self.current_branch(),
            "backend": "git",
            "commit": self.last_commit(),
        }
