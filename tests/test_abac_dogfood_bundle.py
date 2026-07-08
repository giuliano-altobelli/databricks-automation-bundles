import re
from pathlib import Path

from repoctl.discovery import discover
from repoctl.metadata import load_metadata
from repoctl.validation import validate_repo

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = (
    ROOT / "projects" / "platform-governance" / "bundles" / "abac-jira-project-access"
)
EXPECTED_ACCESS_MAP_COLUMNS = {
    "effective_principal": ("STRING", "NOT NULL"),
    "principal_type": ("STRING", "NOT NULL"),
    "project_key": ("STRING", "NOT NULL"),
    "access_level": ("STRING", "NOT NULL"),
    "is_active": ("BOOLEAN", "NOT NULL"),
    "valid_from": ("TIMESTAMP", "NOT NULL"),
    "expires_at": ("TIMESTAMP", "NULL"),
    "source_decision_id": ("STRING", "NOT NULL"),
    "source_system": ("STRING", "NOT NULL"),
    "updated_at": ("TIMESTAMP", "NOT NULL"),
}
SQL_ROOT = BUNDLE_ROOT / "sql"
ACCESS_MAP_DDL = SQL_ROOT / "access_map_ddl.sql"
CAN_READ_UDF = SQL_ROOT / "can_read_jira_project.sql"
JIRA_ROW_FILTER = SQL_ROOT / "jira_project_row_filter.sql"
NATIVE_DAB_CONFIG = BUNDLE_ROOT / "databricks.yml"
REPOCTL_BUNDLE_METADATA = BUNDLE_ROOT / "repoctl.bundle.yaml"


def test_repo_validation_accepts_abac_dogfood_bundle_metadata() -> None:
    result = validate_repo(ROOT)

    assert result.ok is True, result.errors


def test_discovery_finds_abac_dogfood_bundle_with_expected_metadata() -> None:
    result = discover(ROOT)

    bundle = next(
        bundle
        for bundle in result.bundles
        if bundle.path.relative_to(ROOT).as_posix()
        == "projects/platform-governance/bundles/abac-jira-project-access"
    )

    assert bundle.project == "platform-governance"
    assert bundle.name == "abac-jira-project-access"
    assert bundle.metadata_path == REPOCTL_BUNDLE_METADATA
    assert bundle.metadata["type"] == "abac-access-map"


def test_abac_dogfood_native_bundle_boundary_is_inert() -> None:
    assert NATIVE_DAB_CONFIG.is_file()
    assert REPOCTL_BUNDLE_METADATA.is_file()
    assert not (BUNDLE_ROOT / "bundle.yaml").exists()

    config = load_metadata(NATIVE_DAB_CONFIG)

    assert set(config) == {"bundle", "targets"}
    assert config["bundle"]["name"] == "abac-jira-project-access"
    assert set(config["targets"]) == {"dev", "uat", "prod"}
    assert config["targets"]["dev"]["mode"] == "development"
    assert config["targets"]["dev"]["default"] is True
    assert config["targets"]["uat"]["mode"] == "production"
    assert config["targets"]["prod"]["mode"] == "production"
    assert "resources" not in config
    assert "include" not in config
    for target in config["targets"].values():
        assert "resources" not in target


def load_spec() -> str:
    return (BUNDLE_ROOT / "SPEC.md").read_text(encoding="utf-8")


def extract_column_contracts(spec: str) -> dict[str, tuple[str, str]]:
    rows = re.findall(
        r"^\|\s*`(?P<name>[a-z_]+)`\s*\|\s*`(?P<type>[A-Z]+)`\s*\|"
        r"\s*`(?P<nullability>NOT NULL|NULL)`\s*\|",
        spec,
        flags=re.MULTILINE,
    )
    return {
        name: (column_type, nullability)
        for name, column_type, nullability in rows
    }


def load_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalized_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).lower()


def strip_sql_line_comments(sql: str) -> str:
    return re.sub(r"--.*", "", sql)


