"""Exact reviewed manifests for fixed owner roots, not generic file deletion."""
from __future__ import annotations
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

from .. import deps

TEMP_MARKER = ".pocketlab-rehearsal-owner-v1"
TEMP_MAGIC = b"pocketlab-database-rehearsal-v1\n"
MAX_FILES = 32


def rehearsal_root() -> Path:
    root=deps.settings().state_dir/"system-health-rehearsals"
    root.mkdir(mode=0o700,exist_ok=True)
    if root.is_symlink() or not root.is_dir() or root.stat().st_uid!=os.getuid() or root.stat().st_mode & 0o077:
        raise ValueError("unsafe_rehearsal_root")
    return root


def _identity(info) -> dict:
    if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid():
        raise ValueError("unsafe_cleanup_candidate")
    return {"dev":info.st_dev,"ino":info.st_ino,"size":info.st_size,
            "mtime_ns":info.st_mtime_ns,"ctime_ns":info.st_ctime_ns,"allocated":max(0,info.st_blocks*512)}


def _active_logs(logs: Path) -> set:
    # Fixed existing PM2 inventory contract. Never return process environment.
    result=subprocess.run(["pm2","jlist"],capture_output=True,text=True,timeout=5,check=False)
    if result.returncode or len(result.stdout)>4*1024*1024:
        raise ValueError("process_inventory_unavailable")
    rows=json.loads(result.stdout)
    if not isinstance(rows,list) or not rows or len(rows)>256:
        raise ValueError("process_inventory_unavailable")
    active=set()
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get("pm2_env"),dict):
            raise ValueError("process_inventory_unavailable")
        env=row["pm2_env"]
        for key in ("pm_out_log_path","pm_err_log_path","pm_log_path"):
            value=env.get(key)
            if not isinstance(value,str) or not value:
                if key!="pm_log_path" and env.get("status")=="online":
                    raise ValueError("active_log_inventory_unavailable")
                continue
            path=Path(value).expanduser()
            if path.parent.resolve()!=logs:
                continue
            try:
                info=path.stat()
                active.add((info.st_dev,info.st_ino))
            except FileNotFoundError:
                continue
    return active


def _log_plan() -> tuple[Path,list[dict]]:
    from supervisors.pocketlab_runtime_contract import _resolve_log_dir,_pm2_log_file_snapshot,LogPolicy
    from supervisors.pocketlab_runtime_registry import managed_service_specs
    root=_resolve_log_dir()
    active=_active_logs(root)
    files,complete=_pm2_log_file_snapshot(root)
    if not complete:
        raise ValueError("log_inventory_incomplete")
    names="|".join(re.escape(spec.name) for spec in managed_service_specs())
    pattern=re.compile(r"(?:"+names+r")-(?:out|error)__[0-9]{4}-[0-9]{2}-[0-9]{2}[_T][0-9-]{6,12}\.log")
    cutoff=time.time()-max(7*86400,LogPolicy.from_env().max_age_seconds)
    candidates=[]
    for path,info in sorted(files,key=lambda item:item[0].name):
        if not pattern.fullmatch(path.name) or info.st_mtime>=cutoff or (info.st_dev,info.st_ino) in active:
            continue
        try:
            candidates.append({"name":path.name,**_identity(info)})
        except ValueError:
            continue
        if len(candidates)>=MAX_FILES:
            break
    return root,candidates


def _temp_plan() -> tuple[Path,list[dict]]:
    root=rehearsal_root()
    cutoff=time.time()-86400
    candidates=[]
    with os.scandir(root) as entries:
        for index,entry in enumerate(entries):
            if index>=128:
                raise ValueError("temporary_inventory_incomplete")
            if not re.fullmatch(r"database-rehearsal-[a-z0-9_]{8}",entry.name) or not entry.is_dir(follow_symlinks=False):
                continue
            info=entry.stat(follow_symlinks=False)
            if info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_mtime>=cutoff:
                continue
            folder=root/entry.name
            try:
                fd=os.open(folder/TEMP_MARKER,os.O_RDONLY|os.O_NOFOLLOW)
                with os.fdopen(fd,"rb") as marker:
                    if marker.read(len(TEMP_MAGIC)+1)!=TEMP_MAGIC:
                        continue
                local=[]
                for child in folder.iterdir():
                    if len(local)>=MAX_FILES or child.name in {".",".."} or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",child.name):
                        raise ValueError("temporary_inventory_incomplete")
                    metadata=child.lstat()
                    if metadata.st_mtime>=cutoff:
                        raise ValueError("temporary_not_expired")
                    local.append({"name":child.name,**_identity(metadata)})
                if len(candidates)+len(local)>MAX_FILES:
                    break
                candidates.extend({"folder":entry.name,**item} for item in local)
            except (OSError,ValueError):
                continue
    return root,sorted(candidates,key=lambda item:(item["folder"],item["name"]))


@contextmanager
def _scope_lock(scope: str):
    if scope=="temp":
        from .lite_database_recovery import _database_recovery_lock
        with _database_recovery_lock("system-health-rehearsal-cleanup"):
            yield
    elif scope=="logs":
        # Same lock as the runtime owner's periodic log policy.
        from supervisors.pocketlab_runtime_contract import log_policy_lock
        with log_policy_lock(deps.settings().state_dir):
            yield
    else:
        raise ValueError("unsupported_cleanup_scope")


def preview(scope: str) -> tuple[list[dict],dict]:
    with _scope_lock(scope):
        _,rows=_log_plan() if scope=="logs" else _temp_plan()
    return rows,{"candidate_count":len(rows),"allocated_candidate_bytes":sum(r["allocated"] for r in rows),
                 "estimated_bytes":None,"physical_reclaimed_bytes":None}


def _remove_exact(fd: int,row: dict) -> None:
    current=_identity(os.stat(row["name"],dir_fd=fd,follow_symlinks=False))
    if current!={key:row[key] for key in current}:
        raise RuntimeError("cleanup_candidate_changed")
    os.unlink(row["name"],dir_fd=fd)
    try:
        os.stat(row["name"],dir_fd=fd,follow_symlinks=False)
    except FileNotFoundError:
        return
    raise RuntimeError("cleanup_removal_not_verified")


def apply(scope: str,candidates: list[dict]) -> dict:
    if not candidates or len(candidates)>MAX_FILES:
        raise ValueError("reviewed_candidates_required")
    with _scope_lock(scope):
        root,current=_log_plan() if scope=="logs" else _temp_plan()
        if current!=candidates:
            raise ValueError("retention_preview_changed")
        rootfd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            if scope=="logs":
                for row in candidates:
                    if (row["dev"],row["ino"]) in _active_logs(root):
                        raise RuntimeError("active_log_changed")
                    _remove_exact(rootfd,row)
            else:
                for folder in sorted({row["folder"] for row in candidates}):
                    fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=rootfd)
                    try:
                        # Keep owner marker until all other exact files removed.
                        selected=sorted((r for r in candidates if r["folder"]==folder),key=lambda r:r["name"]==TEMP_MARKER)
                        for row in selected:
                            _remove_exact(fd,row)
                        os.fsync(fd)
                    finally:
                        os.close(fd)
                    os.rmdir(folder,dir_fd=rootfd)
            os.fsync(rootfd)
        finally:
            os.close(rootfd)
    return {"verified":True,"files_removed":len(candidates),"allocated_candidate_bytes":sum(r["allocated"] for r in candidates),"physical_reclaimed_bytes":None}
