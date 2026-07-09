# Live Databricks Dev/UAT/Prod Deployment Design

Status: revised design approved; implementation authorized
Original date: 2026-07-08
Reconciled: 2026-07-09

## Context

Phase 1b shipped the local/offline enforcement and ABAC dogfood slice. It added
the Jira project access bundle, promotion evidence checks, PR validation, and
the `abac-access-map` template, while intentionally keeping the native
Databricks bundle inert.

This slice turns that bundle into a lightweight live deployment path. There
are two Databricks workspaces and three logical lifecycle targets:

| Target | Workspace | Unity Catalog namespace | Identity | Trigger |
| --- | --- | --- | --- | --- |
| `dev` | `sandbox-infra` | `personal.${workspace.current_user.short_name}` | authenticated developer | attended local command |
| `uat` | `sandbox-infra` | `dev_security.access_maps` and `dev_security.policies` | UAT deployment service principal | trusted pull request CI |
| `prod` | `prod-infra` | `prod_security.access_maps` and `prod_security.policies` | production deployment service principal | push to `main` |

Unity Catalog names have three components: catalog, schema, and object. Both
personal dev objects therefore live directly in one developer schema, for
example:

- `personal.giulianoaltobelli.jira_project_access`
- `personal.giulianoaltobelli.can_read_jira_project`

There is no additional `access_maps` or `policies` namespace below a personal
schema.

## Preconditions and Ownership

Terraform, not this repository, owns the platform prerequisites:

- the `personal` catalog and each developer's `personal.<user_key>` schema
- `dev_security.access_maps` and `dev_security.policies`
- `prod_security.access_maps` and `prod_security.policies`
- dedicated UAT and production deployment service principals
- target SQL warehouses and their `CAN_USE` grants
- Unity Catalog storage credentials, IAM roles, S3 buckets, and KMS keys

The least-privilege Unity Catalog contract is:

- developer: `USE_CATALOG` on `personal`; `USE_SCHEMA`, `CREATE_TABLE`, and
  `CREATE_FUNCTION` on their personal schema
- UAT/production principal: `USE_CATALOG` on its catalog; `USE_SCHEMA` and
  `CREATE_TABLE` on `access_maps`; `USE_SCHEMA` and `CREATE_FUNCTION` on
  `policies`

Each catalog storage role must grant `kms:Decrypt`, `kms:Encrypt`, and
`kms:GenerateDataKey*` on the actual KMS key ARN, not an alias ARN. The bundle
does not create or repair any of these prerequisites.

The target SQL warehouses must be serverless or provide Databricks Runtime
18.0-or-later SQL semantics. Parameter markers in SQL UDF bodies were verified
on the sandbox serverless warehouse; earlier runtime semantics reject them.

## Goals

- Let developers validate, deploy, and run locally in their own personal
  schema without service-principal impersonation.
- Deploy the same SQL to shared UAT from trusted pull requests using the UAT
  service principal.
- Deploy the same SQL to production after a merge to `main` using the
  production service principal.
- Keep deployable SQL target-agnostic by passing fully qualified object names.
- Enforce the repository-wide `dev`, `uat`, and `prod` lifecycle contract.
- Fail fast on missing target schemas or warehouse configuration before DDL.

## Non-Goals

- No separate UAT workspace.
- No catalog or schema creation.
- No row-filter or ABAC policy attachment.
- No CI evidence artifact upload.
- No Unity Catalog audit writes.
- No migration of Terraform-owned platform controls into this repository.
- No broad design for every future Databricks bundle type.

## Authentication Model

Local dev is an attended user-to-machine workflow. A developer authenticates
the `sandbox-infra` Databricks CLI profile with OAuth and deploys as themself.
The dev target omits `run_as`, so the developer owns the job and personal Unity
Catalog objects. It does not require `Service Principal User` on the UAT
principal.

UAT and production are unattended workflows. GitHub Actions uses OAuth M2M
client credentials for the dedicated principal in each GitHub environment;
developer PATs must never be placed in Actions.

Each GitHub environment uses the same environment-scoped setting names:

