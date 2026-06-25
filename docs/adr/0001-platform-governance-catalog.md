# Use `prod_security` as the Platform Governance Catalog

Status: accepted

`prod_security` is reserved as a platform governance catalog, not a normal governed domain catalog. ABAC policies attach to governed domain securables at the highest safe scope, while reusable policy-supporting UDFs live in `prod_security.policies` and access-control support data lives under schemas such as `prod_security.access_maps`, `prod_security.access_audit`, and `prod_security.reference`. This centralizes reusable security/platform controls, avoids divergent domain-local policy behavior, and makes the special access semantics of `prod_security` explicit.

## Considered Options

- Put ABAC support objects in each domain catalog.
- Treat `prod_security` like any other `prod_<source>` governed domain catalog.
- Reserve `prod_security` as a platform governance catalog with special access semantics.

## Consequences

- `prod_security` does not inherit normal governed domain-reader access semantics.
- Reusable platform UDFs default to `prod_security.policies`; domain-specific UDFs require a future scoped spec.
- This ADR records direction only and does not approve live Terraform resources or an implementation rollout.
