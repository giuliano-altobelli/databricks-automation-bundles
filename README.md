# databricks-automation-bundles

Lightweight foundation for a Databricks Asset Bundle monorepo.

This repository is intentionally foundation-first. It establishes repository contracts, local tooling, metadata validation, changed-bundle classification, PR validation, promotion-evidence checks, and one offline ABAC dogfood bundle before introducing live Databricks deployments.

## Phase 1 Scope

Phase 1a and Phase 1b are now represented in this branch.

Included:

- root `uv` tooling
- root `justfile` wrappers: `just bootstrap` and `just verify`
- `prek` hook configuration
- `repoctl` for repository discovery, metadata validation, changed-file classification, and `repoctl evidence check`
- project and bundle metadata schemas
- documentation-grade evidence schemas in `schemas/evidence/`
- generic project and bundle templates
- concrete `templates/bundles/abac-access-map/` template
- one inert sample bundle metadata fixture
- offline ABAC dogfood bundle at `projects/platform-governance/bundles/abac-jira-project-access/`
- PR validation workflow at `.github/workflows/pr-validation.yml`

Still deferred:

- live Databricks resource creation
- UAT and production deployment workflows
- GitHub Actions evidence artifact upload
- production promotion automation
- Unity Catalog audit writes

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

No Databricks workspace credentials or Databricks CLI setup are required for this Phase 1 foundation bootstrap.

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

## Repository Shape

The stable scaling unit is:

```text
projects/<project>/bundles/<bundle>
```

A project is an ownership and review boundary. A bundle is one deployable Databricks Asset Bundle boundary. In phase 1, `foundation-smoke` remains metadata-only, while `abac-jira-project-access` owns offline SQL, fixture, contract-test, and inert native bundle files without deploying live resources.

## Metadata Contracts

- `projects/<project>/project.yaml` declares project ownership and review policy.
- `projects/<project>/bundles/<bundle>/repoctl.bundle.yaml` declares bundle ownership, review policy, targets, and dependencies for native Databricks bundle roots that also contain `databricks.yml`.
- `projects/<project>/bundles/<bundle>/bundle.yaml` remains supported as the legacy metadata-only fallback.
- Every bundle declares `dev`, `uat`, and `prod`.
- `dev` is the local default target.
- `uat` and `prod` are CI-controlled targets.

Use `repoctl.bundle.yaml` for native Databricks bundle roots to avoid a Databricks CLI root-config collision with `databricks.yml`.
