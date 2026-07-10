import json
import sys
from pathlib import Path
from subprocess import CompletedProcess, run

import pytest
import repoctl.cli as cli

BUNDLE_PATH = "projects/platform-governance/bundles/foundation-smoke"


def run_evidence_check(
    bundle: Path,
    target: str,
    evidence_dir: Path,
    root: Path | None = None,
    cwd: Path | None = None,
) -> CompletedProcess[str]:
    command = [sys.executable, "-m", "repoctl.cli"]
    if root is not None:
        command.extend(["--root", str(root)])
    command.extend(
        [
            "evidence",
            "check",
            "--bundle",
            str(bundle),
            "--target",
            target,
            "--evidence",
            str(evidence_dir),
        ]
    )
    return run(
        command,
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def write_valid_evidence(
    evidence_dir: Path,
    bundle: str = BUNDLE_PATH,
    target: str = "prod",
    decision: str = "approved",
    changed_bundles: list[str] | None = None,
) -> None:
    evidence_dir.mkdir()
    changed = changed_bundles if changed_bundles is not None else [bundle]
    payloads = {
        "repo-validation.json": {"status": "passed"},
        "changed-bundles.json": {"changed_bundles": changed},
        f"bundle-validate-{target}.json": {
            "bundle": bundle,
            "target": target,
            "status": "passed",
        },
        "abac-contract-tests.json": {
            "bundle": bundle,
            "target": target,
            "status": "passed",
        },
        "promotion-decision.json": {
            "bundle": bundle,
            "target": target,
            "decision": decision,
        },
    }
    for filename, payload in payloads.items():
        write_json(evidence_dir / filename, payload)


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

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

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


def test_repoctl_evidence_check_rejects_malformed_json(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    (evidence_dir / "repo-validation.json").write_text("placeholder\n", encoding="utf-8")

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert "- invalid JSON in repo-validation.json:" in completed.stderr
    assert "line 1, column 1" in completed.stderr


def test_repoctl_evidence_check_rejects_invalid_utf8_json(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    (evidence_dir / "repo-validation.json").write_bytes(b"\xff\n")

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert "- invalid UTF-8 in repo-validation.json:" in completed.stderr


def test_repoctl_evidence_check_reports_read_error(tmp_path: Path, monkeypatch, capsys) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    original_read_text = Path.read_text

    def read_text(path: Path, *args, **kwargs) -> str:
        if path.name == "repo-validation.json":
            raise OSError("permission denied")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)

    returncode = cli.main(
        [
            "--root",
            str(tmp_path),
            "evidence",
            "check",
            "--bundle",
            str(bundle),
            "--target",
            "prod",
            "--evidence",
            str(evidence_dir),
        ]
    )
    captured = capsys.readouterr()

    assert returncode == 1
    assert "Evidence check failed:" in captured.err
    assert "- repo-validation.json could not be read: permission denied" in captured.err


def test_repoctl_evidence_check_rejects_failed_repo_validation_status(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    (evidence_dir / "repo-validation.json").write_text(
        json.dumps({"status": "failed"}) + "\n", encoding="utf-8"
    )

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert "- repo-validation.json status must be passed, got 'failed'" in completed.stderr


def test_repoctl_evidence_check_rejects_empty_bundle_validation_status(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    (evidence_dir / "bundle-validate-prod.json").write_text(
        json.dumps(
            {
                "bundle": "projects/platform-governance/bundles/foundation-smoke",
                "target": "prod",
                "status": "",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert "- bundle-validate-prod.json status must be passed, got ''" in completed.stderr


def test_repoctl_evidence_check_rejects_missing_bundle_validation_status(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    (evidence_dir / "bundle-validate-prod.json").write_text(
        json.dumps(
            {
                "bundle": "projects/platform-governance/bundles/foundation-smoke",
                "target": "prod",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert (
        "- bundle-validate-prod.json status must be passed, got <missing>"
        in completed.stderr
    )


def test_repoctl_evidence_check_rejects_unapproved_promotion_decision(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir, decision="rejected")

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert (
        "- promotion-decision.json decision must be approved, got 'rejected'"
        in completed.stderr
    )


def test_repoctl_evidence_check_rejects_bundle_mismatch(tmp_path: Path) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    write_json(
        evidence_dir / "bundle-validate-prod.json",
        {"bundle": "projects/other/bundle", "target": "prod", "status": "passed"},
    )

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert completed.stderr.splitlines() == [
        "Evidence check failed:",
        "- bundle-validate-prod.json bundle must be "
        f"{BUNDLE_PATH}, got 'projects/other/bundle'",
    ]


def test_repoctl_evidence_check_rejects_target_mismatch(tmp_path: Path) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    write_json(
        evidence_dir / "bundle-validate-prod.json",
        {"bundle": BUNDLE_PATH, "target": "uat", "status": "passed"},
    )

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert completed.stderr.splitlines() == [
        "Evidence check failed:",
        "- bundle-validate-prod.json target must be prod, got 'uat'",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"changed_bundles": BUNDLE_PATH},
        {"changed_bundles": [BUNDLE_PATH, 1]},
    ],
    ids=["missing", "not-a-list", "non-string-item"],
)
def test_repoctl_evidence_check_rejects_invalid_changed_bundles_shapes(
    tmp_path: Path, payload: dict[str, object]
) -> None:
    bundle = tmp_path / BUNDLE_PATH
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    write_json(evidence_dir / "changed-bundles.json", payload)

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert (
        "- changed-bundles.json changed_bundles must be a list of strings"
        in completed.stderr
    )


def test_repoctl_evidence_check_rejects_changed_bundles_missing_requested_bundle(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(
        evidence_dir, changed_bundles=["projects/platform-governance/bundles/other"]
    )

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert (
        "- changed-bundles.json changed_bundles must include "
        "projects/platform-governance/bundles/foundation-smoke"
    ) in completed.stderr


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        ("bundle", "projects/other/bundle"),
        ("target", "uat"),
        ("status", "failed"),
    ],
)
def test_repoctl_evidence_check_rejects_invalid_abac_contract_field(
    tmp_path: Path, field: str, invalid_value: str
) -> None:
    bundle = tmp_path / BUNDLE_PATH
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    payload = {"bundle": BUNDLE_PATH, "target": "prod", "status": "passed"}
    payload[field] = invalid_value
    write_json(evidence_dir / "abac-contract-tests.json", payload)

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    expected_value = {"bundle": BUNDLE_PATH, "target": "prod", "status": "passed"}[field]
    assert completed.returncode == 1
    assert (
        f"- abac-contract-tests.json {field} must be {expected_value}, "
        f"got {invalid_value!r}"
    ) in completed.stderr


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [("bundle", "projects/other/bundle"), ("target", "uat")],
)
def test_repoctl_evidence_check_rejects_invalid_promotion_scope(
    tmp_path: Path, field: str, invalid_value: str
) -> None:
    bundle = tmp_path / BUNDLE_PATH
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    payload = {"bundle": BUNDLE_PATH, "target": "prod", "decision": "approved"}
    payload[field] = invalid_value
    write_json(evidence_dir / "promotion-decision.json", payload)

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    expected_value = {"bundle": BUNDLE_PATH, "target": "prod"}[field]
    assert completed.returncode == 1
    assert (
        f"- promotion-decision.json {field} must be {expected_value}, "
        f"got {invalid_value!r}"
    ) in completed.stderr


def test_repoctl_evidence_check_aggregates_independent_errors(tmp_path: Path) -> None:
    bundle = tmp_path / BUNDLE_PATH
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    write_json(evidence_dir / "repo-validation.json", {"status": "failed"})
    write_json(evidence_dir / "changed-bundles.json", {"changed_bundles": BUNDLE_PATH})
    write_json(
        evidence_dir / "abac-contract-tests.json",
        {"bundle": BUNDLE_PATH, "target": "prod", "status": "failed"},
    )

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert set(completed.stderr.splitlines()) == {
        "Evidence check failed:",
        "- repo-validation.json status must be passed, got 'failed'",
        "- changed-bundles.json changed_bundles must be a list of strings",
        "- abac-contract-tests.json status must be passed, got 'failed'",
    }


def test_repoctl_evidence_check_rejects_json_payload_that_is_not_object(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    write_valid_evidence(evidence_dir)
    (evidence_dir / "promotion-decision.json").write_text(
        '["approved"]\n', encoding="utf-8"
    )

    completed = run_evidence_check(bundle, "prod", evidence_dir, root=tmp_path)

    assert completed.returncode == 1
    assert "Evidence check failed:" in completed.stderr
    assert "- promotion-decision.json must contain a JSON object" in completed.stderr


@pytest.mark.parametrize("target", ["dev", "uat", "prod"])
def test_repoctl_evidence_check_accepts_valid_evidence(
    tmp_path: Path, target: str
) -> None:
    repo_root = tmp_path / "repo"
    bundle = repo_root / "projects" / "platform-governance" / "bundles" / "foundation-smoke"
    evidence_dir = tmp_path / "evidence"
    repo_root.mkdir()
    write_valid_evidence(evidence_dir, target=target)

    completed = run_evidence_check(bundle, target, evidence_dir, root=repo_root)

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
    evidence_dir = repo_root / "evidence"
    write_valid_evidence(evidence_dir)

    completed = run_evidence_check(
        Path(BUNDLE_PATH),
        "prod",
        Path("evidence"),
        root=repo_root,
        cwd=cwd,
    )

    assert completed.returncode == 0
    assert completed.stdout == "Evidence ok\n"
    assert completed.stderr == ""
