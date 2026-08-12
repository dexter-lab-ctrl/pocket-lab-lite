from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

CONSTRAINTS = (
    ROOT
    / "requirements-ci-openapi-constraints.txt"
)

WORKFLOW = (
    ROOT
    / ".github"
    / "workflows"
    / "lite-quality.yml"
)


def test_ci_openapi_constraints_cover_schema_stack():
    text = CONSTRAINTS.read_text(
        encoding="utf-8"
    )

    required = (
        "fastapi==",
        "starlette==",
        "pydantic==",
        "pydantic-core==",
        "uvicorn==",
        "nats-py==",
        "PyYAML==",
    )

    for package in required:
        assert package in text


def test_lite_quality_uses_openapi_constraints():
    workflow = WORKFLOW.read_text(
        encoding="utf-8"
    )

    assert (
        "--constraint "
        "requirements-ci-openapi-constraints.txt"
        in workflow
    )

    assert (
        "pocket-lab-final-structure/runtime/"
        "requirements.txt"
        in workflow
    )


def test_pip_cache_tracks_qualified_inputs():
    workflow = WORKFLOW.read_text(
        encoding="utf-8"
    )

    assert "cache-dependency-path: |" in workflow

    required = (
        "requirements-dev.txt",
        "requirements-docs.txt",
        "requirements-ci-openapi-constraints.txt",
        "pocket-lab-final-structure/runtime/requirements.txt",
    )

    for path in required:
        assert path in workflow


def test_ci_reports_openapi_toolchain_provenance():
    workflow = WORKFLOW.read_text(
        encoding="utf-8"
    )

    assert (
        "Verify qualified Lite API Python toolchain"
        in workflow
    )

    for package in (
        '"fastapi"',
        '"starlette"',
        '"pydantic"',
        '"pydantic-core"',
        '"uvicorn"',
        '"nats-py"',
        '"PyYAML"',
    ):
        assert package in workflow

    assert (
        "PASS qualified OpenAPI toolchain "
        "provenance recorded"
        in workflow
    )
