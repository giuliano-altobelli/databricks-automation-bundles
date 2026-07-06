from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repoctl.discovery import discover


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: list[str]


REQUIRED_TARGETS = {"dev", "prod", "uat"}
PROJECT_FIELDS = {"version", "name", "owner", "review"}
BUNDLE_FIELDS = {"version", "name", "type", "owner", "review", "targets", "depends_on"}
DEPENDENCY_FIELDS = {"bundles", "libs"}
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


def validate_repo(root: Path) -> ValidationResult:
    result = discover(root)
    errors: list[str] = []

    for project in result.projects:
        errors.extend(_validate_project(root, project.path, project.metadata))

    for bundle in result.bundles:
        errors.extend(_validate_bundle(root, bundle.path, bundle.metadata))

    return ValidationResult(ok=not errors, errors=errors)


def _validate_project(root: Path, path: Path, metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    display_path = _display_path(root, path / "project.yaml")

    errors.extend(_reject_unknown_fields(display_path, metadata, PROJECT_FIELDS))
    errors.extend(_require_fields(display_path, metadata, ["version", "name", "owner", "review"]))
    if metadata.get("version") != 1:
        errors.append(f"{display_path} version must be 1")
    errors.extend(_validate_name(display_path, metadata.get("name")))
    if metadata.get("name") != path.name:
        errors.append(f"{display_path} name must match directory name {path.name}")
    errors.extend(_validate_owner(display_path, metadata.get("owner")))
    errors.extend(_validate_review(display_path, metadata.get("review")))
    return errors


def _validate_bundle(root: Path, path: Path, metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    display_path = _display_path(root, path / "bundle.yaml")

    errors.extend(_reject_unknown_fields(display_path, metadata, BUNDLE_FIELDS))
    errors.extend(
        _require_fields(
            display_path,
            metadata,
            ["version", "name", "type", "owner", "review", "targets", "depends_on"],
        )
    )
    if metadata.get("version") != 1:
        errors.append(f"{display_path} version must be 1")
    errors.extend(_validate_name(display_path, metadata.get("name")))
    if metadata.get("name") != path.name:
        errors.append(f"{display_path} name must match directory name {path.name}")
    if not _is_non_empty_string(metadata.get("type")):
        errors.append(f"{display_path} type must be a non-empty string")
    errors.extend(_validate_owner(display_path, metadata.get("owner")))
    errors.extend(_validate_review(display_path, metadata.get("review")))
    errors.extend(_validate_targets(display_path, metadata.get("targets")))
    errors.extend(_validate_depends_on(display_path, metadata.get("depends_on")))
    return errors


def _reject_unknown_fields(
    display_path: str,
    metadata: dict[str, Any],
    allowed_fields: set[str],
) -> list[str]:
    return [
        f"{display_path} unknown field {field}"
        for field in sorted(set(metadata) - allowed_fields)
    ]


def _require_fields(display_path: str, metadata: dict[str, Any], fields: list[str]) -> list[str]:
    return [
        f"{display_path} missing required field {field}"
        for field in fields
        if field not in metadata
    ]


def _validate_name(display_path: str, name: Any) -> list[str]:
    if not isinstance(name, str) or NAME_PATTERN.fullmatch(name) is None:
        return [f"{display_path} name must use lowercase letters, numbers, and hyphens"]
    return []


def _validate_owner(display_path: str, owner: Any) -> list[str]:
    if not isinstance(owner, dict) or not _is_non_empty_string(owner.get("team")):
        return [f"{display_path} owner.team must be a non-empty string"]
    return []


def _validate_review(display_path: str, review: Any) -> list[str]:
    if not isinstance(review, dict) or not _is_non_empty_string(review.get("policy")):
        return [f"{display_path} review.policy must be a non-empty string"]
    return []


def _validate_targets(display_path: str, targets: Any) -> list[str]:
    if not isinstance(targets, dict):
        return [f"{display_path} targets must be a mapping"]

    errors: list[str] = []
    declared_targets = set(targets)
    if declared_targets - REQUIRED_TARGETS:
        errors.append(f"{display_path} targets may only declare: dev, prod, uat")
    if not REQUIRED_TARGETS.issubset(declared_targets):
        errors.append(f"{display_path} must declare targets: dev, prod, uat")

    dev = targets.get("dev")
    if (
        not isinstance(dev, dict)
        or dev.get("mode") != "development"
        or dev.get("default") is not True
    ):
        errors.append(f"{display_path} dev target must be default development mode")

    for target, mode in {"uat": "validation", "prod": "production"}.items():
        settings = targets.get(target)
        if (
            not isinstance(settings, dict)
            or settings.get("mode") != mode
            or settings.get("ci_only") is not True
        ):
            errors.append(f"{display_path} {target} target must be CI-only {mode} mode")

    return errors


def _validate_depends_on(display_path: str, depends_on: Any) -> list[str]:
    if not isinstance(depends_on, dict):
        return [f"{display_path} depends_on must be a mapping"]

    errors: list[str] = []
    if set(depends_on) - DEPENDENCY_FIELDS:
        errors.append(f"{display_path} depends_on may only declare: bundles, libs")
    for key in ("bundles", "libs"):
        value = depends_on.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"{display_path} depends_on.{key} must be a list of strings")
    return errors


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _display_path(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()
