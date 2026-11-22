#!/usr/bin/env python3
"""Read-only PM2 daemon identity and ownership verification.

The Lite runtime has one canonical PM2_HOME and one external guardian.  PM2's
pid file is useful evidence, but it is not proof that the process referenced by
that file owns the daemon IPC or the managed applications.  This module keeps
that distinction explicit and emits only bounded, non-secret evidence for
shell recovery callers.

It never starts, stops, kills, edits, or repairs a process.  Ambiguous
ownership is deliberately a hard failure so a guardian cannot resurrect a
second daemon or attach a recovery operation to the wrong PM2 instance.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


PM2_DUPLICATE_DAEMON = "pm2_duplicate_daemon"
PM2_PIDFILE_OWNER_MISMATCH = "pm2_pidfile_owner_mismatch"
PM2_IPC_OWNER_MISMATCH = "pm2_ipc_owner_mismatch"
PM2_OWNERSHIP_UNKNOWN = "pm2_ownership_unknown"
PM2_NORMALIZATION_REQUIRED = "pm2_normalization_required"

_REASONS = (
    PM2_DUPLICATE_DAEMON,
    PM2_PIDFILE_OWNER_MISMATCH,
    PM2_IPC_OWNER_MISMATCH,
    PM2_OWNERSHIP_UNKNOWN,
    PM2_NORMALIZATION_REQUIRED,
)

# PM2 sets process.title to this value.  Anchoring the match prevents a shell
# command containing the words "God Daemon" from being treated as PM2.
_PM2_TITLE = re.compile(r"^PM2 v[^\s:]+: God Daemon \((?P<home>.+)\)$")


@dataclass(frozen=True)
class DaemonObservation:
    """Sanitized process facts needed to evaluate one PM2 daemon."""

    pid: int
    home: str
    executable: str
    ppid: int | None = None
    environment_home: str | None = None
    identity_readable: bool = True


@dataclass(frozen=True)
class IdentityReport:
    """Bounded PM2 ownership result suitable for shell/runtime evidence."""

    state: str
    reasons: tuple[str, ...] = ()
    canonical_pid: int | None = None
    pid_file_pid: int | None = None
    daemon_count: int = 0
    service_parent_pids: tuple[int, ...] = ()

    @property
    def ok(self) -> bool:
        return self.state == "ok"

    @property
    def absent(self) -> bool:
        return self.state == "absent"

    def as_lines(self) -> str:
        """Serialize only non-sensitive, scalar evidence for shell callers."""

        reasons = ",".join(self.reasons) if self.reasons else "none"
        parents = ",".join(str(value) for value in self.service_parent_pids) or "none"
        return "\n".join(
            (
                f"state={self.state}",
                f"reasons={reasons}",
                f"canonical_pid={self.canonical_pid or ''}",
                f"pid_file_pid={self.pid_file_pid or ''}",
                f"daemon_count={self.daemon_count}",
                f"service_parent_pids={parents}",
            )
        )


def _normal_path(value: str | os.PathLike[str] | None) -> str:
    if value is None:
        return ""
    return os.path.normpath(os.path.abspath(os.fspath(value)))


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed > 0 else None


def _ordered_unique(values: Iterable[int]) -> tuple[int, ...]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return tuple(result)


def evaluate_identity(
    daemons: Sequence[DaemonObservation],
    *,
    expected_home: str,
    expected_node: str,
    pid_file_pid: int | None,
    pid_file_present: bool,
    service_parent_pids: Iterable[int] = (),
    service_parent_unknown: bool = False,
    socket_owner_pids: Mapping[str, Iterable[int]] | None = None,
) -> IdentityReport:
    """Evaluate canonical PM2 ownership without taking any action.

    ``service_parent_pids`` comes from the already available PM2 JSON
    projection.  A managed process must be a child of the canonical daemon;
    that is the portable ownership signal on Android/Termux where tools such
    as ``ss`` may be unavailable.  ``socket_owner_pids`` is an optional
    stronger signal used by tests and platforms that can inspect Unix socket
    descriptors.
    """

    expected_home = _normal_path(expected_home)
    expected_node = _normal_path(expected_node)
    parents = _ordered_unique(
        value for value in service_parent_pids if _positive_int(value) is not None
    )
    normalized_daemons = tuple(daemons)
    target = tuple(
        item for item in normalized_daemons if _normal_path(item.home) == expected_home
    )
    foreign = tuple(
        item for item in normalized_daemons if _normal_path(item.home) != expected_home
    )
    reasons: list[str] = []

    def add(reason: str) -> None:
        if reason not in reasons:
            reasons.append(reason)

    if any(
        not item.identity_readable
        or _normal_path(item.executable) != expected_node
        or (
            item.environment_home is not None
            and _normal_path(item.environment_home) != expected_home
        )
        for item in normalized_daemons
    ):
        add(PM2_OWNERSHIP_UNKNOWN)

    if len(target) > 1:
        add(PM2_DUPLICATE_DAEMON)
        add(PM2_NORMALIZATION_REQUIRED)

    canonical = target[0] if len(target) == 1 else None
    if pid_file_present:
        if pid_file_pid is None:
            add(PM2_PIDFILE_OWNER_MISMATCH)
            add(PM2_NORMALIZATION_REQUIRED)
        elif canonical is None or pid_file_pid != canonical.pid:
            add(PM2_PIDFILE_OWNER_MISMATCH)
            add(PM2_NORMALIZATION_REQUIRED)
    elif canonical is not None:
        add(PM2_PIDFILE_OWNER_MISMATCH)
        add(PM2_NORMALIZATION_REQUIRED)

    if service_parent_unknown:
        add(PM2_OWNERSHIP_UNKNOWN)
    if parents:
        if canonical is None or any(parent != canonical.pid for parent in parents):
            add(PM2_IPC_OWNER_MISMATCH)
            add(PM2_NORMALIZATION_REQUIRED)

    if socket_owner_pids:
        if canonical is None:
            add(PM2_IPC_OWNER_MISMATCH)
            add(PM2_NORMALIZATION_REQUIRED)
        else:
            for owners in socket_owner_pids.values():
                normalized_owners = _ordered_unique(
                    value for value in owners if _positive_int(value) is not None
                )
                if not normalized_owners or normalized_owners != (canonical.pid,):
                    add(PM2_IPC_OWNER_MISMATCH)
                    add(PM2_NORMALIZATION_REQUIRED)
                    break

    # A second PM2_HOME is not automatically a duplicate of the canonical
    # one, but on the single-device Lite runtime it makes ownership ambiguous.
    # Fail closed rather than allowing a caller to guess which daemon a CLI
    # might reach.  This also catches an alternate-home daemon owning services.
    if foreign:
        add(PM2_OWNERSHIP_UNKNOWN)
        add(PM2_NORMALIZATION_REQUIRED)

    if canonical is None:
        if not normalized_daemons and not pid_file_present and not parents:
            return IdentityReport(
                state="absent",
                canonical_pid=None,
                pid_file_pid=pid_file_pid,
                daemon_count=0,
                service_parent_pids=parents,
            )
        if not reasons:
            add(PM2_OWNERSHIP_UNKNOWN)

    state = "ok" if canonical is not None and not reasons else "invalid"
    return IdentityReport(
        state=state,
        reasons=tuple(reasons),
        canonical_pid=canonical.pid if canonical is not None else None,
        pid_file_pid=pid_file_pid,
        daemon_count=len(normalized_daemons),
        service_parent_pids=parents,
    )


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return None


def _read_cmdline(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    return " ".join(part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part).strip()


def _read_environment_home(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    for entry in raw.split(b"\0"):
        if entry.startswith(b"PM2_HOME="):
            return entry.partition(b"=")[2].decode("utf-8", errors="replace")
    return None


def _read_ppid(path: Path) -> int | None:
    raw = _read_text(path / "stat")
    if not raw:
        return None
    try:
        after_name = raw.rsplit(")", 1)[1].strip().split()
        return _positive_int(after_name[1])
    except (IndexError, ValueError):
        return None


def discover_daemons(proc_root: Path, *, expected_node: str | None = None) -> tuple[DaemonObservation, ...]:
    """Discover only exact PM2 title matches below a supplied proc root."""

    observations: list[DaemonObservation] = []
    for entry in sorted(proc_root.iterdir(), key=lambda item: item.name):
        if not entry.name.isdigit() or not entry.is_dir():
            continue
        command = _read_cmdline(entry / "cmdline")
        if not command:
            continue
        match = _PM2_TITLE.fullmatch(command)
        if match is None:
            continue
        try:
            pid = int(entry.name)
        except ValueError:
            continue
        try:
            executable = os.path.realpath(os.readlink(entry / "exe"))
            readable = bool(executable)
        except OSError:
            executable = ""
            readable = False
        observations.append(
            DaemonObservation(
                pid=pid,
                home=match.group("home"),
                executable=executable,
                ppid=_read_ppid(entry),
                environment_home=_read_environment_home(entry / "environ"),
                identity_readable=readable and (expected_node is None or executable == _normal_path(expected_node)),
            )
        )
    return tuple(observations)


def _read_pid_file(path: Path) -> tuple[int | None, bool]:
    if not path.exists():
        return None, False
    raw = _read_text(path)
    if raw is None:
        return None, True
    return _positive_int(raw.strip()), True


def _process_parent(path: Path, pid: int) -> int | None:
    return _read_ppid(path / str(pid))


def _service_parent_pids(proc_root: Path, payload: Any) -> tuple[tuple[int, ...], bool]:
    if not isinstance(payload, list):
        return (), True
    parents: list[int] = []
    unknown = False
    for item in payload:
        if not isinstance(item, dict):
            unknown = True
            continue
        env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
        raw_pid = env.get("pid") or item.get("pid")
        pid = _positive_int(raw_pid)
        if pid is None:
            continue
        parent = _process_parent(proc_root, pid)
        if parent is None:
            # Stopped PM2 definitions have no live child to attribute.  Only
            # mark the observation unknown when PM2 says the process is live.
            status = str(env.get("status") or item.get("status") or "").lower()
            if status in {"online", "launching", "waiting restart", "stopping"}:
                unknown = True
            continue
        parents.append(parent)
    return _ordered_unique(parents), unknown


def build_report(
    *,
    proc_root: Path,
    pm2_home: Path,
    pid_file: Path,
    expected_node: Path,
    jlist_file: Path | None = None,
) -> IdentityReport:
    daemons = discover_daemons(proc_root, expected_node=expected_node)
    pid_file_pid, pid_file_present = _read_pid_file(pid_file)
    parents: tuple[int, ...] = ()
    parent_unknown = False
    if jlist_file is not None:
        try:
            payload = json.loads(jlist_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            payload = None
        parents, parent_unknown = _service_parent_pids(proc_root, payload)
    return evaluate_identity(
        daemons,
        expected_home=str(pm2_home),
        expected_node=str(expected_node),
        pid_file_pid=pid_file_pid,
        pid_file_present=pid_file_present,
        service_parent_pids=parents,
        service_parent_unknown=parent_unknown,
    )


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pm2-home", required=True, type=Path)
    parser.add_argument("--pid-file", type=Path)
    parser.add_argument("--expected-node", required=True, type=Path)
    parser.add_argument("--proc-root", type=Path, default=Path("/proc"))
    parser.add_argument("--jlist-file", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    report = build_report(
        proc_root=args.proc_root,
        pm2_home=args.pm2_home,
        pid_file=args.pid_file or args.pm2_home / "pm2.pid",
        expected_node=args.expected_node,
        jlist_file=args.jlist_file,
    )
    print(report.as_lines())
    return 0 if report.state in {"ok", "absent"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
