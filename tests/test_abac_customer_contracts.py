import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = (
    ROOT / "projects" / "platform-governance" / "bundles" / "abac-customer-access"
)
FIXTURE_ROOT = BUNDLE_ROOT / "maps" / "okta-group" / "fixtures"
ACCESS_MAP_ROWS_FIXTURE = FIXTURE_ROOT / "rows.json"
CONTRACT_CASES_FIXTURE = FIXTURE_ROOT / "cases.json"
FIXED_NOW = datetime.fromisoformat("2026-07-08T12:00:00+00:00")
ALLOWED_ACCESS_LEVELS = frozenset({"read", "admin_view"})
REQUIRED_CASES = frozenset(
    {
        "allows_empty_array",
        "fails_closed_when_array_is_null",
        "allows_single_read_group",
        "allows_single_admin_view_group",
        "allows_multiple_groups_when_all_are_granted",
        "denies_multiple_groups_when_one_is_missing",
        "denies_when_no_groups_match",
        "denies_when_only_wrong_principal_matches",
        "denies_inactive_group",
        "denies_future_group",
        "denies_expired_group",
        "denies_unknown_access_level",
        "allows_group_at_exact_valid_from",
        "denies_group_at_exact_expiry",
    }
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def grants_group(
    row: dict[str, Any],
    principal: str,
    *,
    now: datetime,
) -> bool:
    valid_from = parse_timestamp(row["valid_from"])
    expires_at = parse_timestamp(row["expires_at"])

    if row["effective_principal"] != principal:
        return False
    if row["is_active"] is not True:
        return False
    if row["access_level"] not in ALLOWED_ACCESS_LEVELS:
        return False
    if valid_from is None or valid_from > now:
        return False
    if expires_at is not None and now >= expires_at:
        return False

    return True


def can_read_customer_okta_group(
    principal: str,
    okta_group_names: list[str] | None,
    rows: list[dict[str, Any]],
    *,
    now: datetime = FIXED_NOW,
) -> bool:
    if okta_group_names is None:
        return False
    if not okta_group_names:
        return True

    granted = {
        row["okta_group_name"]
        for row in rows
        if grants_group(row, principal, now=now)
    }

    return all(okta_group_name in granted for okta_group_name in okta_group_names)


def test_customer_contract_fixture_cases_are_complete_and_well_formed() -> None:
    cases = load_json(CONTRACT_CASES_FIXTURE)
    names = [case["name"] for case in cases]

    assert len(names) == len(set(names))
    assert all(isinstance(case.get("expected"), bool) for case in cases)
    assert REQUIRED_CASES <= set(names)


def test_offline_can_read_customer_okta_group_contract_cases() -> None:
    rows = load_json(ACCESS_MAP_ROWS_FIXTURE)
    cases = load_json(CONTRACT_CASES_FIXTURE)

    for case in cases:
        assert (
            can_read_customer_okta_group(
                case["principal"],
                case["okta_group_names"],
                rows,
            )
            is case["expected"]
        ), case["name"]
