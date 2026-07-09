# ABAC Jira Project Access Bundle

This live Databricks bundle owns the Jira project-key access map and its
policy-supporting, fail-closed SQL UDF. It deploys the same target-agnostic SQL
through three targets: isolated local development in the sandbox workspace,
shared UAT in that sandbox, and production in the prod workspace.

## Live Resources

The `apply_abac_jira_project_access` job runs a read-only schema preflight and
then `sql/apply.sql` on an existing SQL warehouse. The apply task creates or
updates only:

- `dev`: `personal.<current-user-short-name>.jira_project_access` and
  `personal.<current-user-short-name>.can_read_jira_project`
- `uat`: `dev_security.access_maps.jira_project_access` and
  `dev_security.policies.can_read_jira_project`
- `prod`: `prod_security.access_maps.jira_project_access` and
  `prod_security.policies.can_read_jira_project`

The bundle does not create catalogs or schemas, attach row filters, write Unity
Catalog audit records, or manage Terraform-owned platform controls.

## SQL Execution Contract

The targets pass complete fully qualified names into SQL task parameters. The
apply task receives `access_map_table_fqn` and `policy_udf_fqn`; every dynamic
object reference is a single marker such as
`IDENTIFIER(:access_map_table_fqn)`. Deployable SQL never constructs an object
name with string concatenation.

Before apply, `sql/preflight.sql` uses `DESCRIBE SCHEMA` to check
`access_map_schema_fqn` and `policy_schema_fqn`. This task is read-only and must
succeed before any DDL runs. The warehouse is verified implicitly when the
preflight task starts, so the SQL does not attempt a separate warehouse check.

The SQL file task is intended for a serverless SQL warehouse and follows
Databricks SQL / Databricks Runtime 18.0 or later parameter-marker semantics.
Passing each FQN as one marker also avoids the identifier-expression
concatenation deprecated in DBR 18.

`sql/jira_project_row_filter.sql` is a production-specific Terraform predicate
contract for `prod_security.policies.can_read_jira_project`. The Databricks job
never executes it; Terraform remains responsible for live attachment and
rollout.

## Local Dev Workflow

The `dev` target is local-only. Use an attended Databricks CLI profile for the
sandbox workspace. OAuth U2M is preferred; a personal access token remains a
local-only fallback. Supply the existing sandbox warehouse ID without
committing it:

```bash
export BUNDLE_VAR_sql_warehouse_id="<sandbox-sql-warehouse-id>"

databricks bundle validate -t dev -p sandbox-infra
databricks bundle deploy -t dev -p sandbox-infra
databricks bundle run -t dev -p sandbox-infra apply_abac_jira_project_access
```

Development-mode deployments and the SQL apply job use the authenticated
developer's identity. The bundle resolves both schemas from
`${workspace.current_user.short_name}`, keeping every developer's table and UDF
inside their own `personal` catalog schema. CI must not deploy the `dev` target.

## CI Authentication

Pull-request CI deploys `uat` to the sandbox workspace with the sandbox
deployment service principal. Main-branch CI deploys `prod` with the production
deployment service principal. Both workflows use OAuth M2M and read the same
names from their target-specific GitHub environment; credentials are never
stored in this bundle:

- environment variables `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and
  `DATABRICKS_SQL_WAREHOUSE_ID`
- environment secret `DATABRICKS_CLIENT_SECRET`

For `uat` and `prod`, the authenticated deployment service principal is also
passed as `BUNDLE_VAR_run_as_service_principal_name`. This gives each shared
job and its SQL-created objects one stable run identity and deployment root.

OAuth M2M can later be replaced with GitHub OIDC federation by changing only
the workflow authentication block and Databricks federation configuration.
