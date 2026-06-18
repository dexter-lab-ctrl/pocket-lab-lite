from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    import ansible_runner  # type: ignore

    ANSIBLE_RUNNER_AVAILABLE = True
except Exception:  # pragma: no cover
    ansible_runner = None
    ANSIBLE_RUNNER_AVAILABLE = False

from contracts import utc_now_iso


class AnsibleRunnerService:
    def __init__(self, private_data_dir: Path, event_dir: Path):
        self.private_data_dir = Path(private_data_dir)
        self.event_dir = Path(event_dir)
        self.private_data_dir.mkdir(parents=True, exist_ok=True)
        self.event_dir.mkdir(parents=True, exist_ok=True)

    def _write_event_stream(self, run_dir: Path, events: list[Dict[str, Any]]) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "events.jsonl").write_text(
            "\n".join(json.dumps(event, ensure_ascii=False) for event in events),
            encoding="utf-8",
        )

    def _simulate_run(
        self,
        playbook: str,
        *,
        inventory: Optional[str] = None,
        extravars: Optional[Dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        run_id = uuid.uuid4().hex
        run_dir = self.event_dir / run_id
        started_at = utc_now_iso()
        events: list[Dict[str, Any]] = [
            {
                "timestamp": started_at,
                "event": "playbook_on_start",
                "event_data": {
                    "playbook": playbook,
                    "inventory": inventory,
                    "extravars": extravars or {},
                    "tags": tags or [],
                },
                "stdout": f"PLAY [{playbook}]\n",
                "counter": 1,
                "uuid": run_id,
                "task": "playbook",
                "host": "localhost",
            }
        ]
        task_name = Path(playbook).stem.replace("_", " ").title() or "Pocket Lab Task"
        events.append(
            {
                "timestamp": utc_now_iso(),
                "event": "runner_on_ok",
                "event_data": {
                    "task": task_name,
                    "host": "localhost",
                    "res": {
                        "changed": False,
                        "msg": "Simulated Ansible Runner execution",
                    },
                },
                "stdout": f"ok: [localhost] => {task_name}\n",
                "counter": 2,
                "uuid": run_id,
                "task": task_name,
                "host": "localhost",
            }
        )
        if event_handler:
            for item in events:
                try:
                    event_handler(item)
                except Exception:
                    pass
        finished_at = utc_now_iso()
        stdout = "\n".join(
            [
                f"PLAY [{playbook}]",
                f"TASK [{task_name}]",
                "ok: [localhost] => Simulated Ansible Runner execution",
                "PLAY RECAP: localhost : ok=1 changed=0 unreachable=0 failed=0",
            ]
        )
        stderr = ""
        self._write_event_stream(run_dir, events)
        return {
            "status": "successful",
            "rc": 0,
            "stdout": stdout,
            "stderr": stderr,
            "events": events,
            "artifacts": {
                "job_events": str(run_dir),
                "status": "successful",
                "mode": "simulated",
                "run_id": run_id,
            },
            "started_at": started_at,
            "finished_at": finished_at,
            "command": {
                "playbook": playbook,
                "inventory": inventory,
                "extravars": extravars or {},
                "tags": tags or [],
            },
        }

    def run_playbook(
        self,
        playbook: str,
        *,
        inventory: Optional[str] = None,
        extravars: Optional[Dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
        event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        if not ANSIBLE_RUNNER_AVAILABLE:
            return self._simulate_run(
                playbook,
                inventory=inventory,
                extravars=extravars,
                tags=tags,
                event_handler=event_handler,
            )

        captured_events: list[Dict[str, Any]] = []

        def _event_handler(event: Dict[str, Any]) -> None:
            try:
                captured_events.append(
                    {
                        "timestamp": utc_now_iso(),
                        "event": event.get("event"),
                        "event_data": event.get("event_data", {}),
                        "stdout": event.get("stdout", ""),
                        "counter": event.get("counter"),
                        "uuid": event.get("uuid"),
                        "task": event.get("event_data", {}).get("task"),
                        "host": event.get("event_data", {}).get("host"),
                    }
                )
                if event_handler:
                    try:
                        event_handler(captured_events[-1])
                    except Exception:
                        pass
            except Exception:
                pass

        run = ansible_runner.run(
            private_data_dir=str(self.private_data_dir),
            playbook=playbook,
            inventory=inventory,
            extravars=extravars or {},
            tags=tags or [],
            event_handler=_event_handler,
        )

        stdout = getattr(run, "stdout", "") or ""
        stderr = getattr(run, "stderr", "") or ""
        if not isinstance(stdout, str):
            stdout = str(stdout)
        if not isinstance(stderr, str):
            stderr = str(stderr)

        return {
            "status": getattr(run, "status", "unknown"),
            "rc": getattr(run, "rc", 0),
            "stdout": stdout,
            "stderr": stderr,
            "events": captured_events,
            "artifacts": {
                "job_events": str(getattr(run, "job_events", self.event_dir)),
                "status": getattr(run, "status", "unknown"),
                "mode": "ansible_runner",
            },
            "started_at": utc_now_iso(),
            "finished_at": utc_now_iso(),
            "command": {
                "playbook": playbook,
                "inventory": inventory,
                "extravars": extravars or {},
                "tags": tags or [],
            },
        }
