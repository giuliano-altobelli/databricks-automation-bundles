# Live Databricks Dev/UAT/Prod Deployment Design

Status: revised design approved; implementation authorized
Original date: 2026-07-08
Revised: 2026-07-09

## Context

Phase 1b shipped the local/offline enforcement and ABAC dogfood slice. It added
the ABAC Jira project access bundle, promotion evidence checks, PR validation,
and the `abac-access-map` template, but intentionally kept the native
Databricks bundle inert.

This slice turns the dogfood bundle into a lightweight live deployment path.
There are two Databricks workspaces:

- `sandbox-infra`, which hosts both personal developer deployments and shared
  UAT
- `prod-infra`, which hosts production

The logical lifecycle therefore has three targets without requiring a third
workspace:

| Target | Workspace | Unity Catalog namespace | Identity | Trigger |
| --- | --- | --- | --- | --- |
| `dev` | `sandbox-infra` | `personal.${workspace.current_user.short_name}` | authenticated developer | attended local command |
| `uat` | `sandbox-infra` | `dev_security.access_maps` and `dev_security.policies` | UAT deployment service principal | trusted pull request CI |
| `prod` | `prod-infra` | `prod_security.access_maps` and `prod_security.policies` | production deployment service principal | push to `main` |

Unity Catalog object names have exactly three components: catalog, schema, and
object. Consequently, both personal dev objects live in the developer's one
schema. For example:

- `personal.giulianoaltobelli.jira_project_access`
- `personal.giulianoaltobelli.can_read_jira_project`

There is no additional `access_maps` or `policies` namespace below a personal
schema.

## Prerequisites

The following platform prerequisites are satisfied outside this bundle:

- the `personal` catalog exists in `sandbox-infra`
- each developer's `personal.<user_key>` schema is Terraform-managed and grants
  that developer the privileges required to create and replace the two objects
- `dev_security.access_maps` and `dev_security.policies` exist in
  `sandbox-infra`
- `prod_security.access_maps` and `prod_security.policies` exist in
  `prod-infra`
- dedicated least-privilege UAT and production service principals exist and
  can use their target SQL warehouses and namespaces
- the UAT principal, not developers, has write access to the shared
  `dev_security` namespaces
- a SQL warehouse exists in each workspace

The bundle does not create catalogs or schemas and does not manage their
grants. Local Databricks CLI profiles must be authenticated after any CLI
upgrade that invalidates the local credential cache.

## Goals

- Let developers validate, deploy, and run the bundle locally in their own
  personal schema without service-principal impersonation.
- Deploy the same SQL to shared UAT from trusted pull requests using the UAT
  service principal.
- Deploy the same SQL to production after a merge to `main` using the
  production service principal.
- Keep SQL target-agnostic and select all destinations with bundle variables.
- Restore `dev`, `uat`, and `prod` as the repository lifecycle contract.

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
The dev target omits `run_as`, so the developer owns the deployed job and
personal Unity Catalog objects. It does not require `Service Principal User` on
the UAT principal.

UAT and production are unattended workflows. GitHub Actions uses OAuth M2M
client credentials for the dedicated service principal in each environment;
developer PATs must never be placed in GitHub Actions.

Each GitHub environment uses the same environment-scoped names:

