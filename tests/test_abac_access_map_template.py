import json
import re
import shutil
from pathlib import Path
from typing import Any

from repoctl.discovery import discover
from repoctl.metadata import load_metadata
from repoctl.validation import validate_repo

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "templates" / "bundles" / "abac-access-map"

MATERIALIZED_PROJECT = "platform-governance"
MATERIALIZED_BUNDLE = "customer-region-access"
MATERIALIZED_ACCESS_KEY = "region_code"
MATERIALIZED_ACCESS_MAP_TABLE = "prod_security.access_maps.customer_region_access"
MATERIALIZED_POLICY_UDF = "prod_security.policies.can_read_customer_region"

PLACEHOLDERS = {
    "__BUNDLE_NAME__": MATERIALIZED_BUNDLE,
    "__OWNER_TEAM__": MATERIALIZED_PROJECT,
    "__ACCESS_MAP_TABLE__": MATERIALIZED_ACCESS_MAP_TABLE,
    "__POLICY_UDF__": MATERIALIZED_POLICY_UDF,
    "__ACCESS_KEY__": MATERIALIZED_ACCESS_KEY,
}
PLACEHOLDER_PATTERN = re.compile(r"__[A-Z0-9_]+__")
EXPECTED_ACCESS_MAP_COLUMNS = {
    "effective_principal": ("STRING", "NOT NULL"),
    "principal_type": ("STRING", "NOT NULL"),
    MATERIALIZED_ACCESS_KEY: ("STRING", "NOT NULL"),
    "access_level": ("STRING", "NOT NULL"),
    "is_active": ("BOOLEAN", "NOT NULL"),
    "valid_from": ("TIMESTAMP", "NOT NULL"),
    "expires_at": ("TIMESTAMP", "NULL"),
    "source_decision_id": ("STRING", "NOT NULL"),
    "source_system": ("STRING", "NOT NULL"),
    "updated_at": ("TIMESTAMP", "NOT NULL"),
}


def write_json_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def materialize_abac_access_map_template(root: Path) -> Path:
    bundle_root = (
        root / "projects" / MATERIALIZED_PROJECT / "bundles" / MATERIALIZED_BUNDLE
    )
    shutil.copytree(TEMPLATE_ROOT, bundle_root)

    write_json_yaml(
        root / "projects" / MATERIALIZED_PROJECT / "project.yaml",
        {
            "version": 1,
            "name": MATERIALIZED_PROJECT,
            "owner": {"team": MATERIALIZED_PROJECT},
            "review": {"policy": "owner-approval"},
        },
    )

    for path in bundle_root.rglob("*"):
        if path.is_file():
            rendered = path.read_text(encoding="utf-8")
            for placeholder, value in PLACEHOLDERS.items():
                rendered = rendered.replace(placeholder, value)
            path.write_text(rendered, encoding="utf-8")

    return bundle_root


def load_fixture_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_no_unresolved_placeholders(bundle_root: Path) -> None:
    for path in [bundle_root, *bundle_root.rglob("*")]:
        relative_path = path.relative_to(bundle_root)
        for part in relative_path.parts:
            assert PLACEHOLDER_PATTERN.search(part) is None, path

        if path.is_file():
            contents = path.read_text(encoding="utf-8")
            assert PLACEHOLDER_PATTERN.search(contents) is None, path


def normalized_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).lower()


def strip_sql_line_comments(sql: str) -> str:
    return re.sub(r"--.*", "", sql)


