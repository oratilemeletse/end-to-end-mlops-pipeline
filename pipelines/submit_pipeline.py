"""Submit the governed training pipeline to Azure Machine Learning."""

from __future__ import annotations

import argparse
import os
import subprocess

from pipelines.azureml_pipeline import build_training_pipeline
from src.azure_config import WorkspaceConfig


def source_revision() -> str:
    """Return the required source revision for cloud lineage."""
    explicit = os.getenv("GITHUB_SHA", "").strip()
    if explicit:
        return explicit
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def parse_args() -> argparse.Namespace:
    """Parse pipeline submission arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-asset", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--compute", required=True)
    parser.add_argument("--model-name", default="bank-marketing")
    parser.add_argument(
        "--experiment-name", default="bank-marketing-release-candidates"
    )
    return parser.parse_args()


def main() -> None:
    """Build and submit a traceable release-candidate pipeline job."""
    args = parse_args()
    workspace = WorkspaceConfig.from_environment()
    client = workspace.create_client()
    pipeline = build_training_pipeline(
        raw_data_uri=args.data_asset,
        environment=args.environment,
        compute=args.compute,
        subscription_id=workspace.subscription_id,
        resource_group=workspace.resource_group,
        workspace_name=workspace.workspace_name,
        model_name=args.model_name,
        source_revision=source_revision(),
    )
    submitted = client.jobs.create_or_update(
        pipeline,
        experiment_name=args.experiment_name,
    )
    print(f"Azure ML job: {submitted.name}")
    print(f"Studio URL: {submitted.studio_url}")


if __name__ == "__main__":
    main()
