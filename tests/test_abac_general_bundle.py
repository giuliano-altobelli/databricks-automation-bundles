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

APPLY_PARAMETERS = {"policy_udf_fqn"}
PREFLIGHT_PARAMETERS = {"policy_schema_fqn"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def uncommented(sql: str) -> str:
    return re.sub(r"--.*", "", sql)


def normalized(sql: str) -> str:
    return re.sub(r"\s+", " ", uncommented(sql)).strip().lower()


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

    for path in (APPLY, FILTER):
        changed = classify_changed_files(ROOT, [path.relative_to(ROOT).as_posix()])
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
            "policy_schema_fqn": "personal.${workspace.current_user.short_name}",
            "policy_udf_fqn": (
                "personal.${workspace.current_user.short_name}."
                "can_read_okta_group"
            ),
        },
        "uat": {
            "policy_schema_fqn": "dev_security.policies",
            "policy_udf_fqn": "dev_security.policies.can_read_okta_group",
        },
        "prod": {
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


def test_okta_group_resource_runs_preflight_and_apply() -> None:
    assert {path.name for path in (BUNDLE / "resources").glob("*.yml")} == {
        "okta-group.yml"
    }
    assert {path.name for path in (BUNDLE / "maps").iterdir()} == {"okta-group"}
    assert {path.name for path in (BUNDLE / "sql").glob("*.sql")} == {
        "preflight.sql"
    }
    assert {path.name for path in MAP.iterdir() if path.is_file()} == {
        "apply.sql",
        "filter.sql",
    }
    assert not (MAP / "fixtures").exists()

    resource = load_metadata(RESOURCE)
    jobs = resource["resources"]["jobs"]
    assert set(jobs) == {"okta_group"}
    job = jobs["okta_group"]
    assert job["name"] == "apply_abac_okta_group_policy"
    assert job["max_concurrent_runs"] == 1
    assert "environments" not in job

    tasks = {task["task_key"]: task for task in job["tasks"]}
    assert set(tasks) == {
        "preflight",
        "apply",
    }
    assert "depends_on" not in tasks["preflight"]
    assert tasks["preflight"]["sql_task"]["file"] == {
        "path": "../sql/preflight.sql",
        "source": "WORKSPACE",
    }
    assert tasks["preflight"]["sql_task"]["warehouse_id"] == (
        "${var.sql_warehouse_id}"
    )
    assert tasks["preflight"]["sql_task"]["parameters"] == {
        name: f"${{var.{name}}}" for name in PREFLIGHT_PARAMETERS
    }

    application = tasks["apply"]
    assert application["depends_on"] == [{"task_key": "preflight"}]
    assert application["sql_task"]["file"] == {
        "path": "../maps/okta-group/apply.sql",
        "source": "WORKSPACE",
    }
    assert application["sql_task"]["warehouse_id"] == "${var.sql_warehouse_id}"
    assert application["sql_task"]["parameters"] == {
        name: f"${{var.{name}}}" for name in APPLY_PARAMETERS
    }

    sql = {
        task["sql_task"]["file"]["path"]
        for task in tasks.values()
        if "sql_task" in task
    }
    assert "../maps/okta-group/filter.sql" not in sql


def test_preflight_is_read_only_and_checks_policy_schema() -> None:
    sql = read(PREFLIGHT)
    executable = normalized(sql)

    assert set(re.findall(r":([a-z_]+)", uncommented(sql))) == PREFLIGHT_PARAMETERS
    assert len(re.findall(r"\bdescribe\s+schema\s+identifier\b", executable)) == 1
    assert sum(line.rstrip().endswith(";") for line in sql.splitlines()) == 1
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


def test_apply_sql_defines_only_policy_udf() -> None:
    sql = read(APPLY)
    executable = normalized(sql)

    assert set(re.findall(r":([a-z_]+)", uncommented(sql))) == APPLY_PARAMETERS
    assert len(re.findall(r"\bcreate\s+or\s+replace\s+function\b", executable)) == 1
    assert not re.search(r"\bcreate\s+table\b", executable)
    assert "access_map" not in executable


def test_okta_group_udf_requires_every_scim_account_group_and_fails_closed() -> None:
    executable = normalized(read(APPLY))

    assert re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"identifier\s*\(\s*:policy_udf_fqn\s*\)\s*"
        r"\(\s*okta_group_names\s+array\s*<\s*string\s*>\s*\)\s*"
        r"returns\s+boolean",
        executable,
    )
    assert "session_user()" not in executable
    assert "current_user()" not in executable
    assert re.search(
        r"return\s+coalesce\s*\(\s*forall\s*\(\s*okta_group_names\s*,",
        executable,
    )
    assert re.search(
        r"okta_group_name\s*->\s*case\s+when\s+okta_group_name\s+is\s+null\s+"
        r"then\s+false\s+else\s+"
        r"is_account_group_member\s*\(\s*okta_group_name\s*\)\s+end",
        executable,
    )
    assert re.search(
        r"is_account_group_member\s*\(\s*okta_group_name\s*\)\s+end\s*\)\s*,\s*"
        r"false\s*\)\s*;?$",
        executable,
    )


def test_filter_is_the_production_terraform_predicate_with_one_column_input() -> None:
    predicate = normalized(read(FILTER)).rstrip(";")

    assert predicate == (
        "prod_security.policies.can_read_okta_group(okta_group_names)"
    )
    assert "identifier" not in predicate
    assert ":" not in predicate


def test_sql_tasks_do_not_attach_filters_or_manage_access_maps() -> None:
    executable = normalized(read(APPLY) + "\n" + read(PREFLIGHT))

    for statement in (
        r"\balter\s+table\b",
        r"\bcreate\s+table\b",
        r"\bdrop\s+table\b",
        r"\bset\s+row\s+filter\b",
        r"\binsert\s+into\b",
        r"\bmerge\s+into\b",
        r"\bupdate\b",
        r"\bdelete\s+from\b",
        r"\bcopy\s+into\b",
        r"\btruncate\s+table\b",
    ):
        assert not re.search(statement, executable)
