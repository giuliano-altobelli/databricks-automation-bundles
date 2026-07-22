import importlib
import sys
from collections.abc import Iterator
from copy import deepcopy
from dataclasses import FrozenInstanceError, is_dataclass, replace
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from databricks.sdk.service.catalog import PolicyInfo

ROOT = Path(__file__).resolve().parents[1]
ABAC = ROOT / "projects" / "platform-governance" / "bundles" / "abac"
APPLY = (
    ROOT
    / "projects"
    / "platform-governance"
    / "bundles"
    / "abac-general-access"
    / "maps"
    / "okta-group"
    / "apply.sql"
)
MODULES = (
    "client",
    "command",
    "definition",
    "okta",
    "preflight",
    "reconcile",
    "render",
    "state",
)

NAME = "abac_demo_okta_group_row_filter"
COMMENT = "Filter governed demo rows by the querying user's Okta group membership."
CATALOG = "dev_abac_demo"
SCHEMA = "dev_security.policies"
FUNCTION = f"{SCHEMA}.can_read_okta_group"
PRINCIPAL = "okta-databricks-users"
EXCEPTION = "giulianoaltobelli@gmail.com"
BOUNDARY = "abac_boundary"
BOUNDARY_VALUE = "abac_general_access_okta_group"
PROTECTED = "protected_column"
PROTECTED_VALUE = "okta_group_names"
ALIAS = "okta_group_names_value"
CONDITION = f"has_tag_value('{BOUNDARY}','{BOUNDARY_VALUE}')"
COLUMN = f"has_tag_value('{PROTECTED}','{PROTECTED_VALUE}')"
IDENTITY = ("CATALOG", CATALOG, NAME)
COUPLED = ("policy_type", "row_filter", "column_mask")


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> Iterator[SimpleNamespace]:
    assert ABAC.is_dir(), f"{ABAC} must provide the shared ABAC policy runtime"
    monkeypatch.syspath_prepend(str(ABAC))
    previous = {name: sys.modules[name] for name in MODULES if name in sys.modules}
    try:
        for name in MODULES:
            sys.modules.pop(name, None)
        importlib.import_module("okta")
        loaded = SimpleNamespace(
            **{name: importlib.import_module(name) for name in MODULES}
        )
        yield loaded
    finally:
        for name in MODULES:
            sys.modules.pop(name, None)
        sys.modules.update(previous)


@pytest.fixture
def policy(runtime: SimpleNamespace) -> ModuleType:
    return runtime.definition


@pytest.fixture
def okta(runtime: SimpleNamespace) -> ModuleType:
    return runtime.okta


@pytest.fixture
def preflight(runtime: SimpleNamespace) -> ModuleType:
    return runtime.preflight


@pytest.fixture
def reconcile(runtime: SimpleNamespace) -> ModuleType:
    return runtime.reconcile


def location(policy: ModuleType) -> Any:
    return policy.Location(catalog=CATALOG, schema=SCHEMA)


def contract(policy: ModuleType) -> Any:
    return policy.Definition(
        name=NAME,
        comment=COMMENT,
        scope="CATALOG",
        target="TABLE",
        kind="POLICY_TYPE_ROW_FILTER",
        principals=(PRINCIPAL,),
        exceptions=(EXCEPTION,),
        condition=policy.Tag(key=BOUNDARY, value=BOUNDARY_VALUE),
        matches=(
            policy.Match(
                tag=policy.Tag(key=PROTECTED, value=PROTECTED_VALUE),
                alias=ALIAS,
            ),
        ),
        filter=policy.Filter(function="can_read_okta_group", using=(ALIAS,)),
    )


