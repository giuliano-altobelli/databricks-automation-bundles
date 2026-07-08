# Live Databricks Dev/Prod Deployment Design

Status: design approved; written spec pending user review
Date: 2026-07-08

## Context

Phase 1b shipped the local/offline enforcement and ABAC dogfood slice. It added
the ABAC Jira project access bundle, promotion evidence checks, PR validation,
and the `abac-access-map` template, but it intentionally kept the native
Databricks bundle inert.

The next slice turns the dogfood bundle into a lightweight live Databricks
deployment path. The current Databricks environment has only a shared `dev`
workspace and a `prod` workspace. There is no active `uat` workspace, and this
design does not create one.

The following objects are assumed to already exist:

- `dev_security` catalog in the `dev` workspace
- `dev_security.access_maps` schema in the `dev` workspace
- `dev_security.policies` schema in the `dev` workspace
- `prod_security` catalog in the `prod` workspace
- `prod_security.access_maps` schema in the `prod` workspace
- `prod_security.policies` schema in the `prod` workspace

The implementation also needs a SQL warehouse in each workspace. Warehouse IDs
should be supplied as target-specific bundle variables or GitHub secrets; they
should not be hard-coded into SQL source files.

## Goals

- Allow a developer to locally validate and deploy the
  `abac-jira-project-access` Databricks bundle to the `dev` workspace by using
  the Databricks CLI and their own profile or personal access token.
- Deploy the same bundle to the shared `dev` workspace from pull request CI by
  using a Databricks service principal.
- Deploy the same bundle to the `prod` workspace from `main` by using a
  Databricks service principal.
- Parameterize the ABAC SQL so `dev` deploys to `dev_security` and `prod`
  deploys to `prod_security`.
- Stop treating `uat` as an active deployment target in this repository until a
  real UAT workspace exists.

## Non-Goals

- No UAT workspace or UAT deployment workflow.
- No catalog or schema creation.
- No row-filter or ABAC policy attachment.
- No CI evidence artifact upload.
- No Unity Catalog audit writes.
- No migration of Terraform-owned platform controls into this repository.
- No broad design for every future Databricks bundle type.
- No multi-developer editing model for the `abac-jira-project-access` bundle.

## Authentication Model

Local developer workflows are attended workflows. A developer may use a
Databricks CLI configuration profile backed by OAuth user-to-machine auth or a
personal access token for the `dev` workspace.

GitHub Actions workflows are unattended workflows. They must use Databricks
service-principal authentication, not developer personal access tokens.

The expected GitHub secret shape is:

- `DATABRICKS_DEV_HOST`
- `DATABRICKS_DEV_CLIENT_ID`
- `DATABRICKS_DEV_CLIENT_SECRET`
- `DATABRICKS_DEV_SQL_WAREHOUSE_ID`
- `DATABRICKS_PROD_HOST`
- `DATABRICKS_PROD_CLIENT_ID`
- `DATABRICKS_PROD_CLIENT_SECRET`
- `DATABRICKS_PROD_SQL_WAREHOUSE_ID`

The bundle should avoid hard-coding authentication credentials. Workspace hosts
may be supplied through target variables or GitHub environment variables, while
credentials remain in local Databricks profiles or GitHub secrets.

## Target Contract

The native Databricks bundle targets are:

- `dev`
- `prod`

The repository metadata contract should also move to this two-target model for
active bundle metadata. `repoctl validate` should no longer require `uat` while
there is no real UAT workspace.

`dev` remains the default local target. `prod` remains CI-controlled and should
only deploy from the `main` branch workflow.

## Bundle Shape

`projects/platform-governance/bundles/abac-jira-project-access/databricks.yml`
becomes a live bundle configuration.

It should define:

- bundle variables for the access-map catalog, schema, table, and policy UDF
- bundle variables for the SQL warehouse used by the apply job
- `dev` target values pointing at `dev_security`
- `prod` target values pointing at `prod_security`
- one Databricks job resource, tentatively named
  `apply_abac_jira_project_access`
- a job task that runs the deployable SQL assets through a SQL notebook task
  or equivalent notebook-compatible SQL file

