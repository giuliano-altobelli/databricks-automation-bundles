import re
from pathlib import Path

from repoctl.changes import classify_changed_files
from repoctl.discovery import discover
from repoctl.metadata import load_metadata
from repoctl.validation import validate_repo

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = (
    ROOT / "projects" / "platform-governance" / "bundles" / "abac-jira-access"
)
EXPECTED_ACCESS_MAP_COLUMNS = {
    "effective_principal": ("STRING", "NOT NULL"),
    "project_key": ("STRING", "NOT NULL"),
    "access_level": ("STRING", "NOT NULL"),
    "is_active": ("BOOLEAN", "NOT NULL"),
    "valid_from": ("TIMESTAMP", "NOT NULL"),
    "expires_at": ("TIMESTAMP", "NULL"),
}
SQL_ROOT = BUNDLE_ROOT / "sql"
MAP_ROOT = BUNDLE_ROOT / "maps" / "project"
RESOURCE_ROOT = BUNDLE_ROOT / "resources"
APPLY_SQL = MAP_ROOT / "apply.sql"
PREFLIGHT_SQL = SQL_ROOT / "preflight.sql"
JIRA_ROW_FILTER = MAP_ROOT / "filter.sql"
NATIVE_DAB_CONFIG = BUNDLE_ROOT / "databricks.yml"
PROJECT_RESOURCE = RESOURCE_ROOT / "project.yml"
REPOCTL_BUNDLE_METADATA = BUNDLE_ROOT / "repoctl.bundle.yaml"
EXPECTED_APPLY_SQL_PARAMETERS = {
    "access_map_table_fqn",
    "policy_udf_fqn",
}
EXPECTED_PREFLIGHT_SQL_PARAMETERS = {
    "access_map_schema_fqn",
    "policy_schema_fqn",
}
EXPECTED_FQN_VARIABLES = (
    EXPECTED_APPLY_SQL_PARAMETERS | EXPECTED_PREFLIGHT_SQL_PARAMETERS
)
ACCESS_MAP_IDENTIFIER_PATTERN = r"identifier\s*\(\s*:access_map_table_fqn\s*\)"
POLICY_IDENTIFIER_PATTERN = r"identifier\s*\(\s*:policy_udf_fqn\s*\)"


def test_repo_validation_accepts_abac_dogfood_bundle_metadata() -> None:
    result = validate_repo(ROOT)

    assert result.ok is True, result.errors


def test_discovery_finds_abac_dogfood_bundle_with_expected_metadata() -> None:
    result = discover(ROOT)

    bundle = next(
        bundle
        for bundle in result.bundles
        if bundle.path.relative_to(ROOT).as_posix()
        == "projects/platform-governance/bundles/abac-jira-access"
    )

    assert bundle.project == "platform-governance"
    assert bundle.name == "abac-jira-access"
    assert bundle.metadata_path == REPOCTL_BUNDLE_METADATA
    assert bundle.metadata["type"] == "abac-access-collection"


def test_project_map_change_selects_jira_collection_bundle() -> None:
    changed_file = (MAP_ROOT / "apply.sql").relative_to(ROOT).as_posix()

    result = classify_changed_files(ROOT, [changed_file])

    assert result.changed_bundles == [BUNDLE_ROOT]


