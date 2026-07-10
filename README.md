# databricks-automation-bundles

Lightweight foundation for a Databricks Asset Bundle monorepo.

## Bootstrap

From the repository root, a new developer's Day 0 bootstrap is:

```bash
just bootstrap
```

If `just` is unavailable, run the underlying commands directly:

```bash
uv sync --locked --all-extras --dev
uv run prek -c prek.toml install
```

## Local Verification

After bootstrap, run the local verification loop with:

```bash
just verify
```

If `just` is unavailable, run the underlying commands directly:

```bash
uv run pytest -q
uv run ruff check tools tests
uv run prek -c prek.toml run --all-files
uv run repoctl discover
uv run repoctl validate
uv run repoctl changed --base HEAD
```
