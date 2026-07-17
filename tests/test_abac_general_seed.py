import hashlib
import importlib.util
import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP = (
    ROOT
    / "projects"
    / "platform-governance"
    / "bundles"
    / "abac-general-access"
    / "maps"
    / "okta-group"
)
UPDATE = MAP / "update.py"


def load(name: str, path: Path) -> ModuleType:
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def row() -> dict[str, Any]:
    return {
        "effective_principal": "analyst@example.com",
        "okta_group_name": "finance-readers",
        "access_level": "read",
        "is_active": True,
        "valid_from": "2026-01-01T00:00:00Z",
        "expires_at": None,
    }


@pytest.fixture
def seed() -> ModuleType:
    return load("okta_group_seed", MAP / "seed.py")


@pytest.fixture
def update(seed: ModuleType, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setitem(sys.modules, "seed", seed)
    return load("okta_group_update", UPDATE)


def write(path: Path, payload: object) -> bytes:
    content = (json.dumps(payload, indent=2) + "\n").encode()
    path.write_bytes(content)
    return content


def test_seed_loads_typed_non_empty_snapshot(seed: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "okta-group.json"
    content = write(path, [row()])

    snapshot = seed.load(path)

    assert snapshot.digest == hashlib.sha256(content).hexdigest()
    assert snapshot.rows == (
        seed.Row(
            effective_principal="analyst@example.com",
            okta_group_name="finance-readers",
            access_level="read",
            is_active=True,
            valid_from=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
            expires_at=None,
        ),
    )


def test_deployed_seed_is_valid_and_non_empty(seed: ModuleType) -> None:
    snapshot = seed.load(MAP / "okta-group.json")

    assert snapshot.rows


@pytest.mark.parametrize(
    "change",
    [
        {"access_level": "admin_view"},
        {"is_active": False},
        {"valid_from": "2030-01-01T00:00:00Z"},
        {"expires_at": "2026-06-01T00:00:00Z"},
        {
            "valid_from": "2026-01-01T00:00:00-08:00",
            "expires_at": "2026-01-02T00:00:00-08:00",
        },
    ],
)
def test_seed_accepts_supported_lifecycle_states(
    seed: ModuleType,
    tmp_path: Path,
    change: dict[str, Any],
) -> None:
    payload = row()
    payload.update(change)
    path = tmp_path / "okta-group.json"
    write(path, [payload])

    assert len(seed.load(path).rows) == 1


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"{", "valid JSON"),
        (b"{}\n", "non-empty array"),
        (b"[]\n", "non-empty array"),
        (
            b'[{"effective_principal":"first@example.com",'
            b'"effective_principal":"second@example.com"}]',
            "duplicate field effective_principal",
        ),
        (b"\xff", "UTF-8"),
    ],
)
def test_seed_rejects_invalid_document(
    seed: ModuleType,
    tmp_path: Path,
    content: bytes,
    message: str,
) -> None:
    path = tmp_path / "okta-group.json"
    path.write_bytes(content)

    with pytest.raises(seed.Violation, match=message):
        seed.load(path)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"effective_principal": None}, "effective_principal must be a non-empty string"),
        ({"effective_principal": "  "}, "effective_principal must be a non-empty string"),
        ({"okta_group_name": ""}, "okta_group_name must be a non-empty string"),
        ({"access_level": "write"}, "access_level must be one of"),
        ({"is_active": 1}, "is_active must be a Boolean"),
        ({"valid_from": "not-a-timestamp"}, "valid_from must be an ISO 8601 timestamp"),
        (
            {"valid_from": "2026-01-01T00:00:00"},
            "valid_from must include a timezone",
        ),
        ({"expires_at": 1}, "expires_at must be null or an ISO 8601 timestamp"),
        (
            {"expires_at": "2026-12-31T00:00:00"},
            "expires_at must include a timezone",
        ),
        (
            {"expires_at": "2025-12-31T23:59:59Z"},
            "expires_at must be later than valid_from",
        ),
        (
            {"expires_at": "2026-01-01T00:00:00Z"},
            "expires_at must be later than valid_from",
        ),
    ],
)
def test_seed_rejects_invalid_row_values(
    seed: ModuleType,
    tmp_path: Path,
    change: dict[str, Any],
    message: str,
) -> None:
    payload = row()
    payload.update(change)
    path = tmp_path / "okta-group.json"
    write(path, [payload])

    with pytest.raises(seed.Violation, match=message):
        seed.load(path)


