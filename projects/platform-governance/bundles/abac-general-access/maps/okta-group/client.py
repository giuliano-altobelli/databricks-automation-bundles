from __future__ import annotations

from typing import Protocol

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.catalog import PolicyInfo
from databricks.sdk.service.tags import TagPolicy


class Catalogs(Protocol):
    def get(self, name: str) -> object: ...


class Schemas(Protocol):
    def get(self, full_name: str) -> object: ...


class Tags(Protocol):
    def get_tag_policy(self, tag_key: str) -> TagPolicy: ...


class Policies(Protocol):
    def create_policy(self, policy_info: PolicyInfo) -> PolicyInfo: ...

    def get_policy(
        self,
        on_securable_type: str,
        on_securable_fullname: str,
        name: str,
    ) -> PolicyInfo: ...

    def update_policy(
        self,
        on_securable_type: str,
        on_securable_fullname: str,
        name: str,
        policy_info: PolicyInfo,
        *,
        update_mask: str,
    ) -> PolicyInfo: ...


class Client(Protocol):
    catalogs: Catalogs
    schemas: Schemas
    tag_policies: Tags
    policies: Policies


def workspace() -> Client:
    return WorkspaceClient()
