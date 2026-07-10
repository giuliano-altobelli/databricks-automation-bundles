-- Production-only Jira project-key row-filter predicate contract.
-- Terraform owns stable live attachment/rollout controls for policies
-- that use this fragment. The Databricks bundle never executes this file.
prod_security.policies.can_read_jira_project(current_user(), project_key)
