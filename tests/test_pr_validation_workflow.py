import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "pr-validation.yml"
BUNDLE_ROOT = "projects/platform-governance/bundles/abac-jira-project-access"


def recipe_commands(justfile_text: str, recipe_name: str) -> list[str]:
    lines = justfile_text.splitlines()
    start = lines.index(f"{recipe_name}:") + 1
    commands: list[str] = []

    for line in lines[start:]:
        if line and not line.startswith((" ", "\t")):
            break
        if line.strip():
            commands.append(line.strip())

    return commands


def workflow() -> dict:
    assert WORKFLOW_PATH.exists(), "PR validation workflow must exist"
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def workflow_run_text() -> str:
    parsed = workflow()
    steps = parsed["jobs"]["validate"]["steps"]
    return "\n".join(str(step.get("run", "")) for step in steps)


def executable_commands(shell_text: str) -> list[str]:
    commands: list[str] = []
    for line in shell_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped in {"{", "}", "echo"} or stripped.startswith(("}", "echo ", "cat ")):
            continue
        if stripped == "set -euo pipefail":
            continue

        command = re.split(r"\s+>{1,2}\s+", stripped, maxsplit=1)[0]
        commands.append(" ".join(command.split()))

    return commands


def workflow_executable_commands() -> list[str]:
    return executable_commands(workflow_run_text())


def test_pr_validation_workflow_exists_and_has_pr_trigger() -> None:
    parsed = workflow()

    triggers = parsed.get("on") or parsed.get(True)
    assert set(triggers) == {"pull_request", "workflow_dispatch"}
    assert "pull_request_target" not in triggers


def test_pr_workflow_permissions_are_read_only() -> None:
    assert workflow()["permissions"] == {"contents": "read"}


def test_pr_validation_checkout_fetches_full_history() -> None:
    validate = workflow()["jobs"]["validate"]
    checkout_step = next(
        step for step in validate["steps"] if step.get("uses") == "actions/checkout@v4"
    )

    assert checkout_step["with"]["fetch-depth"] == 0


def test_pr_validation_changed_base_uses_pull_request_base_with_dispatch_fallback() -> None:
    validate = workflow()["jobs"]["validate"]
    changed_step = next(
        step for step in validate["steps"] if step.get("id") == "changed_bundles"
    )

    assert changed_step["env"]["CHANGED_BASE"] == (
        "${{ github.event.pull_request.base.sha || github.sha }}"
    )


def test_pr_validation_workflow_has_full_local_verify_parity() -> None:
    justfile_text = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
    verify_commands = recipe_commands(justfile_text, "verify")
    expected_commands = [
        "uv sync --locked --all-extras --dev",
    ]

    for command in verify_commands:
        if command == "uv run repoctl changed --base HEAD":
            expected_commands.append('uv run repoctl changed --base "$CHANGED_BASE"')
        else:
            expected_commands.append(command)

    assert workflow_executable_commands() == expected_commands


def test_pr_validation_workflow_writes_changed_bundle_summary() -> None:
    validate = workflow()["jobs"]["validate"]
    shell = workflow_run_text()
    changed_step = next(
        step for step in validate["steps"] if step.get("id") == "changed_bundles"
    )

    assert validate["outputs"] == {
        "changed_bundles": "${{ steps.changed_bundles.outputs.changed_bundles }}"
    }
    assert "uv run repoctl changed --base \"$CHANGED_BASE\"" in shell
    assert "jq -c '.changed_bundles' changed-bundles.json" in changed_step["run"]
    assert "$GITHUB_OUTPUT" in changed_step["run"]
    assert "$GITHUB_STEP_SUMMARY" in shell
    assert "Changed bundles" in shell
    assert "changed-bundles.json" in shell


def test_pr_validation_job_never_receives_databricks_credentials() -> None:
    validate = workflow()["jobs"]["validate"]
    validate_text = str(validate)

    assert "if" not in validate
    assert "environment" not in validate
    assert "env" not in validate
    assert "DATABRICKS_" not in validate_text
    assert "BUNDLE_VAR_" not in validate_text
    assert all(
        step.get("uses", "").split("@")[0] != "databricks/setup-cli"
        for step in validate["steps"]
    )
    assert "databricks bundle" not in workflow_run_text()


def test_pr_deploy_job_is_gated_to_trusted_same_repository_pull_requests() -> None:
    deploy = workflow()["jobs"]["deploy-uat"]
    condition = " ".join(deploy["if"].split())

    assert deploy["needs"] == "validate"
    assert deploy["environment"] == "uat"
    assert condition == (
        "github.event_name == 'pull_request' && "
        "github.event.pull_request.head.repo.full_name == github.repository && "
        "github.event.pull_request.user.login != 'dependabot[bot]' && "
        "contains( fromJSON(needs.validate.outputs.changed_bundles), "
        f"'{BUNDLE_ROOT}' )"
    )
    assert deploy["concurrency"] == {
        "group": "abac-jira-project-access-uat",
        "cancel-in-progress": False,
    }


def test_pr_deploy_job_uses_oauth_m2m_and_expected_uat_commands() -> None:
    deploy = workflow()["jobs"]["deploy-uat"]
    setup_step = next(
        step for step in deploy["steps"] if step.get("uses", "").startswith("databricks/setup-cli@")
    )
    command_step = next(
        step for step in deploy["steps"] if "databricks bundle" in step.get("run", "")
    )

    assert setup_step["uses"] == "databricks/setup-cli@v1.7.0"
    assert command_step["working-directory"] == BUNDLE_ROOT
    assert executable_commands(command_step["run"]) == [
        "databricks bundle validate -t uat",
        "databricks bundle deploy -t uat",
        "databricks bundle run -t uat apply_abac_jira_project_access",
    ]
    assert command_step["env"] == {
        "DATABRICKS_AUTH_TYPE": "oauth-m2m",
        "DATABRICKS_HOST": "${{ vars.DATABRICKS_HOST }}",
        "DATABRICKS_CLIENT_ID": "${{ vars.DATABRICKS_CLIENT_ID }}",
        "DATABRICKS_CLIENT_SECRET": "${{ secrets.DATABRICKS_CLIENT_SECRET }}",
        "BUNDLE_VAR_sql_warehouse_id": "${{ vars.DATABRICKS_SQL_WAREHOUSE_ID }}",
        "BUNDLE_VAR_run_as_service_principal_name": (
            "${{ vars.DATABRICKS_CLIENT_ID }}"
        ),
    }
    assert "env" not in deploy
    assert "id-token" not in str(deploy)


def test_pr_workflow_does_not_target_dev_prod_or_upload_evidence() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    forbidden_fragments = [
        "-t dev",
        "-t prod",
        "DATABRICKS_DEV_",
        "DATABRICKS_PROD_",
        "repoctl evidence check",
        "repoctl evidence upload",
        "actions/upload-artifact",
        "pull_request_target",
        "promotion",
        "promote",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in workflow_text
