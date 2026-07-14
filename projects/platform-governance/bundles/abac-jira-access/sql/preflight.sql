-- Shared read-only preflight for the schemas required by access-map tasks.
-- The SQL warehouse is verified implicitly when this task starts.
DESCRIBE SCHEMA IDENTIFIER(:access_map_schema_fqn);

DESCRIBE SCHEMA IDENTIFIER(:policy_schema_fqn);
