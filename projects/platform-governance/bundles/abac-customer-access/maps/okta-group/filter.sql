-- Terraform owns stable live attachment and rollout controls for policies
-- that use this production-only predicate. The bundle never executes it.
prod_security.policies.can_read_customer_okta_group(okta_group_names)
