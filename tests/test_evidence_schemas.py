import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas" / "evidence"
DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
TARGETS = ["dev", "uat", "prod"]

EXPECTED_SCHEMAS = {
    "repo-validation.schema.json": {
        "required": ["status"],
        "constraints": {
            "status": {"const": "passed"},
        },
    },
    "changed-bundles.schema.json": {
        "required": ["changed_bundles"],
        "constraints": {
            "changed_bundles": {
                "type": "array",
                "items.type": "string",
                "items.minLength": 1,
            },
        },
    },
    "bundle-validation.schema.json": {
        "required": ["bundle", "target", "status"],
        "constraints": {
            "bundle": {"type": "string", "minLength": 1},
            "target": {"enum": TARGETS},
            "status": {"const": "passed"},
        },
    },
    "abac-contract-tests.schema.json": {
        "required": ["bundle", "target", "status"],
        "constraints": {
            "bundle": {"type": "string", "minLength": 1},
            "target": {"enum": TARGETS},
            "status": {"const": "passed"},
        },
    },
    "promotion-decision.schema.json": {
        "required": ["bundle", "target", "decision"],
        "constraints": {
            "bundle": {"type": "string", "minLength": 1},
            "target": {"enum": TARGETS},
            "decision": {"const": "approved"},
        },
    },
}


def assert_constraint(property_schema: dict, constraint_path: str, expected: object) -> None:
    value = property_schema
    for path_part in constraint_path.split("."):
        value = value[path_part]

    assert value == expected


def load_schema(filename: str) -> dict:
    path = SCHEMA_DIR / filename

    assert path.is_file(), f"missing schema file: {path}"
    with path.open(encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    assert isinstance(schema, dict)
    return schema


def test_evidence_schema_files_exist_and_are_valid_json() -> None:
    for filename in EXPECTED_SCHEMAS:
        load_schema(filename)


def test_evidence_schemas_define_runtime_contract() -> None:
    for filename, expected in EXPECTED_SCHEMAS.items():
        schema = load_schema(filename)

        assert schema["$schema"] == DRAFT_2020_12
        assert schema["$id"].startswith(
            "https://example.local/databricks-automation-bundles/evidence/"
        )
        assert schema["type"] == "object"
        assert schema["additionalProperties"] is False
        assert schema["required"] == expected["required"]
        properties = schema["properties"]
        for property_name, property_constraints in expected["constraints"].items():
            for constraint_path, expected_value in property_constraints.items():
                assert_constraint(
                    properties[property_name],
                    constraint_path,
                    expected_value,
                )


def test_evidence_schemas_add_no_jsonschema_dependency() -> None:
    for filename in ("pyproject.toml", "uv.lock"):
        assert "jsonschema" not in (ROOT / filename).read_text(encoding="utf-8").lower()
