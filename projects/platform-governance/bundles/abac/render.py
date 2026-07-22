from __future__ import annotations

from databricks.sdk.service.catalog import (
    FunctionArgument,
    MatchColumn,
    PolicyInfo,
    PolicyType,
    RowFilterOptions,
    SecurableType,
)
from definition import Definition, Location, Tag


def expression(tag: Tag) -> str:
    key = tag.key.replace("'", "''")
    value = tag.value.replace("'", "''")
    return f"has_tag_value('{key}','{value}')"


def information(
    definition: Definition,
    location: Location,
    identity: bool,
) -> PolicyInfo:
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
        on_securable_fullname=location.catalog if identity else None,
        on_securable_type=SecurableType(definition.scope) if identity else None,
        row_filter=RowFilterOptions(
            function_name=f"{location.schema}.{definition.filter.function}",
            using=[FunctionArgument(alias=alias) for alias in definition.filter.using],
        ),
        when_condition=expression(definition.condition),
    )