def test_abac_dogfood_native_bundle_is_live_and_target_driven() -> None:
    assert NATIVE_DAB_CONFIG.is_file()
    assert PROJECT_RESOURCE.is_file()
    assert REPOCTL_BUNDLE_METADATA.is_file()
    assert not (BUNDLE_ROOT / "bundle.yaml").exists()

    config = load_metadata(NATIVE_DAB_CONFIG)
    resource = load_metadata(PROJECT_RESOURCE)

    assert set(config) == {"bundle", "include", "variables", "targets"}
    assert config["bundle"]["name"] == "abac-jira-access"
    assert config["bundle"]["databricks_cli_version"] == ">= 1.7.0"
    assert config["include"] == ["resources/*.yml"]
    assert set(config["variables"]) == EXPECTED_FQN_VARIABLES | {
        "sql_warehouse_id",
        "run_as_service_principal_name",
    }
    assert config["variables"]["run_as_service_principal_name"]["default"] == (
        "${workspace.current_user.userName}"
    )
    assert set(config["targets"]) == {"dev", "uat", "prod"}
    assert config["targets"]["dev"]["mode"] == "development"
    assert config["targets"]["dev"]["default"] is True
    assert config["targets"]["uat"]["mode"] == "production"
    assert config["targets"]["prod"]["mode"] == "production"
    assert "resources" not in config

    expected_target_values = {
        "dev": {
            "access_map_schema_fqn": "personal.${workspace.current_user.short_name}",
            "access_map_table_fqn": (
                "personal.${workspace.current_user.short_name}.jira_project_access"
            ),
            "policy_schema_fqn": "personal.${workspace.current_user.short_name}",
            "policy_udf_fqn": (
                "personal.${workspace.current_user.short_name}.can_read_jira_project"
            ),
        },
        "uat": {
            "access_map_schema_fqn": "dev_security.access_maps",
            "access_map_table_fqn": (
                "dev_security.access_maps.jira_project_access"
            ),
            "policy_schema_fqn": "dev_security.policies",
            "policy_udf_fqn": "dev_security.policies.can_read_jira_project",
        },
        "prod": {
            "access_map_schema_fqn": "prod_security.access_maps",
            "access_map_table_fqn": (
                "prod_security.access_maps.jira_project_access"
            ),
            "policy_schema_fqn": "prod_security.policies",
            "policy_udf_fqn": "prod_security.policies.can_read_jira_project",
        },
    }
    for target_name, expected_values in expected_target_values.items():
        target = config["targets"][target_name]
        assert target["variables"] == expected_values

    assert "run_as" not in config["targets"]["dev"]
    for target_name in ("uat", "prod"):
        target = config["targets"][target_name]
        assert target["run_as"] == {
            "service_principal_name": "${var.run_as_service_principal_name}"
        }

    assert config["targets"]["dev"]["workspace"]["root_path"] == (
        "/Workspace/Users/${workspace.current_user.userName}/.bundle/"
        "${bundle.name}/${bundle.target}"
    )
    for target_name in ("uat", "prod"):
        assert config["targets"][target_name]["workspace"]["root_path"] == (
            "/Workspace/Users/${var.run_as_service_principal_name}/.bundle/"
            "${bundle.name}/${bundle.target}"
        )

    assert set(resource) == {"resources"}
    assert set(resource["resources"]["jobs"]) == {"project"}
    job = resource["resources"]["jobs"]["project"]
    assert job["name"] == "apply_abac_jira_project_access"
    assert job["max_concurrent_runs"] == 1
    assert len(job["tasks"]) == 2
    tasks = {task["task_key"]: task for task in job["tasks"]}
    assert set(tasks) == {
        "preflight_target_schemas",
        "apply_abac_jira_project_access",
    }

    preflight_task = tasks["preflight_target_schemas"]
    assert "depends_on" not in preflight_task
    assert preflight_task["sql_task"]["file"] == {
        "path": "../sql/preflight.sql",
        "source": "WORKSPACE",
    }
    assert preflight_task["sql_task"]["warehouse_id"] == "${var.sql_warehouse_id}"
    assert preflight_task["sql_task"]["parameters"] == {
        name: f"${{var.{name}}}" for name in EXPECTED_PREFLIGHT_SQL_PARAMETERS
    }

    apply_task = tasks["apply_abac_jira_project_access"]
    assert apply_task["depends_on"] == [{"task_key": "preflight_target_schemas"}]
    assert apply_task["sql_task"]["file"] == {
        "path": "../maps/project/apply.sql",
        "source": "WORKSPACE",
    }
    assert apply_task["sql_task"]["warehouse_id"] == "${var.sql_warehouse_id}"
    assert apply_task["sql_task"]["parameters"] == {
        name: f"${{var.{name}}}" for name in EXPECTED_APPLY_SQL_PARAMETERS
    }
    assert all(
        task["sql_task"]["file"]["path"] != "../maps/project/filter.sql"
        for task in tasks.values()
    )


def test_abac_dogfood_collection_contains_only_project_access_map() -> None:
    assert {path.name for path in RESOURCE_ROOT.glob("*.yml")} == {"project.yml"}
    assert {path.name for path in (BUNDLE_ROOT / "maps").iterdir()} == {"project"}


def test_abac_dogfood_native_bundle_does_not_embed_authentication_credentials() -> None:
    config_text = NATIVE_DAB_CONFIG.read_text(encoding="utf-8").lower()

    for forbidden in (
        "client_secret",
        "databricks_token",
        "personal access token",
        "dbc-86214b5d-e911",
        "dbc-cc553e0d-3fbe",
    ):
        assert forbidden not in config_text


def load_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalized_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).lower()


def strip_sql_line_comments(sql: str) -> str:
    return re.sub(r"--.*", "", sql)


