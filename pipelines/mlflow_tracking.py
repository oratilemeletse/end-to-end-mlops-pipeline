"""MLflow experiment tracking helpers."""

from collections.abc import Mapping
from typing import Any

import mlflow
import mlflow.sklearn
from sklearn.base import BaseEstimator


def log_training_run(
    model: BaseEstimator,
    *,
    parameters: Mapping[str, Any],
    metrics: Mapping[str, float],
    experiment_name: str = "mlops-portfolio",
    run_name: str = "baseline-training",
) -> str:
    """Log parameters, metrics, and a scikit-learn model, returning the run ID."""
    mlflow.set_experiment(experiment_name)
    with mlflow.start_run(run_name=run_name) as run:
        for name, value in parameters.items():
            mlflow.log_param(name, value)
        for name, value in metrics.items():
            mlflow.log_metric(name, value)
        mlflow.sklearn.log_model(model, artifact_path="model")
        return run.info.run_id
