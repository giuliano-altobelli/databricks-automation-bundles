from __future__ import annotations

from dataclasses import dataclass


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
    target: str
    kind: str
    principals: tuple[str, ...]
    exceptions: tuple[str, ...]
    condition: Tag
    matches: tuple[Match, ...]
    filter: Filter


@dataclass(frozen=True)
class Result:
    action: str
    identity: tuple[str, str, str]
    fields: tuple[str, ...]
