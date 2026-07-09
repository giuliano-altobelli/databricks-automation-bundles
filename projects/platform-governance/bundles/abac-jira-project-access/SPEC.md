# ABAC Jira Project Access SPEC

## Purpose

This bundle implements Jira project-key row access as the first live ABAC
dogfood slice. It owns the target-driven access-map table, policy-supporting UDF,
offline fail-closed contract tests, and the Databricks job that applies the SQL.

## Owned Objects

The bundle owns these objects in each active target:

| Target | Access map | Policy-supporting UDF |
| --- | --- | --- |
| `dev` | `personal.<current-user-short-name>.jira_project_access` | `personal.<current-user-short-name>.can_read_jira_project` |
| `uat` | `dev_security.access_maps.jira_project_access` | `dev_security.policies.can_read_jira_project` |
| `prod` | `prod_security.access_maps.jira_project_access` | `prod_security.policies.can_read_jira_project` |

The access key is `project_key`.

## Target and Identity Contract

- `dev` is an attended, local-only target in the sandbox workspace. It deploys
  and runs as the current developer and derives both schemas from
  `${workspace.current_user.short_name}`. CI must not deploy this target.
- `uat` is the shared pull-request target in the sandbox workspace. It deploys
  and runs as the sandbox deployment service principal.
- `prod` is the main-branch target in the production workspace. It deploys and
  runs as the production deployment service principal.

The shared targets use a service-principal-owned deployment root. The local
target uses the current developer's workspace root.

## SQL Parameter Contract

`sql/apply.sql` is target-agnostic. The bundle supplies these named SQL
parameters to `IDENTIFIER(:param)` expressions:

- `access_map_catalog`
- `access_map_schema`
- `access_map_table`
- `policy_catalog`
- `policy_schema`
- `policy_udf`

The SQL source must not hard-code `personal`, `dev_security`, or
`prod_security`.

## Access Map Contract

The access map grain is one row per effective principal, project key, access
level, and source decision. It is an enforcement index for current effective
access, not an approval ledger or wide audit table.

| Column | Type | Nullability | Meaning |
| --- | --- | --- | --- |
| `effective_principal` | `STRING` | `NOT NULL` | Materialized effective principal identity used by policy checks. |
| `principal_type` | `STRING` | `NOT NULL` | Principal kind, such as user or service principal. |
| `project_key` | `STRING` | `NOT NULL` | Jira project key protected by the row policy. |
| `access_level` | `STRING` | `NOT NULL` | Positive access decision for this slice. |
| `is_active` | `BOOLEAN` | `NOT NULL` | Active-state marker for current effective access. |
| `valid_from` | `TIMESTAMP` | `NOT NULL` | Timestamp when the effective access row becomes valid. |
| `expires_at` | `TIMESTAMP` | `NULL` | Nullable timestamp when the effective access row stops being valid. |
| `source_decision_id` | `STRING` | `NOT NULL` | Link back to the source access workflow or approval decision. |
| `source_system` | `STRING` | `NOT NULL` | System that produced the source decision. |
| `updated_at` | `TIMESTAMP` | `NOT NULL` | Timestamp for materialization freshness checks. |

Allowed access levels are exactly: `read`, `admin_view`.

Unknown access levels fail closed. The default pattern is allow-only; deny rows
are out of scope until a future spec defines conflict-resolution rules. Coarse
RBAC without a current matching effective access row fails closed to zero
protected rows.

## UDF Decision

The target-resolved UDF signature is
`can_read_jira_project(principal STRING, project_key STRING) RETURNS BOOLEAN`.
It reads materialized effective access from the target-resolved Jira access map
and does not dynamically resolve group membership at query time.

The UDF returns true only when there is a current active access-map row for the
principal/project where:

- `effective_principal` matches the `principal` argument
- `project_key` matches the `project_key` argument
- `is_active` is true
- access_level in (`read`, `admin_view`)
- current time within the effective range: `valid_from <= current_timestamp()`
  and `expires_at IS NULL OR current_timestamp() < expires_at`

For missing rows, inactive rows, unknown access levels, future rows, expired
rows, or null required inputs, the UDF otherwise returns false.

## Policy SQL Decision

The target-driven row-filter predicate fragment calls
`can_read_jira_project(current_user(), project_key)` after resolving its UDF
identifier from bundle parameters. Terraform remains owner of stable platform
policy definitions and live attachment/rollout controls. This bundle does not
execute or attach the fragment.

## Deployment Boundary

The live bundle creates or updates only the target access-map table, the
policy-supporting UDF, and the `apply_abac_jira_project_access` Databricks job.
It uses an existing SQL warehouse, catalog, and schemas.

Production deploys only from the `main` workflow. Pull-request deployment uses
the `uat` target in the sandbox workspace. The `dev` target remains local-only.
Developer credentials stay local; shared deployments use target service
principals. The workflows do not upload evidence artifacts.

## Verification

Required offline evidence includes repository validation, exact dev/uat/prod
target checks, target-driven SQL assertions, workflow command assertions, and
the ABAC fail-closed contract tests. Live evidence is the validate/deploy/run
command sequence for local dev and the corresponding GitHub Actions runs for
UAT and prod.