def extract_access_map_ddl_columns(sql: str) -> dict[str, tuple[str, str]]:
    table_pattern = re.escape(MATERIALIZED_ACCESS_MAP_TABLE).replace(r"\.", r"\.")
    match = re.search(
        r"create\s+(?:or\s+replace\s+)?table\s+(?:if\s+not\s+exists\s+)?"
        rf"{table_pattern}\s*\((?P<columns>.*?)\)",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match is not None

    columns = {}
    for raw_line in match.group("columns").splitlines():
        line = raw_line.split("--", 1)[0].strip().rstrip(",")
        if not line:
            continue

        column_match = re.match(
            r"(?P<name>[a-z_]+)\s+(?P<type>STRING|BOOLEAN|TIMESTAMP)"
            r"(?:\s+(?P<not_null>NOT\s+NULL))?$",
            line,
            flags=re.IGNORECASE,
        )
        assert column_match is not None, line
        nullability = "NOT NULL" if column_match.group("not_null") else "NULL"
        columns[column_match.group("name")] = (
            column_match.group("type").upper(),
            nullability,
        )
    return columns


def case_is_allowed(
    access_rows: list[dict[str, Any]],
    *,
    principal: str | None,
    access_key_value: str | None,
) -> bool:
    if principal is None or access_key_value is None:
        return False

    return any(
        row["effective_principal"] == principal
        and row[MATERIALIZED_ACCESS_KEY] == access_key_value
        and row["is_active"] is True
        and row["access_level"] in {"read", "admin_view"}
        and row["valid_from"] <= "2026-01-15T12:00:00Z"
        and (
            row["expires_at"] is None
            or "2026-01-15T12:00:00Z" < row["expires_at"]
        )
        for row in access_rows
    )


def test_abac_access_map_template_materializes_to_valid_testable_bundle(
    tmp_path: Path,
) -> None:
    bundle_root = materialize_abac_access_map_template(tmp_path)

    assert_no_unresolved_placeholders(bundle_root)

    validation = validate_repo(tmp_path)
    assert validation.ok is True, validation.errors

    discovery = discover(tmp_path)
    assert [bundle.name for bundle in discovery.bundles] == [MATERIALIZED_BUNDLE]
    assert discovery.bundles[0].metadata_path == bundle_root / "repoctl.bundle.yaml"
    assert discovery.bundles[0].metadata["type"] == "abac-access-map"
    assert discovery.bundles[0].metadata["targets"] == {
        "dev": {"mode": "development", "default": True, "local": True},
        "uat": {"mode": "production", "ci_only": True},
        "prod": {"mode": "production", "ci_only": True},
    }

    native_databricks_config = load_metadata(bundle_root / "databricks.yml")
    assert set(native_databricks_config) == {"bundle", "targets"}
    assert native_databricks_config["bundle"]["name"] == MATERIALIZED_BUNDLE
    assert native_databricks_config["targets"] == {
        "dev": {"mode": "development", "default": True},
        "uat": {"mode": "production"},
        "prod": {"mode": "production"},
    }
    assert "resources" not in native_databricks_config
    assert "include" not in native_databricks_config
    assert not (bundle_root / "bundle.yaml").exists()

    expected_sql_files = {
        "access_map_ddl.sql",
        "can_read_access.sql",
        "row_filter.sql",
    }
    assert {path.name for path in (bundle_root / "sql").glob("*.sql")} == expected_sql_files

    ddl = (bundle_root / "sql" / "access_map_ddl.sql").read_text(encoding="utf-8")
    udf = (bundle_root / "sql" / "can_read_access.sql").read_text(encoding="utf-8")
    row_filter = (bundle_root / "sql" / "row_filter.sql").read_text(encoding="utf-8")
    assert MATERIALIZED_ACCESS_MAP_TABLE in ddl
    assert MATERIALIZED_ACCESS_MAP_TABLE in udf
    assert MATERIALIZED_POLICY_UDF in udf
    assert MATERIALIZED_POLICY_UDF in row_filter
    assert MATERIALIZED_ACCESS_KEY in ddl
    assert MATERIALIZED_ACCESS_KEY in udf
    assert MATERIALIZED_ACCESS_KEY in row_filter
    assert extract_access_map_ddl_columns(ddl) == EXPECTED_ACCESS_MAP_COLUMNS

    executable_udf = normalized_sql(strip_sql_line_comments(udf))
    assert re.search(
        rf"\(\s*principal\s+STRING\s*,\s*{MATERIALIZED_ACCESS_KEY}\s+STRING\s*\)"
        r"\s*RETURNS\s+BOOLEAN",
        udf,
        flags=re.IGNORECASE,
    )
    assert f"{MATERIALIZED_ACCESS_MAP_TABLE}" in executable_udf
    assert "effective_principal = principal" not in executable_udf
    assert (
        f"{MATERIALIZED_ACCESS_KEY} = {MATERIALIZED_ACCESS_KEY}"
        not in executable_udf
    )
    assert re.search(
        r"access_map\.effective_principal\s*=\s*args\.requested_principal",
        executable_udf,
    )
    assert re.search(
        rf"access_map\.{MATERIALIZED_ACCESS_KEY}\s*=\s*args\.requested_access_key",
        executable_udf,
    )
    assert "principal is null" in executable_udf
    assert f"{MATERIALIZED_ACCESS_KEY} is null" in executable_udf
    assert "is_active = true" in executable_udf
    assert re.search(
        r"access_level\s+in\s*\(\s*'read'\s*,\s*'admin_view'\s*\)",
        executable_udf,
    )
    assert re.search(r"valid_from\s+<=\s+current_timestamp\(\)", executable_udf)
    assert re.search(
        r"expires_at\s+is\s+null\s+or\s+current_timestamp\(\)\s+<\s+"
        r"(?:[a-z_]+\.)?expires_at",
        executable_udf,
    )
    assert "false" in executable_udf

    executable_row_filter = normalized_sql(strip_sql_line_comments(row_filter))
    assert (
        f"{MATERIALIZED_POLICY_UDF}(current_user(), {MATERIALIZED_ACCESS_KEY})"
        in executable_row_filter
    )

    access_map_rows = load_fixture_json(
        bundle_root / "tests" / "fixtures" / "access_map_rows.json"
    )
    contract_cases = load_fixture_json(
        bundle_root / "tests" / "fixtures" / "contract_cases.json"
    )
    assert isinstance(access_map_rows, list)
    assert isinstance(contract_cases, list)

    case_names = {case["name"] for case in contract_cases}
    assert "allows_read_access_level" in case_names
    assert "fails_closed_when_no_matching_row" in case_names

    for contract_case in contract_cases:
        assert (
            case_is_allowed(
                access_map_rows,
                principal=contract_case["principal"],
                access_key_value=contract_case[MATERIALIZED_ACCESS_KEY],
            )
            is contract_case["expected"]
        )
