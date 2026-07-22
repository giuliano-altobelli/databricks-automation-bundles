from __future__ import annotations

from command import main
from definition import Definition, Filter, Match, Tag

POLICY = Definition(
    name="abac_demo_okta_group_row_filter",
    comment="Filter governed demo rows by the querying user's Okta group membership.",
    scope="CATALOG",
    target="TABLE",
    kind="POLICY_TYPE_ROW_FILTER",
    principals=("okta-databricks-users",),
    exceptions=("giulianoaltobelli@gmail.com",),
    condition=Tag(
        key="abac_boundary",
        value="abac_general_access_okta_group",
    ),
    matches=(
        Match(
            tag=Tag(key="protected_column", value="okta_group_names"),
            alias="okta_group_names_value",
        ),
    ),
    filter=Filter(
        function="can_read_okta_group",
        using=("okta_group_names_value",),
    ),
)


if __name__ == "__main__":
    main(POLICY)
