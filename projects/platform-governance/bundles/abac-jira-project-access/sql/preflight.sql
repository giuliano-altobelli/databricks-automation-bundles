-- Read-only preflight for the two schemas required by the apply task.
-- The SQL warehouse is verified implicitly when this task starts.
DESCRIBE SCHEMA IDENTIFIER(:access_map_schema_fqn);

DESCRIBE SCHEMA IDENTIFIER(:policy_schema_fqn);