def test_seed_rejects_non_object_missing_and_additional_fields(
    seed: ModuleType,
    tmp_path: Path,
) -> None:
    path = tmp_path / "okta-group.json"
    write(path, ["row"])

    with pytest.raises(seed.Violation, match="row 1 must be an object"):
        seed.load(path)

    missing = row()
    del missing["expires_at"]
    write(path, [missing])
    with pytest.raises(seed.Violation, match="row 1 fields must be exactly"):
        seed.load(path)

    additional = row()
    additional["source"] = "manual"
    write(path, [additional])
    with pytest.raises(seed.Violation, match="row 1 fields must be exactly"):
        seed.load(path)


def test_seed_rejects_duplicate_principal_group_key(
    seed: ModuleType,
    tmp_path: Path,
) -> None:
    duplicate = deepcopy(row())
    duplicate["access_level"] = "admin_view"
    path = tmp_path / "okta-group.json"
    write(path, [row(), duplicate])

    with pytest.raises(
        seed.Violation,
        match="duplicate key .*analyst@example.com.*finance-readers",
    ):
        seed.load(path)


class Result:
    def __init__(self) -> None:
        self.collected = False

    def collect(self) -> list[object]:
        self.collected = True
        return []


class Frame:
    def __init__(self) -> None:
        self.view: str | None = None

    def createOrReplaceTempView(self, name: str) -> None:
        self.view = name


class Session:
    def __init__(self) -> None:
        self.rows: list[tuple[object, ...]] | None = None
        self.schema: str | None = None
        self.frame = Frame()
        self.queries: list[tuple[str, dict[str, str]]] = []
        self.result = Result()

    def createDataFrame(self, rows: list[tuple[object, ...]], schema: str) -> Frame:
        self.rows = rows
        self.schema = schema
        return self.frame

    def sql(self, query: str, args: dict[str, str]) -> Result:
        self.queries.append((query, args))
        return self.result


def test_update_performs_one_parameterized_authoritative_overwrite(
    update: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "okta-group.json"
    write(path, [row()])
    session = Session()

    snapshot = update.execute(session, "security.access.okta_group", path)

    assert len(snapshot.rows) == 1
    assert session.rows == [
        (
            "analyst@example.com",
            "finance-readers",
            "read",
            True,
            datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
            None,
        )
    ]
    assert session.schema == update.SCHEMA
    assert session.frame.view == "seed"
    assert len(session.queries) == 1
    query, arguments = session.queries[0]
    assert " ".join(query.split()) == (
        "INSERT OVERWRITE TABLE IDENTIFIER(:table) BY NAME "
        "SELECT effective_principal, okta_group_name, access_level, is_active, "
        "valid_from, expires_at FROM seed"
    )
    assert arguments == {"table": "security.access.okta_group"}
    assert session.result.collected is True
    output = capsys.readouterr().out
    assert f"seed={path} rows=1 sha256={snapshot.digest}" in output
    assert f"updated=security.access.okta_group rows=1 sha256={snapshot.digest}" in output


def test_update_derives_seed_from_its_map_directory(update: ModuleType) -> None:
    assert update.source(MAP) == MAP / "okta-group.json"


def test_update_loads_without_file_global(
    seed: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "seed", seed)
    monkeypatch.chdir(MAP)
    scope: dict[str, Any] = {"__name__": "okta_group_update_runtime"}

    exec(compile(UPDATE.read_bytes(), str(UPDATE), "exec"), scope)

    assert scope["source"](Path.cwd()) == MAP / "okta-group.json"


def test_update_rejects_invalid_seed_before_spark_interaction(
    seed: ModuleType,
    update: ModuleType,
    tmp_path: Path,
) -> None:
    path = tmp_path / "okta-group.json"
    write(path, [])
    session = Session()

    with pytest.raises(seed.Violation, match="non-empty array"):
        update.execute(session, "security.access.okta_group", path)

    assert session.rows is None
    assert session.queries == []


def test_update_propagates_the_single_write_failure(
    update: ModuleType,
    tmp_path: Path,
) -> None:
    class Failed(Session):
        def sql(self, query: str, args: dict[str, str]) -> Result:
            super().sql(query, args)
            raise RuntimeError("write failed")

    path = tmp_path / "okta-group.json"
    write(path, [row()])
    session = Failed()

    with pytest.raises(RuntimeError, match="write failed"):
        update.execute(session, "security.access.okta_group", path)

    assert len(session.queries) == 1
