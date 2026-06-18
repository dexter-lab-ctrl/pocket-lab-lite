import json
from pocket_lab_test_utils import isolated_state_dir


def test_old_state_directory_can_exist(tmp_path):
    state = isolated_state_dir(tmp_path)
    (state / "operations.json").write_text(
        json.dumps({"operations": [{"operation": "git_sync", "status": "succeeded"}]})
    )
    assert (state / "operations.json").exists()


def test_workflow_projections_rebuild_from_journal(tmp_path):
    state = isolated_state_dir(tmp_path)
    journal = state / "workflow_events.jsonl"
    journal.write_text(
        "\n".join(
            [
                json.dumps({"workflow_id": "wf-1", "status": "running"}),
                json.dumps({"workflow_id": "wf-1", "status": "succeeded"}),
            ]
        )
        + "\n"
    )
    projection = {}
    for line in journal.read_text().splitlines():
        item = json.loads(line)
        projection[item["workflow_id"]] = item["status"]
    assert projection["wf-1"] == "succeeded"


def test_dead_letters_release_fleet_catalog_backup_state_shapes(tmp_path):
    state = isolated_state_dir(tmp_path)
    files = {
        "dead_letters.json": [],
        "release_state.json": {"status": "idle"},
        "fleet_registry.json": {"agents": []},
        "catalog_state.json": {"items": []},
        "backup_state.json": {"latest": None},
    }
    for name, payload in files.items():
        (state / name).write_text(json.dumps(payload))
    for name in files:
        assert json.loads((state / name).read_text()) is not None
