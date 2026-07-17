import json
from pathlib import Path

from repoctl.validation import validate_repo

TARGETS = {
    "dev": {"mode": "development", "default": True, "local": True},
    "uat": {"mode": "production", "ci_only": True},
    "prod": {"mode": "production", "ci_only": True},
}


def write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def project(root: Path) -> Path:
    path = root / "projects" / "platform-governance"
    write(
        path / "project.yaml",
        {
            "version": 1,
            "name": "platform-governance",
            "owner": {"team": "platform-governance"},
            "review": {"policy": "owner-approval"},
        },
    )
    return path


def bundle(
    root: Path,
    name: str,
    mapping: str,
    tables: dict[str, str],
    *,
    seeded: bool = True,
    updater: bool = True,
) -> Path:
    path = root / "projects" / "platform-governance" / "bundles" / name
    write(
        path / "repoctl.bundle.yaml",
        {
            "version": 1,
            "name": name,
            "type": "abac-access-collection",
            "owner": {"team": "platform-governance"},
            "review": {"policy": "owner-approval"},
            "targets": TARGETS,
            "depends_on": {"bundles": [], "libs": []},
        },
    )
    write(
        path / "databricks.yml",
        {
            "bundle": {"name": name},
            "variables": {"access_map_table_fqn": {"description": "table"}},
            "targets": {
                target: {"variables": {"access_map_table_fqn": table}}
                for target, table in tables.items()
            },
        },
    )
    directory = path / "maps" / mapping
    directory.mkdir(parents=True)
    if updater:
        (directory / "update.py").write_text("pass\n", encoding="utf-8")
    if seeded:
        write(directory / f"{mapping}.json", [{"row": 1}])
    write(
        path / "resources" / f"{mapping}.yml",
        {
            "resources": {
                "jobs": {
                    mapping: {
                        "tasks": [
                            {
                                "task_key": "update",
                                "spark_python_task": {
                                    "python_file": f"../maps/{mapping}/update.py",
                                    "parameters": [
                                        "--table",
                                        "${var.access_map_table_fqn}",
                                    ],
                                },
                            }
                        ]
                    }
                }
            }
        },
    )
    return path


def tables(prefix: str) -> dict[str, str]:
    return {
        "dev": f"personal.user.{prefix}",
        "uat": f"dev_security.access_maps.{prefix}",
        "prod": f"prod_security.access_maps.{prefix}",
    }


def test_validate_accepts_one_seed_promoted_to_each_target(tmp_path: Path) -> None:
    project(tmp_path)
    bundle(tmp_path, "general-access", "okta-group", tables("okta_group_access"))

    result = validate_repo(tmp_path)

    assert result.ok is True
    assert result.errors == []


def test_validate_rejects_two_seeds_for_one_target_table(tmp_path: Path) -> None:
    project(tmp_path)
    first = bundle(tmp_path, "general-access", "okta-group", tables("okta_group_access"))
    second_tables = tables("workforce_group_access")
    second_tables["uat"] = "dev_security.access_maps.okta_group_access"
    second = bundle(tmp_path, "workforce-access", "workforce-group", second_tables)

    result = validate_repo(tmp_path)

    assert result.ok is False
    errors = "\n".join(result.errors)
    assert "uat table dev_security.access_maps.okta_group_access has multiple seeds" in errors
    assert str((first / "maps" / "okta-group" / "okta-group.json").relative_to(tmp_path)) in errors
    assert str(
        (second / "maps" / "workforce-group" / "workforce-group.json").relative_to(tmp_path)
    ) in errors


def test_validate_compares_target_tables_case_insensitively(tmp_path: Path) -> None:
    project(tmp_path)
    bundle(tmp_path, "general-access", "okta-group", tables("okta_group_access"))
    second_tables = tables("workforce_group_access")
    second_tables["uat"] = "DEV_SECURITY.ACCESS_MAPS.OKTA_GROUP_ACCESS"
    bundle(tmp_path, "workforce-access", "workforce-group", second_tables)

    result = validate_repo(tmp_path)

    assert result.ok is False
    assert "uat table DEV_SECURITY.ACCESS_MAPS.OKTA_GROUP_ACCESS has multiple seeds" in "\n".join(
        result.errors
    )


