# databricks-automation-bundles

Lightweight foundation for a Databricks Asset Bundle monorepo.

This repository is intentionally foundation-first. It establishes repository contracts, local tooling, metadata validation, changed-bundle classification, PR validation, promotion-evidence checks, and a focused live Databricks deployment path for the ABAC dogfood bundle.

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
- live ABAC dogfood bundle at `projects/platform-governance/bundles/abac-jira-project-access/`
- PR validation and shared-UAT deployment workflow at `.github/workflows/pr-validation.yml`
- main-branch production deployment workflow at `.github/workflows/prod-deployment.yml`

Still deferred:

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

## Live Dev Deployment

The `abac-jira-project-access` bundle supports attended local deployment to the
developer's `personal.<user_key>` schema in `sandbox-infra`. From its bundle
directory, authenticate the `sandbox-infra` profile, supply the existing SQL
warehouse ID, then validate, deploy, and run as yourself:

```bash
export BUNDLE_VAR_sql_warehouse_id="<dev-sql-warehouse-id>"
databricks bundle validate -t dev -p sandbox-infra
databricks bundle deploy -t dev -p sandbox-infra
databricks bundle run -t dev -p sandbox-infra apply_abac_jira_project_access
```

See the bundle's `README.md` for authentication, resource, and safety details.

## GitHub Deployment Environments

GitHub environments are repository-level secret scopes and deployment gates;
they are separate from Databricks workspaces. Create them under **Repository
Settings → Environments → New environment** because the deployment jobs declare
`environment: uat` and `environment: prod`. Local dev does not use a GitHub
environment.

Configure `uat` as follows:

- Under deployment branches, choose selected branches and tags and add the
  branch pattern `refs/pull/*/merge`.
- Add environment variables `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and
  `DATABRICKS_SQL_WAREHOUSE_ID`, plus secret `DATABRICKS_CLIENT_SECRET`.
- Add a required reviewer only if every shared-UAT deployment should pause for
  manual approval.

Configure `prod` as follows:

- Under deployment branches, choose selected branches and tags and add only the
  branch pattern `main`.
- Add environment variables `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and
  `DATABRICKS_SQL_WAREHOUSE_ID`, plus secret `DATABRICKS_CLIENT_SECRET`.
- Optionally require a reviewer for an explicit production approval gate.

The environment rules are a second guard beyond the workflow triggers: GitHub
does not release an environment's secrets until its protection rules pass.
Fork and Dependabot pull requests run offline validation only and never enter
the credentialed UAT deployment job.

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

A project is an ownership and review boundary. A bundle is one deployable Databricks Asset Bundle boundary. `foundation-smoke` remains metadata-only, while `abac-jira-project-access` owns target-driven SQL, fixtures, contract tests, and the live dev/UAT/prod job resource.

## Metadata Contracts

- `projects/<project>/project.yaml` declares project ownership and review policy.
- `projects/<project>/bundles/<bundle>/repoctl.bundle.yaml` declares bundle ownership, review policy, targets, and dependencies for native Databricks bundle roots that also contain `databricks.yml`.
- `projects/<project>/bundles/<bundle>/bundle.yaml` remains supported as the legacy metadata-only fallback.
- Every bundle declares exactly `dev`, `uat`, and `prod`.
- `dev` is the local default target.
- `uat` and `prod` are CI-controlled targets.

Use `repoctl.bundle.yaml` for native Databricks bundle roots to avoid a Databricks CLI root-config collision with `databricks.yml`.
