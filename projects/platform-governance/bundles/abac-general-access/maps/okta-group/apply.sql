CREATE OR REPLACE FUNCTION IDENTIFIER(:policy_udf_fqn) (
  okta_group_names ARRAY<STRING>
)
RETURNS BOOLEAN
RETURN
  COALESCE(
    FORALL(
      okta_group_names,
      okta_group_name ->
        CASE
          WHEN okta_group_name IS NULL THEN false
          ELSE is_account_group_member(okta_group_name)
        END
    ),
    false
  );
