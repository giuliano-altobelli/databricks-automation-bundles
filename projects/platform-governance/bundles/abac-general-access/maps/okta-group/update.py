from __future__ import annotations

import argparse
from pathlib import Path
from typing import Protocol

from seed import Snapshot, load

SCHEMA = """
effective_principal STRING,
okta_group_name STRING,
access_level STRING,
is_active BOOLEAN,
valid_from TIMESTAMP,
expires_at TIMESTAMP
"""
WRITE = """
INSERT OVERWRITE TABLE IDENTIFIER(:table) BY NAME
SELECT
  effective_principal,
  okta_group_name,
  access_level,
  is_active,
  valid_from,
  expires_at
FROM seed
"""


class Result(Protocol):
    def collect(self) -> list[object]: ...


class Frame(Protocol):
    def createOrReplaceTempView(self, name: str) -> None: ...


class Session(Protocol):
    def createDataFrame(self, rows: list[tuple[object, ...]], schema: str) -> Frame: ...

    def sql(self, query: str, args: dict[str, str]) -> Result: ...


def execute(session: Session, table: str, path: Path) -> Snapshot:
    snapshot = load(path)
    print(f"seed={path} rows={len(snapshot.rows)} sha256={snapshot.digest}")
    rows = [row.values() for row in snapshot.rows]
    frame = session.createDataFrame(rows, schema=SCHEMA)
    frame.createOrReplaceTempView("seed")
    session.sql(WRITE, args={"table": table}).collect()
    print(f"updated={table} rows={len(snapshot.rows)} sha256={snapshot.digest}")
    return snapshot


def source(script: Path = Path(__file__)) -> Path:
    directory = script.resolve().parent
    return directory / f"{directory.name}.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    arguments = parser.parse_args()

    from pyspark.sql import SparkSession

    execute(SparkSession.builder.getOrCreate(), arguments.table, source())


if __name__ == "__main__":
    main()
