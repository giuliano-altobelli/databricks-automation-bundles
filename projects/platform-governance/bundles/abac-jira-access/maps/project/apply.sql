-- Jira project access-map implementation for ABAC policy enforcement.
-- This table is an enforcement index for current effective access,
-- not an approval ledger or wide audit table.
CREATE TABLE IF NOT EXISTS IDENTIFIER(:access_map_table_fqn) (
  effective_principal STRING NOT NULL,
  project_key STRING NOT NULL,
  access_level STRING NOT NULL,
  is_active BOOLEAN NOT NULL,
  valid_from TIMESTAMP NOT NULL,
  expires_at TIMESTAMP
)
USING DELTA
COMMENT 'Enforcement index for current Jira project access; not an approval ledger.'
TBLPROPERTIES ('delta.columnMapping.mode' = 'name');

-- The session principal is resolved inside the security boundary. The project
-- key is aliased before joining so column checks remain unambiguous. Null keys
-- and missing, inactive, unsupported, not-yet-valid, or expired grants fail closed.
CREATE OR REPLACE FUNCTION IDENTIFIER(:policy_udf_fqn) (
  project_key STRING
)
RETURNS BOOLEAN
RETURN
  CASE
    WHEN project_key IS NULL THEN false
    ELSE EXISTS (
      WITH args AS (
        SELECT project_key AS requested_project_key
      )
      SELECT 1
      FROM IDENTIFIER(:access_map_table_fqn) AS access_map
      CROSS JOIN args
      WHERE access_map.effective_principal = session_user()
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
