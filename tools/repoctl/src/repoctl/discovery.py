from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repoctl.metadata import load_metadata


@dataclass(frozen=True)
class Project:
    name: str
    path: Path
    metadata: dict[str, Any]


@dataclass(frozen=True)
class Bundle:
    name: str
    project: str
    path: Path
    metadata: dict[str, Any]


@dataclass(frozen=True)
class DiscoveryResult:
    projects: list[Project]
    bundles: list[Bundle]

    def to_json(self, root: Path) -> dict[str, Any]:
        return {
            "projects": [
                {
                    "name": project.name,
                    "path": project.path.relative_to(root).as_posix(),
                }
                for project in self.projects
            ],
            "bundles": [
                {
                    "name": bundle.name,
                    "project": bundle.project,
                    "path": bundle.path.relative_to(root).as_posix(),
                }
                for bundle in self.bundles
            ],
        }


def discover(root: Path) -> DiscoveryResult:
    projects_root = root / "projects"
    if not projects_root.exists():
        return DiscoveryResult(projects=[], bundles=[])

    projects: list[Project] = []
    bundles: list[Bundle] = []

    for project_dir in sorted(path for path in projects_root.iterdir() if path.is_dir()):
        project_file = project_dir / "project.yaml"
        if not project_file.exists():
            continue
        project_metadata = load_metadata(project_file)
        project_name = str(project_metadata.get("name") or project_dir.name)
        projects.append(Project(name=project_name, path=project_dir, metadata=project_metadata))

        bundles_root = project_dir / "bundles"
        if not bundles_root.exists():
            continue

        for bundle_dir in sorted(path for path in bundles_root.iterdir() if path.is_dir()):
            bundle_file = bundle_dir / "bundle.yaml"
            if not bundle_file.exists():
                continue
            bundle_metadata = load_metadata(bundle_file)
            bundle_name = str(bundle_metadata.get("name") or bundle_dir.name)
            bundles.append(
                Bundle(
                    name=bundle_name,
                    project=project_name,
                    path=bundle_dir,
                    metadata=bundle_metadata,
                )
            )

    return DiscoveryResult(projects=projects, bundles=bundles)
