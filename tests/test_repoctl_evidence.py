import sys
from pathlib import Path
from subprocess import CompletedProcess, run

import repoctl.cli as cli

REQUIRED_PROD_EVIDENCE = [
    "repo-validation.json",
    "changed-bundles.json",
    "bundle-validate-prod.json",
    "abac-contract-tests.json",
    "promotion-decision.json",
]


def run_evidence_check(
    bundle: Path, target: str, evidence_dir: Path
) -> CompletedProcess[str]:
    return run(
        [
            sys.executable,
            "-m",
            "repoctl.cli",
            "evidence",
            "check",
            "--bundle",
            str(bundle),
            "--target",
            target,
            "--evidence",
            str(evidence_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_repoctl_evidence_check_rejects_missing_evidence_directory(tmp_path: Path) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"

    completed = run_evidence_check(bundle, "prod", tmp_path / "missing-evidence")

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert "- evidence directory does not exist:" in completed.stderr


def test_repoctl_evidence_check_rejects_evidence_path_that_is_not_directory(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_path = tmp_path / "evidence-file"
    evidence_path.write_text("placeholder\n", encoding="utf-8")

    completed = run_evidence_check(bundle, "prod", evidence_path)

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert "- evidence path is not a directory:" in completed.stderr


def test_repoctl_evidence_check_rejects_missing_required_files(tmp_path: Path) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "repo-validation.json").write_text("placeholder\n", encoding="utf-8")

    completed = run_evidence_check(bundle, "prod", evidence_dir)

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert "- missing evidence file: changed-bundles.json" in completed.stderr
    assert "- missing evidence file: bundle-validate-prod.json" in completed.stderr
    assert "- missing evidence file: abac-contract-tests.json" in completed.stderr
    assert "- missing evidence file: promotion-decision.json" in completed.stderr


def test_repoctl_evidence_check_rejects_unsupported_target_before_file_checks(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()

    completed = run_evidence_check(bundle, "prod/../../x", evidence_dir)

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert "- unsupported evidence target: prod/../../x" in completed.stderr
    assert "bundle-validate-prod/../../x.json" not in completed.stderr
    assert "missing evidence file" not in completed.stderr


def test_repoctl_evidence_check_accepts_required_files_with_placeholder_content(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    for filename in REQUIRED_PROD_EVIDENCE:
        (evidence_dir / filename).write_text("placeholder\n", encoding="utf-8")

    completed = run_evidence_check(bundle, "prod", evidence_dir)

    assert completed.returncode == 0
    assert completed.stdout == "Evidence ok\n"
    assert completed.stderr == ""


def test_repoctl_evidence_check_resolves_relative_inputs_against_root(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    cwd = tmp_path / "caller"
    repo_root.mkdir()
    cwd.mkdir()

    assert cli._resolve_input_path(
        repo_root,
        Path("projects/platform-governance/bundles/foundation-smoke"),
    ) == repo_root / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    assert cli._resolve_input_path(cwd, repo_root / "evidence") == repo_root / "evidence"
