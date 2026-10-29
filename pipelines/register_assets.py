"""Register versioned Azure ML data and environment assets."""

from __future__ import annotations

import argparse
from pathlib import Path

from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import Data, Environment

from src.azure_config import WorkspaceConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    """Parse asset registration arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", required=True)
    parser.add_argument("--data-name", default="bank-marketing-raw")
    parser.add_argument("--data-version", required=True)
    parser.add_argument(
        "--task-type",
        choices=("classification", "customer-intelligence"),
        default="classification",
    )
    parser.add_argument("--environment-name", default="mlops-runtime")
    parser.add_argument("--environment-version", required=True)
    return parser.parse_args()


def main() -> None:
    """Create or update immutable-versioned workspace assets."""
    args = parse_args()
    client = WorkspaceConfig.from_environment().create_client()
    if args.task_type == "classification":
        data_description = "Verified UCI Bank Marketing source CSV."
        data_tags = {"target": "y", "prohibited_feature": "duration"}
    else:
        data_description = "Verified UCI Online Retail transaction CSV."
        data_tags = {
            "tasks": "regression,clustering",
            "target": "derived_next_30d_spend_gbp",
        }
    data = Data(
        name=args.data_name,
        version=args.data_version,
        path=args.data_path,
        type=AssetTypes.URI_FILE,
        description=data_description,
        tags=data_tags,
    )
    environment = Environment(
        name=args.environment_name,
        version=args.environment_version,
        image="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu22.04:20240212.v1",
        conda_file=str(PROJECT_ROOT / "components" / "environment" / "conda.yml"),
        description="Pinned Python runtime for governed machine-learning stages.",
    )
    registered_data = client.data.create_or_update(data)
    registered_environment = client.environments.create_or_update(environment)
    print(f"Data asset: azureml:{registered_data.name}:{registered_data.version}")
    print(
        "Environment asset: "
        f"azureml:{registered_environment.name}:{registered_environment.version}"
    )
