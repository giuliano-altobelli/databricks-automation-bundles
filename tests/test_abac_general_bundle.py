import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from repoctl.changes import classify_changed_files
from repoctl.discovery import discover
from repoctl.metadata import load_metadata

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "projects" / "platform-governance" / "bundles"
BUNDLE = (
    BUNDLES / "abac-general-access"
)
ABAC = BUNDLES / "abac"
MAP = BUNDLE / "maps" / "okta-group"
RESOURCE = BUNDLE / "resources" / "okta-group.yml"
METADATA = BUNDLE / "repoctl.bundle.yaml"
CONFIGURATION = BUNDLE / "databricks.yml"
PROJECT = ROOT / "pyproject.toml"
APPLY = MAP / "apply.sql"
CLIENT = ABAC / "client.py"
COMMAND = ABAC / "command.py"
DEFINITION = ABAC / "definition.py"
OKTA = ABAC / "okta.py"
PREFLIGHT = ABAC / "preflight.py"
RECONCILE = ABAC / "reconcile.py"
RENDER = ABAC / "render.py"
STATE = ABAC / "state.py"
SCRIPTS = {CLIENT, COMMAND, DEFINITION, OKTA, PREFLIGHT, RECONCILE, RENDER, STATE}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def uncommented(sql: str) -> str:
    return re.sub(r"--.*", "", sql)


def normalized(sql: str) -> str:
    return re.sub(r"\s+", " ", uncommented(sql)).strip().lower()


def tasks(job: dict[str, object]) -> dict[str, dict[str, object]]:
    return {task["task_key"]: task for task in job["tasks"]}


def source(owner: Path, path: str) -> Path:
    return (owner.parent / path).resolve()


def covered(path: Path, roots: tuple[Path, ...]) -> bool:
    return any(path.is_relative_to(root) for root in roots)


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
    assert bundle.metadata["depends_on"]["libs"] == [
        "projects/platform-governance/bundles/abac"
    ]
    consumers = sorted(
        item.path
        for item in discovery.bundles
        if ABAC.relative_to(ROOT).as_posix()
        in item.metadata["depends_on"]["libs"]
    )
    assert BUNDLE in consumers
    assert all(path.name != "foundation-smoke" for path in consumers)

    for path in {APPLY}:
        changed = classify_changed_files(ROOT, [path.relative_to(ROOT).as_posix()])
        assert changed.docs_only is False
        assert changed.affects_all_bundles is False
        assert changed.changed_bundles == [BUNDLE]

    for path in SCRIPTS:
        changed = classify_changed_files(ROOT, [path.relative_to(ROOT).as_posix()])
        assert changed.docs_only is False
        assert changed.affects_all_bundles is False
        assert changed.changed_bundles == consumers


def test_native_bundle_exposes_only_deployment_location() -> None:
    configuration = load_metadata(CONFIGURATION)

    assert set(configuration) == {
        "bundle",
        "include",
        "sync",
        "variables",
        "targets",
    }
    assert configuration["bundle"] == {
        "name": "abac-general-access",
        "databricks_cli_version": ">= 1.7.0",
    }
    assert configuration["include"] == ["resources/*.yml"]
    assert configuration["sync"] == {"paths": [".", "../abac"]}
    assert set(configuration["variables"]) == {
        "location",
        "sql_warehouse_id",
        "run_as_service_principal_name",
    }
    assert configuration["variables"]["location"]["type"] == "complex"

    locations = {
        "dev": {"schema": "personal.${workspace.current_user.short_name}"},
        "uat": {"schema": "dev_security.policies", "catalog": "dev_abac_demo"},
        "prod": {
            "schema": "prod_security.policies",
            "catalog": "prod_abac_demo",
        },
    }
    for target, location in locations.items():
        assert configuration["targets"][target]["variables"] == {
            "location": location
        }

    dev = configuration["targets"]["dev"]
    assert dev["mode"] == "development"
    assert dev["default"] is True
    assert "run_as" not in dev
    assert "resources" not in dev
    assert dev["workspace"]["root_path"] == (
        "/Workspace/Users/${workspace.current_user.userName}/.bundle/"
        "${bundle.name}/${bundle.target}"
    )

    for target in ("uat", "prod"):
        shared = configuration["targets"][target]
        assert shared["mode"] == "production"
        assert shared["run_as"] == {
            "service_principal_name": "${var.run_as_service_principal_name}"
        }
        assert shared["workspace"]["root_path"] == (
            "/Workspace/Users/${var.run_as_service_principal_name}/.bundle/"
            "${bundle.name}/${bundle.target}"
        )


