from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from definition import Tag
from render import expression


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