- variables `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and
  `DATABRICKS_SQL_WAREHOUSE_ID`
- secret `DATABRICKS_CLIENT_SECRET`

The `uat` and `prod` environment boundaries supply different values without
duplicating target names in every setting.

OAuth M2M can be migrated to GitHub OIDC federation later without changing the
bundle or SQL. That migration replaces each client secret with a Databricks
federation policy, uses `DATABRICKS_AUTH_TYPE=github-oidc`, and grants the
deployment job `id-token: write`.

## Target Contract

The native bundle and repository metadata declare exactly `dev`, `uat`, and
`prod`:

- `dev` uses development mode, is the default target, and is local-only
- `uat` uses production mode and is CI-only
- `prod` uses production mode and is CI-only

Production mode is appropriate for UAT because the shared deployment must have
one stable resource identity rather than developer-prefixed resources.

## Bundle Shape

`projects/platform-governance/bundles/abac-jira-project-access/databricks.yml`
defines:

- variables for the access-map catalog, schema, table, policy catalog, policy
  schema, and policy UDF
- an externally supplied SQL warehouse ID
- the three targets and their target-owned namespace values
- one job resource, `apply_abac_jira_project_access`
- one SQL task that executes `sql/apply.sql` with six named parameters

The live objects are:

- `personal.<user_key>.jira_project_access` and
  `personal.<user_key>.can_read_jira_project` for each local dev deployment
- `dev_security.access_maps.jira_project_access` and
  `dev_security.policies.can_read_jira_project` in UAT
- `prod_security.access_maps.jira_project_access` and
  `prod_security.policies.can_read_jira_project` in production
- one target-specific Databricks job resource for applying the SQL

## SQL Parameterization

`sql/apply.sql` is canonical and target-agnostic. The job passes:

- `access_map_catalog`
- `access_map_schema`
- `access_map_table`
- `policy_catalog`
- `policy_schema`
- `policy_udf`

DDL object names use Databricks SQL `IDENTIFIER(:param)`. The bundle never
duplicates SQL by environment or hard-codes a production destination. Existing
fail-closed ABAC contract tests remain authoritative for UDF behavior.

## GitHub Actions Workflows

### Pull Request Workflow

Every pull request runs uncredentialed local verification. A separate job runs
only for same-repository, non-Dependabot pull requests, enters the `uat` GitHub
environment, authenticates with the UAT service principal, and runs:

1. `databricks bundle validate -t uat`
2. `databricks bundle deploy -t uat`
3. `databricks bundle run -t uat apply_abac_jira_project_access`

Separating the jobs ensures fork and Dependabot code never executes on a runner
that receives UAT credentials.

### Main Workflow

On a push to `main`, an uncredentialed verification job runs first. A separate
job then enters the `prod` GitHub environment, authenticates with the
production service principal, and runs:

1. `databricks bundle validate -t prod`
2. `databricks bundle deploy -t prod`
3. `databricks bundle run -t prod apply_abac_jira_project_access`

The production workflow does not upload evidence artifacts in this slice.

## GitHub Environments

GitHub environments are repository-level secret scopes and deployment gates;
they are not Databricks environments or workspaces.

- Create environment `uat`, add the three variables and one secret described
  above, and add selected branch pattern `refs/pull/*/merge`.
- Create environment `prod`, add the same setting names with production values,
  and restrict deployment to `main`.
- A required reviewer is optional. Enabling one intentionally adds a manual
  approval to every deployment using that environment.

## Safety Rules

- Dev deploys only as the authenticated developer and only to their personal
  schema.
- Pull-request deployment targets shared UAT, never production.
- Production deployment runs only from `main`.
- Fork and Dependabot pull requests never receive Databricks credentials.
- Developer PATs are local-only and never used by GitHub Actions.
- The bundle does not create catalogs/schemas, attach row filters, write audit
  records, or mutate Terraform-owned platform controls.
- UAT and production jobs use stable concurrency groups and are not cancelled
  midway through deployment.

## Verification Strategy

Offline tests prove:

- `repoctl validate` requires the `dev`/`uat`/`prod` lifecycle contract
- target modes and CI ownership are correct
- personal dev, shared UAT, and production destinations are target-driven
- workflows contain only the intended target commands and credential scopes
- workflows do not upload evidence artifacts
- existing ABAC fail-closed contract tests still pass

Live local verification proves:

- `databricks bundle validate -t dev -p sandbox-infra` succeeds
- `databricks bundle deploy -t dev -p sandbox-infra` succeeds without a
  service-principal run-as grant
- running the apply job creates or replaces the personal table and UDF

Read-only validation also covers `uat` and `prod`. End-to-end remote verification
is completed by a trusted pull request deployment to UAT and a post-merge
deployment from `main` to production.

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
