"""Create Azure ML online and batch endpoints from approved model assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from azure.ai.ml.constants import BatchDeploymentOutputAction
from azure.ai.ml.entities import (
    BatchEndpoint,
    BatchRetrySettings,
    CodeConfiguration,
    ManagedOnlineDeployment,
    ManagedOnlineEndpoint,
    ModelBatchDeployment,
    ModelBatchDeploymentSettings,
    OnlineRequestSettings,
)
from azure.core.exceptions import ResourceNotFoundError

from src.azure_config import WorkspaceConfig

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_deployment_config(path: Path) -> dict[str, Any]:
    """Load and validate environment-specific endpoint settings."""
    if not path.exists():
        raise FileNotFoundError(f"Deployment configuration does not exist: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    required = {"environment", "online", "batch"}
    missing = required.difference(raw)
    if missing:
        raise ValueError(
            "Deployment configuration is missing: " + ", ".join(sorted(missing))
        )
    online = raw["online"]
    batch = raw["batch"]
    if int(online["instance_count"]) < 1:
        raise ValueError("online.instance_count must be at least one")
    if int(batch["instance_count"]) < 1:
        raise ValueError("batch.instance_count must be at least one")
    return raw


def build_online_resources(
    config: dict[str, Any],
    *,
    endpoint_name: str,
    deployment_name: str,
    model: str,
    environment: str,
) -> tuple[ManagedOnlineEndpoint, ManagedOnlineDeployment]:
    """Build an AAD-authenticated online endpoint and isolated deployment."""
    settings = config["online"]
    endpoint = ManagedOnlineEndpoint(
        name=endpoint_name,
        description=f"{config['environment']} Bank Marketing endpoint.",
        auth_mode="aad_token",
        public_network_access=settings["public_network_access"],
        tags={"environment": config["environment"], "model": "bank-marketing"},
    )
    deployment = ManagedOnlineDeployment(
        name=deployment_name,
        endpoint_name=endpoint_name,
        model=model,
        environment=environment,
        code_configuration=CodeConfiguration(
            code=str(PROJECT_ROOT / "deployment" / "online"),
            scoring_script="score.py",
        ),
        instance_type=settings["instance_type"],
        instance_count=int(settings["instance_count"]),
        app_insights_enabled=True,
        request_settings=OnlineRequestSettings(
            max_concurrent_requests_per_instance=int(
                settings["max_concurrent_requests"]
            ),
            request_timeout_ms=int(settings["request_timeout_ms"]),
        ),
        egress_public_network_access="disabled",
        tags={"lifecycle_stage": "candidate"},
    )
    return endpoint, deployment


def build_batch_resources(
    config: dict[str, Any],
    *,
    endpoint_name: str,
    deployment_name: str,
    model: str,
    environment: str,
    compute: str,
) -> tuple[BatchEndpoint, ModelBatchDeployment]:
    """Build a batch endpoint and deployment with bounded retries."""
    settings = config["batch"]
    endpoint = BatchEndpoint(
        name=endpoint_name,
        description=f"{config['environment']} Bank Marketing batch endpoint.",
        auth_mode="aad_token",
        tags={"environment": config["environment"], "model": "bank-marketing"},
    )
    deployment = ModelBatchDeployment(
        name=deployment_name,
        endpoint_name=endpoint_name,
        model=model,
        environment=environment,
        compute=compute,
        code_configuration=CodeConfiguration(
            code=str(PROJECT_ROOT / "deployment" / "batch"),
            scoring_script="score.py",
        ),
        settings=ModelBatchDeploymentSettings(
            mini_batch_size=int(settings["mini_batch_size"]),
            instance_count=int(settings["instance_count"]),
            max_concurrency_per_instance=int(settings["max_concurrency"]),
            output_action=BatchDeploymentOutputAction.APPEND_ROW,
            output_file_name="predictions.csv",
            retry_settings=BatchRetrySettings(
                max_retries=int(settings["max_retries"]),
                timeout=int(settings["timeout_seconds"]),
            ),
            error_threshold=0,
            logging_level="info",
        ),
        tags={"lifecycle_stage": "candidate"},
    )
    return endpoint, deployment


def parse_args() -> argparse.Namespace:
    """Parse deployment arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--online-endpoint", required=True)
    parser.add_argument("--batch-endpoint", required=True)
    parser.add_argument("--deployment-name", required=True)
    parser.add_argument("--compute", required=True)
    return parser.parse_args()


def main() -> None:
    """Create endpoints and candidate deployments without shifting traffic."""
    args = parse_args()
    config = load_deployment_config(args.config)
    client = WorkspaceConfig.from_environment().create_client()
    online_endpoint, online_deployment = build_online_resources(
        config,
        endpoint_name=args.online_endpoint,
        deployment_name=args.deployment_name,
        model=args.model,
        environment=args.environment,
    )
    batch_endpoint, batch_deployment = build_batch_resources(
        config,
        endpoint_name=args.batch_endpoint,
        deployment_name=args.deployment_name,
        model=args.model,
        environment=args.environment,
        compute=args.compute,
    )
    try:
        client.online_endpoints.get(online_endpoint.name)
    except ResourceNotFoundError:
        client.online_endpoints.begin_create_or_update(online_endpoint).result()
    client.online_deployments.begin_create_or_update(online_deployment).result()
    try:
        client.batch_endpoints.get(batch_endpoint.name)
    except ResourceNotFoundError:
        client.batch_endpoints.begin_create_or_update(batch_endpoint).result()
    client.batch_deployments.begin_create_or_update(batch_deployment).result()
    print("Candidate deployments created; online traffic was not changed.")


if __name__ == "__main__":
    main()
