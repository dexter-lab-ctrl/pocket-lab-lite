import json
import re
from pathlib import Path


def test_frontend_uses_only_typed_operation_names():
    contract = json.loads(Path("contracts/pocketlab_operations.json").read_text())
    allowed = set(contract["allowed_operations"])
    src_text = "\n".join(
        path.read_text(errors="ignore")
        for path in Path("src").rglob("*")
        if path.is_file() and path.suffix in {".js", ".jsx", ".ts", ".tsx"}
    )
    for forbidden in [
        "retired compatibility intent field",
        "retired sync compatibility task",
        "retired IaC deploy compatibility task",
        "submitLegacyOperation",
    ]:
        assert forbidden not in src_text
    calls = set(
        re.findall(r"executeOperation\(\s*['\"]([a-zA-Z0-9_:-]+)['\"]", src_text)
    )
    assert not (
        calls - allowed
    ), f"Unknown frontend operation literals: {sorted(calls - allowed)}"


def test_taskfile_uses_current_operation_contract_language():
    text = Path("Taskfile.yml").read_text()
    for forbidden in [
        "retired compatibility intent field",
        "retired sync compatibility task",
        "retired IaC deploy compatibility task",
        "retired update compatibility endpoint",
    ]:
        assert forbidden not in text
