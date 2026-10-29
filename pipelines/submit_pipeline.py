"""Submit the governed training pipeline to Azure Machine Learning."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from pipelines.azureml_pipeline import (
    build_customer_intelligence_pipeline,
    build_training_pipeline,
)
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
        "--pipeline-task",
        choices=("classification", "customer-intelligence"),
        default="classification",
    )
    parser.add_argument(
        "--regression-model-name",
        default="retail-spending-regression",
    )
    parser.add_argument(
        "--clustering-model-name",
        default="retail-customer-segmentation",
    )
    parser.add_argument(
        "--experiment-name", default="bank-marketing-release-candidates"
    )
    parser.add_argument("--config-path")
    parser.add_argument("--source-repository")
    parser.add_argument("--source-ref")
    parser.add_argument("--source-revision")
    parser.add_argument("--output-yaml", type=Path)
    return parser.parse_args()


def main() -> None:
    """Build and submit a traceable release-candidate pipeline job."""
    args = parse_args()
    workspace = WorkspaceConfig.from_environment()
    revision = args.source_revision or source_revision()
    if args.pipeline_task == "classification":
        pipeline = build_training_pipeline(
            raw_data_uri=args.data_asset,
            environment=args.environment,
            compute=args.compute,
            subscription_id=workspace.subscription_id,
            resource_group=workspace.resource_group,
            workspace_name=workspace.workspace_name,
            model_name=args.model_name,
            source_revision=revision,
        )
    else:
        config_path = args.config_path or "configs/customer_intelligence.json"
        pipeline = build_customer_intelligence_pipeline(
            raw_data_uri=args.data_asset,
            environment=args.environment,
            compute=args.compute,
            subscription_id=workspace.subscription_id,
            resource_group=workspace.resource_group,
            workspace_name=workspace.workspace_name,
            regression_model_name=args.regression_model_name,
            clustering_model_name=args.clustering_model_name,
            source_revision=revision,
            config_path=config_path,
            source_repository=args.source_repository,
            source_ref=args.source_ref,
        )
    if args.output_yaml:
        args.output_yaml.parent.mkdir(parents=True, exist_ok=True)
        pipeline.dump(args.output_yaml)
        print(f"Azure ML pipeline YAML: {args.output_yaml}")
        return
    client = workspace.create_client()
    submitted = client.jobs.create_or_update(
        pipeline,
        experiment_name=args.experiment_name,
    )
    print(f"Azure ML job: {submitted.name}")
    print(f"Studio URL: {submitted.studio_url}")


if __name__ == "__main__":
    main()