- variables `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and
  `DATABRICKS_SQL_WAREHOUSE_ID`
- secret `DATABRICKS_CLIENT_SECRET`

The `uat` and `prod` environment boundaries supply different values without
duplicating target names in every setting.

OAuth M2M can migrate to GitHub OIDC federation later without changing the
bundle or SQL. That migration replaces the client secret with a Databricks
federation policy, uses `DATABRICKS_AUTH_TYPE=github-oidc`, and grants the
deployment job `id-token: write`.

## Target Contract

The native bundle and repository metadata declare exactly `dev`, `uat`, and
`prod`:

- `dev` uses development mode, is the default, and is local-only
- `uat` uses production mode and is CI-only
- `prod` uses production mode and is CI-only

Production mode is appropriate for UAT because the shared deployment requires
one stable resource identity rather than developer-prefixed resources.

## Bundle Shape

`projects/platform-governance/bundles/abac-jira-project-access/databricks.yml`
defines:

- variables for the complete access-map schema/table and policy schema/UDF
  names
- an externally supplied SQL warehouse ID
- the three targets and their target-owned namespace values
- one job resource, `apply_abac_jira_project_access`
- a read-only `preflight` SQL task
- an `apply` SQL task that depends on successful preflight

Preflight describes both target schemas through complete schema FQN
parameters. This fails before DDL when a catalog/schema is missing. Successful
task startup also proves that the configured warehouse exists and is usable.
Preflight never creates or mutates a platform object.

The live objects are:

- `personal.<user_key>.jira_project_access` and
  `personal.<user_key>.can_read_jira_project` for each local dev deployment
- `dev_security.access_maps.jira_project_access` and
  `dev_security.policies.can_read_jira_project` in UAT
- `prod_security.access_maps.jira_project_access` and
  `prod_security.policies.can_read_jira_project` in production
- one target-specific Databricks job resource for applying the SQL

## SQL Contract

The deployable SQL assets are exactly:

- `sql/preflight.sql`
- `sql/apply.sql`

`apply.sql` creates the table and UDF once, using only complete-name markers:

- `access_map_table_fqn`
- `policy_udf_fqn`

Each target supplies those complete values directly. SQL uses
`IDENTIFIER(:access_map_table_fqn)` and
`IDENTIFIER(:policy_udf_fqn)` directly; it does not concatenate name parts with
`|| '.' ||`. This avoids duplicate environment SQL and extra executable string
literals.

`sql/jira_project_row_filter.sql` is deliberately exempt from the
target-agnostic rule. It is a stored production predicate contract consumed by
Terraform's stable policy attachment controls; the bundle never executes it.
Its header must state that boundary explicitly.

Existing fail-closed ABAC contract tests remain authoritative for UDF behavior.
Live verification also proves null input and missing grants return `false`.

## GitHub Actions Workflows

### Pull Request Workflow

Every pull request runs uncredentialed local verification. The validation job
also emits the `repoctl changed` bundle list as a job output.

A separate deployment job runs only when all of these conditions are true:

- the event is `pull_request`
- the pull request originates from this repository
- the author is not Dependabot
- changed-bundle classification contains
  `projects/platform-governance/bundles/abac-jira-project-access`

That job enters the `uat` GitHub environment, authenticates with the UAT
service principal, and runs:

1. `databricks bundle validate -t uat`
2. `databricks bundle deploy -t uat`
3. `databricks bundle run -t uat apply_abac_jira_project_access`

Docs-only pull requests skip UAT. Root tooling changes still deploy because
`repoctl changed` marks every bundle affected. Fork and Dependabot code never
executes on a runner that receives UAT credentials.

### Main Workflow

On push to `main`, an uncredentialed verification job runs before entering the
`prod` environment. Checkout uses full history. After `uv sync`, CI runs the
raw commands equivalent to the local `just verify` wrapper:

1. `uv run pytest -q`
2. `uv run ruff check tools tests`
3. `uv run prek -c prek.toml run --all-files`
4. `uv run repoctl discover`
5. `uv run repoctl validate`
6. `uv run repoctl changed --base "$CHANGED_BASE"`

`CHANGED_BASE` is `github.event.before`, with `github.sha` as the fallback for
a missing or all-zero before SHA.

After verification, a separate production job authenticates with the prod
service principal and runs:

1. `databricks bundle validate -t prod`
2. `databricks bundle deploy -t prod`
3. `databricks bundle run -t prod apply_abac_jira_project_access`

The production workflow does not upload evidence artifacts in this slice.

## GitHub Environments

GitHub environments are repository-level secret scopes and deployment gates;
they are not Databricks workspaces.

- `uat` contains the three variables and one secret above and allows selected
  branch pattern `refs/pull/*/merge`.
- `prod` contains the same setting names with production values and allows
  only branch `main`.
- A required reviewer is optional. Enabling one intentionally adds manual
  approval to every deployment using that environment.

## Safety Rules

- Dev deploys only as the authenticated developer and only to their personal
  schema.
- Pull-request deployment targets shared UAT, never production.
- Docs-only, fork, and Dependabot pull requests never deploy UAT.
- Production deployment runs only from `main`.
- Developer PATs are local-only and never used by GitHub Actions.
- The bundle does not create catalogs/schemas, attach row filters, write audit
  records, or mutate Terraform-owned platform controls.
- UAT and production use stable concurrency groups and are not cancelled
  midway through deployment.

## Guard-Test Retirement

Phase 1b tests that froze the inert/offline state are replaced deliberately:

- the PR no-deploy guard now permits only the credentialed UAT deployment job
  and still rejects dev/prod deployment, promotion, and evidence upload
- the inert native-bundle guard now asserts the live three-target job shape
- SQL tests assert full-FQN marker use and reject environment literals in
  deployable SQL
- policy-fragment tests preserve the Terraform-owned production predicate
- preflight tests require read-only schema checks before apply
- workflow tests require changed-bundle gating and environment credential
  isolation

## Verification Strategy

Offline verification proves:

- `repoctl validate` requires the `dev`/`uat`/`prod` lifecycle contract
- target modes and CI ownership are correct
- personal dev, shared UAT, and production destinations are target-driven
- deployable SQL uses complete-FQN markers and contains no environment literals
- preflight runs before apply and never mutates platform resources
- workflows contain only the intended target commands and credential scopes
- workflows do not upload evidence artifacts
- existing ABAC fail-closed contract tests still pass

Live local verification proves:

- all three targets validate
- dev deploys without service-principal impersonation
- the apply job creates the personal table and UDF under developer ownership
- null inputs and missing access rows return `false`

Remote verification proves:

- a trusted pull request deploys and runs UAT
- a merge to `main` deploys and runs production

## References

- Databricks bundle configuration:
  <https://docs.databricks.com/aws/en/dev-tools/bundles/settings>
- Databricks bundle authentication:
  <https://docs.databricks.com/aws/en/dev-tools/bundles/authentication>
- Databricks deployment modes:
  <https://docs.databricks.com/aws/en/dev-tools/bundles/deployment-modes>
- Databricks SQL parameter markers:
  <https://docs.databricks.com/aws/en/sql/language-manual/sql-ref-parameter-marker>
- GitHub environments:
  <https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments>
