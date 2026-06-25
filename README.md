# databricks-automation-bundles

Lightweight foundation for a Databricks Asset Bundle monorepo.

This repository is intentionally foundation-first. It establishes repository contracts, local tooling, metadata validation, and changed-bundle classification before introducing any concrete Databricks assets.

## Phase 1 Scope

Included:

- root `uv` tooling
- `prek` hook configuration
- `repoctl` for repository discovery, metadata validation, and changed-file classification
- project and bundle metadata schemas
- generic project and bundle templates
- one inert sample bundle metadata fixture

Deferred:

- ABAC asset bundle implementation
- `databricks.yml`
- SQL and UDF source
- access-map contracts
- live Databricks resource creation
- UAT and production deployment workflows

## Bootstrap

```bash
uv sync --locked --all-extras --dev
uv run prek -c prek.toml install
```

## Local Verification

```bash
uv run pytest -q
uv run ruff check tools tests
uv run prek -c prek.toml run --all-files
uv run repoctl discover
uv run repoctl validate
uv run repoctl changed --base HEAD
```

## Repository Shape

The stable scaling unit is:

```text
projects/<project>/bundles/<bundle>
```

A project is an ownership and review boundary. A bundle is one deployable Databricks Asset Bundle once asset files are introduced. In phase 1, the included `foundation-smoke` bundle is metadata-only.

## Metadata Contracts

- `projects/<project>/project.yaml` declares project ownership and review policy.
- `projects/<project>/bundles/<bundle>/bundle.yaml` declares bundle ownership, review policy, targets, and dependencies.
- Every bundle declares `dev`, `uat`, and `prod`.
- `dev` is the local default target.
- `uat` and `prod` are CI-controlled targets.
