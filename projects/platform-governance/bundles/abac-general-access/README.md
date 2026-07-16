# ABAC General Access Collection

This live Databricks bundle is the deployment boundary for general access
maps. The collection currently owns one access map, `okta-group`, which
manages the shared Okta-group access table and its fail-closed policy-supporting
SQL UDF.

The collection deploys the same target-agnostic SQL through three targets:
isolated local development in the sandbox workspace, shared UAT in that
sandbox, and production in the production workspace.

## Collection Layout

`databricks.yml` owns the collection identity, shared variables, and targets.
It includes the independently runnable access-map jobs from `resources/*.yml`.

The `okta-group` resource in `resources/okta-group.yml` runs a shared read-only
schema preflight and then `maps/okta-group/apply.sql`. Okta-group-specific SQL
and contract fixtures remain together under `maps/okta-group/`; shared SQL
remains under `sql/`.

## Live Resources

The `okta-group` resource creates or updates only:

- `dev`: `personal.<current-user-short-name>.okta_group_access` and
  `personal.<current-user-short-name>.can_read_okta_group`
- `uat`: `dev_security.access_maps.okta_group_access` and
  `dev_security.policies.can_read_okta_group`
- `prod`: `prod_security.access_maps.okta_group_access` and
  `prod_security.policies.can_read_okta_group`

The access map retains the Jira collection's grant lifecycle fields. Each row
maps one effective principal to one Okta group. Only active, currently valid
`read` and `admin_view` grants contribute to access.

The collection does not create catalogs or schemas, populate the access map,
attach row filters, write Unity Catalog audit records, or manage
Terraform-owned platform controls.

## SQL Execution Contract

Targets pass complete fully qualified names into SQL task parameters. The
Okta-group apply task receives `access_map_table_fqn` and `policy_udf_fqn`;
every dynamic object reference is a single marker such as
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

The policy UDF receives the protected row's `okta_group_names` array and
resolves the principal internally with `session_user()`. A row is visible when
the array is empty or every named group has a current qualifying grant for the
session principal. A null array fails closed.

`maps/okta-group/filter.sql` is a production-specific Terraform predicate
contract for `prod_security.policies.can_read_okta_group`. The
Databricks job never executes it; Terraform remains responsible for live
attachment and rollout.

## Local Development Workflow

The `dev` target is local-only. Use an attended Databricks CLI profile for the
sandbox workspace. OAuth U2M is preferred; a personal access token remains a
local-only fallback. Supply the existing sandbox warehouse ID without
committing it:

```bash
export BUNDLE_VAR_sql_warehouse_id="<sandbox-sql-warehouse-id>"

databricks bundle validate -t dev -p sandbox-infra
databricks bundle deploy -t dev -p sandbox-infra
databricks bundle run -t dev -p sandbox-infra okta_group
```

Development-mode deployments and the Okta-group job use the authenticated
developer's identity. The collection resolves both schemas from
`${workspace.current_user.short_name}`, keeping every developer's table and UDF
inside their own `personal` catalog schema. CI must not deploy the `dev` target.

## CI Authentication

Pull-request CI deploys `uat` when this collection is reported as changed.
Main-branch CI deploys `prod` after repository verification. Both workflows use
OAuth M2M. Each target-specific GitHub environment provides these variables:

- variables `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and
  `DATABRICKS_SQL_WAREHOUSE_ID`

The caller repository provides `DATABRICKS_UAT_CLIENT_SECRET` and
`DATABRICKS_PROD_CLIENT_SECRET` as repository secrets. Each deployment caller
passes only its target credential to the reusable workflow, which maps it to
`DATABRICKS_CLIENT_SECRET` for the Databricks CLI. This explicit mapping avoids
GitHub's reusable-workflow limitation for environment secrets. Each caller
repository must define matching `uat` and `prod` environments and both
repository secrets.

For `uat` and `prod`, the authenticated deployment service principal is also
passed as `BUNDLE_VAR_run_as_service_principal_name`. This gives each shared
job and its SQL-created objects one stable run identity and deployment root.
