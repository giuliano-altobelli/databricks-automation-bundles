# ABAC General Access Collection

This Databricks Asset Bundle owns the Okta-group row-filter function and the
complete `abac_demo_okta_group_row_filter` ABAC policy definition. Terraform
continues to own the destination catalogs and schemas, but does not own this
policy.

## Target Matrix

| Target | Function schema | Policy scope |
| --- | --- | --- |
| `dev` | `personal.<current-user-short-name>` | None |
| `uat` | `dev_security.policies` | Catalog `dev_abac_demo` |
| `prod` | `prod_security.policies` | Catalog `prod_abac_demo` |

The complex bundle variable `location` contains only these deployment
locations. Policy behavior is not exposed through bundle variables, job
parameters, or run-time overrides.

## Deployment

The `dev` job graph is:

```text
preflight -> apply
```

It validates the personal function schema and creates or replaces only
`can_read_okta_group`.

The `uat` and `prod` graph is:

```text
preflight -> apply -> reconcile
```

Before the first mutation, preflight verifies that the destination function
schema, policy catalog, and these governed tag dependencies already exist:

- `abac_boundary=abac_general_access_okta_group`
- `protected_column=okta_group_names`

All validation failures are aggregated and fail the job. Missing dependencies,
unreadable dependencies, and API failures all prevent the function and policy
tasks from running.

The reconciler uses `databricks-sdk==0.121.0` and the public ABAC policy API:

- A missing policy is created from the complete checked-in definition.
- An equal policy is left unchanged.
- Mutable drift is repaired with `update_policy` and an explicit field mask.
- Every create or update is followed by an exact read and convergence check.
- An identity mismatch returned by an exact read fails as an explicit migration.

The controller does not list, delete, prune, or move policies. If function
replacement succeeds and policy reconciliation fails, the failed run is safe
to repeat. Because policy scope is part of the API lookup key, changing a
target catalog requires a reviewed migration; the controller cannot discover a
same-named policy stranded in a previous catalog.

## Policy Contract

The policy applies to tables in its target catalog when the table has
`abac_boundary=abac_general_access_okta_group`. It matches the protected column
tagged `protected_column=okta_group_names`, aliases that column as
`okta_group_names_value`, and passes it to the target-specific
`can_read_okta_group` function.

The policy applies to `okta-databricks-users` except
`giulianoaltobelli@gmail.com`.

The function requires every non-null group name in the protected row to be an
account-level group containing the connected user according to
`is_account_group_member`. A null array or null element fails closed. An empty
array returns true.

## Terraform Cutover

Terraform must remove its UAT policy before the first UAT bundle run. After UAT
convergence is verified, Terraform must remove its production policy before the
first production bundle run. No zero-policy-gap migration is required.

## Local Development

Use an attended Databricks CLI profile and provide the existing serverless SQL
warehouse without committing it:

```bash
export BUNDLE_VAR_sql_warehouse_id="<sandbox-sql-warehouse-id>"

databricks bundle validate -t dev -p sandbox-infra
databricks bundle deploy -t dev -p sandbox-infra
databricks bundle run -t dev -p sandbox-infra okta_group
```

The local target never creates or reconciles an ABAC policy.

## CI Authentication

Pull-request CI deploys `uat`; main-branch CI deploys `prod` after repository
verification. Both use OAuth M2M. Each target-specific GitHub environment
provides `DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, and
`DATABRICKS_SQL_WAREHOUSE_ID`.

The caller repository provides `DATABRICKS_UAT_CLIENT_SECRET` and
`DATABRICKS_PROD_CLIENT_SECRET`. The deployment service principal is passed as
`BUNDLE_VAR_run_as_service_principal_name`, giving the shared job and created
objects a stable run identity and deployment root.
