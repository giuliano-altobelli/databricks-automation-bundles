from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repoctl.discovery import Bundle
from repoctl.metadata import load_metadata

VARIABLE = re.compile(r"^\$\{var\.([a-z_][a-z0-9_]*)\}$")
DELIMITED = re.compile(r"(^|\.)`([A-Za-z0-9_]*[A-Za-z_][A-Za-z0-9_]*)`(?=\.|$)")
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
            key = (destination.target, _canonical(destination.table))
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
    return (directory / "update.py").exists() or bool(_seeds(directory))


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
    for candidate in _seeds(directory):
        if candidate == path:
            continue
        errors.append(
            f"{_display(root, candidate)} is not a valid seed path; "
            f"expected {_display(root, path)}"
        )

    updater = directory / "update.py"
    if not updater.is_file():
        errors.append(f"{_display(root, updater)} is required")
    documents = _documents(bundle.path, configuration)
    variables = _variables(updater, documents)
    variable = variables[0] if len(variables) == 1 else None
    if variable is None:
        errors.append(f"{_display(root, path)} must bind to exactly one table")
        return None, errors

    if not _declared(documents, variable):
        errors.append(
            f"{_display(root, path)} references undeclared table variable {variable}"
        )
        return None, errors

    destinations: list[Destination] = []
    for target in TARGETS:
        table = _value(documents, target, variable)
        if (
            not isinstance(table, str)
            or not table
            or any(character.isspace() for character in table)
        ):
            errors.append(
                f"{_display(root, path)} {target} must resolve table variable {variable}"
            )
            continue
        destinations.append(Destination(target=target, table=table))

    if errors:
        return None, errors
    return Binding(path=path, destinations=tuple(destinations)), []


def _variables(
    updater: Path,
    documents: list[tuple[Path, dict[str, Any]]],
) -> list[str | None]:
    variables: list[str | None] = []
    identities: set[tuple[str, str]] = set()
    for path, metadata in documents:
        for job, task, nested in _tasks(metadata):
            python = _python(path, task, updater)
            if python is None:
                continue
            variables.append(None if nested else _variable(python.get("parameters")))
            key = task.get("task_key")
            if isinstance(key, str):
                identities.add((job, key))

    for path, metadata in documents:
        targets = metadata.get("targets")
        if not isinstance(targets, dict):
            continue
        for settings in targets.values():
            if not isinstance(settings, dict):
                continue
            for job, task, _ in _tasks(settings):
                key = task.get("task_key")
                identified = isinstance(key, str) and (job, key) in identities
                if not identified and _python(path, task, updater) is None:
                    continue
                variables.append(None)
    return variables


def _declared(
    documents: list[tuple[Path, dict[str, Any]]],
    variable: str,
) -> bool:
    for _, metadata in documents:
        declarations = metadata.get("variables")
        if isinstance(declarations, dict) and variable in declarations:
            return True
    return False


def _value(
    documents: list[tuple[Path, dict[str, Any]]],
    target: str,
    variable: str,
) -> Any:
    discovered: list[Any] = []
    for _, metadata in documents:
        targets = metadata.get("targets")
        settings = targets.get(target) if isinstance(targets, dict) else None
        variables = settings.get("variables") if isinstance(settings, dict) else None
        if isinstance(variables, dict) and variable in variables:
            discovered.append(variables[variable])
    if not discovered or any(value != discovered[0] for value in discovered[1:]):
        return None
    return discovered[0]


def _documents(
    bundle: Path,
    configuration: dict[str, Any],
) -> list[tuple[Path, dict[str, Any]]]:
    root = bundle / "databricks.yml"
    documents = [(root, configuration)]
    included = configuration.get("include")
    if not isinstance(included, list):
        return documents

    discovered = {root.resolve()}
    for pattern in included:
        if not isinstance(pattern, str) or Path(pattern).is_absolute():
            continue
        for path in sorted(bundle.glob(pattern)):
            resolved = path.resolve()
            if not path.is_file() or resolved in discovered:
                continue
            discovered.add(resolved)
            documents.append((path, load_metadata(path)))
    return documents


def _tasks(metadata: dict[str, Any]) -> list[tuple[str, dict[str, Any], bool]]:
    resources = metadata.get("resources")
    jobs = resources.get("jobs") if isinstance(resources, dict) else None
    if not isinstance(jobs, dict):
        return []

    tasks: list[tuple[str, dict[str, Any], bool]] = []
    for name, job in jobs.items():
        if not isinstance(name, str):
            continue
        configured = job.get("tasks") if isinstance(job, dict) else None
        if not isinstance(configured, list):
            continue
        for task in configured:
            if not isinstance(task, dict):
                continue
            tasks.append((name, task, False))
            loop = task.get("for_each_task")
            nested = loop.get("task") if isinstance(loop, dict) else None
            if isinstance(nested, dict):
                tasks.append((name, nested, True))
    return tasks


def _python(path: Path, task: dict[str, Any], updater: Path) -> dict[str, Any] | None:
    python = task.get("spark_python_task")
    if not isinstance(python, dict):
        return None
    source = python.get("python_file")
    if not isinstance(source, str):
        return None
    if (path.parent / source).resolve() != updater.resolve():
        return None
    return python


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


def _seeds(directory: Path) -> list[Path]:
    return sorted(
        path
        for path in directory.rglob("*.json")
        if "fixtures" not in path.relative_to(directory).parts
    )


def _canonical(table: str) -> str:
    return DELIMITED.sub(r"\1\2", table).casefold()


def _display(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()
