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

The following objects are required preconditions per target:

- `dev_security` catalog in the `dev` workspace
- `dev_security.access_maps` schema in the `dev` workspace
- `dev_security.policies` schema in the `dev` workspace
- `prod_security` catalog in the `prod` workspace
- `prod_security.access_maps` schema in the `prod` workspace
- `prod_security.policies` schema in the `prod` workspace

Catalog and schema creation is owned by the Terraform repository, not by this
repository or the bundle. State as of 2026-07-09: the prod objects exist; the
dev objects were created manually on 2026-07-08 after discovering they were
missing, and must be reconciled into Terraform ownership (import or recreate)
as a follow-up in the Terraform repository. Preconditions are verified, not
assumed: the apply job includes a read-only preflight check (see Bundle
Shape).

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

The repository metadata contract also moves to this two-target model. `uat`
becomes an unsupported target: `repoctl validate` neither requires nor accepts
it while there is no real UAT workspace.

Dropping `uat` applies repo-wide, not only to the ABAC bundle. This slice
updates every artifact that currently pins the three-target contract:

- `tools/repoctl/src/repoctl/validation.py` required/allowed targets
- `tools/repoctl/src/repoctl/evidence.py` allowed evidence targets
- `schemas/bundle.schema.json` target requirements
- `schemas/evidence/*.json` target enums
- `projects/platform-governance/bundles/foundation-smoke/bundle.yaml`
- `templates/bundles/abac-access-map/repoctl.bundle.yaml`
- `templates/bundles/abac-access-map/databricks.yml`
- `templates/bundle-basic/bundle.yaml`
- README target conventions ("Every bundle declares `dev`, `uat`, and
  `prod`")

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
- a read-only preflight task that verifies the target catalog, schemas, and
  SQL warehouse exist before the apply task runs, failing fast with a clear
  message; the preflight never creates catalogs or schemas
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

`sql/jira_project_row_filter.sql` is exempt from the target-agnostic rule and
is kept as-is. It is not a deployable SQL asset: it is the stored contract
for the row-filter predicate that the Terraform repository attaches in live
environments, per the bundle `SPEC.md` policy SQL decision, so it stays
pinned to `prod_security` on purpose. The deployable SQL assets are exactly
`access_map_ddl.sql` and `can_read_jira_project.sql`; the apply job must not
execute the fragment. Its header comment should state explicitly that it is a
predicate contract fragment consumed by Terraform, not an executable bundle
step. The `abac-access-map` template's `row_filter.sql` keeps the same role.

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

Parameter markers are only legal inside SQL UDF bodies on warehouses with
Databricks Runtime 18.0 or later semantics; Databricks Runtime 17.3 LTS and
earlier reject them there. This was verified against the dev serverless SQL
warehouse on 2026-07-08: creation succeeds, invocation works, and the marker
is constant-folded into the stored function body at creation time. The SQL
warehouses used by the apply job must therefore be serverless or on a channel
with these semantics in every target, including `prod`.

Fully qualified object names should be passed to the SQL as single parameters,
for example `access_map_table_fqn` and `policy_udf_fqn`, composed from the
catalog, schema, and object variables in the `databricks.yml` target
configuration. The SQL itself must not concatenate name parts with string
literals such as `|| '.' ||`; this keeps the executable SQL free of extra
string literals and preserves the offline contract-test literal assertions.

The existing offline fail-closed ABAC contract tests remain authoritative for
UDF behavior. Additional tests should verify that SQL destination selection is
target-driven.

## GitHub Actions Workflows

### Pull Request Workflow

The pull request workflow should keep local verify parity and add dev
deployment as a separate `deploy-dev` job with `needs: validate`. The existing
`validate` job keeps exact local verify parity; deploy steps never mix into
it.

The `deploy-dev` job is gated by the changed-bundle classification the
`validate` job already computes. It runs only when
`projects/platform-governance/bundles/abac-jira-project-access` appears in
the `changed_bundles` output of `uv run repoctl changed`: docs-only pull
requests skip it, and root tooling changes deploy it because the
classification marks all bundles as changed. The `validate` job exposes the
classification as a job output. `deploy-dev` also skips pull requests from
forked repositories, which receive no secrets and would otherwise fail a
deploy step they cannot satisfy.

Expected `validate` job steps:

1. Checkout repository.
2. Install `uv`.
3. Run root verification:
   - `uv run pytest -q`
   - `uv run ruff check tools tests`
   - `uv run prek -c prek.toml run --all-files`
   - `uv run repoctl discover`
   - `uv run repoctl validate`
   - changed-bundle computation into the job summary.

Expected `deploy-dev` job steps:

1. Checkout repository.
2. Install or use the Databricks CLI.
3. Authenticate to the dev workspace with the dev service-principal secrets.
4. From the ABAC bundle root, run:
   - `databricks bundle validate -t dev`
   - `databricks bundle deploy -t dev`
   - `databricks bundle run -t dev apply_abac_jira_project_access`

### Main Workflow

The main workflow deploys to production after a merge to `main`.

`just` stays a local developer convenience wrapper and is not installed in
CI. The workflow runs the raw verification commands equivalent to
`just verify` after `uv sync`, mirroring the pull request workflow. On `push`
events the changed-bundle base is `github.event.before` (the previous `main`
tip), falling back to `github.sha` when `before` is unavailable; this
requires a full-history checkout.

Expected steps:

1. Trigger on push to `main`.
2. Checkout repository with full history.
3. Install `uv`.
4. Bootstrap tooling: `uv sync --locked --all-extras --dev`.
5. Run the raw verification commands equivalent to `just verify`:
   - `uv run pytest -q`
   - `uv run ruff check tools tests`
   - `uv run prek -c prek.toml run --all-files`
   - `uv run repoctl discover`
   - `uv run repoctl validate`
   - `uv run repoctl changed --base "$CHANGED_BASE"`
6. Install or use the Databricks CLI.
7. Authenticate to the prod workspace with the prod service-principal secrets.
8. From the ABAC bundle root, run:
   - `databricks bundle validate -t prod`
   - `databricks bundle deploy -t prod`
   - `databricks bundle run -t prod apply_abac_jira_project_access`

The production workflow does not upload evidence artifacts in this slice.

## Safety Rules

- Production deploy only runs from `main`.
- Pull request deploys only target the shared `dev` workspace.
- Docs-only pull requests must not deploy.
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
- the pull request workflow gates `deploy-dev` on the changed-bundle
  classification.
- the apply job declares the read-only preflight task before the apply task.
- existing ABAC fail-closed contract tests still pass.

### Guard-Test Retirement

Phase 1b guard tests froze the inert/offline state on purpose. This slice
retires or replaces them consciously instead of discovering them as CI
failures:

- `test_pr_validation_workflow_does_not_deploy_or_promote` is replaced by a
  guard that allows `databricks bundle deploy -t dev` in the `deploy-dev` job
  but still forbids `-t prod`, evidence upload, and promotion fragments in
  the pull request workflow.
- `test_pr_validation_workflow_has_full_local_verify_parity` stays unchanged;
  the separate `deploy-dev` job keeps the `validate` job at exact parity.
- `test_abac_dogfood_native_bundle_boundary_is_inert` is replaced by live
  bundle-shape assertions: exactly `dev` and `prod` targets, the documented
  bundle variables, the `apply_abac_jira_project_access` job resource, and no
  catalog or schema creation.
- `test_abac_dogfood_spec_keeps_original_boundary_decisions` and the bundle
  `SPEC.md` are updated together: the "no live Databricks resources are
  created by this task" boundary is superseded by the dev/prod deployment
  contract.
- `test_abac_dogfood_sql_source_files_exist` and
  `test_abac_dogfood_policy_fragment_calls_udf_and_preserves_terraform_boundary`
  stay unchanged: the row-filter fragment file remains the stored predicate
  contract for Terraform attachment.
- SQL assertions that pin `prod_security.*` literals in the DDL and UDF
  sources (and their template-test counterparts) are replaced by
  target-driven assertions.

Local Databricks verification should prove:

- a developer can run `databricks bundle validate -t dev`
- a developer can run `databricks bundle deploy -t dev`
- a developer can run
  `databricks bundle run -t dev apply_abac_jira_project_access`

Remote verification should prove:

- pull request GitHub Actions deploys and runs the bundle against `dev`
- merge to `main` deploys and runs the bundle against `prod`
- the prod SQL warehouse satisfies the SQL-parameterization runtime
  requirement (one-time probe before the first prod deploy, mirroring the dev
  probe from 2026-07-08)

## References

- Databricks bundle configuration:
  <https://docs.databricks.com/aws/en/dev-tools/bundles/settings>
- Databricks bundle authentication:
  <https://docs.databricks.com/aws/en/dev-tools/bundles/authentication>
- Databricks bundle resources:
  <https://docs.databricks.com/aws/en/dev-tools/bundles/resources>
- Databricks SQL parameter markers:
  <https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-parameter-marker>
