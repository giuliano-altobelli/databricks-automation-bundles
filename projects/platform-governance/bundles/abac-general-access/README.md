# ABAC General Access Collection

This Databricks Asset Bundle deploys the SQL policy function used to authorize
rows tagged with required Okta account groups. Okta provisions the groups and
their users to Databricks through SCIM, so the bundle does not maintain a
separate access-map table or seed.

## Deployment

The `okta_group` job first verifies the destination policy schema and then
creates or replaces `maps/okta-group/apply.sql` on a serverless SQL warehouse.
It creates or updates only one function per target:

- `dev`: `personal.<current-user-short-name>.can_read_okta_group`
- `uat`: `dev_security.policies.can_read_okta_group`
- `prod`: `prod_security.policies.can_read_okta_group`

The bundle does not create catalogs, schemas, mapping tables, or seed data. It
also does not attach row filters or manage the Terraform-owned production
policy rollout.

Targets pass the complete function name through `policy_udf_fqn` and the apply
SQL references it with `IDENTIFIER(:policy_udf_fqn)`. The read-only preflight
uses `policy_schema_fqn`. Both tasks use the existing warehouse passed through
`sql_warehouse_id`.

## Policy Contract

The policy UDF receives the protected row's `okta_group_names` array. Every
non-null group name must identify an account-level group containing the
connected user according to `is_account_group_member`. This includes indirect
membership resolved by Unity Catalog.

A null array or null array element fails closed. An empty array returns true,
so rows without an Okta-group restriction remain visible. Group membership is
evaluated from the Databricks identity synchronized by SCIM rather than from a
bundle-owned authorization snapshot.

`maps/okta-group/filter.sql` is the production Terraform predicate contract:

```sql
prod_security.policies.can_read_okta_group(okta_group_names)
```

The Databricks job never executes this file.

## Local Development

Use an attended Databricks CLI profile for the sandbox workspace and provide
the existing serverless SQL warehouse without committing it:

```bash
export BUNDLE_VAR_sql_warehouse_id="<sandbox-sql-warehouse-id>"

databricks bundle validate -t dev -p sandbox-infra
databricks bundle deploy -t dev -p sandbox-infra
databricks bundle run -t dev -p sandbox-infra okta_group
```

The `dev` target uses the authenticated developer and writes the UDF to that
developer's `personal` schema. CI must not deploy this target.

## CI Authentication

Pull-request CI deploys `uat`; main-branch CI deploys `prod` after repository
verification. Both use OAuth M2M. Each target-specific GitHub environment
provides `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and
`DATABRICKS_SQL_WAREHOUSE_ID`.

The caller repository provides `DATABRICKS_UAT_CLIENT_SECRET` and
`DATABRICKS_PROD_CLIENT_SECRET` as repository secrets. The deployment service
principal is also passed as `BUNDLE_VAR_run_as_service_principal_name`, giving
shared jobs and SQL-created objects a stable run identity and deployment root.