The live resources created by this slice are limited to:

- `dev_security.access_maps.jira_project_access` in `dev`
- `dev_security.policies.can_read_jira_project` in `dev`
- `prod_security.access_maps.jira_project_access` in `prod`
- `prod_security.policies.can_read_jira_project` in `prod`
- the Databricks job resource that applies those SQL assets in each target

## SQL Parameterization

The SQL under
`projects/platform-governance/bundles/abac-jira-project-access/sql/` should be
target-agnostic.

The SQL should not hard-code `prod_security` as the only deployment
destination. Instead, the bundle should pass target-specific values such as:

- `access_map_catalog`
- `access_map_schema`
- `access_map_table`
- `policy_catalog`
- `policy_schema`
- `policy_udf`

DDL object names should use Databricks SQL `IDENTIFIER(:param)` where possible.
This allows target-specific object names without maintaining duplicate dev and
prod SQL files.

The existing offline fail-closed ABAC contract tests remain authoritative for
UDF behavior. Additional tests should verify that SQL destination selection is
target-driven.

## GitHub Actions Workflows

### Pull Request Workflow

The pull request workflow should keep local verify parity and add dev
deployment.

Expected steps:

1. Checkout repository.
2. Install `uv`.
3. Run root verification:
   - `uv run pytest -q`
   - `uv run ruff check tools tests`
   - `uv run prek -c prek.toml run --all-files`
   - `uv run repoctl discover`
   - `uv run repoctl validate`
   - changed-bundle computation into the job summary.
4. Install or use the Databricks CLI.
5. Authenticate to the dev workspace with the dev service-principal secrets.
6. From the ABAC bundle root, run:
   - `databricks bundle validate -t dev`
   - `databricks bundle deploy -t dev`
   - `databricks bundle run -t dev apply_abac_jira_project_access`

### Main Workflow

The main workflow deploys to production after a merge to `main`.

Expected steps:

1. Trigger on push to `main`.
2. Checkout repository.
3. Install `uv`.
4. Run `just verify`.
5. Install or use the Databricks CLI.
6. Authenticate to the prod workspace with the prod service-principal secrets.
7. From the ABAC bundle root, run:
   - `databricks bundle validate -t prod`
   - `databricks bundle deploy -t prod`
   - `databricks bundle run -t prod apply_abac_jira_project_access`

The production workflow does not upload evidence artifacts in this slice.

## Safety Rules

- Production deploy only runs from `main`.
- Pull request deploys only target the shared `dev` workspace.
- Developer PATs are local-only and must not be used by GitHub Actions.
- The bundle must not create catalogs or schemas.
- The bundle must not attach row filters or ABAC policies.
- The bundle must not write Unity Catalog audit records.
- The workflows must not upload CI evidence artifacts.
- Terraform-owned platform controls remain outside this repository.

## Verification Strategy

Offline tests should prove:

- `repoctl validate` accepts the new `dev`/`prod` target contract.
- `repoctl validate` rejects unsupported targets.
- the ABAC native bundle declares exactly `dev` and `prod`.
- SQL deployment destinations are target-driven rather than hard-coded to
  `prod_security`.
- workflows contain the intended Databricks validate/deploy/run commands.
- workflows do not upload evidence artifacts.
- existing ABAC fail-closed contract tests still pass.

Local Databricks verification should prove:

- a developer can run `databricks bundle validate -t dev`
- a developer can run `databricks bundle deploy -t dev`
- a developer can run
  `databricks bundle run -t dev apply_abac_jira_project_access`

Remote verification should prove:

- pull request GitHub Actions deploys and runs the bundle against `dev`
- merge to `main` deploys and runs the bundle against `prod`

## References

- Databricks bundle configuration:
  <https://docs.databricks.com/aws/en/dev-tools/bundles/settings>
- Databricks bundle authentication:
  <https://docs.databricks.com/aws/en/dev-tools/bundles/authentication>
- Databricks bundle resources:
  <https://docs.databricks.com/aws/en/dev-tools/bundles/resources>
- Databricks SQL parameter markers:
  <https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-parameter-marker>
