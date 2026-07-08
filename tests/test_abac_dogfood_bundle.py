import re
from pathlib import Path

from repoctl.discovery import discover
from repoctl.validation import validate_repo

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = (
    ROOT / "projects" / "platform-governance" / "bundles" / "abac-jira-project-access"
)
EXPECTED_ACCESS_MAP_COLUMNS = {
    "effective_principal": ("STRING", "NOT NULL"),
    "principal_type": ("STRING", "NOT NULL"),
    "project_key": ("STRING", "NOT NULL"),
    "access_level": ("STRING", "NOT NULL"),
    "is_active": ("BOOLEAN", "NOT NULL"),
    "valid_from": ("TIMESTAMP", "NOT NULL"),
    "expires_at": ("TIMESTAMP", "NULL"),
    "source_decision_id": ("STRING", "NOT NULL"),
    "source_system": ("STRING", "NOT NULL"),
    "updated_at": ("TIMESTAMP", "NOT NULL"),
}


def test_repo_validation_accepts_abac_dogfood_bundle_metadata() -> None:
    result = validate_repo(ROOT)

    assert result.ok is True, result.errors


def test_discovery_finds_abac_dogfood_bundle_with_expected_metadata() -> None:
    result = discover(ROOT)

    bundle = next(
        bundle
        for bundle in result.bundles
        if bundle.path.relative_to(ROOT).as_posix()
        == "projects/platform-governance/bundles/abac-jira-project-access"
    )

    assert bundle.project == "platform-governance"
    assert bundle.name == "abac-jira-project-access"
    assert bundle.metadata["type"] == "abac-access-map"


def load_spec() -> str:
    return (BUNDLE_ROOT / "SPEC.md").read_text(encoding="utf-8")


def extract_column_contracts(spec: str) -> dict[str, tuple[str, str]]:
    rows = re.findall(
        r"^\|\s*`(?P<name>[a-z_]+)`\s*\|\s*`(?P<type>[A-Z]+)`\s*\|"
        r"\s*`(?P<nullability>NOT NULL|NULL)`\s*\|",
        spec,
        flags=re.MULTILINE,
    )
    return {
        name: (column_type, nullability)
        for name, column_type, nullability in rows
        if name in EXPECTED_ACCESS_MAP_COLUMNS
    }


def extract_allowed_access_levels(spec: str) -> set[str]:
    match = re.search(
        r"Allowed access levels are exactly:\s*(?P<levels>(?:`[a-z_]+`(?:,\s*)?)+)\.",
        spec,
    )
    assert match is not None
    return set(re.findall(r"`([a-z_]+)`", match.group("levels")))


def test_abac_dogfood_spec_keeps_original_boundary_decisions() -> None:
    spec = load_spec()

    required_phrases = [
        "Jira project-key row access",
        "prod_security.access_maps.jira_project_access",
        "prod_security.policies.can_read_jira_project",
        "project_key",
        "one row per effective principal, project key, access level, and source decision",
        "fails closed to zero protected rows",
        "does not dynamically resolve group membership at query time",
        "policy SQL contract/fragments",
        "Terraform remains owner of stable platform policy definitions",
        "live attachment/rollout controls",
        "no live Databricks resources are created by this task",
        "repo validation",
        "changed-bundles",
        "bundle validation",
        "ABAC contract tests",
        "approved promotion decision",
    ]

    for phrase in required_phrases:
        assert phrase in spec


def test_abac_dogfood_spec_defines_sql_facing_access_map_columns() -> None:
    spec = load_spec()

    assert extract_column_contracts(spec) == EXPECTED_ACCESS_MAP_COLUMNS


def test_abac_dogfood_spec_defines_exact_access_level_contract() -> None:
    spec = load_spec()

    assert extract_allowed_access_levels(spec) == {"read", "admin_view"}
    assert "Unknown access levels fail closed." in spec


def test_abac_dogfood_spec_defines_udf_signature_and_policy_predicate() -> None:
    spec = load_spec()

    assert (
        "`prod_security.policies.can_read_jira_project(principal STRING, project_key STRING)"
        " RETURNS BOOLEAN`"
    ) in spec
    assert "current active access-map row for the principal/project" in spec
    assert "access_level in (`read`, `admin_view`)" in spec
    assert "current time within the effective range" in spec
    assert "otherwise returns false" in spec
    assert (
        "`prod_security.policies.can_read_jira_project(current_user(), project_key)`"
        in spec
    )
    assert "principal argument equivalent supplied by Databricks policy context" in spec