def alternative(policy: ModuleType) -> Any:
    return policy.Definition(
        name="alternate_row_filter",
        comment="Filter rows through another immutable policy.",
        scope="CATALOG",
        target="TABLE",
        kind="POLICY_TYPE_ROW_FILTER",
        principals=("alternate-group",),
        exceptions=(),
        condition=policy.Tag(key="boundary", value="alternate"),
        matches=(
            policy.Match(
                tag=policy.Tag(key="protected", value="alternate_column"),
                alias="protected_value",
            ),
        ),
        filter=policy.Filter(
            function="alternate_filter",
            using=("protected_value",),
        ),
    )


def serialize(value: Any) -> Any:
    if hasattr(value, "as_dict"):
        return value.as_dict()
    if isinstance(value, list):
        return [serialize(item) for item in value]
    if isinstance(value, tuple):
        return [serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    if hasattr(value, "value"):
        return value.value
    return value


class Model:
    def __init__(self, **values: Any) -> None:
        self.values = values
        for name, value in values.items():
            setattr(self, name, value)

    def as_dict(self) -> dict[str, Any]:
        return {
            name: serialize(value)
            for name, value in self.values.items()
            if value is not None
        }

    def clone(self, **changes: Any) -> "Model":
        values = deepcopy(self.values)
        values.update(changes)
        return Model(**values)


def payload(place: Any) -> dict[str, Any]:
    return {
        "comment": COMMENT,
        "except_principals": [EXCEPTION],
        "for_securable_type": "TABLE",
        "match_columns": [{"alias": ALIAS, "condition": COLUMN}],
        "name": NAME,
        "on_securable_fullname": place.catalog,
        "on_securable_type": "CATALOG",
        "policy_type": "POLICY_TYPE_ROW_FILTER",
        "row_filter": {
            "function_name": f"{place.schema}.can_read_okta_group",
            "using": [{"alias": ALIAS}],
        },
        "to_principals": [PRINCIPAL],
        "when_condition": CONDITION,
    }


def mutable(place: Any) -> dict[str, Any]:
    values = payload(place)
    for field in ("name", "on_securable_fullname", "on_securable_type"):
        del values[field]
    return values


def snapshot(place: Any, **changes: Any) -> Model:
    values = {
        **payload(place),
        "column_mask": None,
        "created_at": 1,
        "created_by": "creator@example.com",
        "id": "policy-id",
        "updated_at": 2,
        "updated_by": "updater@example.com",
    }
    values["match_columns"] = [Model(**item) for item in values["match_columns"]]
    row = values["row_filter"]
    values["row_filter"] = Model(
        function_name=row["function_name"],
        using=[Model(**item) for item in row["using"]],
    )
    values.update(changes)
    return Model(**values)


class Catalogs:
    def __init__(self, events: list[tuple[str, Any]]) -> None:
        self.events = events
        self.failures: dict[str, Exception] = {}

    def get(self, name: str) -> Model:
        self.events.append(("catalogs.get", {"name": name}))
        if name in self.failures:
            raise self.failures[name]
        return Model(name=name)


class Schemas:
    def __init__(self, events: list[tuple[str, Any]]) -> None:
        self.events = events
        self.failures: dict[str, Exception] = {}

    def get(self, full_name: str) -> Model:
        self.events.append(("schemas.get", {"full_name": full_name}))
        if full_name in self.failures:
            raise self.failures[full_name]
        return Model(full_name=full_name)


class Tags:
    def __init__(self, events: list[tuple[str, Any]]) -> None:
        self.events = events
        self.failures: dict[str, Exception] = {}
        self.values: dict[str, tuple[str, ...] | None] = {
            BOUNDARY: (BOUNDARY_VALUE,),
            PROTECTED: (PROTECTED_VALUE,),
        }
        self.keys = {BOUNDARY: BOUNDARY, PROTECTED: PROTECTED}

    def get_tag_policy(self, tag_key: str) -> Model:
        self.events.append(("tag_policies.get_tag_policy", {"tag_key": tag_key}))
        if tag_key in self.failures:
            raise self.failures[tag_key]
        values = self.values[tag_key]
        entries = None if values is None else [Model(name=value) for value in values]
        return Model(tag_key=self.keys[tag_key], values=entries)


class Policies:
    def __init__(self, events: list[tuple[str, Any]]) -> None:
        self.events = events
        self.current: Any = None
        self.after: Any = None
        self.missing: Exception | None = None
        self.conflict: Exception | None = None
        self.update_missing: Exception | None = None

    def get_policy(
        self,
        on_securable_type: str,
        on_securable_fullname: str,
        name: str,
    ) -> Any:
        self.events.append(
            (
                "policies.get_policy",
                {
                    "on_securable_type": serialize(on_securable_type),
                    "on_securable_fullname": on_securable_fullname,
                    "name": name,
                },
            )
        )
        if self.current is None:
            assert self.missing is not None
            raise self.missing
        return self.current

    def create_policy(self, policy_info: Any) -> Any:
        self.events.append(("policies.create_policy", {"policy_info": policy_info}))
        if self.conflict is not None:
            failure = self.conflict
            self.conflict = None
            if self.after is not None:
                self.current = self.after
            raise failure
        self.current = self.after if self.after is not None else policy_info
        return self.current

    def update_policy(
        self,
        on_securable_type: str,
        on_securable_fullname: str,
        name: str,
        policy_info: Any,
        update_mask: str,
    ) -> Any:
        self.events.append(
            (
                "policies.update_policy",
                {
                    "on_securable_type": serialize(on_securable_type),
                    "on_securable_fullname": on_securable_fullname,
                    "name": name,
                    "policy_info": policy_info,
                    "update_mask": update_mask,
                },
            )
        )
        if self.update_missing is not None:
            failure = self.update_missing
            self.update_missing = None
            self.current = None
            raise failure
        self.current = self.after if self.after is not None else policy_info
        return self.current


class Workspace:
    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []
        self.catalogs = Catalogs(self.events)
        self.schemas = Schemas(self.events)
        self.tag_policies = Tags(self.events)
        self.policies = Policies(self.events)


def event(workspace: Workspace, name: str) -> dict[str, Any]:
    matches = [value for kind, value in workspace.events if kind == name]
    assert len(matches) == 1
    return matches[0]


def missing(reconcile: ModuleType) -> Exception:
    return reconcile.NotFound("policy does not exist")


def conflict(reconcile: ModuleType) -> Exception:
    return reconcile.ResourceConflict("policy already exists")


def test_policy_is_one_complete_immutable_semantic_definition(
    policy: ModuleType,
    okta: ModuleType,
    runtime: SimpleNamespace,
) -> None:
    assert okta.POLICY == contract(policy)
    with pytest.raises(FrozenInstanceError):
        okta.POLICY.name = "another_policy"
    for name in (
        "Location",
        "Tag",
        "Match",
        "Filter",
        "Definition",
        "Result",
    ):
        kind = getattr(policy, name)
        assert is_dataclass(kind), name
        assert kind.__dataclass_params__.frozen is True, name
    assert is_dataclass(runtime.state.Snapshot)
    assert runtime.state.Snapshot.__dataclass_params__.frozen is True
    assert (
        f":schema || '.{okta.POLICY.filter.function}'"
        in APPLY.read_text(encoding="utf-8")
    )


def test_only_location_changes_between_uat_and_prod(
    policy: ModuleType,
    okta: ModuleType,
    runtime: SimpleNamespace,
) -> None:
    uat = location(policy)
    prod = policy.Location(
        catalog="prod_abac_demo",
        schema="prod_security.policies",
    )

    assert okta.POLICY == contract(policy)
    assert okta.POLICY.filter.function == "can_read_okta_group"
    assert serialize(runtime.render.information(okta.POLICY, uat, True)) == payload(uat)
    assert serialize(runtime.render.information(okta.POLICY, prod, True)) == payload(prod)


def test_shared_controller_reconciles_a_distinct_immutable_definition(
    policy: ModuleType,
    reconcile: ModuleType,
    runtime: SimpleNamespace,
) -> None:
    definition = alternative(policy)
    place = policy.Location(catalog="alternate_catalog", schema="security.policies")
    workspace = Workspace()
    workspace.policies.missing = missing(reconcile)
    workspace.policies.after = runtime.render.information(definition, place, True)

    result = reconcile.reconcile(workspace, definition, place)

    assert result == policy.Result(
        action="created",
        identity=("CATALOG", "alternate_catalog", "alternate_row_filter"),
        fields=(),
    )
    created = serialize(event(workspace, "policies.create_policy")["policy_info"])
    assert created["name"] == "alternate_row_filter"
    assert created["on_securable_fullname"] == "alternate_catalog"
    assert created["to_principals"] == ["alternate-group"]
    assert created["when_condition"] == "has_tag_value('boundary','alternate')"
    assert created["row_filter"] == {
        "function_name": "security.policies.alternate_filter",
        "using": [{"alias": "protected_value"}],
    }


def test_shared_preflight_validates_a_distinct_immutable_definition(
    policy: ModuleType,
    preflight: ModuleType,
) -> None:
    definition = alternative(policy)
    place = policy.Location(catalog="alternate_catalog", schema="security.policies")
    workspace = Workspace()
    workspace.tag_policies.keys = {
        "boundary": "boundary",
        "protected": "protected",
    }
    workspace.tag_policies.values = {
        "boundary": ("alternate",),
        "protected": ("alternate_column",),
    }

    assert preflight.validate(workspace, definition, place) is None
    assert workspace.events == [
        ("catalogs.get", {"name": "alternate_catalog"}),
        ("schemas.get", {"full_name": "security.policies"}),
        ("tag_policies.get_tag_policy", {"tag_key": "boundary"}),
        ("tag_policies.get_tag_policy", {"tag_key": "protected"}),
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    (("scope", "INVALID_SCOPE"), ("target", "INVALID_TARGET"), ("kind", "INVALID_KIND")),
)
def test_preflight_rejects_an_unrenderable_definition_before_remote_reads(
    field: str,
    value: str,
    policy: ModuleType,
    okta: ModuleType,
    preflight: ModuleType,
) -> None:
    workspace = Workspace()
    definition = replace(okta.POLICY, **{field: value})

    with pytest.raises(preflight.Invalid) as captured:
        preflight.validate(workspace, definition, location(policy))

    assert captured.value.errors[0].resource == "definition"
    assert value in captured.value.errors[0].message
    assert workspace.events == []


def test_preflight_rejects_a_non_catalog_policy_scope_before_remote_reads(
    policy: ModuleType,
    okta: ModuleType,
    preflight: ModuleType,
) -> None:
    workspace = Workspace()
    definition = replace(okta.POLICY, scope="SCHEMA")

    with pytest.raises(preflight.Invalid) as captured:
        preflight.validate(workspace, definition, location(policy))

    assert captured.value.errors[0].resource == "scope"
    assert "SCHEMA" in captured.value.errors[0].message
    assert "CATALOG" in captured.value.errors[0].message
    assert workspace.events == []


def test_preflight_reads_every_dependency_without_touching_policies(
    policy: ModuleType,
    okta: ModuleType,
    preflight: ModuleType,
) -> None:
    workspace = Workspace()

    assert preflight.validate(workspace, okta.POLICY, location(policy)) is None
    assert workspace.events == [
        ("catalogs.get", {"name": CATALOG}),
        ("schemas.get", {"full_name": SCHEMA}),
        ("tag_policies.get_tag_policy", {"tag_key": BOUNDARY}),
        ("tag_policies.get_tag_policy", {"tag_key": PROTECTED}),
    ]


def test_dev_preflight_reads_only_the_personal_function_schema(
    policy: ModuleType,
    okta: ModuleType,
    preflight: ModuleType,
) -> None:
    workspace = Workspace()
    place = policy.Location(
        catalog=None,
        schema="personal.developer",
    )

    assert preflight.validate(workspace, okta.POLICY, place) is None
    assert workspace.events == [
        ("schemas.get", {"full_name": "personal.developer"}),
    ]


def test_preflight_aggregates_missing_and_unreadable_dependencies_fail_closed(
    policy: ModuleType,
    okta: ModuleType,
    preflight: ModuleType,
) -> None:
    workspace = Workspace()
    workspace.catalogs.failures[CATALOG] = RuntimeError("catalog denied")
    workspace.schemas.failures[SCHEMA] = RuntimeError("schema missing")
    workspace.tag_policies.values[BOUNDARY] = ("another-value",)
    workspace.tag_policies.failures[PROTECTED] = RuntimeError("tag unavailable")

    with pytest.raises(preflight.Invalid) as captured:
        preflight.validate(workspace, okta.POLICY, location(policy))

    errors = captured.value.errors
    assert isinstance(errors, tuple)
    assert len(errors) == 4
    message = "\n".join(str(error) for error in errors)
    for fragment in (
        CATALOG,
        "catalog denied",
        SCHEMA,
        "schema missing",
        BOUNDARY,
        BOUNDARY_VALUE,
        PROTECTED,
        PROTECTED_VALUE,
        "tag unavailable",
    ):
        assert fragment in message
    assert [name for name, _ in workspace.events] == [
        "catalogs.get",
        "schemas.get",
        "tag_policies.get_tag_policy",
        "tag_policies.get_tag_policy",
    ]


@pytest.mark.parametrize(
    ("tag", "value"),
    ((BOUNDARY, BOUNDARY_VALUE), (PROTECTED, PROTECTED_VALUE)),
)
@pytest.mark.parametrize("values", [None, ()])
def test_preflight_rejects_a_governed_tag_without_allowed_values(
    tag: str,
    value: str,
    values: tuple[str, ...] | None,
    policy: ModuleType,
    okta: ModuleType,
    preflight: ModuleType,
) -> None:
    workspace = Workspace()
    workspace.tag_policies.values[tag] = values

    with pytest.raises(preflight.Invalid) as captured:
        preflight.validate(workspace, okta.POLICY, location(policy))

    message = "\n".join(str(error) for error in captured.value.errors)
    assert tag in message
    assert value in message
    assert all(not name.startswith("policies.") for name, _ in workspace.events)


def test_preflight_rejects_a_mismatched_governed_tag_key(
    policy: ModuleType,
    okta: ModuleType,
    preflight: ModuleType,
) -> None:
    workspace = Workspace()
    workspace.tag_policies.keys[BOUNDARY] = "another_boundary"

    with pytest.raises(preflight.Invalid) as captured:
        preflight.validate(workspace, okta.POLICY, location(policy))

    message = "\n".join(str(error) for error in captured.value.errors)
    assert BOUNDARY in message
    assert "another_boundary" in message
    assert all(not name.startswith("policies.") for name, _ in workspace.events)


def test_reconcile_creates_the_complete_policy_then_verifies_remote_state(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    workspace.policies.missing = missing(reconcile)
    workspace.policies.after = snapshot(place)

    result = reconcile.reconcile(workspace, okta.POLICY, place)

    assert result == policy.Result(action="created", identity=IDENTITY, fields=())
    creation = event(workspace, "policies.create_policy")
    assert isinstance(creation["policy_info"], PolicyInfo)
    assert serialize(creation["policy_info"]) == payload(place)
    assert [name for name, _ in workspace.events] == [
        "policies.get_policy",
        "policies.create_policy",
        "policies.get_policy",
    ]


def test_reconcile_accepts_a_concurrent_equivalent_create(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    workspace.policies.missing = missing(reconcile)
    workspace.policies.conflict = conflict(reconcile)
    workspace.policies.after = snapshot(place)

    result = reconcile.reconcile(workspace, okta.POLICY, place)

    assert result == policy.Result(action="unchanged", identity=IDENTITY, fields=())
    assert [name for name, _ in workspace.events] == [
        "policies.get_policy",
        "policies.create_policy",
        "policies.get_policy",
    ]


def test_reconcile_preserves_a_create_conflict_when_exact_policy_is_absent(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    workspace.policies.missing = missing(reconcile)
    failure = conflict(reconcile)
    workspace.policies.conflict = failure

    with pytest.raises(reconcile.ResourceConflict) as captured:
        reconcile.reconcile(workspace, okta.POLICY, place)

    assert captured.value is failure
    assert [name for name, _ in workspace.events] == [
        "policies.get_policy",
        "policies.create_policy",
        "policies.get_policy",
    ]


def test_reconcile_leaves_an_equal_policy_unchanged(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    workspace.policies.current = snapshot(place)

    result = reconcile.reconcile(workspace, okta.POLICY, place)

    assert result == policy.Result(action="unchanged", identity=IDENTITY, fields=())
    assert [name for name, _ in workspace.events] == ["policies.get_policy"]


def test_reconcile_normalizes_server_spacing_in_owned_tag_conditions(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    workspace.policies.current = snapshot(
        place,
        when_condition=(
            " HAS_TAG_VALUE ( 'abac_boundary' , "
            "'abac_general_access_okta_group' ) "
        ),
        match_columns=[
            Model(
                alias=ALIAS,
                condition=(
                    "has_tag_value ( 'protected_column' , 'okta_group_names' )"
                ),
            )
        ],
    )

    result = reconcile.reconcile(workspace, okta.POLICY, place)

    assert result == policy.Result(action="unchanged", identity=IDENTITY, fields=())
    assert [name for name, _ in workspace.events] == ["policies.get_policy"]


@pytest.mark.parametrize(
    "field",
    (
        "comment",
        "except_principals",
        "for_securable_type",
        "match_columns",
        "to_principals",
        "when_condition",
    ),
)
def test_reconcile_partially_updates_one_independent_field_with_an_exact_mask(
    field: str,
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    drift = {
        "comment": "old comment",
        "except_principals": [],
        "for_securable_type": "SCHEMA",
        "match_columns": [Model(condition="has_tag('other')", alias="other")],
        "to_principals": ["another-group"],
        "when_condition": "has_tag('other')",
    }[field]
    workspace.policies.current = snapshot(place, **{field: drift})
    workspace.policies.after = snapshot(place)

    result = reconcile.reconcile(workspace, okta.POLICY, place)

    assert result == policy.Result(action="updated", identity=IDENTITY, fields=(field,))
    update = event(workspace, "policies.update_policy")
    assert update["on_securable_type"] == "CATALOG"
    assert update["on_securable_fullname"] == CATALOG
    assert update["name"] == NAME
    assert update["update_mask"] == field
    assert isinstance(update["policy_info"], PolicyInfo)
    assert serialize(update["policy_info"]) == mutable(place)
    assert [name for name, _ in workspace.events] == [
        "policies.get_policy",
        "policies.update_policy",
        "policies.get_policy",
    ]


def test_reconcile_combines_independent_drift_in_definition_order(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    fields = ("comment", "to_principals", "when_condition")
    workspace.policies.current = snapshot(
        place,
        comment="old comment",
        to_principals=["another-group"],
        when_condition="has_tag('other')",
    )
    workspace.policies.after = snapshot(place)

    result = reconcile.reconcile(workspace, okta.POLICY, place)

    assert result == policy.Result(action="updated", identity=IDENTITY, fields=fields)
    update = event(workspace, "policies.update_policy")
    assert update["update_mask"] == ",".join(fields)
    assert serialize(update["policy_info"]) == mutable(place)


def test_reconcile_updates_only_a_drifted_row_filter(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    workspace.policies.current = snapshot(
        place,
        row_filter=Model(
            function_name="dev_security.policies.another_filter",
            using=[Model(alias="another")],
        ),
    )
    workspace.policies.after = snapshot(place)

    result = reconcile.reconcile(workspace, okta.POLICY, place)

    assert result == policy.Result(
        action="updated",
        identity=IDENTITY,
        fields=("row_filter",),
    )
    update = event(workspace, "policies.update_policy")
    assert update["update_mask"] == "row_filter"
    assert serialize(update["policy_info"]) == mutable(place)


def test_reconcile_clears_only_a_stale_column_mask(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    workspace.policies.current = snapshot(
        place,
        column_mask=Model(
            function_name="dev_security.policies.mask",
            on_column=ALIAS,
            using=[],
        ),
    )
    workspace.policies.after = snapshot(place)

    result = reconcile.reconcile(workspace, okta.POLICY, place)

    assert result == policy.Result(
        action="updated",
        identity=IDENTITY,
        fields=("column_mask",),
    )
    update = event(workspace, "policies.update_policy")
    assert update["update_mask"] == "column_mask"
    assert "column_mask" not in serialize(update["policy_info"])


def test_reconcile_replaces_coupled_bodies_when_policy_type_drifts(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    workspace.policies.current = snapshot(
        place,
        policy_type="POLICY_TYPE_COLUMN_MASK",
    )
    workspace.policies.after = snapshot(place)

    result = reconcile.reconcile(workspace, okta.POLICY, place)

    assert result == policy.Result(action="updated", identity=IDENTITY, fields=COUPLED)
    update = event(workspace, "policies.update_policy")
    assert update["update_mask"] == ",".join(COUPLED)
    assert serialize(update["policy_info"]) == mutable(place)


def test_reconcile_rejects_an_identity_mismatch_without_mutation(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    workspace.policies.current = snapshot(place, name="another_policy")

    with pytest.raises(RuntimeError):
        reconcile.reconcile(workspace, okta.POLICY, place)

    assert [name for name, _ in workspace.events] == ["policies.get_policy"]


def test_reconcile_restarts_once_when_policy_disappears_during_update(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    workspace.policies.current = snapshot(place, comment="old comment")
    workspace.policies.missing = missing(reconcile)
    workspace.policies.update_missing = missing(reconcile)
    workspace.policies.after = snapshot(place)

    result = reconcile.reconcile(workspace, okta.POLICY, place)

    assert result == policy.Result(action="created", identity=IDENTITY, fields=())
    assert [name for name, _ in workspace.events] == [
        "policies.get_policy",
        "policies.update_policy",
        "policies.get_policy",
        "policies.create_policy",
        "policies.get_policy",
    ]


def test_reconcile_fails_when_post_update_verification_does_not_converge(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    stale = snapshot(place, comment="old comment")
    workspace.policies.current = stale
    workspace.policies.after = stale

    with pytest.raises(RuntimeError):
        reconcile.reconcile(workspace, okta.POLICY, place)

    assert [name for name, _ in workspace.events] == [
        "policies.get_policy",
        "policies.update_policy",
        "policies.get_policy",
    ]


def test_reconcile_fails_when_post_create_verification_does_not_converge(
    policy: ModuleType,
    okta: ModuleType,
    reconcile: ModuleType,
) -> None:
    workspace = Workspace()
    place = location(policy)
    workspace.policies.missing = missing(reconcile)
    workspace.policies.after = snapshot(place, when_condition="has_tag('other')")

    with pytest.raises(RuntimeError):
        reconcile.reconcile(workspace, okta.POLICY, place)

    assert [name for name, _ in workspace.events] == [
        "policies.get_policy",
        "policies.create_policy",
        "policies.get_policy",
    ]
