import re
from pathlib import Path

from repoctl.changes import classify_changed_files
from repoctl.discovery import discover
from repoctl.metadata import load_metadata

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = (
    ROOT / "projects" / "platform-governance" / "bundles" / "abac-general-access"
)
MAP = BUNDLE / "maps" / "okta-group"
RESOURCE = BUNDLE / "resources" / "okta-group.yml"
METADATA = BUNDLE / "repoctl.bundle.yaml"
CONFIGURATION = BUNDLE / "databricks.yml"
PREFLIGHT = BUNDLE / "sql" / "preflight.sql"
APPLY = MAP / "apply.sql"
FILTER = MAP / "filter.sql"

APPLY_PARAMETERS = {"access_map_table_fqn", "policy_udf_fqn"}
PREFLIGHT_PARAMETERS = {"access_map_schema_fqn", "policy_schema_fqn"}
TABLE_COLUMNS = {
    "effective_principal": ("STRING", "NOT NULL"),
    "okta_group_name": ("STRING", "NOT NULL"),
    "access_level": ("STRING", "NOT NULL"),
    "is_active": ("BOOLEAN", "NOT NULL"),
    "valid_from": ("TIMESTAMP", "NOT NULL"),
    "expires_at": ("TIMESTAMP", "NULL"),
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def uncommented(sql: str) -> str:
    return re.sub(r"--.*", "", sql)


def normalized(sql: str) -> str:
    return re.sub(r"\s+", " ", uncommented(sql)).strip().lower()


def columns(sql: str) -> dict[str, tuple[str, str]]:
    match = re.search(
        r"create\s+table\s+if\s+not\s+exists\s+"
        r"identifier\s*\(\s*:access_map_table_fqn\s*\)\s*"
        r"\((?P<columns>.*?)\)\s*using\s+delta",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None

    result = {}
    for raw in match.group("columns").splitlines():
        line = raw.strip().rstrip(",")
        if not line:
            continue
        column = re.fullmatch(
            r"(?P<name>[a-z_]+)\s+(?P<type>STRING|BOOLEAN|TIMESTAMP)"
            r"(?:\s+(?P<required>NOT\s+NULL))?",
            line,
            flags=re.IGNORECASE,
        )
        assert column is not None, line
        result[column.group("name").lower()] = (
            column.group("type").upper(),
            "NOT NULL" if column.group("required") else "NULL",
        )
    return result


def test_repoctl_discovers_and_classifies_general_collection() -> None:
    discovery = discover(ROOT)
    bundle = next(item for item in discovery.bundles if item.path == BUNDLE)

    assert bundle.name == "abac-general-access"
    assert bundle.project == "platform-governance"
    assert bundle.metadata_path == METADATA
    assert bundle.metadata["type"] == "abac-access-collection"
    assert bundle.metadata["targets"] == {
        "dev": {"mode": "development", "default": True, "local": True},
        "uat": {"mode": "production", "ci_only": True},
        "prod": {"mode": "production", "ci_only": True},
    }

    changed = classify_changed_files(
        ROOT, [(MAP / "apply.sql").relative_to(ROOT).as_posix()]
    )
    assert changed.docs_only is False
    assert changed.affects_all_bundles is False
    assert changed.changed_bundles == [BUNDLE]


def test_native_bundle_has_exact_targets_and_general_destinations() -> None:
    configuration = load_metadata(CONFIGURATION)

    assert set(configuration) == {"bundle", "include", "variables", "targets"}
    assert configuration["bundle"]["name"] == "abac-general-access"
    assert configuration["bundle"]["databricks_cli_version"] == ">= 1.7.0"
    assert configuration["include"] == ["resources/*.yml"]
    assert set(configuration["variables"]) == (
        APPLY_PARAMETERS
        | PREFLIGHT_PARAMETERS
        | {"sql_warehouse_id", "run_as_service_principal_name"}
    )
    assert set(configuration["targets"]) == {"dev", "uat", "prod"}

    destinations = {
        "dev": {
            "access_map_schema_fqn": "personal.${workspace.current_user.short_name}",
            "access_map_table_fqn": (
                "personal.${workspace.current_user.short_name}."
                "okta_group_access"
            ),
            "policy_schema_fqn": "personal.${workspace.current_user.short_name}",
            "policy_udf_fqn": (
                "personal.${workspace.current_user.short_name}."
                "can_read_okta_group"
            ),
        },
        "uat": {
            "access_map_schema_fqn": "dev_security.access_maps",
            "access_map_table_fqn": (
                "dev_security.access_maps.okta_group_access"
            ),
            "policy_schema_fqn": "dev_security.policies",
            "policy_udf_fqn": "dev_security.policies.can_read_okta_group",
        },
        "prod": {
            "access_map_schema_fqn": "prod_security.access_maps",
            "access_map_table_fqn": (
                "prod_security.access_maps.okta_group_access"
            ),
            "policy_schema_fqn": "prod_security.policies",
            "policy_udf_fqn": "prod_security.policies.can_read_okta_group",
        },
    }
    for target, expected in destinations.items():
        assert configuration["targets"][target]["variables"] == expected

    assert configuration["targets"]["dev"]["mode"] == "development"
    assert configuration["targets"]["dev"]["default"] is True
    assert "run_as" not in configuration["targets"]["dev"]
    assert configuration["targets"]["dev"]["workspace"]["root_path"] == (
        "/Workspace/Users/${workspace.current_user.userName}/.bundle/"
        "${bundle.name}/${bundle.target}"
    )

    for target in ("uat", "prod"):
        assert configuration["targets"][target]["mode"] == "production"
        assert configuration["targets"][target]["run_as"] == {
            "service_principal_name": "${var.run_as_service_principal_name}"
        }
        assert configuration["targets"][target]["workspace"]["root_path"] == (
            "/Workspace/Users/${var.run_as_service_principal_name}/.bundle/"
            "${bundle.name}/${bundle.target}"
        )


def test_okta_group_resource_runs_only_preflight_and_apply() -> None:
    assert {path.name for path in (BUNDLE / "resources").glob("*.yml")} == {
        "okta-group.yml"
    }
    assert {path.name for path in (BUNDLE / "maps").iterdir()} == {"okta-group"}
    assert {path.name for path in (BUNDLE / "sql").glob("*.sql")} == {
        "preflight.sql"
    }
    assert {path.name for path in MAP.glob("*.sql")} == {"apply.sql", "filter.sql"}
    assert {path.name for path in (MAP / "fixtures").glob("*.json")} == {
        "cases.json",
        "rows.json",
    }

    resource = load_metadata(RESOURCE)
    jobs = resource["resources"]["jobs"]
    assert len(jobs) == 1
    job = next(iter(jobs.values()))
    assert job["name"] == "apply_abac_okta_group_access"
    assert job["max_concurrent_runs"] == 1

    tasks = {task["task_key"]: task for task in job["tasks"]}
    assert set(tasks) == {
        "preflight_target_schemas",
        "apply_abac_okta_group_access",
    }
    assert "depends_on" not in tasks["preflight_target_schemas"]
    assert tasks["preflight_target_schemas"]["sql_task"]["file"] == {
        "path": "../sql/preflight.sql",
        "source": "WORKSPACE",
    }
    assert tasks["preflight_target_schemas"]["sql_task"]["warehouse_id"] == (
        "${var.sql_warehouse_id}"
    )
    assert tasks["preflight_target_schemas"]["sql_task"]["parameters"] == {
        name: f"${{var.{name}}}" for name in PREFLIGHT_PARAMETERS
    }

    application = tasks["apply_abac_okta_group_access"]
    assert application["depends_on"] == [{"task_key": "preflight_target_schemas"}]
    assert application["sql_task"]["file"] == {
        "path": "../maps/okta-group/apply.sql",
        "source": "WORKSPACE",
    }
    assert application["sql_task"]["warehouse_id"] == "${var.sql_warehouse_id}"
    assert application["sql_task"]["parameters"] == {
        name: f"${{var.{name}}}" for name in APPLY_PARAMETERS
    }
    assert all(
        task["sql_task"]["file"]["path"] != "../maps/okta-group/filter.sql"
        for task in tasks.values()
    )


def test_preflight_is_read_only_and_checks_both_target_schemas() -> None:
    sql = read(PREFLIGHT)
    executable = normalized(sql)

    assert set(re.findall(r":([a-z_]+)", uncommented(sql))) == PREFLIGHT_PARAMETERS
    assert len(re.findall(r"\bdescribe\s+schema\s+identifier\b", executable)) == 2
    assert sum(line.rstrip().endswith(";") for line in sql.splitlines()) == 2
    for keyword in (
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
        assert not re.search(rf"\b{keyword}\b", executable)


def test_apply_sql_defines_exact_map_table_contract() -> None:
    sql = read(APPLY)
    executable = normalized(sql)

    assert columns(sql) == TABLE_COLUMNS
    assert set(re.findall(r":([a-z_]+)", uncommented(sql))) == APPLY_PARAMETERS
    assert len(re.findall(r"\bcreate\s+table\s+if\s+not\s+exists\b", executable)) == 1
    assert len(re.findall(r"\bcreate\s+or\s+replace\s+function\b", executable)) == 1
    assert "jira_project_access" not in executable
    assert "can_read_jira_project" not in executable


def test_okta_group_udf_has_single_array_input_and_resolves_session_identity() -> None:
    executable = normalized(read(APPLY))

    assert re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"identifier\s*\(\s*:policy_udf_fqn\s*\)\s*"
        r"\(\s*okta_group_names\s+array\s*<\s*string\s*>\s*\)\s*"
        r"returns\s+boolean",
        executable,
    )
    assert "session_user()" in executable
    assert "current_user()" not in executable
    assert re.search(
        r"when\s+okta_group_names\s+is\s+null\s+then\s+false", executable
    )
    assert re.search(
        r"when\s+array_size\s*\(\s*okta_group_names\s*\)\s*=\s*0\s+"
        r"then\s+true",
        executable,
    )


def test_okta_group_udf_requires_matched_distinct_group_cardinality() -> None:
    executable = normalized(read(APPLY))

    matched = r"count\s*\(\s*distinct\s+(?:[a-z_]+\.)?okta_group_name\s*\)"
    required = (
        r"array_size\s*\(\s*(?:[a-z_]+\.)?"
        r"(?:requested_)?okta_group_names\s*\)"
    )
    assert re.search(rf"{matched}\s*=\s*{required}", executable)
    assert re.search(
        r"array_contains\s*\(\s*(?:[a-z_]+\.)?"
        r"(?:requested_)?okta_group_names\s*,\s*"
        r"(?:[a-z_]+\.)?okta_group_name\s*\)",
        executable,
    )
    assert re.search(
        r"(?:[a-z_]+\.)?effective_principal\s*=\s*session_user\s*\(\s*\)",
        executable,
    )
    assert re.search(r"(?:[a-z_]+\.)?is_active\s*=\s*true", executable)

    levels = re.search(
        r"(?:[a-z_]+\.)?access_level\s+in\s*\((?P<levels>[^)]+)\)",
        executable,
    )
    assert levels is not None
    assert re.findall(r"'([^']+)'", levels.group("levels")) == [
        "read",
        "admin_view",
    ]
    assert re.search(
        r"(?:[a-z_]+\.)?valid_from\s*<=\s*current_timestamp\s*\(\s*\)",
        executable,
    )
    assert re.search(
        r"(?:[a-z_]+\.)?expires_at\s+is\s+null\s+or\s+"
        r"current_timestamp\s*\(\s*\)\s*<\s*(?:[a-z_]+\.)?expires_at",
        executable,
    )


def test_filter_is_the_production_terraform_predicate_with_one_column_input() -> None:
    predicate = normalized(read(FILTER)).rstrip(";")

    assert predicate == (
        "prod_security.policies.can_read_okta_group(okta_group_names)"
    )
    assert "identifier" not in predicate
    assert ":" not in predicate


def test_bundle_does_not_attach_filters_or_populate_the_mapping_table() -> None:
    executable = normalized(read(APPLY) + "\n" + read(PREFLIGHT))

    for statement in (
        r"\balter\s+table\b",
        r"\bset\s+row\s+filter\b",
        r"\binsert\s+into\b",
        r"\bmerge\s+into\b",
        r"\bupdate\b",
        r"\bdelete\s+from\b",
        r"\bcopy\s+into\b",
        r"\btruncate\s+table\b",
    ):
        assert not re.search(statement, executable)
