from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass

from client import Client, workspace
from policy import Location, Tag, desired


@dataclass(frozen=True)
class Issue:
    resource: str
    message: str

    def __str__(self) -> str:
        return f"{self.resource}: {self.message}"


class ValidationError(RuntimeError):
    def __init__(self, errors: list[Issue]) -> None:
        self.errors = tuple(errors)
        super().__init__("\n".join(str(error) for error in errors))


def validate(client: Client, location: Location) -> None:
    local = inputs(location)
    if local:
        raise ValidationError(local)

    definition = desired(location)
    errors: list[Issue] = []
    if location.catalog is not None:
        read(
            errors,
            f"catalog {location.catalog}",
            lambda: client.catalogs.get(name=location.catalog),
        )
    read(
        errors,
        f"schema {location.schema}",
        lambda: client.schemas.get(full_name=location.schema),
    )
    if location.catalog is not None:
        tags = (definition.condition,) + tuple(match.tag for match in definition.matches)
        for tag in tags:
            governed(errors, client, tag)
    if errors:
        raise ValidationError(errors)


def inputs(location: Location) -> list[Issue]:
    errors: list[Issue] = []
    if len(location.schema.split(".")) != 2 or any(
        not part for part in location.schema.split(".")
    ):
        errors.append(Issue("schema", "must be a two-part nonempty name"))
    if location.catalog is not None and (
        "." in location.catalog or not location.catalog
    ):
        errors.append(Issue("catalog", "must be a one-part nonempty name"))
    return errors


def read(errors: list[Issue], resource: str, operation: Callable[[], object]) -> None:
    try:
        operation()
    except Exception as error:
        errors.append(Issue(resource, str(error)))


def governed(errors: list[Issue], client: Client, tag: Tag) -> None:
    try:
        policy = client.tag_policies.get_tag_policy(tag_key=tag.key)
    except Exception as error:
        errors.append(Issue(f"governed tag {tag.key}={tag.value}", str(error)))
        return
    actual = getattr(policy, "tag_key", None)
    if actual != tag.key:
        errors.append(
            Issue(
                f"governed tag {tag.key}",
                f"returned key {actual!r}",
            )
        )
        return
    values = {value.name for value in policy.values or []}
    if tag.value not in values:
        errors.append(
            Issue(
                f"governed tag {tag.key}",
                f"allowed value {tag.value} does not exist",
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True)
    parser.add_argument("--catalog")
    arguments = parser.parse_args()
    location = Location(catalog=arguments.catalog, schema=arguments.schema)
    validate(workspace(), location)
    catalog = location.catalog if location.catalog is not None else "none"
    print(f"validated schema={location.schema} catalog={catalog}")


if __name__ == "__main__":
    main()
