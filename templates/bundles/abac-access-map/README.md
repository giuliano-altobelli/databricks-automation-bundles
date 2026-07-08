# ABAC Access-Map Bundle Template

This template is a starting point for a Databricks ABAC access-map bundle.
Copy this directory into `projects/<project>/bundles/<bundle>/`, then replace
the placeholders with bundle-specific values.

Required replacements:

- `__BUNDLE_NAME__`
- `__OWNER_TEAM__`
- `__ACCESS_MAP_TABLE__`
- `__POLICY_UDF__`
- `__ACCESS_KEY__`

`__ACCESS_KEY__` must be a valid SQL identifier because it is rendered into
table DDL, UDF arguments, fixture keys, and row-filter fragments.
`__ACCESS_MAP_TABLE__` and `__POLICY_UDF__` should be fully qualified object names,
for example `prod_security.access_maps.customer_region_access` and
`prod_security.policies.can_read_customer_region`.

The template uses `repoctl.bundle.yaml` for repoctl metadata because native
Databricks Asset Bundle configuration also lives in `databricks.yml`. Do not
rename `repoctl.bundle.yaml` to `bundle.yaml` for native DAB bundle roots.

The included `databricks.yml` is intentionally inert: it declares only the
native bundle name and targets, with no resources or include entries.
