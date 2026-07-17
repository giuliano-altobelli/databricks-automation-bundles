from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repoctl.discovery import Bundle
from repoctl.metadata import load_metadata

VARIABLE = re.compile(r"^\$\{var\.([a-z_][a-z0-9_]*)\}$")
TARGETS = ("dev", "uat", "prod")


@dataclass(frozen=True)
class Destination:
    target: str
    table: str


@dataclass(frozen=True)
class Binding:
    path: Path
    destinations: tuple[Destination, ...]


def check(root: Path, bundles: list[Bundle]) -> list[str]:
    errors: list[str] = []
    bindings: list[Binding] = []
    for bundle in bundles:
        if bundle.metadata.get("type") != "abac-access-collection":
            continue
        discovered, violations = _bundle(root, bundle)
        bindings.extend(discovered)
        errors.extend(violations)

    owners: dict[tuple[str, str], Binding] = {}
    for binding in bindings:
        for destination in binding.destinations:
            key = (destination.target, destination.table.casefold())
            owner = owners.get(key)
            if owner is None:
                owners[key] = binding
                continue
            if owner.path == binding.path:
                continue
            errors.append(
                f"{destination.target} table {destination.table} has multiple seeds: "
                f"{_display(root, owner.path)}, {_display(root, binding.path)}"
            )

    return errors


def _bundle(root: Path, bundle: Bundle) -> tuple[list[Binding], list[str]]:
    maps = bundle.path / "maps"
    if not maps.is_dir():
        return [], []

    directories = sorted(path for path in maps.iterdir() if path.is_dir())
    enabled = [path for path in directories if _enabled(path)]
    if not enabled:
        return [], []

    configuration = bundle.path / "databricks.yml"
    if not configuration.is_file():
        return [], [f"{_display(root, configuration)} is required for seeded maps"]
    metadata = load_metadata(configuration)

    bindings: list[Binding] = []
    errors: list[str] = []
    for directory in enabled:
        binding, violations = _binding(root, bundle, metadata, directory)
        errors.extend(violations)
        if binding is not None:
            bindings.append(binding)
    return bindings, errors


def _enabled(directory: Path) -> bool:
    return (directory / "update.py").exists() or any(directory.glob("*.json"))


def _binding(
    root: Path,
    bundle: Bundle,
    configuration: dict[str, Any],
    directory: Path,
) -> tuple[Binding | None, list[str]]:
    errors: list[str] = []
    path = directory / f"{directory.name}.json"
    if not path.is_file():
        errors.append(f"{_display(root, path)} is required")
    for candidate in sorted(directory.glob("*.json")):
        if candidate == path:
            continue
        errors.append(
            f"{_display(root, candidate)} is not a valid seed path; "
            f"expected {_display(root, path)}"
        )

    updater = directory / "update.py"
    if not updater.is_file():
        errors.append(f"{_display(root, updater)} is required")
    variables = _variables(bundle.path, updater)
    variable = variables[0] if len(variables) == 1 else None
    if variable is None:
        errors.append(f"{_display(root, path)} must bind to exactly one table")
        return None, errors

    declarations = configuration.get("variables")
    if not isinstance(declarations, dict) or variable not in declarations:
        errors.append(
            f"{_display(root, path)} references undeclared table variable {variable}"
        )
        return None, errors

    targets = configuration.get("targets")
    destinations: list[Destination] = []
    for target in TARGETS:
        settings = targets.get(target) if isinstance(targets, dict) else None
        values = settings.get("variables") if isinstance(settings, dict) else None
        table = values.get(variable) if isinstance(values, dict) else None
        if not isinstance(table, str) or not table.strip():
            errors.append(
                f"{_display(root, path)} {target} must resolve table variable {variable}"
            )
            continue
        destinations.append(Destination(target=target, table=table))

    if errors:
        return None, errors
    return Binding(path=path, destinations=tuple(destinations)), []


def _variables(bundle: Path, updater: Path) -> list[str | None]:
    resources = bundle / "resources"
    if not resources.is_dir():
        return []

    variables: list[str | None] = []
    for path in sorted(resources.glob("*.yml")):
        metadata = load_metadata(path)
        for task in _tasks(metadata):
            python = task.get("spark_python_task")
            if not isinstance(python, dict):
                continue
            source = python.get("python_file")
            if not isinstance(source, str):
                continue
            if (path.parent / source).resolve() != updater.resolve():
                continue
            variables.append(_variable(python.get("parameters")))
    return variables


def _tasks(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    resources = metadata.get("resources")
    jobs = resources.get("jobs") if isinstance(resources, dict) else None
    if not isinstance(jobs, dict):
        return []

    tasks: list[dict[str, Any]] = []
    for job in jobs.values():
        configured = job.get("tasks") if isinstance(job, dict) else None
        if not isinstance(configured, list):
            continue
        tasks.extend(task for task in configured if isinstance(task, dict))
    return tasks


def _variable(parameters: Any) -> str | None:
    if not isinstance(parameters, list):
        return None
    indexes = [index for index, value in enumerate(parameters) if value == "--table"]
    if len(indexes) != 1 or indexes[0] + 1 >= len(parameters):
        return None
    value = parameters[indexes[0] + 1]
    if not isinstance(value, str):
        return None
    match = VARIABLE.fullmatch(value)
    return match.group(1) if match is not None else None


def _display(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()
