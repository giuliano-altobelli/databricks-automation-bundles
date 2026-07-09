-- Jira project-key row filter predicate fragment.
-- Terraform owns stable live attachment/rollout controls for policies
-- that use this fragment.
IDENTIFIER(:policy_catalog || '.' || :policy_schema || '.' || :policy_udf)(
  current_user(),
  project_key
)
