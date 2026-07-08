bootstrap:
    uv sync --locked --all-extras --dev
    uv run prek -c prek.toml install

verify:
    uv run pytest -q
    uv run ruff check tools tests
    uv run prek -c prek.toml run --all-files
    uv run repoctl discover
    uv run repoctl validate
    uv run repoctl changed --base HEAD
