from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def recipe_commands(justfile_text: str, recipe_name: str) -> list[str]:
    lines = justfile_text.splitlines()
    start = lines.index(f"{recipe_name}:") + 1
    commands: list[str] = []

    for line in lines[start:]:
        if line and not line.startswith((" ", "\t")):
            break
        if line.strip():
            commands.append(line.strip())

    return commands


def test_root_justfile_exposes_bootstrap_and_verify_recipes() -> None:
    justfile_text = (REPO_ROOT / "justfile").read_text(encoding="utf-8")

    assert recipe_commands(justfile_text, "bootstrap") == [
        "uv sync --locked --all-extras --dev",
        "uv run prek -c prek.toml install",
    ]
    assert recipe_commands(justfile_text, "verify") == [
        "uv run pytest -q",
        "uv run ruff check tools tests",
        "uv run prek -c prek.toml run --all-files",
        "uv run repoctl discover",
        "uv run repoctl validate",
        "uv run repoctl changed --base HEAD",
    ]


def test_root_justfile_serves_bundle_explorer_on_an_optional_port() -> None:
    justfile_text = (REPO_ROOT / "justfile").read_text(encoding="utf-8")

    assert recipe_commands(justfile_text, 'explore port="8000"') == [
        "python3 -m http.server {{port}} --bind 127.0.0.1 "
        "--directory projects/platform-governance/apps/bundle-explorer"
    ]
