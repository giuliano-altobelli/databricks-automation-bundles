-- Row filter predicate fragment.
-- Terraform owns stable live attachment/rollout controls for policies
-- that use this fragment.
__POLICY_UDF__(current_user(), __ACCESS_KEY__)
