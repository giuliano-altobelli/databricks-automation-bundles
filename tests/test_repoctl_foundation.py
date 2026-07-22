import json
import subprocess
import sys
from pathlib import Path

import pytest
from repoctl.changes import classify_changed_files
from repoctl.discovery import discover
from repoctl.metadata import load_metadata
from repoctl.validation import validate_repo

ROOT = Path(__file__).resolve().parents[1]


def write_json_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def write_foundation_fixture(root: Path) -> Path:
    project_root = root / "projects" / "platform-governance"
    bundle_root = project_root / "bundles" / "foundation-smoke"

    write_json_yaml(
        project_root / "project.yaml",
        {
            "version": 1,
            "name": "platform-governance",
            "owner": {"team": "platform-governance"},
            "review": {"policy": "owner-approval"},
        },
    )
    write_json_yaml(
        bundle_root / "bundle.yaml",
        {
            "version": 1,
            "name": "foundation-smoke",
            "type": "generic",
            "owner": {"team": "platform-governance"},
            "review": {"policy": "owner-approval"},
            "targets": {
                "dev": {"mode": "development", "default": True, "local": True},
                "uat": {"mode": "production", "ci_only": True},
                "prod": {"mode": "production", "ci_only": True},
            },
            "depends_on": {"bundles": [], "libs": []},
        },
    )
    return bundle_root


def test_discover_finds_project_bundle_scaling_unit(tmp_path: Path) -> None:
    bundle_root = write_foundation_fixture(tmp_path)

    result = discover(tmp_path)

    assert [project.name for project in result.projects] == ["platform-governance"]
    assert [bundle.name for bundle in result.bundles] == ["foundation-smoke"]
    assert result.bundles[0].project == "platform-governance"
    assert result.bundles[0].path == bundle_root
    assert result.bundles[0].metadata_path == bundle_root / "bundle.yaml"


def test_discover_prefers_repoctl_bundle_metadata_when_present(tmp_path: Path) -> None:
    bundle_root = write_foundation_fixture(tmp_path)
    write_json_yaml(
        bundle_root / "repoctl.bundle.yaml",
        {
            "version": 1,
            "name": "foundation-smoke",
            "type": "repoctl-native-boundary",
            "owner": {"team": "platform-governance"},
            "review": {"policy": "owner-approval"},
            "targets": {
                "dev": {"mode": "development", "default": True, "local": True},
                "uat": {"mode": "production", "ci_only": True},
                "prod": {"mode": "production", "ci_only": True},
            },
            "depends_on": {"bundles": [], "libs": []},
        },
    )

    result = discover(tmp_path)

    assert [bundle.name for bundle in result.bundles] == ["foundation-smoke"]
    assert result.bundles[0].metadata["type"] == "repoctl-native-boundary"
    assert result.bundles[0].metadata_path == bundle_root / "repoctl.bundle.yaml"


def test_validate_accepts_minimal_foundation_metadata(tmp_path: Path) -> None:
    write_foundation_fixture(tmp_path)

    result = validate_repo(tmp_path)

    assert result.ok is True
    assert result.errors == []


def test_validate_accepts_an_existing_repository_relative_library(
    tmp_path: Path,
) -> None:
    bundle = write_foundation_fixture(tmp_path)
    shared = tmp_path / "projects" / "platform-governance" / "bundles" / "abac"
    shared.mkdir()
    metadata = load_metadata(bundle / "bundle.yaml")
    metadata["depends_on"]["libs"] = [
        "projects/platform-governance/bundles/abac"
    ]
    write_json_yaml(bundle / "bundle.yaml", metadata)

    result = validate_repo(tmp_path)

    assert result.ok is True
    assert result.errors == []


def test_validate_rejects_the_repository_root_as_a_shared_library(
    tmp_path: Path,
) -> None:
    bundle = write_foundation_fixture(tmp_path)
    metadata = load_metadata(bundle / "bundle.yaml")
    metadata["depends_on"]["libs"] = ["."]
    write_json_yaml(bundle / "bundle.yaml", metadata)

    validation = validate_repo(tmp_path)

    assert validation.ok is False
    assert "must reference a canonical repository subdirectory" in "\n".join(
        validation.errors
    )


