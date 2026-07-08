import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = (
    ROOT / "projects" / "platform-governance" / "bundles" / "abac-jira-project-access"
)
FIXTURE_ROOT = BUNDLE_ROOT / "tests" / "fixtures"
ACCESS_MAP_ROWS_FIXTURE = FIXTURE_ROOT / "access_map_rows.json"
CONTRACT_CASES_FIXTURE = FIXTURE_ROOT / "contract_cases.json"
CAN_READ_UDF = BUNDLE_ROOT / "sql" / "can_read_jira_project.sql"
FIXED_NOW = datetime.fromisoformat("2026-07-08T12:00:00+00:00")
ALLOWED_ACCESS_LEVELS = {"read", "admin_view"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def can_read_jira_project(
    principal: str | None,
    project_key: str | None,
    rows: list[dict[str, Any]],
    *,
    now: datetime = FIXED_NOW,
) -> bool:
    if principal is None or project_key is None:
        return False

    for row in rows:
        valid_from = parse_timestamp(row["valid_from"])
        expires_at = parse_timestamp(row["expires_at"])

        if row["effective_principal"] != principal:
            continue
        if row["project_key"] != project_key:
            continue
        if row["is_active"] is not True:
            continue
        if row["access_level"] not in ALLOWED_ACCESS_LEVELS:
            continue
        if valid_from is None or valid_from > now:
            continue
        if expires_at is not None and now >= expires_at:
            continue

        return True

    return False


def strip_sql_line_comments(sql: str) -> str:
    return re.sub(r"--.*", "", sql)


def extract_executable_sql_literals(sql: str) -> list[str]:
    executable = strip_sql_line_comments(sql)
    return re.findall(r"'([^']+)'", executable)


def test_abac_contract_fixture_cases_have_unique_names_and_expected_boolean() -> None:
    cases = load_json(CONTRACT_CASES_FIXTURE)

    names = [case["name"] for case in cases]

    assert len(names) == len(set(names))
    assert all(isinstance(case.get("expected"), bool) for case in cases)


def test_offline_can_read_jira_project_contract_cases() -> None:
    rows = load_json(ACCESS_MAP_ROWS_FIXTURE)
    cases = load_json(CONTRACT_CASES_FIXTURE)

    for case in cases:
        assert (
            can_read_jira_project(case["principal"], case["project_key"], rows)
            is case["expected"]
        ), case["name"]


def test_can_read_jira_project_udf_access_levels_match_offline_contract() -> None:
    literals = extract_executable_sql_literals(CAN_READ_UDF.read_text(encoding="utf-8"))

    assert set(literals) == ALLOWED_ACCESS_LEVELS
    assert len(literals) == len(ALLOWED_ACCESS_LEVELS)
