from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "prod-deployment.yml"
BUNDLE_ROOT = "projects/platform-governance/bundles/abac-jira-project-access"
CHECKOUT_ACTION = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"
SETUP_UV_ACTION = "astral-sh/setup-uv@d0cc045d04ccac9d8b7881df0226f9e82c39688e"


def workflow() -> dict:
    assert WORKFLOW_PATH.exists(), "Production deployment workflow must exist"
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def executable_commands(shell_text: str) -> list[str]:
    return [
        " ".join(line.split())
        for line in shell_text.splitlines()
        if line.strip() and line.strip() != "set -euo pipefail"
    ]


def test_prod_workflow_triggers_only_on_push_to_main() -> None:
    parsed = workflow()
    triggers = parsed.get("on") or parsed.get(True)

    assert set(triggers) == {"push"}
    assert triggers["push"] == {"branches": ["main"]}


def test_prod_workflow_verifies_before_entering_prod_environment() -> None:
    parsed = workflow()
    verify = parsed["jobs"]["verify"]
    deploy = parsed["jobs"]["deploy-prod"]

    assert "environment" not in verify
    assert "env" not in verify
    assert deploy["needs"] == "verify"
    assert deploy["environment"] == "prod"
    assert deploy["concurrency"] == {
        "group": "abac-jira-project-access-prod",
        "cancel-in-progress": False,
    }
    assert {
        job["runs-on"] for job in parsed["jobs"].values()
    } == {"ubuntu-22.04"}

    assert [step.get("uses") for step in verify["steps"] if "uses" in step] == [
        CHECKOUT_ACTION,
        SETUP_UV_ACTION,
    ]
    checkout_step = next(
        step for step in verify["steps"] if step.get("uses") == CHECKOUT_ACTION
    )
    assert checkout_step["with"]["fetch-depth"] == 0

    run_steps = [step for step in verify["steps"] if "run" in step]
    assert [step["run"] for step in run_steps[:-1]] == [
        "uv sync --locked --all-extras --dev",
        "uv run pytest -q",
        "uv run ruff check tools tests",
        "uv run prek -c prek.toml run --all-files",
        "uv run repoctl discover",
        "uv run repoctl validate",
    ]

    changed_step = run_steps[-1]
    assert changed_step["env"] == {
        "CHANGED_BASE": "${{ github.event.before }}",
        "CHANGED_FALLBACK": "${{ github.sha }}",
    }
    assert '[[ -z "$CHANGED_BASE" || "$CHANGED_BASE" =~ ^0+$ ]]' in changed_step["run"]
    assert 'CHANGED_BASE="$CHANGED_FALLBACK"' in changed_step["run"]
    assert 'uv run repoctl changed --base "$CHANGED_BASE"' in changed_step["run"]


def test_prod_deploy_job_uses_oauth_m2m_and_expected_commands() -> None:
    deploy = workflow()["jobs"]["deploy-prod"]
    checkout_step = next(
        step for step in deploy["steps"] if step.get("uses", "").startswith("actions/checkout@")
    )
    setup_step = next(
        step for step in deploy["steps"] if step.get("uses", "").startswith("databricks/setup-cli@")
    )
    command_step = next(
        step for step in deploy["steps"] if "databricks bundle" in step.get("run", "")
    )

    assert checkout_step["uses"] == CHECKOUT_ACTION
    assert setup_step["uses"] == "databricks/setup-cli@v1.7.0"
    assert command_step["working-directory"] == BUNDLE_ROOT
    assert executable_commands(command_step["run"]) == [
        "databricks bundle validate -t prod",
        "databricks bundle deploy -t prod",
        "databricks bundle run -t prod apply_abac_jira_project_access",
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


def test_prod_workflow_has_no_dev_uat_pat_or_evidence_uploads() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "-t dev",
        "-t uat",
        "DATABRICKS_TOKEN",
        "repoctl evidence",
        "actions/upload-artifact",
        "setup-just",
        "just verify",
    ):
        assert forbidden not in text
