-- Jira project-key row filter predicate fragment.
-- Terraform owns stable live attachment/rollout controls for policies
-- that use this fragment.
prod_security.policies.can_read_jira_project(current_user(), project_key)
