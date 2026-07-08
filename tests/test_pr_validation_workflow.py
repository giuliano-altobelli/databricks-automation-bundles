import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "pr-validation.yml"


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


def test_executable_command_parser_ignores_summary_formatting() -> None:
    shell = """
      set -euo pipefail
      echo "uv run pytest -q"
      uv run pytest -q
      uv run repoctl changed --base "$CHANGED_BASE" > changed-bundles.json
      {
        echo "## Changed bundles"
        cat changed-bundles.json
      } >> "$GITHUB_STEP_SUMMARY"
    """

    assert executable_commands(shell) == [
        "uv run pytest -q",
        'uv run repoctl changed --base "$CHANGED_BASE"',
    ]


def test_pr_validation_workflow_exists_and_has_pr_trigger() -> None:
    parsed = workflow()

    triggers = parsed.get("on") or parsed.get(True)
    assert "pull_request" in triggers
    assert "workflow_dispatch" in triggers


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
    shell = workflow_run_text()

    assert "uv run repoctl changed --base \"$CHANGED_BASE\"" in shell
    assert "$GITHUB_STEP_SUMMARY" in shell
    assert "Changed bundles" in shell
    assert "changed-bundles.json" in shell


def test_pr_validation_workflow_does_not_deploy_or_promote() -> None:
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8") if WORKFLOW_PATH.exists() else ""
    forbidden_fragments = [
        "databricks bundle deploy",
        "repoctl evidence check",
        "repoctl evidence upload",
        "promotion",
        "promote",
    ]

    for fragment in forbidden_fragments:
        assert fragment not in workflow_text
