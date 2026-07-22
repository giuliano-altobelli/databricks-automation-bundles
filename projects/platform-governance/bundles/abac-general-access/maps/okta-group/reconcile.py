from __future__ import annotations

import argparse

from client import Client, workspace
from databricks.sdk.errors import NotFound, ResourceConflict
from policy import (
    Definition,
    Location,
    Result,
    desired,
    difference,
    information,
    snapshot,
)


def reconcile(client: Client, location: Location) -> Result:
    definition = desired(location)
    identity = key(definition)
    return converge(client, definition, identity, True)


def converge(
    client: Client,
    definition: Definition,
    identity: tuple[str, str, str],
    retry: bool,
) -> Result:
    try:
        current = get(client, identity)
    except NotFound:
        return create(client, definition, identity, retry)
    return update(client, definition, identity, current, retry)


def create(
    client: Client,
    definition: Definition,
    identity: tuple[str, str, str],
    retry: bool,
) -> Result:
    try:
        client.policies.create_policy(policy_info=information(definition, True))
    except ResourceConflict as conflict:
        try:
            current = get(client, identity)
        except NotFound:
            raise conflict from None
        return update(client, definition, identity, current, retry)
    verify(client, definition, identity)
    return Result(action="created", identity=identity, fields=())


def update(
    client: Client,
    definition: Definition,
    identity: tuple[str, str, str],
    current: object,
    retry: bool,
) -> Result:
    target = snapshot(information(definition, True))
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
            policy_info=information(definition, False),
            update_mask=",".join(fields),
        )
    except NotFound:
        if not retry:
            raise
        return converge(client, definition, identity, False)
    verify(client, definition, identity)
    return Result(action="updated", identity=identity, fields=fields)


def verify(
    client: Client,
    definition: Definition,
    identity: tuple[str, str, str],
) -> None:
    target = snapshot(information(definition, True))
    actual = snapshot(get(client, identity))
    if actual.identity != target.identity or difference(actual, target):
        raise RuntimeError(f"policy did not converge: {identity}")


def get(client: Client, identity: tuple[str, str, str]) -> object:
    return client.policies.get_policy(
        on_securable_type=identity[0],
        on_securable_fullname=identity[1],
        name=identity[2],
    )


def key(definition: Definition) -> tuple[str, str, str]:
    if definition.catalog is None:
        raise RuntimeError("policy catalog is required")
    return (definition.scope, definition.catalog, definition.name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", required=True)
    parser.add_argument("--catalog", required=True)
    arguments = parser.parse_args()
    result = reconcile(
        workspace(),
        Location(catalog=arguments.catalog, schema=arguments.schema),
    )
    fields = ",".join(result.fields) if result.fields else "none"
    identity = "/".join(result.identity)
    print(f"action={result.action} identity={identity} fields={fields}")


if __name__ == "__main__":
    main()
