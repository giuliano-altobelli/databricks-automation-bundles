from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from databricks.sdk.service.catalog import (
    FunctionArgument,
    MatchColumn,
    PolicyInfo,
    PolicyType,
    RowFilterOptions,
    SecurableType,
)


@dataclass(frozen=True)
class Location:
    catalog: str | None
    schema: str


@dataclass(frozen=True)
class Tag:
    key: str
    value: str


@dataclass(frozen=True)
class Match:
    tag: Tag
    alias: str


@dataclass(frozen=True)
class Filter:
    function: str
    using: tuple[str, ...]


@dataclass(frozen=True)
class Definition:
    name: str
    comment: str
    scope: str
    catalog: str | None
    target: str
    kind: str
    principals: tuple[str, ...]
    exceptions: tuple[str, ...]
    condition: Tag
    matches: tuple[Match, ...]
    filter: Filter


@dataclass(frozen=True)
class Snapshot:
    identity: tuple[str | None, str | None, str | None]
    comment: str | None
    principals: tuple[str, ...]
    exceptions: tuple[str, ...]
    target: str | None
    kind: str | None
    condition: str | None
    matches: tuple[tuple[str | None, str | None], ...]
    filter: tuple[str | None, tuple[tuple[str | None, str | None], ...]] | None
    mask: object


@dataclass(frozen=True)
class Result:
    action: str
    identity: tuple[str, str, str]
    fields: tuple[str, ...]


COUPLED = ("policy_type", "row_filter", "column_mask")
ORDER = (
    "comment",
    "to_principals",
    "except_principals",
    "for_securable_type",
    "policy_type",
    "when_condition",
    "match_columns",
    "row_filter",
    "column_mask",
)
TAG = re.compile(
    r"^\s*has_tag_value\s*\(\s*'(?P<key>(?:''|[^'])*)'\s*,\s*"
    r"'(?P<value>(?:''|[^'])*)'\s*\)\s*$",
    re.IGNORECASE,
)


def desired(location: Location) -> Definition:
    return Definition(
        name="abac_demo_okta_group_row_filter",
        comment=(
            "Filter governed demo rows by the querying user's Okta group membership."
        ),
        scope="CATALOG",
        catalog=location.catalog,
        target="TABLE",
        kind="POLICY_TYPE_ROW_FILTER",
        principals=("okta-databricks-users",),
        exceptions=("giulianoaltobelli@gmail.com",),
        condition=Tag(
            key="abac_boundary",
            value="abac_general_access_okta_group",
        ),
        matches=(
            Match(
                tag=Tag(key="protected_column", value="okta_group_names"),
                alias="okta_group_names_value",
            ),
        ),
        filter=Filter(
            function=f"{location.schema}.can_read_okta_group",
            using=("okta_group_names_value",),
        ),
    )


def expression(tag: Tag) -> str:
    key = tag.key.replace("'", "''")
    value = tag.value.replace("'", "''")
    return f"has_tag_value('{key}','{value}')"


def information(definition: Definition, identity: bool) -> PolicyInfo:
    return PolicyInfo(
        to_principals=list(definition.principals),
        for_securable_type=SecurableType(definition.target),
        policy_type=PolicyType(definition.kind),
        comment=definition.comment,
        except_principals=list(definition.exceptions),
        match_columns=[
            MatchColumn(alias=match.alias, condition=expression(match.tag))
            for match in definition.matches
        ],
        name=definition.name if identity else None,
        on_securable_fullname=definition.catalog if identity else None,
        on_securable_type=SecurableType(definition.scope) if identity else None,
        row_filter=RowFilterOptions(
            function_name=definition.filter.function,
            using=[FunctionArgument(alias=alias) for alias in definition.filter.using],
        ),
        when_condition=expression(definition.condition),
    )


def scalar(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def frozen(value: Any) -> object:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "as_dict"):
        return frozen(value.as_dict())
    if isinstance(value, dict):
        return tuple(sorted((str(key), frozen(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(frozen(item) for item in value)
    return repr(value)


def snapshot(policy: object) -> Snapshot:
    columns = tuple(
        (
            getattr(column, "alias", None),
            condition(getattr(column, "condition", None)),
        )
        for column in (getattr(policy, "match_columns", None) or [])
    )
    columns = tuple(
        sorted(
            columns,
            key=lambda column: tuple(value or "" for value in column),
        )
    )
    row = getattr(policy, "row_filter", None)
    filter = None
    if row is not None:
        arguments = tuple(
            (
                getattr(argument, "alias", None),
                getattr(argument, "constant", None),
            )
            for argument in (getattr(row, "using", None) or [])
        )
        filter = (getattr(row, "function_name", None), arguments)
    return Snapshot(
        identity=(
            scalar(getattr(policy, "on_securable_type", None)),
            getattr(policy, "on_securable_fullname", None),
            getattr(policy, "name", None),
        ),
        comment=getattr(policy, "comment", None),
        principals=tuple(sorted(getattr(policy, "to_principals", None) or [])),
        exceptions=tuple(sorted(getattr(policy, "except_principals", None) or [])),
        target=scalar(getattr(policy, "for_securable_type", None)),
        kind=scalar(getattr(policy, "policy_type", None)),
        condition=condition(getattr(policy, "when_condition", None)),
        matches=columns,
        filter=filter,
        mask=frozen(getattr(policy, "column_mask", None)),
    )


def condition(value: str | None) -> str | None:
    if value is None:
        return None
    matched = TAG.fullmatch(value)
    if matched is None:
        return value.strip()
    return expression(
        Tag(
            key=matched.group("key").replace("''", "'"),
            value=matched.group("value").replace("''", "'"),
        )
    )


def difference(current: Snapshot, target: Snapshot) -> tuple[str, ...]:
    changed: set[str] = set()
    independent = (
        ("comment", "comment"),
        ("to_principals", "principals"),
        ("except_principals", "exceptions"),
        ("for_securable_type", "target"),
    )
    for field, attribute in independent:
        if getattr(current, attribute) != getattr(target, attribute):
            changed.add(field)
    if current.kind != target.kind:
        changed.update(COUPLED)
    else:
        if current.filter != target.filter:
            changed.add("row_filter")
        if current.mask != target.mask:
            changed.add("column_mask")
    trailing = (
        ("when_condition", "condition"),
        ("match_columns", "matches"),
    )
    for field, attribute in trailing:
        if getattr(current, attribute) != getattr(target, attribute):
            changed.add(field)
    return tuple(field for field in ORDER if field in changed)
