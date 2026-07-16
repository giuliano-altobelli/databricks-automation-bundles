-- This table is an enforcement index for current effective access,
-- not an approval ledger or wide audit table.
CREATE TABLE IF NOT EXISTS IDENTIFIER(:access_map_table_fqn) (
  effective_principal STRING NOT NULL,
  okta_group_name STRING NOT NULL,
  access_level STRING NOT NULL,
  is_active BOOLEAN NOT NULL,
  valid_from TIMESTAMP NOT NULL,
  expires_at TIMESTAMP
)
USING DELTA
COMMENT 'Enforcement index for current Okta-group access; not an approval ledger.'
TBLPROPERTIES ('delta.columnMapping.mode' = 'name');

-- The session principal is resolved inside the security boundary. Null arrays
-- fail closed, while empty arrays intentionally expose the protected row.
CREATE OR REPLACE FUNCTION IDENTIFIER(:policy_udf_fqn) (
  okta_group_names ARRAY<STRING>
)
RETURNS BOOLEAN
RETURN
  SELECT
    CASE
      WHEN okta_group_names IS NULL THEN false
      WHEN array_size(okta_group_names) = 0 THEN true
      ELSE COUNT(DISTINCT access_map.okta_group_name) = array_size(okta_group_names)
    END
  FROM IDENTIFIER(:access_map_table_fqn) AS access_map
  WHERE access_map.effective_principal = session_user()
    AND array_contains(okta_group_names, access_map.okta_group_name)
    AND access_map.is_active = true
    AND access_map.access_level IN ('read', 'admin_view')
    AND access_map.valid_from <= current_timestamp()
    AND (
      access_map.expires_at IS NULL
      OR current_timestamp() < access_map.expires_at
    );
