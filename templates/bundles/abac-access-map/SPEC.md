# __BUNDLE_NAME__ SPEC

## Purpose

This bundle defines an ABAC access-map contract for `__ACCESS_KEY__`-based row
access. It provides the access-map table contract, policy-supporting UDF
contract, row-filter SQL fragment, local fixtures, and evidence expectations
needed before live policy rollout.

## Owned Objects

The bundle owns the contract for these objects:

- access map table: `__ACCESS_MAP_TABLE__`
- policy-supporting UDF: `__POLICY_UDF__`

The access key is `__ACCESS_KEY__`.

## Access Map Contract

The access map grain is one row per effective principal, `__ACCESS_KEY__`,
access level, and source decision. It is an enforcement index for current
effective access, not an approval ledger or wide audit table.

SQL sources must implement this SQL-facing column contract:

| Column | Type | Nullability | Meaning |
| --- | --- | --- | --- |
| `effective_principal` | `STRING` | `NOT NULL` | Materialized effective principal identity used by policy checks. |
| `principal_type` | `STRING` | `NOT NULL` | Principal kind, such as user or service principal. |
| `__ACCESS_KEY__` | `STRING` | `NOT NULL` | Protected access key value used by the row policy. |
| `access_level` | `STRING` | `NOT NULL` | Positive access decision for this slice. |
| `is_active` | `BOOLEAN` | `NOT NULL` | Active-state marker for current effective access. |
| `valid_from` | `TIMESTAMP` | `NOT NULL` | Timestamp when the effective access row becomes valid. |
| `expires_at` | `TIMESTAMP` | `NULL` | Nullable timestamp when the effective access row stops being valid. |
| `source_decision_id` | `STRING` | `NOT NULL` | Link back to the source access workflow or approval decision. |
| `source_system` | `STRING` | `NOT NULL` | System that produced the source decision. |
| `updated_at` | `TIMESTAMP` | `NOT NULL` | Timestamp for materialization freshness checks. |

Allowed access levels are exactly: `read`, `admin_view`.

Unknown access levels fail closed. The default pattern is allow-only; deny rows
are out of scope until a future spec defines conflict-resolution rules.

Coarse RBAC without a current matching effective access row fails closed to zero
protected rows.

## UDF Decision

The intended UDF signature is `__POLICY_UDF__(principal STRING, __ACCESS_KEY__ STRING) RETURNS BOOLEAN`.

`__POLICY_UDF__` reads materialized effective access from `__ACCESS_MAP_TABLE__`.
It does not dynamically resolve group membership at query time.

The UDF returns true only when there is a current active access-map row for the
principal and `__ACCESS_KEY__` where:

- `effective_principal` matches the `principal` argument
- `__ACCESS_KEY__` matches the `__ACCESS_KEY__` argument
- `is_active` is true
- access_level in (`read`, `admin_view`)
- current time within the effective range: `valid_from <= current_timestamp()` and `expires_at IS NULL OR current_timestamp() < expires_at`

For missing rows, inactive rows, unknown access levels, future rows, expired
rows, or null required inputs, the UDF otherwise returns false.

## Policy SQL Decision

This bundle owns the reusable policy SQL contract/fragments for
`__ACCESS_KEY__` row filtering. Terraform remains owner of stable platform
policy definitions and live attachment/rollout controls.

The row-filter predicate fragment is expected to call
`__POLICY_UDF__(current_user(), __ACCESS_KEY__)` or a principal argument
equivalent supplied by Databricks policy context.

The bundle SQL should provide reusable predicate fragments and support-object
source needed for this access-map slice, while Terraform-controlled platform
rollout decides where stable policies attach in live environments.

## Deployment Boundary

This template creates no live Databricks resources. The native `databricks.yml`
is present only to establish the Databricks Asset Bundle boundary.

## Evidence Expectation

Promotion evidence for this bundle must include:

- repo validation
- changed-bundles
- bundle validation
- ABAC contract tests
- an approved promotion decision matching this bundle and target
