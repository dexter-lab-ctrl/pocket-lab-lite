from pocket_lab_test_utils import load_fastapi_app


def test_fastapi_app_imports():
    app = load_fastapi_app()
    assert app.title
    assert len(app.routes) > 0