def test_dev_job_validates_schema_then_applies_only_the_udf() -> None:
    assert {path.name for path in (BUNDLE / "resources").glob("*.yml")} == {
        "okta-group.yml"
    }
    assert {path.name for path in (BUNDLE / "maps").iterdir()} == {"okta-group"}
    assert not (BUNDLE / "sql").exists()
    assert {path.name for path in MAP.iterdir() if path.is_file()} == {
        "apply.sql",
    }
    assert {
        "client.py",
        "command.py",
        "definition.py",
        "okta.py",
        "preflight.py",
        "reconcile.py",
        "render.py",
        "state.py",
    }.issubset({path.name for path in ABAC.iterdir() if path.is_file()})

    resource = load_metadata(RESOURCE)
    job = resource["resources"]["jobs"]["okta_group"]
    assert job["name"] == "apply_abac_okta_group_policy"
    assert job["max_concurrent_runs"] == 1
    assert job["environments"] == [
        {
            "environment_key": "policy",
            "spec": {
                "environment_version": "2",
                "dependencies": ["databricks-sdk==0.121.0"],
            },
        }
    ]
    assert read(PROJECT).count('"databricks-sdk==0.121.0"') == 1

    graph = tasks(job)
    assert set(graph) == {"preflight", "apply"}
    assert graph["preflight"] == {
        "task_key": "preflight",
        "spark_python_task": {
            "python_file": "../../abac/okta.py",
            "parameters": [
                "preflight",
                "--schema",
                "${var.location.schema}",
            ],
        },
        "environment_key": "policy",
    }
    assert graph["apply"] == {
        "task_key": "apply",
        "depends_on": [{"task_key": "preflight"}],
        "sql_task": {
            "file": {
                "path": "../maps/okta-group/apply.sql",
                "source": "WORKSPACE",
            },
            "warehouse_id": "${var.sql_warehouse_id}",
            "parameters": {"schema": "${var.location.schema}"},
        },
    }
    configuration = load_metadata(CONFIGURATION)
    roots = tuple((BUNDLE / path).resolve() for path in configuration["sync"]["paths"])
    preflight = source(RESOURCE, graph["preflight"]["spark_python_task"]["python_file"])
    apply = source(RESOURCE, graph["apply"]["sql_task"]["file"]["path"])
    assert preflight == OKTA
    assert apply == APPLY
    assert covered(preflight, roots)
    assert covered(apply, roots)


def test_shared_targets_add_catalog_validation_and_policy_reconciliation() -> None:
    configuration = load_metadata(CONFIGURATION)
    resource = load_metadata(RESOURCE)
    base = tasks(resource["resources"]["jobs"]["okta_group"])

    for target in ("uat", "prod"):
        catalog = configuration["targets"][target]["variables"]["location"][
            "catalog"
        ]
        job = configuration["targets"][target]["resources"]["jobs"]["okta_group"]
        graph = tasks(job)
        assert set(graph) == {"preflight", "reconcile"}
        assert graph["preflight"] == {
            "task_key": "preflight",
            "spark_python_task": {
                "parameters": [
                    "--catalog",
                    "${var.location.catalog}",
                ],
            },
        }
        assert (
            base["preflight"]["spark_python_task"]["parameters"]
            + graph["preflight"]["spark_python_task"]["parameters"]
        ) == [
            "preflight",
            "--schema",
            "${var.location.schema}",
            "--catalog",
            "${var.location.catalog}",
        ]
        assert base["preflight"]["spark_python_task"]["python_file"] == (
            "../../abac/okta.py"
        )
        assert graph["reconcile"] == {
            "task_key": "reconcile",
            "depends_on": [{"task_key": "apply"}],
            "spark_python_task": {
                "python_file": "../abac/okta.py",
                "parameters": [
                    "reconcile",
                    "--schema",
                    "${var.location.schema}",
                    "--catalog",
                    "${var.location.catalog}",
                ],
            },
            "environment_key": "policy",
        }
        roots = tuple(
            (BUNDLE / path).resolve()
            for path in configuration["sync"]["paths"]
        )
        reconciler = source(
            CONFIGURATION,
            graph["reconcile"]["spark_python_task"]["python_file"],
        )
        assert reconciler == OKTA
        assert covered(reconciler, roots)
        assert catalog in {"dev_abac_demo", "prod_abac_demo"}


