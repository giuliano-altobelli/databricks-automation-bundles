from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPLORER = ROOT / "apps" / "bundle-explorer"


def test_bundle_explorer_contains_the_static_app_and_browser_suite() -> None:
    expected = {
        "README.md",
        "app.js",
        "canvas.js",
        "index.html",
        "model.js",
        "style.css",
        "tests/index.html",
        "tests/test.js",
    }

    assert {
        path.relative_to(EXPLORER).as_posix()
        for path in EXPLORER.rglob("*")
        if path.is_file()
    } == expected


def test_bundle_explorer_runtime_has_no_remote_or_backend_dependencies() -> None:
    runtime = [
        EXPLORER / "index.html",
        EXPLORER / "app.js",
        EXPLORER / "canvas.js",
        EXPLORER / "model.js",
        EXPLORER / "style.css",
        EXPLORER / "tests" / "index.html",
        EXPLORER / "tests" / "test.js",
    ]

    contents = "\n".join(path.read_text(encoding="utf-8") for path in runtime)

    assert "https://" not in contents
    assert "http://" not in contents
    assert "fetch(" not in contents
    assert "WebSocket" not in contents
    assert "XMLHttpRequest" not in contents


def test_bundle_explorer_documents_the_local_workflow_and_current_ci_limit() -> None:
    readme = (EXPLORER / "README.md").read_text(encoding="utf-8")
    page = (EXPLORER / "index.html").read_text(encoding="utf-8")

    assert "just explore" in readme
    assert "just explore 9000" in readme
    assert "http://127.0.0.1:8000/tests/" in readme
    assert "UAT" in page
    assert "production" in page
    assert "hardcoded" in page
