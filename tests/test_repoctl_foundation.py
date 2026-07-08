import json
import subprocess
import sys
from pathlib import Path

from repoctl.changes import classify_changed_files
from repoctl.discovery import discover
from repoctl.validation import validate_repo


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
                "dev": {"mode": "development", "default": True},
                "uat": {"mode": "validation", "ci_only": True},
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


def test_validate_accepts_minimal_foundation_metadata(tmp_path: Path) -> None:
    write_foundation_fixture(tmp_path)

    result = validate_repo(tmp_path)

    assert result.ok is True
    assert result.errors == []


def test_validate_rejects_bundle_without_required_targets(tmp_path: Path) -> None:
    bundle_root = write_foundation_fixture(tmp_path)
    write_json_yaml(
        bundle_root / "bundle.yaml",
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
    assert "must declare targets: dev, prod, uat" in "\n".join(result.errors)


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
                "dev": {"mode": "development", "default": True},
                "qa": {"mode": "validation", "ci_only": True},
                "uat": {"mode": "validation", "ci_only": True},
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
    assert "targets may only declare: dev, prod, uat" in errors
    assert "depends_on may only declare: bundles, libs" in errors


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
                "dev": {"mode": "development", "default": True},
                "uat": {"mode": "validation", "ci_only": True},
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