def test_validate_rejects_one_seed_bound_to_multiple_tables(tmp_path: Path) -> None:
    project(tmp_path)
    path = bundle(tmp_path, "general-access", "okta-group", tables("okta_group_access"))
    configuration = json.loads((path / "databricks.yml").read_text(encoding="utf-8"))
    configuration["variables"]["other_table_fqn"] = {"description": "other"}
    for target, settings in configuration["targets"].items():
        settings["variables"]["other_table_fqn"] = f"{target}.access.other"
    write(path / "databricks.yml", configuration)
    resource = json.loads(
        (path / "resources" / "okta-group.yml").read_text(encoding="utf-8")
    )
    tasks = resource["resources"]["jobs"]["okta-group"]["tasks"]
    tasks.append(
        {
            "task_key": "other",
            "spark_python_task": {
                "python_file": "../maps/okta-group/update.py",
                "parameters": ["--table", "${var.other_table_fqn}"],
            },
        }
    )
    write(path / "resources" / "okta-group.yml", resource)

    result = validate_repo(tmp_path)

    assert result.ok is False
    assert "maps/okta-group/okta-group.json must bind to exactly one table" in "\n".join(
        result.errors
    )


def test_validate_rejects_an_additional_malformed_updater_task(tmp_path: Path) -> None:
    project(tmp_path)
    path = bundle(tmp_path, "general-access", "okta-group", tables("okta_group_access"))
    resource = json.loads(
        (path / "resources" / "okta-group.yml").read_text(encoding="utf-8")
    )
    tasks = resource["resources"]["jobs"]["okta-group"]["tasks"]
    tasks.append(
        {
            "task_key": "malformed",
            "spark_python_task": {
                "python_file": "../maps/okta-group/update.py",
                "parameters": ["--table"],
            },
        }
    )
    write(path / "resources" / "okta-group.yml", resource)

    result = validate_repo(tmp_path)

    assert result.ok is False
    assert "maps/okta-group/okta-group.json must bind to exactly one table" in "\n".join(
        result.errors
    )


def test_validate_rejects_missing_convention_seed(tmp_path: Path) -> None:
    project(tmp_path)
    bundle(
        tmp_path,
        "general-access",
        "okta-group",
        tables("okta_group_access"),
        seeded=False,
    )

    result = validate_repo(tmp_path)

    assert result.ok is False
    assert "maps/okta-group/okta-group.json is required" in "\n".join(result.errors)


def test_validate_rejects_seed_without_updater(tmp_path: Path) -> None:
    project(tmp_path)
    bundle(
        tmp_path,
        "general-access",
        "okta-group",
        tables("okta_group_access"),
        updater=False,
    )

    result = validate_repo(tmp_path)

    assert result.ok is False
    assert "maps/okta-group/update.py is required" in "\n".join(result.errors)


def test_validate_rejects_additional_direct_seed_json(tmp_path: Path) -> None:
    project(tmp_path)
    path = bundle(tmp_path, "general-access", "okta-group", tables("okta_group_access"))
    write(path / "maps" / "okta-group" / "alternate.json", [{"row": 2}])

    result = validate_repo(tmp_path)

    assert result.ok is False
    errors = "\n".join(result.errors)
    assert "is not a valid seed path; expected" in errors
    assert "general-access/maps/okta-group/alternate.json" in errors
    assert "general-access/maps/okta-group/okta-group.json" in errors


def test_validate_rejects_only_misnamed_direct_seed_json(tmp_path: Path) -> None:
    project(tmp_path)
    path = bundle(
        tmp_path,
        "general-access",
        "okta-group",
        tables("okta_group_access"),
        seeded=False,
        updater=False,
    )
    write(path / "maps" / "okta-group" / "alternate.json", [{"row": 2}])

    result = validate_repo(tmp_path)

    assert result.ok is False
    errors = "\n".join(result.errors)
    assert "general-access/maps/okta-group/alternate.json" in errors
    assert "general-access/maps/okta-group/okta-group.json is required" in errors


def test_validate_rejects_unresolved_target_table_variable(tmp_path: Path) -> None:
    project(tmp_path)
    path = bundle(tmp_path, "general-access", "okta-group", tables("okta_group_access"))
    configuration = json.loads((path / "databricks.yml").read_text(encoding="utf-8"))
    del configuration["targets"]["uat"]["variables"]["access_map_table_fqn"]
    write(path / "databricks.yml", configuration)

    result = validate_repo(tmp_path)

    assert result.ok is False
    assert "uat must resolve table variable access_map_table_fqn" in "\n".join(result.errors)


def test_validate_ignores_fixture_json_and_unseeded_maps(tmp_path: Path) -> None:
    project(tmp_path)
    path = bundle(tmp_path, "general-access", "okta-group", tables("okta_group_access"))
    write(path / "maps" / "okta-group" / "fixtures" / "rows.json", [{"fixture": True}])
    write(path / "maps" / "project" / "fixtures" / "rows.json", [{"fixture": True}])

    result = validate_repo(tmp_path)

    assert result.ok is True
    assert result.errors == []
