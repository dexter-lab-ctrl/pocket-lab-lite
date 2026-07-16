from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.delenv("POCKETLAB_GATE_FAULT_INJECTION", raising=False)
    monkeypatch.delenv("POCKETLAB_GATE_STORAGE_TEST_MODE", raising=False)
    monkeypatch.delenv("POCKETLAB_GATE_ISOLATED_ROOT", raising=False)
    monkeypatch.delenv("POCKETLAB_GATE_STORAGE_FAILPOINT", raising=False)
    yield state


def test_storage_failpoint_is_disabled_without_all_authorizers(isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch):
    from api_fastapi.services import lite_storage_faults

    monkeypatch.setenv("POCKETLAB_GATE_STORAGE_FAILPOINT", "sqlite_lifecycle_write")
    lite_storage_faults.raise_if_storage_fault("sqlite_lifecycle_write")
    monkeypatch.setenv("POCKETLAB_GATE_FAULT_INJECTION", "1")
    lite_storage_faults.raise_if_storage_fault("sqlite_lifecycle_write")
    monkeypatch.setenv("POCKETLAB_GATE_STORAGE_TEST_MODE", "1")
    lite_storage_faults.raise_if_storage_fault("sqlite_lifecycle_write")


def test_allowlisted_isolated_failpoint_raises_real_enospc(isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch):
    from api_fastapi.services import lite_storage_faults

    monkeypatch.setenv("POCKETLAB_GATE_FAULT_INJECTION", "1")
    monkeypatch.setenv("POCKETLAB_GATE_STORAGE_TEST_MODE", "1")
    monkeypatch.setenv("POCKETLAB_GATE_ISOLATED_ROOT", str(isolated_runtime.parent))
    monkeypatch.setenv("POCKETLAB_GATE_STORAGE_FAILPOINT", "sqlite_lifecycle_write")
    with pytest.raises(OSError) as raised:
        lite_storage_faults.raise_if_storage_fault("sqlite_lifecycle_write")
    assert raised.value.errno == errno.ENOSPC
    monkeypatch.setenv("POCKETLAB_GATE_STORAGE_FAILPOINT", "not-allowlisted")
    lite_storage_faults.raise_if_storage_fault("not-allowlisted")


def test_atomic_replace_failure_preserves_prior_file(isolated_runtime: Path, monkeypatch: pytest.MonkeyPatch):
    from api_fastapi.services import lite_security_evidence

    target = isolated_runtime / "security" / "security_state.json"
    lite_security_evidence.write_json(target, {"revision": 1})
    prior = target.read_bytes()
    monkeypatch.setenv("POCKETLAB_GATE_FAULT_INJECTION", "1")
    monkeypatch.setenv("POCKETLAB_GATE_STORAGE_TEST_MODE", "1")
    monkeypatch.setenv("POCKETLAB_GATE_ISOLATED_ROOT", str(isolated_runtime.parent))
    monkeypatch.setenv("POCKETLAB_GATE_STORAGE_FAILPOINT", "atomic_replace")
    with pytest.raises(OSError) as raised:
        lite_security_evidence.write_json(target, {"revision": 2})
    assert raised.value.errno == errno.ENOSPC
    assert target.read_bytes() == prior
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))
