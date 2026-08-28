"""Validated Azure ML workspace configuration from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from azure.ai.ml import MLClient
from azure.identity import DefaultAzureCredential


@dataclass(frozen=True)
class WorkspaceConfig:
    """Non-secret identifiers required to address an Azure ML workspace."""

    subscription_id: str
    resource_group: str
    workspace_name: str

    @classmethod
    def from_environment(cls) -> WorkspaceConfig:
        """Load required workspace identifiers without embedding credentials."""
        names = {
            "subscription_id": "AZURE_SUBSCRIPTION_ID",
            "resource_group": "AZURE_RESOURCE_GROUP",
            "workspace_name": "AZURE_ML_WORKSPACE",
        }
        values: dict[str, str] = {}
        missing: list[str] = []
        for field, variable in names.items():
            value = os.getenv(variable, "").strip()
            if value:
                values[field] = value
            else:
                missing.append(variable)
        if missing:
            raise ValueError(
                "Missing required Azure ML environment variables: " + ", ".join(missing)
            )
        return cls(**values)

    def create_client(self) -> MLClient:
        """Create an Azure ML client using the default credential chain."""
        return MLClient(
            credential=DefaultAzureCredential(),
            subscription_id=self.subscription_id,
            resource_group_name=self.resource_group,
            workspace_name=self.workspace_name,
        )
