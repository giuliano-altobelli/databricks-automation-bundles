from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "deploy.yml"
CHECKOUT_ACTION = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"


def workflow() -> dict:
    assert WORKFLOW_PATH.exists(), "Reusable deployment workflow must exist"
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def executable_commands(shell: str) -> list[str]:
    return [
        " ".join(line.split())
        for line in shell.splitlines()
        if line.strip() and line.strip() != "set -euo pipefail"
    ]


def test_deploy_workflow_is_reusable_with_explicit_contract() -> None:
    parsed = workflow()
    triggers = parsed.get("on") or parsed.get(True)

    assert set(triggers) == {"workflow_call"}
    assert triggers["workflow_call"] == {
        "inputs": {
            name: {"required": True, "type": "string"}
            for name in ("path", "resource", "target", "group")
        },
        "secrets": {
            "credential": {"required": True},
        },
    }
    assert parsed["permissions"] == {"contents": "read"}
    assert set(parsed["jobs"]) == {"deploy"}


def test_deploy_workflow_isolates_environment_and_concurrency_by_input() -> None:
    deploy = workflow()["jobs"]["deploy"]

    assert deploy["runs-on"] == "ubuntu-22.04"
    assert deploy["environment"] == "${{ inputs.target }}"
    assert deploy["concurrency"] == {
        "group": "${{ inputs.group }}",
        "cancel-in-progress": False,
    }


def test_deploy_workflow_owns_m2m_and_bundle_commands() -> None:
    deploy = workflow()["jobs"]["deploy"]
    checkout = next(
        step for step in deploy["steps"] if step.get("uses", "").startswith("actions/checkout@")
    )
    setup = next(
        step
        for step in deploy["steps"]
        if step.get("uses", "").startswith("databricks/setup-cli@")
    )
    command = next(
        step for step in deploy["steps"] if "databricks bundle" in step.get("run", "")
    )

    assert checkout["uses"] == CHECKOUT_ACTION
    assert setup["uses"] == "databricks/setup-cli@v1.7.0"
    assert command["working-directory"] == "${{ inputs.path }}"
    assert executable_commands(command["run"]) == [
        ': "${DATABRICKS_HOST:?GitHub environment variable DATABRICKS_HOST is required}"',
        ': "${DATABRICKS_CLIENT_ID:?GitHub environment variable DATABRICKS_CLIENT_ID is required}"',
        (
            ': "${DATABRICKS_CLIENT_SECRET:?Databricks client secret is required}"'
        ),
        (
            ': "${BUNDLE_VAR_sql_warehouse_id:?GitHub environment variable '
            'DATABRICKS_SQL_WAREHOUSE_ID is required}"'
        ),
        'databricks bundle validate -t "$BUNDLE_TARGET"',
        'databricks bundle deploy -t "$BUNDLE_TARGET"',
        'databricks bundle run -t "$BUNDLE_TARGET" "$BUNDLE_RESOURCE"',
    ]
    assert command["env"] == {
        "DATABRICKS_AUTH_TYPE": "oauth-m2m",
        "DATABRICKS_HOST": "${{ vars.DATABRICKS_HOST }}",
        "DATABRICKS_CLIENT_ID": "${{ vars.DATABRICKS_CLIENT_ID }}",
        "DATABRICKS_CLIENT_SECRET": "${{ secrets.credential }}",
        "BUNDLE_VAR_sql_warehouse_id": "${{ vars.DATABRICKS_SQL_WAREHOUSE_ID }}",
        "BUNDLE_VAR_run_as_service_principal_name": (
            "${{ vars.DATABRICKS_CLIENT_ID }}"
        ),
        "BUNDLE_TARGET": "${{ inputs.target }}",
        "BUNDLE_RESOURCE": "${{ inputs.resource }}",
    }
    assert "env" not in deploy

    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "github-oidc" not in workflow_text
    assert "id-token" not in workflow_text
