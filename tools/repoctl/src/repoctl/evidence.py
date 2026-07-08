from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_TARGETS = {"dev", "uat", "prod"}
MISSING = object()


@dataclass(frozen=True)
class EvidenceCheckResult:
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def check_evidence_files(
    bundle: Path, target: str, evidence_dir: Path, root: Path | None = None
) -> EvidenceCheckResult:
    if target not in ALLOWED_TARGETS:
        return EvidenceCheckResult(errors=[f"unsupported evidence target: {target}"])

    required_files = [
        "repo-validation.json",
        "changed-bundles.json",
        f"bundle-validate-{target}.json",
        "abac-contract-tests.json",
        "promotion-decision.json",
    ]

    errors: list[str] = []
    if not evidence_dir.exists():
        return EvidenceCheckResult(
            errors=[f"evidence directory does not exist: {evidence_dir}"]
        )
    if not evidence_dir.is_dir():
        return EvidenceCheckResult(
            errors=[f"evidence path is not a directory: {evidence_dir}"]
        )

    for filename in required_files:
        if not (evidence_dir / filename).is_file():
            errors.append(f"missing evidence file: {filename}")

    if errors:
        return EvidenceCheckResult(errors=errors)

    expected_bundle = _expected_bundle_path(bundle, root)
    evidence = {
        filename: _load_json_object(evidence_dir / filename, filename, errors)
        for filename in required_files
    }

    repo_validation = evidence["repo-validation.json"]
    if repo_validation is not None:
        _require_value(
            repo_validation,
            "repo-validation.json",
            "status",
            "passed",
            errors,
        )

    changed_bundles = evidence["changed-bundles.json"]
    if changed_bundles is not None:
        changed = changed_bundles.get("changed_bundles", MISSING)
        if not isinstance(changed, list) or not all(
            isinstance(item, str) for item in changed
        ):
            errors.append(
                "changed-bundles.json changed_bundles must be a list of strings"
            )
        elif expected_bundle not in changed:
            errors.append(
                "changed-bundles.json changed_bundles must include "
                f"{expected_bundle}"
            )

    bundle_validation_filename = f"bundle-validate-{target}.json"
    bundle_validation = evidence[bundle_validation_filename]
    if bundle_validation is not None:
        _require_value(
            bundle_validation,
            bundle_validation_filename,
            "bundle",
            expected_bundle,
            errors,
        )
        _require_value(
            bundle_validation,
            bundle_validation_filename,
            "target",
            target,
            errors,
        )
        _require_value(
            bundle_validation,
            bundle_validation_filename,
            "status",
            "passed",
            errors,
        )

    abac_contract_tests = evidence["abac-contract-tests.json"]
    if abac_contract_tests is not None:
        _require_value(
            abac_contract_tests,
            "abac-contract-tests.json",
            "bundle",
            expected_bundle,
            errors,
        )
        _require_value(
            abac_contract_tests,
            "abac-contract-tests.json",
            "target",
            target,
            errors,
        )
        _require_value(
            abac_contract_tests,
            "abac-contract-tests.json",
            "status",
            "passed",
            errors,
        )

    promotion_decision = evidence["promotion-decision.json"]
    if promotion_decision is not None:
        _require_value(
            promotion_decision,
            "promotion-decision.json",
            "bundle",
            expected_bundle,
            errors,
        )
        _require_value(
            promotion_decision,
            "promotion-decision.json",
            "target",
            target,
            errors,
        )
        _require_value(
            promotion_decision,
            "promotion-decision.json",
            "decision",
            "approved",
            errors,
        )

    return EvidenceCheckResult(errors=errors)


def _expected_bundle_path(bundle: Path, root: Path | None) -> str:
    if root is not None:
        try:
            return bundle.relative_to(root).as_posix()
        except ValueError:
            pass
    return str(bundle)


def _load_json_object(
    path: Path, filename: str, errors: list[str]
) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"invalid UTF-8 in {filename}: {exc.reason}")
        return None
    except OSError as exc:
        errors.append(f"{filename} could not be read: {exc}")
        return None

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(
            f"invalid JSON in {filename}: {exc.msg} "
            f"(line {exc.lineno}, column {exc.colno})"
        )
        return None

    if not isinstance(payload, dict):
        errors.append(f"{filename} must contain a JSON object")
        return None

    return payload


def _require_value(
    payload: dict[str, Any],
    filename: str,
    key: str,
    expected: str,
    errors: list[str],
) -> None:
    value = payload.get(key, MISSING)
    if value != expected:
        errors.append(
            f"{filename} {key} must be {expected}, got {_format_value(value)}"
        )


def _format_value(value: Any) -> str:
    if value is MISSING:
        return "<missing>"
    return repr(value)