def extract_access_map_ddl_columns(sql: str) -> dict[str, tuple[str, str]]:
    match = re.search(
        r"create\s+(?:or\s+replace\s+)?table\s+(?:if\s+not\s+exists\s+)?"
        r"prod_security\.access_maps\.jira_project_access\s*\((?P<columns>.*?)\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None

    columns = {}
    for raw_line in match.group("columns").splitlines():
        line = raw_line.split("--", 1)[0].strip().rstrip(",")
        if not line:
            continue

        column_match = re.match(
            r"(?P<name>[a-z_]+)\s+(?P<type>STRING|BOOLEAN|TIMESTAMP)"
            r"(?:\s+(?P<not_null>NOT\s+NULL))?$",
            line,
            flags=re.IGNORECASE,
        )
        assert column_match is not None, line
        nullability = "NOT NULL" if column_match.group("not_null") else "NULL"
        columns[column_match.group("name")] = (
            column_match.group("type").upper(),
            nullability,
        )
    return columns


def extract_allowed_access_levels(spec: str) -> set[str]:
    match = re.search(
        r"Allowed access levels are exactly:\s*(?P<levels>(?:`[a-z_]+`(?:,\s*)?)+)\.",
        spec,
    )
    assert match is not None
    return set(re.findall(r"`([a-z_]+)`", match.group("levels")))


def test_abac_dogfood_spec_keeps_original_boundary_decisions() -> None:
    spec = load_spec()

    required_phrases = [
        "Jira project-key row access",
        "prod_security.access_maps.jira_project_access",
        "prod_security.policies.can_read_jira_project",
        "project_key",
        "one row per effective principal, project key, access level, and source decision",
        "fails closed to zero protected rows",
        "does not dynamically resolve group membership at query time",
        "policy SQL contract/fragments",
        "Terraform remains owner of stable platform policy definitions",
        "live attachment/rollout controls",
        "no live Databricks resources are created by this task",
        "repo validation",
        "changed-bundles",
        "bundle validation",
        "ABAC contract tests",
        "approved promotion decision",
    ]

    for phrase in required_phrases:
        assert phrase in spec


def test_abac_dogfood_spec_defines_sql_facing_access_map_columns() -> None:
    spec = load_spec()

    assert extract_column_contracts(spec) == EXPECTED_ACCESS_MAP_COLUMNS


def test_abac_dogfood_spec_defines_exact_access_level_contract() -> None:
    spec = load_spec()

    assert extract_allowed_access_levels(spec) == {"read", "admin_view"}
    assert "Unknown access levels fail closed." in spec


def test_abac_dogfood_spec_defines_udf_signature_and_policy_predicate() -> None:
    spec = load_spec()

    assert (
        "`prod_security.policies.can_read_jira_project(principal STRING, project_key STRING)"
        " RETURNS BOOLEAN`"
    ) in spec
    assert "current active access-map row for the principal/project" in spec
    assert "access_level in (`read`, `admin_view`)" in spec
    assert "current time within the effective range" in spec
    assert "otherwise returns false" in spec
    assert (
        "`prod_security.policies.can_read_jira_project(current_user(), project_key)`"
        in spec
    )
    assert "principal argument equivalent supplied by Databricks policy context" in spec


def test_abac_dogfood_sql_source_files_exist() -> None:
    assert ACCESS_MAP_DDL.is_file()
    assert CAN_READ_UDF.is_file()
    assert JIRA_ROW_FILTER.is_file()


def test_abac_dogfood_access_map_ddl_matches_spec_column_contract() -> None:
    ddl = load_sql(ACCESS_MAP_DDL)

    assert "prod_security.access_maps.jira_project_access" in ddl
    assert extract_access_map_ddl_columns(ddl) == EXPECTED_ACCESS_MAP_COLUMNS
    assert "enforcement index" in ddl.lower()
    assert "not an approval ledger" in ddl.lower()


def test_abac_dogfood_udf_source_matches_decision_contract() -> None:
    udf = load_sql(CAN_READ_UDF)
    normalized = normalized_sql(udf)
    executable = normalized_sql(strip_sql_line_comments(udf))

    assert "prod_security.policies.can_read_jira_project" in udf
    assert re.search(
        r"\(\s*principal\s+STRING\s*,\s*project_key\s+STRING\s*\)\s*"
        r"RETURNS\s+BOOLEAN",
        udf,
        flags=re.IGNORECASE,
    )
    assert "prod_security.access_maps.jira_project_access" in executable
    assert "effective_principal = principal" not in normalized
    assert "project_key = project_key" not in normalized
    assert re.search(
        r"access_map\.effective_principal\s*=\s*args\.requested_principal",
        executable,
    )
    assert re.search(
        r"access_map\.project_key\s*=\s*args\.requested_project_key",
        executable,
    )
    assert "is_active = true" in executable
    assert re.search(
        r"access_level\s+in\s*\(\s*'read'\s*,\s*'admin_view'\s*\)",
        executable,
    )
    assert re.search(r"valid_from\s+<=\s+current_timestamp\(\)", executable)
    assert re.search(
        r"expires_at\s+is\s+null\s+or\s+current_timestamp\(\)\s+<\s+"
        r"(?:[a-z_]+\.)?expires_at",
        executable,
    )
    assert "principal is null" in executable
    assert "project_key is null" in executable
    assert "false" in executable


def test_abac_dogfood_policy_fragment_calls_udf_and_preserves_terraform_boundary() -> None:
    policy = load_sql(JIRA_ROW_FILTER)

    assert (
        "prod_security.policies.can_read_jira_project(current_user(), project_key)"
        in policy
    )
    assert "Terraform" in policy
    assert "live attachment/rollout controls" in policy
