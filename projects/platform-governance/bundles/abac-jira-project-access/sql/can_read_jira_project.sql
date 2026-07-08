-- Signature contract:
-- prod_security.policies.can_read_jira_project(principal STRING, project_key STRING) RETURNS BOOLEAN
--
-- The predicate aliases UDF inputs before joining to the access map so
-- column checks remain unambiguous.
CREATE OR REPLACE FUNCTION prod_security.policies.can_read_jira_project(
  principal STRING,
  project_key STRING
)
RETURNS BOOLEAN
RETURN
  CASE
    WHEN principal IS NULL OR project_key IS NULL THEN false
    ELSE EXISTS (
      WITH args AS (
        SELECT
          principal AS requested_principal,
          project_key AS requested_project_key
      )
      SELECT 1
      FROM prod_security.access_maps.jira_project_access AS access_map
      CROSS JOIN args
      WHERE access_map.effective_principal = args.requested_principal
        AND access_map.project_key = args.requested_project_key
        AND access_map.is_active = true
        AND access_map.access_level IN ('read', 'admin_view')
        AND access_map.valid_from <= current_timestamp()
        AND (
          access_map.expires_at IS NULL
          OR current_timestamp() < access_map.expires_at
        )
    )
  END;