def extract_access_map_ddl_columns(sql: str) -> dict[str, tuple[str, str]]:
    match = re.search(
        r"create\s+(?:or\s+replace\s+)?table\s+(?:if\s+not\s+exists\s+)?"
        r"identifier\s*\([^)]*\)\s*\((?P<columns>.*?)\)",
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


def test_abac_dogfood_sql_source_files_exist() -> None:
    assert {path.name for path in SQL_ROOT.glob("*.sql")} == {"preflight.sql"}
    assert {path.name for path in MAP_ROOT.glob("*.sql")} == {"apply.sql", "filter.sql"}
    assert {path.name for path in (MAP_ROOT / "fixtures").glob("*.json")} == {
        "cases.json",
        "rows.json",
    }


def test_abac_dogfood_access_map_ddl_matches_column_contract() -> None:
    ddl = load_sql(APPLY_SQL)
    executable = normalized_sql(strip_sql_line_comments(ddl))

    assert re.search(ACCESS_MAP_IDENTIFIER_PATTERN, ddl, flags=re.IGNORECASE)
    assert extract_access_map_ddl_columns(ddl) == EXPECTED_ACCESS_MAP_COLUMNS
    assert re.search(
        r"create\s+table\s+if\s+not\s+exists\s+"
        + ACCESS_MAP_IDENTIFIER_PATTERN
        + r"\s*\([^;]*?\)\s+using\s+delta\s+comment\s+'.*?'\s+"
        + r"tblproperties\s*\(\s*"
        r"'delta\.columnmapping\.mode'\s*=\s*'name'\s*\)",
        executable,
    )


def test_abac_dogfood_udf_source_matches_decision_contract() -> None:
    udf = load_sql(APPLY_SQL)
    executable = normalized_sql(strip_sql_line_comments(udf))

    assert re.search(POLICY_IDENTIFIER_PATTERN, udf, flags=re.IGNORECASE)
    assert re.search(
        r"\(\s*principal\s+STRING\s*,\s*project_key\s+STRING\s*\)\s*"
        r"RETURNS\s+BOOLEAN",
        udf,
        flags=re.IGNORECASE,
    )
    assert re.search(ACCESS_MAP_IDENTIFIER_PATTERN, executable)
    assert "effective_principal = principal" not in executable
    assert "project_key = project_key" not in executable
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


def test_abac_dogfood_policy_fragment_calls_udf() -> None:
    policy = normalized_sql(strip_sql_line_comments(load_sql(JIRA_ROW_FILTER)))

    assert (
        "prod_security.policies.can_read_jira_project(current_user(), project_key)"
        in policy
    )
    assert "identifier" not in policy
    assert ":" not in policy


def test_abac_dogfood_sql_destinations_are_entirely_target_driven() -> None:
    apply_sql = strip_sql_line_comments(load_sql(APPLY_SQL))
    preflight_sql = strip_sql_line_comments(load_sql(PREFLIGHT_SQL))

    assert set(re.findall(r":([a-z_]+)", apply_sql)) == (
        EXPECTED_APPLY_SQL_PARAMETERS
    )
    assert set(re.findall(r":([a-z_]+)", preflight_sql)) == (
        EXPECTED_PREFLIGHT_SQL_PARAMETERS
    )
    for target_catalog in ("personal", "dev_security", "prod_security"):
        assert target_catalog not in apply_sql.lower()
        assert target_catalog not in preflight_sql.lower()


def test_abac_dogfood_deployable_sql_uses_only_single_marker_identifiers() -> None:
    deployable_sql = load_sql(APPLY_SQL) + "\n" + load_sql(PREFLIGHT_SQL)
    identifier_arguments = re.findall(
        r"identifier\s*\((?P<argument>[^)]*)\)",
        deployable_sql,
        flags=re.IGNORECASE,
    )

    assert identifier_arguments
    assert {argument.strip() for argument in identifier_arguments} == {
        ":access_map_schema_fqn",
        ":access_map_table_fqn",
        ":policy_schema_fqn",
        ":policy_udf_fqn",
    }
    assert "||" not in deployable_sql
    assert "'.'" not in deployable_sql


def test_abac_dogfood_preflight_is_read_only_and_checks_both_schemas() -> None:
    preflight_sql = load_sql(PREFLIGHT_SQL)
    executable = normalized_sql(strip_sql_line_comments(preflight_sql))

    assert len(re.findall(r"\bdescribe schema identifier\b", executable)) == 2
    assert sum(line.rstrip().endswith(";") for line in preflight_sql.splitlines()) == 2
    for mutating_keyword in (
        "alter",
        "create",
        "delete",
        "drop",
        "insert",
        "merge",
        "replace",
        "truncate",
        "update",
    ):
        assert not re.search(rf"\b{mutating_keyword}\b", executable)


def test_abac_dogfood_apply_sql_has_one_copy_of_each_deployable_statement() -> None:
    apply_sql = load_sql(APPLY_SQL)
    executable = normalized_sql(strip_sql_line_comments(apply_sql))

    assert len(re.findall(r"\bcreate table if not exists\b", executable)) == 1
    assert len(re.findall(r"\bcreate or replace function\b", executable)) == 1
    assert sum(line.rstrip().endswith(";") for line in apply_sql.splitlines()) == 2
    assert "Databricks notebook source" not in apply_sql
    assert "COMMAND ----------" not in apply_sql


def test_abac_dogfood_apply_sql_does_not_attach_row_filters() -> None:
    executable = normalized_sql(strip_sql_line_comments(load_sql(APPLY_SQL)))

    assert "set row filter" not in executable
    assert "row filter" not in executable
    assert "alter table" not in executable
