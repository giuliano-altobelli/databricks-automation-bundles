from __future__ import annotations

from client import Client
from databricks.sdk.errors import NotFound, ResourceConflict
from definition import Definition, Location, Result
from render import information
from state import difference, snapshot


def reconcile(
    client: Client,
    definition: Definition,
    location: Location,
) -> Result:
    identity = key(definition, location)
    return converge(client, definition, location, identity, True)


def converge(
    client: Client,
    definition: Definition,
    location: Location,
    identity: tuple[str, str, str],
    retry: bool,
) -> Result:
    try:
        current = get(client, identity)
    except NotFound:
        return create(client, definition, location, identity, retry)
    return update(client, definition, location, identity, current, retry)


def create(
    client: Client,
    definition: Definition,
    location: Location,
    identity: tuple[str, str, str],
    retry: bool,
) -> Result:
    try:
        client.policies.create_policy(
            policy_info=information(definition, location, True)
        )
    except ResourceConflict as conflict:
        try:
            current = get(client, identity)
        except NotFound:
            raise conflict from None
        return update(client, definition, location, identity, current, retry)
    verify(client, definition, location, identity)
    return Result(action="created", identity=identity, fields=())


def update(
    client: Client,
    definition: Definition,
    location: Location,
    identity: tuple[str, str, str],
    current: object,
    retry: bool,
) -> Result:
    target = snapshot(information(definition, location, True))
    actual = snapshot(current)
    if actual.identity != target.identity:
        raise RuntimeError(
            f"policy identity mismatch: expected {target.identity}, found {actual.identity}"
        )
    fields = difference(actual, target)
    if not fields:
        return Result(action="unchanged", identity=identity, fields=())
    try:
        client.policies.update_policy(
            on_securable_type=identity[0],
            on_securable_fullname=identity[1],
            name=identity[2],
            policy_info=information(definition, location, False),
            update_mask=",".join(fields),
        )
    except NotFound:
        if not retry:
            raise
        return converge(client, definition, location, identity, False)
    verify(client, definition, location, identity)
    return Result(action="updated", identity=identity, fields=fields)


def verify(
    client: Client,
    definition: Definition,
    location: Location,
    identity: tuple[str, str, str],
) -> None:
    target = snapshot(information(definition, location, True))
    actual = snapshot(get(client, identity))
    if actual.identity != target.identity or difference(actual, target):
        raise RuntimeError(f"policy did not converge: {identity}")


def get(client: Client, identity: tuple[str, str, str]) -> object:
    return client.policies.get_policy(
        on_securable_type=identity[0],
        on_securable_fullname=identity[1],
        name=identity[2],
    )


def key(definition: Definition, location: Location) -> tuple[str, str, str]:
    if location.catalog is None:
        raise RuntimeError("policy catalog is required")
    return (definition.scope, location.catalog, definition.name)