def test_validate_rejects_a_shared_library_symlink_alias(
    tmp_path: Path,
) -> None:
    bundle = write_foundation_fixture(tmp_path)
    shared = tmp_path / "projects" / "platform-governance" / "bundles" / "abac"
    shared.mkdir()
    alias = tmp_path / "abac"
    alias.symlink_to(shared.relative_to(tmp_path), target_is_directory=True)
    metadata = load_metadata(bundle / "bundle.yaml")
    metadata["depends_on"]["libs"] = ["abac"]
    write_json_yaml(bundle / "bundle.yaml", metadata)

    validation = validate_repo(tmp_path)

    assert validation.ok is False
    assert "must reference a canonical repository subdirectory" in "\n".join(
        validation.errors
    )


@pytest.mark.parametrize(
    ("library", "message"),
    (
        ("", "must be non-empty"),
        ("   ", "must be non-empty"),
        ("/absolute/abac", "must be repository-relative without parent traversal"),
        (
            "projects/platform-governance/bundles/../abac",
            "must be repository-relative without parent traversal",
        ),
        (
            "projects/platform-governance/bundles/missing",
            "must reference an existing directory",
        ),
    ),
)
def test_validate_rejects_an_invalid_shared_library(
    tmp_path: Path,
    library: str,
    message: str,
) -> None:
    bundle = write_foundation_fixture(tmp_path)
    metadata = load_metadata(bundle / "bundle.yaml")
    metadata["depends_on"]["libs"] = [library]
    write_json_yaml(bundle / "bundle.yaml", metadata)

    result = validate_repo(tmp_path)

    assert result.ok is False
    errors = "\n".join(result.errors)
    assert "depends_on.libs" in errors
    assert message in errors


def test_active_bundle_schema_declares_dev_uat_prod_lifecycle() -> None:
    schema = json.loads((ROOT / "schemas" / "bundle.schema.json").read_text(encoding="utf-8"))
    targets = schema["properties"]["targets"]

    assert targets["required"] == ["dev", "uat", "prod"]
    assert set(targets["properties"]) == {"dev", "uat", "prod"}
    assert targets["additionalProperties"] is False
    assert set(targets["properties"]["dev"]["required"]) == {"mode", "default", "local"}
    assert targets["properties"]["dev"]["properties"] == {
        "mode": {"const": "development"},
        "default": {"const": True},
        "local": {"const": True},
    }
    for target in ("uat", "prod"):
        assert set(targets["properties"][target]["required"]) == {"mode", "ci_only"}
        assert targets["properties"][target]["properties"] == {
            "mode": {"const": "production"},
            "ci_only": {"const": True},
        }


def test_basic_bundle_template_declares_dev_uat_prod_lifecycle() -> None:
    metadata = load_metadata(ROOT / "templates" / "bundle-basic" / "bundle.yaml")

    assert metadata["targets"] == {
        "dev": {"mode": "development", "default": True, "local": True},
        "uat": {"mode": "production", "ci_only": True},
        "prod": {"mode": "production", "ci_only": True},
    }


def test_validate_rejects_bundle_without_required_targets(tmp_path: Path) -> None:
    bundle_root = write_foundation_fixture(tmp_path)
    write_json_yaml(
        bundle_root / "repoctl.bundle.yaml",
        {
            "version": 1,
            "name": "foundation-smoke",
            "type": "generic",
            "owner": {"team": "platform-governance"},
            "review": {"policy": "owner-approval"},
            "targets": {"dev": {"mode": "development", "default": True}},
            "depends_on": {"bundles": [], "libs": []},
        },
    )

    result = validate_repo(tmp_path)

    assert result.ok is False
    errors = "\n".join(result.errors)
    assert (
        "projects/platform-governance/bundles/foundation-smoke/repoctl.bundle.yaml "
        "must declare targets: dev, uat, prod"
    ) in errors


def test_validate_rejects_metadata_outside_schema_contract(tmp_path: Path) -> None:
    bundle_root = write_foundation_fixture(tmp_path)
    write_json_yaml(
        bundle_root / "bundle.yaml",
        {
            "version": 1,
            "name": "foundation-smoke",
            "type": "generic",
            "owner": {"team": "platform-governance"},
            "review": {"policy": "owner-approval"},
            "targets": {
                "dev": {"mode": "development", "default": True, "local": True},
                "qa": {"mode": "production", "ci_only": True},
                "uat": {"mode": "production", "ci_only": True},
                "prod": {"mode": "production", "ci_only": True},
            },
            "depends_on": {"bundles": [], "libs": [], "unknown": []},
            "unexpected": True,
        },
    )

    result = validate_repo(tmp_path)

    assert result.ok is False
    errors = "\n".join(result.errors)
    assert "unknown field unexpected" in errors
    assert "targets may only declare: dev, uat, prod" in errors
    assert "depends_on may only declare: bundles, libs" in errors