def test_shared_policy_entrypoint_accepts_only_operation_and_location(
    tmp_path: Path,
) -> None:
    staged = tmp_path / "abac"
    outside = tmp_path / "outside"
    shutil.copytree(ABAC, staged)
    outside.mkdir()
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment.pop("PYTHONPATH", None)

    for operation in ("preflight", "reconcile"):
        completed = subprocess.run(
            [sys.executable, str(staged / "okta.py"), operation, "--help"],
            cwd=outside,
            check=True,
            capture_output=True,
            env=environment,
            text=True,
        )
        assert "--schema" in completed.stdout
        assert "--catalog" in completed.stdout
        for forbidden in (
            "--definition",
            "--name",
            "--principal",
            "--condition",
            "--function",
        ):
            assert forbidden not in completed.stdout


def test_abac_maps_do_not_copy_the_shared_policy_layout() -> None:
    forbidden = {path.name for path in SCRIPTS} | {"policy.py"}
    collections = (
        bundle
        for bundle in discover(ROOT).bundles
        if bundle.metadata["type"] == "abac-access-collection"
    )

    for bundle in collections:
        maps = bundle.path / "maps"
        if not maps.exists():
            continue
        duplicated = sorted(
            path.relative_to(bundle.path).as_posix()
            for path in maps.rglob("*.py")
            if path.name in forbidden
        )
        assert duplicated == [], bundle.name


def test_apply_sql_defines_only_the_derived_policy_udf() -> None:
    sql = read(APPLY)
    executable = normalized(sql)

    assert set(re.findall(r":([a-z_]+)", uncommented(sql))) == {"schema"}
    assert len(re.findall(r"\bcreate\s+or\s+replace\s+function\b", executable)) == 1
    assert re.search(
        r"identifier\s*\(\s*:schema\s*\|\|\s*'\.can_read_okta_group'\s*\)",
        executable,
    )
    assert not re.search(r"\bcreate\s+table\b", executable)
    assert "access_map" not in executable


def test_okta_group_udf_requires_every_scim_account_group_and_fails_closed() -> None:
    executable = normalized(read(APPLY))

    assert re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"identifier\s*\(\s*:schema\s*\|\|\s*'\.can_read_okta_group'\s*\)\s*"
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


def test_bundle_contains_no_terraform_policy_predicate_or_policy_sql() -> None:
    assert not (MAP / "filter.sql").exists()
    assert not list(BUNDLE.rglob("*.sql")) == []

    executable = normalized("\n".join(read(path) for path in BUNDLE.rglob("*.sql")))
    for statement in (
        r"\balter\s+table\b",
        r"\bcreate\s+policy\b",
        r"\bdrop\s+policy\b",
        r"\bset\s+row\s+filter\b",
    ):
        assert not re.search(statement, executable)


def test_bundle_does_not_embed_authentication_credentials() -> None:
    shared = set(ABAC.glob("*.py"))
    assert SCRIPTS.issubset(shared)
    text = "\n".join(
        read(path) for path in {CONFIGURATION, RESOURCE} | shared
    )
    lowered = text.lower()

    for forbidden in (
        "client_secret",
        "databricks_token",
        "personal access token",
        "dbc-86214b5d-e911",
        "dbc-cc553e0d-3fbe",
    ):
        assert forbidden not in lowered
