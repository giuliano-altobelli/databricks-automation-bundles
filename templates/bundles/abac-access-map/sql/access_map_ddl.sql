-- Access map for ABAC policy enforcement.
-- This table is an enforcement index for current effective access,
-- not an approval ledger or wide audit table.
CREATE TABLE IF NOT EXISTS __ACCESS_MAP_TABLE__ (
  effective_principal STRING NOT NULL,
  principal_type STRING NOT NULL,
  __ACCESS_KEY__ STRING NOT NULL,
  access_level STRING NOT NULL,
  is_active BOOLEAN NOT NULL,
  valid_from TIMESTAMP NOT NULL,
  expires_at TIMESTAMP,
  source_decision_id STRING NOT NULL,
  source_system STRING NOT NULL,
  updated_at TIMESTAMP NOT NULL
)
COMMENT 'Enforcement index for current access; not an approval ledger.';