def test_validate_rejects_noncanonical_lifecycle_target_settings(tmp_path: Path) -> None:
    bundle_root = write_foundation_fixture(tmp_path)
    write_json_yaml(
        bundle_root / "bundle.yaml",
        {
            "version": 1,
            "name": "foundation-smoke",
            "type": "generic",
            "owner": {"team": "platform-governance"},
            "review": {"policy": "owner-approval"},
            "targets": {
                "dev": {"mode": "development", "default": True, "local": False},
                "uat": {"mode": "validation", "ci_only": True},
                "prod": {"mode": "production", "ci_only": False},
            },
            "depends_on": {"bundles": [], "libs": []},
        },
    )

    result = validate_repo(tmp_path)

    assert result.ok is False
    errors = "\n".join(result.errors)
    assert "dev target must be local default development mode" in errors
    assert "uat target must be CI-only production mode" in errors
    assert "prod target must be CI-only production mode" in errors


def test_validate_rejects_names_outside_schema_pattern(tmp_path: Path) -> None:
    project_root = tmp_path / "projects" / "bad_name"
    write_json_yaml(
        project_root / "project.yaml",
        {
            "version": 1,
            "name": "bad_name",
            "owner": {"team": "platform-governance"},
            "review": {"policy": "owner-approval"},
        },
    )

    result = validate_repo(tmp_path)

    assert result.ok is False
    assert "name must use lowercase letters, numbers, and hyphens" in "\n".join(result.errors)


def test_classify_changed_files_keeps_docs_only_changes_non_deploying(tmp_path: Path) -> None:
    write_foundation_fixture(tmp_path)

    result = classify_changed_files(tmp_path, ["docs/design-docs/foundation.md"])

    assert result.docs_only is True
    assert result.affects_all_bundles is False
    assert result.changed_bundles == []


@pytest.mark.parametrize("filename", ["README.md", "ARCHITECTURE.md"])
def test_classify_changed_files_treats_exact_root_documentation_files_as_docs_only(
    tmp_path: Path, filename: str
) -> None:
    write_foundation_fixture(tmp_path)

    result = classify_changed_files(tmp_path, [filename])

    assert result.docs_only is True
    assert result.affects_all_bundles is False
    assert result.changed_bundles == []


@pytest.mark.parametrize("filename", ["README.md.bak", "ARCHITECTURE.md.old"])
def test_classify_changed_files_does_not_treat_root_documentation_name_prefixes_as_docs_only(
    tmp_path: Path, filename: str
) -> None:
    write_foundation_fixture(tmp_path)

    result = classify_changed_files(tmp_path, [filename])

    assert result.docs_only is False
    assert result.affects_all_bundles is False
    assert result.changed_bundles == []


def test_classify_changed_files_maps_bundle_local_changes(tmp_path: Path) -> None:
    bundle_root = write_foundation_fixture(tmp_path)

    result = classify_changed_files(
        tmp_path,
        [
            "projects/platform-governance/bundles/foundation-smoke/resources/job.yml",
        ],
    )

    assert result.docs_only is False
    assert result.affects_all_bundles is False
    assert result.changed_bundles == [bundle_root]


def test_classify_changed_files_maps_shared_libraries_to_declared_consumers(
    tmp_path: Path,
) -> None:
    bundle_root = write_foundation_fixture(tmp_path)
    metadata = load_metadata(bundle_root / "bundle.yaml")
    metadata["depends_on"]["libs"] = [
        "projects/platform-governance/bundles/abac"
    ]
    write_json_yaml(bundle_root / "bundle.yaml", metadata)

    result = classify_changed_files(
        tmp_path,
        ["projects/platform-governance/bundles/abac/reconcile.py"],
    )

    assert result.docs_only is False
    assert result.affects_all_bundles is False
    assert result.changed_bundles == [bundle_root]


def test_classify_changed_files_maps_a_shared_library_to_every_declared_consumer(
    tmp_path: Path,
) -> None:
    first = write_foundation_fixture(tmp_path)
    shared = tmp_path / "projects" / "platform-governance" / "bundles" / "abac"
    shared.mkdir()
    metadata = load_metadata(first / "bundle.yaml")
    metadata["depends_on"]["libs"] = [
        "projects/platform-governance/bundles/abac"
    ]
    write_json_yaml(first / "bundle.yaml", metadata)
    second = first.parent / "second-smoke"
    metadata["name"] = "second-smoke"
    write_json_yaml(second / "bundle.yaml", metadata)

    result = classify_changed_files(
        tmp_path,
        ["projects/platform-governance/bundles/abac/reconcile.py"],
    )

    assert result.docs_only is False
    assert result.affects_all_bundles is False
    assert result.changed_bundles == [first, second]


