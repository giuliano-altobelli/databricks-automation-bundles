from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from repoctl.discovery import discover


@dataclass(frozen=True)
class ChangedResult:
    changed_files: list[str]
    changed_bundles: list[Path]
    docs_only: bool
    affects_all_bundles: bool


DOC_PATHS = ("docs/", "README.md", "ARCHITECTURE.md")
ALL_BUNDLE_PREFIXES = ("libs/", "schemas/", "templates/", "tools/", ".github/")
ALL_BUNDLE_FILES = {"pyproject.toml", "uv.lock", "prek.toml"}


def classify_changed_files(root: Path, changed_files: list[str]) -> ChangedResult:
    normalized = [file.strip() for file in changed_files if file.strip()]
    discovered = discover(root)
    all_bundles = sorted({bundle.path for bundle in discovered.bundles})

    if not normalized:
        return ChangedResult(
            changed_files=[],
            changed_bundles=[],
            docs_only=False,
            affects_all_bundles=False,
        )

    if all(_is_docs_only(path) for path in normalized):
        return ChangedResult(
            changed_files=normalized,
            changed_bundles=[],
            docs_only=True,
            affects_all_bundles=False,
        )

    if any(_affects_all_bundles(path) for path in normalized):
        return ChangedResult(
            changed_files=normalized,
            changed_bundles=all_bundles,
            docs_only=False,
            affects_all_bundles=True,
        )

    changed_bundles = {
        bundle.path
        for bundle in discovered.bundles
        for changed_file in normalized
        if _is_inside_bundle(changed_file, bundle.path.relative_to(root))
    }

    changed_bundles.update(
        bundle.path
        for bundle in discovered.bundles
        for changed_file in normalized
        if _is_project_metadata_change(changed_file, bundle.path.relative_to(root).parents[1])
    )

    return ChangedResult(
        changed_files=normalized,
        changed_bundles=sorted(changed_bundles),
        docs_only=False,
        affects_all_bundles=False,
    )


def _is_docs_only(path: str) -> bool:
    return path.startswith(DOC_PATHS) or path in DOC_PATHS


def _affects_all_bundles(path: str) -> bool:
    return path.startswith(ALL_BUNDLE_PREFIXES) or path in ALL_BUNDLE_FILES


def _is_inside_bundle(changed_file: str, bundle_path: Path) -> bool:
    bundle_prefix = bundle_path.as_posix().rstrip("/") + "/"
    return changed_file.startswith(bundle_prefix)


def _is_project_metadata_change(changed_file: str, project_path: Path) -> bool:
    return changed_file == (project_path / "project.yaml").as_posix()
