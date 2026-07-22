from __future__ import annotations

import argparse

import preflight
import reconcile
from client import workspace
from definition import Definition, Location


def main(definition: Definition) -> None:
    parser = argparse.ArgumentParser()
    operations = parser.add_subparsers(dest="operation", required=True)
    validation = operations.add_parser("preflight")
    validation.add_argument("--schema", required=True)
    validation.add_argument("--catalog")
    convergence = operations.add_parser("reconcile")
    convergence.add_argument("--schema", required=True)
    convergence.add_argument("--catalog", required=True)
    arguments = parser.parse_args()
    location = Location(catalog=arguments.catalog, schema=arguments.schema)
    client = workspace()

    if arguments.operation == "preflight":
        preflight.validate(client, definition, location)
        catalog = location.catalog if location.catalog is not None else "none"
        print(f"validated schema={location.schema} catalog={catalog}")
        return

    result = reconcile.reconcile(client, definition, location)
    fields = ",".join(result.fields) if result.fields else "none"
    identity = "/".join(result.identity)
    print(f"action={result.action} identity={identity} fields={fields}")
