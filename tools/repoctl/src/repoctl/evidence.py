from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ALLOWED_TARGETS = {"dev", "uat", "prod"}


@dataclass(frozen=True)
class EvidenceCheckResult:
    errors: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def check_evidence_files(bundle: Path, target: str, evidence_dir: Path) -> EvidenceCheckResult:
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

    return EvidenceCheckResult(errors=errors)
