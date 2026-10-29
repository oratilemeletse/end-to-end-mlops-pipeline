"""Validate release evidence and register an MLflow model in Azure ML."""

import json
from pathlib import Path
from typing import Any

from azure.ai.ml import MLClient
from azure.ai.ml.constants import AssetTypes
from azure.ai.ml.entities import Model
from azure.identity import DefaultAzureCredential

REQUIRED_PROVENANCE_FIELDS = {
    "data_reference",
    "dependency_versions",
    "model_artifact_uri",
    "parameters",
    "run_id",
    "source_revision",
}
TASK_REQUIRED_METRICS = {
    "classification": {"roc_auc", "recall", "precision"},
    "regression": {
        "mae",
        "rmse",
        "baseline_mae",
        "mae_to_baseline_ratio",
        "rmse_to_baseline_ratio",
    },
    "clustering": {
        "silhouette_score",
        "davies_bouldin_score",
        "minimum_cluster_fraction",
        "stability_score",
    },
}


def load_release_evidence(evidence_path: str | Path) -> dict[str, Any]:
    """Load and validate the evidence required for model registration."""
    path = Path(evidence_path)
    if not path.exists():
        raise FileNotFoundError(f"Release evidence does not exist: {path}")

    try:
        evidence = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"Release evidence is not valid JSON: {path}") from error

    if not isinstance(evidence, dict):
        raise ValueError("Release evidence must be a JSON object")
    if evidence.get("approved") is not True:
        raise ValueError("Model registration requires approved evaluation evidence")

    metrics = evidence.get("metrics")
    if not isinstance(metrics, dict) or not metrics:
        raise ValueError("Release evidence must contain evaluation metrics")
    task_type = str(evidence.get("task_type", "classification"))
    if task_type not in TASK_REQUIRED_METRICS:
        raise ValueError(f"Unsupported release task type: {task_type}")
    missing_metrics = TASK_REQUIRED_METRICS[task_type].difference(metrics)
    if missing_metrics:
        raise ValueError(
            f"{task_type} release evidence is missing metrics: "
            + ", ".join(sorted(missing_metrics))
        )

    provenance = evidence.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Release evidence must contain provenance")
    missing = REQUIRED_PROVENANCE_FIELDS.difference(provenance)
    if missing:
        raise ValueError(
            "Release evidence is missing provenance fields: "
            + ", ".join(sorted(missing))
        )
    for field in REQUIRED_PROVENANCE_FIELDS:
        value = provenance[field]
        if value is None or value == "" or value == {}:
            raise ValueError(f"Release provenance field must not be empty: {field}")
    return evidence


def build_model_asset(
    model_path: str | Path,
    *,
    name: str,
    evidence: dict[str, Any],
    lifecycle_stage: str = "candidate",
) -> Model:
    """Build a traceable Azure ML model asset after local validation."""
    artifact = Path(model_path)
    if not artifact.exists():
        raise FileNotFoundError(f"Model artifact does not exist: {artifact}")
    if lifecycle_stage not in {"candidate", "staging", "approved", "archived"}:
        raise ValueError(f"Unsupported lifecycle stage: {lifecycle_stage}")

    metrics = evidence["metrics"]
    provenance = evidence["provenance"]
    task_type = str(evidence.get("task_type", "classification"))
    tags = {
        "lifecycle_stage": lifecycle_stage,
        "task_type": task_type,
        "mlflow_run_id": str(provenance["run_id"]),
        "source_revision": str(provenance["source_revision"]),
        "data_reference": str(provenance["data_reference"]),
        "approved": "true",
    }
    properties = {
        "model_artifact_uri": str(provenance["model_artifact_uri"]),
        "evaluation_metrics": json.dumps(metrics, sort_keys=True),
        "parameters": json.dumps(provenance["parameters"], sort_keys=True),
        "dependency_versions": json.dumps(
            provenance["dependency_versions"],
            sort_keys=True,
        ),
    }
    if provenance.get("feature_columns"):
        properties["feature_columns"] = json.dumps(
            provenance["feature_columns"],
            sort_keys=True,
        )
    return Model(
        path=str(artifact),
        name=name,
        type=AssetTypes.MLFLOW_MODEL,
        description=f"Evaluated {task_type} release candidate.",
        tags=tags,
        properties=properties,
    )


def register_model(
    model_path: str | Path,
    *,
    evidence_path: str | Path,
    name: str,
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    lifecycle_stage: str = "candidate",
    client: MLClient | None = None,
) -> Model:
    """Register an approved, fully traceable MLflow model artifact."""
    evidence = load_release_evidence(evidence_path)
    model = build_model_asset(
        model_path,
        name=name,
        evidence=evidence,
        lifecycle_stage=lifecycle_stage,
    )
    workspace_client = client or MLClient(
        credential=DefaultAzureCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group,
        workspace_name=workspace_name,
    )
    return workspace_client.models.create_or_update(model)
