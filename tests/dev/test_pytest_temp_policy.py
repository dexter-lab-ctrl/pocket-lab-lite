from pathlib import Path


def test_pytest_uses_shared_repo_local_dev_scratch_policy():
    config = Path("pytest.ini").read_text(encoding="utf-8")
    conftest = Path("conftest.py").read_text(encoding="utf-8")

    assert "--basetemp=.pocketlab-dev/tmp/pytest" not in config
    assert "POCKETLAB_DEV_TMPDIR" in conftest
    assert '".pocketlab-dev" / "tmp"' in conftest
    assert 'root / "pytest"' in conftest
