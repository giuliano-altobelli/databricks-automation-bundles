# ABAC Jira Project Access SPEC

## Purpose

This bundle defines Jira project-key row access as the first ABAC dogfood slice. It turns the deferred DDL, UDF, and policy-SQL decisions from the design docs into a focused contract for Task 8 SQL sources.

## Owned Objects

The bundle owns the first-slice contract for these objects:

- access map table: `prod_security.access_maps.jira_project_access`
- policy-supporting UDF: `prod_security.policies.can_read_jira_project`

The access key is `project_key`.

## Access Map Contract

The access map grain is one row per effective principal, project key, access level, and source decision. It is an enforcement index for current effective access, not an approval ledger or wide audit table.

Task 8 SQL sources must implement this SQL-facing column contract:

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

Unknown access levels fail closed. The default pattern is allow-only; deny rows are out of scope until a future spec defines conflict-resolution rules.

Coarse RBAC without a current matching effective access row fails closed to zero protected rows.

## UDF Decision

The intended UDF signature is `prod_security.policies.can_read_jira_project(principal STRING, project_key STRING) RETURNS BOOLEAN`.

`prod_security.policies.can_read_jira_project` reads materialized effective access from `prod_security.access_maps.jira_project_access`. It does not dynamically resolve group membership at query time.

The UDF returns true only when there is a current active access-map row for the principal/project where:

- `effective_principal` matches the `principal` argument
- `project_key` matches the `project_key` argument
- `is_active` is true
- access_level in (`read`, `admin_view`)
- current time within the effective range: `valid_from <= current_timestamp()` and `expires_at IS NULL OR current_timestamp() < expires_at`

For missing rows, inactive rows, unknown access levels, future rows, expired rows, or null required inputs, the UDF otherwise returns false.

The UDF is policy-supporting infrastructure for Jira project-key row filtering. Task 8 owns the executable SQL body while preserving this signature and semantics.

## Policy SQL Decision

This bundle owns the first-slice policy SQL contract/fragments for Jira project-key row filtering. Terraform remains owner of stable platform policy definitions and live attachment/rollout controls.

The row filter predicate fragment is expected to call `prod_security.policies.can_read_jira_project(current_user(), project_key)` or a principal argument equivalent supplied by Databricks policy context.

The bundle SQL should therefore provide the reusable predicate fragments and support-object source needed for the Jira slice, while Terraform-controlled platform rollout decides where stable policies attach in live environments.

## Deployment Boundary

Phase 1b remains offline/local for this task. For clarity, no live Databricks resources are created by this task.

Task 7 does not add SQL source files, offline ABAC fixtures, contract-test fixtures, or `databricks.yml`.

## Evidence Expectation

Future CI promotion evidence for this bundle must include:

- repo validation
- changed-bundles
- bundle validation
- ABAC contract tests
- an approved promotion decision matching this bundle and target
