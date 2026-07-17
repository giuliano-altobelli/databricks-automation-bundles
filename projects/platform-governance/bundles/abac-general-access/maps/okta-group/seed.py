from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

FIELDS = frozenset(
    {
        "effective_principal",
        "okta_group_name",
        "access_level",
        "is_active",
        "valid_from",
        "expires_at",
    }
)
LEVELS = frozenset({"read", "admin_view"})


class Violation(ValueError):
    pass


@dataclass(frozen=True)
class Row:
    effective_principal: str
    okta_group_name: str
    access_level: str
    is_active: bool
    valid_from: datetime
    expires_at: datetime | None

    def values(self) -> tuple[str, str, str, bool, datetime, datetime | None]:
        return (
            self.effective_principal,
            self.okta_group_name,
            self.access_level,
            self.is_active,
            self.valid_from,
            self.expires_at,
        )


@dataclass(frozen=True)
class Snapshot:
    rows: tuple[Row, ...]
    digest: str


def load(path: Path) -> Snapshot:
    content = path.read_bytes()
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Violation(f"{path} must be UTF-8") from error

    try:
        payload = json.loads(text, object_pairs_hook=_object)
    except json.JSONDecodeError as error:
        raise Violation(f"{path} must contain valid JSON") from error

    return Snapshot(rows=validate(payload), digest=hashlib.sha256(content).hexdigest())


def validate(payload: Any) -> tuple[Row, ...]:
    if not isinstance(payload, list) or not payload:
        raise Violation("seed must be a non-empty array")

    rows: list[Row] = []
    keys: set[tuple[str, str]] = set()
    for position, candidate in enumerate(payload, start=1):
        row = _row(candidate, position)
        key = (row.effective_principal, row.okta_group_name)
        if key in keys:
            raise Violation(f"row {position} has duplicate key {key!r}")
        keys.add(key)
        rows.append(row)

    return tuple(rows)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field, value in pairs:
        if field in result:
            raise Violation(f"duplicate field {field}")
        result[field] = value
    return result


def _row(candidate: Any, position: int) -> Row:
    if not isinstance(candidate, dict):
        raise Violation(f"row {position} must be an object")
    if set(candidate) != FIELDS:
        raise Violation(f"row {position} fields must be exactly {sorted(FIELDS)!r}")

    principal = _string(candidate["effective_principal"], "effective_principal", position)
    group = _string(candidate["okta_group_name"], "okta_group_name", position)
    level = _string(candidate["access_level"], "access_level", position)
    if level not in LEVELS:
        raise Violation(f"row {position} access_level must be one of {sorted(LEVELS)!r}")

    active = candidate["is_active"]
    if type(active) is not bool:
        raise Violation(f"row {position} is_active must be a Boolean")

    valid = _timestamp(candidate["valid_from"], "valid_from", position, nullable=False)
    assert valid is not None
    expires = _timestamp(candidate["expires_at"], "expires_at", position, nullable=True)
    if expires is not None and expires <= valid:
        raise Violation(f"row {position} expires_at must be later than valid_from")

    return Row(
        effective_principal=principal,
        okta_group_name=group,
        access_level=level,
        is_active=active,
        valid_from=valid,
        expires_at=expires,
    )


def _string(value: Any, field: str, position: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Violation(f"row {position} {field} must be a non-empty string")
    return value


def _timestamp(
    value: Any,
    field: str,
    position: int,
    *,
    nullable: bool,
) -> datetime | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        requirement = "null or an ISO 8601 timestamp" if nullable else "an ISO 8601 timestamp"
        raise Violation(f"row {position} {field} must be {requirement}")

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        timestamp = datetime.fromisoformat(normalized)
    except ValueError as error:
        requirement = "null or an ISO 8601 timestamp" if nullable else "an ISO 8601 timestamp"
        raise Violation(f"row {position} {field} must be {requirement}") from error

    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise Violation(f"row {position} {field} must include a timezone")
    return timestamp
