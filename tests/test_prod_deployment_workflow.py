from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "prod-deployment.yml"
DEPLOY_WORKFLOW = "./.github/workflows/deploy.yml"
COLLECTIONS = {
    "deploy-jira-prod": {
        "path": "projects/platform-governance/bundles/abac-jira-access",
        "resource": "project",
        "target": "prod",
        "group": "abac-jira-access-prod",
    },
    "deploy-general-prod": {
        "path": "projects/platform-governance/bundles/abac-general-access",
        "resource": "okta_group",
        "target": "prod",
        "group": "abac-general-access-prod",
    },
}
CHECKOUT_ACTION = "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd"
SETUP_UV_ACTION = "astral-sh/setup-uv@37802adc94f370d6bfd71619e3f0bf239e1f3b78"


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


def test_prod_workflow_permissions_are_read_only() -> None:
    assert workflow()["permissions"] == {"contents": "read"}


def test_prod_deploy_jobs_cannot_bypass_verification_failure() -> None:
    jobs = workflow()["jobs"]

    assert set(jobs) == {"verify", *COLLECTIONS}
    for identifier in COLLECTIONS:
        deploy = jobs[identifier]
        assert deploy["needs"] == "verify"
        assert "if" not in deploy


def test_prod_workflow_verifies_before_entering_prod_environment() -> None:
    parsed = workflow()
    verify = parsed["jobs"]["verify"]

    assert "environment" not in verify
    assert "env" not in verify
    assert "id-token" not in str(verify)
    assert verify["runs-on"] == "ubuntu-22.04"
    for identifier in COLLECTIONS:
        deploy = parsed["jobs"][identifier]
        assert deploy["needs"] == "verify"
        assert deploy["uses"] == DEPLOY_WORKFLOW

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


def test_prod_deploy_jobs_parameterize_both_collections() -> None:
    jobs = workflow()["jobs"]

    for identifier, collection in COLLECTIONS.items():
        deploy = jobs[identifier]
        assert deploy["uses"] == DEPLOY_WORKFLOW
        assert deploy["with"] == collection
        assert deploy["permissions"] == {"contents": "read"}
        assert deploy["secrets"] == {
            "credential": "${{ secrets.DATABRICKS_PROD_CLIENT_SECRET }}",
        }

    groups = {collection["group"] for collection in COLLECTIONS.values()}
    assert len(groups) == len(COLLECTIONS)
    assert "id-token" not in WORKFLOW_PATH.read_text(encoding="utf-8")


def test_prod_workflow_has_no_dev_uat_pat_or_evidence_uploads() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    for forbidden in (
        "-t dev",
        "-t uat",
        "DATABRICKS_TOKEN",
        "DATABRICKS_UAT_CLIENT_SECRET",
        "repoctl evidence",
        "actions/upload-artifact",
        "setup-just",
        "just verify",
    ):
        assert forbidden not in text