def test_classify_changed_files_does_not_match_a_library_name_prefix(
    tmp_path: Path,
) -> None:
    bundle = write_foundation_fixture(tmp_path)
    metadata = load_metadata(bundle / "bundle.yaml")
    metadata["depends_on"]["libs"] = [
        "projects/platform-governance/bundles/abac"
    ]
    write_json_yaml(bundle / "bundle.yaml", metadata)

    result = classify_changed_files(
        tmp_path,
        ["projects/platform-governance/bundles/abacus/reconcile.py"],
    )

    assert result.docs_only is False
    assert result.affects_all_bundles is False
    assert result.changed_bundles == []


def test_classify_changed_files_ignores_undeclared_shared_libraries(
    tmp_path: Path,
) -> None:
    write_foundation_fixture(tmp_path)

    result = classify_changed_files(
        tmp_path,
        ["projects/platform-governance/bundles/abac/reconcile.py"],
    )

    assert result.docs_only is False
    assert result.affects_all_bundles is False
    assert result.changed_bundles == []


def test_classify_changed_files_keeps_root_app_changes_non_deploying(tmp_path: Path) -> None:
    write_foundation_fixture(tmp_path)

    result = classify_changed_files(tmp_path, ["apps/bundle-explorer/app.js"])

    assert result.docs_only is False
    assert result.affects_all_bundles is False
    assert result.changed_bundles == []


def test_classify_changed_files_marks_root_tooling_as_all_bundles(tmp_path: Path) -> None:
    bundle_root = write_foundation_fixture(tmp_path)

    result = classify_changed_files(tmp_path, ["tools/repoctl/src/repoctl/cli.py"])

    assert result.docs_only is False
    assert result.affects_all_bundles is True
    assert result.changed_bundles == [bundle_root]


def test_classify_changed_files_marks_justfile_as_all_bundles(tmp_path: Path) -> None:
    bundle_root = write_foundation_fixture(tmp_path)

    result = classify_changed_files(tmp_path, ["justfile"])

    assert result.docs_only is False
    assert result.affects_all_bundles is True
    assert result.changed_bundles == [bundle_root]


def test_repoctl_cli_discover_outputs_json(tmp_path: Path) -> None:
    write_foundation_fixture(tmp_path)

    completed = subprocess.run(
        [sys.executable, "-m", "repoctl.cli", "--root", str(tmp_path), "discover"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["projects"][0]["name"] == "platform-governance"
    assert payload["bundles"][0]["name"] == "foundation-smoke"


def test_repoctl_cli_changed_includes_uncommitted_and_untracked_files(tmp_path: Path) -> None:
    bundle_root = write_foundation_fixture(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "repoctl@example.local"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "repoctl"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "commit", "-m", "baseline"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    (bundle_root / "resources").mkdir()
    (bundle_root / "resources" / "job.yml").write_text("name: smoke\n", encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, "-m", "repoctl.cli", "--root", str(tmp_path), "changed", "--base", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["changed_files"] == [
        "projects/platform-governance/bundles/foundation-smoke/resources/job.yml"
    ]
    assert payload["changed_bundles"] == [
        "projects/platform-governance/bundles/foundation-smoke"
    ]


def test_repoctl_cli_validate_reports_errors(tmp_path: Path) -> None:
    project_root = tmp_path / "projects" / "platform-governance"
    write_json_yaml(
        project_root / "project.yaml",
        {
            "version": 1,
            "name": "platform-governance",
            "owner": {"team": "platform-governance"},
            "review": {"policy": "owner-approval"},
        },
    )
    bundle_root = project_root / "bundles" / "foundation-smoke"
    write_json_yaml(
        bundle_root / "bundle.yaml",
        {
            "version": 1,
            "name": "wrong-name",
            "type": "generic",
            "owner": {"team": "platform-governance"},
            "review": {"policy": "owner-approval"},
            "targets": {
                "dev": {"mode": "development", "default": True, "local": True},
                "uat": {"mode": "production", "ci_only": True},
                "prod": {"mode": "production", "ci_only": True},
            },
            "depends_on": {"bundles": [], "libs": []},
        },
    )

    completed = subprocess.run(
        [sys.executable, "-m", "repoctl.cli", "--root", str(tmp_path), "validate"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    expected_error = (
        "Validation failed:\n"
        "- projects/platform-governance/bundles/foundation-smoke/bundle.yaml "
        "name must match directory name foundation-smoke"
    )
    assert expected_error in completed.stderr
