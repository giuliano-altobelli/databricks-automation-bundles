# Databricks DAB Monorepo Foundation Phase 1

Status: complete

This tracker records the initial lightweight implementation of this repository as the real Databricks Declarative Automation Bundles monorepo foundation.

## Approved Scope

- Treat this repository as the real DAB monorepo foundation.
- Keep this phase local, lightweight, and contract-focused.
- Add root `uv` tooling, `prek.toml`, metadata schemas, generic templates, a small `repoctl`, and offline tests.
- Do not implement the ABAC asset bundle in this phase.

## Non-Goals

- No ABAC asset bundle.
- No `databricks.yml`, SQL, UDFs, or access-map contracts.
- No live Databricks resource creation.
- No GitHub Actions deployment workflows.
- No UAT or production deployment.
- No evidence upload or Unity Catalog audit writes.

## Implementation Checklist

- [x] Add this implementation tracker.
- [x] Write failing tests for `repoctl` discovery, validation, and changed-file classification.
- [x] Add root `pyproject.toml`, `uv.lock`, and `prek.toml`.
- [x] Add the `repoctl` package with `discover`, `validate`, and `changed` commands.
- [x] Add project and bundle metadata schemas.
- [x] Add generic project and bundle templates.
- [x] Add one inert sample project and bundle metadata fixture.
- [x] Run local verification and record evidence.

## Design Decisions

- Use `projects/<project>/bundles/<bundle>` as the stable scaling unit.
- Keep root dependencies scoped to repository tooling only.
- Keep bundle runtime dependencies bundle-local and optional.
- Represent the target contract in `bundle.yaml`: every bundle declares `dev`, `uat`, and `prod`; `dev` is the local default.
- Keep changed-file classification path-based in phase 1:
  - bundle-local changes affect that bundle
  - `libs/`, `schemas/`, `templates/`, `tools/`, `pyproject.toml`, `uv.lock`, `prek.toml`, and `.github/` affect all bundles
  - docs-only changes do not affect deployable bundles

## Verification Log

- 2026-06-25: `uvx pytest -q` failed before implementation with `ModuleNotFoundError: No module named 'repoctl'`, confirming the first red test state.
- 2026-06-25: `uv run pytest -q` passed with 8 tests after implementation.
- 2026-06-25: `uv run ruff check tools tests` passed when rerun with elevated cache access.
- 2026-06-25: `uv run repoctl discover` found the `platform-governance` project and `foundation-smoke` bundle.
- 2026-06-25: `uv run repoctl validate` reported `Validation ok`.
- 2026-06-25: Code review found that `repoctl changed --base` ignored working-tree and untracked files; fixed by including committed, staged, unstaged, and untracked files.
- 2026-06-25: Code review found schema/validator drift; fixed by adding validation for unknown fields, target/dependency key sets, and metadata name patterns.
- 2026-06-25: `uv run prek -c prek.toml run --all-files` passed after fixing pre-existing trailing whitespace in `.gitignore`.
- 2026-06-25: Final verification sweep:
  - `uv sync --locked --all-extras --dev` resolved and audited the locked environment.
  - `uv run pytest -q` passed with 11 tests.
  - `uv run ruff check tools tests` passed.
  - `uv run prek -c prek.toml run --all-files` passed.
  - `uv run repoctl discover` found one project and one inert bundle.
  - `uv run repoctl validate` reported `Validation ok`.
  - `uv run repoctl changed --base HEAD` reported the active foundation working-tree changes and marked the inert bundle affected because root tooling/contracts changed.
